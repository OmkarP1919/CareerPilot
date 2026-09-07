"""Phase 5E.5 - production logging & request tracing tests.

Exercises the request-ID middleware and logging foundation (tests A-J)
using an in-memory app that captures emitted log records. No external
logging service is required.
"""

import logging
import os
import tempfile
import unittest
from unittest import mock
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.logging_config import setup_logging
from app.core.request_middleware import _generate_request_id, _validate_request_id
from app.core.request_context import get_request_id


class _LogCapture:
    """Attaches a handler to the root logger and records emitted records."""

    def __init__(self):
        self.records = []
        self._handler = logging.Handler()

        class _Buffer(logging.Handler):
            def __init__(self, sink):
                super().__init__()
                self.sink = sink

            def emit(self, record):
                self.format(record)  # populate exc_text / message
                self.sink.records.append(record)

        self._handler = _Buffer(self)

    def __enter__(self):
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        root.addHandler(self._handler)
        return self

    def __exit__(self, *exc):
        root = logging.getLogger()
        root.removeHandler(self._handler)
        return False

    def lines(self, name=None):
        return [r for r in self.records if name is None or r.name == name]


def _make_app():
    """Return (app, client) with built-in health, ok, and exception routes.

    Includes the real health router so unauthenticated /health* and the
    request-logging skip for those paths are exercised against the real
    endpoints. Does NOT call ``setup_logging()``; the test supplies its own
    capture handler instead.
    """
    app = FastAPI()

    from app.api import health as health_module
    from app.core.request_middleware import RequestLoggingMiddleware

    app.include_router(health_module.router)
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/boom")
    def boom():
        raise RuntimeError("test boom")
        return None

    return app, TestClient(app, raise_server_exceptions=False)


class TestRequestID(unittest.TestCase):
    def setUp(self):
        self.app, self.client = _make_app()

    def test_a_generates_request_id_when_header_absent(self):
        resp = self.client.get("/ok")
        self.assertEqual(resp.status_code, 200)
        rid = resp.headers.get("X-Request-ID")
        self.assertTrue(rid)

    def test_b_preserves_valid_request_id(self):
        resp = self.client.get("/ok", headers={"X-Request-ID": "my-valid-id-123"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("X-Request-ID"), "my-valid-id-123")

    def test_c_replaces_oversized_request_id(self):
        resp = self.client.get(
            "/ok", headers={"X-Request-ID": "x" * 2000}
        )
        self.assertEqual(resp.status_code, 200)
        rid = resp.headers.get("X-Request-ID")
        self.assertNotEqual(rid, "x" * 2000)

    def test_d_request_id_cannot_inject_newline(self):
        # A client-supplied ID with a newline must be rejected and regenerated.
        resp = self.client.get(
            "/ok", headers={"X-Request-ID": "legitid\nINJECTED"}
        )
        self.assertEqual(resp.status_code, 200)
        rid = resp.headers.get("X-Request-ID")
        self.assertNotIn("\n", rid)
        self.assertNotIn("\r", rid)
        self.assertFalse(rid.startswith("legitid\n"))

        # Empty / whitespace / malformed also regenerated.
        resp = self.client.get("/ok", headers={"X-Request-ID": ""})
        self.assertTrue(resp.headers.get("X-Request-ID"))

    def test_e_response_contains_request_id(self):
        resp = self.client.get("/ok")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("X-Request-ID", resp.headers)
        self.assertTrue(resp.headers["X-Request-ID"])


class TestRequestLogging(unittest.TestCase):
    def test_f_request_log_contains_all_expected_fields(self):
        app, client = _make_app()
        with _LogCapture() as capture:
            resp = client.get("/ok", headers={"X-Request-ID": "trace-42"})
        self.assertEqual(resp.status_code, 200)
        request_logs = [
            r for r in capture.records
            if r.name == "app.request" and r.getMessage().startswith("request ")
        ]
        self.assertEqual(len(request_logs), 1)
        message = request_logs[0].getMessage()
        self.assertIn("request_id=trace-42", message)
        self.assertIn("method=GET", message)
        self.assertIn("path=/ok", message)
        self.assertIn("status=200", message)
        self.assertRegex(message, r"duration_ms=[0-9.]+")

    def test_g_authorization_header_is_not_logged(self):
        app, client = _make_app()
        with _LogCapture() as capture:
            resp = client.get(
                "/ok",
                headers={"Authorization": "Bearer SECRETFIREBASETOKEN"},
            )
        self.assertEqual(resp.status_code, 200)

        # Serialize every captured log record (message + all attributes) and
        # assert the bearer token is nowhere in them.
        chunks = []
        for r in capture.records:
            chunks.append(str(r.getMessage()))
            for k, v in vars(r).items():
                if isinstance(v, str):
                    chunks.append(v)
        all_text = "\n".join(chunks)
        self.assertNotIn("SECRETFIREBASETOKEN", all_text)
        self.assertNotIn("Bearer", all_text)


class TestErrorLogging(unittest.TestCase):
    def test_h_unexpected_exception_is_logged_server_side(self):
        app, client = _make_app()
        with _LogCapture() as capture:
            resp = client.get(
                "/boom", headers={"X-Request-ID": "boom-1"}
            )
        self.assertEqual(resp.status_code, 500)
        # The client must not receive a stack trace or exception detail.
        self.assertNotIn("test boom", resp.text)
        self.assertNotIn("Traceback", resp.text)
        # The server-side log must include the request ID and the exception.
        error_logs = [
            r for r in capture.records
            if r.name == "app.request" and r.levelno >= logging.ERROR
        ]
        self.assertTrue(error_logs)
        rec = error_logs[0]
        self.assertIn("request_id=boom-1", rec.getMessage())
        self.assertIn("method=GET", rec.getMessage())
        self.assertIn("path=/boom", rec.getMessage())
        self.assertIn("test boom", rec.exc_text)


class TestRequestContextIsolation(unittest.TestCase):
    def test_i_request_id_does_not_leak_across_requests(self):
        from app.core.request_context import set_request_id

        app, client = _make_app()

        # Prime the current thread's context with an unrelated value.
        set_request_id("primed")

        # Issue two sequential requests; each runs inside its own ASGI task
        # with a fresh ContextVar, so neither should observe the other's ID
        # or the primed value from the test thread.
        with _LogCapture() as capture:
            resp1 = client.get("/ok", headers={"X-Request-ID": "first-request"})
            resp2 = client.get("/ok", headers={"X-Request-ID": "second-request"})

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)

        # The middleware attached its own ID to each response, independent of
        # the primed value set on the test thread.
        self.assertEqual(resp1.headers["X-Request-ID"], "first-request")
        self.assertEqual(resp2.headers["X-Request-ID"], "second-request")

        # Capture all request log records; each must carry exactly the ID of
        # its own request - none should observe "primed" or the other ID.
        request_logs = [
            r for r in capture.records
            if r.name == "app.request" and r.getMessage().startswith("request ")
        ]
        self.assertEqual(len(request_logs), 2)
        logged_ids = set()
        for r in request_logs:
            for part in r.getMessage().split():
                if part.startswith("request_id="):
                    logged_ids.add(part.split("=", 1)[1])
        self.assertEqual(logged_ids, {"first-request", "second-request"})
        self.assertNotIn("primed", logged_ids)


class TestHealthUnauthenticated(unittest.TestCase):
    def test_j_health_endpoints_remain_unauthenticated_and_functional(self):
        from app.api import health as health_module

        class _HealthyConnection:
            """Duck-typed engine.connect() result: SELECT 1 succeeds."""

            def execute(self, statement):
                return iter([(1,)])

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        app, client = _make_app()
        # Readiness probes the configured database engine; pin that probe so
        # this unit test is deterministic on any machine/CI run (SELECT 1
        # deliberately "succeeds") and never depends on a live database.
        with mock.patch.object(
            health_module.engine, "connect", return_value=_HealthyConnection()
        ):
            for path in ("/healthz", "/health", "/health/readyz"):
                resp = client.get(path)
                self.assertEqual(resp.status_code, 200, path)
                self.assertIn("status", resp.json())


class TestRequestIdUtility(unittest.TestCase):
    def test_validate_rejects_bad(self):
        self.assertIsNone(_validate_request_id(""))
        self.assertIsNone(_validate_request_id("x" * 2000))
        self.assertIsNone(_validate_request_id("bad\nid"))
        self.assertIsNone(_validate_request_id("bad\r\nid"))

    def test_validate_accepts_good(self):
        self.assertEqual(_validate_request_id("abc-123"), "abc-123")

    def test_generate_is_unique(self):
        self.assertNotEqual(_generate_request_id(), _generate_request_id())


if __name__ == "__main__":
    unittest.main()