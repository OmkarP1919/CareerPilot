import json
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.profile import Profile, UserSkill, Project, Experience
from app.models.job import Job
from app.models.job_match import JobMatch
from app.services.matching import calculate_match
from app.services.ranking import (
    calculate_rank,
    load_profile_context,
    ProfileRankingContext,
    canonicalize_skill,
)
from app.services.job_sources.adzuna import AdzunaSource
from app.services.job_sources.jobicy import JobicySource
from app.services.job_sources.jooble import JoobleSource
from app.services.job_sources.remoteok import RemoteOKSource
from app.services.job_sources.remotive import RemotiveSource
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
    profile_context: ProfileRankingContext | None = None,
    **kwargs: Any,
) -> bool:
    """Calculates and persists a JobMatch for (user_id, job).

    Consumes the complete preloaded candidate context (education, certifications,
    classified_experience_level) and reuses it across batch iterations to eliminate N+1 queries.
    Returns True only when a NEW JobMatch row was created. Returns False when
    an existing match was left unchanged or updated, enabling idempotent
    match counting across repeated discovery runs.
    """
    ctx = profile_context
    if ctx is None and profile is not None:
        ctx = getattr(profile, "_cached_ranking_context", None)
        if ctx is None or getattr(ctx, "user_id", None) != user_id:
            ctx = load_profile_context(user_id, db)
            try:
                profile._cached_ranking_context = ctx
            except Exception:
                pass
    elif ctx is None:
        ctx = load_profile_context(user_id, db)

    rank_result = calculate_rank(profile_context=ctx, job=job)

    skills_sc = rank_result.factor_scores.get("skills") or 0
    project_sc = rank_result.factor_scores.get("projects") or 0
    exp_sc = rank_result.factor_scores.get("experience") or 0
    role_sc = rank_result.factor_scores.get("role") or 0
    loc_sc = rank_result.factor_scores.get("location") or 0
    work_mode_sc = rank_result.factor_scores.get("work_mode")
    edu_sc = rank_result.factor_scores.get("education")

    if existing_matches is not None:
        existing_match = existing_matches.get(job.id)
    else:
        existing_match = db.query(JobMatch).filter(
            JobMatch.user_id == user_id, JobMatch.job_id == job.id
        ).first()

    if existing_match:
        if (
            existing_match.overall_score == rank_result.overall_score
            and existing_match.skills_score == skills_sc
            and existing_match.role_score == role_sc
            and existing_match.score_version == "v2"
        ):
            return False
        existing_match.overall_score = rank_result.overall_score
        existing_match.skills_score = skills_sc
        existing_match.project_score = project_sc
        existing_match.experience_score = exp_sc
        existing_match.role_score = role_sc
        existing_match.location_score = loc_sc
        existing_match.work_mode_score = work_mode_sc
        existing_match.education_score = edu_sc
        existing_match.score_version = "v2"
        existing_match.matched_skills = json.dumps(rank_result.matched_skills)
        existing_match.missing_skills = json.dumps(rank_result.missing_skills)
        existing_match.relevant_projects = json.dumps(rank_result.relevant_projects)
        existing_match.relevant_experience = json.dumps(rank_result.relevant_experience)
        existing_match.explanation = rank_result.explanation
        return False
    else:
        match = JobMatch(
            user_id=user_id,
            job_id=job.id,
            overall_score=rank_result.overall_score,
            skills_score=skills_sc,
            project_score=project_sc,
            experience_score=exp_sc,
            role_score=role_sc,
            location_score=loc_sc,
            work_mode_score=work_mode_sc,
            education_score=edu_sc,
            score_version="v2",
            matched_skills=json.dumps(rank_result.matched_skills),
            missing_skills=json.dumps(rank_result.missing_skills),
            relevant_projects=json.dumps(rank_result.relevant_projects),
            relevant_experience=json.dumps(rank_result.relevant_experience),
            explanation=rank_result.explanation,
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

    sources = [
        AdzunaSource(),
        JobicySource(),
        JoobleSource(),
        RemoteOKSource(),
        RemotiveSource(),
    ]
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
    profile_context = load_profile_context(user_id, db)

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
            _upsert_match(user_id, existing_job, db, profile_context=profile_context)
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
        _upsert_match(user_id, new_job, db, profile_context=profile_context)
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
