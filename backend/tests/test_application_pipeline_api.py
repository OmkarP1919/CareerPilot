"""HTTP/API-level tests for the Phase 5D application pipeline endpoints.

These exercise the real FastAPI route handlers in app.api.applications for:

- events      POST/GET /applications/{id}/events
- interviews  POST/GET/PUT/DELETE /applications/{id}/interviews[...]
- documents   POST/GET/DELETE /applications/{id}/documents[...] (+ upload)
- timeline    GET /applications/{id}/timeline

plus the additive auto status-change event generation and the ownership /
IDOR guarantees. Style follows test_applications.py / test_discovery_saved_search_api.py.
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.applications import router as applications_router
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

DUMMY_PDF = b"%PDF-1.4 test"  # 13 bytes


class _PipelineAPIHarness:
    """Shared FastAPI app harness: in-memory SQLite, auth override, seeded
    users/jobs/resumes for user-scoped (IDOR) coverage."""

    def __init__(self, enforce_fk=False):
        self.tmpdir = tempfile.mkdtemp()
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        if enforce_fk:
            # Same trick as test_resume_delete_upload.py: SQLite normally does
            # not enforce foreign keys, so activate them to reproduce the exact
            # failure mode PostgreSQL raises on a constrained delete.
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
        # Jobs are a global catalog; both users can discover the same job.
        # Committed after the users (separate transaction) so the FK-enforcing
        # harness (PRAGMA foreign_keys=ON) can insert them: each job references
        # an existing users row, mirroring test_resume_delete_upload.py.
        db.add_all([
            Job(id="job_1", user_id=USER_A["id"], title="Backend Developer",
                company="Acme", description="Python FastAPI", required_skills="Python, FastAPI"),
            Job(id="job_2", user_id=USER_B["id"], title="Frontend Developer",
                company="Beta", description="React", required_skills="React"),
        ])
        db.commit()
        db.close()

        self.app = FastAPI()
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
        self.client = TestClient(self.app)

    def close(self):
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def seed_application(self, app_id="app_a", user_id=USER_A["id"], job_id="job_1", status="Applied"):
        db = self.Session()
        application = Application(id=app_id, user_id=user_id, job_id=job_id, status=status)
        db.add(application)
        db.commit()
        db.close()
        return app_id

    def seed_resume(self, resume_id="res_a", user_id=USER_A["id"], filename="resume.pdf"):
        file_path = os.path.join(self.tmpdir, f"{resume_id}.pdf")
        with open(file_path, "wb") as f:
            f.write(DUMMY_PDF)
        db = self.Session()
        resume = Resume(
            id=resume_id,
            user_id=user_id,
            filename=filename,
            original_filename=filename,
            file_path=file_path,
            file_size="1",
            parsing_status="completed",
        )
        db.add(resume)
        db.commit()
        db.close()
        return resume_id

    def create_application_via_api(self, job_id="job_1", status="Saved"):
        resp = self.client.post("/applications", json={"job_id": job_id, "status": status})
        assert resp.status_code == 201, resp.text
        return resp.json()

    def post_event(self, app_id="app_a", event_type="note_added", notes=None, metadata=None, created_by=None):
        body = {"event_type": event_type}
        if notes is not None:
            body["notes"] = notes
        if metadata is not None:
            body["metadata"] = metadata
        if created_by is not None:
            body["created_by"] = created_by
        return self.client.post(f"/applications/{app_id}/events", json=body)

    def post_interview(self, app_id="app_a", scheduled_at="2026-09-10T15:00:00Z", kind="video", status=None, notes=None):
        body = {"scheduled_at": scheduled_at, "kind": kind}
        if status is not None:
            body["status"] = status
        if notes is not None:
            body["notes"] = notes
        return self.client.post(f"/applications/{app_id}/interviews", json=body)

    def attach(self, app_id="app_a", source_resume_id="res_a", document_type="resume", name=None, metadata=None):
        body = {"source_resume_id": source_resume_id, "document_type": document_type}
        if name is not None:
            body["name"] = name
        if metadata is not None:
            body["metadata"] = metadata
        return self.client.post(f"/applications/{app_id}/documents", json=body)


class TestEventsAPI(unittest.TestCase):
    def setUp(self):
        self.h = _PipelineAPIHarness()
        self.h.seed_application()

    def tearDown(self):
        self.h.close()

    def test_post_event_creates_event_201(self):
        resp = self.h.post_event(notes="Spoke with recruiter")
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["event_type"], "note_added")
        self.assertEqual(body["notes"], "Spoke with recruiter")
        self.assertEqual(body["user_id"], USER_A["id"])
        self.assertEqual(body["application_id"], "app_a")
        self.assertTrue(body["id"])
        self.assertIsNotNone(body["created_at"])

    def test_post_event_created_by_is_server_actor_not_client_input(self):
        resp = self.h.post_event(created_by="someone_else")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["created_by"], USER_A["id"])

    def test_post_event_metadata_roundtrip(self):
        metadata = {"from_status": "Saved", "to_status": "Applied", "nested": {"tags": ["a", "b"]}}
        self.assertEqual(self.h.post_event(metadata=metadata).status_code, 201)
        resp = self.h.client.get("/applications/app_a/events")
        self.assertEqual(resp.status_code, 200)
        events = resp.json()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["metadata"], metadata)

    def test_get_events_serialization_and_deterministic_order(self):
        self.h.post_event(event_type="note_added", notes="first")
        self.h.post_event(event_type="milestone", notes="second")
        resp = self.h.client.get("/applications/app_a/events")
        self.assertEqual(resp.status_code, 200)
        events = resp.json()
        self.assertEqual([e["event_type"] for e in events], ["note_added", "milestone"])
        stamps = [e["created_at"] for e in events]
        self.assertEqual(stamps, sorted(stamps))

    def test_post_event_invalid_event_type_400(self):
        resp = self.h.post_event(event_type="not_a_real_event")
        self.assertEqual(resp.status_code, 400)

    def test_missing_application_404(self):
        resp = self.h.post_event(app_id="does-not-exist")
        self.assertEqual(resp.status_code, 404)
        resp = self.h.client.get("/applications/does-not-exist/events")
        self.assertEqual(resp.status_code, 404)

    def test_cross_user_application_404(self):
        self.h.seed_application(app_id="app_b", user_id=USER_B["id"], job_id="job_2")
        # User A must not see or mutate B's application events.
        self.assertEqual(self.h.post_event(app_id="app_b").status_code, 404)
        self.assertEqual(self.h.client.get("/applications/app_b/events").status_code, 404)


class TestAutoStatusChangeEvents(unittest.TestCase):
    def setUp(self):
        self.h = _PipelineAPIHarness()

    def tearDown(self):
        self.h.close()

    def test_create_application_auto_records_created_event(self):
        app = self.h.create_application_via_api(status="Saved")
        resp = self.h.client.get(f"/applications/{app['id']}/events")
        self.assertEqual(resp.status_code, 200)
        events = resp.json()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "created")
        self.assertEqual(events[0]["created_by"], USER_A["id"])

    def test_applied_to_interview_generates_status_changed_event(self):
        app = self.h.create_application_via_api(status="Applied")
        resp = self.h.client.put(f"/applications/{app['id']}", json={"status": "Interview"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "Interview")

        events = self.h.client.get(f"/applications/{app['id']}/events").json()
        self.assertEqual([e["event_type"] for e in events], ["created", "status_changed"])
        transition = events[1]
        self.assertEqual(transition["metadata"], {"from_status": "Applied", "to_status": "Interview"})

    def test_interview_to_offer_transition_metadata(self):
        app = self.h.create_application_via_api(status="Interview")
        resp = self.h.client.put(f"/applications/{app['id']}", json={"status": "Offer"})
        self.assertEqual(resp.status_code, 200)
        events = self.h.client.get(f"/applications/{app['id']}/events").json()
        transition = events[-1]
        self.assertEqual(transition["event_type"], "status_changed")
        self.assertEqual(transition["metadata"], {"from_status": "Interview", "to_status": "Offer"})

    def test_same_status_update_does_not_create_event(self):
        app = self.h.create_application_via_api(status="Applied")
        self.h.client.put(f"/applications/{app['id']}", json={"status": "Applied"})
        events = self.h.client.get(f"/applications/{app['id']}/events").json()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "created")

    def test_status_contract_and_invalid_status_unchanged(self):
        app = self.h.create_application_via_api(status="Saved")
        resp = self.h.client.put(f"/applications/{app['id']}", json={"status": "NotARealStatus"})
        self.assertEqual(resp.status_code, 400)


class TestInterviewsAPI(unittest.TestCase):
    def setUp(self):
        self.h = _PipelineAPIHarness()
        self.h.seed_application()

    def tearDown(self):
        self.h.close()

    def seed_interview(self, interview_id, scheduled_at, kind="video", status="scheduled", user_id=USER_A["id"], app_id="app_a"):
        db = self.h.Session()
        interview = ApplicationInterview(
            id=interview_id, application_id=app_id, user_id=user_id,
            scheduled_at=scheduled_at, kind=kind, status=status,
        )
        db.add(interview)
        db.commit()
        db.close()
        return interview_id

    def test_post_interview_201(self):
        resp = self.h.post_interview(notes="Hiring manager round")
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["kind"], "video")
        self.assertEqual(body["status"], "scheduled")
        self.assertEqual(body["notes"], "Hiring manager round")
        self.assertEqual(body["user_id"], USER_A["id"])
        self.assertEqual(body["application_id"], "app_a")
        self.assertIsNotNone(body["scheduled_at"])
        self.assertIsNotNone(body["created_at"])
        self.assertIsNotNone(body["updated_at"])

    def test_get_interviews_ordered_by_scheduled_at_ascending(self):
        self.h.post_interview(scheduled_at="2026-10-01T15:00:00Z")
        self.h.post_interview(scheduled_at="2026-09-01T15:00:00Z")
        resp = self.h.client.get("/applications/app_a/interviews")
        self.assertEqual(resp.status_code, 200)
        interviews = resp.json()
        self.assertEqual(len(interviews), 2)
        self.assertTrue(interviews[0]["scheduled_at"] < interviews[1]["scheduled_at"])

    def test_get_interviews_stable_tie_break_on_id(self):
        now = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        self.seed_interview("iv_z", now)
        self.seed_interview("iv_a", now)
        resp = self.h.client.get("/applications/app_a/interviews")
        ids = [i["id"] for i in resp.json()]
        self.assertEqual(ids, sorted(ids))

    def test_put_interview_partial_update_200(self):
        iv = self.h.post_interview().json()
        resp = self.h.client.put(
            f"/applications/app_a/interviews/{iv['id']}",
            json={"status": "completed", "notes": "Went well"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["notes"], "Went well")
        self.assertEqual(body["kind"], "video")  # untouched by partial update

    def test_put_interview_reschedule(self):
        iv = self.h.post_interview().json()
        resp = self.h.client.put(
            f"/applications/app_a/interviews/{iv['id']}",
            json={"scheduled_at": "2026-12-01T09:00:00+05:30"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["scheduled_at"], "2026-12-01T03:30:00")

    def test_delete_interview_204(self):
        iv = self.h.post_interview().json()
        resp = self.h.client.delete(f"/applications/app_a/interviews/{iv['id']}")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.h.client.get("/applications/app_a/interviews").json(), [])

    def test_interview_validation_kind_status(self):
        self.assertEqual(self.h.post_interview(kind="skywriting").status_code, 400)
        self.assertEqual(self.h.post_interview(status="maybe").status_code, 400)

    def test_naive_scheduled_at_rejected(self):
        resp = self.h.post_interview(scheduled_at="2026-09-10T15:00:00")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("timezone", resp.json()["detail"])

    def test_missing_application_404(self):
        self.assertEqual(self.h.post_interview(app_id="nope").status_code, 404)
        self.assertEqual(self.h.client.get("/applications/nope/interviews").status_code, 404)

    def test_cross_user_application_404(self):
        self.h.seed_application(app_id="app_b", user_id=USER_B["id"], job_id="job_2")
        self.assertEqual(self.h.post_interview(app_id="app_b").status_code, 404)

    def test_cannot_access_interview_through_another_users_context(self):
        iv = self.h.post_interview().json()  # user A's interview on app_a
        self.h.current_user_id = USER_B["id"]
        self.assertEqual(self.h.client.get("/applications/app_a/interviews").status_code, 404)
        self.assertEqual(
            self.h.client.put(f"/applications/app_a/interviews/{iv['id']}", json={"status": "completed"}).status_code,
            404,
        )
        self.assertEqual(
            self.h.client.delete(f"/applications/app_a/interviews/{iv['id']}").status_code,
            404,
        )
        # A's interview still exists and is reachable by A.
        self.h.current_user_id = USER_A["id"]
        self.assertEqual(self.h.client.get("/applications/app_a/interviews").json()[0]["id"], iv["id"])

    def test_cannot_change_ownership_via_payload(self):
        iv = self.h.post_interview().json()
        resp = self.h.client.put(
            f"/applications/app_a/interviews/{iv['id']}",
            json={"user_id": USER_B["id"], "application_id": "app_b", "status": "completed"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["user_id"], USER_A["id"])
        self.assertEqual(body["application_id"], "app_a")

    def test_interview_status_independent_of_application_status(self):
        self.h.post_interview()
        self.assertEqual(self.h.client.get("/applications/app_a/interviews").json()[0]["status"], "scheduled")
        # The app's own 8-status contract is untouched.
        self.assertEqual(self.h.client.get("/applications").json()[0]["status"], "Applied")


class TestDocumentsAPI(unittest.TestCase):
    def setUp(self):
        self.h = _PipelineAPIHarness()
        self.h.seed_application()
        self.h.seed_resume("res_a", USER_A["id"])
        self.h.seed_resume("res_b", USER_B["id"])

    def tearDown(self):
        self.h.close()

    def test_attach_existing_owned_resume_201(self):
        resp = self.h.attach(name="Master resume")
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["source_resume_id"], "res_a")
        self.assertEqual(body["document_type"], "resume")
        self.assertEqual(body["name"], "Master resume")
        self.assertEqual(body["user_id"], USER_A["id"])
        self.assertEqual(body["application_id"], "app_a")
        self.assertIsNone(body["filename"])
        self.assertIsNotNone(body["created_at"])

    def test_get_documents_200_and_reference_serialization(self):
        self.h.attach()
        resp = self.h.client.get("/applications/app_a/documents")
        self.assertEqual(resp.status_code, 200)
        docs = resp.json()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["source_resume_id"], "res_a")
        self.assertEqual(docs[0]["filename"], None)

    def test_attach_cross_user_resume_404(self):
        resp = self.h.attach(source_resume_id="res_b")
        self.assertEqual(resp.status_code, 404)

    def test_attach_missing_resume_404(self):
        resp = self.h.attach(source_resume_id="does-not-exist")
        self.assertEqual(resp.status_code, 404)

    def test_attach_requires_source_resume_id_400(self):
        resp = self.h.client.post("/applications/app_a/documents", json={"document_type": "resume"})
        self.assertEqual(resp.status_code, 400)

    def test_attach_invalid_document_type_400(self):
        resp = self.h.client.post(
            "/applications/app_a/documents",
            json={"source_resume_id": "res_a", "document_type": "super-secret"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_document_201_and_storage_contract(self):
        with patch("app.api.applications.UPLOAD_DIR", os.path.join(self.h.tmpdir, "uploads")):
            resp = self.h.client.post(
                "/applications/app_a/documents/upload",
                data={"document_type": "cover_letter", "name": "Acme cover letter"},
                files={"file": ("cover_letter.pdf", DUMMY_PDF, "application/pdf")},
            )
        self.assertEqual(resp.status_code, 201, resp.text)
        body = resp.json()
        self.assertEqual(body["document_type"], "cover_letter")
        self.assertEqual(body["name"], "Acme cover letter")
        self.assertEqual(body["original_filename"], "cover_letter.pdf")
        self.assertEqual(body["file_size"], str(len(DUMMY_PDF)))
        self.assertTrue(body["filename"].endswith(".pdf"))
        self.assertIsNone(body["source_resume_id"])
        # Filesystem internals must not leak into the API response.
        self.assertNotIn("file_path", body)
        # The physical file actually landed under the user's own directory.
        user_upload_dir = os.path.join(self.h.tmpdir, "uploads", USER_A["id"])
        self.assertEqual(len(os.listdir(user_upload_dir)), 1)

    def test_upload_rejects_unsupported_extension(self):
        with patch("app.api.applications.UPLOAD_DIR", os.path.join(self.h.tmpdir, "uploads")):
            resp = self.h.client.post(
                "/applications/app_a/documents/upload",
                files={"file": ("notes.txt", b"plain text", "text/plain")},
            )
        self.assertEqual(resp.status_code, 400)

    def test_upload_rejects_oversized_file(self):
        with patch("app.api.applications.UPLOAD_DIR", os.path.join(self.h.tmpdir, "uploads")), \
                patch("app.api.applications.MAX_UPLOAD_SIZE", 10):
            resp = self.h.client.post(
                "/applications/app_a/documents/upload",
                files={"file": ("big.pdf", b"x" * 20, "application/pdf")},
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("10MB", resp.json()["detail"])

    def test_upload_sanitizes_unsafe_client_filename(self):
        with patch("app.api.applications.UPLOAD_DIR", os.path.join(self.h.tmpdir, "uploads")):
            resp = self.h.client.post(
                "/applications/app_a/documents/upload",
                files={"file": ("..\\..\\evil.pdf", DUMMY_PDF, "application/pdf")},
            )
        self.assertEqual(resp.status_code, 201, resp.text)
        body = resp.json()
        # Only the basename is ever stored; nothing may escape the upload dir.
        self.assertEqual(body["original_filename"], "evil.pdf")
        user_upload_dir = os.path.join(self.h.tmpdir, "uploads", USER_A["id"])
        self.assertEqual(len(os.listdir(user_upload_dir)), 1)
        self.assertNotIn("..", body["filename"])

    def test_get_documents_isolation(self):
        self.h.seed_application(app_id="app_b", user_id=USER_B["id"], job_id="job_2")
        self.h.attach()  # A's doc on app_a
        self.h.current_user_id = USER_B["id"]
        self.assertEqual(self.h.client.get("/applications/app_a/documents").status_code, 404)
        self.assertEqual(self.h.client.get("/applications/app_b/documents").json(), [])

    def test_delete_document_204(self):
        doc = self.h.attach().json()
        resp = self.h.client.delete(f"/applications/app_a/documents/{doc['id']}")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.h.client.get("/applications/app_a/documents").json(), [])

    def test_delete_reference_document_never_deletes_resume(self):
        doc = self.h.attach().json()
        resume_file = os.path.join(self.h.tmpdir, "res_a.pdf")
        self.assertTrue(os.path.exists(resume_file))
        self.assertEqual(self.h.client.delete(f"/applications/app_a/documents/{doc['id']}").status_code, 204)
        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(Resume).filter(Resume.id == "res_a").first())
        finally:
            db.close()
        self.assertTrue(os.path.exists(resume_file))

    def test_delete_uploaded_document_removes_its_physical_file(self):
        upload_dir = os.path.join(self.h.tmpdir, "uploads")
        with patch("app.api.applications.UPLOAD_DIR", upload_dir):
            doc = self.h.client.post(
                "/applications/app_a/documents/upload",
                files={"file": ("cover.pdf", DUMMY_PDF, "application/pdf")},
            ).json()
            user_dir = os.path.join(upload_dir, USER_A["id"])
            stored = os.listdir(user_dir)
            self.assertEqual(len(stored), 1)
            stored_path = os.path.join(user_dir, stored[0])
        self.assertEqual(self.h.client.delete(f"/applications/app_a/documents/{doc['id']}").status_code, 204)
        self.assertFalse(os.path.exists(stored_path))

    def test_cross_user_document_access_404(self):
        doc = self.h.attach().json()  # A's doc
        self.h.current_user_id = USER_B["id"]
        self.assertEqual(self.h.client.get("/applications/app_a/documents").status_code, 404)
        self.assertEqual(
            self.h.client.delete(f"/applications/app_a/documents/{doc['id']}").status_code,
            404,
        )
        self.h.current_user_id = USER_A["id"]
        self.assertEqual(self.h.client.get("/applications/app_a/documents").json()[0]["id"], doc["id"])


class TestTimelineAPI(unittest.TestCase):
    def setUp(self):
        self.h = _PipelineAPIHarness()
        self.h.seed_application()
        self.h.seed_resume("res_a", USER_A["id"])

    def tearDown(self):
        self.h.close()

    def seed_event(self, event_id, created_at, event_type="note_added", notes=None):
        db = self.h.Session()
        event = ApplicationEvent(
            id=event_id, application_id="app_a", user_id=USER_A["id"],
            event_type=event_type, notes=notes, created_by=USER_A["id"],
            created_at=created_at, meta_data=None,
        )
        db.add(event)
        db.commit()
        db.close()

    def test_empty_timeline_returns_valid_contract(self):
        resp = self.h.client.get("/applications/app_a/timeline")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["application_id"], "app_a")
        self.assertEqual(body["user_id"], USER_A["id"])
        self.assertEqual(body["entries"], [])

    def test_missing_application_404(self):
        self.assertEqual(self.h.client.get("/applications/nope/timeline").status_code, 404)

    def test_timeline_combines_all_resource_kinds(self):
        self.h.client.post("/applications/app_a/events", json={"event_type": "note_added"})
        self.h.client.post("/applications/app_a/interviews", json={
            "scheduled_at": "2026-09-10T15:00:00Z", "kind": "video",
        })
        self.h.client.post("/applications/app_a/documents", json={
            "source_resume_id": "res_a", "document_type": "resume",
        })
        resp = self.h.client.get("/applications/app_a/timeline")
        self.assertEqual(resp.status_code, 200)
        kinds = {e["kind"] for e in resp.json()["entries"]}
        self.assertEqual(kinds, {"event", "interview", "document"})

    def test_timeline_discriminated_serialization_by_kind(self):
        self.h.client.post("/applications/app_a/events", json={"event_type": "milestone", "notes": "x"})
        self.h.client.post("/applications/app_a/interviews", json={
            "scheduled_at": "2026-09-10T15:00:00Z", "kind": "onsite", "status": "scheduled",
        })
        self.h.client.post("/applications/app_a/documents", json={
            "source_resume_id": "res_a", "document_type": "resume", "name": "Master",
        })
        entries = {e["kind"]: e for e in self.h.client.get("/applications/app_a/timeline").json()["entries"]}

        ev = entries["event"]
        self.assertEqual(ev["event_type"], "milestone")
        self.assertEqual(ev["notes"], "x")
        self.assertEqual(ev["created_by"], USER_A["id"])

        iv = entries["interview"]
        self.assertEqual(iv["interview_kind"], "onsite")
        self.assertEqual(iv["kind"], "interview")
        self.assertEqual(iv["status"], "scheduled")
        self.assertIsNotNone(iv["scheduled_at"])

        doc = entries["document"]
        self.assertEqual(doc["document_type"], "resume")
        self.assertEqual(doc["name"], "Master")
        self.assertEqual(doc["source_resume_id"], "res_a")

        for entry in entries.values():
            self.assertIn("id", entry)
            self.assertIn("application_id", entry)
            self.assertIn("user_id", entry)
            self.assertIn("created_at", entry)

    def test_timeline_chronological_ordering_by_created_at(self):
        base = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
        self.seed_event("ev_2", base + timedelta(minutes=10))  # event mid
        self.seed_event("ev_1", base - timedelta(minutes=10))  # event first
        # interview created last
        db = self.h.Session()
        db.add(ApplicationInterview(
            id="iv_3", application_id="app_a", user_id=USER_A["id"],
            scheduled_at=base + timedelta(days=2), kind="video",
            created_at=base + timedelta(minutes=20),
        ))
        db.commit()
        db.close()

        entries = self.h.client.get("/applications/app_a/timeline").json()["entries"]
        self.assertEqual([e["id"] for e in entries], ["ev_1", "ev_2", "iv_3"])
        stamps = [e["created_at"] for e in entries]
        self.assertEqual(stamps, sorted(stamps))

    def test_timeline_scheduled_at_is_agenda_not_creation_time(self):
        self.h.client.post("/applications/app_a/interviews", json={
            "scheduled_at": "2026-09-20T15:00:00Z", "kind": "video",
        })
        entry = [e for e in self.h.client.get("/applications/app_a/timeline").json()["entries"]
                 if e["kind"] == "interview"][0]
        self.assertTrue(entry["scheduled_at"] > entry["created_at"])

    def test_no_cross_user_timeline_leakage(self):
        self.h.client.post("/applications/app_a/events", json={"event_type": "note_added"})
        self.h.seed_application(app_id="app_b", user_id=USER_B["id"], job_id="job_2")
        self.h.current_user_id = USER_B["id"]
        self.assertEqual(self.h.client.get("/applications/app_a/timeline").status_code, 404)
        self.assertEqual(self.h.client.get("/applications/app_b/timeline").json()["entries"], [])

    def test_timeline_pagination_limit(self):
        for i in range(5):
            self.h.client.post("/applications/app_a/events", json={"event_type": "note_added", "notes": str(i)})
        resp = self.h.client.get("/applications/app_a/timeline", params={"limit": 2})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["entries"]), 2)


class TestApplicationsRegression(unittest.TestCase):
    """The pre-existing /applications endpoints must keep their exact contract
    now that auto event generation runs inside them."""

    def setUp(self):
        self.h = _PipelineAPIHarness()

    def tearDown(self):
        self.h.close()

    def test_create_application_201(self):
        resp = self.h.client.post("/applications", json={"job_id": "job_1", "status": "Saved"})
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["status"], "Saved")
        self.assertEqual(body["job_title"], "Backend Developer")
        self.assertEqual(body["user_id"], USER_A["id"])

    def test_duplicate_application_rejected_400(self):
        self.h.create_application_via_api()
        resp = self.h.client.post("/applications", json={"job_id": "job_1", "status": "Saved"})
        self.assertEqual(resp.status_code, 400)

    def test_update_application_keeps_response_shape(self):
        app = self.h.create_application_via_api(status="Applied")
        resp = self.h.client.put(f"/applications/{app['id']}", json={"status": "Offer", "notes": "signed"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "Offer")
        self.assertEqual(body["notes"], "signed")
        self.assertEqual(body["job_title"], "Backend Developer")
        self.assertEqual(body["job_company"], "Acme")
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)

    def test_status_filtering(self):
        app = self.h.create_application_via_api(status="Applied")
        self.h.client.put(f"/applications/{app['id']}", json={"status": "Interview"})
        self.assertEqual(
            [x["status"] for x in self.h.client.get("/applications", params={"status": "Interview"}).json()],
            ["Interview"],
        )
        self.assertEqual(self.h.client.get("/applications", params={"status": "Offer"}).json(), [])

    def test_delete_application_204(self):
        app = self.h.create_application_via_api()
        resp = self.h.client.delete(f"/applications/{app['id']}")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.h.client.get("/applications").json(), [])

    def test_all_eight_statuses_accepted(self):
        db = self.h.Session()
        db.add_all([
            Job(id=f"job_s{i}", user_id=USER_A["id"], title=f"Role {i}",
                company="Acme", description="desc", required_skills="s")
            for i in range(8)
        ])
        db.commit()
        db.close()

        for i, status in enumerate(
            ["Saved", "Preparing", "Applied", "Assessment", "Interview", "Offer", "Rejected", "Withdrawn"]
        ):
            resp = self.h.client.post("/applications", json={"job_id": f"job_s{i}", "status": status})
            self.assertEqual(resp.status_code, 201, resp.text)
        self.assertEqual(len(self.h.client.get("/applications").json()), 8)

    def test_cross_user_application_update_still_404(self):
        app_a = self.h.seed_application(app_id="app_a", user_id=USER_A["id"], job_id="job_1")
        self.h.current_user_id = USER_B["id"]
        resp = self.h.client.put(f"/applications/{app_a}", json={"status": "Offer"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.h.client.delete(f"/applications/{app_a}").status_code, 404)


class TestApplicationDeleteCascade(unittest.TestCase):
    """B-1 blocker regression: DELETE /applications/{id} must remove every owned
    child row and uploaded file without tripping foreign-key enforcement.

    Runs on the SQLite harness with PRAGMA foreign_keys=ON (the exact approach
    test_resume_delete_upload.py uses) so the PostgreSQL ForeignKeyViolation the
    production DB raises on an un-cascaded delete is reproduced and pinned
    locally. Every test below fails with a 500 unless the application cascade
    relationships and the endpoint's file cleanup are in place.
    """

    def setUp(self):
        self.h = _PipelineAPIHarness(enforce_fk=True)

    def tearDown(self):
        self.h.close()

    def test_delete_application_removes_events(self):
        app = self.h.create_application_via_api(status="Interview")
        app_id = app["id"]
        self.assertEqual(self.h.post_event(app_id=app_id, event_type="note_added").status_code, 201)
        db = self.h.Session()
        try:
            self.assertEqual(
                db.query(ApplicationEvent).filter(ApplicationEvent.application_id == app_id).count(),
                2,  # auto "created" event + the note_added event
            )
        finally:
            db.close()

        self.assertEqual(self.h.client.delete(f"/applications/{app_id}").status_code, 204)
        self.assertEqual(self.h.client.get(f"/applications/{app_id}/events").status_code, 404)
        self.assertNotIn(
            app_id,
            [application["id"] for application in self.h.client.get("/applications").json()],
        )
        db = self.h.Session()
        try:
            self.assertIsNone(db.query(Application).filter(Application.id == app_id).first())
            self.assertEqual(
                db.query(ApplicationEvent).filter(ApplicationEvent.application_id == app_id).count(),
                0,
            )
        finally:
            db.close()

    def test_delete_application_removes_interviews(self):
        app = self.h.create_application_via_api()
        app_id = app["id"]
        self.assertEqual(
            self.h.post_interview(app_id=app_id, scheduled_at="2026-09-10T15:00:00Z", kind="phone").status_code,
            201,
        )
        db = self.h.Session()
        try:
            self.assertEqual(
                db.query(ApplicationInterview).filter(ApplicationInterview.application_id == app_id).count(),
                1,
            )
        finally:
            db.close()

        self.assertEqual(self.h.client.delete(f"/applications/{app_id}").status_code, 204)
        self.assertEqual(self.h.client.get(f"/applications/{app_id}/interviews").status_code, 404)
        db = self.h.Session()
        try:
            self.assertEqual(
                db.query(ApplicationInterview).filter(ApplicationInterview.application_id == app_id).count(),
                0,
            )
        finally:
            db.close()

    def test_delete_application_removes_reference_document_but_keeps_resume(self):
        app = self.h.create_application_via_api()
        app_id = app["id"]
        self.h.seed_resume("res_a")
        self.assertEqual(
            self.h.attach(app_id=app_id, source_resume_id="res_a", document_type="resume").status_code,
            201,
        )
        resume_file = os.path.join(self.h.tmpdir, "res_a.pdf")
        self.assertTrue(os.path.exists(resume_file))

        self.assertEqual(self.h.client.delete(f"/applications/{app_id}").status_code, 204)
        db = self.h.Session()
        try:
            self.assertEqual(
                db.query(ApplicationDocument).filter(ApplicationDocument.application_id == app_id).count(),
                0,
            )
            self.assertIsNotNone(
                db.query(Resume).filter(Resume.id == "res_a", Resume.user_id == USER_A["id"]).first()
            )
        finally:
            db.close()
        # A reference document NEVER owns the resume's physical file.
        self.assertTrue(os.path.exists(resume_file))

    def test_delete_application_removes_uploaded_document_and_physical_file(self):
        app = self.h.create_application_via_api()
        app_id = app["id"]
        upload_dir = os.path.join(self.h.tmpdir, "uploads")
        with patch("app.api.applications.UPLOAD_DIR", upload_dir):
            doc = self.h.client.post(
                f"/applications/{app_id}/documents/upload",
                files={"file": ("cover.pdf", DUMMY_PDF, "application/pdf")},
            ).json()
            user_dir = os.path.join(upload_dir, USER_A["id"])
            stored = os.listdir(user_dir)
            self.assertEqual(len(stored), 1)
            stored_path = os.path.join(user_dir, stored[0])

        self.assertEqual(self.h.client.delete(f"/applications/{app_id}").status_code, 204)
        db = self.h.Session()
        try:
            self.assertEqual(
                db.query(ApplicationDocument)
                .filter(ApplicationDocument.application_id == app_id).count(),
                0,
            )
        finally:
            db.close()
        self.assertFalse(os.path.exists(stored_path))

    def test_foreign_user_delete_is_404_and_touches_nothing(self):
        app_a = self.h.create_application_via_api(job_id="job_1", status="Applied")
        app_a_id = app_a["id"]

        self.h.current_user_id = USER_B["id"]
        app_b = self.h.create_application_via_api(job_id="job_2", status="Saved")
        app_b_id = app_b["id"]
        upload_dir = os.path.join(self.h.tmpdir, "uploads")
        with patch("app.api.applications.UPLOAD_DIR", upload_dir):
            self.h.client.post(
                f"/applications/{app_b_id}/documents/upload",
                files={"file": ("b.pdf", DUMMY_PDF, "application/pdf")},
            )
            b_user_dir = os.path.join(upload_dir, USER_B["id"])
            b_stored = os.listdir(b_user_dir)
            self.assertEqual(len(b_stored), 1)
            b_stored_path = os.path.join(b_user_dir, b_stored[0])

        self.h.current_user_id = USER_A["id"]
        self.assertEqual(self.h.client.delete(f"/applications/{app_b_id}").status_code, 404)

        db = self.h.Session()
        try:
            self.assertIsNotNone(db.query(Application).filter(Application.id == app_b_id).first())
            self.assertEqual(
                db.query(ApplicationDocument).filter(ApplicationDocument.application_id == app_b_id).count(),
                1,
            )
        finally:
            db.close()
        self.assertTrue(os.path.exists(b_stored_path))

        self.assertEqual(self.h.client.delete(f"/applications/{app_a_id}").status_code, 204)
        db = self.h.Session()
        try:
            self.assertEqual(
                db.query(ApplicationDocument).filter(ApplicationDocument.application_id == app_b_id).count(),
                1,
            )
        finally:
            db.close()
        self.assertTrue(os.path.exists(b_stored_path))


POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


class TestPostgresApplicationDeleteRegression(unittest.TestCase):
    """B-1 blocker pinned against a real PostgreSQL server.

    PostgreSQL is the runtime database and it enforces foreign keys, so this
    class re-runs the delete-with-child-rows scenario against an actual
    PostgreSQL database instead of only trusting SQLite. It reuses the exact
    app-under-test, so it validates the same routers, models and cascade the
    rest of the suite exercises.

    Enablement: set POSTGRES_TEST_DATABASE_URL to a disposable PostgreSQL
    database (the harness runs create_all and drops every table in tearDown), for example:

        POSTGRES_TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/careerpilot_test

    When the variable is unset or the database is unreachable the whole class
    is skipped cleanly and the rest of the suite is unaffected.
    """

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
        db.add_all([
            Job(id="job_1", user_id=USER_A["id"], title="Backend Developer",
                company="Acme", description="Python FastAPI", required_skills="Python, FastAPI"),
            Job(id="job_2", user_id=USER_B["id"], title="Frontend Developer",
                company="Beta", description="React", required_skills="React"),
        ])
        db.commit()
        db.close()

        cls.app = FastAPI()
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

    def test_delete_application_with_events_and_interviews(self):
        resp = self.client.post("/applications", json={"job_id": "job_1", "status": "Interview"})
        self.assertEqual(resp.status_code, 201, resp.text)
        app_id = resp.json()["id"]
        resp = self.client.post(f"/applications/{app_id}/events", json={"event_type": "note_added"})
        self.assertEqual(resp.status_code, 201, resp.text)
        resp = self.client.post(
            f"/applications/{app_id}/interviews",
            json={"scheduled_at": "2026-09-10T15:00:00Z", "kind": "phone"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)

        resp = self.client.delete(f"/applications/{app_id}")
        self.assertEqual(resp.status_code, 204, resp.text)

        db = self.Session()
        try:
            self.assertEqual(db.query(Application).filter(Application.id == app_id).count(), 0)
            self.assertEqual(
                db.query(ApplicationEvent).filter(ApplicationEvent.application_id == app_id).count(),
                0,
            )
            self.assertEqual(
                db.query(ApplicationInterview).filter(ApplicationInterview.application_id == app_id).count(),
                0,
            )
            self.assertEqual(
                db.query(ApplicationDocument).filter(ApplicationDocument.application_id == app_id).count(),
                0,
            )
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()