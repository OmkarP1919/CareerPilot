from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class JobMatch(Base):
    __tablename__ = "job_matches"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    overall_score = Column(Integer, nullable=False)
    skills_score = Column(Integer, default=0)
    project_score = Column(Integer, default=0)
    experience_score = Column(Integer, default=0)
    role_score = Column(Integer, default=0)
    location_score = Column(Integer, default=0)
    matched_skills = Column(Text, nullable=True)
    missing_skills = Column(Text, nullable=True)
    relevant_projects = Column(Text, nullable=True)
    relevant_experience = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
