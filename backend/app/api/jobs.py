from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
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

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
def list_jobs(
    search: str = Query(None),
    employment_type: str = Query(None),
    experience_level: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Job)

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


@router.post("/discover", response_model=DiscoveryResponse)
def trigger_discovery(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = discover_jobs(user.id, db)
    return DiscoveryResponse(**result)


@router.post("/discover/personalized", response_model=PersonalizedDiscoveryResponse)
def trigger_personalized_discovery(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    print(f"[BACKEND 1] Personalized endpoint entered for user_id={user.id}")
    try:
        print("[BACKEND 2] Calling personalized discovery service")
        result = PersonalizedDiscoveryService.discover(user.id, db)
        print(f"[BACKEND 3] Discovery service returned: new={result.get('new_jobs')}, existing={result.get('existing_jobs')}, matches={result.get('matches_created')}")
        print("[BACKEND 4] Sending response")
        return PersonalizedDiscoveryResponse(**result)
    except Exception as e:
        import traceback
        print(f"[BACKEND ERROR] Discovery endpoint exception: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



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
    job = db.query(Job).filter(Job.id == job_id).first()
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


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
