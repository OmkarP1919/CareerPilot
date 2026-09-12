"""Test end-to-end job details flow and identifier contract.

Verifies:
1. Job creator can view own job via GET /jobs/{job_id}.
2. Matched/recommended user can view job details via GET /jobs/{job_id}.
3. User with an application for a job can view job details via GET /jobs/{job_id}.
4. Discovered catalog job (with external_id/source) can be viewed by any authenticated user.
5. Unrelated private job without relationship remains 404 (IDOR protection intact).
6. Nonexistent job returns 404.
"""

import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.models.job_match import JobMatch
from app.api.jobs import router as jobs_router

USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
USER_B = {"id": "user_b", "firebase_uid": "fb_b"}


class JobDetailsFlowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        db = self.Session()
        db.add_all([
            User(id=USER_A["id"], firebase_uid=USER_A["firebase_uid"], email="a@test.com", name="User A"),
            User(id=USER_B["id"], firebase_uid=USER_B["firebase_uid"], email="b@test.com", name="User B"),
        ])
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(jobs_router)
        self.current_user_id = USER_B["id"]

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

    def tearDown(self):
        self.engine.dispose()

    def _create_job(self, job_id, user_id, title="Software Engineer", source=None, external_id=None):
        db = self.Session()
        job = Job(
            id=job_id,
            user_id=user_id,
            title=title,
            company="Stripe",
            location="Remote",
            employment_type="Full-time",
            experience_level="Senior",
            description="Build modern developer tools.",
            required_skills="Python, React, TypeScript",
            source=source,
            external_id=external_id,
        )
        db.add(job)
        db.commit()
        db.close()

    def test_owner_can_view_job_details(self):
        self._create_job("job_b1", user_id=USER_B["id"], title="Backend Lead")
        resp = self.client.get("/jobs/job_b1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "job_b1")
        self.assertEqual(resp.json()["title"], "Backend Lead")

    def test_recommended_job_can_be_viewed_by_matched_user(self):
        # Job created originally by User A
        self._create_job("rec_job_1", user_id=USER_A["id"], title="Staff Platform Engineer")
        # System generates JobMatch for User B
        db = self.Session()
        db.add(JobMatch(
            id="match_b_1",
            user_id=USER_B["id"],
            job_id="rec_job_1",
            overall_score=92,
            role_score=90,
            skills_score=95,
        ))
        db.commit()
        db.close()

        # User B views the recommended job details
        resp = self.client.get("/jobs/rec_job_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "rec_job_1")
        self.assertEqual(resp.json()["title"], "Staff Platform Engineer")

    def test_applied_job_can_be_viewed_by_applicant(self):
        self._create_job("applied_job_1", user_id=USER_A["id"], title="Frontend Architect")
        db = self.Session()
        db.add(Application(
            id="app_b_1",
            user_id=USER_B["id"],
            job_id="applied_job_1",
            status="Applied",
        ))
        db.commit()
        db.close()

        resp = self.client.get("/jobs/applied_job_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "applied_job_1")
        self.assertEqual(resp.json()["title"], "Frontend Architect")

    def test_external_catalog_job_can_be_viewed_by_user(self):
        self._create_job(
            "ext_job_1",
            user_id=USER_A["id"],
            title="Senior DevOps Engineer",
            source="Adzuna",
            external_id="adzuna_98765",
        )
        resp = self.client.get("/jobs/ext_job_1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "ext_job_1")
        self.assertEqual(resp.json()["title"], "Senior DevOps Engineer")

    def test_unrelated_private_job_returns_404(self):
        # Private job created by User A with no match, application, or catalog external_id
        self._create_job("private_job_a", user_id=USER_A["id"], title="Secret Internal Role")
        resp = self.client.get("/jobs/private_job_a")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json(), {"detail": "Job not found"})

    def test_nonexistent_job_returns_404(self):
        resp = self.client.get("/jobs/nonexistent-id-999")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json(), {"detail": "Job not found"})


if __name__ == "__main__":
    unittest.main()
