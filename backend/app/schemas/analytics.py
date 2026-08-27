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
