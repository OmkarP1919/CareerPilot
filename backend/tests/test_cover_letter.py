"""Tests for the AI Cover Letter generation backend (Phase 4A).

These tests never call a real, paid AI provider. The provider is mocked so the
service/API logic, validation and error handling can be exercised
deterministically.
"""

import copy
import os
import shutil
import tempfile
import unittest
from unittest import mock

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
from app.models.cover_letter import CoverLetter
from app.services.cover_letter import (
    CoverLetterInput,
    build_provider,
    call_cover_letter,
    assemble_content,
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
from app.api.cover_letter import router as cover_letter_router

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
    """A valid structured AI response that stays grounded in the source resume.

    Note: the job requires Kubernetes but the candidate has no such evidence;
    a rule-abiding response lists it in unsupported_requirements and never
    claims it as a fact.
    """
    return {
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


class FakeProvider:
    """Deterministic stand-in for BaseAIProvider."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0
        self.last_user_prompt = None

    def generate_structured(self, *, system_prompt, user_prompt, schema, timeout_seconds):
        self.calls += 1
        self.last_user_prompt = user_prompt
        if self.error:
            raise self.error
        return copy.deepcopy(self.response)


class JobStub:
    def __init__(self, id="job_1", title="Backend Developer", description=None, required_skills=None):
        self.id = id
        self.title = title
        self.company = "Acme"
        self.description = description or (
            "Backend Developer required. Python, FastAPI, PostgreSQL, Docker. "
            "Degree in Computer Science. AWS and Kubernetes are a plus."
        )
        self.required_skills = required_skills or "Python, FastAPI, PostgreSQL, Docker, Kubernetes"


class TestCoverLetterServiceValidation(unittest.TestCase):
    """Unit tests for the cover letter service's AI call + validation."""

    def _input(self):
        return CoverLetterInput(
            resume=copy.deepcopy(SOURCE_RESUME),
            extracted_text="Backend Developer Acme Corp 2020 Present.",
            profile={"skills": ["Python", "FastAPI", "PostgreSQL"]},
            job=JobStub(),
            analysis={"matched_skills": ["Python"], "missing_skills": ["Kubernetes"]},
        )

    def test_valid_structured_ai_response(self):
        provider = FakeProvider(response=valid_ai_response())
        result = call_cover_letter(provider, self._input(), timeout_seconds=30)
        self.assertEqual(result["greeting"], "Dear Hiring Manager,")
        self.assertEqual(result["unsupported_requirements"], ["Kubernetes"])
        self.assertEqual(len(result["body_paragraphs"]), 1)

    def test_invalid_pydantic_response_raises_controlled_error(self):
        bad = valid_ai_response()
        bad["body_paragraphs"] = "this should be a list"
        provider = FakeProvider(response=bad)
        with self.assertRaises(AIInvalidResponseError):
            call_cover_letter(provider, self._input(), timeout_seconds=30)

    def test_non_object_response_raises_controlled_error(self):
        provider = FakeProvider(response=["not", "an", "object"])
        with self.assertRaises(AIInvalidResponseError):
            call_cover_letter(provider, self._input(), timeout_seconds=30)

    def test_provider_timeout_propagates(self):
        provider = FakeProvider(error=AITimeoutError("timeout"))
        with self.assertRaises(AITimeoutError):
            call_cover_letter(provider, self._input(), timeout_seconds=1)

    def test_provider_failure_propagates(self):
        provider = FakeProvider(error=AIProviderUnavailableError("down"))
        with self.assertRaises(AIProviderUnavailableError):
            call_cover_letter(provider, self._input(), timeout_seconds=1)

    def test_original_resume_unchanged_after_call(self):
        original = copy.deepcopy(SOURCE_RESUME)
        provider = FakeProvider(response=valid_ai_response())
        call_cover_letter(provider, self._input(), timeout_seconds=30)
        self.assertEqual(SOURCE_RESUME, original)

    def test_assemble_content_joins_sections(self):
        content = valid_ai_response()
        text = assemble_content(content)
        self.assertIn("Dear Hiring Manager", text)
        self.assertIn("Python, FastAPI and PostgreSQL", text)
        self.assertIn("Sincerely", text)

    def test_summarise_for_response_keeps_structure(self):
        result = valid_ai_response()
        view = summarise_for_response(result)
        self.assertEqual(view["greeting"], result["greeting"])
        self.assertEqual(view["unsupported_requirements"], ["Kubernetes"])
        self.assertEqual(view["supported_points"], result["supported_points"])

    def test_system_instruction_is_anti_hallucination(self):
        self.assertIn("Never invent", SYSTEM_INSTRUCTION)
        self.assertIn("never convert a job requirement", SYSTEM_INSTRUCTION.lower())
        self.assertIn("unsupported_requirements", SYSTEM_INSTRUCTION)

    def test_no_unsupported_requirement_represented_as_candidate_fact(self):
        # Even if AI is loose, the structured output must keep Kubernetes in
        # unsupported_requirements, not in the body.
        provider = FakeProvider(response=valid_ai_response())
        result = call_cover_letter(provider, self._input(), timeout_seconds=30)
        body_text = " ".join(result["body_paragraphs"]).lower()
        self.assertIn("kubernetes", [u.lower() for u in result["unsupported_requirements"]])
        self.assertNotIn("kubernetes", body_text)


class TestBuildProvider(unittest.TestCase):
    def test_missing_provider_raises_config_error(self):
        with self.assertRaises(AIProviderConfigurationError):
            build_provider(mock.Mock(AI_PROVIDER="", AI_API_KEY="", AI_MODEL=""))

    def test_missing_api_key_raises_config_error(self):
        with self.assertRaises(AIProviderConfigurationError):
            build_provider(mock.Mock(AI_PROVIDER="openai", AI_API_KEY="", AI_MODEL="gpt-4o-mini"))

    def test_valid_openai_builds(self):
        p = build_provider(mock.Mock(AI_PROVIDER="openai", AI_API_KEY="secret", AI_MODEL="gpt-4o-mini"))
        self.assertEqual(p.model, "gpt-4o-mini")


class PrivacyTest(unittest.TestCase):
    def test_no_sensitive_contact_info_sent_to_ai(self):
        provider = FakeProvider(response=valid_ai_response())
        inp = CoverLetterInput(
            resume=copy.deepcopy(SOURCE_RESUME),
            extracted_text="Alex Doe alex@test.com 5551234567 Backend.",
            profile={"skills": ["Python"]},
            job=JobStub(),
            analysis={},
        )
        call_cover_letter(provider, inp, timeout_seconds=30)
        prompt = provider.last_user_prompt.lower()
        # Contact info / sensitive identifiers must not be transmitted in raw form.
        self.assertNotIn("alex@test.com", prompt)
        self.assertNotIn("5551234567", prompt)
        # They are replaced by redaction placeholders.
        self.assertIn("[contact removed]", prompt)
        self.assertIn("[phone removed]", prompt)


class CoverLetterAPITestBase(unittest.TestCase):
    USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
    USER_B = {"id": "user_b", "firebase_uid": "fb_b"}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "cover.db")
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
                                    "AWS and Kubernetes are a plus."),
                       required_skills="Python, FastAPI, PostgreSQL, Kubernetes")
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
        self.app.include_router(cover_letter_router)

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
            "app.api.cover_letter.build_provider", return_value=self._provider
        )
        self.mock_build_provider = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestCoverLetterAPI(CoverLetterAPITestBase):
    def test_generation_persisted_and_returns_structured(self):
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["resume_id"], "res_a")
        self.assertEqual(body["job_id"], "job_1")
        self.assertEqual(body["structured_content"]["greeting"], "Dear Hiring Manager,")
        self.assertIn("Kubernetes", body["unsupported_requirements"])
        self.assertEqual(self._provider.calls, 1)

        # Persisted.
        db = self.Session()
        count = db.query(CoverLetter).filter(
            CoverLetter.user_id == self.USER_A["id"]
        ).count()
        db.close()
        self.assertEqual(count, 1)

    def test_generation_content_is_assembled(self):
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("Dear Hiring Manager", body["content"])
        self.assertIn("Sincerely", body["content"])

    def test_original_resume_unchanged_after_generation(self):
        db = self.Session()
        before = copy.deepcopy(db.query(Resume).filter(Resume.id == "res_a").first().parsed_data)
        db.close()
        self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        db = self.Session()
        after = db.query(Resume).filter(Resume.id == "res_a").first().parsed_data
        db.close()
        self.assertEqual(before, after)

    def test_repeated_request_reuses_existing_no_duplicate(self):
        r1 = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(r1.status_code, 200)
        calls_after_first = self._provider.calls

        r2 = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(self._provider.calls, calls_after_first)
        self.assertEqual(r2.json()["id"], r1.json()["id"])

        db = self.Session()
        count = db.query(CoverLetter).filter(
            CoverLetter.user_id == self.USER_A["id"],
            CoverLetter.job_id == "job_1",
            CoverLetter.source_resume_id == "res_a",
        ).count()
        db.close()
        self.assertEqual(count, 1)

    def test_regenerate_forces_new_ai_call(self):
        r1 = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(r1.status_code, 200)
        calls_before = self._provider.calls
        r2 = self.client.post("/jobs/job_1/cover-letter",
                              json={"resume_id": "res_a", "regenerate": True})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(self._provider.calls, calls_before + 1)
        # Still only one row (updated), no uncontrolled duplicate.
        db = self.Session()
        count = db.query(CoverLetter).filter(
            CoverLetter.source_resume_id == "res_a",
            CoverLetter.job_id == "job_1",
        ).count()
        db.close()
        self.assertEqual(count, 1)

    def test_retrieve_existing_cover_letter(self):
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 200)
        letter_id = resp.json()["id"]

        get_resp = self.client.get(f"/jobs/job_1/cover-letter/res_a")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["id"], letter_id)

    def test_retrieve_missing_cover_letter_404(self):
        resp = self.client.get("/jobs/job_1/cover-letter/res_a")
        self.assertEqual(resp.status_code, 404)

    def test_cannot_use_another_users_resume(self):
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_b"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._provider.calls, 0)

    def test_nonexistent_job_404(self):
        resp = self.client.post("/jobs/nope/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 404)

    def test_nonexistent_resume_404(self):
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "nope"})
        self.assertEqual(resp.status_code, 404)

    def test_user_b_cannot_see_user_a_letter_via_get(self):
        self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.current_user_id = self.USER_B["id"]
        resp = self.client.get("/jobs/job_1/cover-letter/res_a")
        self.assertEqual(resp.status_code, 404)

    def test_user_b_cannot_generate_from_user_a_resume(self):
        self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.current_user_id = self.USER_B["id"]
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 404)


class TestCoverLetterParsingStates(unittest.TestCase):
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
                       description="Python FastAPI Kubernetes", required_skills="Python")
        db.add(self.job)
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(cover_letter_router)

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
            "app.api.cover_letter.build_provider", return_value=self._provider
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
        resp = self.client.post("/jobs/job/cover-letter", json={"resume_id": "r_pending"})
        self.assertEqual(resp.status_code, 409)

    def test_failed_resume_422(self):
        self._make_resume("r_failed", "failed", error="parse error")
        resp = self.client.post("/jobs/job/cover-letter", json={"resume_id": "r_failed"})
        self.assertEqual(resp.status_code, 422)

    def test_empty_resume_422(self):
        self._make_resume("r_empty", "completed", parsed_data={})
        resp = self.client.post("/jobs/job/cover-letter", json={"resume_id": "r_empty"})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("No usable resume data", resp.json()["detail"])

    def test_scanned_resume_422(self):
        self._make_resume("r_scanned", "completed", parsed_data=None)
        resp = self.client.post("/jobs/job/cover-letter", json={"resume_id": "r_scanned"})
        self.assertEqual(resp.status_code, 422)

    def test_missing_job_description_422(self):
        db = self.Session()
        job = db.query(Job).filter(Job.id == "job").first()
        job.description = None
        job.required_skills = None
        db.commit()
        db.close()
        self._make_resume("r_ok", "completed", parsed_data={"skills": ["Python"]})
        resp = self.client.post("/jobs/job/cover-letter", json={"resume_id": "r_ok"})
        self.assertEqual(resp.status_code, 422)


class TestCoverLetterFailurePaths(CoverLetterAPITestBase):
    def test_missing_ai_key_503(self):
        self.mock_build_provider.side_effect = AIProviderConfigurationError("not configured")
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 503)
        self.assertIn("not configured", resp.json()["detail"])

    def test_ai_timeout_504(self):
        self._provider.error = AITimeoutError("timeout")
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 504)

    def test_ai_invalid_response_502(self):
        self._provider.error = AIInvalidResponseError("invalid")
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 502)

    def test_ai_unavailable_503(self):
        self._provider.error = AIProviderUnavailableError("unavailable")
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 503)

    def test_malformed_ai_output_not_persisted(self):
        # Provider returns valid JSON but invalid structure -> 502, nothing saved.
        bad = valid_ai_response()
        bad["body_paragraphs"] = "nope"
        self._provider.response = bad
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        self.assertEqual(resp.status_code, 502)
        db = self.Session()
        count = db.query(CoverLetter).filter(CoverLetter.user_id == self.USER_A["id"]).count()
        db.close()
        self.assertEqual(count, 0)

    def test_phase2_analysis_generated_and_reused(self):
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
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


class TestCoverLetterCollection(CoverLetterAPITestBase):
    def _list_app(self, user_id):
        from app.api.cover_letter import collection_router
        app2 = FastAPI()
        app2.include_router(collection_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            session = self.Session()
            try:
                return session.query(User).filter(User.id == user_id).first()
            finally:
                session.close()

        app2.dependency_overrides[get_db] = override_get_db
        app2.dependency_overrides[get_current_user] = override_get_current_user
        return TestClient(app2)

    def test_list_shows_owned_letters(self):
        self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        client2 = self._list_app(self.USER_A["id"])
        resp = client2.get("/cover-letters")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["job_title"], "Backend Developer")
        self.assertEqual(body[0]["source_resume_name"], "a.pdf")

    def test_list_is_ownership_isolated(self):
        self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        client2 = self._list_app(self.USER_B["id"])
        resp = client2.get("/cover-letters")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_delete_owned_letter(self):
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        letter_id = resp.json()["id"]
        client2 = self._list_app(self.USER_A["id"])
        del_resp = client2.delete(f"/cover-letters/{letter_id}")
        self.assertEqual(del_resp.status_code, 204)
        db = self.Session()
        count = db.query(CoverLetter).filter(CoverLetter.id == letter_id).count()
        db.close()
        self.assertEqual(count, 0)

    def test_delete_another_users_letter_404(self):
        resp = self.client.post("/jobs/job_1/cover-letter", json={"resume_id": "res_a"})
        letter_id = resp.json()["id"]
        client2 = self._list_app(self.USER_B["id"])
        del_resp = client2.delete(f"/cover-letters/{letter_id}")
        self.assertEqual(del_resp.status_code, 404)
        db = self.Session()
        count = db.query(CoverLetter).filter(CoverLetter.id == letter_id).count()
        db.close()
        self.assertEqual(count, 1)


class TestExistingEnginesUnchanged(unittest.TestCase):
    def test_profile_match_engine_still_importable(self):
        self.assertTrue(hasattr(matching, "calculate_match"))
        self.assertTrue(hasattr(matching, "parse_skills"))

    def test_resume_match_service_still_works(self):
        from app.services.resume_job_analysis import analyze_resume_against_job
        job = JobStub(required_skills="Python, FastAPI, PostgreSQL, Docker, Kubernetes")
        result = analyze_resume_against_job(copy.deepcopy(SOURCE_RESUME), job)
        self.assertIn("Python", result["matched_skills"])
        self.assertIn("Kubernetes", result["missing_skills"])


if __name__ == "__main__":
    unittest.main()
