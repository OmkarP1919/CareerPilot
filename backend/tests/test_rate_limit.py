"""Phase 5E.9 - production-safe rate limiting.

Covers:
- rate_limit config validation + sanitization (backend allow-list, warnings)
- fixed-window memory backend (boundary, window reset, bounds, hashing,
  fail-open at key cap, clear)
- global anonymous/client-IP middleware (count, 429 shape/headers, health
  exemption, X-Forwarded-For not trusted, disabled bypass, request-ID +
  security-header envelope)
- per-user authenticated / expensive dependencies (per-user independence,
  verified-UID keying, 429 + Retry-After, disabled bypass)

The real production app configuration is never used; apps are built inline with
injected settings, matching the 5E.7 test style.
"""
import threading
import time
import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import cors_origins_for, Settings
from app.core.rate_limit import MemoryRateLimitBackend, RateLimiter
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.core.rate_limit_deps import (
    configure_rate_limits,
    expensive_rate_limiter,
    authenticated_rate_limiter,
)
from app.core.request_middleware import RequestLoggingMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.dependencies.auth import get_current_user
from app.models.user import User


def _mk_user(uid: str) -> User:
    u = User(firebase_uid=uid, email=f"{uid}@test.local", name=uid)
    u.id = f"db-{uid}"
    return u


class TestConfig(unittest.TestCase):
    def test_invalid_backend_raises(self):
        s = Settings(RATE_LIMIT_BACKEND="redis-unknown", _env_file=None)
        with self.assertRaises(ValueError):
            s.rate_limit_config

    def test_defaults_sane(self):
        s = Settings(_env_file=None)
        cfg = s.rate_limit_config
        self.assertEqual(cfg["backend"], "memory")
        self.assertTrue(cfg["enabled"])
        self.assertTrue(cfg["window_seconds"] >= 1)
        self.assertTrue(cfg["authenticated_max"] >= 1)
        self.assertTrue(cfg["anonymous_max"] >= 1)
        self.assertTrue(cfg["expensive_max"] >= 1)

    def test_zero_values_sanitized_to_minimum(self):
        s = Settings(
            RATE_LIMIT_WINDOW_SECONDS=0,
            RATE_LIMIT_AUTHENTICATED_MAX=0,
            RATE_LIMIT_ANONYMOUS_MAX=0,
            RATE_LIMIT_EXPENSIVE_MAX=-5,
            _env_file=None,
        )
        cfg = s.rate_limit_config
        self.assertEqual(cfg["window_seconds"], 1)
        self.assertEqual(cfg["authenticated_max"], 1)
        self.assertEqual(cfg["anonymous_max"], 1)
        self.assertEqual(cfg["expensive_max"], 1)

    @patch("app.core.config.logger")
    def test_production_memory_warns_once(self, mock_logger):
        s = Settings(ENVIRONMENT="production", RATE_LIMIT_ENABLED=True, _env_file=None)
        s.rate_limit_config
        self.assertTrue(mock_logger.warning.called)

    @patch("app.core.config.logger")
    def test_nonproduction_memory_no_warning(self, mock_logger):
        s = Settings(ENVIRONMENT="development", RATE_LIMIT_ENABLED=True, _env_file=None)
        s.rate_limit_config
        self.assertFalse(mock_logger.warning.called)


class TestMemoryBackend(unittest.TestCase):
    def test_allow_until_limit(self):
        be = MemoryRateLimitBackend()
        key = be.key("ip-a")
        for _ in range(3):
            self.assertTrue(be.check_limit(key, 3, 60).allowed)

    def test_reject_at_limit(self):
        be = MemoryRateLimitBackend()
        key = be.key("ip-a")
        for _ in range(3):
            be.check_limit(key, 3, 60)
        res = be.check_limit(key, 3, 60)
        self.assertFalse(res.allowed)
        self.assertGreater(res.retry_after, 0)
        self.assertLessEqual(res.retry_after, 60)

    def test_window_reset(self):
        be = MemoryRateLimitBackend()
        key = be.key("k")
        with patch("app.core.rate_limit.time.monotonic", return_value=100.0):
            self.assertTrue(be.check_limit(key, 2, 60).allowed)
            self.assertTrue(be.check_limit(key, 2, 60).allowed)
            self.assertFalse(be.check_limit(key, 2, 60).allowed)
        # Advance the monotonic clock well past the 60s window -> fresh window.
        with patch("app.core.rate_limit.time.monotonic", return_value=200.0):
            self.assertTrue(be.check_limit(key, 2, 60).allowed)

    def test_key_hashes_identity_no_pii(self):
        be = MemoryRateLimitBackend()
        be.check_limit(be.key("user-secret-uid"), 10, 60)
        raw = [k for k in be._buckets.keys()][0]
        self.assertNotIn("user-secret-uid", raw)
        self.assertEqual(len(raw), 64)  # SHA-256 hex

    def test_concurrent_access_no_crash(self):
        be = MemoryRateLimitBackend()
        errors = []

        def worker():
            try:
                for _ in range(200):
                    be.check_limit(be.key("k"), 10, 60)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_fail_open_when_key_cap_reached(self):
        be = MemoryRateLimitBackend(max_keys=2)
        be.check_limit(be.key("a"), 10, 60)
        be.check_limit(be.key("b"), 10, 60)
        # Table full; a third unique key fails open (allowed) and warns.
        res = be.check_limit(be.key("c"), 10, 60)
        self.assertTrue(res.allowed)

    def test_clear(self):
        be = MemoryRateLimitBackend()
        be.check_limit(be.key("a"), 10, 60)
        self.assertEqual(be.bucket_count(), 1)
        be.clear()
        self.assertEqual(be.bucket_count(), 0)


def _build_mw_app(anonymous_max=3, enabled=True, client_probe=True, window=60, max_keys=20000):
    """App with just the RateLimitMiddleware + security/logging envelope."""
    app = FastAPI()
    origins = cors_origins_for("development", "http://localhost:5173")

    @app.get("/public")
    def public():
        return {"public": True}

    @app.get("/healthz")
    def hz():
        return {"status": "ok"}

    @app.get("/health/readyz")
    def ready():
        return {"status": "ready"}

    app.add_middleware(RateLimitMiddleware,
                       enabled=enabled, anonymous_max=anonymous_max,
                       window_seconds=window, max_keys=max_keys)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=False)
    app.add_middleware(CORSMiddleware,
                       allow_origins=origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    return app


class TestAnonymousMiddleware(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(_build_mw_app(anonymous_max=3), base_url="http://localhost")

    def test_allows_until_limit(self):
        for _ in range(3):
            self.assertEqual(self.client.get("/public").status_code, 200)

    def test_429_after_limit(self):
        for _ in range(3):
            self.client.get("/public")
        r = self.client.get("/public")
        self.assertEqual(r.status_code, 429)
        self.assertIn("application/json", r.headers.get("content-type", ""))
        self.assertIn("Too many requests", r.json().get("detail", ""))

    def test_retry_after_header_present(self):
        for _ in range(3):
            self.client.get("/public")
        r = self.client.get("/public")
        self.assertIsNotNone(r.headers.get("retry-after"))
        self.assertTrue(r.headers["retry-after"].isdigit())

    def test_health_paths_always_exempt(self):
        # hammer health beyond limit repeatedly, never 429
        for _ in range(20):
            self.assertEqual(self.client.get("/healthz").status_code, 200)
            self.assertEqual(self.client.get("/health/readyz").status_code, 200)

    def test_429_receives_security_headers_and_request_id(self):
        for _ in range(3):
            self.client.get("/public")
        r = self.client.get("/public")
        self.assertEqual(r.headers.get("x-content-type-options"), "nosniff")
        self.assertIn("frame-ancestors 'none'", r.headers.get("content-security-policy", ""))
        self.assertTrue(r.headers.get("x-request-id"))

    def test_disabled_bypasses(self):
        client = TestClient(_build_mw_app(anonymous_max=3, enabled=False), base_url="http://localhost")
        for _ in range(50):
            self.assertEqual(client.get("/public").status_code, 200)

    def test_x_forwarded_for_not_trusted(self):
        # Same client IP regardless of spoofed X-Forwarded-For -> same bucket.
        for _ in range(3):
            self.assertEqual(self.client.get("/public").status_code, 200)
        r = self.client.get("/public", headers={"X-Forwarded-For": "10.9.9.9"})
        self.assertEqual(r.status_code, 429)  # still counting the real client


class TestPerUserDependency(unittest.TestCase):
    def _app(self):
        app = FastAPI()
        origins = cors_origins_for("development", "http://localhost:5173")

        @app.get("/expensive", dependencies=[Depends(expensive_rate_limiter)])
        def expensive():
            return {"ok": True}

        @app.get("/authed", dependencies=[Depends(authenticated_rate_limiter)])
        def authed():
            return {"ok": True}

        @app.get("/normal")
        def normal():
            return {"ok": True}

        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                           allow_methods=["*"], allow_headers=["*"])
        return app

    def setUp(self):
        configure_rate_limits(enabled=True, window_seconds=60,
                              authenticated_max=5, expensive_max=2, max_keys=20000)
        self.app = self._app()

    def tearDown(self):
        # Leave the process-global dependency state disabled so other test
        # modules are never throttled.
        configure_rate_limits(enabled=False, window_seconds=60,
                              authenticated_max=5, expensive_max=2, max_keys=20000)

    def _client_for(self, uid):
        # Each call gets its OWN app instance so its dependency override points
        # at a single UID. The counter table is still the shared module-global
        # limiter, which is exactly what we want to assert per-UID independence.
        app = self._app()
        app.dependency_overrides[get_current_user] = lambda: _mk_user(uid)
        return TestClient(app, base_url="http://localhost")

    def test_expensive_rejects_after_limit(self):
        c = self._client_for("uid-a")
        self.assertEqual(c.get("/expensive").status_code, 200)
        self.assertEqual(c.get("/expensive").status_code, 200)
        r = c.get("/expensive")
        self.assertEqual(r.status_code, 429)
        self.assertIsNotNone(r.headers.get("retry-after"))

    def test_users_are_independent(self):
        a = self._client_for("uid-a")
        b = self._client_for("uid-b")
        for _ in range(2):
            a.get("/expensive")
        # user B is untouched by A's consumption
        self.assertEqual(b.get("/expensive").status_code, 200)
        # but A is now blocked
        self.assertEqual(a.get("/expensive").status_code, 429)

    def test_authenticated_has_own_ceiling(self):
        c = self._client_for("uid-a")
        for _ in range(5):
            self.assertEqual(c.get("/authed").status_code, 200)
        self.assertEqual(c.get("/authed").status_code, 429)
        # normal (no dependency) is unaffected
        self.assertEqual(c.get("/normal").status_code, 200)

    def test_window_resets_per_user(self):
        c = self._client_for("uid-a")
        for _ in range(2):
            c.get("/expensive")
        self.assertEqual(c.get("/expensive").status_code, 429)
        with patch("app.core.rate_limit.time.monotonic", return_value=1_000_000.0):
            self.assertEqual(c.get("/expensive").status_code, 200)

    def test_disabled_no_429(self):
        configure_rate_limits(enabled=False, window_seconds=60,
                              authenticated_max=5, expensive_max=2, max_keys=20000)
        c = self._client_for("uid-a")
        for _ in range(20):
            self.assertEqual(c.get("/expensive").status_code, 200)


if __name__ == "__main__":
    unittest.main()
