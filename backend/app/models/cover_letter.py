from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class CoverLetter(Base):
    """A grounded, AI-generated cover letter for a specific job, generated from
    a specific source resume.

    The original uploaded resume (``Resume``) is NEVER modified. Each generated
    cover letter is stored as a separate row, isolated by ``user_id`` so a user
    can never read or modify another user's cover letter.

    ``structured_data`` stores the validated structured generation result (a
    plain dict in a JSON column). ``content`` stores the final assembled cover
    letter text (the greeting + paragraphs + closing + signature joined) for
    convenient display / export.

    Privacy: no API keys or raw prompts are stored. Only the generated text and
    structured content plus provenance metadata (provider, model) are kept.
    """

    __tablename__ = "cover_letters"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    source_resume_id = Column(String, ForeignKey("resumes.id"), nullable=False, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)
    version_name = Column(String, default="cover-letter")
    content = Column(Text, nullable=True)
    structured_data = Column(JSON, nullable=True)
    changes = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    ai_provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    resume = relationship("Resume", back_populates="cover_letters")
