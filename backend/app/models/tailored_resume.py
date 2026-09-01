from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class TailoredResume(Base):
    """A logical AI-tailored version of a source resume for a specific job.

    The original uploaded resume (``Resume``) is NEVER modified. Each tailoring
    is stored as a separate row, isolated by ``user_id`` so a user can never
    read another user's tailored resume.

    ``tailored_data`` stores the structured tailoring result (a plain dict,
    JSON column) and ``tailored_content`` stores the flattened, frontend-ready
    view for convenience.
    """

    __tablename__ = "tailored_resumes"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    source_resume_id = Column(String, ForeignKey("resumes.id"), nullable=False, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)
    version_name = Column(String, default="tailored")
    tailored_content = Column(JSON, nullable=True)
    structured_data = Column(JSON, nullable=True)
    changes = Column(JSON, nullable=True)
    supported_keywords_added = Column(JSON, nullable=True)
    unsupported_job_keywords = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    ai_provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    resume = relationship("Resume", back_populates="tailored_resumes")
