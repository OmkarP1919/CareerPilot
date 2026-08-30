"""Tests for the Resume Export backend (Phase 3C).

These tests never call the real AI provider - export is verified against stored
structured content, and provider calls are asserted to never happen.
"""

import copy
import os
import re
import shutil
import tempfile
import unittest
from io import BytesIO
from unittest import mock

import pymupdf
from docx import Document
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
from app.services import resume_export
from app.api.resume_export import router as export_router

CONTACT_BASIC_INFO = {
    "name": "Alex Doe",
    "email": "alex@test.com",
    "phone": "+91 555 123 4567",
    "location": "Pune, India",
    "linkedin": "linkedin.com/in/alexdoe",
    "github": "https://github.com/alexdoe",
    "portfolio": "alexdev.me",
}

SOURCE_RESUME = {
    "basic_info": CONTACT_BASIC_INFO,
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "experience": [
        {
            "job_title": "Backend Developer",
            "company": "Acme Corp",
            "dates": "2020 - Present",
            "description": "Built REST APIs with Python, FastAPI and PostgreSQL.",
        }
    ],
    "projects": [
        {
            "name": "E-commerce Platform",
            "technologies": ["Python", "FastAPI"],
            "description": "Built REST APIs and a payment integration backend.",
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


def valid_structured_data():
    return {
        "summary": {
            "original": "Backend developer with API experience.",
            "tailored": "Backend Developer experienced in building REST APIs with Python, "
                        "FastAPI and PostgreSQL.",
        },
        "skills": {
            "kept": ["Python", "FastAPI", "PostgreSQL", "Docker"],
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
                "changes": [],
            }
        ],
        "projects": [
            {
                "name": "E-commerce Platform",
                "original_description": "Built REST APIs.",
                "tailored_description": "Built a payment-integration backend with Python and FastAPI.",
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


def pdf_text(content: bytes) -> str:
    doc = pymupdf.open(stream=content, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


def docx_text(content: bytes) -> str:
    doc = Document(BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)


class TestResumeExportService(unittest.TestCase):
    def setUp(self):
        class Tailored:
            structured_data = copy.deepcopy(valid_structured_data())
            tailored_content = {
                "summary": "Backend Developer experienced in building REST APIs with Python.",
                "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
            }

        class Resume:
            parsed_data = copy.deepcopy(SOURCE_RESUME)

        self.tailored = Tailored()
        self.resume = Resume()

        self.document = resume_export.build_export_document(self.tailored, self.resume)

    def test_pdf_generation_succeeds(self):
        content = resume_export.render_pdf(self.document)
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 1000)

    def test_docx_generation_succeeds(self):
        content = resume_export.render_docx(self.document)
        self.assertTrue(content.startswith(b"PK"))
        self.assertGreater(len(content), 4000)

    def test_pdf_contains_expected_text(self):
        content = resume_export.render_pdf(self.document)
        text = pdf_text(content)
        for probe in (
            "Alex Doe",
            "alex@test.com",
            "PROFESSIONAL SUMMARY",
            "SKILLS",
            "EXPERIENCE",
            "PROJECTS",
            "EDUCATION",
            "CERTIFICATIONS",
            "FastAPI",
            "Acme Corp",
            "AWS Certified",
        ):
            self.assertIn(probe, text)

    def test_docx_contains_expected_text(self):
        content = resume_export.render_docx(self.document)
        text = docx_text(content)
        for probe in (
            "Alex Doe",
            "alex@test.com",
            "+91 555 123 4567",
            "PROFESSIONAL SUMMARY",
            "SKILLS",
            "EXPERIENCE",
            "PROJECTS",
            "EDUCATION",
            "CERTIFICATIONS",
            "FastAPI",
            "Acme Corp",
            "AWS Certified",
        ):
            self.assertIn(probe, text)

    def test_pdf_and_docx_contain_equivalent_content(self):
        pdf = pdf_text(resume_export.render_pdf(self.document))
        docx = docx_text(resume_export.render_docx(self.document))
        for probe in ("alex@test.com", "FastAPI", "Acme Corp", "AWS Certified", "E-commerce Platform"):
            self.assertIn(probe, pdf)
            self.assertIn(probe, docx)

    def test_long_content_does_not_crash_and_multipages(self):
        data = copy.deepcopy(self.document)
        data["skills"] = [f"Skill {i}" for i in range(150)]
        data["experience"] = [
            {
                "title": f"Role {i}",
                "company": f"A really long company name that keeps going and going #{i}",
                "bullets": [
                    "Long bullet describing work with absolutely no truncation happening "
                    f"at all for entry {i} across many sentences and details.",
                ]
                * 6,
            }
            for i in range(12)
        ]
        data["contact"].extend(
            ["https://example.com/{0}/portfolio/very-long-{0}-url-with-many-parts".format(i) for i in range(4)]
        )

        pdf = resume_export.render_pdf(data)
        docx = resume_export.render_docx(data)
        self.assertTrue(pdf.startswith(b"%PDF"))
        doc = pymupdf.open(stream=pdf, filetype="pdf")
        self.assertGreater(doc.page_count, 1)
        self.assertIn("Skill 149", pdf_text(pdf))
        self.assertIn("Skill 149", docx_text(docx))

    def test_empty_optional_sections_omitted(self):
        data = copy.deepcopy(self.document)
        data["education"] = []
        data["certifications"] = []
        data["projects"] = []
        pdf = pdf_text(resume_export.render_pdf(data))
        docx = docx_text(resume_export.render_docx(data))
        for out in (pdf, docx):
            self.assertNotIn("EDUCATION", out)
            self.assertNotIn("CERTIFICATIONS", out)
            self.assertNotIn("PROJECTS", out)
        self.assertIn("SKILLS", pdf)
        self.assertIn("EXPERIENCE", pdf)

    def test_contact_information_sourced_from_resume(self):
        text = pdf_text(resume_export.render_pdf(self.document))
        for probe in ("alex@test.com", "+91 555 123 4567", "Pune, India", "linkedin.com/in/alexdoe",
                      "https://github.com/alexdoe", "https://alexdev.me"):
            self.assertIn(probe, text)

    def test_original_resume_unchanged(self):
        original = copy.deepcopy(SOURCE_RESUME)
        resume_export.render_pdf(self.document)
        resume_export.render_docx(self.document)
        self.assertEqual(self.resume.parsed_data, original)

    def test_tailored_resume_unchanged(self):
        original = copy.deepcopy(valid_structured_data())
        resume_export.render_pdf(self.document)
        resume_export.render_docx(self.document)
        self.assertEqual(self.tailored.structured_data, original)

    def test_no_contact_never_invented(self):
        class BareResume:
            parsed_data = {"skills": ["Python"]}

        data = resume_export.build_export_document(self.tailored, BareResume())
        self.assertEqual(data["contact"], [])
        self.assertEqual(data["name"], "")

    def test_unsafe_filenames_sanitized(self):
        self.assertEqual(resume_export.sanitize_filename_component("../../Backend::Dev//"), "Backend_Dev")
        name = resume_export.build_export_filename("Backend Developer", "Acme, Inc.", "pdf")
        self.assertRegex(name, r"^CareerPilot_Backend_Developer_Acme_Inc\.pdf$")
        for char_s in ("../", ":", "/", "\\", " "):
            self.assertNotIn(char_s, name)

    def test_filename_fallback_when_no_job(self):
        name = resume_export.build_export_filename(None, None, "docx")
        self.assertEqual(name, "CareerPilot_Tailored_Resume.docx")
        self.assertNotIn("/", name)

    def test_no_ai_provider_called_during_export(self):
        with mock.patch(
            "app.services.ai_provider.openai_provider.OpenAIProvider.generate_structured",
            side_effect=AssertionError("AI must not be called during export"),
        ):
            resume_export.render_pdf(self.document)
            resume_export.render_docx(self.document)


class ResumeExportAPITestBase(unittest.TestCase):
    """Shared API fixture: a user, their resume/job/tailoring, and a second user."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "export.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        db.add_all([
            User(id="user_a", firebase_uid="fb_a", email="a@test.com", name="A"),
            User(id="user_b", firebase_uid="fb_b", email="b@test.com", name="B"),
        ])
        self.job = Job(id="job_1", user_id="user_a", title="Backend Developer",
                       company="Acme", description="Python, FastAPI, PostgreSQL.",
                       required_skills="Python, FastAPI")
        # A's resume is the ONLY one with contact info.
        self.resume_a = Resume(
            id="res_a", user_id="user_a", filename="a.pdf",
            original_filename="a.pdf", file_path="/tmp/a.pdf", file_size="1",
            parsing_status="completed", parsed_data=copy.deepcopy(SOURCE_RESUME),
            extracted_text="Backend Developer Acme 2020 Present.",
        )
        self.resume_b = Resume(
            id="res_b", user_id="user_b", filename="b.pdf",
            original_filename="b.pdf", file_path="/tmp/b.pdf", file_size="1",
            parsing_status="completed", parsed_data={"skills": ["React"]},
        )
        self.tailoring_a = TailoredResume(
            id="tail_a", user_id="user_a", source_resume_id="res_a", job_id="job_1",
            version_name="tailored", tailored_content={},
            structured_data=copy.deepcopy(valid_structured_data()),
        )
        self.tailoring_b = TailoredResume(
            id="tail_b", user_id="user_b", source_resume_id="res_b", job_id="job_1",
            version_name="tailored", tailored_content={},
            structured_data=copy.deepcopy(valid_structured_data()),
        )
        db.add_all([self.job, self.resume_a, self.resume_b, self.tailoring_a, self.tailoring_b])
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(export_router)
        self.current_user_id = "user_a"

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

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestResumeExportAPI(ResumeExportAPITestBase):
    def test_pdf_endpoint_returns_valid_pdf(self):
        resp = self.client.get("/resumes/tailored/tail_a/export/pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))
        disposition = resp.headers["content-disposition"]
        self.assertIn(".pdf", disposition)
        self.assertIn("Backend_Developer", disposition)

    def test_docx_endpoint_returns_valid_docx(self):
        resp = self.client.get("/resumes/tailored/tail_a/export/docx")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertTrue(resp.content.startswith(b"PK"))
        disposition = resp.headers["content-disposition"]
        self.assertIn(".docx", disposition)

    def test_missing_tailored_404(self):
        resp = self.client.get("/resumes/tailored/nope/export/pdf")
        self.assertEqual(resp.status_code, 404)

    def test_user_b_cannot_export_user_a(self):
        # A's tailored resume must be unreachable for B via BOTH formats.
        self.current_user_id = "user_b"
        for fmt in ("pdf", "docx"):
            resp = self.client.get(f"/resumes/tailored/tail_a/export/{fmt}")
            self.assertEqual(resp.status_code, 404)

    def test_user_a_can_export_own_resume_only(self):
        resp = self.client.get("/resumes/tailored/tail_a/export/pdf")
        self.assertEqual(resp.status_code, 200)
        # A cannot reach B's tailoring either.
        resp = self.client.get("/resumes/tailored/tail_b/export/pdf")
        self.assertEqual(resp.status_code, 404)

    def test_exported_pdf_contains_users_contact(self):
        resp = self.client.get("/resumes/tailored/tail_a/export/pdf")
        text = pdf_text(resp.content)
        self.assertIn("Alex Doe", text)
        self.assertIn("alex@test.com", text)
        self.assertIn("linkedin.com/in/alexdoe", text)

    def test_no_ai_called_during_api_export(self):
        with mock.patch(
            "app.services.ai_provider.openai_provider.OpenAIProvider.generate_structured",
            side_effect=AssertionError("AI must not be called during export"),
        ):
            for fmt in ("pdf", "docx"):
                resp = self.client.get(f"/resumes/tailored/tail_a/export/{fmt}")
                self.assertEqual(resp.status_code, 200)

    def test_tailored_resume_unchanged_after_api_export(self):
        db = self.Session()
        before = copy.deepcopy(
            db.query(TailoredResume).filter(TailoredResume.id == "tail_a").first().structured_data
        )
        db.close()
        self.client.get("/resumes/tailored/tail_a/export/pdf")
        self.client.get("/resumes/tailored/tail_a/export/docx")
        db = self.Session()
        after = db.query(TailoredResume).filter(TailoredResume.id == "tail_a").first().structured_data
        db.close()
        self.assertEqual(before, after)

    def test_filename_never_contains_path_traversal(self):
        db = self.Session()
        job = db.query(Job).filter(Job.id == "job_1").first()
        job.title = "../../ Etc/Passwd"
        job.company = "Acme: Inc"
        db.commit()
        db.close()
        resp = self.client.get("/resumes/tailored/tail_a/export/pdf")
        disposition = resp.headers["content-disposition"]
        filename = re.search(r'filename="([^"]+)"', disposition).group(1)
        self.assertNotIn("/", filename)
        self.assertNotIn("..", filename)
        self.assertTrue(filename.endswith(".pdf"))


if __name__ == "__main__":
    unittest.main()