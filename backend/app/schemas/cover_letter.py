"""Schemas for AI Cover Letter generation (Phase 4A).

Includes the structured AI output contract (validated with Pydantic), the API
request, and the API response. The cover letter is a short, professional piece
of writing grounded entirely in the candidate's supplied evidence.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Structured AI output (control contract for the AI provider)
# =============================================================================
class CoverLetterContent(BaseModel):
    """The full structured result the AI must produce.

    ``supported_points`` are the factual, evidence-backed highlights used in the
    body. ``unsupported_requirements`` are job requirements the candidate does
    NOT have supporting evidence for - they must never be presented as facts.
    """

    greeting: str = ""
    opening: str = ""
    body_paragraphs: List[str] = Field(default_factory=list)
    closing: str = ""
    signature: str = ""
    supported_points: List[str] = Field(default_factory=list)
    unsupported_requirements: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# =============================================================================
# API request
# =============================================================================
class CoverLetterRequest(BaseModel):
    resume_id: str
    regenerate: bool = False


# =============================================================================
# API response
# =============================================================================
class CoverLetterResponse(BaseModel):
    id: str
    resume_id: str
    job_id: str
    status: str
    content: str = ""
    structured_content: CoverLetterContent = Field(default_factory=CoverLetterContent)
    supported_points: List[str] = Field(default_factory=list)
    unsupported_requirements: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    changes: List[str] = Field(default_factory=list)
    ai_provider: str = ""
    model: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CoverLetterListItem(BaseModel):
    """A saved cover letter, intended for listing (ownership isolated)."""

    id: str
    job_id: str
    job_title: str = ""
    job_company: str = ""
    source_resume_id: str
    source_resume_name: str = ""
    version_name: str = ""
    content: str = ""
    warnings: List[str] = Field(default_factory=list)
    ai_provider: str = ""
    model: str = ""
    created_at: Optional[datetime] = None
