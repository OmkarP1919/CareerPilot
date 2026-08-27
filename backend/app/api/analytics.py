from collections import Counter
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.application import Application
from app.schemas.analytics import (
    DashboardResponse, RecentApplication, RecentJob,
    ApplicationFunnelResponse, FunnelStage,
    SkillsAnalyticsResponse, SkillFrequency,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

FUNNEL_ORDER = ["Saved", "Preparing", "Applied", "Assessment", "Interview", "Offer"]


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_jobs = db.query(Job).filter(Job.user_id == user.id).count()

    high_match_jobs = db.query(JobMatch).filter(
        JobMatch.user_id == user.id, JobMatch.overall_score >= 70
    ).count()

    applications = db.query(Application).filter(Application.user_id == user.id).all()

    status_counts = Counter(a.status for a in applications)
    total_applications = len(applications)

    scores = [
        m.overall_score
        for m in db.query(JobMatch).filter(JobMatch.user_id == user.id).all()
    ]
    avg_score = round(sum(scores) / len(scores)) if scores else None

    recent_apps_query = (
        db.query(Application)
        .filter(Application.user_id == user.id)
        .order_by(Application.updated_at.desc())
        .limit(5)
        .all()
    )
    recent_applications = []
    for a in recent_apps_query:
        job = db.query(Job).filter(Job.id == a.job_id).first()
        recent_applications.append(RecentApplication(
            id=a.id,
            job_title=job.title if job else None,
            job_company=job.company if job else None,
            status=a.status,
            updated_at=a.updated_at,
        ))

    recent_jobs_query = (
        db.query(Job)
        .filter(Job.user_id == user.id)
        .order_by(Job.created_at.desc())
        .limit(5)
        .all()
    )
    recent_jobs = [
        RecentJob(id=j.id, title=j.title, company=j.company, created_at=j.created_at)
        for j in recent_jobs_query
    ]

    return DashboardResponse(
        total_jobs=total_jobs,
        high_match_jobs=high_match_jobs,
        total_applications=total_applications,
        saved_count=status_counts.get("Saved", 0),
        applied_count=status_counts.get("Applied", 0),
        interview_count=status_counts.get("Interview", 0),
        offer_count=status_counts.get("Offer", 0),
        rejected_count=status_counts.get("Rejected", 0),
        average_match_score=avg_score,
        recent_applications=recent_applications,
        recent_jobs=recent_jobs,
    )


@router.get("/application-funnel", response_model=ApplicationFunnelResponse)
def get_application_funnel(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    applications = db.query(Application).filter(Application.user_id == user.id).all()
    status_counts = Counter(a.status for a in applications)

    funnel = [
        FunnelStage(stage=stage, count=status_counts.get(stage, 0))
        for stage in FUNNEL_ORDER
    ]

    return ApplicationFunnelResponse(
        funnel=funnel,
        total=len(applications),
    )


@router.get("/skills", response_model=SkillsAnalyticsResponse)
def get_skills_analytics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    matches = db.query(JobMatch).filter(JobMatch.user_id == user.id).all()

    matched_counter: Counter = Counter()
    missing_counter: Counter = Counter()

    for m in matches:
        try:
            matched = json.loads(m.matched_skills or "[]")
            missing = json.loads(m.missing_skills or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        matched_counter.update(matched)
        missing_counter.update(missing)

    frequent_matched = [
        SkillFrequency(skill=s, count=c, type="matched")
        for s, c in matched_counter.most_common(10)
    ]
    frequent_missing = [
        SkillFrequency(skill=s, count=c, type="missing")
        for s, c in missing_counter.most_common(10)
    ]

    return SkillsAnalyticsResponse(
        frequent_missing=frequent_missing,
        frequent_matched=frequent_matched,
        total_analyses=len(matches),
    )
