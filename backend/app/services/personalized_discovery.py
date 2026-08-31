import re
import logging
import time
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.profile import Profile, UserSkill, Project, Experience, Education
from app.models.job import Job
from app.models.job_match import JobMatch
from app.services.job_discovery import (
    normalize_title_company,
    _upsert_match,
)
from app.services.job_sources.adzuna import AdzunaSource
from app.services.job_sources.jobicy import JobicySource
from app.services.job_sources.base import NormalizedJob, SourceUnavailableError

logger = logging.getLogger(__name__)

INCOMPLETE_PROFILE_MESSAGE = (
    "Complete your profile to discover jobs matched to your skills and goals."
)
NO_PROFILE_MESSAGE = "Create a career profile to enable personalized job discovery."

# Deterministic role signal mapping for skill & project tech sets
ROLE_SIGNALS: dict[str, set[str]] = {
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

# Country resolution map from city/country names to ISO country codes
COUNTRY_MAP: dict[str, str] = {
    "india": "in",
    "pune": "in",
    "mumbai": "in",
    "bangalore": "in",
    "bengaluru": "in",
    "delhi": "in",
    "hyderabad": "in",
    "chennai": "in",
    "gurgaon": "in",
    "gurugram": "in",
    "noida": "in",
    "kolkata": "in",
    "united kingdom": "gb",
    "uk": "gb",
    "great britain": "gb",
    "england": "gb",
    "london": "gb",
    "manchester": "gb",
    "birmingham": "gb",
    "edinburgh": "gb",
    "united states": "us",
    "usa": "us",
    "us": "us",
    "san francisco": "us",
    "new york": "us",
    "seattle": "us",
    "austin": "us",
    "california": "us",
    "chicago": "us",
    "canada": "ca",
    "toronto": "ca",
    "vancouver": "ca",
    "montreal": "ca",
    "germany": "de",
    "berlin": "de",
    "munich": "de",
    "frankfurt": "de",
    "australia": "au",
    "sydney": "au",
    "melbourne": "au",
    "singapore": "sg",
    "new zealand": "nz",
}

GENERIC_TERMS = {"job", "jobs", "developer", "developers", "software", "engineer", "intern", "internship"}


def _empty_result(errors: list[str]) -> dict:
    return {
        "queries_used": [],
        "sources": {},
        "new_jobs": 0,
        "existing_jobs": 0,
        "matches_created": 0,
        "errors": errors,
    }


def resolve_country_and_location(
    location_str: str | None, preferred_locations: str | None
) -> tuple[str | None, list[str]]:
    """Deterministically extracts country code and location terms from profile preferences."""
    combined_parts = []
    if preferred_locations:
        combined_parts.extend([p.strip() for p in preferred_locations.split(",") if p.strip()])
    if location_str:
        combined_parts.extend([p.strip() for p in location_str.split(",") if p.strip()])

    if not combined_parts:
        return None, []

    detected_country = None
    cleaned_locations = []

    for loc in combined_parts:
        loc_lower = loc.lower().strip()
        cleaned_locations.append(loc.strip())
        if not detected_country:
            for keyword, code in COUNTRY_MAP.items():
                if keyword in loc_lower:
                    detected_country = code
                    break

    return detected_country, cleaned_locations[:2]


def classify_experience_level(
    graduation_year_str: str | None, experiences: list[Experience]
) -> str:
    """Classifies user experience: 'student_fresher', 'junior', 'mid', or 'senior'."""
    current_year = datetime.now().year

    # Check graduation year
    if graduation_year_str:
        try:
            grad_year = int(re.sub(r"\D", "", graduation_year_str))
            if grad_year >= current_year:
                return "student_fresher"
        except (ValueError, TypeError):
            pass

    # Evaluate experience entries count
    if not experiences:
        return "student_fresher"

    num_exp = len(experiences)
    if num_exp == 1:
        return "junior"
    elif num_exp <= 3:
        return "mid"
    else:
        return "senior"


def infer_roles_from_skills_and_projects(
    skills: list[str], projects: list[Project], experiences: list[Experience]
) -> list[str]:
    """Infers top 1-3 target roles based on technology and skill overlap."""
    all_tokens = set()

    for s in skills:
        all_tokens.add(s.lower().strip())

    for p in projects:
        if p.technologies:
            for t in p.technologies.split(","):
                if t.strip():
                    all_tokens.add(t.lower().strip())
        if p.name:
            all_tokens.add(p.name.lower().strip())

    for e in experiences:
        if e.technologies:
            for t in e.technologies.split(","):
                if t.strip():
                    all_tokens.add(t.lower().strip())

    if not all_tokens:
        return []

    # Score each candidate role
    role_scores: dict[str, int] = {}
    for role_name, signal_set in ROLE_SIGNALS.items():
        if role_name == "Full Stack Developer":
            # Requires both frontend and backend signals
            has_frontend = bool(all_tokens & ROLE_SIGNALS["Frontend Developer"])
            has_backend = bool(all_tokens & ROLE_SIGNALS["Backend Developer"])
            if has_frontend and has_backend:
                role_scores[role_name] = 3
        else:
            overlap = all_tokens & signal_set
            if overlap:
                role_scores[role_name] = len(overlap)

    # Sort roles by match strength
    sorted_roles = sorted(role_scores.items(), key=lambda x: x[1], reverse=True)
    return [role for role, score in sorted_roles if score > 0][:3]


class PersonalizedQueryBuilder:
    """Generates a small, high-precision, deduplicated set of search queries (3-6 queries)."""

    @classmethod
    def build_queries(
        cls,
        profile: Profile | None,
        skills: list[str],
        projects: list[Project],
        experiences: list[Experience],
        education: list[Education],
    ) -> list[str]:
        if not profile and not skills and not projects:
            return []

        raw_candidates: list[str] = []

        # 1. Preferred Roles (Explicit user choice - highest priority)
        preferred_roles_list = []
        if profile and profile.preferred_roles:
            preferred_roles_list = [
                r.strip() for r in profile.preferred_roles.split(",") if r.strip()
            ]
            for role in preferred_roles_list[:3]:
                raw_candidates.append(role)

        # 2. Inferred Roles from skills & projects (if preferred roles are absent or minimal)
        inferred_roles = infer_roles_from_skills_and_projects(skills, projects, experiences)
        for inf_role in inferred_roles:
            if len(raw_candidates) < 3 and inf_role not in raw_candidates:
                raw_candidates.append(inf_role)

        # 3. Primary Technical Skills Combination
        primary_skills = [s.strip() for s in skills if s.strip() and len(s.strip()) > 1][:3]
        if primary_skills:
            if preferred_roles_list:
                top_role = preferred_roles_list[0]
                top_skill = primary_skills[0]
                # Avoid "Python Developer Python"
                if top_skill.lower() not in top_role.lower():
                    raw_candidates.append(f"{top_skill} {top_role}")
            else:
                for skill in primary_skills[:2]:
                    raw_candidates.append(f"{skill} Developer")

        # 4. Experience Level Modifiers (Supplement queries - max 1-2 modified queries)
        grad_year = education[0].graduation_year if education else None
        exp_level = classify_experience_level(grad_year, experiences)

        if exp_level in ("student_fresher", "junior") and raw_candidates:
            base = raw_candidates[0]
            if not any(k in base.lower() for k in ("junior", "entry", "intern", "internship", "graduate")):
                raw_candidates.append(f"Junior {base}")

        # 5. Normalization, Deduplication & Redundant Term Elimination
        final_queries: list[str] = []
        seen_normalized = set()

        for query in raw_candidates:
            cleaned = re.sub(r"\s+", " ", query).strip()
            if not cleaned or len(cleaned) < 3:
                continue

            lower_q = cleaned.lower()

            # Reject purely generic single terms
            if lower_q in GENERIC_TERMS:
                continue

            # Exact duplicate check
            if lower_q in seen_normalized:
                continue

            # Subsumption / redundant permutation check
            # e.g., if "Python Developer" exists, do not add "Developer Python"
            words = sorted(lower_q.split())
            canonical_key = " ".join(words)
            if canonical_key in seen_normalized:
                continue

            seen_normalized.add(lower_q)
            seen_normalized.add(canonical_key)
            final_queries.append(cleaned)

            # Strict limit: 3-6 queries (max 8)
            if len(final_queries) >= 6:
                break

        return final_queries


class PersonalizedDiscoveryService:
    """Orchestrates personalized discovery by generating queries and leveraging existing sources."""

    @classmethod
    def discover(cls, user_id: str, db: Session) -> dict:
        started = time.perf_counter()
        logger.info("Personalized discovery started for user %s", user_id)

        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if not profile:
            logger.info("Personalized discovery aborted for user %s: no profile", user_id)
            return _empty_result([NO_PROFILE_MESSAGE])

        user_skills = [
            us.skill.name
            for us in db.query(UserSkill).filter(UserSkill.profile_id == profile.id).all()
        ]
        projects = db.query(Project).filter(Project.profile_id == profile.id).all()
        experiences = db.query(Experience).filter(Experience.profile_id == profile.id).all()
        education = db.query(Education).filter(Education.profile_id == profile.id).all()
        logger.info(
            "Profile loaded for user %s: %d skills, %d projects, %d exp, %d edu",
            user_id, len(user_skills), len(projects), len(experiences), len(education),
        )

        # Build personalized queries
        queries = PersonalizedQueryBuilder.build_queries(
            profile, user_skills, projects, experiences, education
        )
        logger.info("Queries generated for user %s: %s", user_id, queries)

        if not queries:
            logger.info(
                "Personalized discovery aborted for user %s: insufficient profile data", user_id
            )
            return _empty_result([INCOMPLETE_PROFILE_MESSAGE])

        # Resolve location and country
        detected_country, location_terms = resolve_country_and_location(
            profile.location, profile.preferred_locations
        )
        logger.info(
            "Country detected for user %s: '%s', locations: %s",
            user_id, detected_country, location_terms,
        )

        # Source orchestration with isolated exception handling
        adzuna = AdzunaSource()
        jobicy = JobicySource()

        sources_counts: dict[str, int] = {"Adzuna": 0, "Jobicy": 0}
        all_fetched: list[NormalizedJob] = []
        errors: list[str] = []

        # Fetch from Adzuna (top 2 queries)
        try:
            adzuna_jobs = adzuna.fetch(queries[:2], location_terms, country=detected_country)
            sources_counts["Adzuna"] = len(adzuna_jobs)
            all_fetched.extend(adzuna_jobs)
            logger.info("Adzuna returned %d jobs for user %s", len(adzuna_jobs), user_id)
        except SourceUnavailableError as e:
            logger.warning("Adzuna unavailable for user %s: %s", user_id, e)
            errors.append("Adzuna was temporarily unavailable.")
        except Exception:
            logger.exception("Adzuna search failed for user %s", user_id)
            errors.append("Adzuna was temporarily unavailable.")

        # Fetch from Jobicy (top 2 queries)
        try:
            jobicy_jobs = jobicy.fetch(queries[:2], location_terms)
            sources_counts["Jobicy"] = len(jobicy_jobs)
            all_fetched.extend(jobicy_jobs)
            logger.info("Jobicy returned %d jobs for user %s", len(jobicy_jobs), user_id)
        except SourceUnavailableError as e:
            logger.warning("Jobicy unavailable for user %s: %s", user_id, e)
            errors.append("Jobicy was temporarily unavailable.")
        except Exception:
            logger.exception("Jobicy search failed for user %s", user_id)
            errors.append("Jobicy was temporarily unavailable.")

        # Global Deduplication & Global Job Upsert
        new_jobs = 0
        existing_jobs = 0
        matches_created = 0
        now = datetime.now(timezone.utc)

        existing_matches = {
            m.job_id: m for m in db.query(JobMatch).filter(JobMatch.user_id == user_id).all()
        }
        user_skills_set = {s.lower().strip() for s in user_skills if s.strip()}

        existing_external: dict[tuple[str, str], Job] = {}
        for j in db.query(Job).filter(
            Job.external_id.isnot(None),
            Job.source.isnot(None),
        ).all():
            existing_external[(j.external_id, j.source)] = j

        existing_title_company: dict[str, Job] = {}
        for j in db.query(Job).all():
            key = normalize_title_company(j.title, j.company)
            existing_title_company[key] = j

        for fetched in all_fetched:
            try:
                if not fetched.title.strip() or not fetched.company.strip():
                    continue

                existing_job = None

                if fetched.external_id and fetched.source:
                    composite_key = (fetched.external_id, fetched.source)
                    existing_job = existing_external.get(composite_key)

                if not existing_job:
                    tc_key = normalize_title_company(fetched.title, fetched.company)
                    existing_job = existing_title_company.get(tc_key)

                if existing_job:
                    if fetched.description and not existing_job.description:
                        existing_job.description = fetched.description
                    if fetched.application_url and not existing_job.application_url:
                        existing_job.application_url = fetched.application_url
                    if fetched.posted_at and not existing_job.posted_at:
                        try:
                            existing_job.posted_at = datetime.fromisoformat(
                                fetched.posted_at.replace("Z", "+00:00")
                            )
                        except (ValueError, TypeError):
                            pass
                    existing_jobs += 1
                    created = _upsert_match(
                        user_id,
                        existing_job,
                        db,
                        existing_matches=existing_matches,
                        profile=profile,
                        user_skills_set=user_skills_set,
                        user_projects=projects,
                        user_experiences=experiences,
                    )
                    if created:
                        matches_created += 1
                    continue

                job_uuid = str(uuid.uuid4())
                new_job = Job(
                    id=job_uuid,
                    user_id=user_id,
                    external_id=fetched.external_id,
                    title=fetched.title.strip(),
                    company=fetched.company.strip(),
                    location=fetched.location,
                    employment_type=fetched.employment_type,
                    experience_level=fetched.experience_level,
                    description=fetched.description,
                    application_url=fetched.application_url,
                    source=fetched.source,
                    fetched_at=now,
                )

                if fetched.posted_at:
                    try:
                        new_job.posted_at = datetime.fromisoformat(
                            fetched.posted_at.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                db.add(new_job)

                tc_key = normalize_title_company(new_job.title, new_job.company)
                existing_title_company[tc_key] = new_job
                if new_job.external_id and new_job.source:
                    existing_external[(new_job.external_id, new_job.source)] = new_job

                new_jobs += 1
                created = _upsert_match(
                    user_id,
                    new_job,
                    db,
                    existing_matches=existing_matches,
                    profile=profile,
                    user_skills_set=user_skills_set,
                    user_projects=projects,
                    user_experiences=experiences,
                )
                if created:
                    matches_created += 1
            except Exception:
                # A single malformed record must not abort the whole discovery run.
                logger.exception("Failed to process a discovered job for user %s", user_id)

        db.commit()

        duration = round(time.perf_counter() - started, 2)
        logger.info(
            "Discovery completed for user %s in %ss: new=%d existing=%d matches=%d source_errors=%d",
            user_id, duration, new_jobs, existing_jobs, matches_created, len(errors),
        )

        return {
            "queries_used": queries,
            "sources": sources_counts,
            "new_jobs": new_jobs,
            "existing_jobs": existing_jobs,
            "matches_created": matches_created,
            "errors": errors,
        }