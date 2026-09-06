from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class ApplicationEvent(Base):
    """Immutable audit/history record for an application's lifecycle.

    Represents a single user- or system-initiated activity on an application
    (status change, note added, milestone reached, ...). Rows are append-only
    by design; the future endpoints must never mutate an existing event.

    Ownership is enforced with both ``user_id`` (the owning user) and
    ``application_id`` (the parent application) so future endpoints can assert
    ``user owns application AND event belongs to that application`` without
    trusting the application_id alone.

    ``created_by`` records the actor that recorded the event (a user id, or a
    reserved future actor such as "system"). ``metadata`` is a free-form JSON
    context payload (e.g. ``{"from_status": "Preparing", "to_status": "Applied"}``).

    The JSON column is exposed in the API contract as ``metadata``. The SQLAlchemy
    mapped attribute is ``meta_data`` because the name ``metadata`` is reserved by
    the Declarative API (InvalidRequestError).
    """

    __tablename__ = "application_events"
    __table_args__ = (
        Index("ix_application_events_application_id", "application_id"),
        Index("ix_application_events_user_id", "user_id"),
        Index("ix_application_events_application_created", "application_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    application_id = Column(String, ForeignKey("applications.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    event_type = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    meta_data = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    application = relationship("Application", foreign_keys=[application_id], back_populates="events")