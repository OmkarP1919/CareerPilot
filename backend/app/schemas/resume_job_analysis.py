from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class ResumeAnalysisRequest(BaseModel):
    resume_id: str


class RelevantProject(BaseModel):
    name: str | None = None
    relevance_score: float
    matched_technologies: list[str] = []
    reason: str


class RelevantExperience(BaseModel):
    job_title: str | None = None
    company: str | None = None
    dates: str | None = None
    relevance_score: float
    reason: str


class EducationCertificationRelevance(BaseModel):
    score: int | None = None
    reason: str | None = None


class ResumeAnalysisResponse(BaseModel):
    id: str
    job_id: str
    resume_id: str
    overall_score: int
    scores: dict[str, int | None]
    matched_skills: list[str]
    missing_skills: list[str]
    additional_relevant_skills: list[str] = []
    matched_keywords: list[str]
    missing_keywords: list[str]
    relevant_projects: list[RelevantProject]
    relevant_experience: list[RelevantExperience]
    education_certification_relevance: EducationCertificationRelevance
    suggestions: list[str]
    note: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
