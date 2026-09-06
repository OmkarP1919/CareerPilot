"""Phase 5E.7 - security headers, TrustedHost & request-body-limit hardening.

Covers configuration resolution plus the composed middleware behavior:
- security response headers (nosniff, X-Frame-Options, Referrer-Policy, CSP,
  conditional HSTS)
- TRUSTED_HOSTS (dev defaults, custom hosts, production fail-fast)
- MAX_REQUEST_BODY_BYTES (Content-Length short-circuit + chunked streaming,
  413 responses, request-ID preservation, no storage of oversized bodies)
- middleware interaction and health endpoints

Temporary app instances are built with injected settings; the developer's real
production configuration is never used.
"""
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import (
    DEFAULT_MAX_REQUEST_BODY_BYTES,
    DEV_TRUSTED_HOSTS,
    Settings,
    cors_origins_for,
    trusted_hosts_for,
)
from app.core.body_limit import RequestBodyLimitMiddleware
from app.core.request_middleware import RequestLoggingMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.api.health import router as health_router
from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.job import Job
from app.models.application import Application
from app.api.applications import router as applications_router


def _build_app(trusted_hosts=None, max_body=None, hsts=False) -> FastAPI:
    """Build a FastAPI app using the 5E.7 middleware order (mirrors main.py)."""
    app = FastAPI()
    origins = cors_origins_for("development", "http://localhost:5173")

    @app.get("/")
    def root():
        return {"ok": True}

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/echo")
    async def echo(request: Request):
        body = await request.body()
        return {"len": len(body)}

    app.include_router(health_router)
    app.add_middleware(RequestBodyLimitMiddleware,
                       max_bytes=max_body if max_body is not None else DEFAULT_MAX_REQUEST_BODY_BYTES)
    app.add_middleware(TrustedHostMiddleware,
                       allowed_hosts=trusted_hosts if trusted_hosts is not None else DEV_TRUSTED_HOSTS)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=hsts)
    app.add_middleware(CORSMiddleware,
                       allow_origins=origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    return app


class TestSecurityHeaders(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(_build_app(), base_url="http://localhost")

    def test_x_content_type_options_present(self):
        r = self.client.get("/")
        self.assertEqual(r.headers.get("x-content-type-options"), "nosniff")

    def test_x_frame_options_present(self):
        r = self.client.get("/")
        self.assertEqual(r.headers.get("x-frame-options"), "DENY")

    def test_referrer_policy_present(self):
        r = self.client.get("/")
        self.assertEqual(r.headers.get("referrer-policy"), "strict-origin-when-cross-origin")

    def test_csp_present_and_conservative(self):
        r = self.client.get("/")
        csp = r.headers.get("content-security-policy", "")
        self.assertIn("default-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("base-uri 'none'", csp)
        self.assertNotIn("'unsafe-inline'", csp)
        self.assertNotIn("'unsafe-eval'", csp)
        self.assertNotIn("http://", csp)

    def test_hsts_absent_in_development(self):
        r = self.client.get("/")
        self.assertIsNone(r.headers.get("strict-transport-security"))

    def test_hsts_present_when_enabled(self):
        client = TestClient(_build_app(hsts=True), base_url="http://localhost")
        r = client.get("/")
        self.assertEqual(r.headers.get("strict-transport-security"), "max-age=31536000")
        self.assertNotIn("includeSubDomains", r.headers.get("strict-transport-security", ""))

    def test_security_headers_on_error_responses(self):
        r = self.client.get("/missing")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(r.headers.get("x-frame-options"), "DENY")
        self.assertIn("frame-ancestors 'none'", r.headers.get("content-security-policy", ""))

    def test_docs_endpoints_excluded_from_csp_but_keep_other_headers(self):
        for path in ("/docs", "/redoc", "/docs/oauth2-redirect"):
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertIn(r.status_code, (200, 404, 405))
                self.assertEqual(r.headers.get("x-content-type-options"), "nosniff")
                self.assertEqual(r.headers.get("x-frame-options"), "DENY")
                self.assertEqual(r.headers.get("referrer-policy"),
                                 "strict-origin-when-cross-origin")
                self.assertIsNone(r.headers.get("content-security-policy"),
                                  f"CSP must be excluded on {path}")


class TestTrustedHost(unittest.TestCase):
    def test_localhost_development_default_accepted(self):
        client = TestClient(_build_app())
        r = client.get("/", headers={"host": "localhost"})
        self.assertEqual(r.status_code, 200)

    def test_ipv4_localhost_accepted(self):
        client = TestClient(_build_app())
        r = client.get("/", headers={"host": "127.0.0.1"})
        self.assertEqual(r.status_code, 200)
        r = client.get("/", headers={"host": "127.0.0.1:5174"})
        self.assertEqual(r.status_code, 200)

    def test_disallowed_host_rejected(self):
        client = TestClient(_build_app())
        r = client.get("/", headers={"host": "evil.example.com"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.text, "Invalid host header")
        self.assertNotIn("TRUSTED_HOSTS", r.text)

    def test_custom_configured_host_accepted(self):
        client = TestClient(_build_app(trusted_hosts=["api.example.com"]))
        r = client.get("/", headers={"host": "api.example.com"})
        self.assertEqual(r.status_code, 200)
        r2 = client.get("/", headers={"host": "other.example.com"})
        self.assertEqual(r2.status_code, 400)

    def test_wildcard_subdomain_accepted(self):
        client = TestClient(_build_app(trusted_hosts=["*.example.com"]))
        r = client.get("/", headers={"host": "app.example.com"})
        self.assertEqual(r.status_code, 200)

    def test_production_empty_fails_configuration(self):
        for env in ("production", "prod", "staging"):
            with self.subTest(env=env):
                with self.assertRaises(ValueError):
                    trusted_hosts_for(env, "")

    def test_no_wildcard_default_for_production(self):
        for env in ("production", "prod", "staging"):
            with self.subTest(env=env):
                with self.assertRaises(ValueError):
                    Settings(ENVIRONMENT=env, TRUSTED_HOSTS="").allowed_trusted_hosts

    def test_comma_separated_hosts_parsed(self):
        hosts = trusted_hosts_for("production", "a.example.com, b.example.com ,*.c.example.com")
        self.assertEqual(hosts, ["a.example.com", "b.example.com", "*.c.example.com"])

    def test_malformed_hosts_rejected(self):
        for raw in ("*", "https://a.example.com", "a.example.com/path", "a b.com", "  "):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    trusted_hosts_for("production", raw)

    def test_development_default_matches_trusted_hosts(self):
        self.assertEqual(
            trusted_hosts_for("development", ""),
            ["localhost", "127.0.0.1", "::1"],
        )
        self.assertEqual(Settings(ENVIRONMENT="development", TRUSTED_HOSTS="").allowed_trusted_hosts,
                         DEV_TRUSTED_HOSTS)


class TestRequestBodyLimit(unittest.TestCase):
    def _client(self, max_body):
        return TestClient(_build_app(max_body=max_body), base_url="http://localhost")

    def test_below_limit_succeeds(self):
        r = self._client(1000).post("/echo", content=b"x" * 500)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"len": 500})

    def test_at_limit_succeeds(self):
        r = self._client(1000).post("/echo", content=b"x" * 1000)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"len": 1000})

    def test_above_limit_returns_413(self):
        r = self._client(1000).post("/echo", content=b"x" * 1001)
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.json(), {"detail": "Request body too large"})

    def test_413_does_not_leak_body_or_path(self):
        r = self._client(1000).post("/echo", content=b"x" * 2000)
        self.assertEqual(r.status_code, 413)
        self.assertNotIn("x" * 20, r.text)
        self.assertNotIn("/echo", r.text)
        self.assertNotIn("Traceback", r.text)
        self.assertNotIn("secret", r.text)

    def test_content_length_above_limit_rejected_without_downstream(self):
        calls = {"n": 0}
        app = FastAPI()

        @app.post("/downstream")
        async def downstream():
            calls["n"] += 1
            return {"ran": True}

        app.add_middleware(RequestBodyLimitMiddleware, max_bytes=1000)

        @app.middleware("http")
        async def marker(request, call_next):
            return await call_next(request)

        client = TestClient(app)
        r = client.post(
            "/downstream",
            content=b"x" * 5000,
            headers={"content-length": "5000"},
        )
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.json(), {"detail": "Request body too large"})
        self.assertEqual(calls["n"], 0)

    def test_chunked_above_limit_returns_413(self):
        r = self._client(1000).post(
            "/echo",
            content=b"x" * 2000,
            headers={"transfer-encoding": "chunked"},
        )
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.json(), {"detail": "Request body too large"})

    def test_chunked_within_limit_succeeds(self):
        r = self._client(2000).post(
            "/echo",
            content=b"y" * 1500,
            headers={"transfer-encoding": "chunked"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"len": 1500})

    def test_malformed_content_length_handled_safely(self):
        # Non-numeric/negative Content-Length is stream-counted, not trusted.
        r = self._client(10).post(
            "/echo", content=b"12345",
            headers={"content-length": "not-a-number"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"len": 5})

    def test_request_id_preserved_on_body_limit_rejection(self):
        r = self._client(1000).post(
            "/echo", content=b"x" * 5000,
            headers={"X-Request-ID": "body-limit-id"},
        )
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.headers.get("X-Request-ID"), "body-limit-id")

    def test_request_id_generated_on_body_limit_rejection(self):
        r = self._client(1000).post("/echo", content=b"x" * 5000)
        self.assertEqual(r.status_code, 413)
        self.assertTrue(r.headers.get("X-Request-ID"))


class TestRequestLimitStorage(unittest.TestCase):
    """Global body-limit interaction with the real upload endpoints."""

    def setUp(self):
        self._tmpbase = tempfile.mkdtemp(prefix="cp_sec_")
        self.tmpdir = os.path.join(self._tmpbase, "uploads")
        os.makedirs(self.tmpdir, exist_ok=True)
        self._patch_uploads = patch("app.api.applications.UPLOAD_DIR", self.tmpdir)
        self._patch_uploads.start()
        self._patch_resumes = patch("app.api.resumes.UPLOAD_DIR", self.tmpdir)
        self._patch_resumes.start()

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.database.base import Base, get_db
        from app.dependencies.auth import get_current_user
        from app.models.user import User
        from app.models.job import Job
        from app.models.application import Application
        from app.api.applications import router as applications_router

        self.db_path = os.path.join(os.path.dirname(self.tmpdir), "t.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        db.add_all([
            User(id="user_a", firebase_uid="fb_a", email="a@test.com", name="A"),
        ])
        db.add(Job(id="job_1", user_id="user_a", title="Dev", company="Acme",
                   description="d", required_skills="python"))
        db.add(Application(id="app_a", user_id="user_a", job_id="job_1", status="Applied"))
        db.commit()
        db.close()

        self.app = FastAPI()
        self.app.include_router(applications_router)
        self.current_user_id = "user_a"

        def override_get_db():
            s = self.Session()
            try:
                yield s
            finally:
                s.close()

        def override_get_current_user():
            s = self.Session()
            try:
                return s.query(User).filter(User.id == self.current_user_id).first()
            finally:
                s.close()

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_current_user] = override_get_current_user
        self.app.add_middleware(RequestLoggingMiddleware)
        self.app.add_middleware(RequestBodyLimitMiddleware, max_bytes=DEFAULT_MAX_REQUEST_BODY_BYTES)
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self._patch_uploads.stop()
        self._patch_resumes.stop()
        shutil.rmtree(self._tmpbase, ignore_errors=True)

    def _uploads(self):
        if not os.path.isdir(self.tmpdir):
            return []
        files = []
        for base, _, names in os.walk(self.tmpdir):
            for n in names:
                files.append(os.path.join(base, n))
        return files

    def test_multipart_near_limit_still_reaches_upload_handler(self):
        # A small-but-nonempty PDF under the 16 MiB global cap succeeds.
        pdf = b"%PDF-1.4" + (b"a" * 200)
        r = self.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("cv.pdf", pdf, "application/pdf")},
        )
        self.assertEqual(r.status_code, 201, r.text)

    def test_existing_10mb_upload_rejection_still_works(self):
        with patch("app.api.applications.MAX_UPLOAD_SIZE", 10):
            r = self.client.post(
                "/applications/app_a/documents/upload",
                files={"file": ("big.pdf", b"x" * 20, "application/pdf")},
            )
        self.assertEqual(r.status_code, 400)
        self.assertIn("10MB", r.json()["detail"])

    def test_existing_valid_upload_still_works(self):
        r = self.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("ok.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(len(self._uploads()), 1)

    def test_no_partial_upload_file_when_global_limit_rejects(self):
        huge = b"%PDF-1.4 test " + (b"x" * (DEFAULT_MAX_REQUEST_BODY_BYTES + (2 * 1024 * 1024)))
        r = self.client.post(
            "/applications/app_a/documents/upload",
            files={"file": ("huge.pdf", huge, "application/pdf")},
            headers={"transfer-encoding": "chunked"},
        )
        self.assertEqual(r.status_code, 413)
        self.assertEqual(self._uploads(), [])


class TestMiddlewareInteraction(unittest.TestCase):
    def test_trustedhost_size_requestid_headers_interact(self):
        client = TestClient(_build_app(max_body=500))
        # Allowed host + oversized body -> 413 WITH security headers + request ID.
        r = client.post("/echo", content=b"x" * 1000,
                        headers={"host": "localhost"})
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.headers.get("x-content-type-options"), "nosniff")
        self.assertIsNotNone(r.headers.get("x-request-id"))
        self.assertEqual(r.json(), {"detail": "Request body too large"})

        # Disallowed host -> 400 immediately.
        r2 = client.post("/echo", content=b"x" * 10,
                         headers={"host": "evil.example.com"})
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.headers.get("x-content-type-options"), "nosniff")
        self.assertIsNotNone(r2.headers.get("x-request-id"))

    def test_healthz_unauthenticated_and_functional(self):
        client = TestClient(_build_app())
        r = client.get("/healthz", headers={"host": "localhost"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok"})

    def test_security_headers_on_all_health(self):
        client = TestClient(_build_app())
        for path in ("/healthz", "/health", "/health/readyz"):
            with self.subTest(path=path):
                with patch("app.api.health.engine.connect") as mock_connect:
                    mock_connect.return_value.__enter__ = mock_connect.return_value
                    mock_connect.return_value.__exit__ = lambda *a: None
                    r = client.get(path, headers={"host": "localhost"})
                self.assertIn(r.status_code, (200, 503))
                self.assertEqual(r.headers.get("x-content-type-options"), "nosniff")


class TestConfigProperties(unittest.TestCase):
    def test_hsts_default_off_in_all_environments(self):
        for env in ("development", "test", "production"):
            with self.subTest(env=env):
                s = Settings(ENVIRONMENT=env, ENABLE_HSTS=False)
                self.assertFalse(s.hsts_enabled)

    def test_hsts_opt_in(self):
        self.assertTrue(Settings(ENABLE_HSTS=True).hsts_enabled)

    def test_max_body_default(self):
        self.assertEqual(Settings().MAX_REQUEST_BODY_BYTES, DEFAULT_MAX_REQUEST_BODY_BYTES)

    def test_trusted_hosts_resolution_is_stable(self):
        self.assertIn("localhost", trusted_hosts_for("test", ""))
        self.assertIn("127.0.0.1", trusted_hosts_for("development", ""))


if __name__ == "__main__":
    unittest.main()
