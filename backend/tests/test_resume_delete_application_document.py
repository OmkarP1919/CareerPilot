"""Phase 5E.4 - reverse resume -> application_document FK regression.

Deleting a Resume that is referenced by ApplicationDocument rows
(application_documents.source_resume_id -> resumes.id) used to raise a
PostgreSQL ForeignKeyViolation (HTTP 500) because the ORM did not remove the
referencing rows first. The Resume.application_documents relationship now
cascades those REFERENCE rows at delete time.

This suite pins:

A. basic reference deletion          resume + its reference documents gone, application kept
B. resume physical file safety      resume's own file removed, unrelated uploaded files kept
C. application remains intact       other events/interviews/uploaded documents survive
D. ownership isolation              cross-user delete stays 404 and touches nothing
E. FK-enabled SQLite regression    PRAGMA foreign_keys=ON reproduces the old 500 and now passes
F. PostgreSQL-gated regression     real-PG delete with an attached reference (skips cleanly)
G. existing application-document   DELETE keeps working (reference doc never deletes the resume)
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.applications import router as applications_router
from app.api.resumes import router as resumes_router
from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.application_event import ApplicationEvent
from app.models.application_interview import ApplicationInterview
from app.models.application_document import ApplicationDocument

USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
USER_B = {"id": "user_b", "firebase_uid": "fb_b"}

DUMMY_PDF = b"%PDF-1.4 test"


class _ResumeDocFKHarness:
    """Shared FastAPI harness with the resumes + applications routers and an
    optional FK-enforcing SQLite backend (PRAGMA foreign_keys=ON), mirroring
    the conventions of test_resume_delete_upload.py."""

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
        # Committed after the users so the FK-enforcing harness can point at an
        # existing users row.
        db.add(Job(id="job_1", user_id=USER_A["id"], title="Backend Developer",
                   company="Acme", description="Python FastAPI", required_skills="Python"))
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(resumes_router)
        self.app.include_router(applications_router)
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
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def seed_resume(self, resume_id="res_a", user_id=USER_A["id"], filename="resume.pdf",
                    content=DUMMY_PDF):
        file_path = os.path.join(self.tmpdir, f"{resume_id}_file.pdf")
        with open(file_path, "wb") as f:
            f.write(content)
        db = self.Session()
        db.add(Resume(
            id=resume_id, user_id=user_id, filename=filename,
            original_filename=filename, file_path=file_path,
            file_size=str(len(content)), parsing_status="completed",
        ))
        db.commit()
        db.close()
        return file_path

    def seed_application(self, app_id="app_a", user_id=USER_A["id"], job_id="job_1",
                         status="Applied"):
        db = self.Session()
        db.add(Application(id=app_id, user_id=user_id, job_id=job_id, status=status))
        db.commit()
        db.close()

    def seed_event(self, event_id="evt_1", app_id="app_a", event_type="milestone"):
        db = self.Session()
        db.add(ApplicationEvent(id=event_id, application_id=app_id, user_id=USER_A["id"],
                                event_type=event_type, created_by=USER_A["id"]))
        db.commit()
        db.close()

    def seed_interview(self, interview_id="iv_1", app_id="app_a", kind="video", status="scheduled"):
        db = self.Session()
        db.add(ApplicationInterview(id=interview_id, application_id=app_id, user_id=USER_A["id"],
                                    scheduled_at=datetime(2026, 9, 10, 15, 0, 0), kind=kind, status=status))
        db.commit()
        db.close()

    def attach(self, app_id="app_a", source_resume_id="res_a", document_type="resume"):
        resp = self.client.post(
            f"/applications/{app_id}/documents",
            json={"source_resume_id": source_resume_id, "document_type": document_type},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    def upload_document(self, app_id="app_a", filename="uploaded.pdf", content=DUMMY_PDF):
        upload_dir = os.path.join(self.tmpdir, "uploads")
        with patch("app.api.applications.UPLOAD_DIR", upload_dir):
            resp = self.client.post(
                f"/applications/{app_id}/documents/upload",
                files={"file": (filename, content, "application/pdf")},
            )
        assert resp.status_code == 201, resp.text
        user_dir = os.path.join(upload_dir, self.current_user_id)
        stored = os.listdir(user_dir)
        return resp.json(), os.path.join(user_dir, stored[0])


class TestResumeDeleteApplicationDocumentReference(unittest.TestCase):
    """5E.4 A+B+C - resume deletion removes reference rows, keeps the
    application, and touches only the resume's own physical file."""

    def setUp(self):
        self.h = _ResumeDocFKHarness()

    def tearDown(self):
        self.h.close()

    def test_basic_reference_deletion(self):
        resume_file = self.h.seed_resume()
        self.h.seed_application()
        doc = self.h.attach(source_resume_id="res_a")
        self.assertTrue(os.path.exists(resume_file))

        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)

        db = self.h.Session()
        try:
            self.assertIsNone(db.query(Resume).filter(Resume.id == "res_a").first())
            self.assertIsNone(
                db.query(ApplicationDocument).filter(ApplicationDocument.id == doc["id"]).first()
            )
            # The application itself is NEVER deleted by a resume deletion.
            self.assertIsNotNone(db.query(Application).filter(Application.id == "app_a").first())
        finally:
            db.close()

    def test_resume_file_removed_but_unrelated_file_kept(self):
        resume_file = self.h.seed_resume()
        self.h.seed_application()
        doc = self.h.attach(source_resume_id="res_a")
        uploaded, uploaded_path = self.h.upload_document(app_id="app_a")

        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)

        db = self.h.Session()
        try:
            # Reference row gone; the unrelated uploaded document row and its
            # physical file are untouched.
            self.assertIsNone(
                db.query(ApplicationDocument).filter(ApplicationDocument.id == doc["id"]).first()
            )
            self.assertIsNotNone(
                db.query(ApplicationDocument).filter(ApplicationDocument.id == uploaded["id"]).first()
            )
        finally:
            db.close()
        # The resume's own file follows the existing resume deletion behavior;
        # the uploaded application-document file was never owned by the resume.
        self.assertFalse(os.path.exists(resume_file))
        self.assertTrue(os.path.exists(uploaded_path))

    def test_application_remains_intact(self):
        self.h.seed_resume()
        self.h.seed_application()
        ref_doc = self.h.attach(source_resume_id="res_a")
        self.h.seed_event(event_id="evt_1")
        self.h.seed_interview(interview_id="iv_1")
        uploaded, _ = self.h.upload_document(app_id="app_a")

        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)

        db = self.h.Session()
        try:
            app = db.query(Application).filter(Application.id == "app_a").first()
            self.assertIsNotNone(app)
            self.assertEqual(app.id, "app_a")
            self.assertEqual(
                db.query(ApplicationDocument).filter(ApplicationDocument.id == ref_doc["id"]).count(),
                0,
            )
            self.assertIsNotNone(db.query(ApplicationEvent).filter(ApplicationEvent.id == "evt_1").first())
            self.assertIsNotNone(
                db.query(ApplicationInterview).filter(ApplicationInterview.id == "iv_1").first()
            )
            self.assertIsNotNone(
                db.query(ApplicationDocument).filter(ApplicationDocument.id == uploaded["id"]).first()
            )
        finally:
            db.close()


class TestResumeDeleteOwnership(unittest.TestCase):
    """5E.4 D - cross-user deletion stays 404 and touches nothing."""

    def setUp(self):
        self.h = _ResumeDocFKHarness()

    def tearDown(self):
        self.h.close()

    def test_foreign_user_delete_is_404_and_changes_nothing(self):
        resume_file = self.h.seed_resume()
        self.h.seed_application()
        doc = self.h.attach(source_resume_id="res_a")

        self.h.current_user_id = USER_B["id"]
        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 404)

        self.h.current_user_id = USER_A["id"]
        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(Resume).filter(Resume.id == "res_a").first())
            self.assertIsNotNone(
                db.query(ApplicationDocument).filter(ApplicationDocument.id == doc["id"]).first()
            )
            self.assertIsNotNone(db.query(Application).filter(Application.id == "app_a").first())
        finally:
            db.close()
        self.assertTrue(os.path.exists(resume_file))


class TestResumeDeleteApplicationDocumentFK(unittest.TestCase):
    """5E.4 E - the exact PostgreSQL failure mode pinned on an FK-enforcing
    SQLite backend (PRAGMA foreign_keys=ON). Before the resume-side cascade
    this scenario returns 500; with it, the reference rows are removed before
    the resume DELETE and the delete commits."""

    def setUp(self):
        self.h = _ResumeDocFKHarness(enforce_fk=True)

    def tearDown(self):
        self.h.close()

    def test_fk_enforced_resume_delete_with_reference_succeeds(self):
        resume_file = self.h.seed_resume()
        self.h.seed_application()
        doc = self.h.attach(source_resume_id="res_a")

        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)

        db = self.h.Session()
        try:
            self.assertIsNone(db.query(Resume).filter(Resume.id == "res_a").first())
            self.assertIsNone(
                db.query(ApplicationDocument).filter(ApplicationDocument.id == doc["id"]).first()
            )
            self.assertIsNotNone(db.query(Application).filter(Application.id == "app_a").first())
        finally:
            db.close()
        self.assertFalse(os.path.exists(resume_file))


class TestApplicationDocumentDeleteBehavior(unittest.TestCase):
    """5E.4 G - the existing DELETE /applications/{id}/documents/{document_id}
    contract is unchanged. A reference document's deletion NEVER deletes the
    resume; an uploaded document's deletion removes its own physical file."""

    def setUp(self):
        self.h = _ResumeDocFKHarness()

    def tearDown(self):
        self.h.close()

    def test_reference_document_delete_keeps_resume_and_file(self):
        resume_file = self.h.seed_resume()
        self.h.seed_application()
        doc = self.h.attach(source_resume_id="res_a")

        resp = self.h.client.delete(f"/applications/app_a/documents/{doc['id']}")
        self.assertEqual(resp.status_code, 204)

        db = self.h.Session()
        try:
            self.assertIsNone(
                db.query(ApplicationDocument).filter(ApplicationDocument.id == doc["id"]).first()
            )
            self.assertIsNotNone(db.query(Resume).filter(Resume.id == "res_a").first())
        finally:
            db.close()
        self.assertTrue(os.path.exists(resume_file))

    def test_uploaded_document_delete_removes_own_file(self):
        self.h.seed_application()
        doc, stored_path = self.h.upload_document(app_id="app_a")
        self.assertTrue(os.path.exists(stored_path))

        resp = self.h.client.delete(f"/applications/app_a/documents/{doc['id']}")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(os.path.exists(stored_path))

    def test_foreign_user_document_delete_is_404(self):
        self.h.seed_application()
        doc, stored_path = self.h.upload_document(app_id="app_a")
        self.h.current_user_id = USER_B["id"]

        resp = self.h.client.delete(f"/applications/app_a/documents/{doc['id']}")
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(os.path.exists(stored_path))
        db = self.h.Session()
        try:
            self.assertIsNotNone(
                db.query(ApplicationDocument).filter(ApplicationDocument.id == doc["id"]).first()
            )
        finally:
            db.close()


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class TestPostgresResumeDeleteApplicationDocumentRegression(unittest.TestCase):
    """5E.4 F - resume delete with an attached reference document pinned
    against a real PostgreSQL server (enabled via POSTGRES_TEST_DATABASE_URL;
    skips cleanly when unset or unreachable)."""

    @classmethod
    def setUpClass(cls):
        cls.url = POSTGRES_TEST_DATABASE_URL
        if not cls.url:
            raise unittest.SkipTest("POSTGRES_TEST_DATABASE_URL is not set")
        cls.engine = create_engine(cls.url, pool_pre_ping=True)
        try:
            cls.engine.connect().close()
        except Exception as exc:
            cls.engine.dispose()
            raise unittest.SkipTest(
                f"PostgreSQL test database unreachable ({exc.__class__.__name__}): {exc}"
            )
        Base.metadata.create_all(cls.engine)
        cls.Session = sessionmaker(bind=cls.engine)

        db = cls.Session()
        db.add_all([
            User(id=USER_A["id"], firebase_uid=USER_A["firebase_uid"], email="a@test.com", name="A"),
            User(id=USER_B["id"], firebase_uid=USER_B["firebase_uid"], email="b@test.com", name="B"),
        ])
        db.commit()
        db.add(Job(id="job_1", user_id=USER_A["id"], title="Backend Developer",
                   company="Acme", description="Python FastAPI", required_skills="Python"))
        db.commit()
        db.close()

        cls.app = FastAPI()
        cls.app.include_router(resumes_router)
        cls.app.include_router(applications_router)
        cls.current_user_id = USER_A["id"]

        def override_get_db():
            session = cls.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            session = cls.Session()
            try:
                return session.query(User).filter(User.id == cls.current_user_id).first()
            finally:
                session.close()

        cls.app.dependency_overrides[get_db] = override_get_db
        cls.app.dependency_overrides[get_current_user] = override_get_current_user
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(cls.engine)
        cls.engine.dispose()

    def test_delete_resume_with_attached_reference_on_postgres(self):
        app_resp = self.client.post("/applications", json={"job_id": "job_1", "status": "Applied"})
        self.assertEqual(app_resp.status_code, 201, app_resp.text)
        app_id = app_resp.json()["id"]

        db = self.Session()
        db.add(Resume(
            id="res_pg", user_id=USER_A["id"], filename="resume.pdf",
            original_filename="resume.pdf", file_path="/nonexistent/res_pg.pdf",
            file_size="13", parsing_status="completed",
        ))
        db.commit()
        db.close()

        attach_resp = self.client.post(
            f"/applications/{app_id}/documents",
            json={"source_resume_id": "res_pg", "document_type": "resume"},
        )
        self.assertEqual(attach_resp.status_code, 201, attach_resp.text)
        doc_id = attach_resp.json()["id"]

        resp = self.client.delete("/resumes/res_pg")
        self.assertEqual(resp.status_code, 204, resp.text)

        db = self.Session()
        try:
            self.assertIsNone(db.query(Resume).filter(Resume.id == "res_pg").first())
            self.assertIsNone(
                db.query(ApplicationDocument).filter(ApplicationDocument.id == doc_id).first()
            )
            self.assertIsNotNone(db.query(Application).filter(Application.id == app_id).first())
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()