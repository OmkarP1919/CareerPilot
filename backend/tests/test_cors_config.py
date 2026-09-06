"""Phase 5E.1 - CORS configuration and middleware behavior.

These tests exercise the config-driven CORS allowlist without requiring any
external service: origin resolution is tested directly, and middleware
behavior is verified with a minimal in-memory FastAPI app.
"""

import unittest

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import (
    DEV_CORS_ORIGINS,
    Settings,
    cors_origins_for,
)


def _build_app(origins: list[str]) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return {"ok": True}

    return app


class TestCorsOriginResolution(unittest.TestCase):
    def test_development_default_includes_localhost(self):
        origins = Settings(ENVIRONMENT="development", CORS_ORIGINS="").allowed_cors_origins
        self.assertEqual(origins, DEV_CORS_ORIGINS)
        self.assertIn("http://localhost:5173", origins)

    def test_default_environment_is_development_and_uses_localhost(self):
        origins = Settings(CORS_ORIGINS="").allowed_cors_origins
        self.assertEqual(origins, DEV_CORS_ORIGINS)

    def test_production_explicit_origin_allowed(self):
        origins = Settings(
            ENVIRONMENT="production",
            CORS_ORIGINS="https://app.careerpilot.app",
        ).allowed_cors_origins
        self.assertEqual(origins, ["https://app.careerpilot.app"])

    def test_multiple_origins_normalized_and_deduplicated(self):
        origins = cors_origins_for(
            "production",
            "https://a.example.com, http://localhost:8080 , https://a.example.com/",
        )
        self.assertEqual(origins, ["https://a.example.com", "http://localhost:8080"])

    def test_empty_entries_dropped_and_whitespace_trimmed(self):
        origins = cors_origins_for("production", "  , https://app.example.com , , ")
        self.assertEqual(origins, ["https://app.example.com"])

    def test_production_without_configured_origins_fails_safely(self):
        for env in ("production", "prod", "staging"):
            with self.subTest(env=env):
                settings = Settings(ENVIRONMENT=env, CORS_ORIGINS="")
                with self.assertRaises(ValueError):
                    _ = settings.allowed_cors_origins

    def test_wildcard_origin_rejected(self):
        for raw in ("*", "https://app.example.com, *"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    cors_origins_for("production", raw)

    def test_malformed_origins_rejected(self):
        for raw in (
            "not-a-url",
            "http://",
            "https://app.example.com/path",
            "https://app.example.com?q=1",
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    cors_origins_for("production", raw)


class TestCorsMiddlewareBehavior(unittest.TestCase):
    def test_configured_production_origin_allowed(self):
        origins = cors_origins_for("production", "https://app.example.com")
        client = TestClient(_build_app(origins))
        response = client.options(
            "/",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "https://app.example.com",
        )

    def test_unrelated_origin_not_allowed(self):
        origins = cors_origins_for("production", "https://app.example.com")
        client = TestClient(_build_app(origins))
        response = client.options(
            "/",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_localhost_development_origin_allowed(self):
        client = TestClient(_build_app(DEV_CORS_ORIGINS))
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:5173",
        )

    def test_multiple_configured_origins_all_allowed(self):
        origins = cors_origins_for(
            "production",
            "https://a.example.com,https://b.example.com",
        )
        client = TestClient(_build_app(origins))
        for origin in origins:
            with self.subTest(origin=origin):
                response = client.options(
                    "/",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "GET",
                    },
                )
                self.assertEqual(
                    response.headers.get("access-control-allow-origin"),
                    origin,
                )

    def test_resolved_origins_never_contain_wildcard(self):
        self.assertNotIn("*", DEV_CORS_ORIGINS)
        for env in ("development", "test"):
            self.assertNotIn("*", cors_origins_for(env, ""))
        for raw in ("https://app.example.com", "https://a.example.com , http://localhost:5173"):
            self.assertNotIn("*", cors_origins_for("production", raw))


if __name__ == "__main__":
    unittest.main()