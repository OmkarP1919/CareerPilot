import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.resume_job_analysis import ResumeJobAnalysis
from app.schemas.resume_job_analysis import (
    ResumeAnalysisRequest,
    ResumeAnalysisResponse,
    EducationCertificationRelevance,
    RelevantProject,
    RelevantExperience,
)
from app.services.resume_job_analysis import analyze_resume_against_job

router = APIRouter(prefix="/jobs", tags=["resume-analysis"])

NO_USABLE_DATA_MESSAGE = (
    "No usable resume data is available for analysis. "
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
    if not resume.parsed_data and not resume.extracted_text:
        raise HTTPException(
            status_code=422,
            detail=NO_USABLE_DATA_MESSAGE,
        )

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
        raise HTTPException(
            status_code=422,
            detail=NO_USABLE_DATA_MESSAGE,
        )


def _parsed_view(resume: Resume) -> dict:
    parsed = dict(resume.parsed_data or {})
    if resume.extracted_text:
        parsed["extracted_text"] = resume.extracted_text
    return parsed


def _to_response(analysis: ResumeJobAnalysis) -> ResumeAnalysisResponse:
    data = analysis.analysis_data or {}
    return ResumeAnalysisResponse(
        id=analysis.id,
        job_id=analysis.job_id,
        resume_id=analysis.resume_id,
        overall_score=analysis.overall_score,
        scores=data.get("scores") or {},
        matched_skills=data.get("matched_skills") or [],
        missing_skills=data.get("missing_skills") or [],
        additional_relevant_skills=data.get("additional_relevant_skills") or [],
        matched_keywords=data.get("matched_keywords") or [],
        missing_keywords=data.get("missing_keywords") or [],
        relevant_projects=[
            RelevantProject(**p) for p in (data.get("relevant_projects") or [])
        ],
        relevant_experience=[
            RelevantExperience(**e) for e in (data.get("relevant_experience") or [])
        ],
        education_certification_relevance=EducationCertificationRelevance(
            **(data.get("education_certification_relevance") or {})
        ),
        suggestions=data.get("suggestions") or [],
        note=data.get("note"),
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


@router.post("/{job_id}/resume-analysis", response_model=ResumeAnalysisResponse)
def analyze_resume(
    job_id: str,
    body: ResumeAnalysisRequest,
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
            detail="This job does not have enough description or required skills to analyze.",
        )

    result = analyze_resume_against_job(_parsed_view(resume), job)

    existing = db.query(ResumeJobAnalysis).filter(
        ResumeJobAnalysis.user_id == user.id,
        ResumeJobAnalysis.resume_id == resume.id,
        ResumeJobAnalysis.job_id == job_id,
    ).first()

    if existing:
        existing.overall_score = result["overall_score"]
        existing.skill_score = result["scores"]["skills"] or 0
        existing.keyword_score = result["scores"]["keywords"] or 0
        existing.experience_score = result["scores"]["experience"] or 0
        existing.project_score = result["scores"]["projects"] or 0
        existing.education_score = result["scores"]["education"] or 0
        existing.analysis_data = result
        db.commit()
        db.refresh(existing)
        return _to_response(existing)

    analysis = ResumeJobAnalysis(
        user_id=user.id,
        resume_id=resume.id,
        job_id=job_id,
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
    return _to_response(analysis)


@router.get("/{job_id}/resume-analysis/{resume_id}", response_model=ResumeAnalysisResponse)
def get_resume_analysis(
    job_id: str,
    resume_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    analysis = db.query(ResumeJobAnalysis).filter(
        ResumeJobAnalysis.user_id == user.id,
        ResumeJobAnalysis.job_id == job_id,
        ResumeJobAnalysis.resume_id == resume_id,
    ).first()
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="No Resume Match analysis found for this resume and job. Run an analysis first.",
        )
    return _to_response(analysis)
