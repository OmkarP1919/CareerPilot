from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.types import JSON
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class ResumeJobAnalysis(Base):
    """Persisted deterministic Resume vs Job analysis (RESUME MATCH).

    This is intentionally separate and distinct from the JobMatch model,
    which represents the CareerPilot profile-to-job match (PROFILE MATCH).
    """

    __tablename__ = "resume_job_analyses"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    resume_id = Column(String, ForeignKey("resumes.id"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    overall_score = Column(Integer, nullable=False)
    skill_score = Column(Integer, default=0)
    keyword_score = Column(Integer, default=0)
    experience_score = Column(Integer, default=0)
    project_score = Column(Integer, default=0)
    education_score = Column(Integer, default=0)
    analysis_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
