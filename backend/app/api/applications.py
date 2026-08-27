from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationUpdate, ApplicationResponse

router = APIRouter(prefix="/applications", tags=["applications"])

STATUSES = ["Saved", "Preparing", "Applied", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn"]


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

    existing = db.query(Application).filter(
        Application.user_id == user.id, Application.job_id == data.job_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Application already exists for this job")

    app = Application(user_id=user.id, **data.model_dump())
    db.add(app)
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
    db.delete(app)
    db.commit()
