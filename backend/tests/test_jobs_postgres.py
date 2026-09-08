"""Phase 5E.4 PostgreSQL-gated job-delete integrity test.

Gated on ``POSTGRES_TEST_DATABASE_URL`` (existing suite convention): the class
SKIPS when it is unset, unreachable, or not PostgreSQL. It NEVER touches the
application's normal ``DATABASE_URL``.

Purpose: the /jobs delete guard must be deterministic on a constraint-enforcing
database. SQLite ignores foreign keys by default, which is exactly what masked
the bug; PostgreSQL enforces them. This test drives the real FastAPI DELETE
route against live PostgreSQL and asserts the guarded 409 (not a 500
ForeignKeyViolation) and the successful 204 for unreferenced jobs.

Only the tables the test needs are created, and they are created the SQLAlchemy
way (additive, ``IF NOT EXISTS``). Tables that already existed are left alone;
tables the test created are dropped afterwards.
"""

import os
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import sessionmaker

from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.models.job_match import JobMatch
from app.api.jobs import router as jobs_router

POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")

# Tables this test needs, in FK-safe creation order.
_NEEDED_TABLES = [JobMatch.__table__, Application.__table__, Job.__table__, User.__table__]
_NEEDED_NAMES = {t.name for t in _NEEDED_TABLES}


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "POSTGRES_TEST_DATABASE_URL is not set",
)
class TestPostgresJobDeleteIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = POSTGRES_TEST_DATABASE_URL
        parsed = make_url(cls.url)
        if parsed.get_backend_name() not in ("postgresql", "postgres"):
            raise unittest.SkipTest("POSTGRES_TEST_DATABASE_URL is not PostgreSQL")
        cls.engine = create_engine(cls.url, pool_pre_ping=True)
        try:
            cls.engine.connect().close()
        except Exception as exc:
            cls.engine.dispose()
            raise unittest.SkipTest(
                f"PostgreSQL test database unreachable ({exc.__class__.__name__}): {exc}"
            )

        before = set(inspect(cls.engine).get_table_names())
        cls._created_tables = list(_NEEDED_NAMES - before)
        Base.metadata.create_all(cls.engine, tables=_NEEDED_TABLES)

        cls.Session = sessionmaker(bind=cls.engine)

        with cls.engine.begin() as conn:
            conn.execute(text("TRUNCATE applications, job_matches, jobs, users RESTART IDENTITY CASCADE"))

    @classmethod
    def tearDownClass(cls):
        try:
            with cls.engine.begin() as conn:
                conn.execute(text("TRUNCATE applications, job_matches, jobs, users RESTART IDENTITY CASCADE"))
            if cls._created_tables:
                with cls.engine.begin() as conn:
                    conn.execute(
                        text("DROP TABLE IF EXISTS applications, job_matches, jobs, users CASCADE")
                    )
        finally:
            cls.engine.dispose()

    def _make_app(self, current_user_id: str) -> TestClient:
        app = FastAPI()
        app.include_router(jobs_router)

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            session = self.Session()
            try:
                return session.query(User).filter(User.id == current_user_id).first()
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user
        return TestClient(app, raise_server_exceptions=False)

    def _seed_user(self, user_id, fb_uid, email):
        db = self.Session()
        if db.query(User).filter(User.id == user_id).first() is None:
            db.add(User(id=user_id, firebase_uid=fb_uid, email=email, name=user_id))
            db.commit()
        db.close()

    def _seed_job(self, job_id, user_id):
        db = self.Session()
        db.add(Job(
            id=job_id, user_id=user_id, title=f"{job_id} title", company="Acme",
            description="desc", required_skills="python",
        ))
        db.commit()
        db.close()

    def _seed_application(self, app_id, job_id, user_id):
        db = self.Session()
        db.add(Application(id=app_id, user_id=user_id, job_id=job_id, status="Applied"))
        db.commit()
        db.close()

    def test_delete_job_with_application_returns_409_not_500(self):
        self._seed_user("pg_user_a", "pg_fb_a", "a@pg.test")
        self._seed_job("pg_job_1", "pg_user_a")
        self._seed_application("pg_app_1", "pg_job_1", "pg_user_a")

        client = self._make_app("pg_user_a")
        resp = client.delete("/jobs/pg_job_1")
        self.assertEqual(resp.status_code, 409, f"expected 409, got {resp.status_code}: {resp.text}")
        self.assertIn("applications", resp.json()["detail"])

        db = self.Session()
        try:
            self.assertIsNotNone(db.query(Job).filter(Job.id == "pg_job_1").first(), "job must survive")
            self.assertIsNotNone(
                db.query(Application).filter(Application.id == "pg_app_1").first(),
                "application history must survive",
            )
        finally:
            db.close()

    def test_delete_job_with_match_returns_409_not_500(self):
        self._seed_user("pg_user_b", "pg_fb_b", "b@pg.test")
        self._seed_job("pg_job_2", "pg_user_b")
        db = self.Session()
        db.add(JobMatch(id="pg_m_1", user_id="pg_user_b", job_id="pg_job_2", overall_score=90, role_score=90))
        db.commit()
        db.close()

        client = self._make_app("pg_user_b")
        resp = client.delete("/jobs/pg_job_2")
        self.assertEqual(resp.status_code, 409, f"expected 409, got {resp.status_code}: {resp.text}")
        self.assertIn("job_matches", resp.json()["detail"])

    def test_delete_unreferenced_job_succeeds_on_postgres(self):
        self._seed_user("pg_user_c", "pg_fb_c", "c@pg.test")
        self._seed_job("pg_job_3", "pg_user_c")

        client = self._make_app("pg_user_c")
        resp = client.delete("/jobs/pg_job_3")
        self.assertEqual(resp.status_code, 204, f"expected 204, got {resp.status_code}: {resp.text}")

        db = self.Session()
        try:
            self.assertIsNone(db.query(Job).filter(Job.id == "pg_job_3").first())
        finally:
            db.close()

    def test_non_owner_delete_is_404_on_postgres(self):
        self._seed_user("pg_user_d", "pg_fb_d", "d@pg.test")
        self._seed_user("pg_user_e", "pg_fb_e", "e@pg.test")
        self._seed_job("pg_job_4", "pg_user_d")

        client = self._make_app("pg_user_e")
        resp = client.delete("/jobs/pg_job_4")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()