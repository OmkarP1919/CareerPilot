from datetime import datetime
from pydantic import BaseModel


class ResumeResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    original_filename: str
    file_size: str | None
    is_master: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
