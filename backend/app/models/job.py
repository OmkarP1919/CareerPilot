from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, UniqueConstraint
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    external_id = Column(String, nullable=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)
    experience_level = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    required_skills = Column(Text, nullable=True)
    application_url = Column(String, nullable=True)
    source = Column(String, nullable=True)
    posted_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
