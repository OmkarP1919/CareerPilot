from datetime import datetime
from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    location: str | None = None
    preferred_roles: str | None = None
    preferred_locations: str | None = None


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    location: str | None
    preferred_roles: str | None
    preferred_locations: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EducationCreate(BaseModel):
    degree: str
    college: str
    branch: str | None = None
    graduation_year: str | None = None
    cgpa: str | None = None


class EducationUpdate(BaseModel):
    degree: str | None = None
    college: str | None = None
    branch: str | None = None
    graduation_year: str | None = None
    cgpa: str | None = None


class EducationResponse(BaseModel):
    id: str
    profile_id: str
    degree: str
    college: str
    branch: str | None
    graduation_year: str | None
    cgpa: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SkillCreate(BaseModel):
    name: str
    category: str


class UserSkillResponse(BaseModel):
    id: str
    skill_name: str
    category: str

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    technologies: str | None = None
    github_url: str | None = None
    live_url: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    technologies: str | None = None
    github_url: str | None = None
    live_url: str | None = None


class ProjectResponse(BaseModel):
    id: str
    profile_id: str
    name: str
    description: str | None
    technologies: str | None
    github_url: str | None
    live_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExperienceCreate(BaseModel):
    company: str
    role: str
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    technologies: str | None = None


class ExperienceUpdate(BaseModel):
    company: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    technologies: str | None = None


class ExperienceResponse(BaseModel):
    id: str
    profile_id: str
    company: str
    role: str
    start_date: str | None
    end_date: str | None
    description: str | None
    technologies: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CertificationCreate(BaseModel):
    name: str
    organization: str | None = None
    issue_date: str | None = None
    credential_url: str | None = None


class CertificationUpdate(BaseModel):
    name: str | None = None
    organization: str | None = None
    issue_date: str | None = None
    credential_url: str | None = None


class CertificationResponse(BaseModel):
    id: str
    profile_id: str
    name: str
    organization: str | None
    issue_date: str | None
    credential_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FullProfileResponse(BaseModel):
    profile: ProfileResponse
    education: list[EducationResponse]
    skills: list[UserSkillResponse]
    projects: list[ProjectResponse]
    experiences: list[ExperienceResponse]
    certifications: list[CertificationResponse]
