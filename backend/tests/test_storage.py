"""Phase 5E.6 - file storage hardening tests.

Focused coverage for the centralized storage layer (app.core.storage):

- STORAGE_ROOT configuration (default + explicit)
- safe path resolution / containment (traversal, absolute paths, separators)
- generated stored filenames (UUID + validated extension)
- atomic bounded uploads with temp-file cleanup on any failure
- centralized idempotent safe deletes
- per-user isolation

plus API-level scenarios (temp directories only, never the real
backend/uploads): PDF/DOCX upload success, oversized rejection with no
partial file, extension hardening, delete semantics for uploaded vs
resume-linked vs application documents vs resumes, and no absolute paths in
API responses.
"""
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import storage
from app.core.config import Settings
from app.api.applications import router as applications_router
from app.api.resumes import router as resumes_router
from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.application_document import ApplicationDocument

USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
USER_B = {"id": "user_b", "firebase_uid": "fb_b"}

DUMMY_PDF = b"%PDF-1.4 test"  # 13 bytes
DUMMY_DOCX = b"PK\x03\x04 fake docx bytes"

UUID_RE = re.compile(r"^[0-9a-f-]{36}\.(pdf|docx)$")


class TestStorageRootConfig(unittest.TestCase):
    """STORAGE_ROOT / storage_root() resolution."""

    def test_default_root_is_backend_uploads(self):
        backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        expected = os.path.join(backend, "uploads")
        self.assertEqual(str(storage._default_storage_root().resolve()), os.path.normpath(expected))

    def test_storage_root_default_when_unset(self):
        with patch("app.core.storage.get_settings", return_value=Settings(STORAGE_ROOT="")):
            self.assertEqual(str(storage.storage_root()), str(storage._default_storage_root().resolve()))

    def test_storage_root_honors_configured_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            configured = os.path.join(tmp, "configured", "uploads")
            with patch("app.core.storage.get_settings", return_value=Settings(STORAGE_ROOT=configured)):
                self.assertEqual(str(storage.storage_root()), os.path.normpath(configured))

    def test_root_switch_isolates_user_dirs(self):
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            with patch("app.core.storage.get_settings", return_value=Settings(STORAGE_ROOT=tmp_a)):
                d1 = storage.ensure_user_dir("u1")
            with patch("app.core.storage.get_settings", return_value=Settings(STORAGE_ROOT=tmp_b)):
                d2 = storage.ensure_user_dir("u1")
            self.assertNotEqual(d1, d2)
            self.assertTrue(str(d1).startswith(os.path.normpath(tmp_a)))
            self.assertTrue(str(d2).startswith(os.path.normpath(tmp_b)))


class TestStoragePathSafety(unittest.TestCase):
    """Path containment, traversal and separator hardening."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "uploads"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ensure_user_dir_creates_user_scoped_dir(self):
        user_dir = storage.ensure_user_dir("user_1", root=self.root)
        self.assertTrue(user_dir.is_dir())
        self.assertEqual(user_dir, (self.root.resolve() / "user_1"))

    def test_ensure_user_dir_isolates_users(self):
        d1 = storage.ensure_user_dir("user_1", root=self.root)
        d2 = storage.ensure_user_dir("user_2", root=self.root)
        self.assertNotEqual(d1, d2)
        self.assertEqual(d1.name, "user_1")
        self.assertEqual(d2.name, "user_2")

    def test_user_component_cannot_escape_root(self):
        # ".." alone would resolve to the parent of the storage root.
        with self.assertRaises(ValueError):
            storage.ensure_user_dir("..", root=self.root)

    def test_traversal_like_user_component_stays_contained(self):
        # Separators are stripped, so a traversal-looking id collapses to a
        # single contained component - never an escape above the root.
        user_dir = storage.ensure_user_dir("../..", root=self.root)
        self.assertEqual(user_dir, (self.root.resolve() / "...."))

    def test_resolve_rejects_relative_traversal(self):
        self.assertIsNone(storage.resolve_user_file_path("u1", "../secret.txt", root=self.root))
        self.assertIsNone(storage.resolve_user_file_path("u1", "a/../../secret.txt", root=self.root))

    def test_resolve_rejects_absolute_path_outside_user_dir(self):
        outside = os.path.join(self.tmp, "secret.txt")
        with open(outside, "wb") as f:
            f.write(b"x")
        self.assertIsNone(storage.resolve_user_file_path("u1", outside, root=self.root))

    def test_resolve_accepts_absolute_path_inside_user_dir(self):
        # The DB stores absolute server paths; contained absolute targets are
        # accepted (needed for safe deletes).
        os.makedirs(self.root / "u1", exist_ok=True)
        target = str(self.root / "u1" / "abc.pdf")
        with open(target, "wb") as f:
            f.write(b"x")
        resolved = storage.resolve_user_file_path("u1", target, root=self.root)
        self.assertEqual(resolved, Path(target).resolve())

    def test_resolve_accepts_plain_filename(self):
        resolved = storage.resolve_user_file_path("u1", "abc.pdf", root=self.root)
        self.assertEqual(resolved, (self.root.resolve() / "u1" / "abc.pdf"))

    def test_stored_filename_is_uuid_with_normalized_extension(self):
        name = storage.safe_stored_filename(".PDF")
        self.assertRegex(name, UUID_RE)
        name2 = storage.safe_stored_filename(".pdf")
        self.assertRegex(name2, UUID_RE)
        self.assertNotEqual(name, name2)

    def test_stored_filename_strips_separators(self):
        for raw in ("/../.pdf", "..\\.pdf", "/.pdf"):
            name = storage.safe_stored_filename(raw)
            self.assertNotIn("/", name)
            self.assertNotIn("\\", name)
            self.assertRegex(name.split(".", 1)[0], r"^[0-9a-f-]{36}$")
            self.assertTrue(name.endswith(".pdf"))

    def test_sanitize_name_strips_control_and_separators(self):
        self.assertEqual(storage.sanitize_name("a../b.pdf"), "a..b.pdf")
        self.assertNotIn("\x00", storage.sanitize_name("a\x00b.pdf"))


class TestStorageAtomicUploads(unittest.TestCase):
    """Bounded streaming uploads with atomic rename and temp cleanup."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "uploads"
        self.payload = b"0123456789abcdef"  # 16 bytes

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _chunks(self):
        sent = {"done": False}

        def read():
            if sent["done"]:
                return b""
            sent["done"] = True
            return self.payload

        return read

    def _upload_dir(self):
        return self.root.resolve() / "u1"

    def _temps(self):
        if not self._upload_dir().is_dir():
            return []
        return [n for n in os.listdir(self._upload_dir()) if ".tmp-" in n]

    def test_write_upload_atomic_success_and_no_temp(self):
        fname = storage.safe_stored_filename(".pdf")
        path = storage.write_upload_atomic(
            "u1", fname, self._chunks(), max_size=1024, root=self.root
        )
        self.assertTrue(os.path.isfile(path))
        with open(path, "rb") as f:
            self.assertEqual(f.read(), self.payload)
        self.assertEqual(self._temps(), [])

    def test_write_upload_atomic_leaves_only_final_file(self):
        # The write was staged under a temp name then moved into place, so the
        # dir holds exactly the final file (no temp sibling, no partial).
        fname = storage.safe_stored_filename(".pdf")
        storage.write_upload_atomic("u1", fname, self._chunks(), max_size=1024, root=self.root)
        self.assertEqual(os.listdir(self._upload_dir()), [fname])

    def test_oversized_upload_rejected_and_cleaned(self):
        fname = storage.safe_stored_filename(".pdf")
        with self.assertRaises(ValueError):
            storage.write_upload_atomic("u1", fname, self._chunks(), max_size=10, root=self.root)
        self.assertFalse(os.path.exists(self._upload_dir() / fname))
        self.assertEqual(self._temps(), [])

    def test_no_partial_final_file_after_oversized(self):
        fname = storage.safe_stored_filename(".pdf")
        with self.assertRaises(ValueError):
            storage.write_upload_atomic("u1", fname, self._chunks(), max_size=10, root=self.root)
        # The final name must never appear with partial content.
        self.assertFalse(os.path.exists(self._upload_dir() / fname))

    def test_reader_failure_cleans_temp(self):
        calls = {"n": 0}

        def read():
            calls["n"] += 1
            if calls["n"] == 1:
                return b"AAA"
            raise OSError("simulated read failure")

        fname = storage.safe_stored_filename(".pdf")
        with self.assertRaises(OSError):
            storage.write_upload_atomic("u1", fname, read, max_size=1024, root=self.root)
        self.assertFalse(os.path.exists(self._upload_dir() / fname))
        self.assertEqual(self._temps(), [])

    def test_final_file_is_user_scoped(self):
        fname = storage.safe_stored_filename(".pdf")
        path_u1 = storage.write_upload_atomic("u1", fname, self._chunks(), max_size=1024, root=self.root)
        path_u2 = storage.write_upload_atomic("u2", fname, self._chunks(), max_size=1024, root=self.root)
        self.assertNotEqual(path_u1, path_u2)
        self.assertEqual(Path(path_u1).parent, self.root.resolve() / "u1")
        self.assertEqual(Path(path_u2).parent, self.root.resolve() / "u2")


class TestStorageSafeDeletes(unittest.TestCase):
    """Centralized, idempotent, containment-checked deletes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "uploads"
        os.makedirs(self.root / "u1", exist_ok=True)
        self.file_path = str(self.root / "u1" / "doc.pdf")
        with open(self.file_path, "wb") as f:
            f.write(b"data")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_delete_removes_file(self):
        storage.delete_file_safely("u1", self.file_path, root=self.root)
        self.assertFalse(os.path.exists(self.file_path))

    def test_delete_missing_file_is_idempotent(self):
        storage.delete_file_safely("u1", str(self.root / "u1" / "ghost.pdf"), root=self.root)
        storage.delete_file_safely("u1", str(self.root / "u1" / "ghost.pdf"), root=self.root)

    def test_delete_none_or_empty_is_noop(self):
        storage.delete_file_safely("u1", None, root=self.root)
        storage.delete_file_safely("u1", "", root=self.root)
        self.assertTrue(os.path.exists(self.file_path))

    def test_delete_absolute_path_outside_root_is_legacy_recorded(self):
        # A server-recorded absolute path from an earlier STORAGE_ROOT is still
        # removed for its owner (matches the pre-5E.6 delete contract).
        legacy = os.path.join(self.tmp, "legacy.pdf")
        with open(legacy, "wb") as f:
            f.write(b"old")
        storage.delete_file_safely("u1", legacy, root=self.root)
        self.assertFalse(os.path.exists(legacy))

    def test_delete_neutralizes_traversal_still_contained(self):
        # The same file reached through a traversal that still resolves inside
        # the user dir is a legitimate contained delete.
        traversal = os.path.join(self.root, "u1", "..", "u1", "doc.pdf")
        storage.delete_file_safely("u1", traversal, root=self.root)
        self.assertFalse(os.path.exists(self.file_path))

    def test_cross_user_delete_is_blocked(self):
        other = self.root / "u2"
        os.makedirs(other, exist_ok=True)
        other_file = str(other / "doc2.pdf")
        with open(other_file, "wb") as f:
            f.write(b"other")
        storage.delete_file_safely("u1", other_file, root=self.root)
        self.assertTrue(os.path.exists(other_file))


class _StorageAPIHarness:
    """FastAPI harness with file-backed SQLite and auth override, mirroring the
    application-pipeline test harness. All upload paths are redirected to a
    temp directory (never the real backend/uploads)."""

    def __init__(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        db = self.Session()
        db.add_all([
            User(id=USER_A["id"], firebase_uid=USER_A["firebase_uid"], email="a@test.com", name="A"),
            User(id=USER_B["id"], firebase_uid=USER_B["firebase_uid"], email="b@test.com", name="B"),
        ])
        db.add_all([
            Job(id="job_1", user_id=USER_A["id"], title="Backend Developer",
                company="Acme", description="Python FastAPI", required_skills="Python"),
        ])
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(applications_router)
        self.app.include_router(resumes_router)
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

        self.uploads_dir = os.path.join(self.tmpdir, "uploads")
        self.uploads_patch = patch("app.api.applications.UPLOAD_DIR", self.uploads_dir)
        self.uploads_patch.start()
        self.resumes_patch = patch("app.api.resumes.UPLOAD_DIR", self.uploads_dir)
        self.resumes_patch.start()

    def close(self):
        self.uploads_patch.stop()
        self.resumes_patch.stop()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def create_application(self, app_id="app_a", user_id=USER_A["id"]):
        db = self.Session()
        db.add(Application(id=app_id, user_id=user_id, job_id="job_1", status="Applied"))
        db.commit()
        db.close()

    def seed_resume(self, resume_id="res_a", filename="resume.pdf"):
        file_path = os.path.join(self.uploads_dir, USER_A["id"], filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(DUMMY_PDF)
        db = self.Session()
        db.add(Resume(
            id=resume_id, user_id=USER_A["id"], filename=filename,
            original_filename=filename, file_path=file_path, file_size="13",
            is_master=False, parsing_status="completed",
        ))
        db.commit()
        db.close()

    def uploaded_files(self, user_id=USER_A["id"]):
        user_dir = os.path.join(self.uploads_dir, user_id)
        if not os.path.isdir(user_dir):
            return []
        return os.listdir(user_dir)


class TestStorageAPI(unittest.TestCase):
    """API-level storage scenarios (temp uploads dir only)."""

    def setUp(self):
        self.h = _StorageAPIHarness()

    def tearDown(self):
        self.h.close()

    def test_upload_pdf_success(self):
        self.h.create_application()
        resp = self.h.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("resume.pdf", DUMMY_PDF, "application/pdf")},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        files = self.h.uploaded_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], resp.json()["filename"])
        self.assertTrue(files[0].endswith(".pdf"))

    def test_upload_docx_success(self):
        self.h.create_application()
        resp = self.h.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("cover.docx", DUMMY_DOCX,
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        self.assertTrue(resp.json()["filename"].endswith(".docx"))

    def test_upload_rejects_unsupported_extension(self):
        self.h.create_application()
        resp = self.h.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("evil.pdf.exe", DUMMY_PDF, "application/pdf")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("files are allowed", resp.json()["detail"])
        self.assertEqual(self.h.uploaded_files(), [])

    def test_upload_rejects_oversized_no_partial_file(self):
        self.h.create_application()
        with patch("app.api.applications.MAX_UPLOAD_SIZE", 10):
            resp = self.h.client.post(
                "/applications/app_a/documents/upload",
                files={"file": ("big.pdf", b"x" * 20, "application/pdf")},
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("10MB", resp.json()["detail"])
        self.assertEqual(self.h.uploaded_files(), [])

    def test_upload_response_has_no_absolute_paths(self):
        self.h.create_application()
        resp = self.h.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("my resume.pdf", DUMMY_PDF, "application/pdf")},
        )
        body = resp.json()
        self.assertNotIn("file_path", body)
        self.assertRegex(body["filename"], UUID_RE)
        self.assertEqual(body["original_filename"], "my resume.pdf")

    def test_original_filename_is_basename_only(self):
        from app.api.applications import _sanitize_original_filename
        self.assertEqual(_sanitize_original_filename("../evil.pdf"), "evil.pdf")
        self.assertEqual(_sanitize_original_filename("..\\..\\evil.pdf"), "evil.pdf")
        self.assertEqual(_sanitize_original_filename("a/../b.pdf"), "b.pdf")
        self.assertEqual(_sanitize_original_filename("a\x00b.pdf"), "ab.pdf")
        self.assertEqual(_sanitize_original_filename(None), "")
        self.assertEqual(_sanitize_original_filename(""), "")

    def test_document_delete_removes_its_own_file(self):
        self.h.create_application()
        upload = self.h.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("resume.pdf", DUMMY_PDF, "application/pdf")},
        )
        doc_id = upload.json()["id"]
        stored_name = upload.json()["filename"]
        self.assertEqual(self.h.uploaded_files(), [stored_name])
        resp = self.h.client.delete(f"/applications/app_a/documents/{doc_id}")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.h.uploaded_files(), [])

    def test_resume_linked_document_delete_keeps_resume_file(self):
        self.h.create_application()
        self.h.seed_resume(resume_id="res_a", filename="linked_resume.pdf")
        attach = self.h.client.post(
            "/applications/app_a/documents",
            json={"document_type": "resume", "source_resume_id": "res_a"},
        )
        self.assertEqual(attach.status_code, 201, attach.text)
        self.assertIsNotNone(attach.json()["source_resume_id"])
        doc_id = attach.json()["id"]
        resp = self.h.client.delete(f"/applications/app_a/documents/{doc_id}")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.h.uploaded_files(), ["linked_resume.pdf"])

    def test_application_delete_removes_uploaded_document_files(self):
        self.h.create_application()
        upload = self.h.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("resume.pdf", DUMMY_PDF, "application/pdf")},
        )
        self.assertEqual(len(self.h.uploaded_files()), 1)
        resp = self.h.client.delete("/applications/app_a")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.h.uploaded_files(), [])

    def test_resume_delete_removes_stored_file(self):
        self.h.seed_resume(resume_id="res_a", filename="delete_me.pdf")
        self.assertEqual(self.h.uploaded_files(), ["delete_me.pdf"])
        resp = self.h.client.delete("/resumes/res_a")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.h.uploaded_files(), [])

    def test_upload_is_isolated_per_user(self):
        self.h.create_application()
        upload = self.h.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("resume.pdf", DUMMY_PDF, "application/pdf")},
        )
        doc_id = upload.json()["id"]
        self.h.current_user_id = USER_B["id"]
        self.assertEqual(
            self.h.client.delete(f"/applications/app_a/documents/{doc_id}").status_code, 404
        )
        self.assertEqual(self.h.client.get("/applications/app_a/documents").status_code, 404)
        self.assertEqual(len(self.h.uploaded_files(USER_A["id"])), 1)

    def test_response_schema_omits_file_path_while_db_stores_it(self):
        # file_path stays server-side: absent from responses yet present on the
        # stored row (absolute, so deletes remain scoped and resolvable).
        self.h.create_application()
        upload = self.h.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("resume.pdf", DUMMY_PDF, "application/pdf")},
        )
        db = self.h.Session()
        try:
            doc = db.query(ApplicationDocument).filter_by(id=upload.json()["id"]).first()
            self.assertIsNotNone(doc)
            self.assertEqual(doc.filename, upload.json()["filename"])
            self.assertTrue(os.path.isabs(doc.file_path))
            self.assertTrue(os.path.isfile(doc.file_path))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()