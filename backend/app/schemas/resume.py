from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class ResumeResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    original_filename: str
    file_size: str | None
    is_master: bool
    parsing_status: str
    parsing_error: str | None
    parsed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResumeParsedResponse(BaseModel):
    resume_id: str
    parsing_status: str
    parsed_at: datetime | None
    parsing_error: str | None
    data: dict[str, Any]

    model_config = {"from_attributes": True}
