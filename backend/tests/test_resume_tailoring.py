"""Tests for the AI Resume Tailoring backend (Phase 3A).

These tests never call a real, paid AI provider. The provider is mocked so the
service/API logic, validation and error handling can be exercised deterministically.
"""

import copy
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import httpx

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.resume import Resume
from app.models.job import Job
from app.models.resume_job_analysis import ResumeJobAnalysis
from app.models.tailored_resume import TailoredResume
from app.services.resume_tailoring import (
    TailoringInput,
    build_provider,
    call_tailoring,
    summarise_for_response,
    SYSTEM_INSTRUCTION,
)
from app.services.ai_provider import (
    AIInvalidResponseError,
    AIProviderConfigurationError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AITimeoutError,
)
from app.services import matching
from app.api.resume_tailoring import router as tailor_router

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


def valid_ai_response(resume=None):
    """A valid structured AI response that stays grounded in the source resume."""
    r = resume or SOURCE_RESUME
    return {
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


class FakeProvider:
    """Deterministic stand-in for BaseAIProvider."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    def generate_structured(self, *, system_prompt, user_prompt, schema, timeout_seconds):
        self.calls += 1
        if self.error:
            raise self.error
        # The mocked AI "follows the rules": return the copy verbatim.
        return copy.deepcopy(self.response)


class JobStub:
    def __init__(self, id="job_1", title="Backend Developer", description=None, required_skills=None):
        self.id = id
        self.title = title
        self.company = "Acme"
        self.description = description or (
            "Backend Developer required. Python, FastAPI, PostgreSQL, Docker. "
            "Degree in Computer Science. Kubernetes is a plus."
        )
        self.required_skills = required_skills or "Python, FastAPI, PostgreSQL, Docker"


class TestAIOutputValidation(unittest.TestCase):
    """Unit tests for the tailoring service's AI call + validation."""

    def _input(self):
        return TailoringInput(
            resume=copy.deepcopy(SOURCE_RESUME),
            extracted_text="Backend Developer Acme Corp 2020 Present.",
            job=JobStub(),
            analysis={"matched_skills": ["Python"], "missing_skills": ["Kubernetes"]},
        )

    def test_valid_structured_ai_response(self):
        provider = FakeProvider(response=valid_ai_response())
        result = call_tailoring(provider, self._input(), timeout_seconds=30)
        self.assertEqual(result["skills"]["kept"], ["Python", "FastAPI", "PostgreSQL", "Docker", "React"])
        self.assertEqual(result["keywords_added"], ["REST", "PostgreSQL"])
        self.assertEqual(result["keywords_not_added"], ["Kubernetes"])

    def test_invalid_json_response_raises_controlled_error(self):
        provider = FakeProvider(error=AIInvalidResponseError("bad json"))
        with self.assertRaises(AIInvalidResponseError):
            call_tailoring(provider, self._input(), timeout_seconds=30)

    def test_invalid_pydantic_response_raises_controlled_error(self):
        # Provider returns valid JSON but a structurally invalid result.
        bad = valid_ai_response()
        bad["experience"] = "this should be a list"  # type mismatch -> Pydantic fails
        provider = FakeProvider(response=bad)
        with self.assertRaises(AIInvalidResponseError):
            call_tailoring(provider, self._input(), timeout_seconds=30)

    def test_non_object_response_raises_controlled_error(self):
        provider = FakeProvider(response=["not", "an", "object"])
        with self.assertRaises(AIInvalidResponseError):
            call_tailoring(provider, self._input(), timeout_seconds=30)

    def test_provider_timeout_propagates(self):
        provider = FakeProvider(error=AITimeoutError("timeout"))
        with self.assertRaises(AITimeoutError):
            call_tailoring(provider, self._input(), timeout_seconds=1)

    def test_provider_failure_propagates(self):
        provider = FakeProvider(error=AIProviderUnavailableError("down"))
        with self.assertRaises(AIProviderUnavailableError):
            call_tailoring(provider, self._input(), timeout_seconds=1)

    def test_original_resume_unchanged_after_call(self):
        original = copy.deepcopy(SOURCE_RESUME)
        provider = FakeProvider(response=valid_ai_response())
        call_tailoring(provider, self._input(), timeout_seconds=30)
        self.assertEqual(SOURCE_RESUME, original)

    def test_no_unsupported_skills_inserted_when_ai_follows_rules(self):
        # The grounded response keeps Kubernetes only in keywords_not_added.
        provider = FakeProvider(response=valid_ai_response())
        result = call_tailoring(provider, self._input(), timeout_seconds=30)
        all_claimed_skills = (
            result["skills"]["kept"] + result["skills"]["emphasized"]
        )
        self.assertIn("Kubernetes", result["keywords_not_added"])
        self.assertNotIn("Kubernetes", all_claimed_skills)
        # Nothing in the grounded output that isn't in the source resume.
        source_skill_lower = {s.lower() for s in SOURCE_RESUME["skills"]}
        for skill in result["skills"]["kept"] + result["skills"]["emphasized"]:
            self.assertIn(skill.lower(), source_skill_lower)

    def test_summarise_for_response_shapes_frontend_view(self):
        result = valid_ai_response()
        view = summarise_for_response(result)
        self.assertEqual(view["summary"], result["summary"]["tailored"])
        self.assertEqual(view["skills"], result["skills"]["kept"])
        self.assertEqual(view["emphasized_skills"], result["skills"]["emphasized"])
        self.assertEqual(len(view["projects"]), 1)

    def test_system_instruction_is_anti_hallucination(self):
        self.assertIn("Never invent", SYSTEM_INSTRUCTION)
        self.assertIn("must use only information", SYSTEM_INSTRUCTION.lower())
        self.assertIn("keywords_not_added", SYSTEM_INSTRUCTION)


class TestBuildProvider(unittest.TestCase):
    def test_missing_provider_raises_config_error(self):
        with self.assertRaises(AIProviderConfigurationError):
            build_provider(mock.Mock(AI_PROVIDER="", AI_API_KEY="", AI_MODEL=""))

    def test_missing_api_key_raises_config_error(self):
        with self.assertRaises(AIProviderConfigurationError):
            build_provider(mock.Mock(AI_PROVIDER="openai", AI_API_KEY="", AI_MODEL="gpt-4o-mini"))

    def test_unsupported_provider_raises_config_error(self):
        with self.assertRaises(AIProviderConfigurationError):
            build_provider(mock.Mock(AI_PROVIDER="unknown", AI_API_KEY="key", AI_MODEL="m"))

    def test_valid_openai_builds(self):
        p = build_provider(mock.Mock(AI_PROVIDER="openai", AI_API_KEY="secret", AI_MODEL="gpt-4o-mini"))
        self.assertEqual(p.model, "gpt-4o-mini")


class TailoringAPITestBase(unittest.TestCase):
    USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
    USER_B = {"id": "user_b", "firebase_uid": "fb_b"}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "tailor.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        db.add_all([
            User(id=self.USER_A["id"], firebase_uid=self.USER_A["firebase_uid"],
                 email="a@test.com", name="A"),
            User(id=self.USER_B["id"], firebase_uid=self.USER_B["firebase_uid"],
                 email="b@test.com", name="B"),
        ])
        self.job = Job(id="job_1", user_id=self.USER_A["id"], title="Backend Developer",
                       company="Acme",
                       description=("Backend Developer required. Python, FastAPI, PostgreSQL, Docker. "
                                    "Kubernetes is a plus."),
                       required_skills="Python, FastAPI, PostgreSQL")
        self.resume_a = Resume(
            id="res_a", user_id=self.USER_A["id"], filename="a.pdf",
            original_filename="a.pdf", file_path="/tmp/a.pdf", file_size="1",
            parsing_status="completed", parsed_data=copy.deepcopy(SOURCE_RESUME),
            extracted_text="Backend Developer Acme 2020 Present.",
        )
        self.resume_b = Resume(
            id="res_b", user_id=self.USER_B["id"], filename="b.pdf",
            original_filename="b.pdf", file_path="/tmp/b.pdf", file_size="1",
            parsing_status="completed", parsed_data={"skills": ["React"]},
        )
        db.add_all([self.job, self.resume_a, self.resume_b])
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(tailor_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        self.current_user_id = self.USER_A["id"]

        def override_get_current_user():
            session = self.Session()
            try:
                return session.query(User).filter(User.id == self.current_user_id).first()
            finally:
                session.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(self.app)

        self._provider = FakeProvider(response=valid_ai_response())
        patcher = mock.patch(
            "app.api.resume_tailoring.build_provider", return_value=self._provider
        )
        self.mock_build_provider = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestTailoringAPI(TailoringAPITestBase):
    def test_tailoring_persisted_and_returns_structured(self):
        resp = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["resume_id"], "res_a")
        self.assertEqual(body["job_id"], "job_1")
        self.assertIn("Python", body["tailored_content"]["skills"])
        self.assertIn("Kubernetes", body["unsupported_job_keywords"])
        self.assertEqual(self._provider.calls, 1)

        # Persisted.
        db = self.Session()
        count = db.query(TailoredResume).filter(
            TailoredResume.user_id == self.USER_A["id"]
        ).count()
        db.close()
        self.assertEqual(count, 1)

    def test_original_resume_unchanged_after_tailoring(self):
        db = self.Session()
        before = copy.deepcopy(db.query(Resume).filter(Resume.id == "res_a").first().parsed_data)
        db.close()
        self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        db = self.Session()
        after = db.query(Resume).filter(Resume.id == "res_a").first().parsed_data
        db.close()
        self.assertEqual(before, after)

    def test_repeated_request_reuses_existing_no_duplicate(self):
        r1 = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(r1.status_code, 200)
        calls_after_first = self._provider.calls

        r2 = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(r2.status_code, 200)
        # No new AI call, no duplicate tailoring row.
        self.assertEqual(self._provider.calls, calls_after_first)
        self.assertEqual(r2.json()["id"], r1.json()["id"])

        db = self.Session()
        count = db.query(TailoredResume).filter(
            TailoredResume.user_id == self.USER_A["id"],
            TailoredResume.job_id == "job_1",
            TailoredResume.source_resume_id == "res_a",
        ).count()
        db.close()
        self.assertEqual(count, 1)

    def test_regenerate_forces_new_ai_call(self):
        r1 = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(r1.status_code, 200)
        calls_before = self._provider.calls
        r2 = self.client.post("/jobs/job_1/resume-tailor",
                              json={"resume_id": "res_a", "regenerate": True})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(self._provider.calls, calls_before + 1)
        # Still only one row (updated), no uncontrolled duplicate.
        db = self.Session()
        count = db.query(TailoredResume).filter(
            TailoredResume.source_resume_id == "res_a",
            TailoredResume.job_id == "job_1",
        ).count()
        db.close()
        self.assertEqual(count, 1)

    def test_cannot_tailor_another_users_resume(self):
        resp = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_b"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._provider.calls, 0)

    def test_nonexistent_job_404(self):
        resp = self.client.post("/jobs/nope/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 404)

    def test_nonexistent_resume_404(self):
        resp = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "nope"})
        self.assertEqual(resp.status_code, 404)

    def test_user_b_cannot_see_user_a_tailoring(self):
        self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        # Switch current user to B; B cannot reach A's resume (404, not data leak).
        self.current_user_id = self.USER_B["id"]
        resp = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 404)


class TestTailoringParsingStates(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "state.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        self.user = User(id="user", firebase_uid="fb", email="u@t.com", name="U")
        db.add(self.user)
        self.job = Job(id="job", user_id="user", title="Backend", company="C",
                       description="Python FastAPI", required_skills="Python")
        db.add(self.job)
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(tailor_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            session = self.Session()
            try:
                return session.query(User).filter(User.id == "user").first()
            finally:
                session.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_current_user] = override_get_current_user

        self._provider = FakeProvider(response=valid_ai_response())
        patcher = mock.patch(
            "app.api.resume_tailoring.build_provider", return_value=self._provider
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.client = TestClient(self.app)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_resume(self, rid, status, parsed_data=None, error=None, text=None):
        db = self.Session()
        r = Resume(
            id=rid, user_id="user", filename=f"{rid}.pdf", original_filename=f"{rid}.pdf",
            file_path="/tmp/x.pdf", file_size="1", parsing_status=status,
            parsed_data=parsed_data, parsing_error=error, extracted_text=text,
        )
        db.add(r)
        db.commit()
        db.close()

    def test_pending_resume_409(self):
        self._make_resume("r_pending", "pending")
        resp = self.client.post("/jobs/job/resume-tailor", json={"resume_id": "r_pending"})
        self.assertEqual(resp.status_code, 409)

    def test_failed_resume_422(self):
        self._make_resume("r_failed", "failed", error="parse error")
        resp = self.client.post("/jobs/job/resume-tailor", json={"resume_id": "r_failed"})
        self.assertEqual(resp.status_code, 422)

    def test_empty_resume_422(self):
        self._make_resume("r_empty", "completed", parsed_data={})
        resp = self.client.post("/jobs/job/resume-tailor", json={"resume_id": "r_empty"})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("No usable resume data", resp.json()["detail"])

    def test_scanned_resume_422(self):
        # Scanned PDFs parse as 'completed' with parsed_data=None.
        self._make_resume("r_scanned", "completed", parsed_data=None)
        resp = self.client.post("/jobs/job/resume-tailor", json={"resume_id": "r_scanned"})
        self.assertEqual(resp.status_code, 422)

    def test_missing_job_description_422(self):
        db = self.Session()
        job = db.query(Job).filter(Job.id == "job").first()
        job.description = None
        job.required_skills = None
        db.commit()
        db.close()
        self._make_resume("r_ok", "completed", parsed_data={"skills": ["Python"]})
        resp = self.client.post("/jobs/job/resume-tailor", json={"resume_id": "r_ok"})
        self.assertEqual(resp.status_code, 422)


class TestTailoringFailurePaths(TailoringAPITestBase):
    def test_missing_ai_key_503(self):
        self.mock_build_provider.side_effect = AIProviderConfigurationError("not configured")
        resp = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 503)
        self.assertIn("not configured", resp.json()["detail"])

    def test_ai_timeout_504(self):
        self._provider.error = AITimeoutError("timeout")
        resp = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 504)

    def test_ai_invalid_response_502(self):
        self._provider.error = AIInvalidResponseError("invalid")
        resp = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 502)

    def test_ai_unavailable_503(self):
        self._provider.error = AIProviderUnavailableError("unavailable")
        resp = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 503)

    def test_phase2_analysis_generated_and_reused(self):
        resp = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 200)
        db = self.Session()
        analysis = db.query(ResumeJobAnalysis).filter(
            ResumeJobAnalysis.user_id == self.USER_A["id"],
            ResumeJobAnalysis.resume_id == "res_a",
            ResumeJobAnalysis.job_id == "job_1",
        ).first()
        db.close()
        self.assertIsNotNone(analysis)
        self.assertIn("Python", analysis.analysis_data["matched_skills"])


class TestExistingEnginesUnchanged(unittest.TestCase):
    def test_profile_match_engine_still_importable(self):
        self.assertTrue(hasattr(matching, "calculate_match"))
        self.assertTrue(hasattr(matching, "parse_skills"))
        self.assertTrue(hasattr(matching, "normalize"))

    def test_resume_match_service_still_works(self):
        from app.services.resume_job_analysis import analyze_resume_against_job
        job = JobStub(required_skills="Python, FastAPI, PostgreSQL, Docker, Kubernetes")
        result = analyze_resume_against_job(copy.deepcopy(SOURCE_RESUME), job)
        self.assertIn("Python", result["matched_skills"])
        self.assertIn("Kubernetes", result["missing_skills"])


class TestTailoredResumesList(TailoringAPITestBase):
    def test_list_tailored_resumes_shows_job_and_source(self):
        # Create a tailoring via the API so it is persisted.
        self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})

        # Use a separate app that exposes the /resumes/tailored list route.
        app2 = FastAPI()
        from app.api.resume_tailoring import tailored_list_router
        app2.include_router(tailored_list_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            session = self.Session()
            try:
                return session.query(User).filter(User.id == self.USER_A["id"]).first()
            finally:
                session.close()

        app2.dependency_overrides[get_db] = override_get_db
        app2.dependency_overrides[get_current_user] = override_get_current_user
        client2 = TestClient(app2)

        resp = client2.get("/resumes/tailored")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["job_title"], "Backend Developer")
        self.assertEqual(body[0]["job_company"], "Acme")
        self.assertEqual(body[0]["source_resume_name"], "a.pdf")

    def test_list_is_ownership_isolated(self):
        # Persist a tailoring for user A but list as B -> empty.
        self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_a"})

        from app.api.resume_tailoring import tailored_list_router
        app2 = FastAPI()
        app2.include_router(tailored_list_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            session = self.Session()
            try:
                return session.query(User).filter(User.id == self.USER_B["id"]).first()
            finally:
                session.close()

        app2.dependency_overrides[get_db] = override_get_db
        app2.dependency_overrides[get_current_user] = override_get_current_user
        client2 = TestClient(app2)

        resp = client2.get("/resumes/tailored")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])


class FakeHttpResponse:
    def __init__(self, status_code, json_body):
        self.status_code = status_code
        self._body = json_body

    def json(self):
        return self._body


def _chat_response(content):
    return {"choices": [{"message": {"content": json.dumps(content)}}]}


class TestOpenAIProviderWireup(unittest.TestCase):
    """Unit tests for the OpenAI-compatible provider (base URL routing and the
    basic-JSON fallback used for routers like OpenRouter). Never calls a real AI."""

    def _response_from_payload(self, records):
        # Build a 200 response using the recorded payload (echo content back).
        content = {
            "summary": {"original": "o", "tailored": "t"},
            "skills": {"kept": ["Python"], "emphasized": [], "removed": []},
            "experience": [],
            "projects": [],
            "education": [],
            "certifications": [],
            "keywords_added": [],
            "keywords_not_added": [],
            "overall_changes": [],
            "warnings": [],
        }
        return records

    def test_structured_output_uses_custom_base_url_and_require_parameters(self):
        from app.services.ai_provider.openai_provider import OpenAIProvider

        provider = OpenAIProvider(
            api_key="k", model="openai/gpt-4o-mini", base_url="https://openrouter.ai/api/v1"
        )
        captured = {}

        def fake_post(url, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["payload"] = json
            return FakeHttpResponse(200, _chat_response({}))

        with mock.patch("app.services.ai_provider.openai_provider.httpx.post", side_effect=fake_post):
            result = provider.generate_structured(
                system_prompt="sys",
                user_prompt="user",
                schema={"type": "object", "properties": {}},
                timeout_seconds=30,
            )

        self.assertIsInstance(result, dict)
        self.assertTrue(captured["url"].startswith("https://openrouter.ai/api/v1/chat/completions"))
        payload = captured["payload"]
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(payload["response_format"]["json_schema"]["strict"], True)
        self.assertEqual(payload["provider"], {"require_parameters": True})

    def test_json_object_fallback_when_structured_not_supported(self):
        from app.services.ai_provider.openai_provider import OpenAIProvider

        provider = OpenAIProvider(
            api_key="k", model="m", base_url="https://openrouter.ai/api/v1"
        )
        calls = []

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append(json if json else {})
            if len(calls) == 1:
                # Endpoint rejects strict structured output.
                return FakeHttpResponse(422, {"error": {"message": "structured outputs not supported"}})
            return FakeHttpResponse(200, _chat_response({}))

        with mock.patch("app.services.ai_provider.openai_provider.httpx.post", side_effect=fake_post):
            provider.generate_structured(
                system_prompt="sys",
                user_prompt="user",
                schema={"type": "object", "properties": {}},
                timeout_seconds=30,
            )

        self.assertEqual(len(calls), 2)
        # First attempt uses strict json_schema, fallback uses basic JSON mode.
        self.assertEqual(calls[0]["response_format"]["type"], "json_schema")
        self.assertEqual(calls[1]["response_format"]["type"], "json_object")

    def test_rate_limit_raises_controlled_error(self):
        from app.services.ai_provider.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key="k", model="m", base_url="https://openrouter.ai/api/v1")

        def fake_post(url, json=None, headers=None, timeout=None):
            return FakeHttpResponse(429, {"error": {"message": "rate limit"}})

        with mock.patch("app.services.ai_provider.openai_provider.httpx.post", side_effect=fake_post):
            with self.assertRaises(AIRateLimitError):
                provider.generate_structured(
                    system_prompt="sys",
                    user_prompt="user",
                    schema={"type": "object", "properties": {}},
                    timeout_seconds=30,
                )

    def test_get_provider_passes_base_url(self):
        from app.services.ai_provider import get_provider

        provider = get_provider(
            provider_name="openai",
            api_key="k",
            model="m",
            base_url="https://openrouter.ai/api/v1",
        )
        self.assertEqual(provider.base_url, "https://openrouter.ai/api/v1")


if __name__ == "__main__":
    unittest.main()
