from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.profile import (
    Profile, Education, Skill, UserSkill, Project, Experience, Certification,
)
from app.schemas.profile import (
    ProfileUpdate, ProfileResponse,
    EducationCreate, EducationUpdate, EducationResponse,
    SkillCreate, UserSkillResponse,
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ExperienceCreate, ExperienceUpdate, ExperienceResponse,
    CertificationCreate, CertificationUpdate, CertificationResponse,
    FullProfileResponse,
)

router = APIRouter(prefix="/profile", tags=["profile"])


def get_profile(user: User, db: Session) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        profile = Profile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def get_user_profile(user: User, db: Session) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


# --- Profile ---

@router.get("", response_model=FullProfileResponse)
def get_full_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = get_profile(user, db)
    skills = [
        UserSkillResponse(id=s.id, skill_name=s.skill.name, category=s.category)
        for s in db.query(UserSkill).filter(UserSkill.profile_id == profile.id).all()
    ]
    return FullProfileResponse(
        profile=ProfileResponse.model_validate(profile),
        education=[EducationResponse.model_validate(e) for e in profile.education],
        skills=skills,
        projects=[ProjectResponse.model_validate(p) for p in profile.projects],
        experiences=[ExperienceResponse.model_validate(e) for e in profile.experiences],
        certifications=[CertificationResponse.model_validate(c) for c in profile.certifications],
    )


@router.put("", response_model=ProfileResponse)
def update_profile(
    data: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_profile(user, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


# --- Education ---

@router.post("/education", response_model=EducationResponse, status_code=201)
def add_education(
    data: EducationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    edu = Education(profile_id=profile.id, **data.model_dump())
    db.add(edu)
    db.commit()
    db.refresh(edu)
    return edu


@router.put("/education/{edu_id}", response_model=EducationResponse)
def update_education(
    edu_id: str,
    data: EducationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    edu = db.query(Education).filter(
        Education.id == edu_id, Education.profile_id == profile.id
    ).first()
    if not edu:
        raise HTTPException(status_code=404, detail="Education not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(edu, field, value)
    db.commit()
    db.refresh(edu)
    return edu


@router.delete("/education/{edu_id}", status_code=204)
def delete_education(
    edu_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    edu = db.query(Education).filter(
        Education.id == edu_id, Education.profile_id == profile.id
    ).first()
    if not edu:
        raise HTTPException(status_code=404, detail="Education not found")
    db.delete(edu)
    db.commit()


# --- Skills ---

@router.post("/skills", response_model=UserSkillResponse, status_code=201)
def add_skill(
    data: SkillCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    skill = db.query(Skill).filter(Skill.name == data.name).first()
    if not skill:
        skill = Skill(name=data.name)
        db.add(skill)
        db.commit()
        db.refresh(skill)
    existing = db.query(UserSkill).filter(
        UserSkill.profile_id == profile.id, UserSkill.skill_id == skill.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Skill already added")
    user_skill = UserSkill(profile_id=profile.id, skill_id=skill.id, category=data.category)
    db.add(user_skill)
    db.commit()
    db.refresh(user_skill)
    return UserSkillResponse(id=user_skill.id, skill_name=skill.name, category=user_skill.category)


@router.delete("/skills/{user_skill_id}", status_code=204)
def delete_skill(
    user_skill_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    us = db.query(UserSkill).filter(
        UserSkill.id == user_skill_id, UserSkill.profile_id == profile.id
    ).first()
    if not us:
        raise HTTPException(status_code=404, detail="Skill not found")
    db.delete(us)
    db.commit()


# --- Projects ---

@router.post("/projects", response_model=ProjectResponse, status_code=201)
def add_project(
    data: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    project = Project(profile_id=profile.id, **data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    data: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    project = db.query(Project).filter(
        Project.id == project_id, Project.profile_id == profile.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    project = db.query(Project).filter(
        Project.id == project_id, Project.profile_id == profile.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()


# --- Experience ---

@router.post("/experiences", response_model=ExperienceResponse, status_code=201)
def add_experience(
    data: ExperienceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    exp = Experience(profile_id=profile.id, **data.model_dump())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.put("/experiences/{exp_id}", response_model=ExperienceResponse)
def update_experience(
    exp_id: str,
    data: ExperienceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    exp = db.query(Experience).filter(
        Experience.id == exp_id, Experience.profile_id == profile.id
    ).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(exp, field, value)
    db.commit()
    db.refresh(exp)
    return exp


@router.delete("/experiences/{exp_id}", status_code=204)
def delete_experience(
    exp_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    exp = db.query(Experience).filter(
        Experience.id == exp_id, Experience.profile_id == profile.id
    ).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    db.delete(exp)
    db.commit()


# --- Certifications ---

@router.post("/certifications", response_model=CertificationResponse, status_code=201)
def add_certification(
    data: CertificationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    cert = Certification(profile_id=profile.id, **data.model_dump())
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert


@router.put("/certifications/{cert_id}", response_model=CertificationResponse)
def update_certification(
    cert_id: str,
    data: CertificationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    cert = db.query(Certification).filter(
        Certification.id == cert_id, Certification.profile_id == profile.id
    ).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cert, field, value)
    db.commit()
    db.refresh(cert)
    return cert


@router.delete("/certifications/{cert_id}", status_code=204)
def delete_certification(
    cert_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = get_user_profile(user, db)
    cert = db.query(Certification).filter(
        Certification.id == cert_id, Certification.profile_id == profile.id
    ).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")
    db.delete(cert)
    db.commit()
