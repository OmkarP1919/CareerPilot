import os
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.application_event import ApplicationEvent
from app.models.application_interview import ApplicationInterview
from app.models.application_document import ApplicationDocument
from app.schemas.application import ApplicationCreate, ApplicationUpdate, ApplicationResponse
from app.schemas.application_pipeline import (
    APPLICATION_DOCUMENT_TYPES,
    APPLICATION_EVENT_TYPES,
    INTERVIEW_KINDS,
    INTERVIEW_STATUSES,
    ApplicationDocumentCreate,
    ApplicationDocumentResponse,
    ApplicationEventCreate,
    ApplicationEventResponse,
    ApplicationInterviewCreate,
    ApplicationInterviewResponse,
    ApplicationInterviewUpdate,
    ApplicationTimelineResponse,
    DocumentTimelineEntry,
    EventTimelineEntry,
    InterviewTimelineEntry,
)

logger = logging.getLogger("app.api.applications")

router = APIRouter(prefix="/applications", tags=["applications"])

STATUSES = ["Saved", "Preparing", "Applied", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn"]

# Phase 5D - application documents reuse the repository's existing file-storage
# convention (see app.api.resumes): physical files live under
# backend/uploads/{user_id}/, the size limit matches the Resume upload limit,
# and only document formats already native to the project are accepted.
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB, matches the Resume upload limit
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx"}


def _get_own_application(app_id: str, user: User, db: Session) -> Application:
    """Fetch an application owned by the requesting user or 404.

    Every sub-resource endpoint calls this first so a client-supplied
    application_id is never trusted without an ownership check.
    """
    application = db.query(Application).filter(
        Application.id == app_id, Application.user_id == user.id
    ).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _record_event(
    db: Session,
    application: Application,
    user: User,
    event_type: str,
    notes: str | None = None,
    metadata: dict | None = None,
) -> ApplicationEvent:
    """Append a lifecycle event for the application. ``created_by`` is always
    the actor executing the request (the authenticated user)."""
    event = ApplicationEvent(
        application_id=application.id,
        user_id=user.id,
        event_type=event_type,
        notes=notes,
        created_by=user.id,
        meta_data=metadata,
    )
    db.add(event)
    return event


def _validate_event_type(event_type: str):
    if event_type not in APPLICATION_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event_type. Must be one of: {', '.join(APPLICATION_EVENT_TYPES)}",
        )


def _validate_interview_kind(kind: str):
    if kind not in INTERVIEW_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interview kind. Must be one of: {', '.join(INTERVIEW_KINDS)}",
        )


def _validate_interview_status(status: str):
    if status not in INTERVIEW_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interview status. Must be one of: {', '.join(INTERVIEW_STATUSES)}",
        )


def _validate_document_type(document_type: str):
    if document_type not in APPLICATION_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document_type. Must be one of: {', '.join(APPLICATION_DOCUMENT_TYPES)}",
        )


def _normalize_utc_datetime(value: datetime) -> datetime:
    """Require a timezone-aware ``scheduled_at`` and normalize it to UTC.

    The ORM's DateTime columns store naive UTC (project convention: the same
    value ``utcnow()`` writes to created_at/updated_at). Naive client input is
    rejected rather than silently assuming a timezone.
    """
    if value.tzinfo is None:
        raise HTTPException(
            status_code=400,
            detail="scheduled_at must include a timezone offset",
        )
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    status: str = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Application).filter(Application.user_id == user.id)
    if status:
        query = query.filter(Application.status == status)
    apps = query.order_by(Application.updated_at.desc()).all()

    result = []
    for app in apps:
        job = db.query(Job).filter(Job.id == app.job_id).first()
        result.append(ApplicationResponse(
            id=app.id,
            user_id=app.user_id,
            job_id=app.job_id,
            status=app.status,
            application_date=app.application_date,
            notes=app.notes,
            resume_version=app.resume_version,
            created_at=app.created_at,
            updated_at=app.updated_at,
            job_title=job.title if job else None,
            job_company=job.company if job else None,
        ))
    return result


@router.post("", response_model=ApplicationResponse, status_code=201)
def create_application(
    data: ApplicationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == data.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if data.status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(STATUSES)}")

    existing = db.query(Application).filter(
        Application.user_id == user.id, Application.job_id == data.job_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Application already exists for this job")

    app = Application(user_id=user.id, **data.model_dump())
    db.add(app)
    db.flush()
    # Lifecycle start: every application gets a "created" event in the same
    # transaction so the timeline is self-complete from the moment the
    # application exists.
    _record_event(db, app, user, "created")
    db.commit()
    db.refresh(app)
    return ApplicationResponse(
        id=app.id,
        user_id=app.user_id,
        job_id=app.job_id,
        status=app.status,
        application_date=app.application_date,
        notes=app.notes,
        resume_version=app.resume_version,
        created_at=app.created_at,
        updated_at=app.updated_at,
        job_title=job.title,
        job_company=job.company,
    )


@router.put("/{app_id}", response_model=ApplicationResponse)
def update_application(
    app_id: str,
    data: ApplicationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = db.query(Application).filter(
        Application.id == app_id, Application.user_id == user.id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    update_data = data.model_dump(exclude_unset=True)
    if "status" in update_data and update_data["status"] not in STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(STATUSES)}")

    # Status transitions are recorded as immutable "status_changed" events
    # (applied only when the status actually changes). The existing status
    # contract and response shape are untouched.
    if "status" in update_data and update_data["status"] != app.status:
        _record_event(
            db,
            app,
            user,
            "status_changed",
            metadata={"from_status": app.status, "to_status": update_data["status"]},
        )

    for field, value in update_data.items():
        setattr(app, field, value)
    db.commit()
    db.refresh(app)

    job = db.query(Job).filter(Job.id == app.job_id).first()
    return ApplicationResponse(
        id=app.id,
        user_id=app.user_id,
        job_id=app.job_id,
        status=app.status,
        application_date=app.application_date,
        notes=app.notes,
        resume_version=app.resume_version,
        created_at=app.created_at,
        updated_at=app.updated_at,
        job_title=job.title if job else None,
        job_company=job.company if job else None,
    )


@router.delete("/{app_id}", status_code=204)
def delete_application(
    app_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = db.query(Application).filter(
        Application.id == app_id, Application.user_id == user.id
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    # Physically uploaded documents (file_path set, NOT a reference) own their
    # file on disk exclusively, so those files are removed with the parent.
    # Reference documents (source_resume_id set) NEVER have the referenced
    # resume's file touched, and a user deletion is scoped to that user's own
    # rows. The paths are captured before delete and removed only after the
    # transaction commits successfully.
    uploaded_file_paths = [
        document.file_path
        for document in db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.application_id == app.id,
            ApplicationDocument.user_id == user.id,
        )
        .all()
        if document.file_path is not None and document.source_resume_id is None
    ]

    db.delete(app)
    db.commit()

    for file_path in uploaded_file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            logger.warning("Could not remove application document file from disk after application deletion")


# ---------------------------------------------------------------------------
# Phase 5D - application events
# ---------------------------------------------------------------------------

@router.get("/{app_id}/events", response_model=list[ApplicationEventResponse])
def list_application_events(
    app_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
):
    application = _get_own_application(app_id, user, db)
    events = (
        db.query(ApplicationEvent)
        .filter(
            ApplicationEvent.application_id == application.id,
            ApplicationEvent.user_id == user.id,
        )
        .order_by(ApplicationEvent.created_at, ApplicationEvent.id)
        .limit(limit)
        .all()
    )
    return [ApplicationEventResponse.model_validate(e) for e in events]


@router.post("/{app_id}/events", response_model=ApplicationEventResponse, status_code=201)
def create_application_event(
    app_id: str,
    data: ApplicationEventCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = _get_own_application(app_id, user, db)
    _validate_event_type(data.event_type)

    # The actor is the authenticated user; a client-supplied created_by is
    # never trusted (audit integrity). Server-side system events will set a
    # reserved actor when they are introduced.
    event = ApplicationEvent(
        application_id=application.id,
        user_id=user.id,
        event_type=data.event_type,
        notes=data.notes,
        created_by=user.id,
        meta_data=data.metadata,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return ApplicationEventResponse.model_validate(event)


# ---------------------------------------------------------------------------
# Phase 5D - application interviews
# ---------------------------------------------------------------------------

@router.get("/{app_id}/interviews", response_model=list[ApplicationInterviewResponse])
def list_application_interviews(
    app_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = _get_own_application(app_id, user, db)
    interviews = (
        db.query(ApplicationInterview)
        .filter(
            ApplicationInterview.application_id == application.id,
            ApplicationInterview.user_id == user.id,
        )
        .order_by(ApplicationInterview.scheduled_at, ApplicationInterview.id)
        .all()
    )
    return [ApplicationInterviewResponse.model_validate(i) for i in interviews]


@router.post("/{app_id}/interviews", response_model=ApplicationInterviewResponse, status_code=201)
def create_application_interview(
    app_id: str,
    data: ApplicationInterviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = _get_own_application(app_id, user, db)
    _validate_interview_kind(data.kind)
    _validate_interview_status(data.status)

    interview = ApplicationInterview(
        application_id=application.id,
        user_id=user.id,
        scheduled_at=_normalize_utc_datetime(data.scheduled_at),
        kind=data.kind,
        status=data.status,
        notes=data.notes,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return ApplicationInterviewResponse.model_validate(interview)


@router.put("/{app_id}/interviews/{interview_id}", response_model=ApplicationInterviewResponse)
def update_application_interview(
    app_id: str,
    interview_id: str,
    data: ApplicationInterviewUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = _get_own_application(app_id, user, db)
    interview = (
        db.query(ApplicationInterview)
        .filter(
            ApplicationInterview.id == interview_id,
            ApplicationInterview.application_id == application.id,
            ApplicationInterview.user_id == user.id,
        )
        .first()
    )
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    update_data = data.model_dump(exclude_unset=True)
    if "kind" in update_data:
        _validate_interview_kind(update_data["kind"])
    if "status" in update_data:
        _validate_interview_status(update_data["status"])
    if "scheduled_at" in update_data:
        update_data["scheduled_at"] = _normalize_utc_datetime(update_data["scheduled_at"])

    for field, value in update_data.items():
        setattr(interview, field, value)
    db.commit()
    db.refresh(interview)
    return ApplicationInterviewResponse.model_validate(interview)


@router.delete("/{app_id}/interviews/{interview_id}", status_code=204)
def delete_application_interview(
    app_id: str,
    interview_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = _get_own_application(app_id, user, db)
    interview = (
        db.query(ApplicationInterview)
        .filter(
            ApplicationInterview.id == interview_id,
            ApplicationInterview.application_id == application.id,
            ApplicationInterview.user_id == user.id,
        )
        .first()
    )
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    db.delete(interview)
    db.commit()


# ---------------------------------------------------------------------------
# Phase 5D - application documents
# ---------------------------------------------------------------------------

@router.get("/{app_id}/documents", response_model=list[ApplicationDocumentResponse])
def list_application_documents(
    app_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = _get_own_application(app_id, user, db)
    documents = (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.application_id == application.id,
            ApplicationDocument.user_id == user.id,
        )
        .order_by(ApplicationDocument.created_at, ApplicationDocument.id)
        .all()
    )
    return [ApplicationDocumentResponse.model_validate(d) for d in documents]


@router.post("/{app_id}/documents", response_model=ApplicationDocumentResponse, status_code=201)
def attach_application_document(
    app_id: str,
    data: ApplicationDocumentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reference mode: attach an existing user-owned Resume (source_resume_id)."""
    application = _get_own_application(app_id, user, db)
    _validate_document_type(data.document_type)

    if not data.source_resume_id:
        raise HTTPException(
            status_code=400,
            detail="source_resume_id is required to attach an existing resume",
        )

    # The referenced resume must exist AND belong to the current user. Both a
    # missing and a foreign resume return 404 so existence is not leaked.
    resume = db.query(Resume).filter(
        Resume.id == data.source_resume_id, Resume.user_id == user.id
    ).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    document = ApplicationDocument(
        application_id=application.id,
        user_id=user.id,
        document_type=data.document_type,
        name=data.name,
        source_resume_id=resume.id,
        meta_data=data.metadata,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return ApplicationDocumentResponse.model_validate(document)


@router.post("/{app_id}/documents/upload", response_model=ApplicationDocumentResponse, status_code=201)
async def upload_application_document(
    app_id: str,
    file: UploadFile = File(...),
    document_type: str | None = Form(None),
    name: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload mode: store a new application document under the repository's
    standard uploads directory (backend/uploads/{user_id}/)."""
    application = _get_own_application(app_id, user, db)
    doc_type = document_type or "other"
    _validate_document_type(doc_type)

    if not file.filename:
        raise HTTPException(status_code=400, detail="A file is required")

    # Never trust a client-supplied path: only the basename is ever used, and a
    # regenerated server-side uuid filename is what actually hits the disk.
    original_filename = os.path.basename(file.filename.replace("\\", "/"))
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Only {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))} files are allowed",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")

    user_dir = os.path.join(UPLOAD_DIR, user.id)
    os.makedirs(user_dir, exist_ok=True)

    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    file_path = os.path.join(user_dir, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    document = ApplicationDocument(
        application_id=application.id,
        user_id=user.id,
        document_type=doc_type,
        name=name,
        filename=filename,
        original_filename=original_filename,
        file_path=file_path,
        file_size=str(len(content)),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return ApplicationDocumentResponse.model_validate(document)


@router.delete("/{app_id}/documents/{document_id}", status_code=204)
def delete_application_document(
    app_id: str,
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    application = _get_own_application(app_id, user, db)
    document = (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.id == document_id,
            ApplicationDocument.application_id == application.id,
            ApplicationDocument.user_id == user.id,
        )
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Application document not found")

    # A physically uploaded file is owned exclusively by this document row and
    # is safe to remove. A reference document (source_resume_id) NEVER has the
    # referenced resume's file removed by this endpoint.
    file_path = document.file_path
    remove_physical_file = file_path is not None and document.source_resume_id is None

    db.delete(document)
    db.commit()

    if remove_physical_file:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            logger.warning("Could not remove application document file from disk after a committed deletion")


# ---------------------------------------------------------------------------
# Phase 5D - unified application timeline
# ---------------------------------------------------------------------------

@router.get("/{app_id}/timeline", response_model=ApplicationTimelineResponse)
def get_application_timeline(
    app_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(200, ge=1, le=500),
):
    application = _get_own_application(app_id, user, db)

    events = (
        db.query(ApplicationEvent)
        .filter(
            ApplicationEvent.application_id == application.id,
            ApplicationEvent.user_id == user.id,
        )
        .all()
    )
    interviews = (
        db.query(ApplicationInterview)
        .filter(
            ApplicationInterview.application_id == application.id,
            ApplicationInterview.user_id == user.id,
        )
        .all()
    )
    documents = (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.application_id == application.id,
            ApplicationDocument.user_id == user.id,
        )
        .all()
    )

    entries = []
    for event in events:
        entries.append(EventTimelineEntry(
            id=event.id,
            application_id=event.application_id,
            user_id=event.user_id,
            created_at=event.created_at,
            event_type=event.event_type,
            notes=event.notes,
            created_by=event.created_by,
            meta_data=event.meta_data,
        ))
    for interview in interviews:
        # scheduled_at is the agenda time; created_at is the record-creation
        # time and is what drives chronology below.
        entries.append(InterviewTimelineEntry(
            id=interview.id,
            application_id=interview.application_id,
            user_id=interview.user_id,
            created_at=interview.created_at,
            scheduled_at=interview.scheduled_at,
            interview_kind=interview.kind,
            status=interview.status,
            notes=interview.notes,
        ))
    for document in documents:
        entries.append(DocumentTimelineEntry(
            id=document.id,
            application_id=document.application_id,
            user_id=document.user_id,
            created_at=document.created_at,
            document_type=document.document_type,
            name=document.name,
            source_resume_id=document.source_resume_id,
        ))

    # Deterministic chronological order: created_at ascending, stable
    # tie-breaking on (kind, id).
    entries.sort(key=lambda entry: (entry.created_at, entry.kind, entry.id))

    return ApplicationTimelineResponse(
        application_id=application.id,
        user_id=user.id,
        entries=entries[:limit],
    )