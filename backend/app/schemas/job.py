from datetime import datetime
from pydantic import BaseModel


class JobCreate(BaseModel):
    title: str
    company: str
    location: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    description: str | None = None
    required_skills: str | None = None
    application_url: str | None = None
    source: str | None = None


class JobUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    employment_type: str | None = None
    experience_level: str | None = None
    description: str | None = None
    required_skills: str | None = None
    application_url: str | None = None
    source: str | None = None


class JobResponse(BaseModel):
    id: str
    user_id: str
    external_id: str | None = None
    title: str
    company: str
    location: str | None
    employment_type: str | None
    experience_level: str | None
    description: str | None
    required_skills: str | None
    application_url: str | None
    source: str | None
    posted_at: datetime | None = None
    fetched_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DiscoveryResponse(BaseModel):
    sources_checked: int
    jobs_fetched: int
    new_jobs: int
    duplicates_skipped: int
    recommendations_updated: int
    errors: list[str]


class RecommendedJob(BaseModel):
    job: JobResponse
    match_score: int
    matched_skills: list[str]
    missing_skills: list[str]
    relevant_projects: list[str]


class PersonalizedDiscoveryResponse(BaseModel):
    queries_used: list[str]
    sources: dict[str, int]
    new_jobs: int
    existing_jobs: int
    matches_created: int
    errors: list[str] = []
    source_statuses: dict[str, str] | None = None

