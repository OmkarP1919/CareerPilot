"""Resume Export API (Phase 3C).

GET /resumes/tailored/{tailored_resume_id}/export/pdf
GET /resumes/tailored/{tailored_resume_id}/export/docx

Exports an already-saved TailoredResume as a downloadable file. The export
NEVER calls the AI provider - it formats the stored, approved content. Strict
ownership checks prevent one user from exporting another user's resume.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.tailored_resume import TailoredResume
from app.services import resume_export

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes/tailored", tags=["resume-export"])


def _get_own_tailored(tailored_resume_id: str, user: User, db: Session) -> TailoredResume:
    record = (
        db.query(TailoredResume)
        .filter(
            TailoredResume.id == tailored_resume_id,
            TailoredResume.user_id == user.id,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Tailored resume not found")
    return record


def _export(tailored_resume_id: str, fmt: str, user: User, db: Session) -> Response:
    try:
        record = _get_own_tailored(tailored_resume_id, user, db)

        resume = (
            db.query(Resume).filter(Resume.id == record.source_resume_id).first()
        )
        job = db.query(Job).filter(Job.id == record.job_id).first()

        if fmt == "pdf":
            content = resume_export.generate_pdf(record, resume)
            media_type = resume_export.PDF_MIME
            ext = "pdf"
        else:
            content = resume_export.generate_docx(record, resume)
            media_type = resume_export.DOCX_MIME
            ext = "docx"

        filename = resume_export.build_export_filename(
            job.title if job else None,
            job.company if job else None,
            ext,
        )
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - never leak internals
        logger.exception("Resume export failed (tailored=%s fmt=%s)", tailored_resume_id, fmt)
        raise HTTPException(status_code=500, detail="Export failed. Please try again.")


@router.get("/{tailored_resume_id}/export/pdf")
def export_tailored_pdf(
    tailored_resume_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _export(tailored_resume_id, "pdf", user, db)


@router.get("/{tailored_resume_id}/export/docx")
def export_tailored_docx(
    tailored_resume_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _export(tailored_resume_id, "docx", user, db)