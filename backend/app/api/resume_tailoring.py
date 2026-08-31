"""AI Resume Tailoring API (Phase 3A).

POST /jobs/{job_id}/resume-tailor

Creates an AI-tailored, grounded version of a parsed source resume for a
specific job. The source resume is never modified. This endpoint never makes an
AI call unless explicitly requested, and it reuses an existing tailoring for the
same (user, resume, job) instead of generating an uncontrolled duplicate.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.resume_job_analysis import ResumeJobAnalysis
from app.models.tailored_resume import TailoredResume
from app.schemas.resume_tailoring import (
    TailorResumeRequest,
    TailorResumeResponse,
    TailoredResumeListItem,
)
from app.services import resume_job_analysis as resume_match
from app.services.resume_tailoring import (
    TailoringInput,
    build_provider,
    call_tailoring,
    summarise_for_response,
)
from app.services.ai_provider import (
    AIProviderConfigurationError,
    AIProviderError,
    AIInvalidResponseError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AITimeoutError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["resume-tailoring"])

NO_USABLE_DATA_MESSAGE = (
    "No usable resume data is available for tailoring. "
    "Try uploading a text-based PDF or re-parse your resume."
)


def _get_own_resume(resume_id: str, user: User, db: Session) -> Resume:
    resume = db.query(Resume).filter(
        Resume.id == resume_id, Resume.user_id == user.id
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


def _validate_resume_usable(resume: Resume) -> None:
    if resume.parsing_status in ("pending", "processing"):
        raise HTTPException(
            status_code=409,
            detail="This resume is still being parsed. Please wait a moment and try again.",
        )
    if resume.parsing_status == "failed":
        raise HTTPException(
            status_code=422,
            detail=f"Resume parsing failed: {resume.parsing_error or 'unknown error'}",
        )
    if resume.parsing_status == "completed" and resume.parsed_data is None:
        # A scanned/image-based resume parses as "completed" with no parsed data.
        raise HTTPException(
            status_code=422,
            detail=(
                "This resume could not be scanned successfully (it may be image-based "
                "or scanned). Please upload a text-based PDF."
            ),
        )
    if not resume.parsed_data and not resume.extracted_text:
        raise HTTPException(status_code=422, detail=NO_USABLE_DATA_MESSAGE)

    parsed = resume.parsed_data or {}
    has_content = bool(
        (parsed.get("skills"))
        or (parsed.get("projects"))
        or (parsed.get("experience"))
        or (parsed.get("education"))
        or (parsed.get("certifications"))
        or (resume.extracted_text or "").strip()
    )
    if not has_content:
        raise HTTPException(status_code=422, detail=NO_USABLE_DATA_MESSAGE)


def _parsed_view(resume: Resume) -> dict:
    parsed = dict(resume.parsed_data or {})
    return parsed


def _get_or_create_analysis(user: User, job: Job, resume: Resume, db: Session) -> dict:
    """Reuse an existing deterministic Phase 2 Resume Match analysis, or generate
    (and persist) one using the existing Resume Match service."""
    existing = (
        db.query(ResumeJobAnalysis)
        .filter(
            ResumeJobAnalysis.user_id == user.id,
            ResumeJobAnalysis.resume_id == resume.id,
            ResumeJobAnalysis.job_id == job.id,
        )
        .first()
    )
    if existing and existing.analysis_data:
        return existing.analysis_data

    result = resume_match.analyze_resume_against_job(_parsed_view(resume), job)
    analysis = ResumeJobAnalysis(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job.id,
        overall_score=result["overall_score"],
        skill_score=result["scores"]["skills"] or 0,
        keyword_score=result["scores"]["keywords"] or 0,
        experience_score=result["scores"]["experience"] or 0,
        project_score=result["scores"]["projects"] or 0,
        education_score=result["scores"]["education"] or 0,
        analysis_data=result,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis.analysis_data


def _existing_tailoring(user: User, job_id: str, resume: Resume, db: Session) -> TailoredResume:
    return (
        db.query(TailoredResume)
        .filter(
            TailoredResume.user_id == user.id,
            TailoredResume.job_id == job_id,
            TailoredResume.source_resume_id == resume.id,
        )
        .order_by(TailoredResume.created_at.desc())
        .first()
    )


def _original_content_view(resume: Resume) -> dict:
    """Build the original resume content view from parsed data (never modified)."""
    parsed = resume.parsed_data or {}
    return {
        "summary": "",
        "skills": parsed.get("skills") or [],
        "experience": parsed.get("experience") or [],
        "projects": parsed.get("projects") or [],
        "education": parsed.get("education") or [],
        "certifications": parsed.get("certifications") or [],
    }


def _to_response(t: TailoredResume, resume: Optional[Resume] = None) -> TailorResumeResponse:
    return TailorResumeResponse(
        id=t.id,
        resume_id=t.source_resume_id,
        job_id=t.job_id,
        status="completed",
        source_version="original",
        original_content=_original_content_view(resume) if resume else {},
        tailored_content=summarise_for_response(t.structured_data or {}),
        changes=t.changes or [],
        supported_keywords_added=t.supported_keywords_added or [],
        unsupported_job_keywords=t.unsupported_job_keywords or [],
        warnings=t.warnings or [],
        ai_provider=t.ai_provider or "",
        model=t.model or "",
        created_at=t.created_at,
    )


@router.post("/{job_id}/resume-tailor", response_model=TailorResumeResponse)
def tailor_resume(
    job_id: str,
    body: TailorResumeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resume = _get_own_resume(body.resume_id, user, db)
    _validate_resume_usable(resume)

    if not (job.description or "").strip() and not (job.required_skills or "").strip():
        raise HTTPException(
            status_code=422,
            detail="This job does not have enough description or required skills to tailor against.",
        )

    # --- Cost / safety control: reuse existing tailoring when present --------
    existing = _existing_tailoring(user, job_id, resume, db)
    if existing and not body.regenerate:
        logger.info(
            "Reusing existing tailoring user=%s resume=%s job=%s",
            user.id, resume.id, job_id,
        )
        return _to_response(existing, resume)

    # --- Phase 2 Resume Match as grounding layer -----------------------------
    grounding = _get_or_create_analysis(user, job, resume, db)

    # --- Provider (fail gracefully if not configured) ------------------------
    settings = get_settings()
    try:
        provider = build_provider(settings)
    except AIProviderConfigurationError as exc:
        logger.warning("AI tailoring requested but not configured: %s", exc)
        raise HTTPException(status_code=503, detail="AI service is not configured. Please try again later.")

    tailoring_input = TailoringInput(
        resume=resume.parsed_data or {},
        extracted_text=resume.extracted_text or "",
        job=job,
        analysis=grounding,
    )

    try:
        result = call_tailoring(
            provider,
            tailoring_input,
            timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        )
    except AITimeoutError:
        raise HTTPException(status_code=504, detail="AI request timed out. Please try again.")
    except AIRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="AI provider rate limit reached. Please wait and try again.",
        )
    except AIInvalidResponseError:
        raise HTTPException(
            status_code=502,
            detail="The AI returned an invalid response. Please try again.",
        )
    except AIProviderUnavailableError:
        raise HTTPException(status_code=503, detail="The AI provider is currently unavailable.")
    except AIProviderError as exc:
        logger.warning("AI tailoring failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="AI tailoring failed. Please try again.")
    except Exception:  # noqa: BLE001 - never leak internal/provider details
        logger.exception("Unexpected error during AI tailoring")
        raise HTTPException(status_code=500, detail="Unexpected error during resume tailoring.")

    # --- Persist the tailored result -----------------------------------------
    # Reuse the existing row on regenerate (avoid uncontrolled duplicates); the
    # ORIGINAL resume is never touched.
    content_summary = summarise_for_response(result)
    if existing:
        record = existing
        record.tailored_content = content_summary
        record.structured_data = result
        record.changes = result.get("overall_changes") or []
        record.supported_keywords_added = result.get("keywords_added") or []
        record.unsupported_job_keywords = result.get("keywords_not_added") or []
        record.warnings = result.get("warnings") or []
        record.ai_provider = settings.AI_PROVIDER or ""
        record.model = settings.AI_MODEL or ""
    else:
        record = TailoredResume(
            user_id=user.id,
            source_resume_id=resume.id,
            job_id=job_id,
            version_name="tailored",
            tailored_content=content_summary,
            structured_data=result,
            changes=result.get("overall_changes") or [],
            supported_keywords_added=result.get("keywords_added") or [],
            unsupported_job_keywords=result.get("keywords_not_added") or [],
            warnings=result.get("warnings") or [],
            ai_provider=settings.AI_PROVIDER or "",
            model=settings.AI_MODEL or "",
        )
        db.add(record)
    db.commit()
    db.refresh(record)
    return _to_response(record, resume)


# =============================================================================
# List tailored versions (read-only) — used by the Resumes page.
# =============================================================================
tailored_list_router = APIRouter(prefix="/resumes", tags=["resume-tailoring"])


@tailored_list_router.get("/tailored", response_model=list[TailoredResumeListItem])
def list_tailored_resumes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the requesting user's saved tailored resume versions (ownership
    isolated). Only returns results persisted in the DB; never triggers an AI
    call."""
    tails = (
        db.query(TailoredResume)
        .filter(TailoredResume.user_id == user.id)
        .order_by(TailoredResume.created_at.desc())
        .all()
    )

    resume_by_id = {}
    job_by_id = {}
    if tails:
        resume_ids = {t.source_resume_id for t in tails}
        job_ids = {t.job_id for t in tails}
        for r in db.query(Resume).filter(Resume.id.in_(resume_ids)).all():
            resume_by_id[r.id] = r
        for j in db.query(Job).filter(Job.id.in_(job_ids)).all():
            job_by_id[j.id] = j

    items = []
    for t in tails:
        src = resume_by_id.get(t.source_resume_id)
        j = job_by_id.get(t.job_id)
        items.append(
            TailoredResumeListItem(
                id=t.id,
                job_id=t.job_id,
                job_title=(j.title if j else "") or "",
                job_company=(j.company if j else "") or "",
                source_resume_id=t.source_resume_id,
                source_resume_name=(src.original_filename if src else "") or "",
                original_content=_original_content_view(src) if src else {},
                tailored_content=summarise_for_response(t.structured_data or {}),
                changes=t.changes or [],
                supported_keywords_added=t.supported_keywords_added or [],
                unsupported_job_keywords=t.unsupported_job_keywords or [],
                warnings=t.warnings or [],
                ai_provider=t.ai_provider or "",
                model=t.model or "",
                created_at=t.created_at,
            )
        )
    return items
