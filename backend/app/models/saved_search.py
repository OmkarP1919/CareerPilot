from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Index
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class SavedSearch(Base):
    """A persisted user search so saved discovery can be re-run later.

    The criteria are stored as canonical JSON so a saved search is human
    readable, version-tolerant, and can be replayed against the discovery
    pipeline at any point in the future. Last-seen canonical job keys let a
    later run report which results are new since the previous run
    (alert-ready design).

    This is intentionally a NEW table; we never ALTER existing tables.
    """

    __tablename__ = "saved_searches"
    __table_args__ = (Index("ix_saved_searches_user_id", "user_id"),)

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    criteria = Column(Text, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    # JSON list of canonical job keys seen at the most recent run
    last_seen_keys = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
