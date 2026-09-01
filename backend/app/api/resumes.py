import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.resume import Resume
from app.schemas.resume import ResumeResponse, ResumeParsedResponse
from app.services.resume_parser import parse_and_store

logger = logging.getLogger("app.api.resumes")

router = APIRouter(prefix="/resumes", tags=["resumes"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


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

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")

    user_dir = os.path.join(UPLOAD_DIR, user.id)
    os.makedirs(user_dir, exist_ok=True)

    file_id = str(uuid.uuid4())
    filename = f"{file_id}.pdf"
    file_path = os.path.join(user_dir, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    resume = Resume(
        user_id=user.id,
        filename=filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=str(len(content)),
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


@router.post("/{resume_id}/parse", response_model=ResumeParsedResponse)
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
    if resume.file_path:
        try:
            if os.path.exists(resume.file_path):
                os.remove(resume.file_path)
        except OSError:
            logger.warning("Could not remove resume file from disk after a committed deletion")
