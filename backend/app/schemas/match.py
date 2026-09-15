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
    work_mode_score: int | None = None
    education_score: int | None = None
    score_version: str | None = None
    factors: list[dict] | None = None
    reasons: list[str] | None = None


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
    work_mode_score: int | None = None
    education_score: int | None = None
    score_version: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
