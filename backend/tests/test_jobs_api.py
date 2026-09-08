"""Phase 5E.4 / Production-Readiness regression tests for the /jobs API.

Covers the three remediation items from the Production Readiness Gate:

BLOCKER #1 - GET /jobs must be scoped to the authenticated user. A client must
             never see another user's saved jobs (list or filtered list).
BLOCKER #2 - GET /jobs/{job_id} requires ownership; a non-owner gets a 404 (not
             403) so neither the job nor the existence of another user's job is
             disclosed.
FINDING #3 - DELETE /jobs/{job_id} must be deterministic across SQLite and
             PostgreSQL. Applications (user application history), job matches
             and AI-derived artifacts reference the job; deleting a referenced
             job would raise a ForeignKeyViolation on PostgreSQL (a 500) while
             silently succeeding with orphaned rows on SQLite's default
             FK-disabled mode. The fix refuses the deletion with a 409 until the
             dependent rows are removed by their owner.

The security tests also prove that client-supplied user IDs/headers cannot
forge ownership (the authenticated identity always comes from get_current_user).
"""

import os
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.models.job_match import JobMatch
from app.models.resume_job_analysis import ResumeJobAnalysis
from app.models.tailored_resume import TailoredResume
from app.models.cover_letter import CoverLetter
from app.api.jobs import router as jobs_router

USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
USER_B = {"id": "user_b", "firebase_uid": "fb_b"}


def _seed_job(db, job_id, user_id, title, company="Acme"):
    job = Job(
        id=job_id,
        user_id=user_id,
        title=title,
        company=company,
        location="Remote",
        employment_type="Full-time",
        experience_level="Mid Level",
        description=f"{title} description",
        required_skills="Python, FastAPI",
    )
    db.add(job)


class _JobsAPIHarness:
    """Shared /jobs FastAPI harness with an in-memory SQLite DB.

    ``enforce_fk=True`` turns SQLite's foreign-key enforcement ON to reproduce
    PostgreSQL's constrained-delete behavior (same trick as
    test_resume_delete_upload.py).
    """

    def __init__(self, enforce_fk=False):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        if enforce_fk:

            @event.listens_for(self.engine, "connect")
            def _set_sqlite_foreign_keys(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        db = self.Session()
        db.add_all([
            User(id=USER_A["id"], firebase_uid=USER_A["firebase_uid"], email="a@test.com", name="A"),
            User(id=USER_B["id"], firebase_uid=USER_B["firebase_uid"], email="b@test.com", name="B"),
        ])
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(jobs_router)
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
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def close(self):
        self.engine.dispose()

    def seed_job(self, job_id, user_id=USER_A["id"], title="Backend Developer"):
        db = self.Session()
        _seed_job(db, job_id, user_id, title)
        db.commit()
        db.close()

    def seed_application(self, app_id, job_id, user_id=USER_A["id"]):
        db = self.Session()
        db.add(Application(id=app_id, user_id=user_id, job_id=job_id, status="Applied"))
        db.commit()
        db.close()

    def seed_job_match(self, match_id, job_id, user_id=USER_A["id"]):
        db = self.Session()
        db.add(JobMatch(
            id=match_id, user_id=user_id, job_id=job_id,
            overall_score=80, role_score=80, skills_score=80,
        ))
        db.commit()
        db.close()


class JobListIDORTests(unittest.TestCase):
    def setUp(self):
        self.h = _JobsAPIHarness()

    def tearDown(self):
        self.h.close()

    def test_list_only_returns_own_jobs(self):
        self.h.seed_job("job_a", user_id=USER_A["id"], title="Backend Developer")
        self.h.seed_job("job_b", user_id=USER_B["id"], title="Frontend Developer")

        resp = self.h.client.get("/jobs")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([j["user_id"] for j in resp.json()], [USER_A["id"]])

        self.h.current_user_id = USER_B["id"]
        resp = self.h.client.get("/jobs")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([j["id"] for j in resp.json()], ["job_b"])

    def test_list_returns_empty_when_user_owns_no_jobs(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        self.h.current_user_id = USER_B["id"]
        resp = self.h.client.get("/jobs")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_search_is_scoped_to_owner(self):
        self.h.seed_job("job_a", user_id=USER_A["id"], title="Backend Developer")
        # B owns a job that matches A's search term - it must NOT leak into A's results
        self.h.seed_job("job_b", user_id=USER_B["id"], title="Backend Developer")

        resp = self.h.client.get("/jobs", params={"search": "Backend"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([j["id"] for j in resp.json()], ["job_a"])

    def test_employment_type_filter_still_works_while_scoped(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        resp = self.h.client.get("/jobs", params={"employment_type": "Full-time"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([j["id"] for j in resp.json()], ["job_a"])

        resp = self.h.client.get("/jobs", params={"employment_type": "Contract"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])


class JobGetIDORTests(unittest.TestCase):
    def setUp(self):
        self.h = _JobsAPIHarness()

    def tearDown(self):
        self.h.close()

    def test_owner_can_retrieve_own_job(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        resp = self.h.client.get("/jobs/job_a")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["user_id"], USER_A["id"])

    def test_non_owner_cannot_retrieve_job(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        self.h.current_user_id = USER_B["id"]
        resp = self.h.client.get("/jobs/job_a")
        self.assertEqual(resp.status_code, 404)

    def test_nonexistent_job_is_404(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        resp = self.h.client.get("/jobs/does-not-exist")
        self.assertEqual(resp.status_code, 404)

    def test_cross_user_and_nonexistent_return_identical_body(self):
        """No information about another user's job existence may be leaked."""
        self.h.seed_job("job_a", user_id=USER_A["id"])
        self.h.current_user_id = USER_B["id"]
        cross_user = self.h.client.get("/jobs/job_a")
        self.assertEqual(cross_user.status_code, 404)

        nonexistent = self.h.client.get("/jobs/no-such-job")
        self.assertEqual(nonexistent.status_code, 404)
        self.assertEqual(cross_user.json(), nonexistent.json())

    def test_forged_user_id_headers_cannot_bypass_ownership(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        self.h.current_user_id = USER_B["id"]
        resp = self.h.client.get(
            "/jobs/job_a",
            headers={
                "X-User-Id": USER_A["id"],
                "X-UID": USER_A["firebase_uid"],
                "uid": USER_A["id"],
            },
        )
        self.assertEqual(resp.status_code, 404)


class JobDeleteIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.h = _JobsAPIHarness()

    def tearDown(self):
        self.h.close()

    def test_delete_own_job_without_dependents_succeeds(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        resp = self.h.client.delete("/jobs/job_a")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.h.client.get("/jobs").json(), [])

    def test_delete_other_users_job_is_404(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        self.h.current_user_id = USER_B["id"]
        resp = self.h.client.delete("/jobs/job_a")
        self.assertEqual(resp.status_code, 404)

    def test_delete_nonexistent_job_is_404(self):
        resp = self.h.client.delete("/jobs/no-such-job")
        self.assertEqual(resp.status_code, 404)

    def test_delete_job_referenced_by_application_is_409(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        self.h.seed_application("app_a", "job_a", user_id=USER_A["id"])

        resp = self.h.client.delete("/jobs/job_a")
        self.assertEqual(resp.status_code, 409)
        self.assertIn("applications", resp.json()["detail"])

        # Application history is preserved and the job still exists.
        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(Application).filter(Application.id == "app_a").first())
            self.assertIsNotNone(db.query(Job).filter(Job.id == "job_a").first())
        finally:
            db.close()

    def test_delete_job_referenced_by_application_requires_owner_cleanup_first(self):
        """After the owner deletes their application, the job delete succeeds."""
        self.h.seed_job("job_a", user_id=USER_A["id"])
        db = self.h.Session()
        db.add(Application(id="app_a", user_id=USER_A["id"], job_id="job_a", status="Applied"))
        db.commit()
        db.delete(db.query(Application).filter(Application.id == "app_a").first())
        db.commit()
        db.close()

        resp = self.h.client.delete("/jobs/job_a")
        self.assertEqual(resp.status_code, 204)

    def test_delete_job_referenced_by_match_is_409(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        self.h.seed_job_match("m_a", "job_a", user_id=USER_A["id"])
        resp = self.h.client.delete("/jobs/job_a")
        self.assertEqual(resp.status_code, 409)
        self.assertIn("job_matches", resp.json()["detail"])


class JobDeletePostgresCorrectnessTests(unittest.TestCase):
    """Delete behavior under SQLite foreign_keys=ON (PostgreSQL-equivalent).

    Without the guard, deleting a referenced job on PostgreSQL raises
    ForeignKeyViolation (a 500), while SQLite's default mode silently orphans
    the dependent row. These tests prove the guarded behavior is identical and
    safe under FK enforcement.
    """

    def setUp(self):
        self.h = _JobsAPIHarness(enforce_fk=True)

    def tearDown(self):
        self.h.close()

    def test_referenced_job_delete_returns_409_not_500(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        self.h.seed_application("app_a", "job_a", user_id=USER_A["id"])

        resp = self.h.client.delete("/jobs/job_a")
        self.assertEqual(resp.status_code, 409, f"expected 409, got {resp.status_code}")
        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(Job).filter(Job.id == "job_a").first())
            self.assertIsNotNone(db.query(Application).filter(Application.id == "app_a").first())
        finally:
            db.close()

    def test_match_referenced_job_delete_returns_409_not_500(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        self.h.seed_job_match("m_a", "job_a", user_id=USER_A["id"])

        resp = self.h.client.delete("/jobs/job_a")
        self.assertEqual(resp.status_code, 409, f"expected 409, got {resp.status_code}")

    def test_unreferenced_job_delete_204_under_fk_enforcement(self):
        self.h.seed_job("job_a", user_id=USER_A["id"])
        resp = self.h.client.delete("/jobs/job_a")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.h.client.get("/jobs").json(), [])


if __name__ == "__main__":
    unittest.main()