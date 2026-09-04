"""Phase 5C discovery service.

A provider-agnostic, additive layer on top of the existing multi-source job
discovery architecture. It provides:

* Source selection        - run discovery against a caller-chosen set of sources.
* Unified filtered search - one validated request -> providers -> common
                            pipeline (normalize + filter + sort) -> result.
* Cross-source dedup      - detect the same underlying listing across providers
                            via a deterministic canonical key and merge them
                            into ONE result while preserving provenance
                            (list of sources and their URLs).
* Freshness               - provide a deterministic freshness label derived
                            from ``posted_at`` (never faked).
* Explainable ranking     - deterministic, profile-aligned ranking with explicit
                            sub-scores and human-readable reasons. This is an
                            ADDITIVE discovery heuristic; it does NOT modify
                            ``matching.py`` weights or ``personalized_discovery``.
* Saved searches          - persist criteria, replay them, and report which
                            results are NEW since the previous run
                            (alert-ready design).

Design rules (phase constraints):
* The existing matching weights (50/20/15/10/5) and ``personalized_discovery``
  behavior are NEVER changed.
* No fake radius: if a caller supplies a radius we only pass it through to
  providers that genuinely support it; we never pretend radius filtering.
* No LLM call per job and no new arbitrary weights without documenting them.
  See :data:`MATCH_WEIGHTS` below.
* We never ALTER existing tables; saved-search + seen-state live in the new
  ``saved_searches`` table.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.profile import Profile, UserSkill
from app.models.saved_search import SavedSearch
from app.models.user import User
from app.schemas.discovery import (
    DiscoveryJobHit,
    DiscoveryReport,
    JobFilterRequest,
    MatchInfo,
    SalaryInfo,
    SourceStatusInfo,
)
from app.services.job_sources.adzuna import AdzunaSource
from app.services.job_sources.jobicy import JobicySource
from app.services.job_sources.jooble import JoobleSource
from app.services.job_sources.base import (
    NormalizedJob,
    SearchCriteria,
)
from app.services.job_sources.orchestrator import DiscoveryOrchestrator

# ---------------------------------------------------------------------------
# Provider registry (source selection)
# ---------------------------------------------------------------------------

#: Ordered (name -> builder) map of all providers this service can select.
#: Using the concrete classes directly (like ``personalized_discovery``) keeps
#: per-source status reporting deterministic and avoids gating unconfigured
#: sources out of the status metadata.
SOURCE_BUILDERS: dict[str, callable] = {
    "Adzuna": lambda: AdzunaSource(),
    "Jobicy": lambda: JobicySource(),
    "Jooble": lambda: JoobleSource(),
}

ALL_SOURCE_NAMES: list[str] = list(SOURCE_BUILDERS.keys())


def resolve_sources(selected: Sequence[str] | None) -> tuple[list, list[str]]:
    """Resolve requested source names into provider instances.

    Unknown names are ignored (never crash the request). Returns
    (providers, resolved_names).
    """
    if not selected:
        resolved_names = list(ALL_SOURCE_NAMES)
        providers = [b() for b in SOURCE_BUILDERS.values()]
    else:
        resolved_names = []
        providers = []
        for name in selected:
            builder = SOURCE_BUILDERS.get(name)
            if builder is not None:
                providers.append(builder())
                resolved_names.append(name)
        if not providers:
            # Fall back to all sources when the caller asked for none we know.
            resolved_names = list(ALL_SOURCE_NAMES)
            providers = [b() for b in SOURCE_BUILDERS.values()]
    return providers, resolved_names


# ---------------------------------------------------------------------------
# Canonical identity + cross-source dedup
# ---------------------------------------------------------------------------


def _collapse(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).lower().strip().split())


def _strip_company_noise(company: str | None) -> str:
    if not company:
        return ""
    cleaned = _collapse(company)
    changed = True
    while changed:
        changed = False
        new = re.sub(r"\b(inc|llc|ltd|limited|corp|corporation|co)\.?$", "", cleaned).strip()
        new = re.sub(r"\s+", " ", new)
        if new != cleaned:
            cleaned = new
            changed = True
    return cleaned


def canonical_job_key(job: NormalizedJob) -> str:
    """Deterministic, source-agnostic canonical identity for a job.

    Uses title + company + normalized location. It is intentionally
    conservative: false merges are worse than duplicates, so we only collapse
    on the strongest identity signals (title + employer + location).
    """
    title = _collapse(job.title)
    company = _strip_company_noise(job.company)
    location = _collapse(job.location)
    return f"{title}|{company}|{location}"


def _completeness(job: NormalizedJob) -> int:
    """A small deterministic richness score used to pick a representative
    listing when the same job appears from multiple sources."""
    score = 0
    if job.description:
        score += 3
    if job.application_url:
        score += 1
    if job.source_url:
        score += 1
    if job.salary_min is not None:
        score += 1
    if job.skills:
        score += 1
    if job.posted_at:
        score += 1
    return score


def _best_job(group: list[NormalizedJob]) -> NormalizedJob:
    """Pick the most complete listing from a dedup group as representative."""
    return max(group, key=lambda j: (len(j.source or ""), _completeness(j)))


def dedupe_jobs(jobs: Sequence[NormalizedJob]) -> tuple[list[dict], int]:
    """Group jobs by canonical key, merging cross-source provenance.

    Returns (deduped_group_records, duplicate_count) where each record is a
    dict with the representative job and merged provenance lists. Duplicates
    are the number of jobs that were merged into an existing group
    (i.e. excess entries), NOT the number of groups.
    """
    groups: dict[str, list[NormalizedJob]] = {}
    for job in jobs:
        key = canonical_job_key(job)
        groups.setdefault(key, []).append(job)

    records: list[dict] = []
    duplicate_count = 0
    for key, group in groups.items():
        representative = _best_job(group)
        sources: list[str] = []
        app_urls: list[str] = []
        src_urls: list[str] = []
        seen_sources: set[str] = set()
        for j in group:
            if j.source and j.source not in seen_sources:
                seen_sources.add(j.source)
                sources.append(j.source)
            if j.application_url and j.application_url not in app_urls:
                app_urls.append(j.application_url)
            if j.source_url and j.source_url not in src_urls:
                src_urls.append(j.source_url)
        records.append({
            "key": key,
            "jobs": group,
            "representative": representative,
            "sources": sources,
            "primary_source": representative.source,
            "application_urls": app_urls,
            "source_urls": src_urls,
        })
        duplicate_count += max(0, len(group) - 1)

    return records, duplicate_count


# ---------------------------------------------------------------------------
# Criteria building
# ---------------------------------------------------------------------------


def build_criteria(request: JobFilterRequest) -> SearchCriteria:
    """Translate a validated user-filter request into canonical criteria."""
    return SearchCriteria(
        queries=list(request.queries or []),
        locations=list(request.locations or []),
        country=request.country,
        radius=request.radius,
        remote=request.remote,
        employment_type=request.employment_type,
        experience_level=request.experience_level,
        internship_only=request.internship_only,
        posted_after=request.posted_after,
        salary_min=request.salary_min,
        salary_max=request.salary_max,
        salary_period=request.salary_period,
        salary_currency=request.salary_currency,
        page=request.page,
        page_size=request.page_size,
        sort=request.sort,
        categories=list(request.categories or []),
        skills=list(request.skills or []),
        skills_match=request.skills_match or "any",
    )


# ---------------------------------------------------------------------------
# Explainable, deterministic ranking
# ---------------------------------------------------------------------------

#: Documented discovery-alignment weights (additive heuristic, separate from the
#: canonical matching.py weights which we do NOT change).
MATCH_WEIGHTS = {
    "skills": 50,
    "role": 25,
    "location": 15,
    "freshness": 10,
}
TOTAL_SCORE = sum(MATCH_WEIGHTS.values())

REMOTE_TERMS = ("remote", "work from home", "wfh", "hybrid", "remote-first")


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _freshness_label(posted_at: str | None) -> tuple[str, int]:
    """Return (label, freshness_subscore 0..10) from posted_at (never faked)."""
    dt = _iso_to_dt(posted_at)
    if dt is None:
        return ("unknown", 1)
    now = datetime.now(timezone.utc)
    age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
    if age_days <= 3:
        return ("Today", 10)
    if age_days <= 7:
        return ("This week", 8)
    if age_days <= 14:
        return ("2 weeks", 6)
    if age_days <= 30:
        return ("This month", 4)
    if age_days <= 90:
        return ("3 months", 2)
    return ("Older", 1)


def _profile_payload(user_id: str, db: Session) -> dict:
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    skills: list[str] = []
    preferred_roles: list[str] = []
    preferred_locations: list[str] = []
    if profile:
        skills = [
            s.skill.name
            for s in db.query(UserSkill).filter(UserSkill.profile_id == profile.id).all()
        ]
        preferred_roles = [r.strip().lower() for r in (profile.preferred_roles or "").split(",") if r.strip()]
        preferred_locations = [l.strip().lower() for l in (profile.preferred_locations or "").split(",") if l.strip()]
    return {
        "profile": profile,
        "skills": skills,
        "preferred_roles": preferred_roles,
        "preferred_locations": preferred_locations,
    }


def _tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    return set(re.findall(r"[a-z0-9+#.\-]+", text.lower()))


def rank_record(record: dict, user_id: str, db: Session) -> dict:
    """Attach explainable profile-alignment metadata + score to one record.

    Deterministic and additive. Returns the record with ``match`` added.
    """
    pp = _profile_payload(user_id, db)
    job = record["representative"]
    job_text = " ".join([
        job.title or "",
        job.company or "",
        job.description or "",
        " ".join(job.skills or []),
        job.category or "",
    ]).lower()
    job_tokens = _tokenize(job_text)

    profile_skills = [s.lower() for s in pp["skills"]]
    matched = [s for s in profile_skills if s in job_tokens]
    missing = [s for s in profile_skills if s not in job_tokens]

    skills_score = round((len(matched) / len(profile_skills)) * 100) if profile_skills else 0

    role_score = 0
    if pp["preferred_roles"]:
        if any(role in job_text for role in pp["preferred_roles"]):
            role_score = 100
    elif profile_skills:
        role_score = 50  # neutral when no explicit preferred roles, but skills exist

    location_score = 50  # neutral default (no strong signal)
    loc = (job.location or "").lower()
    if pp["preferred_locations"]:
        if any(pl in loc for pl in pp["preferred_locations"]):
            location_score = 100
        else:
            location_score = 20
    elif any(term in loc for term in REMOTE_TERMS[:3]):
        location_score = 60  # remote work is broadly desirable

    freshness_label, freshness = _freshness_label(job.posted_at)

    overall = round(
        (skills_score * MATCH_WEIGHTS["skills"]
         + role_score * MATCH_WEIGHTS["role"]
         + location_score * MATCH_WEIGHTS["location"]
         + freshness * MATCH_WEIGHTS["freshness"]) / TOTAL_SCORE
    )

    reasons: list[str] = []
    if matched:
        reasons.append(f"Matches your skills: {', '.join(matched[:5])}"
                        + ("..." if len(matched) > 5 else ""))
    if missing:
        reasons.append(f"Missing skills: {', '.join(missing[:5])}")
    if role_score == 100:
        reasons.append("Aligns with a preferred role on your profile.")
    if location_score == 100:
        reasons.append("Located in a preferred location.")
    if freshness_label != "unknown" and freshness_label != "Older":
        reasons.append(f"Recently posted ({freshness_label}).")
    if not reasons:
        reasons.append("General match based on available profile data.")

    record["match"] = {
        "overall_score": overall,
        "skills_score": skills_score,
        "role_score": role_score,
        "location_score": location_score,
        "freshness": freshness,
        "matched_skills": matched,
        "missing_skills": missing,
        "reasons": reasons,
        "is_new": False,
    }
    record["freshness_label"] = freshness_label
    return record


# ---------------------------------------------------------------------------
# Main filtered search
# ---------------------------------------------------------------------------


def run_filtered_search(user_id: str, db: Session, request: JobFilterRequest) -> DiscoveryReport:
    """Run a unified, source-selectable, deduplicated filtered discovery."""
    providers, resolved_names = resolve_sources(request.sources)
    criteria = build_criteria(request)

    orchestrator = DiscoveryOrchestrator(providers)
    outcome = orchestrator.search_filtered(criteria, concurrency=True)

    deduped, duplicate_count = dedupe_jobs(outcome.get("jobs", []))

    provenance = sorted(
        (
            {"source": r.source, "status": r.status.value if hasattr(r.status, "value") else str(r.status),
             "error": r.error_message, "jobs_fetched": len(r.jobs)}
            for r in outcome.get("results", [])
        ),
        key=lambda x: x["source"],
    )

    records: list[dict] = []
    for rec in deduped:
        if request.include_profile_alignment:
            rec = rank_record(rec, user_id, db)
        records.append(rec)

    if request.include_profile_alignment:
        records.sort(key=lambda r: r["match"]["overall_score"], reverse=True)

    results: list[DiscoveryJobHit] = []
    for rec in records:
        rep = rec["representative"]
        match_info = None
        if request.include_profile_alignment and rec.get("match"):
            m = rec["match"]
            match_info = MatchInfo(
                overall_score=m["overall_score"],
                skills_score=m["skills_score"],
                role_score=m["role_score"],
                location_score=m["location_score"],
                freshness=m["freshness"],
                matched_skills=m["matched_skills"],
                missing_skills=m["missing_skills"],
                reasons=m["reasons"],
                is_new=m["is_new"],
            )
        results.append(DiscoveryJobHit(
            canonical_key=rec["key"],
            title=rep.title,
            company=rep.company,
            location=rep.location,
            work_mode=rep.work_mode,
            employment_type=rep.employment_type,
            experience_level=rep.experience_level,
            description=rep.description,
            category=rep.category,
            skills=rep.skills or [],
            salary=SalaryInfo(
                min=rep.salary_min,
                max=rep.salary_max,
                period=rep.salary_period,
                currency=rep.salary_currency,
            ),
            sources=rec["sources"],
            primary_source=rec["primary_source"],
            application_urls=rec["application_urls"],
            source_urls=rec["source_urls"],
            posted_at=rep.posted_at,
            first_seen_at=rep.posted_at,
            freshness=rec.get("freshness_label"),
            match=match_info,
        ))

    report = DiscoveryReport(
        total=len(outcome.get("jobs", [])),
        unique_results=len(results),
        duplicate_count=duplicate_count,
        sources=[SourceStatusInfo(**s) for s in provenance],
        selected_sources=resolved_names,
        errors=list(outcome.get("errors", [])),
        total_fetched=len(outcome.get("jobs", [])),
        results=results,
    )
    return report


def summarize_report(report: DiscoveryReport) -> dict:
    return report.summary()


# ---------------------------------------------------------------------------
# Saved searches
# ---------------------------------------------------------------------------


def _safe_json_loads(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


def create_saved_search(user_id: str, db: Session, name: str, criteria: dict) -> SavedSearch:
    existing = (
        db.query(SavedSearch)
        .filter(SavedSearch.user_id == user_id, SavedSearch.name == name)
        .first()
    )
    if existing:
        existing.criteria = json.dumps(criteria)
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing
    saved = SavedSearch(
        user_id=user_id,
        name=name,
        criteria=json.dumps(criteria),
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return saved


def list_saved_searches(user_id: str, db: Session) -> list[SavedSearch]:
    return (
        db.query(SavedSearch)
        .filter(SavedSearch.user_id == user_id)
        .order_by(SavedSearch.created_at.desc())
        .all()
    )


def get_saved_search(user_id: str, db: Session, search_id: str) -> SavedSearch | None:
    return (
        db.query(SavedSearch)
        .filter(SavedSearch.user_id == user_id, SavedSearch.id == search_id)
        .first()
    )


def update_saved_search(user_id: str, db: Session, search_id: str, name: str | None, criteria: dict | None) -> SavedSearch | None:
    saved = get_saved_search(user_id, db, search_id)
    if saved is None:
        return None
    if name:
        saved.name = name
    if criteria is not None:
        saved.criteria = json.dumps(criteria)
    saved.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(saved)
    return saved


def delete_saved_search(user_id: str, db: Session, search_id: str) -> bool:
    saved = get_saved_search(user_id, db, search_id)
    if saved is None:
        return False
    db.delete(saved)
    db.commit()
    return True


def run_saved_search(user_id: str, db: Session, search_id: str) -> dict:
    """Replay a saved search and report which results are new since last run."""
    saved = get_saved_search(user_id, db, search_id)
    if saved is None:
        return {"saved_search": None, "report": None, "new_results": 0}

    criteria_dict = _safe_json_loads(saved.criteria, {})
    request = JobFilterRequest(**criteria_dict)
    report = run_filtered_search(user_id, db, request)

    previous_keys = set(_safe_json_loads(saved.last_seen_keys, []) or [])
    current_keys = [r.canonical_key for r in report.results]
    current_set = set(current_keys)

    new_results = 0
    for rec in report.results:
        is_new = rec.canonical_key not in previous_keys
        if rec.match is not None:
            rec.match.is_new = is_new
        if is_new:
            new_results += 1

    saved.last_seen_keys = json.dumps(list(current_set))
    saved.last_run_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(saved)

    return {
        "saved_search": saved,
        "report": report,
        "new_results": new_results,
    }
