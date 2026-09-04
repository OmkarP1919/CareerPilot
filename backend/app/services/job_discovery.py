import json
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.profile import Profile, UserSkill, Project, Experience
from app.models.job import Job
from app.models.job_match import JobMatch
from app.services.matching import calculate_match
from app.services.job_sources.adzuna import AdzunaSource
from app.services.job_sources.jobicy import JobicySource
from app.services.job_sources.jooble import JoobleSource
from app.services.job_sources.base import NormalizedJob, SearchCriteria

logger = logging.getLogger(__name__)

MAX_SEARCH_QUERIES = 4


def generate_search_queries(profile: Profile, skills: list[str]) -> list[str]:
    queries: list[str] = []

    if profile.preferred_roles:
        roles = [r.strip() for r in profile.preferred_roles.split(",") if r.strip()]
        for role in roles[:3]:
            queries.append(role)

    if not queries and skills:
        for skill in skills[:2]:
            queries.append(f"{skill} Developer")

    seen = set()
    unique: list[str] = []
    for q in queries:
        normalized = q.lower().strip()
        if normalized not in seen and len(normalized) >= 2:
            seen.add(normalized)
            unique.append(q.strip())

    return unique[:MAX_SEARCH_QUERIES]


def generate_location_terms(profile: Profile) -> list[str]:
    if not profile.preferred_locations:
        return []
    locations = [l.strip() for l in profile.preferred_locations.split(",") if l.strip()]
    return locations[:1]


def normalize_title_company(title: str, company: str) -> str:
    t = " ".join(title.lower().strip().split())
    c = " ".join(company.lower().strip().split())
    return f"{t}|{c}"


def _upsert_match(
    user_id: str,
    job: Job,
    db: Session,
    existing_matches: dict[str, JobMatch] | None = None,
    profile: Profile | None = None,
    user_skills_set: set[str] | None = None,
    user_projects: list[Project] | None = None,
    user_experiences: list[Experience] | None = None,
) -> bool:
    """Calculates and persists a JobMatch for (user_id, job).

    Returns True only when a NEW JobMatch row was created. Returns False when
    an existing match was left unchanged or updated, enabling idempotent
    match counting across repeated discovery runs.
    """
    result = calculate_match(
        user_id, job, db,
        profile=profile,
        user_skills_set=user_skills_set,
        user_projects=user_projects,
        user_experiences=user_experiences,
    )
    if existing_matches is not None:
        existing_match = existing_matches.get(job.id)
    else:
        existing_match = db.query(JobMatch).filter(
            JobMatch.user_id == user_id, JobMatch.job_id == job.id
        ).first()

    if existing_match:
        if (
            existing_match.overall_score == result["overall_score"]
            and existing_match.skills_score == result["skills_score"]
            and existing_match.role_score == result["role_score"]
        ):
            return False
        existing_match.overall_score = result["overall_score"]
        existing_match.skills_score = result["skills_score"]
        existing_match.project_score = result["project_score"]
        existing_match.experience_score = result["experience_score"]
        existing_match.role_score = result["role_score"]
        existing_match.location_score = result["location_score"]
        existing_match.matched_skills = json.dumps(result["matched_skills"])
        existing_match.missing_skills = json.dumps(result["missing_skills"])
        existing_match.relevant_projects = json.dumps(result["relevant_projects"])
        existing_match.relevant_experience = json.dumps(result["relevant_experience"])
        existing_match.explanation = result["explanation"]
        return False
    else:
        match = JobMatch(
            user_id=user_id,
            job_id=job.id,
            overall_score=result["overall_score"],
            skills_score=result["skills_score"],
            project_score=result["project_score"],
            experience_score=result["experience_score"],
            role_score=result["role_score"],
            location_score=result["location_score"],
            matched_skills=json.dumps(result["matched_skills"]),
            missing_skills=json.dumps(result["missing_skills"]),
            relevant_projects=json.dumps(result["relevant_projects"]),
            relevant_experience=json.dumps(result["relevant_experience"]),
            explanation=result["explanation"],
        )
        db.add(match)
        if existing_matches is not None:
            existing_matches[job.id] = match

    return True


def discover_jobs(user_id: str, db: Session) -> dict:
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if not profile:
        return {
            "sources_checked": 0,
            "jobs_fetched": 0,
            "new_jobs": 0,
            "duplicates_skipped": 0,
            "recommendations_updated": 0,
            "errors": ["No profile found. Complete your profile first."],
        }

    skills = [
        us.skill.name
        for us in db.query(UserSkill).filter(UserSkill.profile_id == profile.id).all()
    ]

    queries = generate_search_queries(profile, skills)
    locations = generate_location_terms(profile)

    if not queries:
        return {
            "sources_checked": 0,
            "jobs_fetched": 0,
            "new_jobs": 0,
            "duplicates_skipped": 0,
            "recommendations_updated": 0,
            "errors": [
                "No search queries could be generated. "
                "Add preferred job roles to your profile."
            ],
        }

    sources = [AdzunaSource(), JobicySource(), JoobleSource()]
    criteria = SearchCriteria(queries=queries, locations=locations)
    all_fetched: list[NormalizedJob] = []
    errors: list[str] = []

    for source in sources:
        try:
            fetched = source.fetch(criteria)
            all_fetched.extend(fetched)
        except Exception as e:
            msg = f"{source.name} failed: {e}"
            logger.exception(msg)
            errors.append(msg)

    new_jobs = 0
    duplicates_skipped = 0
    recommendations_updated = 0
    now = datetime.now(timezone.utc)

    existing_external: dict[tuple[str, str], str] = {}
    for j in db.query(Job).filter(
        Job.external_id.isnot(None),
        Job.source.isnot(None),
    ).all():
        existing_external[(j.external_id, j.source)] = j.id

    existing_title_company: dict[str, str] = {}
    for j in db.query(Job).all():
        key = normalize_title_company(j.title, j.company)
        existing_title_company[key] = j.id

    for fetched in all_fetched:
        if not fetched.title.strip() or not fetched.company.strip():
            continue

        existing_job = None

        if fetched.external_id and fetched.source:
            composite_key = (fetched.external_id, fetched.source)
            if composite_key in existing_external:
                existing_job = db.query(Job).filter(
                    Job.id == existing_external[composite_key]
                ).first()

        if not existing_job:
            tc_key = normalize_title_company(fetched.title, fetched.company)
            if tc_key in existing_title_company:
                existing_job = db.query(Job).filter(
                    Job.id == existing_title_company[tc_key]
                ).first()

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
            duplicates_skipped += 1
            # Ensure the requesting user gets a JobMatch calculated against their profile
            _upsert_match(user_id, existing_job, db)
            recommendations_updated += 1
            continue

        new_job = Job(
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
        db.flush()

        tc_key = normalize_title_company(new_job.title, new_job.company)
        existing_title_company[tc_key] = new_job.id
        if new_job.external_id and new_job.source:
            existing_external[(new_job.external_id, new_job.source)] = new_job.id

        new_jobs += 1
        _upsert_match(user_id, new_job, db)
        recommendations_updated += 1

    db.commit()

    return {
        "sources_checked": len(sources),
        "jobs_fetched": len(all_fetched),
        "new_jobs": new_jobs,
        "duplicates_skipped": duplicates_skipped,
        "recommendations_updated": recommendations_updated,
        "errors": errors,
    }


def get_recommended_jobs(
    user_id: str,
    db: Session,
    min_score: int = 0,
    source: str | None = None,
    remote_only: bool = False,
) -> list[dict]:
    query = (
        db.query(Job, JobMatch)
        .join(JobMatch, JobMatch.job_id == Job.id)
        .filter(JobMatch.user_id == user_id, JobMatch.overall_score >= min_score)
    )

    if source:
        query = query.filter(Job.source == source)

    if remote_only:
        query = query.filter(Job.location.ilike("%remote%"))

    # Multi-tier ranking:
    # 1. Match Score (overall_score desc)
    # 2. Preferred Role Alignment (role_score desc)
    # 3. Freshness (posted_at desc nullslast, created_at desc)
    rows = (
        query.order_by(
            JobMatch.overall_score.desc(),
            JobMatch.role_score.desc(),
            Job.posted_at.desc().nullslast(),
            Job.created_at.desc(),
        )
        .limit(50)
        .all()
    )

    results = []
    for job, match in rows:
        results.append({
            "job": job,
            "match_score": match.overall_score,
            "matched_skills": json.loads(match.matched_skills or "[]"),
            "missing_skills": json.loads(match.missing_skills or "[]"),
            "relevant_projects": json.loads(match.relevant_projects or "[]"),
        })

    return results
