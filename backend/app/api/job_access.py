from fastapi import HTTPException
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.user import User
from app.models.job_match import JobMatch
from app.models.application import Application


def get_own_job(job_id: str, user: User, db: Session) -> Job:
    """Return the Job referenced by ``job_id`` accessible to ``user`` or raise 404.

    The lookup is scoped to jobs owned by the user, jobs matched to the user,
    jobs with an application by the user, or public catalog/discovery jobs.
    A cross-user private job and a nonexistent job both surface as a 404.
    """
    job = db.query(Job).filter(
        Job.id == job_id,
        or_(
            Job.user_id == user.id,
            Job.id.in_(db.query(JobMatch.job_id).filter(JobMatch.user_id == user.id)),
            Job.id.in_(db.query(Application.job_id).filter(Application.user_id == user.id)),
            and_(Job.source.isnot(None), Job.external_id.isnot(None)),
        ),
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job