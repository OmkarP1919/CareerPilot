from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(String, nullable=True)
    is_master = Column(Boolean, default=False)
    extracted_text = Column(Text, nullable=True)
    parsed_data = Column(JSON, nullable=True)
    parsing_status = Column(String, default="pending")
    parsing_error = Column(Text, nullable=True)
    parsed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Records explicitly derived from this resume. When the user deletes their
    # resume these owned children are removed with it (ORM-level cascade,
    # consistent with the Profile model convention), so the delete never trips
    # a PostgreSQL foreign-key violation for the derived tables.
    resume_job_analyses = relationship(
        "ResumeJobAnalysis",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    tailored_resumes = relationship(
        "TailoredResume",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
    cover_letters = relationship(
        "CoverLetter",
        back_populates="resume",
        cascade="all, delete-orphan",
    )
