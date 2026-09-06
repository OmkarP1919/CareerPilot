from datetime import datetime
from pydantic import BaseModel


class StatusCount(BaseModel):
    status: str
    count: int


class FunnelStage(BaseModel):
    stage: str
    count: int


class SkillFrequency(BaseModel):
    skill: str
    count: int
    type: str  # "matched" or "missing"


class RecentApplication(BaseModel):
    id: str
    job_title: str | None
    job_company: str | None
    status: str
    updated_at: datetime


class RecentJob(BaseModel):
    id: str
    title: str
    company: str
    created_at: datetime


class DashboardResponse(BaseModel):
    total_jobs: int
    high_match_jobs: int
    total_applications: int
    saved_count: int
    applied_count: int
    interview_count: int
    offer_count: int
    rejected_count: int
    average_match_score: int | None
    recent_applications: list[RecentApplication]
    recent_jobs: list[RecentJob]


class ApplicationFunnelResponse(BaseModel):
    funnel: list[FunnelStage]
    total: int


class SkillsAnalyticsResponse(BaseModel):
    frequent_missing: list[SkillFrequency]
    frequent_matched: list[SkillFrequency]
    total_analyses: int


# ---------------------------------------------------------------------------
# Phase 5D Step 3 - trustworthy activity + velocity analytics
# ---------------------------------------------------------------------------

class ActivityBucket(BaseModel):
    """One time bucket (a calendar week) of real user activity.

    ``period`` is the ISO date (YYYY-MM-DD) of the bucket's week start (Monday),
    in UTC. ``events`` counts application_events rows the user created that week
    (including auto-generated lifecycle events); ``applications`` counts
    applications created; ``interviews`` counts interview records created;
    ``documents`` counts application documents created. Every count is derived
    from rows owned by the authenticated user - never fabricated.
    """

    period: str
    events: int
    applications: int
    interviews: int
    documents: int


class ActivityResponse(BaseModel):
    """GET /analytics/activity response.

    ``start_date`` / ``end_date`` echo the resolved (UTC date) range actually
    covered so clients can render axis labels deterministically. ``buckets`` is
    one entry per week in that range, earliest first. Empty users return an
    empty ``buckets`` list (all-zero weeks), never fabricated activity.
    """

    start_date: str
    end_date: str
    buckets: list[ActivityBucket]


class VelocityMetric(BaseModel):
    """A single median lifecycle metric with its real sample count.

    ``median_days`` is the median elapsed time (float) computed from the user's
    own status-transition records, or None when the user has no qualifying
    transitions. ``sample_size`` is the exact number of qualifying transitions
    (0 is a truthful count, not a fabricated zero). A None median is never
    replaced with an estimate.
    """

    median_days: float | None
    sample_size: int


class VelocityResponse(BaseModel):
    """GET /analytics/velocity response.

    Both metrics are user-scoped and derived exclusively from the authenticated
    user's own status_changed events and application records.
    """

    applied_to_interview: VelocityMetric
    applied_to_offer: VelocityMetric
