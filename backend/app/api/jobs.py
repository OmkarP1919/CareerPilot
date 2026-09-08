from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
import logging
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.core.rate_limit_deps import expensive_rate_limiter
from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.models.job_match import JobMatch
from app.models.resume_job_analysis import ResumeJobAnalysis
from app.models.tailored_resume import TailoredResume
from app.models.cover_letter import CoverLetter
from app.schemas.job import (
    JobCreate,
    JobUpdate,
    JobResponse,
    DiscoveryResponse,
    RecommendedJob,
    PersonalizedDiscoveryResponse,
)
from app.services.job_discovery import discover_jobs, get_recommended_jobs
from app.services.personalized_discovery import PersonalizedDiscoveryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
def list_jobs(
    search: str = Query(None),
    employment_type: str = Query(None),
    experience_level: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Jobs are saved per-user: a client must never see another user's saved
    # jobs through the list endpoint, even when search/filter terms match.
    query = db.query(Job).filter(Job.user_id == user.id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Job.title.ilike(search_term),
                Job.company.ilike(search_term),
                Job.location.ilike(search_term),
                Job.required_skills.ilike(search_term),
            )
        )

    if employment_type:
        query = query.filter(Job.employment_type == employment_type)

    if experience_level:
        query = query.filter(Job.experience_level == experience_level)

    return query.order_by(Job.created_at.desc()).all()


@router.post("", response_model=JobResponse, status_code=201)
def create_job(
    data: JobCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = Job(user_id=user.id, **data.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/discover", response_model=DiscoveryResponse, dependencies=[Depends(expensive_rate_limiter)])
def trigger_discovery(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = discover_jobs(user.id, db)
    return DiscoveryResponse(**result)


@router.post("/discover/personalized", response_model=PersonalizedDiscoveryResponse, dependencies=[Depends(expensive_rate_limiter)])
def trigger_personalized_discovery(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = PersonalizedDiscoveryService.discover(user.id, db)
        return PersonalizedDiscoveryResponse(**result)
    except Exception:
        logger.exception("Personalized discovery failed for user %s", user.id)
        # Do not leak raw exception details to the client.
        raise HTTPException(
            status_code=500,
            detail="We couldn't finish finding jobs right now. Please try again.",
        )



@router.get("/recommended", response_model=list[RecommendedJob])
def list_recommended(
    min_score: int = Query(0, ge=0, le=100),
    source: str = Query(None),
    remote: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results = get_recommended_jobs(
        user.id, db,
        min_score=min_score,
        source=source,
        remote_only=remote,
    )
    return [
        RecommendedJob(
            job=JobResponse.model_validate(r["job"]),
            match_score=r["match_score"],
            matched_skills=r["matched_skills"],
            missing_skills=r["missing_skills"],
            relevant_projects=r["relevant_projects"],
        )
        for r in results
    ]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job



@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    data: JobUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job


_JOB_DEPENDENT_MODELS = (
    (Application, "applications"),
    (JobMatch, "job_matches"),
    (ResumeJobAnalysis, "resume_job_analyses"),
    (TailoredResume, "tailored_resumes"),
    (CoverLetter, "cover_letters"),
)


def _ensure_job_deletable(job_id: str, db: Session) -> None:
    """Refuse to delete a job that user data still references.

    A saved job can be referenced by user application history (applications),
    match scores (job_matches) and AI-derived artifacts (resume_job_analyses,
    tailored_resumes, cover_letters). PostgreSQL enforces these foreign keys,
    so deleting a referenced row raises a ForeignKeyViolation (a 500); SQLite
    silently ignores the FK - which is exactly the divergence this guard
    closes. The safe, deterministic behavior on both engines is to reject the
    deletion with a 409 until the user removes the dependent rows themselves.

    Critically, applications are user application history and are NEVER
    cascade-deleted when a saved job is removed: the owner must delete the
    application explicitly first.
    """
    referenced = [
        label
        for model, label in _JOB_DEPENDENT_MODELS
        if db.query(model).filter(model.job_id == job_id).first() is not None
    ]
    if referenced:
        raise HTTPException(
            status_code=409,
            detail=(
                "Job cannot be deleted because it is referenced by: "
                + ", ".join(referenced) + "."
            ),
        )


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _ensure_job_deletable(job.id, db)
    db.delete(job)
    db.commit()
