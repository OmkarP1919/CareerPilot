"""AI Cover Letter generation API (Phase 4A).

POST /jobs/{job_id}/cover-letter          generate (or reuse) a cover letter
GET  /jobs/{job_id}/cover-letter/{resume_id}   retrieve an existing one
GET  /cover-letters                        list the user's cover letters
DELETE /cover-letters/{id}                 delete one of the user's letters

The source resume is never modified. The endpoint never makes an AI call unless
explicitly requested; it reuses an existing generation for the same
(user, resume, job) instead of creating an uncontrolled duplicate. Ownership is
enforced on every access.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.resume_job_analysis import ResumeJobAnalysis
from app.models.cover_letter import CoverLetter
from app.models.profile import Profile, UserSkill
from app.schemas.cover_letter import (
    CoverLetterRequest,
    CoverLetterResponse,
    CoverLetterListItem,
)
from app.services import resume_job_analysis as resume_match
from app.services.cover_letter import (
    CoverLetterInput,
    build_provider,
    call_cover_letter,
    assemble_content,
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

router = APIRouter(prefix="/jobs", tags=["cover-letter"])
collection_router = APIRouter(prefix="/cover-letters", tags=["cover-letter"])

NO_USABLE_DATA_MESSAGE = (
    "No usable resume data is available to write a cover letter. "
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


def _profile_view(user: User, db: Session) -> dict:
    """Build a privacy-aware view of the candidate's CareerPilot profile."""
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        return {}
    skills = [
        s.skill.name
        for s in db.query(UserSkill).filter(UserSkill.profile_id == profile.id).all()
        if s.skill and s.skill.name
    ]
    return {
        "skills": skills,
        "projects": [
            {
                "name": p.name,
                "description": p.description,
            }
            for p in profile.projects
        ],
        "experiences": [
            {
                "role": e.role,
                "company": e.company,
                "start_date": e.start_date,
                "end_date": e.end_date,
            }
            for e in profile.experiences
        ],
        "education": [
            {
                "degree": e.degree,
                "college": e.college,
            }
            for e in profile.education
        ],
        "certifications": [
            {
                "name": c.name,
            }
            for c in profile.certifications
        ],
    }


def _get_or_create_analysis(user: User, job: Job, resume: Resume, db: Session) -> dict:
    """Reuse an existing deterministic Phase 2 Resume Match analysis, or generate
    (and persist) one using the existing Resume Match service. Does not duplicate
    the Resume Match algorithm."""
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

    result = resume_match.analyze_resume_against_job(resume.parsed_data or {}, job)
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


def _existing_letter(user: User, job_id: str, resume: Resume, db: Session) -> CoverLetter:
    return (
        db.query(CoverLetter)
        .filter(
            CoverLetter.user_id == user.id,
            CoverLetter.job_id == job_id,
            CoverLetter.source_resume_id == resume.id,
        )
        .order_by(CoverLetter.created_at.desc())
        .first()
    )


def _to_response(c: CoverLetter, resume: Optional[Resume] = None) -> CoverLetterResponse:
    structured = c.structured_data or {}
    return CoverLetterResponse(
        id=c.id,
        resume_id=c.source_resume_id,
        job_id=c.job_id,
        status="completed",
        content=c.content or "",
        structured_content=summarise_for_response(structured),
        supported_points=structured.get("supported_points") or [],
        unsupported_requirements=structured.get("unsupported_requirements") or [],
        warnings=c.warnings or [],
        changes=c.changes or [],
        ai_provider=c.ai_provider or "",
        model=c.model or "",
        created_at=c.created_at,
    )


@router.post("/{job_id}/cover-letter", response_model=CoverLetterResponse)
def generate_cover_letter(
    job_id: str,
    body: CoverLetterRequest,
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
            detail="This job does not have enough description or required skills to write a cover letter against.",
        )

    # --- Cost / safety control: reuse existing generation when present --------
    existing = _existing_letter(user, job_id, resume, db)
    if existing and not body.regenerate:
        logger.info(
            "Reusing existing cover letter user=%s resume=%s job=%s",
            user.id, resume.id, job_id,
        )
        return _to_response(existing, resume)

    # --- Phase 2 Resume Match as grounding layer -----------------------------
    grounding = _get_or_create_analysis(user, job, resume, db)

    # --- Candidate CareerPilot profile (privacy-aware) ----------------------- 
    profile_view = _profile_view(user, db)

    # --- Provider (fail gracefully if not configured) ------------------------
    settings = get_settings()
    try:
        provider = build_provider(settings)
    except AIProviderConfigurationError as exc:
        logger.warning("AI cover letter requested but not configured: %s", exc)
        raise HTTPException(status_code=503, detail="AI service is not configured. Please try again later.")

    cover_letter_input = CoverLetterInput(
        resume=resume.parsed_data or {},
        extracted_text=resume.extracted_text or "",
        profile=profile_view,
        job=job,
        analysis=grounding,
    )

    try:
        result = call_cover_letter(
            provider,
            cover_letter_input,
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
        logger.warning("AI cover letter generation failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="AI cover letter generation failed. Please try again.")
    except Exception:  # noqa: BLE001 - never leak internal/provider details
        logger.exception("Unexpected error during cover letter generation")
        raise HTTPException(status_code=500, detail="Unexpected error during cover letter generation.")

    # --- Persist the generated result -----------------------------------------
    # Reuse the existing row on regenerate (avoid uncontrolled duplicates). The
    # ORIGINAL resume is never touched.
    final_text = assemble_content(result)
    if existing:
        record = existing
        record.content = final_text
        record.structured_data = result
        record.changes = result.get("warnings") or []
        record.warnings = result.get("warnings") or []
        record.ai_provider = settings.AI_PROVIDER or ""
        record.model = settings.AI_MODEL or ""
    else:
        record = CoverLetter(
            user_id=user.id,
            source_resume_id=resume.id,
            job_id=job_id,
            version_name="cover-letter",
            content=final_text,
            structured_data=result,
            changes=result.get("warnings") or [],
            warnings=result.get("warnings") or [],
            ai_provider=settings.AI_PROVIDER or "",
            model=settings.AI_MODEL or "",
        )
        db.add(record)
    db.commit()
    db.refresh(record)
    return _to_response(record, resume)


@router.get("/{job_id}/cover-letter/{resume_id}", response_model=CoverLetterResponse)
def get_cover_letter(
    job_id: str,
    resume_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    letter = (
        db.query(CoverLetter)
        .filter(
            CoverLetter.job_id == job_id,
            CoverLetter.source_resume_id == resume_id,
            CoverLetter.user_id == user.id,
        )
        .order_by(CoverLetter.created_at.desc())
        .first()
    )
    if not letter:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    return _to_response(letter)


@collection_router.get("", response_model=list[CoverLetterListItem])
def list_cover_letters(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the requesting user's saved cover letters (ownership isolated)."""
    letters = (
        db.query(CoverLetter)
        .filter(CoverLetter.user_id == user.id)
        .order_by(CoverLetter.created_at.desc())
        .all()
    )

    resume_by_id = {}
    job_by_id = {}
    if letters:
        resume_ids = {c.source_resume_id for c in letters}
        job_ids = {c.job_id for c in letters}
        for r in db.query(Resume).filter(Resume.id.in_(resume_ids)).all():
            resume_by_id[r.id] = r
        for j in db.query(Job).filter(Job.id.in_(job_ids)).all():
            job_by_id[j.id] = j

    items = []
    for c in letters:
        src = resume_by_id.get(c.source_resume_id)
        j = job_by_id.get(c.job_id)
        items.append(
            CoverLetterListItem(
                id=c.id,
                job_id=c.job_id,
                job_title=(j.title if j else "") or "",
                job_company=(j.company if j else "") or "",
                source_resume_id=c.source_resume_id,
                source_resume_name=(src.original_filename if src else "") or "",
                version_name=c.version_name or "",
                content=c.content or "",
                warnings=c.warnings or [],
                ai_provider=c.ai_provider or "",
                model=c.model or "",
                created_at=c.created_at,
            )
        )
    return items


@collection_router.delete("/{letter_id}", status_code=204)
def delete_cover_letter(
    letter_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    letter = (
        db.query(CoverLetter)
        .filter(CoverLetter.id == letter_id, CoverLetter.user_id == user.id)
        .first()
    )
    if not letter:
        # Cross-user access returns 404 rather than exposing existence.
        raise HTTPException(status_code=404, detail="Cover letter not found")
    db.delete(letter)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
