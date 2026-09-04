from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Filtered discovery request
# ---------------------------------------------------------------------------


class JobFilterRequest(BaseModel):
    """User-facing filter model for the unified filtered discovery endpoint.

    Mirrors the canonical internal :class:`SearchCriteria` so the frontend can
    submit a complete, source-aware search in one object. ``sources`` selects
    which providers to include (empty / None means all enabled providers).
    """

    queries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    country: Optional[str] = None
    radius: Optional[str] = None
    remote: Optional[bool] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    internship_only: Optional[bool] = None
    posted_after: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_period: Optional[str] = None
    salary_currency: Optional[str] = None
    page: int = 1
    page_size: int = 10
    sort: Optional[str] = None
    categories: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    skills_match: str = "any"
    sources: list[str] = Field(default_factory=list)
    # When True, rank results by profile alignment and return match metadata /
    # explanation. When False, results are returned source-ordered and
    # deduplicated without personalized ranking.
    include_profile_alignment: bool = True


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SourceStatusInfo(BaseModel):
    source: str
    status: str
    error: Optional[str] = None
    jobs_fetched: int = 0


class SalaryInfo(BaseModel):
    min: Optional[int] = None
    max: Optional[int] = None
    period: Optional[str] = None
    currency: Optional[str] = None


class MatchInfo(BaseModel):
    overall_score: int = 0
    skills_score: int = 0
    role_score: int = 0
    location_score: int = 0
    freshness: int = 0
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    is_new: bool = False


class DiscoveryJobHit(BaseModel):
    """A single deduplicated job result with cross-source provenance."""

    canonical_key: str
    title: str
    company: str
    location: Optional[str] = None
    work_mode: Optional[str] = None
    employment_type: Optional[str] = None
    experience_level: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    salary: SalaryInfo = SalaryInfo()
    sources: list[str] = Field(default_factory=list)
    primary_source: Optional[str] = None
    application_urls: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    posted_at: Optional[str] = None
    first_seen_at: Optional[str] = None
    freshness: Optional[str] = None
    match: Optional[MatchInfo] = None


class DiscoveryReport(BaseModel):
    total: int = 0
    unique_results: int = 0
    duplicate_count: int = 0
    sources: list[SourceStatusInfo] = Field(default_factory=list)
    selected_sources: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    total_fetched: int = 0
    results: list[DiscoveryJobHit] = Field(default_factory=list)

    def summary(self) -> dict:
        return {
            "total": self.total,
            "unique_results": self.unique_results,
            "duplicate_count": self.duplicate_count,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Saved searches
# ---------------------------------------------------------------------------


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    criteria: dict


class SavedSearchUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    criteria: Optional[dict] = None


class SavedSearchResponse(BaseModel):
    id: str
    name: str
    criteria: dict
    last_run_at: Optional[datetime] = None
    last_seen_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SavedSearchRunResponse(BaseModel):
    saved_search: SavedSearchResponse
    report: DiscoveryReport
    new_results: int = 0
