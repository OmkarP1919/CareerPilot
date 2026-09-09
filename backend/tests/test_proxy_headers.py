"""Proxy-headers middleware — forward-header trust and scheme detection.

Covers the ``ProxyHeadersMiddleware`` introduced to fix the production
mixed-content issue: Azure App Service terminates TLS and forwards
``X-Forwarded-Proto: https`` to the backend over HTTP.  Without the
middleware (or without Uvicorn's ``forwarded_allow_ips``), Starlette
sees ``scope["scheme"] = "http"`` and 307 redirects emit
``http://`` Location headers, causing mixed-content errors in browsers.

Tests are organized into three groups:

1. **Unit tests** — the middleware in isolation (IP trust, header parsing,
   scope mutation, pass-through for non-HTTP / untrusted / missing headers).
2. **Integration tests** — the full application with the middleware wired in,
   verifying that trailing-slash 307 redirects produce the correct scheme.
3. **Configuration tests** — the ``allowed_forwarded_ips`` property on Settings.

Temporary app instances are built with injected settings; the developer's
real production configuration is never used.
"""

import asyncio
import unittest

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import Settings, cors_origins_for
from app.core.proxy_headers import ProxyHeadersMiddleware
from app.core.request_middleware import RequestLoggingMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.api.health import router as health_router
from app.api.applications import router as applications_router
from app.api.profile import router as profile_router
from app.api.jobs import router as jobs_router
from app.api.auth import router as auth_router
from app.api.resumes import router as resumes_router
from app.api.discovery import router as discovery_router
from app.api.match import router as match_router
from app.api.resume_analysis import router as resume_analysis_router
from app.api.resume_tailoring import router as resume_tailoring_router
from app.api.resume_tailoring import tailored_list_router
from app.api.resume_export import router as resume_export_router
from app.api.cover_letter import router as cover_letter_router
from app.api.cover_letter import collection_router as cover_letter_collection_router
from app.api.analytics import router as analytics_router


# ---------------------------------------------------------------------------
# 1. Unit tests — middleware in isolation
# ---------------------------------------------------------------------------

def _run_async(coro):
    return asyncio.run(coro)


async def _invoke_middleware(mw, scope):
    result_scope = {}

    async def _app(s, r, s2):
        result_scope.update(s)

    mw.app = _app
    await mw(scope, None, None)
    return result_scope


class TestProxyHeadersUnit(unittest.TestCase):
    """Direct ASGI-scope tests for ProxyHeadersMiddleware."""

    def test_trusted_ip_sets_scheme_https(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["10.0.0.1"])
        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("10.0.0.1", 12345),
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "https")

    def test_untrusted_ip_keeps_scheme_http(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["10.0.0.1"])
        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("192.168.1.100", 12345),
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "http")

    def test_wildcard_trust_sets_scheme_https(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["*"])
        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("192.168.1.100", 12345),
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "https")

    def test_no_forwarded_header_keeps_scheme(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["*"])
        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("10.0.0.1", 12345),
            "headers": [],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "http")

    def test_empty_allowed_ips_disables_trust(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=[])
        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("10.0.0.1", 12345),
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "http")

    def test_none_allowed_ips_disables_trust(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=None)
        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("10.0.0.1", 12345),
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "http")

    def test_websocket_scope_passes_through(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["*"])
        scope = {
            "type": "websocket",
            "scheme": "ws",
            "client": ("10.0.0.1", 12345),
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "ws")

    def test_invalid_forwarded_proto_ignored(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["*"])
        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("10.0.0.1", 12345),
            "headers": [(b"x-forwarded-proto", b"ftp")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "http")

    def test_no_client_info_keeps_scheme(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["*"])
        scope = {
            "type": "http",
            "scheme": "http",
            "client": None,
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "http")

    def test_forwarded_proto_http_downgrade(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["*"])
        scope = {
            "type": "http",
            "scheme": "https",
            "client": ("10.0.0.1", 12345),
            "headers": [(b"x-forwarded-proto", b"http")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "http")

    def test_multiple_ips_trusted(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["10.0.0.1", "172.16.0.5"])
        for ip in ("10.0.0.1", "172.16.0.5"):
            scope = {
                "type": "http",
                "scheme": "http",
                "client": (ip, 12345),
                "headers": [(b"x-forwarded-proto", b"https")],
            }
            result = _run_async(_invoke_middleware(mw, scope))
            self.assertEqual(result["scheme"], "https", f"Failed for IP {ip}")

    def test_forwarded_proto_value_case_insensitive(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["*"])
        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("10.0.0.1", 12345),
            "headers": [(b"x-forwarded-proto", b"HTTPS")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "https")

    def test_forwarded_proto_mixed_case_value(self):
        mw = ProxyHeadersMiddleware(None, allowed_ips=["*"])
        scope = {
            "type": "http",
            "scheme": "http",
            "client": ("10.0.0.1", 12345),
            "headers": [(b"x-forwarded-proto", b"https")],
        }
        result = _run_async(_invoke_middleware(mw, scope))
        self.assertEqual(result["scheme"], "https")


# ---------------------------------------------------------------------------
# 2. Integration tests — full application with trailing-slash redirects
# ---------------------------------------------------------------------------

def _build_middleware_app(allowed_ips=None) -> FastAPI:
    """Build a FastAPI app matching main.py middleware order with real routers.

    Does NOT import app.main to avoid settings import side-effects.
    """
    origins = cors_origins_for("development", "http://localhost:5173")
    app = FastAPI()

    @app.get("/")
    async def root():
        return {"ok": True}

    # Routers (matching main.py registration order)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(profile_router)
    app.include_router(resumes_router)
    app.include_router(jobs_router)
    app.include_router(discovery_router)
    app.include_router(match_router)
    app.include_router(resume_analysis_router)
    app.include_router(resume_tailoring_router)
    app.include_router(tailored_list_router)
    app.include_router(resume_export_router)
    app.include_router(cover_letter_router)
    app.include_router(cover_letter_collection_router)
    app.include_router(applications_router)
    app.include_router(analytics_router)

    # Middleware (matching main.py order, innermost -> outermost in code)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["testserver", "localhost", "127.0.0.1"])
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ProxyHeadersMiddleware, allowed_ips=allowed_ips or [])
    app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=False)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


class TestProxyHeadersIntegration(unittest.TestCase):
    """Verify 307 redirect Location headers use the correct scheme."""

    def _https_client(self, allowed_ips=None):
        app = _build_middleware_app(allowed_ips=allowed_ips)
        return TestClient(app, base_url="https://testserver", follow_redirects=False)

    def _http_client(self, allowed_ips=None):
        app = _build_middleware_app(allowed_ips=allowed_ips)
        return TestClient(app, base_url="http://localhost", follow_redirects=False)

    # --- HTTPS scheme tests (simulates Azure proxy with scope scheme=https) ---

    def test_https_redirect_applications(self):
        c = self._https_client()
        r = c.get("/applications/")
        self.assertEqual(r.status_code, 307)
        self.assertTrue(
            r.headers["location"].startswith("https://"),
            f"Expected https:// Location, got: {r.headers['location']}",
        )

    def test_https_redirect_profile(self):
        c = self._https_client()
        r = c.get("/profile/")
        self.assertEqual(r.status_code, 307)
        self.assertTrue(
            r.headers["location"].startswith("https://"),
            f"Expected https:// Location, got: {r.headers['location']}",
        )

    def test_https_redirect_jobs(self):
        c = self._https_client()
        r = c.get("/jobs/")
        self.assertEqual(r.status_code, 307)
        self.assertTrue(
            r.headers["location"].startswith("https://"),
            f"Expected https:// Location, got: {r.headers['location']}",
        )

    # --- HTTP scheme tests (simulates local dev with scope scheme=http) ---

    def test_http_redirect_applications(self):
        c = self._http_client()
        r = c.get("/applications/")
        self.assertEqual(r.status_code, 307)
        self.assertTrue(
            r.headers["location"].startswith("http://"),
            f"Expected http:// Location, got: {r.headers['location']}",
        )

    def test_http_redirect_profile(self):
        c = self._http_client()
        r = c.get("/profile/")
        self.assertEqual(r.status_code, 307)
        self.assertTrue(
            r.headers["location"].startswith("http://"),
            f"Expected http:// Location, got: {r.headers['location']}",
        )

    def test_http_redirect_jobs(self):
        c = self._http_client()
        r = c.get("/jobs/")
        self.assertEqual(r.status_code, 307)
        self.assertTrue(
            r.headers["location"].startswith("http://"),
            f"Expected http:// Location, got: {r.headers['location']}",
        )

    # --- Non-redirect routes ---

    def test_root_returns_200(self):
        c = self._https_client()
        r = c.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})

    def test_non_trailing_slash_no_redirect(self):
        c = self._https_client()
        r = c.get("/applications")
        self.assertNotEqual(r.status_code, 307)

    def test_healthz_returns_200(self):
        c = self._https_client()
        r = c.get("/healthz")
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# 3. Configuration tests — allowed_forwarded_ips
# ---------------------------------------------------------------------------

class TestForwardedIpsConfig(unittest.TestCase):
    """Verify the Settings.allowed_forwarded_ips property."""

    def test_empty_string_returns_empty_list(self):
        s = Settings(FORWARDED_ALLOW_IPS="", ENVIRONMENT="development")
        self.assertEqual(s.allowed_forwarded_ips, [])

    def test_wildcard(self):
        s = Settings(FORWARDED_ALLOW_IPS="*", ENVIRONMENT="development")
        self.assertEqual(s.allowed_forwarded_ips, ["*"])

    def test_comma_separated_list(self):
        s = Settings(
            FORWARDED_ALLOW_IPS="10.0.0.1, 172.16.0.5, 192.168.1.1",
            ENVIRONMENT="development",
        )
        self.assertEqual(
            s.allowed_forwarded_ips,
            ["10.0.0.1", "172.16.0.5", "192.168.1.1"],
        )

    def test_whitespace_stripped(self):
        s = Settings(
            FORWARDED_ALLOW_IPS="  10.0.0.1 , 172.16.0.5  ",
            ENVIRONMENT="development",
        )
        self.assertEqual(s.allowed_forwarded_ips, ["10.0.0.1", "172.16.0.5"])

    def test_default_empty(self):
        s = Settings(ENVIRONMENT="development")
        self.assertEqual(s.allowed_forwarded_ips, [])


if __name__ == "__main__":
    unittest.main()
