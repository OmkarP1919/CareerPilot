from datetime import datetime
from pydantic import BaseModel


class MatchResponse(BaseModel):
    overall_score: int
    skills_score: int
    project_score: int
    experience_score: int
    role_score: int
    location_score: int
    matched_skills: list[str]
    missing_skills: list[str]
    relevant_projects: list[str]
    relevant_experience: list[str]
    explanation: str


class SavedMatchResponse(BaseModel):
    id: str
    job_id: str
    overall_score: int
    skills_score: int
    project_score: int
    experience_score: int
    role_score: int
    location_score: int
    matched_skills: list[str]
    missing_skills: list[str]
    relevant_projects: list[str]
    relevant_experience: list[str]
    explanation: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
