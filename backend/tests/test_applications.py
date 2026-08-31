import os
import tempfile
import shutil
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.api.applications import router as applications_router


class TestApplicationCRUDAndIsolation(unittest.TestCase):
    USER_A = {"id": "user_a", "firebase_uid": "fb_a"}
    USER_B = {"id": "user_b", "firebase_uid": "fb_b"}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "apps.db")
        self.engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        db.add_all([
            User(id=self.USER_A["id"], firebase_uid=self.USER_A["firebase_uid"], email="a@test.com", name="A"),
            User(id=self.USER_B["id"], firebase_uid=self.USER_B["firebase_uid"], email="b@test.com", name="B"),
        ])
        # Jobs are a global catalog; both users can discover the same job.
        self.job = Job(id="job_1", user_id=self.USER_A["id"], title="Backend Developer",
                       company="Acme", description="Python FastAPI",
                       required_skills="Python, FastAPI")
        db.add(self.job)
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(applications_router)

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
        self.engine.dispose()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def create_app(self, job_id="job_1", status="Saved", notes=None):
        body = {"job_id": job_id, "status": status}
        if notes is not None:
            body["notes"] = notes
        resp = self.client.post("/applications", json=body)
        assert resp.status_code == 201, resp.text
        return resp.json()

    def test_create_application(self):
        app = self.create_app(status="Saved", notes="Phone screen scheduled")
        self.assertEqual(app["status"], "Saved")
        self.assertEqual(app["job_id"], "job_1")
        self.assertEqual(app["user_id"], self.USER_A["id"])
        self.assertEqual(app["job_title"], "Backend Developer")

    def test_duplicate_application_for_same_job_is_rejected(self):
        self.create_app()
        resp = self.client.post("/applications", json={"job_id": "job_1", "status": "Saved"})
        self.assertEqual(resp.status_code, 400)

    def test_invalid_status_rejected(self):
        resp = self.client.post(
            "/applications", json={"job_id": "job_1", "status": "NotARealStatus"}
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_for_missing_job_404(self):
        resp = self.client.post("/applications", json={"job_id": "nope", "status": "Saved"})
        self.assertEqual(resp.status_code, 404)

    def test_update_own_application_status_and_notes(self):
        app = self.create_app()
        resp = self.client.put(
            f"/applications/{app['id']}",
            json={"status": "Interview", "notes": "Panel round next week"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "Interview")
        self.assertEqual(body["notes"], "Panel round next week")

    def test_list_filters_different_users(self):
        self.create_app()  # created as user A
        self.current_user_id = self.USER_B["id"]
        # B creates their own application for the same (global) job
        self.client.post("/applications", json={"job_id": "job_1", "status": "Applied"})

        # Each user listing must only show their own rows.
        all_apps = self.client.get("/applications").json()
        self.assertEqual(len(all_apps), 1)
        self.assertEqual(all_apps[0]["user_id"], self.USER_B["id"])

    def test_list_status_filter(self):
        a = self.create_app(status="Saved")
        self.client.put(f"/applications/{a['id']}", json={"status": "Applied"})
        resp = self.client.get("/applications").json()
        self.assertEqual([x["status"] for x in resp], ["Applied"])
        resp = self.client.get("/applications", params={"status": "Interview"}).json()
        self.assertEqual(resp, [])

    def test_cannot_update_another_users_application(self):
        app = self.create_app()  # created by A
        self.current_user_id = self.USER_B["id"]
        resp = self.client.put(f"/applications/{app['id']}", json={"status": "Interview"})
        self.assertEqual(resp.status_code, 404)

    def test_cannot_delete_another_users_application(self):
        app = self.create_app()  # created by A
        self.current_user_id = self.USER_B["id"]
        resp = self.client.delete(f"/applications/{app['id']}")
        self.assertEqual(resp.status_code, 404)

    def test_delete_application_does_not_delete_job(self):
        app = self.create_app()
        resp = self.client.delete(f"/applications/{app['id']}")
        self.assertEqual(resp.status_code, 204)

        # Application row gone...
        resp = self.client.get("/applications").json()
        self.assertEqual(resp, [])
        # ...but the global job must still exist.
        db = self.Session()
        try:
            job = db.query(Job).filter(Job.id == "job_1").first()
        finally:
            db.close()
        self.assertIsNotNone(job)
        self.assertEqual(job.title, "Backend Developer")

    def test_delete_nonexistent_application_404(self):
        resp = self.client.delete("/applications/nope")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
