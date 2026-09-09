"""Shared job ownership helper (Phase 7 H-1).

Every route that accepts a ``job_id`` and creates/attaches user-owned records
must resolve the job against the requesting user. A cross-user ``job_id`` and a
nonexistent ``job_id`` both surface as a 404 so the existence of another user's
job is never disclosed.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.user import User


def get_own_job(job_id: str, user: User, db: Session) -> Job:
    """Return the Job referenced by ``job_id`` owned by ``user`` or raise 404.

    The lookup is scoped by both ``Job.id`` and ``Job.user_id`` so a
    client-supplied ``job_id`` is never trusted without an ownership check.
    """
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job