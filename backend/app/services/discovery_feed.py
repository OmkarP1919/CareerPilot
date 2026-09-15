"""Phase 7.0D.1 — Profile-aware discovery feed service.

A thin orchestration boundary that produces a personalized job feed by REUSING
the existing discovery and matching components end-to-end:

    profile context
      -> PersonalizedQueryBuilder + resolve_country_and_location   (retrieval)
      -> registry.get_providers()             (unconfigured providers degrade)
      -> DiscoveryOrchestrator                (per-source isolation, retrieval)
      -> pipeline.run_pipeline                (canonical normalize / sort)
      -> dedupe_jobs / canonical_job_key      (cross-source deduplication)
      -> existing job identity checks         (external_id+source | title|company)
      -> _upsert_match / calculate_match      (persist + PROFILE MATCH)
      -> get_recommended_jobs                 (existing ranked feed)

The headline score exposed to the feed is the canonical PROFILE MATCH score
(weights 50/20/15/10/5, frozen in ``matching.py``). This service NEVER:

* modifies ``matching.py`` weights or semantics,
* maintains a second matching engine,
* sends resume data to providers (providers receive ``SearchCriteria`` only),
* implicitly runs provider discovery on feed loads.

Feed loads are the FAST path: ``build_feed`` returns persisted, ranked
recommendations WITHOUT any provider fan-out. Fresh personalized runs stay
explicit and rate-limited (``POST /jobs/discover/personalized`` already exists,
or a direct ``refresh_feed`` call.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.profile import (
    Certification,
    Education,
    Experience,
    Profile,
    Project,
    UserSkill,
)
from app.services.discovery_service import canonical_job_key, dedupe_jobs
from app.services.job_discovery import (
    _upsert_match,
    get_recommended_jobs,
    normalize_title_company,
)
from app.services.job_sources.base import SearchCriteria
from app.services.job_sources.orchestrator import DiscoveryOrchestrator
from app.services.job_sources.pipeline import run_pipeline
from app.services.job_sources.registry import get_providers
from app.services.personalized_discovery import (
    INCOMPLETE_PROFILE_MESSAGE,
    NO_PROFILE_MESSAGE,
    PersonalizedQueryBuilder,
    classify_experience_level,
    resolve_country_and_location,
)

logger = logging.getLogger(__name__)

#: Ceiling for the ranked feed (matches get_recommended_jobs' limit).
FEED_LIMIT = 50


def _load_context(user_id: str, db: Session) -> dict:
    """Preload the user's profile and candidate fields exactly ONCE.

    Loading everything up-front means match calculation never performs
    per-job database lookups for the same profile data.
    """
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    skills: list[str] = []
    projects = []
    experiences = []
    education = []
    certifications = []
    if profile is not None:
        user_skills = (
            db.query(UserSkill).filter(UserSkill.profile_id == profile.id).all()
        )
        skills = [us.skill.name for us in user_skills]
        projects = db.query(Project).filter(Project.profile_id == profile.id).all()
        experiences = (
            db.query(Experience).filter(Experience.profile_id == profile.id).all()
        )
        education = db.query(Education).filter(Education.profile_id == profile.id).all()
        certifications = (
            db.query(Certification).filter(Certification.profile_id == profile.id).all()
        )
    return {
        "profile": profile,
        "skills": skills,
        "user_skills_set": {s.lower().strip() for s in skills if s.strip()},
        "projects": projects,
        "experiences": experiences,
        "education": education,
        "certifications": certifications,
    }


def build_context(user_id: str, db: Session) -> dict:
    """Deterministic, factual profile context for explanatory metadata only.

    This describes WHAT the feed used — it never fabricates or scores.
    """
    ctx = _load_context(user_id, db)
    profile = ctx["profile"]
    grad_year = ctx["education"][0].graduation_year if ctx["education"] else None
    return {
        "has_profile": profile is not None,
        "has_skills": bool(ctx["skills"]),
        "has_projects": bool(ctx["projects"]),
        "has_experience": bool(ctx["experiences"]),
        "has_education": bool(ctx["education"]),
        "has_certifications": bool(ctx["certifications"]),
        "preferred_roles": (
            [r.strip() for r in (profile.preferred_roles or "").split(",") if r.strip()]
            if profile else []
        ),
        "preferred_locations": (
            [l.strip() for l in (profile.preferred_locations or "").split(",") if l.strip()]
            if profile else []
        ),
        "experience_level": (
            classify_experience_level(grad_year, ctx["experiences"]) if profile else None
        ),
    }


def _empty_discovery(errors: list[str]) -> dict:
    return {
        "queries_used": [],
        "sources": {},
        "new_jobs": 0,
        "existing_jobs": 0,
        "matches_created": 0,
        "errors": errors,
    }


def _parse_posted(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _persist_records(user_id: str, db: Session, records: list[dict], ctx: dict) -> tuple:
    """Persist every deduplicated record's representative as a Job row when new,
    and upsert its PROFILE MATCH.

    Identity/state safety mirrors ``personalized_discovery`` exactly:
    * an existing row is matched by (external_id, source) then by normalized
      title|company, so a single feed run never creates duplicate rows;
    * existing rows are only enriched with missing fields (never overwritten);
    * user application state is never modified here.

    Returns (new_jobs, existing_jobs, matches_created).
    """
    existing_matches = {
        m.job_id: m
        for m in db.query(JobMatch).filter(JobMatch.user_id == user_id).all()
    }
    existing_external: dict[tuple[str, str], Job] = {}
    for j in db.query(Job).filter(
        Job.external_id.isnot(None), Job.source.isnot(None)
    ).all():
        existing_external[(j.external_id, j.source)] = j

    existing_title_company: dict[str, Job] = {}
    for j in db.query(Job).all():
        existing_title_company[normalize_title_company(j.title, j.company)] = j

    new_jobs = 0
    existing_jobs = 0
    matches_created = 0
    now = datetime.now(timezone.utc)

    for record in records:
        fetched = record["representative"]
        try:
            if not fetched.title.strip() or not fetched.company.strip():
                continue

            existing_job = None
            if fetched.external_id and fetched.source:
                existing_job = existing_external.get((fetched.external_id, fetched.source))
            if existing_job is None:
                existing_job = existing_title_company.get(
                    normalize_title_company(fetched.title, fetched.company)
                )

            if existing_job is not None:
                if fetched.description and not existing_job.description:
                    existing_job.description = fetched.description
                if fetched.application_url and not existing_job.application_url:
                    existing_job.application_url = fetched.application_url
                if fetched.posted_at and not existing_job.posted_at:
                    existing_job.posted_at = _parse_posted(fetched.posted_at)
                existing_jobs += 1
                created = _upsert_match(
                    user_id,
                    existing_job,
                    db,
                    existing_matches=existing_matches,
                    profile=ctx["profile"],
                    user_skills_set=ctx["user_skills_set"],
                    user_projects=ctx["projects"],
                    user_experiences=ctx["experiences"],
                )
                if created:
                    matches_created += 1
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
                new_job.posted_at = _parse_posted(fetched.posted_at)

            db.add(new_job)
            db.flush()  # generate UUID before _upsert_match references new_job.id
            if new_job.external_id and new_job.source:
                existing_external[(new_job.external_id, new_job.source)] = new_job
            existing_title_company[
                normalize_title_company(new_job.title, new_job.company)
            ] = new_job

            new_jobs += 1
            created = _upsert_match(
                user_id,
                new_job,
                db,
                existing_matches=existing_matches,
                profile=ctx["profile"],
                user_skills_set=ctx["user_skills_set"],
                user_projects=ctx["projects"],
                user_experiences=ctx["experiences"],
            )
            if created:
                matches_created += 1
        except Exception:
            logger.exception("Failed to persist a feed job for user %s", user_id)

    return new_jobs, existing_jobs, matches_created


def refresh_feed(user_id: str, db: Session) -> dict:
    """Explicit personalized discovery run: retrieve -> normalize -> dedupe -> persist.

    This is the only path that talks to providers and it MUST stay explicit —
    it is synchronous and network-bound. Returns a summary dict; call
    ``build_feed`` afterwards for the ranked feed.
    """
    ctx = _load_context(user_id, db)
    profile = ctx["profile"]
    if profile is None:
        return _empty_discovery([NO_PROFILE_MESSAGE])

    queries = PersonalizedQueryBuilder.build_queries(
        profile, ctx["skills"], ctx["projects"], ctx["experiences"], ctx["education"]
    )
    if not queries:
        return _empty_discovery([INCOMPLETE_PROFILE_MESSAGE])

    detected_country, location_terms = resolve_country_and_location(
        profile.location, profile.preferred_locations
    )

    # Providers receive SearchCriteria ONLY (never resume data). Location/country
    # hints go to the providers themselves — exactly like personalized_discovery —
    # so broad retrieval is preserved and location stays a scored dimension of
    # the frozen PROFILE MATCH rather than a hard filter.
    providers = get_providers()
    criteria = SearchCriteria(
        queries=queries, locations=location_terms, country=detected_country
    )
    outcome = DiscoveryOrchestrator(providers).search(criteria, concurrency=True)

    sources: dict[str, int] = {}
    for result in outcome.get("results", []):
        sources[result.source] = len(result.jobs)

    # Canonical normalization (no hard filters: a profile hint must never lose
    # retrievable jobs before deterministic profile matching scores them).
    pipeline_out = run_pipeline(outcome.get("jobs", []), SearchCriteria(queries=queries))

    # Cross-source dedup: the same listing from multiple providers becomes ONE
    # feed entry (completeness-based representative selection is preserved).
    records, _duplicate_count = dedupe_jobs(pipeline_out["jobs"])
    for record in records:
        logger.debug(
            "Feed canonical identity %s (group of %d)",
            canonical_job_key(record["representative"]),
            len(record["jobs"]),
        )

    new_jobs, existing_jobs, matches_created = _persist_records(user_id, db, records, ctx)
    db.commit()

    return {
        "queries_used": queries,
        "sources": sources,
        "new_jobs": new_jobs,
        "existing_jobs": existing_jobs,
        "matches_created": matches_created,
        "errors": list(outcome.get("errors", [])),
    }


def _attach_explanations(user_id: str, db: Session, rows: list[dict]) -> list[dict]:
    """Attach persisted, factual profile-match explanations in ONE bulk query.

    Never generates AI explanations and never claims eligibility the data does
    not support; a row without a stored explanation simply carries None.
    """
    if not rows:
        return rows
    job_ids = [r["job"].id for r in rows]
    matches = {
        m.job_id: m
        for m in db.query(JobMatch)
        .filter(JobMatch.user_id == user_id, JobMatch.job_id.in_(job_ids))
        .all()
    }
    for row in rows:
        match = matches.get(row["job"].id)
        row["explanation"] = match.explanation if match and match.explanation else None
    return rows


def build_feed(
    user_id: str,
    db: Session,
    min_score: int = 0,
    source: str | None = None,
    remote_only: bool = False,
    limit: int = FEED_LIMIT,
) -> dict:
    """Return the personalized feed from PERSISTED recommendations only.

    This is the fast page-load path: no provider call, no fan-out. A fresh
    personalized run must happen explicitly first (POST /jobs/discover/personalized
    or refresh_feed). Rows carry the existing ranked shape plus an additive
    ``explanation`` key, ranked by the frozen PROFILE MATCH score.
    """
    context = build_context(user_id, db)
    errors = [NO_PROFILE_MESSAGE] if not context["has_profile"] else []

    rows = get_recommended_jobs(
        user_id, db, min_score=min_score, source=source, remote_only=remote_only
    )
    rows = rows[:limit]
    _attach_explanations(user_id, db, rows)

    return {
        "jobs": rows,
        "total": len(rows),
        "context": context,
        "errors": errors,
        "refreshed": False,
        "queries_used": [],
        "new_jobs": 0,
        "existing_jobs": 0,
        "matches_created": 0,
    }