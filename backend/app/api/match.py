import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.core.rate_limit_deps import expensive_rate_limiter
from app.api.job_access import get_own_job
from app.models.user import User
from app.models.job_match import JobMatch
from app.schemas.match import MatchResponse, SavedMatchResponse
from app.services.ranking import calculate_rank, load_profile_context

router = APIRouter(prefix="/jobs", tags=["matching"])


@router.post("/{job_id}/match", response_model=MatchResponse, dependencies=[Depends(expensive_rate_limiter)])
def match_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # The job must belong to the current user (404 for foreign/missing jobs).
    job = get_own_job(job_id, user, db)

    profile_context = load_profile_context(user.id, db)
    rank_result = calculate_rank(profile_context=profile_context, job=job)

    skills_sc = rank_result.factor_scores.get("skills") or 0
    project_sc = rank_result.factor_scores.get("projects") or 0
    exp_sc = rank_result.factor_scores.get("experience") or 0
    role_sc = rank_result.factor_scores.get("role") or 0
    loc_sc = rank_result.factor_scores.get("location") or 0
    work_mode_sc = rank_result.factor_scores.get("work_mode")
    edu_sc = rank_result.factor_scores.get("education")

    existing = db.query(JobMatch).filter(
        JobMatch.user_id == user.id, JobMatch.job_id == job_id
    ).first()

    if existing:
        existing.overall_score = rank_result.overall_score
        existing.skills_score = skills_sc
        existing.project_score = project_sc
        existing.experience_score = exp_sc
        existing.role_score = role_sc
        existing.location_score = loc_sc
        existing.work_mode_score = work_mode_sc
        existing.education_score = edu_sc
        existing.score_version = "v2"
        existing.matched_skills = json.dumps(rank_result.matched_skills)
        existing.missing_skills = json.dumps(rank_result.missing_skills)
        existing.relevant_projects = json.dumps(rank_result.relevant_projects)
        existing.relevant_experience = json.dumps(rank_result.relevant_experience)
        existing.explanation = rank_result.explanation
        db.commit()
    else:
        match = JobMatch(
            user_id=user.id,
            job_id=job_id,
            overall_score=rank_result.overall_score,
            skills_score=skills_sc,
            project_score=project_sc,
            experience_score=exp_sc,
            role_score=role_sc,
            location_score=loc_sc,
            work_mode_score=work_mode_sc,
            education_score=edu_sc,
            score_version="v2",
            matched_skills=json.dumps(rank_result.matched_skills),
            missing_skills=json.dumps(rank_result.missing_skills),
            relevant_projects=json.dumps(rank_result.relevant_projects),
            relevant_experience=json.dumps(rank_result.relevant_experience),
            explanation=rank_result.explanation,
        )
        db.add(match)
        db.commit()

    factors_dict = [
        {
            "key": f.key,
            "score": f.score,
            "weight": f.weight,
            "available": f.available,
            "evidence": f.evidence,
        }
        for f in rank_result.factors
    ]

    return MatchResponse(
        overall_score=rank_result.overall_score,
        skills_score=skills_sc,
        project_score=project_sc,
        experience_score=exp_sc,
        role_score=role_sc,
        location_score=loc_sc,
        work_mode_score=work_mode_sc,
        education_score=edu_sc,
        score_version="v2",
        factors=factors_dict,
        reasons=rank_result.reasons,
        matched_skills=rank_result.matched_skills,
        missing_skills=rank_result.missing_skills,
        relevant_projects=rank_result.relevant_projects,
        relevant_experience=rank_result.relevant_experience,
        explanation=rank_result.explanation,
    )


@router.get("/{job_id}/analysis", response_model=SavedMatchResponse)
def get_analysis(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = get_own_job(job_id, user, db)

    match = db.query(JobMatch).filter(
        JobMatch.user_id == user.id, JobMatch.job_id == job_id
    ).first()
    if not match:
        raise HTTPException(status_code=404, detail="No match analysis found. Run a match first.")

    factors = None
    if match.score_version != "v2":
        # Upgrade legacy row to canonical v2 on-the-fly
        profile_context = load_profile_context(user.id, db)
        rank_result = calculate_rank(profile_context=profile_context, job=job)

        skills_sc = rank_result.factor_scores.get("skills") or 0
        project_sc = rank_result.factor_scores.get("projects") or 0
        exp_sc = rank_result.factor_scores.get("experience") or 0
        role_sc = rank_result.factor_scores.get("role") or 0
        loc_sc = rank_result.factor_scores.get("location") or 0
        work_mode_sc = rank_result.factor_scores.get("work_mode")
        edu_sc = rank_result.factor_scores.get("education")

        match.overall_score = rank_result.overall_score
        match.skills_score = skills_sc
        match.project_score = project_sc
        match.experience_score = exp_sc
        match.role_score = role_sc
        match.location_score = loc_sc
        match.work_mode_score = work_mode_sc
        match.education_score = edu_sc
        match.score_version = "v2"
        match.matched_skills = json.dumps(rank_result.matched_skills)
        match.missing_skills = json.dumps(rank_result.missing_skills)
        match.relevant_projects = json.dumps(rank_result.relevant_projects)
        match.relevant_experience = json.dumps(rank_result.relevant_experience)
        match.explanation = rank_result.explanation
        db.commit()

        factors = [
            {
                "key": f.key,
                "score": f.score,
                "weight": f.weight,
                "available": f.available,
                "evidence": f.evidence,
            }
            for f in rank_result.factors
        ]
    else:
        from app.services.ranking import CANONICAL_FACTOR_WEIGHTS
        factors = [
            {"key": "skills", "score": match.skills_score, "weight": CANONICAL_FACTOR_WEIGHTS["skills"], "available": True, "evidence": None},
            {"key": "experience", "score": match.experience_score, "weight": CANONICAL_FACTOR_WEIGHTS["experience"], "available": True, "evidence": None},
            {"key": "role", "score": match.role_score, "weight": CANONICAL_FACTOR_WEIGHTS["role"], "available": True, "evidence": None},
            {"key": "projects", "score": match.project_score, "weight": CANONICAL_FACTOR_WEIGHTS["projects"], "available": True, "evidence": None},
            {"key": "location", "score": match.location_score, "weight": CANONICAL_FACTOR_WEIGHTS["location"], "available": True, "evidence": None},
            {"key": "education", "score": match.education_score, "weight": CANONICAL_FACTOR_WEIGHTS["education"], "available": match.education_score is not None, "evidence": None},
            {"key": "work_mode", "score": match.work_mode_score, "weight": CANONICAL_FACTOR_WEIGHTS["work_mode"], "available": match.work_mode_score is not None, "evidence": None},
        ]

    return SavedMatchResponse(
        id=match.id,
        job_id=match.job_id,
        overall_score=match.overall_score,
        skills_score=match.skills_score,
        project_score=match.project_score,
        experience_score=match.experience_score,
        role_score=match.role_score,
        location_score=match.location_score,
        work_mode_score=match.work_mode_score,
        education_score=match.education_score,
        score_version=match.score_version,
        factors=factors,
        matched_skills=json.loads(match.matched_skills or "[]"),
        missing_skills=json.loads(match.missing_skills or "[]"),
        relevant_projects=json.loads(match.relevant_projects or "[]"),
        relevant_experience=json.loads(match.relevant_experience or "[]"),
        explanation=match.explanation,
        created_at=match.created_at,
    )
