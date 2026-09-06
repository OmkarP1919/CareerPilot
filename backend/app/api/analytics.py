from collections import Counter
import json
from datetime import date, datetime, time, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.base import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.application import Application
from app.models.application_event import ApplicationEvent
from app.models.application_interview import ApplicationInterview
from app.models.application_document import ApplicationDocument
from app.schemas.analytics import (
    DashboardResponse, RecentApplication, RecentJob,
    ApplicationFunnelResponse, FunnelStage,
    SkillsAnalyticsResponse, SkillFrequency,
    ActivityResponse, ActivityBucket,
    VelocityResponse, VelocityMetric,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

FUNNEL_ORDER = ["Saved", "Preparing", "Applied", "Assessment", "Interview", "Offer"]

DEFAULT_ACTIVITY_WEEKS = 12
MAX_ACTIVITY_WEEKS = 52


def _utc_week_start(value: datetime) -> str:
    """Return the ISO date (YYYY-MM-DD) of the Monday that starts ``value``'s
    calendar week, in UTC. Used as the deterministic activity bucket key."""
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    d = value.replace(tzinfo=None).date() if isinstance(value, datetime) else value
    return (d - timedelta(days=d.weekday())).isoformat()


def _resolve_activity_range(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    """Resolve the bounded activity date range.

    Defaults to the last DEFAULT_ACTIVITY_WEEKS calendar weeks ending with the
    current week (all weeks are Monday-aligned). The range is capped at
    MAX_ACTIVITY_WEEKS and end_date is bounded to today to keep the query set
    bounded and the semantics explicit.
    """
    today = datetime.now(timezone.utc).date()
    today_week_start = today - timedelta(days=today.weekday())

    if end_date is None:
        _end = today
    else:
        _end = end_date
    _end = min(_end, today)

    if start_date is None:
        _start = today_week_start - timedelta(weeks=DEFAULT_ACTIVITY_WEEKS - 1)
    else:
        _start = start_date

    if _start > _end:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date")

    # Bound the span to MAX_ACTIVITY_WEEKS (keeps the query deterministic).
    max_start = _end - timedelta(weeks=MAX_ACTIVITY_WEEKS - 1)
    if _start < max_start:
        _start = max_start

    # Snap both bounds to week starts (Monday) so every bucket is full and the
    # set of covered buckets is deterministic.
    return (
        _start - timedelta(days=_start.weekday()),
        _end - timedelta(days=_end.weekday()),
    )


def _build_activity_buckets(start_week: date, end_week: date, totals: dict) -> list[ActivityBucket]:
    """Emit one zero-seeded bucket per covered week, earliest first."""
    buckets = []
    week = start_week
    while week <= end_week:
        entry = totals.get(week.isoformat(), {})
        buckets.append(ActivityBucket(
            period=week.isoformat(),
            events=entry.get("events", 0),
            applications=entry.get("applications", 0),
            interviews=entry.get("interviews", 0),
            documents=entry.get("documents", 0),
        ))
        week += timedelta(days=7)
    return buckets


@router.get("/activity", response_model=ActivityResponse)
def get_activity(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real per-week activity over the authenticated user's own records.

    No synthetic data. Every count traces to rows owned by ``user``. Activity
    timestamps:

    - applications -> Application.created_at (application creation)
    - events      -> ApplicationEvent.created_at (event chronology)
    - interviews  -> ApplicationInterview.created_at (record creation)
    - documents   -> ApplicationDocument.created_at (record creation)
    """
    start_week, end_week = _resolve_activity_range(start_date, end_date)
    start_bound = datetime.combine(start_week, time.min, tzinfo=timezone.utc)
    end_bound = datetime.combine((end_week + timedelta(days=7)), time.min, tzinfo=timezone.utc)

    # Bounded, user-scoped aggregations (each uses the indexed user_id scan and
    # a SQL date-range bound). Bucketing happens in Python so the week-start
    # math is portable between SQLite (tests) and Postgres (runtime); the row
    # set is bounded by the resolved week range and ownership.
    counts: dict[str, dict] = {}

    def _bucket(key, created_at):
        if created_at is None:
            return
        if created_at.tzinfo is not None:
            created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
        period = _utc_week_start(created_at)
        bucket = counts.get(period)
        if bucket is None:
            bucket = {}
            counts[period] = bucket
        bucket[key] = bucket.get(key, 0) + 1

    for (created_at,) in db.query(Application.created_at).filter(
        Application.user_id == user.id,
        Application.created_at >= start_bound,
        Application.created_at < end_bound,
    ).all():
        _bucket("applications", created_at)

    for (created_at,) in db.query(ApplicationEvent.created_at).filter(
        ApplicationEvent.user_id == user.id,
        ApplicationEvent.created_at >= start_bound,
        ApplicationEvent.created_at < end_bound,
    ).all():
        _bucket("events", created_at)

    for (created_at,) in db.query(ApplicationInterview.created_at).filter(
        ApplicationInterview.user_id == user.id,
        ApplicationInterview.created_at >= start_bound,
        ApplicationInterview.created_at < end_bound,
    ).all():
        _bucket("interviews", created_at)

    for (created_at,) in db.query(ApplicationDocument.created_at).filter(
        ApplicationDocument.user_id == user.id,
        ApplicationDocument.created_at >= start_bound,
        ApplicationDocument.created_at < end_bound,
    ).all():
        _bucket("documents", created_at)

    return ActivityResponse(
        start_date=start_week.isoformat(),
        end_date=end_week.isoformat(),
        buckets=(_build_activity_buckets(start_week, end_week, counts)
                 if start_week <= end_week else []),
    )


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_jobs = db.query(Job).filter(Job.user_id == user.id).count()

    high_match_jobs = db.query(JobMatch).filter(
        JobMatch.user_id == user.id, JobMatch.overall_score >= 70
    ).count()

    applications = db.query(Application).filter(Application.user_id == user.id).all()

    status_counts = Counter(a.status for a in applications)
    total_applications = len(applications)

    scores = [
        m.overall_score
        for m in db.query(JobMatch).filter(JobMatch.user_id == user.id).all()
    ]
    avg_score = round(sum(scores) / len(scores)) if scores else None

    recent_apps_query = (
        db.query(Application)
        .filter(Application.user_id == user.id)
        .order_by(Application.updated_at.desc())
        .limit(5)
        .all()
    )
    recent_applications = []
    for a in recent_apps_query:
        job = db.query(Job).filter(Job.id == a.job_id).first()
        recent_applications.append(RecentApplication(
            id=a.id,
            job_title=job.title if job else None,
            job_company=job.company if job else None,
            status=a.status,
            updated_at=a.updated_at,
        ))

    recent_jobs_query = (
        db.query(Job)
        .filter(Job.user_id == user.id)
        .order_by(Job.created_at.desc())
        .limit(5)
        .all()
    )
    recent_jobs = [
        RecentJob(id=j.id, title=j.title, company=j.company, created_at=j.created_at)
        for j in recent_jobs_query
    ]

    return DashboardResponse(
        total_jobs=total_jobs,
        high_match_jobs=high_match_jobs,
        total_applications=total_applications,
        saved_count=status_counts.get("Saved", 0),
        applied_count=status_counts.get("Applied", 0),
        interview_count=status_counts.get("Interview", 0),
        offer_count=status_counts.get("Offer", 0),
        rejected_count=status_counts.get("Rejected", 0),
        average_match_score=avg_score,
        recent_applications=recent_applications,
        recent_jobs=recent_jobs,
    )


@router.get("/application-funnel", response_model=ApplicationFunnelResponse)
def get_application_funnel(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    applications = db.query(Application).filter(Application.user_id == user.id).all()
    status_counts = Counter(a.status for a in applications)

    funnel = [
        FunnelStage(stage=stage, count=status_counts.get(stage, 0))
        for stage in FUNNEL_ORDER
    ]

    return ApplicationFunnelResponse(
        funnel=funnel,
        total=len(applications),
    )


@router.get("/skills", response_model=SkillsAnalyticsResponse)
def get_skills_analytics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    matches = db.query(JobMatch).filter(JobMatch.user_id == user.id).all()

    matched_counter: Counter = Counter()
    missing_counter: Counter = Counter()

    for m in matches:
        try:
            matched = json.loads(m.matched_skills or "[]")
            missing = json.loads(m.missing_skills or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        matched_counter.update(matched)
        missing_counter.update(missing)

    frequent_matched = [
        SkillFrequency(skill=s, count=c, type="matched")
        for s, c in matched_counter.most_common(10)
    ]
    frequent_missing = [
        SkillFrequency(skill=s, count=c, type="missing")
        for s, c in missing_counter.most_common(10)
    ]

    return SkillsAnalyticsResponse(
        frequent_missing=frequent_missing,
        frequent_matched=frequent_matched,
        total_analyses=len(matches),
    )


@router.get("/velocity", response_model=VelocityResponse)
def get_velocity(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real application-lifecycle timing from the user's own status changes.

    Methodology (exact, no fabrication):

    For each application the user owns, reconstruct the lifecycle from its
    ``status_changed`` events (``metadata.from_status``/``to_status``), which are
    produced automatically by the application update endpoint. Only actual
    recorded transitions count - never the application's mere current status.

    Applied -> Interview days, per application::
        t_int     = created_at of the FIRST status_changed event whose
                    ``to_status == "Interview"`` (application reached interview).
        t_applied = created_at of the LATEST status_changed event before t_int
                    whose ``to_status == "Applied"``; if none exists, the
                    application's own ``created_at`` (the application was
                    created in the Applied state / no earlier recorded
                    transition). This is a real record timestamp, not a guess.
        elapsed   = (t_int - t_applied) in days.

    Applied -> Offer days, per application: identical, using the FIRST
    ``to_status == "Offer"`` event as t_offer.

    An application contributes a sample only when the target transition exists;
    incomplete lifecycles (never reaching Interview/Offer) and Withdrawn /
    Rejected paths that never hit the target are excluded, not treated as zero.
    Repeated transitions are resolved deterministically (first target transition
    matched against the latest prior "Applied" entry). The reported value is the
    MEDIAN of the per-application elapsed-day samples; median of an even count
    is the arithmetic mean of the two middle samples. ``sample_size`` is the
    exact number of qualifying applications - 0 is a truthful count.
    """
    applications = db.query(Application).filter(Application.user_id == user.id).all()
    events = (
        db.query(ApplicationEvent)
        .filter(ApplicationEvent.user_id == user.id, ApplicationEvent.event_type == "status_changed")
        .all()
    )

    # Index status_changed events per application, ordered by (created_at, id).
    by_app: dict[str, list] = {}
    for event in events:
        meta = event.meta_data if isinstance(event.meta_data, dict) else {}
        from_status = meta.get("from_status")
        to_status = meta.get("to_status")
        if not from_status or not to_status:
            continue
        by_app.setdefault(event.application_id, []).append({
            "from_status": from_status,
            "to_status": to_status,
            "created_at": event.created_at,
            "id": event.id,
        })
    for chain in by_app.values():
        chain.sort(key=lambda e: (e["created_at"] or datetime(1970, 1, 1), e["id"]))

    created_at_by_app = {a.id: a.created_at for a in applications}

    def _transition_timestamps(target_status: str) -> list[float]:
        """Per-application elapsed days from entering Applied to `target_status`."""
        samples: list[float] = []
        for app_id, chain in by_app.items():
            # First time this application reached the target status.
            target_event = next(
                (e for e in chain if e["to_status"] == target_status), None
            )
            if target_event is None:
                continue
            t_target = target_event["created_at"]
            if t_target is None:
                continue

            # Latest recorded entry INTO Applied strictly before the target.
            applied_event = None
            for e in chain:
                if e["to_status"] == "Applied" and e["created_at"] is not None and e["created_at"] < t_target:
                    applied_event = e

            if applied_event is not None:
                t_applied = applied_event["created_at"]
            else:
                t_applied = created_at_by_app.get(app_id)

            if t_applied is None:
                continue

            elapsed_seconds = (t_target - t_applied).total_seconds()
            if elapsed_seconds < 0:
                # Defensive: the "Applied" reference is later than the target,
                # which cannot happen with the "latest before target" rule; skip.
                continue
            samples.append(round(elapsed_seconds / 86400.0, 6))
        return samples

    def _median(samples: list[float]) -> float | None:
        if not samples:
            return None
        ordered = sorted(samples)
        n = len(ordered)
        mid = n // 2
        if n % 2 == 1:
            return ordered[mid]
        return round((ordered[mid - 1] + ordered[mid]) / 2.0, 6)

    interview_samples = _transition_timestamps("Interview")
    offer_samples = _transition_timestamps("Offer")

    return VelocityResponse(
        applied_to_interview=VelocityMetric(
            median_days=_median(interview_samples),
            sample_size=len(interview_samples),
        ),
        applied_to_offer=VelocityMetric(
            median_days=_median(offer_samples),
            sample_size=len(offer_samples),
        ),
    )
