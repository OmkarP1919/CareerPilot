from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    location = Column(String, nullable=True)
    preferred_roles = Column(Text, nullable=True)
    preferred_locations = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", backref="profile", uselist=False)
    education = relationship("Education", back_populates="profile", cascade="all, delete-orphan")
    skills = relationship("UserSkill", back_populates="profile", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="profile", cascade="all, delete-orphan")
    experiences = relationship("Experience", back_populates="profile", cascade="all, delete-orphan")
    certifications = relationship("Certification", back_populates="profile", cascade="all, delete-orphan")


class Education(Base):
    __tablename__ = "education"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    degree = Column(String, nullable=False)
    college = Column(String, nullable=False)
    branch = Column(String, nullable=True)
    graduation_year = Column(String, nullable=True)
    cgpa = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    profile = relationship("Profile", back_populates="education")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    name = Column(String, unique=True, nullable=False)


class UserSkill(Base):
    __tablename__ = "user_skills"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    skill_id = Column(String, ForeignKey("skills.id"), nullable=False)
    category = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    profile = relationship("Profile", back_populates="skills")
    skill = relationship("Skill")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    technologies = Column(Text, nullable=True)
    github_url = Column(String, nullable=True)
    live_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    profile = relationship("Profile", back_populates="projects")


class Experience(Base):
    __tablename__ = "experiences"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    technologies = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    profile = relationship("Profile", back_populates="experiences")


class Certification(Base):
    __tablename__ = "certifications"

    id = Column(String, primary_key=True, default=lambda: str(__import__("uuid").uuid4()))
    profile_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    name = Column(String, nullable=False)
    organization = Column(String, nullable=True)
    issue_date = Column(String, nullable=True)
    credential_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    profile = relationship("Profile", back_populates="certifications")
