"""Pydantic contracts for the Phase 5D application pipeline resources.

Step 1 (data-model/schema foundation) only: these schemas define the API
contract for the eventual additive endpoints. They do not register any routes.

Endpoint contract (to be implemented in the endpoint step):

    POST   /applications/{id}/events
    GET    /applications/{id}/events
    POST   /applications/{id}/interviews
    PUT    /applications/{id}/interviews/{interview_id}
    DELETE /applications/{id}/interviews/{interview_id}
    POST   /applications/{id}/documents
    GET    /applications/{id}/documents
    DELETE /applications/{id}/documents/{document_id}
    GET    /applications/{id}/timeline

The existing 8 application statuses and their funnel order are untouched.
"""

from datetime import datetime
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, Field

# Future validation values (endpoints will enforce these).
APPLICATION_EVENT_TYPES = [
    "created",
    "status_changed",
    "note_added",
    "resume_attached",
    "document_attached",
    "interview_scheduled",
    "interview_completed",
    "milestone",
    "other",
]

INTERVIEW_KINDS = [
    "phone",
    "video",
    "onsite",
    "technical",
    "behavioral",
    "assessment",
    "panel",
    "other",
]

INTERVIEW_STATUSES = [
    "scheduled",
    "completed",
    "cancelled",
    "rescheduled",
    "no_show",
]

APPLICATION_DOCUMENT_TYPES = [
    "resume",
    "cover_letter",
    "portfolio",
    "transcript",
    "assessment",
    "contract",
    "other",
]


class ApplicationEventCreate(BaseModel):
    """POST /applications/{id}/events request body."""

    event_type: str
    notes: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] | None = None


class ApplicationEventUpdate(BaseModel):
    """Notes/context are the only mutable event fields (events are append-only)."""

    notes: str | None = None
    metadata: dict[str, Any] | None = None


class ApplicationEventResponse(BaseModel):
    id: str
    application_id: str
    user_id: str
    event_type: str
    notes: str | None
    created_by: str | None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="meta_data")
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationInterviewCreate(BaseModel):
    """POST /applications/{id}/interviews request body."""

    scheduled_at: datetime
    kind: str
    status: str = "scheduled"
    notes: str | None = None


class ApplicationInterviewUpdate(BaseModel):
    """PUT /applications/{id}/interviews/{interview_id} request body."""

    scheduled_at: datetime | None = None
    kind: str | None = None
    status: str | None = None
    notes: str | None = None


class ApplicationInterviewResponse(BaseModel):
    id: str
    application_id: str
    user_id: str
    scheduled_at: datetime
    kind: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationDocumentCreate(BaseModel):
    """POST /applications/{id}/documents metadata body.

    Binary upload handling is deferred to the endpoint step. A document is
    represented either by ``source_resume_id`` (reference to an existing
    user-scoped resume) or by an uploaded file described with the repository's
    standard ``filename``/``original_filename``/``file_path``/``file_size``
    convention; the endpoint owns populating those file fields.
    """

    document_type: str = "other"
    name: str | None = None
    source_resume_id: str | None = None
    metadata: dict[str, Any] | None = None


class ApplicationDocumentResponse(BaseModel):
    """Response for application documents.

    ``file_path`` is deliberately NOT exposed: it is a server-side filesystem
    detail. This mirrors the existing ``ResumeResponse`` contract, which also
    omits ``file_path``. Clients identify an uploaded file by
    ``filename``/``original_filename``/``file_size`` presence and a reference
    document by ``source_resume_id``.
    """

    id: str
    application_id: str
    user_id: str
    document_type: str
    name: str | None
    filename: str | None
    original_filename: str | None
    file_size: str | None
    source_resume_id: str | None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="meta_data")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TimelineBase(BaseModel):
    """Common timeline-entry fields shared by every entry kind.

    ``kind`` discriminates the union; each variant carries only its own
    resource fields (no duplicated data).
    """

    id: str
    application_id: str
    user_id: str
    kind: str
    created_at: datetime


class EventTimelineEntry(TimelineBase):
    kind: Literal["event"] = "event"
    event_type: str
    notes: str | None = None
    created_by: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="meta_data")


class InterviewTimelineEntry(TimelineBase):
    kind: Literal["interview"] = "interview"
    scheduled_at: datetime
    interview_kind: str
    status: str
    notes: str | None = None


class DocumentTimelineEntry(TimelineBase):
    kind: Literal["document"] = "document"
    document_type: str
    name: str | None = None
    source_resume_id: str | None = None


TimelineEntry = Annotated[
    Union[EventTimelineEntry, InterviewTimelineEntry, DocumentTimelineEntry],
    Field(discriminator="kind"),
]


class ApplicationTimelineResponse(BaseModel):
    """GET /applications/{id}/timeline response body.

    A unified, chronological listing of the application's lifecycle events,
    interviews, and document events. The frontend orders by ``created_at``;
    interviews additionally expose ``scheduled_at`` for agenda views.
    """

    application_id: str
    user_id: str
    entries: list[TimelineEntry]