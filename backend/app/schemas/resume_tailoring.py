"""Schemas for AI Resume Tailoring (Phase 3A).

Includes the structured AI output contract (validated with Pydantic), the API
request, and the API response. No PDF/DOCX generation is part of this phase.
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Structured AI output (control contract for the AI provider)
# =============================================================================
class TailoredSummary(BaseModel):
    original: str = ""
    tailored: str = ""


class TailoredSkillSet(BaseModel):
    kept: List[str] = Field(default_factory=list)
    emphasized: List[str] = Field(default_factory=list)
    removed: List[str] = Field(default_factory=list)


class TailoredExperience(BaseModel):
    original_title: str = ""
    company: str = ""
    original_bullets: List[str] = Field(default_factory=list)
    tailored_bullets: List[str] = Field(default_factory=list)
    changes: List[str] = Field(default_factory=list)


class TailoredProject(BaseModel):
    name: str = ""
    original_description: str = ""
    tailored_description: str = ""
    changes: List[str] = Field(default_factory=list)


class TailoredResumeContent(BaseModel):
    """The full structured result the AI must produce.

    Every piece of factual content is expected to trace back to the source
    resume/profile; this schema is also used as the JSON schema handed to the
    provider for structured output.
    """

    summary: TailoredSummary = Field(default_factory=TailoredSummary)
    skills: TailoredSkillSet = Field(default_factory=TailoredSkillSet)
    experience: List[TailoredExperience] = Field(default_factory=list)
    projects: List[TailoredProject] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    keywords_added: List[str] = Field(default_factory=list)
    keywords_not_added: List[str] = Field(default_factory=list)
    overall_changes: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# =============================================================================
# API request
# =============================================================================
class TailorResumeRequest(BaseModel):
    resume_id: str
    regenerate: bool = False


# =============================================================================
# API response
# =============================================================================
class TailoredContentResponse(BaseModel):
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    emphasized_skills: List[str] = Field(default_factory=list)
    experience: List[dict] = Field(default_factory=list)
    projects: List[dict] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


class OriginalContentResponse(BaseModel):
    """The source (original) resume content, for before/after comparison.

    This is derived from the user's actual parsed resume and is never modified.
    The summary is left empty because the deterministic parser does not extract
    a summary; the tailored summary is shown separately.
    """

    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    experience: List[dict] = Field(default_factory=list)
    projects: List[dict] = Field(default_factory=list)
    education: List[dict] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


class TailorResumeResponse(BaseModel):
    id: str
    resume_id: str
    job_id: str
    status: str
    source_version: str = "original"
    original_content: OriginalContentResponse = Field(default_factory=OriginalContentResponse)
    tailored_content: TailoredContentResponse
    changes: List[str] = Field(default_factory=list)
    supported_keywords_added: List[str] = Field(default_factory=list)
    unsupported_job_keywords: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    ai_provider: str = ""
    model: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TailoredResumeListItem(BaseModel):
    """A saved tailored version, intended for listing on the Resumes page."""

    id: str
    job_id: str
    job_title: str = ""
    job_company: str = ""
    source_resume_id: str
    source_resume_name: str = ""
    original_content: OriginalContentResponse = Field(default_factory=OriginalContentResponse)
    tailored_content: TailoredContentResponse = Field(default_factory=TailoredContentResponse)
    changes: List[str] = Field(default_factory=list)
    supported_keywords_added: List[str] = Field(default_factory=list)
    unsupported_job_keywords: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    ai_provider: str = ""
    model: str = ""
    created_at: Optional[datetime] = None
