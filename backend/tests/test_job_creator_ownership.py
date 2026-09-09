"""Phase 7 H-1 regression tests: job-creator route ownership.

Every route that accepts a ``job_id`` to create/attach user-owned records must
resolve the job against the *requesting* user. A cross-user ``job_id`` and a
nonexistent ``job_id`` must both return an identical 404 so the existence of
another user's job is never disclosed (same contract as ``test_jobs_api.py``).

Routes covered:
  - POST /applications                          (applications.create_application)
  - POST /jobs/{job_id}/match                   (match.match_job)
  - POST /jobs/{job_id}/resume-analysis         (resume_analysis.analyze_resume)
  - POST /jobs/{job_id}/resume-tailor           (resume_tailoring.tailor_resume)
  - POST /jobs/{job_id}/cover-letter            (cover_letter.generate_cover_letter)

AI providers are always mocked; the ownership gate must fire *before* any AI
work, so the mocked provider calls == 0 on every rejected attempt and no
cross-user record is ever created.
"""

import copy
import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.job_match import JobMatch
from app.models.resume_job_analysis import ResumeJobAnalysis
from app.models.tailored_resume import TailoredResume
from app.models.cover_letter import CoverLetter
from app.api.applications import router as applications_router
from app.api.match import router as match_router
from app.api.resume_analysis import router as resume_analysis_router
from app.api.resume_tailoring import router as resume_tailoring_router
from app.api.cover_letter import router as cover_letter_router
from app.api.job_access import get_own_job

USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
USER_B = {"id": "user_b", "firebase_uid": "fb_b"}

SOURCE_RESUME = {
    "basic_info": {"name": "Alex Doe", "email": "alex@test.com", "phone": "5551234567"},
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "React"],
    "projects": [
        {
            "name": "E-commerce Platform",
            "technologies": ["Python", "FastAPI", "PostgreSQL"],
            "description": "Built REST APIs and a payment integration backend.",
        }
    ],
    "experience": [
        {
            "job_title": "Backend Developer",
            "company": "Acme Corp",
            "dates": "2020 - Present",
            "description": "Built REST APIs with Python, FastAPI and PostgreSQL.",
        }
    ],
    "education": [
        {
            "degree": "B.Tech",
            "institution": "Example University",
            "field_of_study": "Computer Science",
            "graduation_year": "2020",
        }
    ],
    "certifications": ["AWS Certified Solutions Architect"],
}

# Valid AI responses used ONLY for the owner-success path. They match the
# schemas validated by app.services.cover_letter / app.services.resume_tailoring.
COVER_LETTER_RESPONSE = {
    "greeting": "Dear Hiring Manager,",
    "opening": "I am writing to apply for the Backend Developer position at Acme.",
    "body_paragraphs": [
        "Your experience with Python, FastAPI and PostgreSQL aligns well with the role. "
        "I built REST APIs and a payment integration backend for an e-commerce platform.",
    ],
    "closing": "Thank you for considering my application.",
    "signature": "Sincerely,\nAlex Doe",
    "supported_points": ["Python, FastAPI, PostgreSQL experience", "REST API backend work"],
    "unsupported_requirements": ["Kubernetes"],
    "warnings": [],
}

TAILOR_RESPONSE = {
    "summary": {
        "original": "Backend developer with API experience.",
        "tailored": "Backend Developer experienced in building REST APIs with Python, "
                    "FastAPI and PostgreSQL.",
    },
    "skills": {
        "kept": ["Python", "FastAPI", "PostgreSQL", "Docker", "React"],
        "emphasized": ["Python", "FastAPI"],
        "removed": [],
    },
    "experience": [
        {
            "original_title": "Backend Developer",
            "company": "Acme Corp",
            "original_bullets": ["Built REST APIs with Python, FastAPI and PostgreSQL."],
            "tailored_bullets": [
                "Designed and built scalable REST APIs using Python, FastAPI and PostgreSQL."
            ],
            "changes": ["Clarified wording; no facts altered."],
        }
    ],
    "projects": [
        {
            "name": "E-commerce Platform",
            "original_description": "Built REST APIs and a payment integration backend.",
            "tailored_description": "Built REST APIs and a payment integration backend using Python, FastAPI and PostgreSQL.",
            "changes": [],
        }
    ],
    "education": ["B.Tech in Computer Science, Example University, 2020"],
    "certifications": ["AWS Certified Solutions Architect"],
    "keywords_added": ["REST", "PostgreSQL"],
    "keywords_not_added": ["Kubernetes"],
    "overall_changes": ["Emphasized API backend skills."],
    "warnings": [],
}


class _FakeProvider:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def generate_structured(self, *, system_prompt, user_prompt, schema, timeout_seconds):
        self.calls += 1
        return copy.deepcopy(self.response)


# (label, url_factory) for the five cutting-owner routes. Each accepts the
# job_id as the single parameter.
ROUTES = {
    "applications": lambda job_id: ("/applications", {"job_id": job_id, "status": "Applied"}),
    "match": lambda job_id: (f"/jobs/{job_id}/match", None),
    "resume-analysis": lambda job_id: (f"/jobs/{job_id}/resume-analysis", {"resume_id": "res_a"}),
    "resume-tailor": lambda job_id: (f"/jobs/{job_id}/resume-tailor", {"resume_id": "res_a"}),
    "cover-letter": lambda job_id: (f"/jobs/{job_id}/cover-letter", {"resume_id": "res_a"}),
}
OWNER_SUCCESS_CODE = {"applications": 201}
FORGED_ID_HEADERS = {"X-User-Id": USER_A["id"], "X-UID": USER_A["firebase_uid"], "uid": USER_A["id"]}


class _JobCreatorOwnershipHarness:
    def __init__(self):
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
        job_a = Job(id="job_a", user_id=USER_A["id"], title="Backend Developer", company="Acme",
                    location="Remote", employment_type="Full-time", experience_level="Mid Level",
                    description="Backend Developer required. Python, FastAPI, PostgreSQL, Docker.",
                    required_skills="Python, FastAPI, PostgreSQL, Docker, Kubernetes")
        job_b = Job(id="job_b", user_id=USER_B["id"], title="Frontend Developer", company="Beta",
                    location="Remote", employment_type="Full-time", experience_level="Mid Level",
                    description="Frontend Developer required. React, TypeScript.",
                    required_skills="React, TypeScript")
        resume_a = Resume(id="res_a", user_id=USER_A["id"], filename="a.pdf",
                          original_filename="a.pdf", file_path="/tmp/a.pdf", file_size="1",
                          parsing_status="completed", parsed_data=copy.deepcopy(SOURCE_RESUME),
                          extracted_text="Backend Developer Acme Corp 2020 Present.")
        db.add_all([job_a, job_b, resume_a])
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(applications_router)
        self.app.include_router(match_router)
        self.app.include_router(resume_analysis_router)
        self.app.include_router(resume_tailoring_router)
        self.app.include_router(cover_letter_router)
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

        self.cover_letter_provider = _FakeProvider(COVER_LETTER_RESPONSE)
        self.tailor_provider = _FakeProvider(TAILOR_RESPONSE)
        self._patchers = [
            mock.patch("app.api.cover_letter.build_provider", return_value=self.cover_letter_provider),
            mock.patch("app.api.resume_tailoring.build_provider", return_value=self.tailor_provider),
        ]
        for patcher in self._patchers:
            patcher.start()

        self.client = TestClient(self.app)

    def close(self):
        for patcher in self._patchers:
            patcher.stop()
        self.engine.dispose()

    def call(self, route, job_id, as_user=USER_A["id"], headers=None):
        url, body = ROUTES[route](job_id)
        self.current_user_id = as_user
        return self.client.post(url, json=body, headers=headers or {})


class JobCreatorOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.h = _JobCreatorOwnershipHarness()

    def tearDown(self):
        self.h.close()

    def _count(self, model, **filters):
        db = self.h.Session()
        try:
            return db.query(model).filter_by(**filters).count()
        finally:
            db.close()

    # --- A: the owner can always use their own job ---------------------------
    def test_owner_can_use_own_job_on_all_five_routes(self):
        for route in ROUTES:
            resp = self.h.call(route, "job_a", as_user=USER_A["id"])
            expected = OWNER_SUCCESS_CODE.get(route, 200)
            self.assertEqual(resp.status_code, expected, f"[{route}] {resp.text}")

        self.assertEqual(self._count(Application, user_id=USER_A["id"], job_id="job_a"), 1)
        self.assertEqual(self._count(JobMatch, user_id=USER_A["id"], job_id="job_a"), 1)
        self.assertEqual(self._count(ResumeJobAnalysis, user_id=USER_A["id"], job_id="job_a"), 1)
        self.assertEqual(self._count(TailoredResume, user_id=USER_A["id"], job_id="job_a"), 1)
        self.assertEqual(self._count(CoverLetter, user_id=USER_A["id"], job_id="job_a"), 1)

    # --- B: a cross-user job_id is rejected on every route -------------------
    def test_cross_user_job_404_on_all_five_routes(self):
        for route in ROUTES:
            resp = self.h.call(route, "job_a", as_user=USER_B["id"])
            self.assertEqual(resp.status_code, 404, f"[{route}] expected 404 got {resp.status_code}")
            self.assertEqual(resp.json().get("detail"), "Job not found")

    def test_symmetric_cross_user_404(self):
        # B owns job_b; A cannot use it either (both directions enforced).
        for route in ROUTES:
            resp = self.h.call(route, "job_b", as_user=USER_A["id"])
            self.assertEqual(resp.status_code, 404, f"[{route}] expected 404 got {resp.status_code}")

    # --- C: nonexistent job_id behaves exactly like a foreign one ------------
    def test_nonexistent_job_404_on_all_five_routes(self):
        for route in ROUTES:
            resp = self.h.call(route, "job_does_not_exist", as_user=USER_A["id"])
            self.assertEqual(resp.status_code, 404, f"[{route}] expected 404 got {resp.status_code}")

    def test_cross_user_and_nonexistent_return_identical_body(self):
        """No information about another user's job existence may be leaked."""
        for route in ROUTES:
            cross = self.h.call(route, "job_a", as_user=USER_B["id"])
            missing = self.h.call(route, "job_does_not_exist", as_user=USER_B["id"])
            self.assertEqual(cross.status_code, 404, f"[{route}]")
            self.assertEqual(missing.status_code, 404, f"[{route}]")
            self.assertEqual(cross.json(), missing.json(), f"[{route}] body leak")

    # --- D: forged identity headers cannot bypass the ownership gate ---------
    def test_forged_user_id_headers_cannot_bypass_ownership(self):
        for route in ROUTES:
            resp = self.h.call(route, "job_a", as_user=USER_B["id"], headers=FORGED_ID_HEADERS)
            self.assertEqual(resp.status_code, 404, f"[{route}] expected 404 got {resp.status_code}")

    # --- E: no cross-user record is ever created -----------------------------
    def test_cross_user_attempts_create_no_rows(self):
        for route in ROUTES:
            self.h.call(route, "job_a", as_user=USER_B["id"])
        self.h.call("match", "job_a", as_user=USER_B["id"])

        self.assertEqual(self._count(Application, job_id="job_a"), 0)
        self.assertEqual(self._count(JobMatch, job_id="job_a"), 0)
        self.assertEqual(self._count(ResumeJobAnalysis, job_id="job_a"), 0)
        self.assertEqual(self._count(TailoredResume, job_id="job_a"), 0)
        self.assertEqual(self._count(CoverLetter, job_id="job_a"), 0)

    def test_ai_provider_never_called_within_ownership_gate(self):
        for route in ("cover-letter",):
            self.h.call(route, "job_a", as_user=USER_B["id"])
            self.h.call(route, "job_does_not_exist", as_user=USER_A["id"])
        for route in ("resume-tailor",):
            self.h.call(route, "job_a", as_user=USER_B["id"])
            self.h.call(route, "job_does_not_exist", as_user=USER_A["id"])

        self.assertEqual(self.h.cover_letter_provider.calls, 0)
        self.assertEqual(self.h.tailor_provider.calls, 0)


class GetOwnJobHelperTests(unittest.TestCase):
    def setUp(self):
        self.h = _JobCreatorOwnershipHarness()

    def tearDown(self):
        self.h.close()

    def _user(self, user_id):
        db = self.h.Session()
        try:
            return db.query(User).filter(User.id == user_id).first()
        finally:
            db.close()

    def test_owner_gets_their_job(self):
        db = self.h.Session()
        try:
            job = get_own_job("job_a", self._user(USER_A["id"]), db)
            self.assertEqual(job.id, "job_a")
            self.assertEqual(job.user_id, USER_A["id"])
        finally:
            db.close()

    def test_foreign_job_raises_404(self):
        from fastapi import HTTPException
        db = self.h.Session()
        try:
            with self.assertRaises(HTTPException) as ctx:
                get_own_job("job_a", self._user(USER_B["id"]), db)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            db.close()

    def test_nonexistent_job_raises_404(self):
        from fastapi import HTTPException
        db = self.h.Session()
        try:
            with self.assertRaises(HTTPException) as ctx:
                get_own_job("job_missing", self._user(USER_A["id"]), db)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()