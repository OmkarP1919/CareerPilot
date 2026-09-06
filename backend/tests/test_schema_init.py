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


class TestUsesApplicationEngine(unittest.TestCase):
    def test_default_bind_is_the_application_engine(self):
        with mock.patch.object(Base.metadata, "create_all") as mock_create:
            init_schema()
        mock_create.assert_called_once_with(bind=engine)

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