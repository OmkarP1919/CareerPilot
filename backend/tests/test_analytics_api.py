"""HTTP/API-level tests for the Phase 5D Step 3 trustworthy analytics endpoints.

Covers:

- GET /analytics/activity   (real per-week activity, user scoped, zero-safe)
- GET /analytics/velocity   (real lifecycle timing medians, user scoped)
- GET /analytics/dashboard  (regression: no fabricated values, no cross-user)
- GET /analytics/application-funnel (regression)
- GET /analytics/skills     (regression)
- GET /applications/{id}/timeline (hardening: ownership, orphan rows, ordering)

Style follows test_application_pipeline_api.py / test_discovery_saved_search_api.py.
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.applications import router as applications_router
from app.api.analytics import router as analytics_router
from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.job_match import JobMatch
from app.models.resume import Resume
from app.models.application import Application
from app.models.application_event import ApplicationEvent
from app.models.application_interview import ApplicationInterview
from app.models.application_document import ApplicationDocument

USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
USER_B = {"id": "user_b", "firebase_uid": "fb_b"}

DUMMY_PDF = b"%PDF-1.4 test"


def _wk(date):
    return date - timedelta(days=date.weekday())


class _AnalyticsHarness:
    """Shared FastAPI harness: in-memory SQLite, auth override, seeded users,
    jobs and (for IDOR) a second user so every analytics endpoint can be
    proven user-scoped."""

    def __init__(self):
        self.tmpdir = tempfile.mkdtemp()
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        db = self.Session()
        db.add_all([
            User(id=USER_A["id"], firebase_uid=USER_A["firebase_uid"], email="a@test.com", name="A"),
            User(id=USER_B["id"], firebase_uid=USER_B["firebase_uid"], email="b@test.com", name="B"),
        ])
        db.add_all([
            Job(id="job_1", user_id=USER_A["id"], title="Backend Developer",
                company="Acme", description="Python FastAPI", required_skills="Python, FastAPI"),
            Job(id="job_2", user_id=USER_B["id"], title="Frontend Developer",
                company="Beta", description="React", required_skills="React"),
        ])
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(applications_router)
        self.app.include_router(analytics_router)
        self.current_user_id = USER_A["id"]

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            session = self.Session()
            try:
                return session.query(User).filter(User.id == self.current_user_id).first()
            finally:
                session.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(self.app)

        # Deterministic clock control: every seed timestamp is expressed as an
        # offset from a fixed reference so tests can compute exact expectations.
        self.base = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)

    def close(self):
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # -- direct DB seeding helpers -----------------------------------------

    def seed_application(self, app_id, user_id=USER_A["id"], job_id="job_1",
                         status="Applied", created_at=None, updated_at=None):
        db = self.Session()
        app = Application(id=app_id, user_id=user_id, job_id=job_id, status=status)
        if created_at is not None:
            app.created_at = created_at
        if updated_at is not None:
            app.updated_at = updated_at
        db.add(app)
        db.commit()
        db.close()
        return app_id

    def seed_event(self, event_id, app_id, user_id=USER_A["id"], event_type="status_changed",
                   created_at=None, metadata=None, notes=None):
        db = self.Session()
        event = ApplicationEvent(
            id=event_id, application_id=app_id, user_id=user_id,
            event_type=event_type, notes=notes, created_by=user_id,
            created_at=created_at, meta_data=metadata,
        )
        db.add(event)
        db.commit()
        db.close()
        return event_id

    def seed_interview(self, interview_id, app_id, user_id=USER_A["id"],
                       scheduled_at=None, created_at=None, kind="video", status="scheduled"):
        db = self.Session()
        interview = ApplicationInterview(
            id=interview_id, application_id=app_id, user_id=user_id,
            scheduled_at=scheduled_at or created_at, kind=kind, status=status,
            created_at=created_at, updated_at=created_at,
        )
        db.add(interview)
        db.commit()
        db.close()
        return interview_id

    def seed_document(self, doc_id, app_id, user_id=USER_A["id"], document_type="resume",
                      created_at=None):
        db = self.Session()
        doc = ApplicationDocument(
            id=doc_id, application_id=app_id, user_id=user_id,
            document_type=document_type, created_at=created_at, updated_at=created_at,
        )
        db.add(doc)
        db.commit()
        db.close()
        return doc_id

    def seed_job_match(self, match_id, user_id=USER_A["id"], job_id="job_1",
                       overall_score=80, matched_skills=None, missing_skills=None):
        db = self.Session()
        match = JobMatch(
            id=match_id, user_id=user_id, job_id=job_id, overall_score=overall_score,
            matched_skills=matched_skills, missing_skills=missing_skills,
        )
        db.add(match)
        db.commit()
        db.close()
        return match_id


class TestActivityAuthAndEmpty(unittest.TestCase):
    def setUp(self):
        self.h = _AnalyticsHarness()

    def tearDown(self):
        self.h.close()

    def test_auth_required(self):
        # Remove the auth override so the real dependency 401s.
        self.h.app.dependency_overrides.pop(get_current_user, None)
        resp = self.h.client.get("/analytics/activity")
        self.assertIn(resp.status_code, (401, 403))

    def test_empty_user_returns_empty_buckets(self):
        resp = self.h.client.get("/analytics/activity")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("buckets", body)
        self.assertIn("start_date", body)
        self.assertIn("end_date", body)
        # Every bucket is all-zero (never fabricated activity).
        for bucket in body["buckets"]:
            self.assertEqual(bucket["events"], 0)
            self.assertEqual(bucket["applications"], 0)
            self.assertEqual(bucket["interviews"], 0)
            self.assertEqual(bucket["documents"], 0)

    def test_deterministic_ordering_and_default_range(self):
        resp = self.h.client.get("/analytics/activity")
        body = resp.json()
        periods = [b["period"] for b in body["buckets"]]
        self.assertEqual(periods, sorted(periods))
        self.assertEqual(len(periods), 12)  # default 12 weeks, Monday-aligned


class TestActivityBuckets(unittest.TestCase):
    def setUp(self):
        self.h = _AnalyticsHarness()

    def tearDown(self):
        self.h.close()

    def test_exact_bucket_counts_for_all_sources(self):
        start = self.h.base.replace(tzinfo=None)  # 2026-01-01 09:00
        week0_start = (_wk(datetime(2026, 1, 1))).date()  # Monday 2025-12-29
        week1_start = week0_start + timedelta(days=7)  # Monday 2026-01-05
        # Request a two-week range around these seeds.
        resp = self.h.client.get(
            "/analytics/activity",
            params={"start_date": week0_start.isoformat(), "end_date": week1_start.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["start_date"], week0_start.isoformat())
        self.assertEqual(body["end_date"], week1_start.isoformat())
        # All-zero first.
        for bucket in body["buckets"]:
            self.assertEqual(bucket["events"], 0)
            self.assertEqual(bucket["applications"], 0)
            self.assertEqual(bucket["interviews"], 0)
            self.assertEqual(bucket["documents"], 0)

        # Seed scattered across the two weeks (timestamps naive UTC to survive
        # SQLite round-trip).
        wk0 = week0_start
        wk1 = week1_start
        self.h.seed_application("app_c1", created_at=wk0 + timedelta(hours=1))
        self.h.seed_application("app_c2", created_at=wk0 + timedelta(days=1))
        self.h.seed_application("app_c3", created_at=wk1 + timedelta(hours=1))
        self.h.seed_event("ev_1", "app_c1", created_at=wk0 + timedelta(hours=2))
        self.h.seed_event("ev_2", "app_c1", created_at=wk0 + timedelta(hours=3))
        self.h.seed_event("ev_3", "app_c2", created_at=wk1 + timedelta(hours=2))
        self.h.seed_interview("iv_1", "app_c1", created_at=wk0 + timedelta(hours=4))
        self.h.seed_interview("iv_2", "app_c1", created_at=wk1 + timedelta(hours=4))
        self.h.seed_document("doc_1", "app_c1", created_at=wk0 + timedelta(hours=5))
        self.h.seed_document("doc_2", "app_c2", created_at=wk1 + timedelta(hours=5))

        resp = self.h.client.get(
            "/analytics/activity",
            params={"start_date": week0_start.isoformat(), "end_date": week1_start.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual([b["period"] for b in body["buckets"]],
                         [week0_start.isoformat(), week1_start.isoformat()])
        b0, b1 = body["buckets"]
        self.assertEqual(b0["period"], week0_start.isoformat())
        self.assertEqual(b0["events"], 2)
        self.assertEqual(b0["applications"], 2)
        self.assertEqual(b0["interviews"], 1)
        self.assertEqual(b0["documents"], 1)
        self.assertEqual(b1["period"], week1_start.isoformat())
        self.assertEqual(b1["events"], 1)
        self.assertEqual(b1["applications"], 1)
        self.assertEqual(b1["interviews"], 1)
        self.assertEqual(b1["documents"], 1)

    def test_out_of_range_rows_excluded(self):
        wk0 = _wk(datetime(2026, 1, 1))
        # One row inside, one far outside the requested week.
        self.h.seed_application("app_in", created_at=wk0 + timedelta(hours=1))
        self.h.seed_application("app_out", created_at=wk0 - timedelta(days=400))
        resp = self.h.client.get(
            "/analytics/activity",
            params={"start_date": wk0.isoformat(), "end_date": wk0.isoformat()},
        )
        body = resp.json()
        self.assertEqual(len(body["buckets"]), 1)
        self.assertEqual(body["buckets"][0]["applications"], 1)

    def test_start_after_end_rejected(self):
        resp = self.h.client.get(
            "/analytics/activity",
            params={"start_date": "2026-02-01", "end_date": "2026-01-01"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_user_b_activity_not_leaked_to_user_a(self):
        wk0 = _wk(datetime(2026, 1, 1))
        self.h.seed_application("app_a", created_at=wk0 + timedelta(hours=1))
        self.h.seed_event("ev_a", "app_a", created_at=wk0 + timedelta(hours=2))
        # User B's activity.
        self.h.seed_application("app_b", user_id=USER_B["id"], job_id="job_2",
                                created_at=wk0 + timedelta(days=2))
        self.h.seed_event("ev_b", "app_b", user_id=USER_B["id"],
                          created_at=wk0 + timedelta(days=2, hours=1))

        resp = self.h.client.get(
            "/analytics/activity",
            params={"start_date": wk0.isoformat(), "end_date": wk0.isoformat()},
        )
        buckets = resp.json()["buckets"]
        self.assertEqual(len(buckets), 1)
        b = buckets[0]
        # B's app/event are not counted in A's activity.
        self.assertEqual(b["applications"], 1)
        self.assertEqual(b["events"], 1)


class TestVelocityAuthAndEmpty(unittest.TestCase):
    def setUp(self):
        self.h = _AnalyticsHarness()

    def tearDown(self):
        self.h.close()

    def test_auth_required(self):
        self.h.app.dependency_overrides.pop(get_current_user, None)
        resp = self.h.client.get("/analytics/velocity")
        self.assertIn(resp.status_code, (401, 403))

    def test_empty_user_returns_null_metrics(self):
        resp = self.h.client.get("/analytics/velocity")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIsNone(body["applied_to_interview"]["median_days"])
        self.assertEqual(body["applied_to_interview"]["sample_size"], 0)
        self.assertIsNone(body["applied_to_offer"]["median_days"])
        self.assertEqual(body["applied_to_offer"]["sample_size"], 0)


class TestVelocityCalculation(unittest.TestCase):
    def setUp(self):
        self.h = _AnalyticsHarness()

    def tearDown(self):
        self.h.close()

    def test_applied_to_interview_fallback_to_app_created_at(self):
        # App created in the Applied state with no prior transition recorded.
        created = self.h.base.replace(tzinfo=None)
        self.h.seed_application("app_1", status="Applied", created_at=created)
        self.h.seed_event(
            "ev_i", "app_1", event_type="status_changed",
            created_at=created + timedelta(days=5),
            metadata={"from_status": "Applied", "to_status": "Interview"},
        )
        resp = self.h.client.get("/analytics/velocity")
        metric = resp.json()["applied_to_interview"]
        self.assertEqual(metric["sample_size"], 1)
        self.assertEqual(metric["median_days"], 5.0)
        self.assertEqual(resp.json()["applied_to_offer"]["sample_size"], 0)

    def test_applied_to_interview_uses_prior_into_applied_event(self):
        created = self.h.base.replace(tzinfo=None)
        self.h.seed_application("app_2", status="Interview", created_at=created)
        # Entered Applied 2 days after creation via a recorded transition.
        self.h.seed_event(
            "ev_apply", "app_2", event_type="status_changed",
            created_at=created + timedelta(days=2),
            metadata={"from_status": "Saved", "to_status": "Applied"},
        )
        self.h.seed_event(
            "ev_int", "app_2", event_type="status_changed",
            created_at=created + timedelta(days=7),
            metadata={"from_status": "Applied", "to_status": "Interview"},
        )
        metric = self.h.client.get("/analytics/velocity").json()["applied_to_interview"]
        # 7 - 2 = 5 days; the "into Applied" event is the applied reference.
        self.assertEqual(metric["median_days"], 5.0)
        self.assertEqual(metric["sample_size"], 1)

    def test_applied_to_offer_exact_elapsed(self):
        created = self.h.base.replace(tzinfo=None)
        self.h.seed_application("app_3", status="Offer", created_at=created)
        self.h.seed_event(
            "ev_offer", "app_3", event_type="status_changed",
            created_at=created + timedelta(days=10, hours=12),
            metadata={"from_status": "Applied", "to_status": "Offer"},
        )
        metric = self.h.client.get("/analytics/velocity").json()["applied_to_offer"]
        self.assertEqual(metric["sample_size"], 1)
        self.assertEqual(metric["median_days"], 10.5)
        self.assertEqual(
            self.h.client.get("/analytics/velocity").json()["applied_to_interview"]["sample_size"],
            0,
        )

    def test_median_with_multiple_samples(self):
        created = self.h.base.replace(tzinfo=None)
        # Three Applied->Interview samples: 3, 7, 11 days -> median 7.
        for i, days in enumerate([3, 7, 11]):
            app_id = f"app_m{i}"
            self.h.seed_application(app_id, status="Applied", created_at=created)
            self.h.seed_event(
                f"ev_m{i}", app_id, event_type="status_changed",
                created_at=created + timedelta(days=days),
                metadata={"from_status": "Applied", "to_status": "Interview"},
            )
        metric = self.h.client.get("/analytics/velocity").json()["applied_to_interview"]
        self.assertEqual(metric["sample_size"], 3)
        self.assertEqual(metric["median_days"], 7.0)

    def test_median_even_count_is_mean_of_middle_two(self):
        created = self.h.base.replace(tzinfo=None)
        # Samples: 2 and 8 -> median 5.
        for i, days in enumerate([2, 8]):
            app_id = f"app_e{i}"
            self.h.seed_application(app_id, status="Applied", created_at=created)
            self.h.seed_event(
                f"ev_e{i}", app_id, event_type="status_changed",
                created_at=created + timedelta(days=days),
                metadata={"from_status": "Applied", "to_status": "Interview"},
            )
        metric = self.h.client.get("/analytics/velocity").json()["applied_to_interview"]
        self.assertEqual(metric["median_days"], 5.0)

    def test_incomplete_lifecycle_excluded(self):
        created = self.h.base.replace(tzinfo=None)
        # App stuck in Applied, never reaches Interview/Offer.
        self.h.seed_application("app_stuck", status="Applied", created_at=created)
        self.h.seed_event(
            "ev_stuck", "app_stuck", event_type="status_changed",
            created_at=created + timedelta(days=3),
            metadata={"from_status": "Saved", "to_status": "Applied"},
        )
        body = self.h.client.get("/analytics/velocity").json()
        self.assertEqual(body["applied_to_interview"]["sample_size"], 0)
        self.assertIsNone(body["applied_to_interview"]["median_days"])
        self.assertEqual(body["applied_to_offer"]["sample_size"], 0)
        self.assertIsNone(body["applied_to_offer"]["median_days"])

    def test_withdrawn_path_that_reached_interview_counts(self):
        created = self.h.base.replace(tzinfo=None)
        self.h.seed_application("app_wd", status="Withdrawn", created_at=created)
        self.h.seed_event(
            "ev_wd1", "app_wd", event_type="status_changed",
            created_at=created + timedelta(days=1),
            metadata={"from_status": "Applied", "to_status": "Interview"},
        )
        self.h.seed_event(
            "ev_wd2", "app_wd", event_type="status_changed",
            created_at=created + timedelta(days=2),
            metadata={"from_status": "Interview", "to_status": "Withdrawn"},
        )
        metric = self.h.client.get("/analytics/velocity").json()["applied_to_interview"]
        # Reached interview before being withdrawn, so a valid sample exists.
        self.assertEqual(metric["sample_size"], 1)
        self.assertEqual(metric["median_days"], 1.0)

    def test_rejected_before_offer_excluded_from_offer_metric(self):
        created = self.h.base.replace(tzinfo=None)
        self.h.seed_application("app_rej", status="Rejected", created_at=created)
        self.h.seed_event(
            "ev_r1", "app_rej", event_type="status_changed",
            created_at=created + timedelta(days=2),
            metadata={"from_status": "Applied", "to_status": "Rejected"},
        )
        body = self.h.client.get("/analytics/velocity").json()
        self.assertEqual(body["applied_to_offer"]["sample_size"], 0)
        self.assertIsNone(body["applied_to_offer"]["median_days"])

    def test_repeated_transitions_deterministic(self):
        created = self.h.base.replace(tzinfo=None)
        self.h.seed_application("app_rep", status="Interview", created_at=created)
        # Applied -> Applied (no-op), Applied -> Interview (first), then
        # Interview -> Applied, Applied -> Interview (second). The metric uses
        # the FIRST interview transition and the latest "into Applied" before it.
        self.h.seed_event(
            "rep_1", "app_rep", event_type="status_changed",
            created_at=created + timedelta(days=1),
            metadata={"from_status": "Applied", "to_status": "Applied"},
        )
        self.h.seed_event(
            "rep_2", "app_rep", event_type="status_changed",
            created_at=created + timedelta(days=2),
            metadata={"from_status": "Applied", "to_status": "Interview"},
        )
        self.h.seed_event(
            "rep_3", "app_rep", event_type="status_changed",
            created_at=created + timedelta(days=3),
            metadata={"from_status": "Interview", "to_status": "Applied"},
        )
        self.h.seed_event(
            "rep_4", "app_rep", event_type="status_changed",
            created_at=created + timedelta(days=4),
            metadata={"from_status": "Applied", "to_status": "Interview"},
        )
        metric = self.h.client.get("/analytics/velocity").json()["applied_to_interview"]
        self.assertEqual(metric["sample_size"], 1)
        # The FIRST interview happens at day 2. The latest recorded "into
        # Applied" strictly before it is rep_1 at day 1 (Applied->Applied is
        # still a recorded entry into Applied), so the elapsed reference is day
        # 1, giving 2 - 1 = 1 day. Deterministic across repeated transitions.
        self.assertEqual(metric["median_days"], 1.0)

    def test_user_b_cannot_influence_user_a_metrics(self):
        created = self.h.base.replace(tzinfo=None)
        # A has one 5-day sample.
        self.h.seed_application("app_a", status="Applied", created_at=created)
        self.h.seed_event(
            "ev_a1", "app_a", event_type="status_changed",
            created_at=created + timedelta(days=5),
            metadata={"from_status": "Applied", "to_status": "Interview"},
        )
        # B has a 1000-day sample.
        self.h.seed_application("app_b", user_id=USER_B["id"], job_id="job_2",
                                status="Applied", created_at=created)
        self.h.seed_event(
            "ev_b1", "app_b", user_id=USER_B["id"], event_type="status_changed",
            created_at=created + timedelta(days=1000),
            metadata={"from_status": "Applied", "to_status": "Interview"},
        )
        metric = self.h.client.get("/analytics/velocity").json()["applied_to_interview"]
        self.assertEqual(metric["sample_size"], 1)
        self.assertEqual(metric["median_days"], 5.0)


class TestExistingAnalyticsRegression(unittest.TestCase):
    def setUp(self):
        self.h = _AnalyticsHarness()

    def tearDown(self):
        self.h.close()

    def test_dashboard_empty_user_returns_zeros_and_none(self):
        resp = self.h.client.get("/analytics/dashboard")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # No fabricated values: zeros are truthful counts, avg is null (no data).
        # The harness seeds one Job owned by A, so total_jobs == 1 here; every
        # application/match-derived field must still be a real zero or null.
        self.assertEqual(body["total_jobs"], 1)
        self.assertEqual(body["high_match_jobs"], 0)
        self.assertEqual(body["total_applications"], 0)
        self.assertEqual(body["saved_count"], 0)
        self.assertEqual(body["applied_count"], 0)
        self.assertEqual(body["interview_count"], 0)
        self.assertEqual(body["offer_count"], 0)
        self.assertEqual(body["rejected_count"], 0)
        self.assertIsNone(body["average_match_score"])
        self.assertEqual(body["recent_applications"], [])
        self.assertEqual(body["recent_jobs"][0]["id"], "job_1")

    def test_dashboard_reflects_real_rows_and_is_user_scoped(self):
        self.h.seed_application("app_1", user_id=USER_A["id"], status="Applied")
        self.h.seed_application("app_2", user_id=USER_A["id"], status="Interview")
        self.h.seed_application("app_b", user_id=USER_B["id"], job_id="job_2", status="Offer")
        self.h.seed_job_match("m1", user_id=USER_A["id"], overall_score=85)

        body = self.h.client.get("/analytics/dashboard").json()
        # A sees only A's rows.
        self.assertEqual(body["total_applications"], 2)
        self.assertEqual(body["applied_count"], 1)
        self.assertEqual(body["interview_count"], 1)
        self.assertEqual(body["offer_count"], 0)
        self.assertEqual(body["high_match_jobs"], 1)
        self.assertEqual(body["average_match_score"], 85)

        # Switch to B: B sees only B's rows.
        self.h.current_user_id = USER_B["id"]
        b = self.h.client.get("/analytics/dashboard").json()
        self.assertEqual(b["total_applications"], 1)
        self.assertEqual(b["offer_count"], 1)
        self.assertEqual(b["high_match_jobs"], 0)
        self.assertIsNone(b["average_match_score"])

    def test_dashboard_average_is_real_not_fallback(self):
        self.h.seed_job_match("m1", user_id=USER_A["id"], overall_score=70)
        self.h.seed_job_match("m2", user_id=USER_A["id"], overall_score=100)
        body = self.h.client.get("/analytics/dashboard").json()
        self.assertEqual(body["average_match_score"], 85)  # (70+100)/2 = 85

    def test_application_funnel_user_scoped_and_contract_valid(self):
        self.h.seed_application("app_1", user_id=USER_A["id"], status="Applied")
        self.h.seed_application("app_2", user_id=USER_A["id"], status="Interview")
        self.h.seed_application("app_b", user_id=USER_B["id"], job_id="job_2", status="Offer")

        resp = self.h.client.get("/analytics/application-funnel")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total"], 2)
        by_stage = {s["stage"]: s["count"] for s in body["funnel"]}
        self.assertEqual(by_stage["Applied"], 1)
        self.assertEqual(by_stage["Interview"], 1)
        self.assertEqual(by_stage["Offer"], 0)  # B's offer not counted for A

    def test_application_funnel_empty_user_zeros(self):
        body = self.h.client.get("/analytics/application-funnel").json()
        self.assertEqual(body["total"], 0)
        for stage in body["funnel"]:
            self.assertEqual(stage["count"], 0)

    def test_skills_user_scoped_and_no_fabrication(self):
        self.h.seed_job_match("m1", user_id=USER_A["id"], overall_score=80,
                              matched_skills='["Python","FastAPI"]',
                              missing_skills='["Docker"]')
        self.h.seed_job_match("m2", user_id=USER_A["id"], overall_score=70,
                              matched_skills='["Python"]',
                              missing_skills='["AWS","Docker"]')
        # B's analysis must not appear in A's skills.
        self.h.seed_job_match("m3", user_id=USER_B["id"], job_id="job_2", overall_score=90,
                              matched_skills='["SecretSkill"]')

        resp = self.h.client.get("/analytics/skills")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total_analyses"], 2)
        matched = {s["skill"]: s["count"] for s in body["frequent_matched"]}
        self.assertEqual(matched.get("Python"), 2)
        self.assertEqual(matched.get("FastAPI"), 1)
        self.assertNotIn("SecretSkill", matched)
        missing = {s["skill"]: s["count"] for s in body["frequent_missing"]}
        self.assertEqual(missing.get("Docker"), 2)
        self.assertEqual(missing.get("AWS"), 1)

    def test_skills_empty_user_empty_lists(self):
        body = self.h.client.get("/analytics/skills").json()
        self.assertEqual(body["total_analyses"], 0)
        self.assertEqual(body["frequent_matched"], [])
        self.assertEqual(body["frequent_missing"], [])


class TestTimelineHardening(unittest.TestCase):
    def setUp(self):
        self.h = _AnalyticsHarness()
        self.h.seed_application("app_a", user_id=USER_A["id"])

    def tearDown(self):
        self.h.close()

    def test_orphan_foreign_ownership_row_not_leaked_to_application_owner(self):
        # A row whose application_id belongs to A but user_id belongs to B.
        # The timeline must NOT surface it to A (application_id must not be the
        # only discriminator) and must NOT surface it to B (application_id is
        # not B's).
        self.h.seed_event("orphan_ev", "app_a", user_id=USER_B["id"],
                          event_type="note_added", created_at=self.h.base.replace(tzinfo=None))
        self.h.seed_interview("orphan_iv", "app_a", user_id=USER_B["id"],
                              created_at=self.h.base.replace(tzinfo=None))
        self.h.seed_document("orphan_doc", "app_a", user_id=USER_B["id"],
                             created_at=self.h.base.replace(tzinfo=None))

        entries = self.h.client.get("/applications/app_a/timeline").json()["entries"]
        self.assertEqual(entries, [])

        # B must not see them under app_a either.
        self.h.current_user_id = USER_B["id"]
        self.assertEqual(self.h.client.get("/applications/app_a/timeline").status_code, 404)

    def test_timeline_empty_contract(self):
        body = self.h.client.get("/applications/app_a/timeline").json()
        self.assertEqual(body["application_id"], "app_a")
        self.assertEqual(body["user_id"], USER_A["id"])
        self.assertEqual(body["entries"], [])

    def test_timeline_combines_all_kinds_ordered(self):
        base = self.h.base.replace(tzinfo=None)
        self.h.seed_event("ev_1", "app_a", event_type="milestone", created_at=base)
        self.h.seed_interview("iv_1", "app_a", created_at=base + timedelta(days=1))
        self.h.seed_document("doc_1", "app_a", created_at=base + timedelta(days=2))
        entries = self.h.client.get("/applications/app_a/timeline").json()["entries"]
        self.assertEqual([e["id"] for e in entries], ["ev_1", "iv_1", "doc_1"])
        self.assertEqual({e["kind"] for e in entries}, {"event", "interview", "document"})

    def test_timeline_cross_user_application_404(self):
        self.h.seed_application("app_b", user_id=USER_B["id"], job_id="job_2")
        self.h.current_user_id = USER_B["id"]
        resp = self.h.client.get("/applications/app_a/timeline")
        self.assertEqual(resp.status_code, 404)


class TestApplicationDeleteAnalyticsCleanup(unittest.TestCase):
    """B-1 blocker regression: deleting an application must not leave its child
    rows (and therefore its analytics activity) behind as orphans."""

    def setUp(self):
        self.h = _AnalyticsHarness()

    def tearDown(self):
        self.h.close()

    def _totals(self, body):
        return {name: sum(bucket[name] for bucket in body["buckets"])
                for name in ("events", "applications", "interviews", "documents")}

    def test_deleted_application_activity_stops_counting(self):
        week0_start = (_wk(datetime(2026, 1, 1))).date()  # Monday 2025-12-29
        week1_start = week0_start + timedelta(days=7)  # Monday 2026-01-05
        params = {"start_date": week0_start.isoformat(), "end_date": week1_start.isoformat()}

        # A's application + one child of each kind, all inside week 0.
        base = self.h.base.replace(tzinfo=None)  # 2026-01-01 09:00
        self.h.seed_application("app_a", user_id=USER_A["id"], created_at=base)
        self.h.seed_event("ev_1", "app_a", event_type="note_added", created_at=base)
        self.h.seed_interview("iv_1", "app_a", created_at=base + timedelta(hours=1))
        self.h.seed_document("doc_1", "app_a", created_at=base + timedelta(hours=2))

        resp = self.h.client.get("/analytics/activity", params=params)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self._totals(resp.json()),
            {"events": 1, "applications": 1, "interviews": 1, "documents": 1},
        )

        self.assertEqual(self.h.client.delete("/applications/app_a").status_code, 204)
        db = self.h.Session()
        try:
            self.assertEqual(db.query(Application).filter(Application.id == "app_a").count(), 0)
            self.assertEqual(
                db.query(ApplicationEvent).filter(ApplicationEvent.application_id == "app_a").count(),
                0,
            )
            self.assertEqual(
                db.query(ApplicationInterview).filter(ApplicationInterview.application_id == "app_a").count(),
                0,
            )
            self.assertEqual(
                db.query(ApplicationDocument).filter(ApplicationDocument.application_id == "app_a").count(),
                0,
            )
        finally:
            db.close()

        resp = self.h.client.get("/analytics/activity", params=params)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self._totals(resp.json()),
            {"events": 0, "applications": 0, "interviews": 0, "documents": 0},
        )


if __name__ == "__main__":
    unittest.main()
