from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class ApplicationInterview(Base):
    """A scheduled interview associated with an application.

    ``kind`` is the interview format (phone, video, onsite, technical, ...).
    ``status`` tracks the lifecycle of the interview itself (scheduled,
    completed, cancelled, rescheduled, ...). Neither field is hard-wired to the
    application status flow; interviews can exist independently of the
    application's lifecycle state so status updates here never imply a change
    to the parent application.

    Ownership is enforced with both ``user_id`` and ``application_id``.

    Timestamps: ``scheduled_at`` is provided by the client; ``created_at`` /
    ``updated_at`` are maintained by the ORM (SQLAlchemy ``onupdate``).
    """

    __tablename__ = "application_interviews"
    __table_args__ = (
        Index("ix_application_interviews_application_id", "application_id"),
        Index("ix_application_interviews_user_id", "user_id"),
    )

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    application_id = Column(String, ForeignKey("applications.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    kind = Column(String, nullable=False)
    status = Column(String, nullable=False, default="scheduled")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    application = relationship("Application", foreign_keys=[application_id], back_populates="interviews")