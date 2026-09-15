from datetime import datetime
from pydantic import BaseModel, Field


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


# ---------------------------------------------------------------------------
# 7.0D.1 — Personalized feed (additive; never changes RecommendedJob)
# ---------------------------------------------------------------------------


class FeedJob(RecommendedJob):
    """Personalized feed entry: the existing RecommendedJob shape plus an
    additive, factual ``explanation`` sourced directly from the persisted
    profile-matching row (never invented, never AI-generated)."""

    explanation: str | None = None


class FeedJobContext(BaseModel):
    """Factual, descriptive metadata: WHAT candidate data the feed used.

    This object is purely informational — it never adds to or subtracts
    from any score.
    """

    has_profile: bool = False
    has_skills: bool = False
    has_projects: bool = False
    has_experience: bool = False
    has_education: bool = False
    has_certifications: bool = False
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    experience_level: str | None = None


class FeedResponse(BaseModel):
    """Fast, persisted personalized feed.

    The headline ``match_score`` is the canonical PROFILE MATCH score
    (frozen 50/20/15/10/5 weights). The endpoint serves persisted
    recommendations only and performs NO provider fan-out.
    """

    jobs: list[FeedJob] = Field(default_factory=list)
    total: int = 0
    context: FeedJobContext = FeedJobContext()
    errors: list[str] = Field(default_factory=list)
    # Populated only when an explicit personalized-discovery run precedes this
    # response. Feed loads are always the fast path by default.
    refreshed: bool = False
    queries_used: list[str] = Field(default_factory=list)
    new_jobs: int = 0
    existing_jobs: int = 0
    matches_created: int = 0

