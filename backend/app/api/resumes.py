import os
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.core.rate_limit_deps import expensive_rate_limiter
from app.core import storage
from app.models.user import User
from app.models.resume import Resume
from app.schemas.resume import ResumeResponse, ResumeParsedResponse
from app.services.resume_parser import parse_and_store

logger = logging.getLogger("app.api.resumes")

router = APIRouter(prefix="/resumes", tags=["resumes"])

# Phase 5E.6 - storage is centralized in app.core.storage; UPLOAD_DIR is the
# effective root (default = STORAGE_ROOT -> backend/uploads) and may be
# patched by tests.
UPLOAD_DIR = str(storage.storage_root())
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
_UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB stream chunks


def _stream_upload(file: UploadFile, max_size: int, chunk_size: int):
    """Return a zero-arg chunk reader that enforces ``max_size``.

    Streams the upload in bounded pieces instead of buffering an arbitrarily
    large body in memory. Raises ``ValueError`` when the cumulative size
    exceeds ``max_size`` (cleanly aborting before the file is written).
    """
    total = 0

    def _read():
        nonlocal total
        chunk = file.file.read(chunk_size)
        total += len(chunk)
        if total > max_size:
            raise ValueError("File size must be less than 10MB")
        return chunk

    return _read


def _get_own_resume(resume_id: str, user: User, db: Session) -> Resume:
    """Fetch a resume belonging to the requesting user or 404."""
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.get("", response_model=list[ResumeResponse])
def list_resumes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resumes = db.query(Resume).filter(Resume.user_id == user.id).order_by(Resume.created_at.desc()).all()
    return resumes


@router.post("", response_model=ResumeResponse, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    stored_name = storage.safe_stored_filename(".pdf")
    try:
        file_path = storage.write_upload_atomic(
            user.id,
            stored_name,
            _stream_upload(file, max_size=MAX_FILE_SIZE, chunk_size=_UPLOAD_CHUNK_SIZE),
            max_size=MAX_FILE_SIZE,
            root=Path(UPLOAD_DIR),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError:
        logger.error("Resume upload failed to write to disk user_id=%s", user.id)
        raise HTTPException(status_code=500, detail="File upload failed")

    file_size = str(_os_path_size(file_path))
    resume = Resume(
        user_id=user.id,
        filename=stored_name,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        is_master=False,
        parsing_status="pending",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    # Trigger parsing synchronously. Parsing failure must never remove the
    # original resume or break the upload response.
    parse_and_store(db, resume)
    db.refresh(resume)
    return resume


@router.get("/{resume_id}/parsed", response_model=ResumeParsedResponse)
def get_parsed_resume(
    resume_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _get_own_resume(resume_id, user, db)
    return ResumeParsedResponse(
        resume_id=resume.id,
        parsing_status=resume.parsing_status,
        parsed_at=resume.parsed_at,
        parsing_error=resume.parsing_error,
        data=resume.parsed_data or {},
    )


@router.post("/{resume_id}/parse", response_model=ResumeParsedResponse, dependencies=[Depends(expensive_rate_limiter)])
def reparse_resume(
    resume_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _get_own_resume(resume_id, user, db)
    if not os.path.exists(resume.file_path):
        raise HTTPException(status_code=404, detail="Resume file not found on disk")

    parse_and_store(db, resume)
    db.refresh(resume)
    return ResumeParsedResponse(
        resume_id=resume.id,
        parsing_status=resume.parsing_status,
        parsed_at=resume.parsed_at,
        parsing_error=resume.parsing_error,
        data=resume.parsed_data or {},
    )


@router.put("/{resume_id}/master", response_model=ResumeResponse)
def set_master_resume(
    resume_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _get_own_resume(resume_id, user, db)

    db.query(Resume).filter(Resume.user_id == user.id).update({"is_master": False})
    resume.is_master = True
    db.commit()
    db.refresh(resume)
    return resume


@router.delete("/{resume_id}", status_code=204)
def delete_resume(
    resume_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = _get_own_resume(resume_id, user, db)

    # Capture the path before the delete: after commit the row is gone, so a
    # post-commit attribute access would raise an expired-object error.
    file_path = resume.file_path

    # Dependent records derived from this resume (ResumeJobAnalysis,
    # TailoredResume, CoverLetter) are removed via ORM cascade on the Resume
    # model. The commit is atomic: either the resume and all its directly
    # derived records are removed, or the whole transaction rolls back.
    db.delete(resume)
    db.commit()

    # Remove the stored PDF only after a successful commit so a failed
    # transaction never leaves the database pointing at a deleted file. This
    # step is best-effort: a leftover file on disk must never surface as an
    # error for an already-committed deletion.
    storage.delete_file_safely(user.id, file_path, root=Path(UPLOAD_DIR))


def _os_path_size(path: str) -> int:
    """Return the on-disk byte size of ``path`` (best-effort)."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0
