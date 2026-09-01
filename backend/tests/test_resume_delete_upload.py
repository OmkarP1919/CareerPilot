"""Regression tests for the Resume workflow reliability fixes:

BUG 1 - Resume DELETE must not fail with a PostgreSQL ForeignKeyViolation.
        Dependent records derived from the resume (ResumeJobAnalysis,
        TailoredResume, CoverLetter) are removed via ORM cascade, atomically.

BUG 2 - Resume upload must be reached at the real POST /resumes endpoint.
        The frontend previously called the non-existent POST /resumes/upload,
        which FastAPI answered with 405 Method Not Allowed.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import pymupdf
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, String, ForeignKey, create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.resume_job_analysis import ResumeJobAnalysis
from app.models.tailored_resume import TailoredResume
from app.models.cover_letter import CoverLetter
from app.api.resumes import router as resumes_router

USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
USER_B = {"id": "user_b", "firebase_uid": "fb_b"}


class ExtraDependent(Base):
    """Test-only table that also FK-references resumes.id but is NOT covered by
    the ORM cascade. Used to prove a genuine dependent-cleanup failure rolls
    the whole delete transaction back."""

    __tablename__ = "extra_dependents"

    id = Column(String, primary_key=True)
    resume_id = Column(String, ForeignKey("resumes.id"), nullable=False)


class _ResumeDeleteUploadApp:
    """Shared FastAPI app harness with per-engine SQLite and auth overrides."""

    def __init__(self, enforce_fk=False):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "rt.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        if enforce_fk:

            @event.listens_for(self.engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
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
        self.app.include_router(resumes_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        self.current_user_id = USER_A["id"]

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
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed(self, **columns):
        """Create a resume row for user A with a real backing file.

        Returns (resume_id, file_path) as plain values so callers never touch
        a session-detached ORM object."""
        resume_id = columns.get("id", "res_a")
        file_path = os.path.join(self.tmpdir, columns.get("filename", "resume.pdf"))
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4 test")
        resume = Resume(
            id=resume_id,
            user_id=USER_A["id"],
            filename=columns.get("filename", "resume.pdf"),
            original_filename="resume.pdf",
            file_path=file_path,
            file_size=str(os.path.getsize(file_path)),
            is_master=False,
            parsing_status="completed",
        )
        db = self.Session()
        db.add(resume)
        db.commit()
        db.close()
        return resume_id, file_path

    def _seed_unrelated(self):
        """Shared/global records that must survive a resume delete."""
        db = self.Session()
        job = Job(id="job_1", user_id=USER_A["id"], title="Backend Developer",
                  company="Acme", description="Python FastAPI", required_skills="Python")
        db.add(job)
        db.commit()
        db.close()
        return job


def _write_text_pdf(path: str) -> str:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_textbox(
        (72, 72, 500, 760),
        "John Doe\nEmail: j@d.com\nSKILLS\nPython, FastAPI\n",
        fontsize=10,
    )
    doc.save(path)
    doc.close()
    return path


class TestResumeDeleteCascade(unittest.TestCase):
    """DELETE /resumes/{id} removes the resume and its derived records."""

    def setUp(self):
        self.h = _ResumeDeleteUploadApp()

    def tearDown(self):
        self.h.close()

    def _seed_dependent(self, kind):
        self.h._seed_unrelated()
        db = self.h.Session()
        if kind == "analysis":
            row = ResumeJobAnalysis(
                id="dep_1", user_id=USER_A["id"], resume_id="res_a",
                job_id="job_1", overall_score=85,
            )
        elif kind == "tailored":
            row = TailoredResume(
                id="dep_1", user_id=USER_A["id"], source_resume_id="res_a",
                job_id="job_1", version_name="tailored",
            )
        else:
            row = CoverLetter(
                id="dep_1", user_id=USER_A["id"], source_resume_id="res_a",
                job_id="job_1", version_name="cover-letter",
            )
        db.add(row)
        db.commit()
        db.close()

    def _assert_dependent_gone(self, kind):
        db = self.h.Session()
        try:
            if kind == "analysis":
                n = db.query(ResumeJobAnalysis).filter(ResumeJobAnalysis.id == "dep_1").count()
            elif kind == "tailored":
                n = db.query(TailoredResume).filter(TailoredResume.id == "dep_1").count()
            else:
                n = db.query(CoverLetter).filter(CoverLetter.id == "dep_1").count()
        finally:
            db.close()
        self.assertEqual(n, 0)

    def test_delete_no_dependencies(self):
        resume_id, _ = self.h._seed()
        resp = self.h.client.delete(f"/resumes/{resume_id}")
        self.assertEqual(resp.status_code, 204)
        db = self.h.Session()
        try:
            self.assertIsNone(db.query(Resume).filter(Resume.id == resume_id).first())
        finally:
            db.close()

    def test_delete_with_resume_job_analysis(self):
        self.h._seed()
        self._seed_dependent("analysis")
        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)
        self._assert_dependent_gone("analysis")
        # The job itself is a shared/global entity and must remain.
        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(Job).filter(Job.id == "job_1").first())
        finally:
            db.close()

    def test_delete_with_tailored_resume(self):
        self.h._seed()
        self._seed_dependent("tailored")
        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)
        self._assert_dependent_gone("tailored")
        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(Job).filter(Job.id == "job_1").first())
        finally:
            db.close()

    def test_delete_with_cover_letter(self):
        self.h._seed()
        self._seed_dependent("cover")
        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)
        self._assert_dependent_gone("cover")
        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(Job).filter(Job.id == "job_1").first())
        finally:
            db.close()

    def test_delete_with_all_dependents_removes_all(self):
        self.h._seed()
        self.h._seed_unrelated()
        db = self.h.Session()
        db.add_all([
            ResumeJobAnalysis(id="dep_a", user_id=USER_A["id"], resume_id="res_a",
                              job_id="job_1", overall_score=90),
            TailoredResume(id="dep_t", user_id=USER_A["id"], source_resume_id="res_a",
                           job_id="job_1", version_name="tailored"),
            CoverLetter(id="dep_c", user_id=USER_A["id"], source_resume_id="res_a",
                        job_id="job_1", version_name="cover-letter"),
        ])
        db.commit()
        db.close()

        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)

        db = self.h.Session()
        try:
            self.assertIsNone(db.query(Resume).filter(Resume.id == "res_a").first())
            self.assertEqual(db.query(ResumeJobAnalysis).filter(ResumeJobAnalysis.resume_id == "res_a").count(), 0)
            self.assertEqual(db.query(TailoredResume).filter(TailoredResume.source_resume_id == "res_a").count(), 0)
            self.assertEqual(db.query(CoverLetter).filter(CoverLetter.source_resume_id == "res_a").count(), 0)
            # Shared/global catalog + other-user isolation preserved.
            self.assertIsNotNone(db.query(Job).filter(Job.id == "job_1").first())
        finally:
            db.close()

    def test_delete_removes_file_from_disk(self):
        resume_id, file_path = self.h._seed(filename="to_delete.pdf")
        self.assertTrue(os.path.exists(file_path))
        resp = self.h.client.delete(f"/resumes/{resume_id}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(os.path.exists(file_path))


class TestResumeDeleteOwnership(unittest.TestCase):
    """Cross-user deletes stay 404 and other users' records are untouched."""

    def setUp(self):
        self.h = _ResumeDeleteUploadApp()

    def tearDown(self):
        self.h.close()

    def test_cross_user_delete_returns_404(self):
        db = self.h.Session()
        file_path = os.path.join(self.h.tmpdir, "b.pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4 test")
        db.add(Resume(id="res_b", user_id=USER_B["id"], filename="b.pdf",
                      original_filename="b.pdf", file_path=file_path,
                      file_size="1", parsing_status="completed"))
        db.commit()
        db.close()

        # User A tries to delete User B's resume.
        resp = self.h.client.delete("/resumes/res_b")
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(self.h.client.get("/resumes/res_b/parsed").status_code == 200)

        # B's resume still exists and its file is untouched.
        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(Resume).filter(Resume.id == "res_b").first())
        finally:
            db.close()
        self.assertTrue(os.path.exists(file_path))

    def test_delete_other_user_dependents_are_never_touched(self):
        """A's delete of her resume must not delete B's dependents that happen
        to reference the same job."""
        self.h._seed()  # res_a for A
        db = self.h.Session()
        db.add(Job(id="job_1", user_id=USER_A["id"], title="Backend", company="C",
                   description="Python", required_skills="Python"))
        db.add(Resume(id="res_b", user_id=USER_B["id"], filename="b.pdf",
                      original_filename="b.pdf", file_path="/tmp/b.pdf",
                      file_size="1", parsing_status="completed"))
        db.add(CoverLetter(id="cl_b", user_id=USER_B["id"], source_resume_id="res_b",
                           job_id="job_1", version_name="cover-letter"))
        db.commit()
        db.close()

        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)

        db = self.h.Session()
        try:
            self.assertIsNone(db.query(Resume).filter(Resume.id == "res_a").first())
            self.assertIsNotNone(db.query(Resume).filter(Resume.id == "res_b").first())
            self.assertIsNotNone(db.query(CoverLetter).filter(CoverLetter.id == "cl_b").first())
        finally:
            db.close()

    def test_delete_preserves_global_profile_data(self):
        """Profile/JobMatch/Application data (not derived from the resume) must
        survive a resume delete."""
        self.h._seed()
        db = self.h.Session()
        db.add(Job(id="job_1", user_id=USER_A["id"], title="Backend", company="C",
                   description="Python", required_skills="Python"))
        db.commit()
        db.close()

        from app.models.profile import Profile as ProfileModel, UserSkill, Skill

        db = self.h.Session()
        profile = ProfileModel(id="prof_1", user_id=USER_A["id"], location="NYC")
        skill = Skill(id="sk_1", name="Python")
        db.add_all([profile, skill])
        db.commit()
        db.add(UserSkill(id="us_1", profile_id="prof_1", skill_id="sk_1", category="Programming"))
        db.commit()
        db.close()

        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)

        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(ProfileModel).filter(ProfileModel.id == "prof_1").first())
            self.assertIsNotNone(db.query(Skill).filter(Skill.id == "sk_1").first())
            self.assertIsNotNone(db.query(UserSkill).filter(UserSkill.id == "us_1").first())
            self.assertIsNotNone(db.query(Job).filter(Job.id == "job_1").first())
        finally:
            db.close()


class TestResumeDeleteRollback(unittest.TestCase):
    """A failed dependent cleanup must roll back the whole delete transaction."""

    def setUp(self):
        # SQLite with real FK enforcement; ExtraDependent's FK to resumes.id is
        # intentionally NOT covered by the ORM cascade so the FK is violated
        # exactly like a genuine dependent-cleanup failure.
        self.h = _ResumeDeleteUploadApp(enforce_fk=True)
        db = self.h.Session()
        db.add(Job(id="job_1", user_id=USER_A["id"], title="Backend", company="C",
                   description="Python", required_skills="Python"))
        db.commit()
        db.close()
        self.h._seed()

    def tearDown(self):
        self.h.close()

    def test_dependent_cleanup_failure_rolls_back_everything(self):
        db = self.h.Session()
        db.add_all([
            ResumeJobAnalysis(id="dep_a", user_id=USER_A["id"], resume_id="res_a",
                              job_id="job_1", overall_score=80),
            TailoredResume(id="dep_t", user_id=USER_A["id"], source_resume_id="res_a",
                           job_id="job_1", version_name="tailored"),
            CoverLetter(id="dep_c", user_id=USER_A["id"], source_resume_id="res_a",
                        job_id="job_1", version_name="cover-letter"),
            ExtraDependent(id="extra_1", resume_id="res_a"),
        ])
        db.commit()
        db.close()

        file_path = db_path = None
        db = self.h.Session()
        try:
            file_path = db.query(Resume).filter(Resume.id == "res_a").one().file_path
        finally:
            db.close()
        self.assertTrue(os.path.exists(file_path))

        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 500)

        # The entire transaction must have rolled back: resume, all ORM
        # dependents, and the extra dependent are still present, and the file
        # on disk must NOT have been removed.
        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(Resume).filter(Resume.id == "res_a").first())
            self.assertEqual(db.query(ResumeJobAnalysis).filter(ResumeJobAnalysis.resume_id == "res_a").count(), 1)
            self.assertEqual(db.query(TailoredResume).filter(TailoredResume.source_resume_id == "res_a").count(), 1)
            self.assertEqual(db.query(CoverLetter).filter(CoverLetter.source_resume_id == "res_a").count(), 1)
            self.assertEqual(db.query(ExtraDependent).filter(ExtraDependent.resume_id == "res_a").count(), 1)
        finally:
            db.close()
        self.assertTrue(os.path.exists(file_path))


class TestResumeUploadContract(unittest.TestCase):
    """The upload must live at POST /resumes (the frontend now calls this)."""

    def setUp(self):
        self.h = _ResumeDeleteUploadApp()

    def tearDown(self):
        self.h.close()

    def test_post_resumes_upload_contract(self):
        pdf = _write_text_pdf(os.path.join(self.h.tmpdir, "resume.pdf"))
        with open(pdf, "rb") as f:
            resp = self.h.client.post(
                "/resumes", files={"file": ("resume.pdf", f, "application/pdf")}
            )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["parsing_status"], "completed")
        self.assertEqual(body["user_id"], USER_A["id"])
        self.assertIn("skills", body["parsed_data"] if isinstance(body["parsed_data"], dict) else {})

    def test_legacy_upload_path_returns_405(self):
        # Regression lock: the removed/nonexistent POST /resumes/upload route
        # (which the frontend previously called) must NOT be a valid upload route.
        resp = self.h.client.post("/resumes/upload")
        self.assertEqual(resp.status_code, 405)

    def test_upload_rejects_non_pdf(self):
        resp = self.h.client.post(
            "/resumes",
            files={"file": ("resume.txt", b"not a pdf", "text/plain")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("PDF", resp.json()["detail"])

    def test_upload_rejects_oversized_file(self):
        with patch("app.api.resumes.MAX_FILE_SIZE", 10):
            resp = self.h.client.post(
                "/resumes",
                files={"file": ("big.pdf", b"x" * 20, "application/pdf")},
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("10MB", resp.json()["detail"])

    def test_upload_requires_auth_ownership(self):
        # Uploads are written under the authenticated user's own directory.
        pdf = _write_text_pdf(os.path.join(self.h.tmpdir, "resume.pdf"))
        self.h.current_user_id = USER_A["id"]
        with open(pdf, "rb") as f:
            resp = self.h.client.post(
                "/resumes", files={"file": ("resume.pdf", f, "application/pdf")}
            )
        self.assertEqual(resp.status_code, 201)
        rid = resp.json()["id"]
        # The other user must not see or parse it.
        self.h.current_user_id = USER_B["id"]
        listed = [r["id"] for r in self.h.client.get("/resumes").json()]
        self.assertNotIn(rid, listed)
        self.assertEqual(self.h.client.get(f"/resumes/{rid}/parsed").status_code, 404)


if __name__ == "__main__":
    unittest.main()