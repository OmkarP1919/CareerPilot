import os
import tempfile
import shutil
import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from pydantic import ValidationError

from app.database.base import Base
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.application_event import ApplicationEvent
from app.models.application_interview import ApplicationInterview
from app.models.application_document import ApplicationDocument
from app.schemas.application_pipeline import (
    ApplicationEventCreate,
    ApplicationEventResponse,
    ApplicationInterviewCreate,
    ApplicationDocumentCreate,
    ApplicationDocumentResponse,
    ApplicationTimelineResponse,
    EventTimelineEntry,
    InterviewTimelineEntry,
    DocumentTimelineEntry,
)

# Every table the ORM is expected to produce: the pre-existing tables plus
# exactly the three new Phase 5D tables. This asserts create_all() followed the
# "add ONLY new tables" rule - nothing was renamed, dropped, or added beyond
# the approved set.
PRE_EXISTING_TABLES = {
    "users",
    "profiles",
    "education",
    "skills",
    "user_skills",
    "projects",
    "experiences",
    "certifications",
    "resumes",
    "jobs",
    "job_matches",
    "resume_job_analyses",
    "tailored_resumes",
    "cover_letters",
    "applications",
    "saved_searches",
}

NEW_TABLES = {
    "application_events",
    "application_interviews",
    "application_documents",
}

# test_resume_delete_upload.py registers this test-only table on the shared
# Base.metadata; it is a pre-existing artifact of the test suite, not a
# production model. Tolerated explicitly so create_all() tampering is still
# caught in full-suite runs.
KNOWN_TEST_ONLY_TABLES = {"extra_dependents"}


def utcnow():
    return datetime.now(timezone.utc)


class TestApplicationPipelineModels(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "pipeline.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        self.user = User(id="user_a", firebase_uid="fb_a", email="a@test.com", name="A")
        other_user = User(id="user_b", firebase_uid="fb_b", email="b@test.com", name="B")
        self.job = Job(
            id="job_1", user_id="user_a", title="Backend Developer",
            company="Acme", description="Python FastAPI", required_skills="Python",
        )
        self.app = Application(user_id="user_a", job_id="job_1", status="Saved")
        db.add_all([self.user, other_user, self.job, self.app])
        db.commit()
        self.app_id = self.app.id
        db.close()

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _session(self):
        return self.Session()

    def test_create_all_produces_only_new_tables(self):
        tables = set(inspect(self.engine).get_table_names())

        # All pre-existing tables survive unrenamed and unremoved...
        self.assertTrue(PRE_EXISTING_TABLES <= tables)
        # ...and the three new tables are created.
        self.assertTrue(NEW_TABLES <= tables)

        # No table exists beyond pre-existing + new + the pre-existing
        # test-only artifact. This proves nothing ELSE was added or renamed.
        unexpected = tables - PRE_EXISTING_TABLES - NEW_TABLES - KNOWN_TEST_ONLY_TABLES
        self.assertEqual(unexpected, set())

    def test_new_tables_have_expected_columns(self):
        insp = inspect(self.engine)
        event_cols = {c["name"] for c in insp.get_columns("application_events")}
        self.assertEqual(
            event_cols,
            {"id", "application_id", "user_id", "event_type", "notes",
             "created_by", "metadata", "created_at"},
        )
        interview_cols = {c["name"] for c in insp.get_columns("application_interviews")}
        self.assertEqual(
            interview_cols,
            {"id", "application_id", "user_id", "scheduled_at", "kind",
             "status", "notes", "created_at", "updated_at"},
        )
        doc_cols = {c["name"] for c in insp.get_columns("application_documents")}
        self.assertEqual(
            doc_cols,
            {"id", "application_id", "user_id", "document_type", "name",
             "filename", "original_filename", "file_path", "file_size",
             "source_resume_id", "metadata", "created_at", "updated_at"},
        )

    def test_event_creation_ownership_and_json_metadata(self):
        db = self._session()
        event = ApplicationEvent(
            application_id=self.app_id,
            user_id="user_a",
            event_type="status_changed",
            notes="Moved to Interview",
            created_by="user_a",
            meta_data={"from_status": "Applied", "to_status": "Interview"},
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        self.assertTrue(event.id)
        self.assertEqual(event.application_id, self.app_id)
        self.assertEqual(event.user_id, "user_a")
        self.assertEqual(event.event_type, "status_changed")
        self.assertEqual(event.notes, "Moved to Interview")
        self.assertEqual(event.created_by, "user_a")
        self.assertEqual(event.meta_data, {"from_status": "Applied", "to_status": "Interview"})
        self.assertIsNotNone(event.created_at)
        db.close()

    def test_event_required_fields(self):
        db = self._session()
        missing_type = ApplicationEvent(application_id=self.app_id, user_id="user_a")
        db.add(missing_type)
        with self.assertRaises(Exception):
            db.commit()
        db.rollback()
        db.close()

    def test_event_belongs_to_application_relationship(self):
        db = self._session()
        event = ApplicationEvent(
            application_id=self.app_id, user_id="user_a", event_type="created"
        )
        db.add(event)
        db.flush()
        self.assertEqual(event.application.id, self.app_id)
        self.assertTrue(event.application is db.get(Application, self.app_id))
        db.close()

    def test_interview_creation_and_default_status(self):
        db = self._session()
        interview = ApplicationInterview(
            application_id=self.app_id,
            user_id="user_a",
            scheduled_at=utcnow(),
            kind="video",
            notes="Hiring manager round",
        )
        db.add(interview)
        db.commit()
        db.refresh(interview)

        self.assertTrue(interview.id)
        self.assertEqual(interview.status, "scheduled")
        self.assertEqual(interview.kind, "video")
        self.assertEqual(interview.notes, "Hiring manager round")
        self.assertIsNotNone(interview.scheduled_at)
        self.assertIsNotNone(interview.created_at)
        self.assertIsNotNone(interview.updated_at)
        db.close()

    def test_interview_requires_scheduled_at(self):
        db = self._session()
        missing_sched = ApplicationInterview(
            application_id=self.app_id, user_id="user_a", kind="phone"
        )
        db.add(missing_sched)
        with self.assertRaises(Exception):
            db.commit()
        db.rollback()
        db.close()

    def test_interview_updated_at_advances_on_updates(self):
        db = self._session()
        interview = ApplicationInterview(
            application_id=self.app_id, user_id="user_a",
            scheduled_at=utcnow(), kind="phone",
        )
        db.add(interview)
        db.commit()
        original_updated_at = interview.updated_at

        interview.notes = "Rescheduled to Friday"
        db.commit()
        db.refresh(interview)
        self.assertNotEqual(interview.updated_at, original_updated_at)
        # SQLite returns naive UTC datetimes; compare against naive UTC now().
        naive_utc_now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        self.assertGreaterEqual(interview.updated_at, naive_utc_now)
        db.close()

    def test_interview_shape_supports_lifecycle_states(self):
        # Lifecycle states must be representable without touching the parent
        # application's status - the table is decoupled from notifications.
        db = self._session()
        for status in ["scheduled", "rescheduled", "completed", "cancelled"]:
            interview = ApplicationInterview(
                application_id=self.app_id, user_id="user_a",
                scheduled_at=utcnow(), kind="onsite", status=status,
            )
            db.add(interview)
        db.commit()
        saved = (
            db.query(ApplicationInterview)
            .filter(ApplicationInterview.application_id == self.app_id)
            .order_by(ApplicationInterview.created_at)
            .all()
        )
        self.assertEqual([i.status for i in saved], ["scheduled", "rescheduled", "completed", "cancelled"])
        db.close()

    def test_interview_belongs_to_application_relationship(self):
        db = self._session()
        interview = ApplicationInterview(
            application_id=self.app_id, user_id="user_a",
            scheduled_at=utcnow(), kind="video",
        )
        db.add(interview)
        db.flush()
        self.assertEqual(interview.application.id, self.app_id)
        db.close()

    def test_document_uploaded_file_representation(self):
        db = self._session()
        doc = ApplicationDocument(
            application_id=self.app_id,
            user_id="user_a",
            document_type="cover_letter",
            name="Cover letter - Acme",
            filename="abc123.pdf",
            original_filename="coverletter.pdf",
            file_path=os.path.join(self.tmpdir, "uploads", "user_a", "abc123.pdf"),
            file_size="2048",
            meta_data={"source": "upload"},
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        self.assertTrue(doc.id)
        self.assertEqual(doc.application_id, self.app_id)
        self.assertEqual(doc.user_id, "user_a")
        self.assertEqual(doc.document_type, "cover_letter")
        self.assertEqual(doc.filename, "abc123.pdf")
        self.assertEqual(doc.original_filename, "coverletter.pdf")
        self.assertTrue(doc.file_path.endswith("abc123.pdf"))
        self.assertEqual(doc.file_size, "2048")
        self.assertEqual(doc.meta_data, {"source": "upload"})
        self.assertIsNone(doc.source_resume_id)
        db.close()

    def test_document_source_resume_reference_representation(self):
        db = self._session()
        resume = Resume(
            user_id="user_a", filename="master.pdf", original_filename="master.pdf",
            file_path="uploads/user_a/master.pdf", is_master=True,
            parsing_status="parsed",
        )
        db.add(resume)
        db.flush()

        doc = ApplicationDocument(
            application_id=self.app_id,
            user_id="user_a",
            document_type="resume",
            name="Master resume",
            source_resume_id=resume.id,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        self.assertEqual(doc.source_resume_id, resume.id)
        self.assertEqual(doc.source_resume.id, resume.id)
        self.assertIsNone(doc.file_path)
        db.close()

    def test_document_requires_application_and_user(self):
        db = self._session()
        missing_owner = ApplicationDocument(application_id=self.app_id)
        db.add(missing_owner)
        with self.assertRaises(Exception):
            db.commit()
        db.rollback()
        db.close()

    def test_ownership_fields_queryable_by_user(self):
        db = self._session()
        db.add_all([
            ApplicationEvent(application_id=self.app_id, user_id="user_a", event_type="created"),
            ApplicationEvent(application_id=self.app_id, user_id="user_b", event_type="note_added"),
            ApplicationInterview(application_id=self.app_id, user_id="user_a", scheduled_at=utcnow(), kind="phone"),
            ApplicationInterview(application_id=self.app_id, user_id="user_b", scheduled_at=utcnow(), kind="video"),
            ApplicationDocument(application_id=self.app_id, user_id="user_a", document_type="resume"),
            ApplicationDocument(application_id=self.app_id, user_id="user_b", document_type="other"),
        ])
        db.commit()

        events = db.query(ApplicationEvent).filter(ApplicationEvent.user_id == "user_a").all()
        interviews = db.query(ApplicationInterview).filter(ApplicationInterview.user_id == "user_b").all()
        docs = db.query(ApplicationDocument).filter(ApplicationDocument.user_id == "user_a").all()
        self.assertEqual(len(events), 1)
        self.assertEqual(len(interviews), 1)
        self.assertEqual(len(docs), 1)
        db.close()


class TestApplicationPipelineSchemas(unittest.TestCase):
    def test_event_create_requires_event_type(self):
        with self.assertRaises(ValidationError):
            ApplicationEventCreate()

    def test_event_create_accepts_metadata_dict(self):
        payload = ApplicationEventCreate(
            event_type="status_changed",
            metadata={"from_status": "Saved", "to_status": "Applied"},
        )
        self.assertEqual(payload.event_type, "status_changed")
        self.assertEqual(payload.metadata["to_status"], "Applied")

    def test_event_response_serializes_orm_with_metadata_alias(self):
        class FakeEvent:
            id = "e1"
            application_id = "a1"
            user_id = "u1"
            event_type = "created"
            notes = "note"
            created_by = "u1"
            meta_data = {"k": "v"}
            created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        resp = ApplicationEventResponse.model_validate(FakeEvent())
        body = resp.model_dump()
        self.assertEqual(body["metadata"], {"k": "v"})
        self.assertEqual(body["event_type"], "created")

    def test_interview_create_default_status(self):
        payload = ApplicationInterviewCreate(
            scheduled_at=utcnow(), kind="onsite", notes="Panel"
        )
        self.assertEqual(payload.status, "scheduled")
        self.assertEqual(payload.notes, "Panel")

    def test_interview_create_requires_scheduled_at_and_kind(self):
        with self.assertRaises(ValidationError):
            ApplicationInterviewCreate()
        with self.assertRaises(ValidationError):
            ApplicationInterviewCreate(scheduled_at=utcnow())

    def test_document_create_default_type(self):
        payload = ApplicationDocumentCreate(source_resume_id="r1")
        self.assertEqual(payload.document_type, "other")
        self.assertEqual(payload.source_resume_id, "r1")
        self.assertIsNone(payload.name)

    def test_document_response_serializes_orm_with_metadata_alias(self):
        class FakeDoc:
            id = "d1"
            application_id = "a1"
            user_id = "u1"
            document_type = "resume"
            name = None
            filename = "f.pdf"
            original_filename = "f.pdf"
            file_path = "/tmp/f.pdf"
            file_size = "100"
            source_resume_id = None
            meta_data = {"m": 1}
            created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        resp = ApplicationDocumentResponse.model_validate(FakeDoc())
        body = resp.model_dump()
        self.assertEqual(body["metadata"], {"m": 1})
        self.assertEqual(body["filename"], "f.pdf")

    def test_timeline_discriminated_union(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        timeline = ApplicationTimelineResponse(
            application_id="a1",
            user_id="u1",
            entries=[
                EventTimelineEntry(id="e1", application_id="a1", user_id="u1", kind="event",
                                   event_type="created", notes="started", created_at=now),
                InterviewTimelineEntry(id="i1", application_id="a1", user_id="u1", kind="interview",
                                       scheduled_at=now, interview_kind="video", status="scheduled",
                                       notes="round 1", created_at=now),
                DocumentTimelineEntry(id="d1", application_id="a1", user_id="u1", kind="document",
                                      document_type="resume", name="master", created_at=now),
            ],
        )
        kinds = [type(e).__name__ for e in timeline.entries]
        self.assertEqual(kinds, ["EventTimelineEntry", "InterviewTimelineEntry", "DocumentTimelineEntry"])
        self.assertTrue(hasattr(timeline.entries[1], "scheduled_at"))
        self.assertTrue(hasattr(timeline.entries[2], "document_type"))

    def test_timeline_rejects_unknown_kind(self):
        with self.assertRaises(ValidationError):
            EventTimelineEntry(
                id="x", application_id="a1", user_id="u1", kind="interview",
                event_type="whatever", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()