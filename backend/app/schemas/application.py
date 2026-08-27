from datetime import datetime
from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    job_id: str
    status: str = "Saved"
    application_date: str | None = None
    notes: str | None = None
    resume_version: str | None = None


class ApplicationUpdate(BaseModel):
    status: str | None = None
    application_date: str | None = None
    notes: str | None = None
    resume_version: str | None = None


class ApplicationResponse(BaseModel):
    id: str
    user_id: str
    job_id: str
    status: str
    application_date: str | None
    notes: str | None
    resume_version: str | None
    created_at: datetime
    updated_at: datetime
    job_title: str | None = None
    job_company: str | None = None

    model_config = {"from_attributes": True}
