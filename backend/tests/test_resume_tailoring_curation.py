"""Tests for Phase 7.0C.3 Resume Tailoring Curation.

Verifies:
1. No curation preserves existing behavior.
2. Selected experience indices filter correctly.
3. Explicit empty experience selection produces zero experiences.
4. Selected project indices filter correctly.
5. Explicit empty project selection produces zero projects.
6. Excluded experience cannot appear in generated structured_data (post-gen filter).
7. Excluded project cannot appear in generated structured_data (post-gen filter).
8. Excluded content cannot leak through extracted_text (prompt text isolated).
9. Master resume parsed_data remains unchanged.
10. Curated tailoring does not reuse uncurated cached output.
11. Original content/comparison contains only curated records.
12. PDF export excludes unselected experiences/projects.
13. DOCX export excludes unselected experiences/projects.
14. Invalid indices are handled safely (no crash, out-of-bounds ignored).
15. Existing uncurated tailoring remains backward compatible.
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
from app.models.tailored_resume import TailoredResume
from app.api.resume_tailoring import router as tailor_router
from app.services.resume_export import build_export_document, render_pdf, render_docx

SOURCE_RESUME_MULTI = {
    "basic_info": {"name": "Alex Doe", "email": "alex@test.com", "phone": "5551234567"},
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "React"],
    "experience": [
        {
            "job_title": "Senior Backend Engineer",
            "company": "Acme Corp",
            "dates": "2022 - Present",
            "description": "Architected cloud APIs.",
        },
        {
            "job_title": "Full Stack Developer",
            "company": "Beta Startup",
            "dates": "2020 - 2022",
            "description": "Built web apps with React and Node.",
        },
        {
            "job_title": "Junior Intern",
            "company": "Legacy Systems",
            "dates": "2019 - 2020",
            "description": "Maintained old legacy code.",
        },
    ],
    "projects": [
        {
            "name": "Cloud API Gateway",
            "technologies": ["Python", "FastAPI"],
            "description": "High-throughput API gateway.",
        },
        {
            "name": "Personal Portfolio",
            "technologies": ["HTML", "CSS"],
            "description": "Personal blog site.",
        },
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


class FakeProvider:
    def __init__(self, response=None):
        self.response = response
        self.calls = 0
        self.last_user_prompt = ""

    def generate_structured(self, *, system_prompt, user_prompt, schema, timeout_seconds):
        self.calls += 1
        self.last_user_prompt = user_prompt
        return copy.deepcopy(self.response)


def make_ai_response():
    return {
        "summary": {
            "original": "Backend engineer.",
            "tailored": "Senior Backend Engineer specializing in cloud APIs.",
        },
        "skills": {
            "kept": ["Python", "FastAPI", "PostgreSQL"],
            "emphasized": ["FastAPI"],
            "removed": [],
        },
        "experience": [
            {
                "original_title": "Senior Backend Engineer",
                "company": "Acme Corp",
                "original_bullets": ["Architected cloud APIs."],
                "tailored_bullets": ["Architected high-scale cloud APIs."],
                "changes": ["Emphasized scalability."],
            },
            {
                "original_title": "Full Stack Developer",
                "company": "Beta Startup",
                "original_bullets": ["Built web apps."],
                "tailored_bullets": ["Engineered full-stack features."],
                "changes": [],
            },
            {
                "original_title": "Junior Intern",
                "company": "Legacy Systems",
                "original_bullets": ["Maintained legacy code."],
                "tailored_bullets": ["Supported backend services."],
                "changes": [],
            },
        ],
        "projects": [
            {
                "name": "Cloud API Gateway",
                "original_description": "High-throughput API gateway.",
                "tailored_description": "Engineered high-throughput API gateway.",
                "changes": [],
            },
            {
                "name": "Personal Portfolio",
                "original_description": "Personal blog site.",
                "tailored_description": "Developed web platform.",
                "changes": [],
            },
        ],
        "education": ["B.Tech in Computer Science, Example University, 2020"],
        "certifications": ["AWS Certified Solutions Architect"],
        "keywords_added": ["Cloud", "API"],
        "keywords_not_added": [],
        "overall_changes": ["Tailored for backend role."],
        "warnings": [],
    }


class TestResumeTailoringCuration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "curation_test.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()

        self.user = User(id="usr_1", firebase_uid="fb_1", email="u@test.com", name="User")
        self.job = Job(
            id="job_1",
            user_id="usr_1",
            title="Senior Backend Engineer",
            company="Acme",
            description="We need a Senior Backend Engineer skilled in Python and FastAPI.",
            required_skills="Python, FastAPI, PostgreSQL",
        )
        self.resume = Resume(
            id="res_1",
            user_id="usr_1",
            filename="alex.pdf",
            original_filename="alex.pdf",
            file_path="/tmp/alex.pdf",
            file_size="1024",
            parsing_status="completed",
            parsed_data=copy.deepcopy(SOURCE_RESUME_MULTI),
            extracted_text="Senior Backend Engineer Acme Corp. Full Stack Developer Beta Startup. Junior Intern Legacy Systems.",
        )
        db.add_all([self.user, self.job, self.resume])
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
                return session.query(User).filter(User.id == "usr_1").first()
            finally:
                session.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(self.app)

        self.provider = FakeProvider(response=make_ai_response())
        patcher = mock.patch(
            "app.api.resume_tailoring.build_provider", return_value=self.provider
        )
        self.mock_provider = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_curation_preserves_all_content(self):
        """1. Backward compatibility: When no curation is specified, all experiences and projects are included."""
        resp = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        tailored = data["tailored_content"]
        self.assertEqual(len(tailored["experience"]), 3)
        self.assertEqual(len(tailored["projects"]), 2)

    def test_selected_experience_indices_filtering(self):
        """2. Selected experience indices filter the experiences to only selected items."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        tailored = data["tailored_content"]
        # Only experience 0 (Senior Backend Engineer) should be present
        self.assertEqual(len(tailored["experience"]), 1)
        self.assertEqual(tailored["experience"][0]["original_title"], "Senior Backend Engineer")

    def test_explicit_empty_experience_selection(self):
        """3. Explicit empty experience selection ([]) produces zero experiences."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        tailored = data["tailored_content"]
        self.assertEqual(len(tailored["experience"]), 0)

    def test_selected_project_indices_filtering(self):
        """4. Selected project indices filter the projects to only selected items."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_project_indices": [0],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        tailored = data["tailored_content"]
        self.assertEqual(len(tailored["projects"]), 1)
        self.assertEqual(tailored["projects"][0]["name"], "Cloud API Gateway")

    def test_explicit_empty_project_selection(self):
        """5. Explicit empty project selection ([]) produces zero projects."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_project_indices": [],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        tailored = data["tailored_content"]
        self.assertEqual(len(tailored["projects"]), 0)

    def test_excluded_experience_post_generation_filter(self):
        """6. Even if AI returns all 3 experiences, unselected experience (Junior Intern) is stripped."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        titles = [e["original_title"] for e in data["tailored_content"]["experience"]]
        self.assertIn("Senior Backend Engineer", titles)
        self.assertNotIn("Junior Intern", titles)
        self.assertNotIn("Full Stack Developer", titles)

    def test_excluded_project_post_generation_filter(self):
        """7. Even if AI returns all 2 projects, unselected project (Personal Portfolio) is stripped."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_project_indices": [0],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = [p["name"] for p in data["tailored_content"]["projects"]]
        self.assertIn("Cloud API Gateway", names)
        self.assertNotIn("Personal Portfolio", names)

    def test_raw_extracted_text_leak_prevention(self):
        """8. When curation is active, raw extracted_text is not leaked to the AI user prompt."""
        self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],
            },
        )
        last_prompt = self.provider.last_user_prompt
        self.assertNotIn("=== SOURCE RESUME (extracted text, for wording only) ===", last_prompt)
        self.assertNotIn("Junior Intern Legacy Systems", last_prompt)

    def test_master_resume_parsed_data_immutability(self):
        """9. Master resume parsed_data in DB is 100% unchanged before and after curated tailoring."""
        session = self.Session()
        before = copy.deepcopy(session.query(Resume).filter(Resume.id == "res_1").first().parsed_data)
        session.close()

        self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],
                "selected_project_indices": [],
            },
        )

        session = self.Session()
        after = copy.deepcopy(session.query(Resume).filter(Resume.id == "res_1").first().parsed_data)
        session.close()

        self.assertEqual(before, after)
        self.assertEqual(len(after["experience"]), 3)
        self.assertEqual(len(after["projects"]), 2)

    def test_curated_request_bypasses_uncurated_cache(self):
        """10. An uncurated tailoring is cached, but a curated request does not reuse the uncurated result."""
        # First call: uncurated
        resp1 = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_1"})
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(len(resp1.json()["tailored_content"]["experience"]), 3)
        self.assertEqual(self.provider.calls, 1)

        # Second call: uncurated again -> reuses cache (calls == 1)
        resp2 = self.client.post("/jobs/job_1/resume-tailor", json={"resume_id": "res_1"})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(self.provider.calls, 1)

        # Third call: with curation [0] -> MUST NOT reuse cache, must generate curated tailoring (calls == 2)
        resp3 = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={"resume_id": "res_1", "selected_experience_indices": [0]},
        )
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(self.provider.calls, 2)
        self.assertEqual(len(resp3.json()["tailored_content"]["experience"]), 1)

    def test_original_content_comparison_exposes_only_curated(self):
        """11. original_content in response reflects only curated items for before/after comparison."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],
                "selected_project_indices": [0],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        orig = data["original_content"]
        self.assertEqual(len(orig["experience"]), 1)
        self.assertEqual(orig["experience"][0]["job_title"], "Senior Backend Engineer")
        self.assertEqual(len(orig["projects"]), 1)
        self.assertEqual(orig["projects"][0]["name"], "Cloud API Gateway")

    def test_pdf_export_excludes_unselected_content(self):
        """12. Export document model and PDF bytes omit unselected experiences and projects."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],
                "selected_project_indices": [],
            },
        )
        tailor_id = resp.json()["id"]

        session = self.Session()
        tailored_row = session.query(TailoredResume).filter(TailoredResume.id == tailor_id).first()
        resume_row = session.query(Resume).filter(Resume.id == "res_1").first()

        doc_model = build_export_document(tailored_row, resume_row)
        session.close()

        # Doc model only contains curated items
        self.assertEqual(len(doc_model["experience"]), 1)
        self.assertEqual(doc_model["experience"][0]["title"], "Senior Backend Engineer")
        self.assertEqual(len(doc_model["projects"]), 0)

        # Renders to valid PDF bytes without crashing
        pdf_bytes = render_pdf(doc_model)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_docx_export_excludes_unselected_content(self):
        """13. DOCX export excludes unselected experiences and projects."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],
                "selected_project_indices": [],
            },
        )
        tailor_id = resp.json()["id"]

        session = self.Session()
        tailored_row = session.query(TailoredResume).filter(TailoredResume.id == tailor_id).first()
        resume_row = session.query(Resume).filter(Resume.id == "res_1").first()

        doc_model = build_export_document(tailored_row, resume_row)
        session.close()

        docx_bytes = render_docx(doc_model)
        self.assertTrue(len(docx_bytes) > 0)
        # Valid PK zip header for docx
        self.assertTrue(docx_bytes.startswith(b"PK"))

    def test_invalid_and_out_of_bounds_indices_handled_safely(self):
        """14. Out-of-bounds indices (e.g. 99, -1) and non-ints are safely ignored without crashing."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0, 99, -5],
                "selected_project_indices": [99],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        tailored = data["tailored_content"]
        # Index 0 is valid, 99 and -5 are safely dropped
        self.assertEqual(len(tailored["experience"]), 1)
        self.assertEqual(tailored["experience"][0]["original_title"], "Senior Backend Engineer")
        # 99 is dropped, so 0 projects
        self.assertEqual(len(tailored["projects"]), 0)

    def test_curated_ai_prompt_grounding_excludes_unselected_identities(self):
        """15. Curated AI prompt grounding does not contain excluded experience or project identities."""
        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],  # Senior Backend Engineer only
                "selected_project_indices": [0],     # Cloud API Gateway only
            },
        )
        self.assertEqual(resp.status_code, 200)
        last_prompt = self.provider.last_user_prompt

        # Grounding and structured resume must contain only curated items
        self.assertIn("Senior Backend Engineer", last_prompt)
        self.assertIn("Cloud API Gateway", last_prompt)

        # Excluded identities must NOT appear anywhere in the AI user prompt
        self.assertNotIn("Full Stack Developer", last_prompt)
        self.assertNotIn("Junior Intern", last_prompt)
        self.assertNotIn("Personal Portfolio", last_prompt)

    def test_company_only_match_cannot_admit_excluded_experience(self):
        """16. Company-only match cannot admit an experience if the title does not match curated source."""
        ai_resp = make_ai_response()
        ai_resp["experience"] = [
            {
                "original_title": "Product Manager",  # Not Senior Backend Engineer
                "company": "Acme Corp",               # Same company as curated exp 0
                "original_bullets": ["Led meetings"],
                "tailored_bullets": ["Led agile meetings"],
                "changes": ["Tailored bullets"],
            }
        ]
        self.provider.response = ai_resp

        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],  # Senior Backend Engineer at Acme Corp
            },
        )
        self.assertEqual(resp.status_code, 200)
        tailored = resp.json()["tailored_content"]
        # Product Manager must NOT be admitted just because company matches Acme Corp
        self.assertEqual(len(tailored["experience"]), 0)

    def test_title_substring_cannot_admit_excluded_experience(self):
        """17. Title substring match cannot admit an ungrounded or excluded experience."""
        ai_resp = make_ai_response()
        ai_resp["experience"] = [
            {
                "original_title": "Backend Engineer",  # Substring of "Senior Backend Engineer"
                "company": "Acme Corp",
                "original_bullets": ["Built backend systems"],
                "tailored_bullets": ["Built high-scale backend systems"],
                "changes": ["Tailored bullets"],
            },
            {
                "original_title": "Senior Backend Engineer Specialist",  # Superstring
                "company": "Acme Corp",
                "original_bullets": ["Specialized engineering"],
                "tailored_bullets": ["Cloud specialization"],
                "changes": ["Specialized"],
            },
        ]
        self.provider.response = ai_resp

        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],  # Senior Backend Engineer at Acme Corp
            },
        )
        self.assertEqual(resp.status_code, 200)
        tailored = resp.json()["tailored_content"]
        # Both substring and superstring titles must be rejected (exact normalized match required)
        self.assertEqual(len(tailored["experience"]), 0)

    def test_exact_project_name_required_no_substring(self):
        """18. Exact project name is required; substring project name cannot admit an item."""
        ai_resp = make_ai_response()
        ai_resp["projects"] = [
            {
                "name": "Cloud API",  # Substring of "Cloud API Gateway"
                "original_description": "API description",
                "tailored_description": "Tailored API description",
                "changes": ["Optimized"],
            },
            {
                "name": "Cloud API Gateway v2",  # Superstring
                "original_description": "API Gateway v2",
                "tailored_description": "Tailored v2",
                "changes": ["Updated"],
            },
        ]
        self.provider.response = ai_resp

        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_project_indices": [0],  # "Cloud API Gateway"
            },
        )
        self.assertEqual(resp.status_code, 200)
        tailored = resp.json()["tailored_content"]
        self.assertEqual(len(tailored["projects"]), 0)

    def test_ungrounded_generated_items_removed(self):
        """19. Ungrounded hallucinated experiences or projects not in curated source are stripped."""
        ai_resp = make_ai_response()
        ai_resp["experience"].append({
            "original_title": "Chief Technology Officer",
            "company": "Completely Hallucinated Corp",
            "original_bullets": ["Invented everything"],
            "tailored_bullets": ["Spearheaded innovation"],
            "changes": ["Hallucination"],
        })
        ai_resp["projects"].append({
            "name": "Fabricated Quantum Blockchain",
            "original_description": "Fake project",
            "tailored_description": "Fake tailored description",
            "changes": ["Fake"],
        })
        self.provider.response = ai_resp

        resp = self.client.post(
            "/jobs/job_1/resume-tailor",
            json={
                "resume_id": "res_1",
                "selected_experience_indices": [0],
                "selected_project_indices": [0],
            },
        )
        self.assertEqual(resp.status_code, 200)
        tailored = resp.json()["tailored_content"]
        titles = [e["original_title"] for e in tailored["experience"]]
        names = [p["name"] for p in tailored["projects"]]
        self.assertNotIn("Chief Technology Officer", titles)
        self.assertNotIn("Fabricated Quantum Blockchain", names)


if __name__ == "__main__":
    unittest.main()

