"""Canonical deterministic ranking and matching engine (Phase 7.0D.3).

Establishes ONE unified ranking model across CareerPilot:
- Replaces independent discovery scoring formulas
- Shares factor semantics and canonical skill vocabulary with Resume Match
- Preserves the frozen v1 matching.py intact for backward compatibility
- Produces explainable, evidence-based factor breakdowns with score_version="v2"
- Strictly zero-LLM: 100% deterministic mathematical evaluation

Canonical Factor Model (Active Weights, Total = 100):
- skills:      35
- experience:  20
- role:        15
- projects:    10
- location:    10
- education:    5
- work_mode:    5

Dynamic Active-Factor Normalization:
    overall = round(
        sum(score * weight for active factors)
        / sum(weight for active factors)
    )
Unavailable factors are marked available=False and are NEVER penalized as zero.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.models.profile import (
    Certification,
    Education,
    Experience,
    Profile,
    Project,
    UserSkill,
)
from app.services.resume_parser import SKILL_VOCABULARY, match_skill

logger = logging.getLogger(__name__)

# =============================================================================
# Factor Weights (Total = 100)
# =============================================================================
CANONICAL_FACTOR_WEIGHTS: Dict[str, int] = {
    "skills": 35,
    "experience": 20,
    "role": 15,
    "projects": 10,
    "location": 10,
    "education": 5,
    "work_mode": 5,
}

# Role domain signals (deterministic, shared vocabulary)
ROLE_SIGNALS: Dict[str, Set[str]] = {
    "Backend Developer": {
        "fastapi", "django", "flask", "express", "nestjs", "spring", "springboot",
        "nodejs", "node.js", "graphql", "rest api", "rest apis", "microservices",
        "sql", "postgresql", "postgres", "mongodb", "redis", "kafka", "rabbitmq",
    },
    "Python Developer": {
        "python", "fastapi", "django", "flask", "pandas", "numpy", "pytest",
        "celery", "pydantic", "sqlalchemy", "asyncio",
    },
    "Frontend Developer": {
        "react", "react.js", "reactjs", "vue", "vue.js", "angular", "next.js",
        "nextjs", "javascript", "typescript", "html", "css", "tailwind", "redux",
    },
    "Full Stack Developer": {
        "mern", "mean", "full stack", "fullstack", "full-stack",
    },
    "Data Analyst": {
        "pandas", "numpy", "sql", "powerbi", "power bi", "tableau", "excel",
        "data analysis", "matplotlib", "seaborn", "analytics", "bi",
    },
    "Machine Learning Engineer": {
        "machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn",
        "sklearn", "nlp", "computer vision", "llm", "transformers", "huggingface", "ai",
    },
    "Java Developer": {
        "java", "spring", "springboot", "hibernate", "maven", "gradle", "jvm",
    },
    "DevOps / Cloud Engineer": {
        "docker", "kubernetes", "k8s", "aws", "azure", "gcp", "terraform",
        "ci/cd", "jenkins", "ansible", "linux", "cloud",
    },
    "PHP Developer": {
        "php", "laravel", "symfony", "codeigniter", "wordpress",
    },
    "Mobile Developer": {
        "flutter", "react native", "swift", "kotlin", "android", "ios", "dart",
    },
}

# Safe skill alias mapping (deterministic, canonical targets)
_SAFE_SKILL_ALIASES: Dict[str, str] = {
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "react native": "React Native",
    "reactnative": "React Native",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "next": "Next.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "mariadb": "MariaDB",
    "expressjs": "Express",
    "express": "Express",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
}

# Regex for detecting explicit education requirements in job description
_EDUCATION_REQ_RE = re.compile(
    r"(?i)\b(?:degree|bachelor|master|phd|doctorate|mba|b\.?tech|m\.?tech|"
    r"b\.?sc|m\.?sc|bachelor's|master's|diploma|graduate|postgraduate|"
    r"qualification|certification|certified|license)\b"
)

# Common fields of study for CS/Eng roles
_TECH_FIELDS_OF_STUDY = {
    "computer science", "software engineering", "information technology",
    "computer engineering", "data science", "machine learning",
    "artificial intelligence", "electrical engineering", "mathematics",
    "statistics", "engineering",
}


# =============================================================================
# Helper Functions
# =============================================================================

def canonicalize_skill(skill: str) -> str:
    """Normalize a skill token to its canonical form using aliases and vocabulary."""
    if not skill:
        return ""
    cleaned = skill.strip()
    compact = re.sub(r"[^a-z0-9]", "", cleaned.lower())
    lower = cleaned.lower()

    if lower in _SAFE_SKILL_ALIASES:
        return _SAFE_SKILL_ALIASES[lower]
    if compact in _SAFE_SKILL_ALIASES:
        return _SAFE_SKILL_ALIASES[compact]

    matched = match_skill(cleaned)
    if matched:
        m_compact = re.sub(r"[^a-z0-9]", "", matched.lower())
        return _SAFE_SKILL_ALIASES.get(m_compact, matched)

    return cleaned


def parse_skill_list(raw_skills: Any) -> List[str]:
    """Parse comma-separated strings or list of skills into canonical skill names."""
    if not raw_skills:
        return []
    items: List[str] = []
    if isinstance(raw_skills, str):
        parts = [p.strip() for p in raw_skills.split(",") if p.strip()]
        for p in parts:
            c = canonicalize_skill(p)
            if c and c not in items:
                items.append(c)
    elif isinstance(raw_skills, (list, set, tuple)):
        for p in raw_skills:
            if isinstance(p, str) and p.strip():
                c = canonicalize_skill(p)
                if c and c not in items:
                    items.append(c)
    return items


def extract_skills_from_text(text: str) -> List[str]:
    """Detect known canonical skills from text using multi-word and token scanning."""
    if not text:
        return []
    lowered = text.lower()
    found: List[str] = []
    seen: Set[str] = set()

    # 1. Check multi-word skills from vocabulary first
    multi_word_skills = [s for s in SKILL_VOCABULARY if " " in s or "/" in s or "-" in s]
    for skill in multi_word_skills:
        pattern = r"\b" + re.escape(skill.lower()) + r"\b"
        if re.search(pattern, lowered):
            c = canonicalize_skill(skill)
            if c.lower() not in seen:
                seen.add(c.lower())
                found.append(c)

    # 2. Check alias multi-word keys
    for alias_key, target in _SAFE_SKILL_ALIASES.items():
        if " " in alias_key or "/" in alias_key or "-" in alias_key:
            pattern = r"\b" + re.escape(alias_key) + r"\b"
            if re.search(pattern, lowered):
                c = canonicalize_skill(target)
                if c.lower() not in seen:
                    seen.add(c.lower())
                    found.append(c)

    # 3. Check single tokens
    tokens = re.findall(r"[A-Za-z0-9+#.]+", text)
    for token in tokens:
        c = canonicalize_skill(token)
        if c and c.lower() not in seen and match_skill(c):
            seen.add(c.lower())
            found.append(c)

    return found


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """Retrieve attribute or dict key safely."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class ProfileRankingContext:
    """Preloaded, immutable candidate profile context for O(1) ranking."""
    user_id: str
    has_profile: bool = False
    skills: List[str] = field(default_factory=list)
    user_skills_set: Set[str] = field(default_factory=set)
    projects: List[Any] = field(default_factory=list)
    experiences: List[Any] = field(default_factory=list)
    education: List[Any] = field(default_factory=list)
    certifications: List[Any] = field(default_factory=list)
    preferred_roles: List[str] = field(default_factory=list)
    preferred_locations: List[str] = field(default_factory=list)
    work_mode_preference: Optional[str] = None
    classified_experience_level: Optional[str] = None


@dataclass
class FactorResult:
    """Detailed result for an individual factor in the canonical model."""
    key: str
    score: Optional[int]
    weight: int
    available: bool
    evidence: Optional[str]


@dataclass
class RankResult:
    """Canonical deterministic ranking outcome (score_version='v2')."""
    overall_score: int
    score_version: str = "v2"
    factors: List[FactorResult] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    relevant_projects: List[str] = field(default_factory=list)
    relevant_experience: List[str] = field(default_factory=list)
    factor_scores: Dict[str, Optional[int]] = field(default_factory=dict)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "score_version": self.score_version,
            "factors": [asdict(f) for f in self.factors],
            "reasons": self.reasons,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "relevant_projects": self.relevant_projects,
            "relevant_experience": self.relevant_experience,
            "factor_scores": self.factor_scores,
            "explanation": self.explanation,
        }


# =============================================================================
# Context Loader (Single DB Query Batch)
# =============================================================================

def load_profile_context(user_id: str, db: Session) -> ProfileRankingContext:
    """Load all candidate profile entities in ONE batch.

    Guarantees no O(N) database queries during batch job evaluation.
    """
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        return ProfileRankingContext(user_id=user_id, has_profile=False)

    user_skills = db.query(UserSkill).filter(UserSkill.profile_id == profile.id).all()
    skills = [us.skill.name for us in user_skills if us.skill and us.skill.name]
    canonical_skills = [canonicalize_skill(s) for s in skills if s.strip()]
    user_skills_set = {s.lower() for s in canonical_skills}

    projects = db.query(Project).filter(Project.profile_id == profile.id).all()
    experiences = db.query(Experience).filter(Experience.profile_id == profile.id).all()
    education = db.query(Education).filter(Education.profile_id == profile.id).all()
    certifications = db.query(Certification).filter(Certification.profile_id == profile.id).all()

    pref_roles = [
        r.strip() for r in (profile.preferred_roles or "").split(",") if r.strip()
    ]
    pref_locs = [
        l.strip() for l in (profile.preferred_locations or "").split(",") if l.strip()
    ]

    # Infer remote preference only if explicitly present in locations
    work_mode_pref = None
    if any("remote" in l.lower() for l in pref_locs):
        work_mode_pref = "remote"

    from app.services.personalized_discovery import classify_experience_level

    grad_year = education[0].graduation_year if education else None
    grad_year_str = str(grad_year) if grad_year else None
    exp_level = classify_experience_level(grad_year_str, experiences)

    return ProfileRankingContext(
        user_id=user_id,
        has_profile=True,
        skills=canonical_skills,
        user_skills_set=user_skills_set,
        projects=projects,
        experiences=experiences,
        education=education,
        certifications=certifications,
        preferred_roles=pref_roles,
        preferred_locations=pref_locs,
        work_mode_preference=work_mode_pref,
        classified_experience_level=exp_level,
    )


# =============================================================================
# Individual Factor Evaluators
# =============================================================================

def _evaluate_skills(
    job: Any,
    candidate_skills: List[str],
    candidate_skills_set: Set[str],
    job_description: str,
) -> Tuple[FactorResult, List[str], List[str]]:
    """Evaluates skills with multi-word & alias awareness, using required skills, provider tags, or text."""
    weight = CANONICAL_FACTOR_WEIGHTS["skills"]

    # 1. Primary: explicitly stated job.required_skills
    raw_req = _safe_get(job, "required_skills")
    parsed_skills = parse_skill_list(raw_req)
    source_type = "required"

    # 2. Secondary: provider-supplied skill tags (NormalizedJob.skills or Job.skills)
    if not parsed_skills:
        raw_tags = _safe_get(job, "skills")
        parsed_skills = parse_skill_list(raw_tags)
        if parsed_skills:
            source_type = "provider_tag"

    if parsed_skills:
        # Deduplicate canonicalized skills by lowercased token to avoid double-counting
        seen_skills = set()
        deduped_req = []
        for req in parsed_skills:
            req_c = canonicalize_skill(req)
            if req_c and req_c.lower() not in seen_skills:
                seen_skills.add(req_c.lower())
                deduped_req.append(req_c)

        if deduped_req:
            matched = [r for r in deduped_req if r.lower() in candidate_skills_set]
            missing = [r for r in deduped_req if r.lower() not in candidate_skills_set]
            score = round((len(matched) / len(deduped_req)) * 100)
            if source_type == "required":
                evidence = f"Matches {len(matched)} of {len(deduped_req)} required skills"
            else:
                evidence = f"Matches {len(matched)} of {len(deduped_req)} provider-tagged skills"
            return (
                FactorResult(key="skills", score=score, weight=weight, available=True, evidence=evidence),
                sorted(matched),
                sorted(missing),
            )

    # 3. Structured/tagged skills absent: extract recognized skills from available job text
    job_text = " ".join([
        _safe_get(job, "title", "") or "",
        job_description or "",
        _safe_get(job, "category", "") or "",
    ])
    job_skills = extract_skills_from_text(job_text)

    if not job_skills:
        return (
            FactorResult(
                key="skills",
                score=None,
                weight=weight,
                available=False,
                evidence="Job does not specify required skills, provider tags, or recognizable technical skills in description",
            ),
            [],
            [],
        )

    # Bounded, honest coverage over detected job skills
    matched = [s for s in job_skills if s.lower() in candidate_skills_set]
    missing = [s for s in job_skills if s.lower() not in candidate_skills_set]

    score = round((len(matched) / len(job_skills)) * 100)
    evidence = (
        f"Matches {len(matched)} of {len(job_skills)} skills identified in description "
        "(structured required skills and provider tags not specified by job)"
    )
    return (
        FactorResult(key="skills", score=score, weight=weight, available=True, evidence=evidence),
        sorted(matched),
        sorted(missing),
    )


def _evaluate_role(
    job_title: str,
    preferred_roles: List[str],
) -> FactorResult:
    """Evaluates role alignment using preferred roles and ROLE_SIGNALS."""
    weight = CANONICAL_FACTOR_WEIGHTS["role"]
    if not preferred_roles:
        return FactorResult(
            key="role",
            score=None,
            weight=weight,
            available=False,
            evidence="No preferred roles specified on profile",
        )

    title_lower = (job_title or "").lower().strip()
    if not title_lower:
        return FactorResult(
            key="role",
            score=None,
            weight=weight,
            available=False,
            evidence="Job title not specified",
        )

    norm_prefs = [r.lower().strip() for r in preferred_roles if r.strip()]

    # 1. Exact or substring match in job title
    for pref in norm_prefs:
        if pref in title_lower:
            return FactorResult(
                key="role",
                score=100,
                weight=weight,
                available=True,
                evidence=f"Job title aligns directly with preferred role '{pref.title()}'",
            )

    # 2. Token overlap
    title_words = set(re.findall(r"[a-z0-9]+", title_lower))
    best_score = 25
    best_evidence = "Role is outside preferred roles"

    for pref in norm_prefs:
        pref_words = set(re.findall(r"[a-z0-9]+", pref))
        overlap = pref_words & title_words
        if len(overlap) >= 2:
            best_score = max(best_score, 85)
            best_evidence = f"Strong title overlap with preferred role '{pref.title()}'"
        elif len(overlap) == 1 and not overlap.issubset({"developer", "engineer", "specialist"}):
            best_score = max(best_score, 75)
            best_evidence = f"Role shares key domain term '{list(overlap)[0]}' with '{pref.title()}'"

    # 3. Domain signals from ROLE_SIGNALS
    if best_score < 70:
        for pref in norm_prefs:
            for role_name, signals in ROLE_SIGNALS.items():
                if pref in role_name.lower():
                    hits = sum(1 for s in signals if s in title_lower)
                    if hits >= 1:
                        best_score = max(best_score, 70)
                        best_evidence = f"Role title relates to domain signals of '{pref.title()}'"
                        break

    return FactorResult(
        key="role",
        score=best_score,
        weight=weight,
        available=True,
        evidence=best_evidence,
    )


def _evaluate_experience(
    job: Any,
    candidate_exp_level: Optional[str],
    candidate_experiences: List[Any],
) -> FactorResult:
    """Evaluates experience level compatibility without inventing YOE."""
    weight = CANONICAL_FACTOR_WEIGHTS["experience"]
    job_level = (_safe_get(job, "experience_level") or "").strip().lower()

    if not job_level:
        return FactorResult(
            key="experience",
            score=None,
            weight=weight,
            available=False,
            evidence="Job does not specify an experience level requirement",
        )

    cand_level = (candidate_exp_level or "mid").lower()

    level_ranks = {
        "intern": 1,
        "student_fresher": 1,
        "entry": 2,
        "junior": 2,
        "entry level": 2,
        "mid": 3,
        "mid level": 3,
        "senior": 4,
        "senior level": 4,
        "lead": 5,
        "principal": 5,
    }

    job_rank = level_ranks.get(job_level, 3)
    cand_rank = level_ranks.get(cand_level, 3)
    diff = abs(job_rank - cand_rank)

    if diff == 0:
        score = 100
        evidence = f"Experience level '{job_level.title()}' directly matches candidate level"
    elif diff == 1:
        score = 80
        evidence = f"Experience level '{job_level.title()}' is adjacent/compatible with candidate level"
    elif diff == 2:
        score = 40
        evidence = f"Experience level '{job_level.title()}' differs from candidate level"
    else:
        score = 20
        evidence = f"Significant difference in experience level requirements ('{job_level.title()}')"

    return FactorResult(
        key="experience",
        score=score,
        weight=weight,
        available=True,
        evidence=evidence,
    )


def _evaluate_projects(
    job: Any,
    projects: List[Any],
    all_job_skills: Set[str],
    job_description: str,
) -> Tuple[FactorResult, List[str]]:
    """Evaluates candidate project relevance based on technology overlap."""
    weight = CANONICAL_FACTOR_WEIGHTS["projects"]
    if not projects:
        return (
            FactorResult(
                key="projects",
                score=None,
                weight=weight,
                available=False,
                evidence="No candidate projects recorded on profile",
            ),
            [],
        )

    job_desc_words = set(re.findall(r"[a-z0-9]+", (job_description or "").lower()))
    job_skills_lower = {s.lower() for s in all_job_skills}

    relevant_projects = []
    for proj in projects:
        proj_name = _safe_get(proj, "name", "")
        proj_tech_raw = _safe_get(proj, "technologies", "") or ""
        if isinstance(proj_tech_raw, (list, set, tuple)):
            proj_techs = {str(t).lower().strip() for t in proj_tech_raw if t}
        else:
            proj_techs = {t.lower().strip() for t in str(proj_tech_raw).split(",") if t.strip()}
        proj_desc = (_safe_get(proj, "description", "") or "").lower()
        proj_words = set(re.findall(r"[a-z0-9]+", f"{proj_name.lower()} {proj_desc}"))

        tech_overlap = bool(proj_techs & job_skills_lower)
        keyword_overlap = bool(proj_words & job_desc_words) if job_desc_words else False

        if tech_overlap or keyword_overlap:
            relevant_projects.append(proj_name)

    score = min(100, round((len(relevant_projects) / max(1, min(3, len(projects)))) * 100))
    if relevant_projects:
        evidence = f"Found {len(relevant_projects)} relevant project(s) matching job technologies"
    else:
        evidence = "No candidate projects overlap with job technologies or description"

    return (
        FactorResult(key="projects", score=score, weight=weight, available=True, evidence=evidence),
        relevant_projects,
    )


def _evaluate_location(
    job: Any,
    preferred_locations: List[str],
) -> FactorResult:
    """Evaluates location match deterministically including remote roles."""
    weight = CANONICAL_FACTOR_WEIGHTS["location"]
    job_location = (_safe_get(job, "location") or "").strip()

    if not preferred_locations:
        return FactorResult(
            key="location",
            score=None,
            weight=weight,
            available=False,
            evidence="No preferred locations configured on profile",
        )

    if not job_location:
        return FactorResult(
            key="location",
            score=None,
            weight=weight,
            available=False,
            evidence="Job does not specify a location",
        )

    job_loc_lower = job_location.lower()
    norm_prefs = [p.lower().strip() for p in preferred_locations if p.strip()]

    # 1. Exact or substring match of preferred location in job location
    for pl in norm_prefs:
        if pl in job_loc_lower:
            return FactorResult(
                key="location",
                score=100,
                weight=weight,
                available=True,
                evidence=f"Job location '{job_location}' matches preferred location '{pl.title()}'",
            )

    # 2. Remote job handling
    is_remote = "remote" in job_loc_lower or _safe_get(job, "work_mode") == "remote"
    if is_remote:
        return FactorResult(
            key="location",
            score=90,
            weight=weight,
            available=True,
            evidence="Remote job aligns with location flexibility",
        )

    # 3. Location does not match
    return FactorResult(
        key="location",
        score=20,
        weight=weight,
        available=True,
        evidence=f"Job location '{job_location}' is outside preferred locations",
    )


def _evaluate_work_mode(
    job: Any,
    candidate_work_mode_pref: Optional[str],
) -> FactorResult:
    """Evaluates work mode only when candidate preference is available."""
    weight = CANONICAL_FACTOR_WEIGHTS["work_mode"]
    job_work_mode = _safe_get(job, "work_mode")
    job_loc = (_safe_get(job, "location") or "").lower()

    if not job_work_mode and "remote" in job_loc:
        job_work_mode = "remote"

    if not candidate_work_mode_pref:
        return FactorResult(
            key="work_mode",
            score=None,
            weight=weight,
            available=False,
            evidence="No candidate work-mode preference configured",
        )

    if not job_work_mode:
        return FactorResult(
            key="work_mode",
            score=None,
            weight=weight,
            available=False,
            evidence="Job does not specify work mode (remote/hybrid/onsite)",
        )

    cand_pref = candidate_work_mode_pref.lower()
    job_wm = str(job_work_mode).lower()

    if cand_pref == job_wm:
        score = 100
        evidence = f"Work mode '{job_wm.title()}' matches candidate preference"
    elif cand_pref == "remote" and job_wm == "hybrid":
        score = 50
        evidence = "Job is hybrid; candidate prefers fully remote"
    elif cand_pref == "remote" and job_wm == "onsite":
        score = 20
        evidence = "Job is onsite; candidate prefers remote"
    else:
        score = 70
        evidence = f"Work mode is '{job_wm.title()}'"

    return FactorResult(
        key="work_mode",
        score=score,
        weight=weight,
        available=True,
        evidence=evidence,
    )


def _evaluate_education(
    job_description: str,
    education_entries: List[Any],
    certifications: List[Any],
) -> FactorResult:
    """Evaluates education ONLY when the job description expresses a requirement."""
    weight = CANONICAL_FACTOR_WEIGHTS["education"]
    if not job_description or not _EDUCATION_REQ_RE.search(job_description):
        return FactorResult(
            key="education",
            score=None,
            weight=weight,
            available=False,
            evidence="Job does not state specific education or degree requirements",
        )

    if not education_entries and not certifications:
        return FactorResult(
            key="education",
            score=30,
            weight=weight,
            available=True,
            evidence="Job states education requirements but candidate has no education recorded",
        )

    matched_degree = False
    for edu in education_entries:
        deg = (_safe_get(edu, "degree", "") or "").lower()
        branch = (_safe_get(edu, "branch", "") or "").lower()
        if any(field in branch or field in deg for field in _TECH_FIELDS_OF_STUDY):
            matched_degree = True
            break
        if "bachelor" in deg or "b.tech" in deg or "btech" in deg or "master" in deg or "m.tech" in deg:
            matched_degree = True
            break

    if matched_degree or certifications:
        score = 100
        evidence = "Candidate degree/certification aligns with job requirements"
    else:
        score = 60
        evidence = "Candidate has completed education; specific degree specialization may vary"

    return FactorResult(
        key="education",
        score=score,
        weight=weight,
        available=True,
        evidence=evidence,
    )


# =============================================================================
# Main Canonical Scorer
# =============================================================================

def calculate_rank(
    profile_context: Optional[ProfileRankingContext] = None,
    resume_context: Optional[Dict[str, Any]] = None,
    job: Any = None,
) -> RankResult:
    """Calculate canonical deterministic match score and factor breakdown (v2).

    Operates on preloaded candidate context and job object in memory (O(1)).
    Uses dynamic active-factor re-weighting so unavailable factors do NOT penalize candidates.
    """
    if job is None:
        return _empty_rank_result("No job provided")

    if (profile_context is None or not profile_context.has_profile) and not resume_context:
        return _empty_rank_result("Complete your profile to get personalized match scores")

    candidate_skills: List[str] = []
    candidate_skills_set: Set[str] = set()
    preferred_roles: List[str] = []
    preferred_locations: List[str] = []
    projects: List[Any] = []
    experiences: List[Any] = []
    education: List[Any] = []
    certifications: List[Any] = []
    work_mode_pref: Optional[str] = None
    exp_level: Optional[str] = None

    if profile_context and profile_context.has_profile:
        candidate_skills.extend(profile_context.skills)
        candidate_skills_set.update(profile_context.user_skills_set)
        preferred_roles.extend(profile_context.preferred_roles)
        preferred_locations.extend(profile_context.preferred_locations)
        projects.extend(profile_context.projects)
        experiences.extend(profile_context.experiences)
        education.extend(profile_context.education)
        certifications.extend(profile_context.certifications)
        work_mode_pref = profile_context.work_mode_preference
        exp_level = profile_context.classified_experience_level

    if resume_context:
        r_skills = parse_skill_list(resume_context.get("skills", []))
        candidate_skills.extend(r_skills)
        candidate_skills_set.update(s.lower() for s in r_skills)
        if not projects:
            projects.extend(resume_context.get("projects", []))
        if not experiences:
            experiences.extend(resume_context.get("experience", []))
        if not education:
            education.extend(resume_context.get("education", []))
        if not certifications:
            certifications.extend(resume_context.get("certifications", []))

    job_title = _safe_get(job, "title", "") or ""
    job_desc = _safe_get(job, "description", "") or ""

    # Evaluate 7 factors
    skills_factor, matched_skills, missing_skills = _evaluate_skills(
        job, candidate_skills, candidate_skills_set, job_desc
    )
    role_factor = _evaluate_role(job_title, preferred_roles)
    exp_factor = _evaluate_experience(job, exp_level, experiences)

    all_job_skills = set(matched_skills + missing_skills)
    projects_factor, relevant_projects = _evaluate_projects(
        job, projects, all_job_skills, job_desc
    )
    location_factor = _evaluate_location(job, preferred_locations)
    work_mode_factor = _evaluate_work_mode(job, work_mode_pref)
    education_factor = _evaluate_education(job_desc, education, certifications)

    factors = [
        skills_factor,
        exp_factor,
        role_factor,
        projects_factor,
        location_factor,
        education_factor,
        work_mode_factor,
    ]

    # Evaluate relevant experiences for reporting
    relevant_experience = []
    job_desc_words = set(re.findall(r"[a-z0-9]+", f"{job_title.lower()} {job_desc.lower()}"))
    for exp in experiences:
        e_role = _safe_get(exp, "role") or _safe_get(exp, "job_title", "")
        e_comp = _safe_get(exp, "company", "")
        e_tech_raw = _safe_get(exp, "technologies", "") or ""
        if isinstance(e_tech_raw, (list, set, tuple)):
            e_tech = {str(t).lower().strip() for t in e_tech_raw if t}
        else:
            e_tech = {t.lower().strip() for t in str(e_tech_raw).split(",") if t.strip()}
        if e_tech & {s.lower() for s in all_job_skills} or (e_role and e_role.lower() in job_title.lower()):
            relevant_experience.append(f"{e_role} at {e_comp}" if e_comp else str(e_role))

    # Dynamic Active-Factor Normalization
    active_factors = [f for f in factors if f.available and f.score is not None]
    if active_factors:
        total_active_weight = sum(f.weight for f in active_factors)
        weighted_sum = sum(f.score * f.weight for f in active_factors)
        overall_score = round(weighted_sum / total_active_weight)
    else:
        overall_score = 10

    reasons: List[str] = []
    for f in factors:
        if f.available and f.evidence:
            reasons.append(f.evidence)

    factor_scores: Dict[str, Optional[int]] = {
        f.key: f.score if f.available else None for f in factors
    }

    explanation = _build_explanation(
        overall_score=overall_score,
        skills_factor=skills_factor,
        role_factor=role_factor,
        location_factor=location_factor,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        relevant_projects=relevant_projects,
    )

    return RankResult(
        overall_score=overall_score,
        score_version="v2",
        factors=factors,
        reasons=reasons,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        relevant_projects=relevant_projects,
        relevant_experience=relevant_experience,
        factor_scores=factor_scores,
        explanation=explanation,
    )


def _build_explanation(
    overall_score: int,
    skills_factor: FactorResult,
    role_factor: FactorResult,
    location_factor: FactorResult,
    matched_skills: List[str],
    missing_skills: List[str],
    relevant_projects: List[str],
) -> str:
    """Construct factual, evidence-based user-facing match summary."""
    parts = [f"Overall match: {overall_score}%."]

    if skills_factor.available and skills_factor.score is not None:
        if matched_skills:
            parts.append(
                f"Skills match: {skills_factor.score}% — covers {len(matched_skills)} skills "
                f"({', '.join(matched_skills[:4])}{'...' if len(matched_skills) > 4 else ''})."
            )
        else:
            parts.append("No directly matching technical skills found.")

    if missing_skills:
        parts.append(
            f"Missing skills to acquire: {', '.join(missing_skills[:4])}"
            f"{'...' if len(missing_skills) > 4 else ''}."
        )

    if relevant_projects:
        parts.append(f"Relevant projects: {len(relevant_projects)}.")

    if role_factor.available and role_factor.score is not None:
        if role_factor.score >= 80:
            parts.append("Role aligns with preferred career roles.")
        elif role_factor.score < 50:
            parts.append("Job role differs from stated preferred roles.")

    if location_factor.available and location_factor.score is not None:
        if location_factor.score >= 80:
            parts.append("Location aligns with your preferences.")

    return " ".join(parts)


def _empty_rank_result(reason: str) -> RankResult:
    """Return neutral empty result for candidates without profile data."""
    factors = [
        FactorResult(key=k, score=None, weight=w, available=False, evidence=reason)
        for k, w in CANONICAL_FACTOR_WEIGHTS.items()
    ]
    return RankResult(
        overall_score=0,
        score_version="v2",
        factors=factors,
        reasons=[reason],
        matched_skills=[],
        missing_skills=[],
        relevant_projects=[],
        relevant_experience=[],
        factor_scores={k: None for k in CANONICAL_FACTOR_WEIGHTS},
        explanation=reason,
    )
