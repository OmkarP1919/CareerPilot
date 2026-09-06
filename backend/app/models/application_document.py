from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class ApplicationDocument(Base):
    """A document associated with an application.

    STORAGE CONTRACT (Phase 5D Step 1): no binary upload handling is
    implemented yet. This table defines the storage representation only, and it
    reuses the repository's existing file convention (the ``Resume`` model's
    ``filename`` / ``original_filename`` / ``file_path`` / ``file_size``
    columns, backed by files under ``backend/uploads/{user_id}/``). No second
    storage system is introduced.

    A row stores exactly ONE of the following representations:

    1. Reference to an already-uploaded source: ``source_resume_id`` points at
       an existing ``resumes`` row (user-scoped). Used when attaching a resume
       (master or tailored) to an application without copying the file.
    2. An uploaded file: ``filename``, ``original_filename``, ``file_path`` and
       ``file_size`` describe a file stored under the standard uploads
       directory. The future upload endpoint must place files at
       ``backend/uploads/{user_id}/<uuid>.<ext>`` and populate these columns,
       exactly like the ``Resume`` upload flow.

    ``document_type`` (resume, cover_letter, transcript, other, ...) and the
    free-form ``metadata`` JSON column let future endpoints and analytics
    classify documents without schema churn.

    Ownership is enforced with both ``user_id`` and ``application_id``.
    """

    __tablename__ = "application_documents"
    __table_args__ = (
        Index("ix_application_documents_application_id", "application_id"),
        Index("ix_application_documents_user_id", "user_id"),
        Index("ix_application_documents_source_resume_id", "source_resume_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    application_id = Column(String, ForeignKey("applications.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    document_type = Column(String, nullable=False, default="other")
    name = Column(String, nullable=True)
    # Uploaded-file representation (Resume storage convention).
    filename = Column(String, nullable=True)
    original_filename = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    file_size = Column(String, nullable=True)
    # Reference-to-existing-resume representation.
    source_resume_id = Column(String, ForeignKey("resumes.id"), nullable=True)
    meta_data = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    application = relationship("Application", foreign_keys=[application_id], back_populates="documents")
    source_resume = relationship("Resume", foreign_keys=[source_resume_id])