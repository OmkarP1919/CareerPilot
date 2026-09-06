from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    status = Column(String, default="Saved")
    application_date = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    resume_version = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Child rows are owned exclusively by this application and are removed via
    # ORM cascade when the application is deleted. Without this, deleting an
    # application on PostgreSQL (which enforces foreign keys) raises a
    # ForeignKeyViolation and turns DELETE /applications/{id} into a 500.
    events = relationship(
        "ApplicationEvent",
        back_populates="application",
        cascade="all, delete-orphan",
    )
    interviews = relationship(
        "ApplicationInterview",
        back_populates="application",
        cascade="all, delete-orphan",
    )
    documents = relationship(
        "ApplicationDocument",
        back_populates="application",
        cascade="all, delete-orphan",
    )
