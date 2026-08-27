import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.job_match import JobMatch
from app.schemas.match import MatchResponse, SavedMatchResponse
from app.services.matching import calculate_match

router = APIRouter(prefix="/jobs", tags=["matching"])


@router.post("/{job_id}/match", response_model=MatchResponse)
def match_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = calculate_match(user.id, job, db)

    existing = db.query(JobMatch).filter(
        JobMatch.user_id == user.id, JobMatch.job_id == job_id
    ).first()

    if existing:
        existing.overall_score = result["overall_score"]
        existing.skills_score = result["skills_score"]
        existing.project_score = result["project_score"]
        existing.experience_score = result["experience_score"]
        existing.role_score = result["role_score"]
        existing.location_score = result["location_score"]
        existing.matched_skills = json.dumps(result["matched_skills"])
        existing.missing_skills = json.dumps(result["missing_skills"])
        existing.relevant_projects = json.dumps(result["relevant_projects"])
        existing.relevant_experience = json.dumps(result["relevant_experience"])
        existing.explanation = result["explanation"]
        db.commit()
    else:
        match = JobMatch(
            user_id=user.id,
            job_id=job_id,
            overall_score=result["overall_score"],
            skills_score=result["skills_score"],
            project_score=result["project_score"],
            experience_score=result["experience_score"],
            role_score=result["role_score"],
            location_score=result["location_score"],
            matched_skills=json.dumps(result["matched_skills"]),
            missing_skills=json.dumps(result["missing_skills"]),
            relevant_projects=json.dumps(result["relevant_projects"]),
            relevant_experience=json.dumps(result["relevant_experience"]),
            explanation=result["explanation"],
        )
        db.add(match)
        db.commit()

    return result


@router.get("/{job_id}/analysis", response_model=SavedMatchResponse)
def get_analysis(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    match = db.query(JobMatch).filter(
        JobMatch.user_id == user.id, JobMatch.job_id == job_id
    ).first()
    if not match:
        raise HTTPException(status_code=404, detail="No match analysis found. Run a match first.")

    return SavedMatchResponse(
        id=match.id,
        job_id=match.job_id,
        overall_score=match.overall_score,
        skills_score=match.skills_score,
        project_score=match.project_score,
        experience_score=match.experience_score,
        role_score=match.role_score,
        location_score=match.location_score,
        matched_skills=json.loads(match.matched_skills or "[]"),
        missing_skills=json.loads(match.missing_skills or "[]"),
        relevant_projects=json.loads(match.relevant_projects or "[]"),
        relevant_experience=json.loads(match.relevant_experience or "[]"),
        explanation=match.explanation,
        created_at=match.created_at,
    )
