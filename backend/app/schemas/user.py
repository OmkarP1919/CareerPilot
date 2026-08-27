from datetime import datetime
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: str
    firebase_uid: str
    email: str
    name: str
    profile_picture_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
