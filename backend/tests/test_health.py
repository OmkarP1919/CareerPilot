"""Phase 5E.3 - liveness and database readiness endpoints.

Database connectivity is mocked so ordinary test runs never touch a real
database; success and failure paths of ``SELECT 1`` are both covered.
"""

import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import health
from app.api.health import router


class _HealthyConnection:
    """Duck-typed engine.connect() result that succeeds on SELECT 1."""

    def execute(self, statement):
        return iter([(1,)])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _make_app() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestLiveness(unittest.TestCase):
    def test_healthz_returns_200_without_database(self):
        response = _make_app().get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_healthz_never_queries_database(self):
        with mock.patch.object(
            health.engine,
            "connect",
            side_effect=AssertionError("liveness must not touch the database"),
        ):
            response = _make_app().get("/healthz")
        self.assertEqual(response.status_code, 200)


class TestReadiness(unittest.TestCase):
    def test_readyz_returns_200_when_select_1_succeeds(self):
        with mock.patch.object(health.engine, "connect", return_value=_HealthyConnection()):
            response = _make_app().get("/health/readyz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})

    def test_readyz_returns_503_when_database_unavailable(self):
        with mock.patch.object(
            health.engine,
            "connect",
            side_effect=OperationalError("SELECT 1", {}, Exception("connection refused")),
        ):
            response = _make_app().get("/health/readyz")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "not_ready"})

    def test_readyz_failure_does_not_expose_database_details(self):
        with mock.patch.object(
            health.engine,
            "connect",
            side_effect=OperationalError(
                "SELECT 1", {}, Exception("psycopg2 password=supersecret connection refused")
            ),
        ):
            response = _make_app().get("/health/readyz")
        body = response.text
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "not_ready"})
        self.assertNotIn("supersecret", body)
        self.assertNotIn("OperationalError", body)
        self.assertNotIn("Traceback", body)


class TestCompatibilityAndAuth(unittest.TestCase):
    def test_legacy_health_endpoint_remains_compatible(self):
        response = _make_app().get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})

    def test_health_endpoints_do_not_require_authentication(self):
        with mock.patch.object(health.engine, "connect", return_value=_HealthyConnection()):
            client = _make_app()
            for path in ("/healthz", "/health", "/health/readyz"):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()