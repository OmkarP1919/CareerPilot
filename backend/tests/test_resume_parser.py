import os
import shutil
import tempfile
import unittest

import pymupdf
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.resume import Resume
from app.api.resumes import router as resumes_router
from app.services.resume_parser import (
    extract_pdf_text,
    parse_resume,
    parse_and_store,
    match_skill,
    _ScannedPdfError,
    SCANNED_PDF_ERROR,
)

TEXT_RESUME = """\
John Doe
john.doe@example.com | +1 555-123-4567 | San Francisco, CA
linkedin.com/in/johndoe | github.com/johndoe

SUMMARY
Full Stack Developer with 5 years of experience building web applications.

SKILLS
Python, FastAPI, React, TypeScript, PostgreSQL, Docker, AWS, Git, Python

EXPERIENCE

Senior Software Engineer, Acme Corp - 2020 - Present
- Built microservices with Python and FastAPI

Backend Developer, Tech Inc | 2018 - 2020
- Designed REST APIs with PostgreSQL

EDUCATION

B.Tech in Computer Science, Example University, 2016 - 2020

PROJECTS

E-commerce Platform
Python, Django, PostgreSQL
Full stack e-commerce with payment integration.

CERTIFICATIONS
AWS Certified Solutions Architect, Certified Scrum Master
"""


def _write_text_pdf(path: str) -> str:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox((72, 72, 500, 760), TEXT_RESUME, fontsize=10)
    doc.save(path)
    doc.close()
    return path


def _write_scanned_pdf(path: str) -> str:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200))
    pix.clear_with(200)
    doc = pymupdf.open()
    page = doc.new_page(width=200, height=200)
    page.insert_image(pymupdf.Rect(0, 0, 200, 200), pixmap=pix)
    doc.save(path)
    doc.close()
    return path


def _write_empty_pdf(path: str) -> str:
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    return path


class TestPdfTextExtraction(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_valid_text_pdf_extraction(self):
        pdf = _write_text_pdf(os.path.join(self.tmpdir, "resume.pdf"))
        text = extract_pdf_text(pdf)
        self.assertIn("John Doe", text)
        self.assertIn("john.doe@example.com", text)
        # Normalized whitespace: no double spaces
        self.assertNotIn("  ", text)

    def test_scanned_pdf_raises_clean_error(self):
        pdf = _write_scanned_pdf(os.path.join(self.tmpdir, "scanned.pdf"))
        with self.assertRaises(_ScannedPdfError) as ctx:
            extract_pdf_text(pdf)
        self.assertIn("image-based", str(ctx.exception))
        self.assertIn("scanned", str(ctx.exception).lower())

    def test_empty_pdf_raises_clean_error(self):
        pdf = _write_empty_pdf(os.path.join(self.tmpdir, "empty.pdf"))
        with self.assertRaises(_ScannedPdfError):
            extract_pdf_text(pdf)

    def test_non_pdf_rejected(self):
        path = os.path.join(self.tmpdir, "notes.txt")
        with open(path, "w") as f:
            f.write("hello world")
        with self.assertRaises(ValueError):
            extract_pdf_text(path)


class TestSkillExtraction(unittest.TestCase):
    def test_skill_deduplication_and_matching(self):
        parsed = parse_resume(TEXT_RESUME)
        skills = parsed.to_dict()["skills"]
        # Python appears twice in the SKILLS line -> must be deduplicated.
        self.assertEqual(len(skills), len(set(skills)))
        self.assertIn("Python", skills)
        self.assertIn("FastAPI", skills)
        self.assertIn("React", skills)
        self.assertIn("PostgreSQL", skills)
        self.assertIn("AWS", skills)

    def test_match_skill_case_insensitive(self):
        for token in ["python", "PYTHON", "Python", "fastAPI", "tailwind css"]:
            self.assertIsNotNone(match_skill(token))
        self.assertIsNone(match_skill("not-a-real-skill-xyz"))


class TestStructuredExtraction(unittest.TestCase):
    def test_structured_output_validity_and_content(self):
        parsed = parse_resume(TEXT_RESUME)
        data = parsed.to_dict()

        # Valid top-level structure.
        self.assertEqual(set(data.keys()), {
            "basic_info", "skills", "education", "experience", "projects", "certifications",
        })
        self.assertIsInstance(data["skills"], list)
        self.assertIsInstance(data["education"], list)
        self.assertIsInstance(data["experience"], list)
        self.assertIsInstance(data["projects"], list)
        self.assertIsInstance(data["certifications"], list)

        # Basic info.
        self.assertEqual(data["basic_info"]["name"], "John Doe")
        self.assertEqual(data["basic_info"]["email"], "john.doe@example.com")
        self.assertIn("San Francisco", data["basic_info"].get("location", "") or "")
        self.assertIn("linkedin.com", data["basic_info"].get("linkedin", "") or "")

        # Education.
        self.assertTrue(data["education"])
        edu = data["education"][0]
        self.assertIn("B.Tech", edu.get("degree", ""))
        self.assertIn("Example University", edu.get("institution", ""))
        self.assertIn("Computer Science", edu.get("field_of_study", ""))

        # Experience.
        self.assertEqual(len(data["experience"]), 2)
        self.assertEqual(data["experience"][0]["job_title"], "Senior Software Engineer")
        self.assertEqual(data["experience"][0]["company"], "Acme Corp")
        self.assertEqual(data["experience"][1]["job_title"], "Backend Developer")
        self.assertEqual(data["experience"][1]["company"], "Tech Inc")

        # Projects.
        self.assertTrue(data["projects"])
        proj = data["projects"][0]
        self.assertIn("E-commerce", proj.get("name", ""))
        self.assertIn("Django", proj.get("technologies", []))

        # Certifications.
        self.assertTrue(data["certifications"])
        joined = " ".join(data["certifications"])
        self.assertIn("AWS", joined)
        self.assertIn("Scrum", joined)

    def test_empty_text_returns_empty_structures(self):
        parsed = parse_resume("")
        data = parsed.to_dict()
        self.assertEqual(data["basic_info"], {})
        self.assertEqual(data["skills"], [])
        self.assertEqual(data["education"], [])
        self.assertEqual(data["experience"], [])
        self.assertEqual(data["projects"], [])
        self.assertEqual(data["certifications"], [])

    def test_no_fabrication_when_unknown_text(self):
        parsed = parse_resume("Totally unrelated text with no resume fields whatsoever.")
        data = parsed.to_dict()
        self.assertEqual(data["skills"], [])
        self.assertEqual(data["education"], [])
        self.assertEqual(data["experience"], [])


class TestParseAndStore(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.tmpdir = tempfile.mkdtemp()
        user = User(id="user_a", firebase_uid="fb_a", email="a@test.com", name="User A")
        self.db.add(user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_resume(self, resume_id, file_path):
        resume = Resume(
            id=resume_id, user_id="user_a", filename=f"{resume_id}.pdf",
            original_filename=f"{resume_id}.pdf", file_path=file_path, file_size="100",
        )
        self.db.add(resume)
        self.db.commit()
        return resume

    def test_parse_success_stores_structured_data(self):
        pdf = _write_text_pdf(os.path.join(self.tmpdir, "ok.pdf"))
        resume = self._make_resume("r_ok", pdf)
        parse_and_store(self.db, resume)
        self.db.refresh(resume)
        self.assertEqual(resume.parsing_status, "completed")
        self.assertIsNone(resume.parsing_error)
        self.assertIsNotNone(resume.parsed_data)
        self.assertIn("John Doe", resume.extracted_text)
        self.assertIn("email", resume.parsed_data["basic_info"])
        self.assertIsNotNone(resume.parsed_at)
        # Original file must remain untouched.
        self.assertTrue(os.path.exists(pdf))

    def test_scanned_pdf_parsing_does_not_delete_resume(self):
        pdf = _write_scanned_pdf(os.path.join(self.tmpdir, "scanned.pdf"))
        resume = self._make_resume("r_scanned", pdf)
        parse_and_store(self.db, resume)
        self.db.refresh(resume)
        self.assertEqual(resume.parsing_status, "completed")
        self.assertIn("image-based", resume.parsing_error)
        self.assertIsNone(resume.parsed_data)
        # Resume record and file still exist.
        self.assertIsNotNone(self.db.query(Resume).filter(Resume.id == "r_scanned").first())
        self.assertTrue(os.path.exists(pdf))

    def test_failed_parsing_does_not_delete_resume(self):
        # A non-existent/non-PDF file path -> extraction fails but resume survives.
        resume = self._make_resume("r_fail", os.path.join(self.tmpdir, "missing.pdf"))
        parse_and_store(self.db, resume)
        self.db.refresh(resume)
        self.assertEqual(resume.parsing_status, "failed")
        self.assertIsNotNone(resume.parsing_error)
        # Resume record not deleted.
        self.assertIsNotNone(self.db.query(Resume).filter(Resume.id == "r_fail").first())

    def test_empty_pdf_sets_completed_with_scanned_message(self):
        pdf = _write_empty_pdf(os.path.join(self.tmpdir, "empty.pdf"))
        resume = self._make_resume("r_empty", pdf)
        parse_and_store(self.db, resume)
        self.db.refresh(resume)
        self.assertEqual(resume.parsing_status, "completed")
        self.assertEqual(resume.parsing_error, SCANNED_PDF_ERROR)


class TestUserAuthorizationIsolation(unittest.TestCase):
    """Verify that parsed data is only accessible to the owning user."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.user_a = User(id="user_a", firebase_uid="fb_a", email="a@test.com", name="A")
        self.user_b = User(id="user_b", firebase_uid="fb_b", email="b@test.com", name="B")
        self.db.add_all([self.user_a, self.user_b])

        self.resume_a = Resume(
            id="res_a", user_id="user_a", filename="a.pdf", original_filename="a.pdf",
            file_path="/tmp/a.pdf", file_size="1", parsing_status="completed",
            parsed_data={"skills": ["A"]},
        )
        self.resume_b = Resume(
            id="res_b", user_id="user_b", filename="b.pdf", original_filename="b.pdf",
            file_path="/tmp/b.pdf", file_size="1", parsing_status="completed",
            parsed_data={"skills": ["B"]},
        )
        self.db.add_all([self.resume_a, self.resume_b])
        self.db.commit()

    def _own_resume(self, resume_id, user_id):
        # Mirrors the filter used by the API (_get_own_resume).
        return (
            self.db.query(Resume)
            .filter(Resume.id == resume_id, Resume.user_id == user_id)
            .first()
        )

    def test_user_cannot_access_other_users_parsed_resume(self):
        # User A asks for User B's resume -> None (would be 404 in the API).
        self.assertIsNone(self._own_resume("res_b", "user_a"))
        # User A has access to their own.
        found = self._own_resume("res_a", "user_a")
        self.assertIsNotNone(found)
        self.assertEqual(found.parsed_data, {"skills": ["A"]})

    def test_list_isolation(self):
        a_resumes = self.db.query(Resume).filter(Resume.user_id == "user_a").all()
        ids = {r.id for r in a_resumes}
        self.assertEqual(ids, {"res_a"})
        self.assertNotIn("res_b", ids)


class TestResumeApiEndpoints(unittest.TestCase):
    """Integration tests for the /resumes parsed endpoints using TestClient."""

    USER_A = {"id": "api_user_a", "firebase_uid": "fb_a"}
    USER_B = {"id": "api_user_b", "firebase_uid": "fb_b"}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(self.tmpdir, "api.db")
        self.engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Seed two users.
        db = self.Session()
        db.add_all([
            User(id=self.USER_A["id"], firebase_uid=self.USER_A["firebase_uid"], email="a@test.com", name="A"),
            User(id=self.USER_B["id"], firebase_uid=self.USER_B["firebase_uid"], email="b@test.com", name="B"),
        ])
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(resumes_router)

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

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_upload_parses_and_retrieve_parsed(self):
        pdf = _write_text_pdf(os.path.join(self.tmpdir, "resume.pdf"))
        with open(pdf, "rb") as f:
            resp = self.client.post("/resumes", files={"file": ("resume.pdf", f, "application/pdf")})
        self.assertEqual(resp.status_code, 201)
        resume = resp.json()
        self.assertEqual(resume["parsing_status"], "completed")

        rid = resume["id"]
        parsed_resp = self.client.get(f"/resumes/{rid}/parsed")
        self.assertEqual(parsed_resp.status_code, 200)
        body = parsed_resp.json()
        self.assertEqual(body["resume_id"], rid)
        self.assertEqual(body["parsing_status"], "completed")
        self.assertIn("John Doe", body["data"]["basic_info"].get("name", ""))
        self.assertIn("Python", body["data"]["skills"])

    def test_reparse_endpoint(self):
        pdf = _write_text_pdf(os.path.join(self.tmpdir, "resume.pdf"))
        with open(pdf, "rb") as f:
            resp = self.client.post("/resumes", files={"file": ("resume.pdf", f, "application/pdf")})
        rid = resp.json()["id"]

        reparse = self.client.post(f"/resumes/{rid}/parse")
        self.assertEqual(reparse.status_code, 200)
        body = reparse.json()
        self.assertEqual(body["parsing_status"], "completed")
        self.assertIn("FastAPI", body["data"]["skills"])

    def test_parsed_data_authorization_isolation(self):
        """User A's parsed data must be hidden from User B."""
        pdf = _write_text_pdf(os.path.join(self.tmpdir, "resume.pdf"))
        with open(pdf, "rb") as f:
            resp = self.client.post("/resumes", files={"file": ("resume.pdf", f, "application/pdf")})
        rid = resp.json()["id"]
        self.assertEqual(resp.status_code, 201)

        # Switch to User B.
        self.current_user_id = self.USER_B["id"]

        list_b = self.client.get("/resumes").json()
        self.assertNotIn(rid, [r["id"] for r in list_b])

        get_b = self.client.get(f"/resumes/{rid}/parsed")
        self.assertEqual(get_b.status_code, 404)

        reparse_b = self.client.post(f"/resumes/{rid}/parse")
        self.assertEqual(reparse_b.status_code, 404)

    def test_upload_does_not_fail_on_scanned_pdf(self):
        # A scanned PDF uploads fine and reports a clean parsing message without
        # erroring the upload request.
        pdf = _write_scanned_pdf(os.path.join(self.tmpdir, "scanned.pdf"))
        with open(pdf, "rb") as f:
            resp = self.client.post("/resumes", files={"file": ("scanned.pdf", f, "application/pdf")})
        self.assertEqual(resp.status_code, 201)
        resume = resp.json()
        self.assertEqual(resume["parsing_status"], "completed")
        self.assertIn("image-based", resume["parsing_error"])

        # The resume itself is retained and retrievable.
        rid = resume["id"]
        parsed = self.client.get(f"/resumes/{rid}/parsed").json()
        self.assertIn("scanned", parsed["parsing_error"].lower())


class TestAlternativeSectionHeadings(unittest.TestCase):
    """Parser must recognise the common alternate spellings/appearance of
    resume section headings (case-insensitive, whitespace-tolerant)."""

    def test_common_heading_variants(self):
        text = """\
Jane Roe
EDUCATION
B.Sc. Computer Science, City University

KEY PROJECTS

Chat Analytics Dashboard
React, Python
A dashboard that aggregates chat metrics.

SKILLS & TECHNOLOGIES
React, Python, Docker

EMPLOYMENT HISTORY

Software Engineer, Big Co - 2020 - Present
- Built the dashboards.

COURSES & CERTIFICATIONS
AWS Certified Solutions Architect
"""
        data = parse_resume(text).to_dict()
        self.assertIn("Python", data["skills"])
        self.assertIn("React", data["skills"])
        self.assertIn("Docker", data["skills"])
        self.assertEqual(len(data["experience"]), 1)
        self.assertEqual(data["experience"][0]["job_title"], "Software Engineer")
        self.assertIn("Big Co", data["experience"][0].get("company", ""))
        self.assertEqual(data["projects"][0]["name"], "Chat Analytics Dashboard")
        self.assertIn("Python", data["projects"][0]["technologies"])
        self.assertTrue(data["education"])
        self.assertIn("B.Sc.", data["education"][0].get("degree", ""))
        self.assertTrue(data["certifications"])
        self.assertIn("AWS", " ".join(data["certifications"]))

    def test_case_insensitive_and_extra_whitespace(self):
        text = """\
EDUCATION
B.Tech Computer Science, State University

work   experience

Backend Developer | Corp Ltd | 2019 - Now
- Built APIs.
"""
        parse_resume(text)  # must not raise on arbitrary casing/spacing
        data = parse_resume(text).to_dict()
        self.assertEqual(len(data["experience"]), 1)
        self.assertEqual(data["experience"][0]["job_title"], "Backend Developer")

    def test_heading_with_trailing_separator_decorations(self):
        text = """\
SKILLS -------
JavaScript, Java

EXPERIENCE .....
QA Engineer, Test Co | 2021 - Present
- Wrote automated tests.
"""
        data = parse_resume(text).to_dict()
        self.assertIn("JavaScript", data["skills"])
        self.assertEqual(data["experience"][0]["job_title"], "QA Engineer")

    def test_inline_colon_section_headers(self):
        """Condensed/two-column layouts: 'Skills: Python, FastAPI'."""
        text = """\
Avery Lee
Skills: Python, FastAPI, Git
EXPERIENCE: Backend Developer at Tech Corp 2021 - Present
- Built REST services.
PROJECTS: Resume Builder (React)
"""
        data = parse_resume(text).to_dict()
        self.assertIn("Python", data["skills"])
        self.assertIn("FastAPI", data["skills"])
        self.assertEqual(len(data["experience"]), 1)
        self.assertEqual(data["experience"][0]["job_title"], "Backend Developer")
        self.assertIn("Tech Corp", data["experience"][0].get("company", ""))

    def test_non_header_lines_do_not_start_sections(self):
        text = """\
Professional Summary
Skills that I love using every day: Python and teamwork.
A line that simply mentions 'Projects: gone wild' should not count.
"""
        data = parse_resume(text).to_dict()
        self.assertEqual(data["skills"], [])
        self.assertEqual(data["projects"], [])


class TestProjectChunking(unittest.TestCase):
    """Regression: PDF text extraction can lose blank-line separation; two
    back-to-back projects must still be split into two entries."""

    def test_projects_split_without_blank_lines(self):
        text = """\
PROJECTS
Store Analytics App
Python, Pandas
Real-time store analytics.
Portfolio Site
React, Tailwind CSS
A personal portfolio with a blog.
"""
        data = parse_resume(text).to_dict()
        names = [p.get("name") for p in data["projects"]]
        self.assertEqual(names, ["Store Analytics App", "Portfolio Site"])
        self.assertIn("Pandas", data["projects"][0].get("technologies", []))
        self.assertIn("React", data["projects"][1].get("technologies", []))


class TestResumeApiContractRegression(unittest.TestCase):
    """Regression for the reported bug: 'Parsed successfully' with
    '0 skills • 0 projects • 0 experiences' even though the resume contains
    real content. The list endpoint must expose parsed_data so the UI can show
    real counts, and /parsed must nest the data under `data`."""

    def setUp(self):
        self.view = ("tmpdir", tempfile.mkdtemp())
        self.tmpdir = self.view[1]
        db_path = os.path.join(self.tmpdir, "api.db")
        self.engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        db = self.Session()
        db.add(User(id="reg_a", firebase_uid="fb_reg_a", email="a@test.com", name="A"))
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(resumes_router)

        def override_get_db():
            s = self.Session()
            try:
                yield s
            finally:
                s.close()

        def override_get_current_user():
            s = self.Session()
            try:
                return s.query(User).filter(User.id == "reg_a").first()
            finally:
                s.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(self.app)

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _upload_resume(self):
        # A resume without a dedicated SKILLS heading relies on recognition of
        # the 'Skills & Technologies' variant to surface its skills.
        body = """\
Sam Rivera
sam@example.com | +1 555-010-0200 | Chicago, IL

Skills & Technologies
Python, FastAPI, TypeScript, Docker

Work Experience

Senior Backend Engineer, Northwind Labs | 2020 - Present
- Built payment APIs with FastAPI.

Projects

E-Commerce Store
Python, Django
A storefront with checkout.

EDUCATION
B.Tech Computer Science, Midwest Institute, 2016 - 2020
"""
        pdf = os.path.join(self.tmpdir, "resume.pdf")
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_textbox((72, 72, 500, 760), body, fontsize=10)
        doc.save(pdf)
        doc.close()
        with open(pdf, "rb") as f:
            resp = self.client.post("/resumes", files={"file": ("resume.pdf", f, "application/pdf")})
        self.assertEqual(resp.status_code, 201)
        return resp.json(), pdf

    def test_list_returns_parsed_data_for_card_counts(self):
        """The reported bug: the resume card read counts from r.parsed_data,
        but the list endpoint never returned parsed_data -> always 0."""
        resume, _ = self._upload_resume()
        self.assertEqual(resume["parsing_status"], "completed")

        listing = self.client.get("/resumes").json()
        self.assertEqual(len(listing), 1)
        item = listing[0]
        self.assertIn("parsed_data", item, "ResumeResponse must expose parsed_data")
        parsed = item["parsed_data"] or {}
        self.assertGreaterEqual(len(parsed.get("skills", [])), 1)
        self.assertGreaterEqual(len(parsed.get("experience", [])), 1)
        self.assertGreaterEqual(len(parsed.get("projects", [])), 1)
        # The UI computes: skills/projects/experiences counts from these fields.
        self.assertEqual(len(parsed["skills"]), 4)
        self.assertEqual(len(parsed["experience"]), 1)
        self.assertEqual(len(parsed["projects"]), 1)

    def test_parsed_endpoint_nests_structured_data_under_data(self):
        """Frontend Insights reads `data.*`; verify the documented contract."""
        resume, _ = self._upload_resume()
        body = self.client.get(f"/resumes/{resume['id']}/parsed").json()
        self.assertEqual(body["parsing_status"], "completed")
        self.assertIn("data", body)
        self.assertIn("Python", body["data"]["skills"])
        self.assertEqual(len(body["data"]["experience"]), 1)
        self.assertEqual(len(body["data"]["projects"]), 1)


if __name__ == "__main__":
    unittest.main()
