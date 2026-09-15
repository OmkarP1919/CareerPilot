"""Phase 5E.2 - explicit database schema initialization.

These tests verify the schema-init operation without requiring a live
PostgreSQL server: SQLite in-memory coverage is used for deterministic schema
creation + idempotence, and the application-engine + CLI paths are exercised
with the real ``Base``/engine objects and mocked ``create_all``.
"""

import unittest
from unittest import mock

from sqlalchemy import create_engine, inspect

from app import models as app_models  # noqa: F401  (mirrors model registration)
from app.database import init as cli
from app.database.base import Base, engine
from app.database.schema_init import init_schema

EXPECTED_TABLES = {
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
    "application_events",
    "application_interviews",
    "application_documents",
    "saved_searches",
}


class TestSchemaRegistration(unittest.TestCase):
    def test_complete_application_model_set_is_registered(self):
        registered = set(Base.metadata.tables.keys())
        self.assertTrue(EXPECTED_TABLES.issubset(registered), "\nmissing: " + str(sorted(EXPECTED_TABLES - registered)))


class TestInitSchemaSQLite(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

    def test_creates_complete_expected_schema(self):
        tables = set(init_schema(bind=self.engine))
        self.assertTrue(EXPECTED_TABLES.issubset(tables), "missing: " + str(sorted(EXPECTED_TABLES - tables)))
        created = set(inspect(self.engine).get_table_names())
        self.assertTrue(EXPECTED_TABLES.issubset(created))
        # Everything registered on Base.metadata in this process (including any
        # test-only tables like extra_dependents) is materialized.
        self.assertEqual(created, set(Base.metadata.tables.keys()))

    def test_repeated_initialization_is_idempotent(self):
        first = init_schema(bind=self.engine)
        second = init_schema(bind=self.engine)
        self.assertEqual(first, second)
        self.assertEqual(set(inspect(self.engine).get_table_names()), set(Base.metadata.tables.keys()))


class TestAdditiveSchemaEvolution(unittest.TestCase):
    """Phase 7.0D.3: Verify controlled additive column evolution."""

    def test_fresh_db_creates_required_columns(self):
        engine = create_engine("sqlite:///:memory:")
        init_schema(bind=engine)
        insp = inspect(engine)

        jm_cols = {c["name"] for c in insp.get_columns("job_matches")}
        self.assertIn("work_mode_score", jm_cols)
        self.assertIn("education_score", jm_cols)
        self.assertIn("score_version", jm_cols)

        rja_cols = {c["name"] for c in insp.get_columns("resume_job_analyses")}
        self.assertIn("score_version", rja_cols)

    def test_existing_db_without_new_columns_receives_them_and_preserves_data(self):
        engine = create_engine("sqlite:///:memory:")
        # Simulate an existing production database before Phase 7.0D.3
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE job_matches (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    job_id VARCHAR NOT NULL,
                    overall_score INTEGER NOT NULL,
                    skills_score INTEGER,
                    role_score INTEGER,
                    location_score INTEGER,
                    experience_score INTEGER,
                    project_score INTEGER
                )
            """))
            conn.execute(text("""
                CREATE TABLE resume_job_analyses (
                    id VARCHAR PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    resume_id VARCHAR NOT NULL,
                    job_id VARCHAR NOT NULL,
                    overall_score INTEGER NOT NULL
                )
            """))
            conn.execute(text("""
                INSERT INTO job_matches (id, user_id, job_id, overall_score, skills_score)
                VALUES ('jm_old', 'u1', 'j1', 85, 90)
            """))
            conn.execute(text("""
                INSERT INTO resume_job_analyses (id, user_id, resume_id, job_id, overall_score)
                VALUES ('rja_old', 'u1', 'r1', 'j1', 75)
            """))

        # Before migration: verify columns are missing
        insp_before = inspect(engine)
        jm_cols_before = {c["name"] for c in insp_before.get_columns("job_matches")}
        self.assertNotIn("work_mode_score", jm_cols_before)
        self.assertNotIn("education_score", jm_cols_before)
        self.assertNotIn("score_version", jm_cols_before)

        # Run controlled additive evolution
        init_schema(bind=engine)

        # After migration: verify columns exist
        insp_after = inspect(engine)
        jm_cols_after = {c["name"] for c in insp_after.get_columns("job_matches")}
        self.assertIn("work_mode_score", jm_cols_after)
        self.assertIn("education_score", jm_cols_after)
        self.assertIn("score_version", jm_cols_after)

        rja_cols_after = {c["name"] for c in insp_after.get_columns("resume_job_analyses")}
        self.assertIn("score_version", rja_cols_after)

        # Verify existing data is preserved and score_version defaults to NULL
        with engine.connect() as conn:
            row = conn.execute(text("SELECT id, overall_score, score_version FROM job_matches WHERE id = 'jm_old'")).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "jm_old")
            self.assertEqual(row[1], 85)
            self.assertIsNone(row[2])  # Existing rows remain NULL

            rja_row = conn.execute(text("SELECT id, overall_score, score_version FROM resume_job_analyses WHERE id = 'rja_old'")).fetchone()
            self.assertIsNotNone(rja_row)
            self.assertEqual(rja_row[0], "rja_old")
            self.assertEqual(rja_row[1], 75)
            self.assertIsNone(rja_row[2])  # Existing rows remain NULL

    def test_running_schema_update_twice_is_idempotent(self):
        engine = create_engine("sqlite:///:memory:")
        # First call creates schema and adds columns
        init_schema(bind=engine)
        # Second call runs without error or duplicate column exceptions
        init_schema(bind=engine)

        insp = inspect(engine)
        jm_cols = {c["name"] for c in insp.get_columns("job_matches")}
        self.assertIn("work_mode_score", jm_cols)
        self.assertIn("education_score", jm_cols)
        self.assertIn("score_version", jm_cols)


class TestUsesApplicationEngine(unittest.TestCase):
    def test_default_bind_is_the_application_engine(self):
        with mock.patch.object(Base.metadata, "create_all") as mock_create, \
             mock.patch("app.database.schema_init._apply_additive_columns") as mock_evolve:
            init_schema()
        mock_create.assert_called_once_with(bind=engine)
        mock_evolve.assert_called_once_with(engine)

    def test_failure_is_propagated_not_swallowed(self):
        with mock.patch.object(
            Base.metadata, "create_all", side_effect=RuntimeError("database unavailable")
        ):
            with self.assertRaises(RuntimeError):
                init_schema()


class TestCliEntryPoint(unittest.TestCase):
    def test_main_calls_init_schema_and_succeeds(self):
        with mock.patch("app.database.init.init_schema", return_value=sorted(EXPECTED_TABLES)) as mock_init:
            result = cli.main()
        self.assertEqual(result, 0)
        mock_init.assert_called_once_with()

    def test_main_propagates_failure_to_the_shell(self):
        with mock.patch("app.database.init.init_schema", side_effect=RuntimeError("database unavailable")):
            with self.assertRaises(RuntimeError):
                cli.main()


if __name__ == "__main__":
    unittest.main()