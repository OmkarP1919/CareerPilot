"""CareerPilot release smoke harness (Phase 5E.13).

A repeatable, deterministic, pre-deployment release gate that exercises the
behaviors a real deployment depends on WITHOUT touching production resources.

Run from the backend directory (so ``app`` resolves):

    python -m scripts.release_smoke [--json] [--fail-fast] [--pg] [--frontend-build]

Design rules
------------

- **Deterministic & offline by default.** Checks A-N never make a network
  call and never read real credentials. External job providers are replaced
  with in-process fake providers or exercised in their "credentials absent"
  mode; the database is an in-memory/temp SQLite instance (or mocked) so no
  PostgreSQL server is required. The only live-PostgreSQL checks are PG.1/PG.2
  and they are **gated**: they SKIP (never fail) unless both ``--pg`` and
  ``POSTGRES_TEST_DATABASE_URL`` are provided.
- **No production credentials.** The harness never loads a real Firebase,
  Adzuna, Jooble, Jobicy, or AI provider configuration into a live call. It
  validates that the *configuration* fails fast when unsafe and that
  *behavior* works with mocked/absent credentials.
- **Honest statuses.** Every check is one of:
    PASS   - the required behavior was verified end-to-end.
    SKIP   - an OPTIONAL/ENVIRONMENT-GATED check could not run this time
             (reason is always printed). Skips never block a release.
    FAIL   - a required behavior is broken. Any FAIL fails the gate.
  Unknown/unexpected behavior (an exception inside a check) is recorded as
  FAIL, never silently passed.
- **Distinct from the full test suite.** The unittest suite proves
  regression behavior; this harness is the *deployment* gate: it verifies the
  process can start and route, the production configuration is safe, the HTTP
  security contract holds, authentication/rate limiting are wired, discovery,
  saved searches, the application pipeline, storage safety, analytics, backup
  ops, the frontend build contract, and repository integrity are all intact.

Exit codes
----------
    0  RELEASE GATE: PASS (no FAIL results; skips allowed)
    1  RELEASE GATE: FAIL (one or more required checks failed)
    2  usage error (unknown flag)

This module is intentionally stdlib + already-pinned-dependency only (fastapi,
pydantic-settings, sqlalchemy, httpx) so it can run in the same environment as
the backend service. The optional ``--frontend-build`` flag shells out to npm;
without it check M is a static contract check only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.body_limit import RequestBodyLimitMiddleware
from app.core.config import (
    DEFAULT_MAX_REQUEST_BODY_BYTES,
    DEV_TRUSTED_HOSTS,
    Settings,
    cors_origins_for,
    trusted_hosts_for,
)
from app.core.rate_limit_deps import configure_rate_limits
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.core.request_middleware import RequestLoggingMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.services import discovery_service
from app.services.job_sources.adzuna import AdzunaSource
from app.services.job_sources.base import (
    SearchCriteria,
    SourceUnavailableError,
)

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.profile import router as profile_router
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.discovery import router as discovery_router
from app.api.match import router as match_router
from app.api.resume_analysis import router as resume_analysis_router
from app.api.resume_tailoring import router as resume_tailoring_router
from app.api.resume_tailoring import tailored_list_router
from app.api.resume_export import router as resume_export_router
from app.api.cover_letter import router as cover_letter_router
from app.api.cover_letter import collection_router as cover_letter_collection_router
from app.api.applications import router as applications_router
from app.api.analytics import router as analytics_router

from app.models.user import User
from app.models.job import Job
from app.models.resume import Resume
from app.models.application import Application
from app.models.application_event import ApplicationEvent
from app.models.application_interview import ApplicationInterview
from app.models.application_document import ApplicationDocument
from app.models.job_match import JobMatch
from app.models.saved_search import SavedSearch

import app.api.health as health_module
import app.dependencies.auth as auth_deps
import app.core.storage as storage
from app.core.storage import (
    delete_file_safely,
    resolve_user_file_path,
    safe_stored_filename,
    sanitize_name,
    write_upload_atomic,
)
from app.database.base import Base, get_db
from app.dependencies.auth import get_current_user

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

# Protected Resume Parsing 2.0 files. The committed baseline blob for each path
# (HEAD) must never change without the deliberate, documented release process
# described in docs/ci_cd.md. Values are the committed SHA-1 blob hashes at the
# protected baseline commit (origin/main). A local working tree may carry
# uncommitted edits; check N compares the committed HEAD blob only.
PROTECTED_FILES_AT_HEAD = {
    "backend/app/services/resume_parser.py": "8b993dedf6460c0c87460ef8804a39dac43d4ef3",
    "backend/tests/test_resume_parser.py": "f7f18c8e33d9c79743f198dc7ed2ede4b5f1dcfb",
    "frontend/src/pages/ResumesPage.jsx": "e318462452d5df17f64d5049ecb13ecf67fc1b13",
}

_MAX_TITLE_WIDTH = 40

_ALL_ROUTERS = [
    health_router,
    auth_router,
    profile_router,
    resumes_router,
    jobs_router,
    discovery_router,
    match_router,
    resume_analysis_router,
    resume_tailoring_router,
    tailored_list_router,
    resume_export_router,
    cover_letter_router,
    cover_letter_collection_router,
    applications_router,
    analytics_router,
]


@dataclass
class SmokeResult:
    letter: str
    title: str
    status: str
    message: str


@dataclass
class Options:
    json: bool = False
    fail_fast: bool = False
    pg: bool = False
    frontend_build: bool = False


def _cleanup_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _temp_sqlite(prefix: str = "cp_smoke_"):
    """Return (base_dir, engine, Session) for an isolated on-disk SQLite DB."""
    base = Path(tempfile.mkdtemp(prefix=prefix))
    engine = create_engine(
        f"sqlite:///{base / 'smoke.db'}",
        connect_args={"check_same_thread": False},
    )
    # The model imports above have already registered every table on
    # Base.metadata; create them all so each check sees a real schema.
    Base.metadata.create_all(engine)
    return base, engine, sessionmaker(bind=engine)


def _build_full_app(
    trusted_hosts=None,
    body_max: int = DEFAULT_MAX_REQUEST_BODY_BYTES,
    hsts: bool = False,
    rate_enabled: bool = False,
    anonymous_max: int = 120,
    window_seconds: int = 60,
    max_keys: int = 20_000,
) -> FastAPI:
    """Wire every production router with the exact middleware order of main.py
    (see app/main.py for the documented ordering). Dev-safe settings only."""
    app = FastAPI()

    @app.get("/")
    def root():
        return {"message": "CareerPilot AI API"}

    for router in _ALL_ROUTERS:
        app.include_router(router)
    origins = cors_origins_for("development", "http://localhost:5173")
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=body_max)
    app.add_middleware(
        RateLimitMiddleware,
        enabled=rate_enabled,
        anonymous_max=anonymous_max,
        window_seconds=window_seconds,
        max_keys=max_keys,
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=trusted_hosts if trusted_hosts is not None else DEV_TRUSTED_HOSTS,
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=hsts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


def _override_db_app(engine, session_factory, routers, current_user_id="user_a"):
    """A TestClient-ready app with get_db/get_current_user overridden.

    ``current_user_id`` is read through a mutable holder so an individual check
    can switch identity mid-flight (used for cross-user isolation checks).
    """
    app = FastAPI()
    for router in routers:
        app.include_router(router)
    holder = {"id": current_user_id}

    def override_get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    def override_get_current_user():
        s = session_factory()
        try:
            return s.query(User).filter(User.id == holder["id"]).first()
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return app, holder


# ---------------------------------------------------------------------------
# Check implementation helpers
# ---------------------------------------------------------------------------

def _require(value: bool, msg: str) -> tuple[str, str] | None:
    """Return a FAIL result tuple when ``value`` is falsy, else None."""
    if not value:
        return (FAIL, msg)
    return None


def _security_headers_ok(response) -> list[str]:
    problems = []
    if response.headers.get("x-content-type-options") != "nosniff":
        problems.append("missing x-content-type-options: nosniff")
    if response.headers.get("x-frame-options") != "DENY":
        problems.append("missing x-frame-options: DENY")
    if response.headers.get("referrer-policy") != "strict-origin-when-cross-origin":
        problems.append("missing referrer-policy")
    csp = response.headers.get("content-security-policy", "")
    if "default-src 'none'" not in csp:
        problems.append("missing conservative CSP")
    if "'unsafe-inline'" in csp or "'unsafe-eval'" in csp:
        problems.append("CSP contains unsafe-* directives")
    return problems


# ---------------------------------------------------------------------------
# Checks A-N
# ---------------------------------------------------------------------------

def _collect_paths(app) -> set[str]:
    """Return every route path, including routers that FastAPI 0.141+ includes
    lazily (``app.routes`` then exposes ``_IncludedRouter`` entries whose routes
    live on ``original_router``)."""
    paths = set()
    stack = [getattr(app, "router", None)]
    seen = set()
    while stack:
        container = stack.pop()
        if container is None or id(container) in seen:
            continue
        seen.add(id(container))
        for r in getattr(container, "routes", []):
            path = getattr(r, "path", None)
            if isinstance(path, str):
                paths.add(path)
            original = getattr(r, "original_router", None)
            if original is not None:
                stack.append(original)
    return paths


def check_a(opts: Options):
    """Backend bootstrap: every router mounts, routes resolve, liveness works."""
    app = _build_full_app()
    paths = _collect_paths(app)
    prefixes = [
        "/auth", "/profile", "/resumes", "/resumes/tailored",
        "/jobs", "/jobs/discovery", "/cover-letters", "/applications",
        "/analytics", "/healthz", "/health",
    ]
    missing = [
        p for p in prefixes
        if p != "/" and not any(candidate.startswith(p.rstrip("/")) for candidate in paths)
    ]
    if "/" not in paths:
        missing.append("/")
    if missing:
        return FAIL, f"unmounted route prefixes: {sorted(set(missing))}"
    if len(paths) < 60:
        return FAIL, f"route table unexpectedly small ({len(paths)} routes)"
    client = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)
    r = client.get("/healthz")
    if r.status_code != 200:
        return FAIL, f"/healthz -> HTTP {r.status_code}"
    return PASS, f"{len(_ALL_ROUTERS)} routers, {len(paths)} routes; /healthz 200"


def check_b(opts: Options):
    """Health endpoints: liveness, compat alias, and simulated readiness."""
    app = _build_full_app()
    client = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)

    for path, expected in (("/healthz", {"status": "ok"}), ("/health", {"status": "healthy"})):
        r = client.get(path)
        if r.status_code != 200 or r.json() != expected:
            return FAIL, f"{path} -> {r.status_code} {r.text!r}"

    class _Healthy:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def execute(self, *a, **k):
            return None

    class _Broken:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def execute(self, *a, **k):
            raise RuntimeError("simulated database outage")

    with mock.patch.object(health_module.engine, "connect", return_value=_Healthy()):
        r = client.get("/health/readyz")
        if r.status_code != 200 or r.json() != {"status": "ready"}:
            return FAIL, f"readyz (healthy) -> {r.status_code} {r.text!r}"

    with mock.patch.object(health_module.engine, "connect", return_value=_Broken()):
        r = client.get("/health/readyz")
        if r.status_code != 503 or r.json() != {"status": "not_ready"}:
            return FAIL, f"readyz (down) -> {r.status_code} {r.text!r}"
        if "Traceback" in r.text or "RuntimeError" in r.text:
            return FAIL, "readyz leaked internal error details"
        if r.headers.get("x-content-type-options") != "nosniff":
            return FAIL, "readyz response missing security headers"

    return PASS, "healthz/health 200; readyz 200/503 verified (simulated engine; live PG is PG.1)"


def check_c(opts: Options):
    """Production configuration fails fast instead of shipping unsafe defaults."""
    problems = []

    def record(fn):
        try:
            fn()
            problems.append("expected a safety exception but none was raised")
        except ValueError:
            pass
        except Exception as exc:  # noqa: BLE001 - any failure to fail-fast is a problem
            problems.append(f"raised {type(exc).__name__} instead of ValueError")

    record(lambda: cors_origins_for("production", ""))
    record(lambda: trusted_hosts_for("production", ""))
    record(lambda: Settings(ENVIRONMENT="production", CORS_ORIGINS="").allowed_cors_origins)
    record(lambda: Settings(ENVIRONMENT="production", TRUSTED_HOSTS="").allowed_trusted_hosts)
    record(lambda: cors_origins_for("staging", "*"))
    record(lambda: trusted_hosts_for("production", "*"))

    valid = cors_origins_for("production", "https://app.example.com,https://api.example.com")
    if valid != ["https://app.example.com", "https://api.example.com"]:
        problems.append(f"valid production origins not resolved: {valid!r}")
    hosts = trusted_hosts_for("production", "api.example.com,*.example.com")
    if hosts != ["api.example.com", "*.example.com"]:
        problems.append(f"valid production hosts not resolved: {hosts!r}")

    s = Settings(ENVIRONMENT="production", CORS_ORIGINS="https://app.example.com")
    if s.allowed_cors_origins != ["https://app.example.com"]:
        problems.append("production Settings resolved wrong CORS origins")
    if Settings(ENABLE_HSTS=True).hsts_enabled is not True:
        problems.append("HSTS opt-in not honored")
    if Settings(ENVIRONMENT="production", ENABLE_HSTS=False).hsts_enabled is not False:
        problems.append("HSTS leaked on without opt-in")

    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "empty/unsafe production CORS+TRUSTED_HOSTS fail fast; explicit config valid; HSTS opt-in"


def check_d(opts: Options):
    """The HTTP security contract holds on success AND on rejection paths."""
    app = _build_full_app(trusted_hosts=DEV_TRUSTED_HOSTS, body_max=1000)

    @app.post("/echo")
    async def _echo(request: Request):
        body = await request.body()
        return {"len": len(body)}

    client = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)
    problems = []
    base_checks = 0

    r = client.get("/")
    if r.status_code != 200:
        return FAIL, f"GET / -> {r.status_code}"
    problems += _security_headers_ok(r)
    if r.headers.get("strict-transport-security") is not None:
        problems.append("HSTS present in development")
    base_checks += 1

    r404 = client.get("/missing")
    if r404.status_code != 404:
        problems.append(f"404 path -> {r404.status_code}")
    problems += _security_headers_ok(r404)
    base_checks += 1

    r413 = client.post("/echo", content=b"x" * 1001)
    if r413.status_code != 413:
        problems.append(f"oversized body -> {r413.status_code}")
    if r413.json().get("detail") != "Request body too large":
        problems.append("413 detail contract changed")
    if r413.headers.get("x-content-type-options") != "nosniff":
        problems.append("413 missing security headers")
    if not r413.headers.get("x-request-id"):
        problems.append("413 missing request ID")
    for leak in ("x" * 20, "/echo", "Traceback", "secret"):
        if leak in r413.text:
            problems.append(f"413 leaked {leak!r}")
    base_checks += 1

    rhost = client.post("/echo", content=b"x", headers={"host": "evil.example.com"})
    if rhost.status_code != 400 or "Invalid host header" not in rhost.text:
        problems.append(f"disallowed host -> {rhost.status_code} {rhost.text!r}")
    if "TRUSTED_HOSTS" in rhost.text:
        problems.append("host rejection leaked TRUSTED_HOSTS config")
    if not rhost.headers.get("x-request-id"):
        problems.append("host rejection missing request ID")
    base_checks += 1

    hsts_app = _build_full_app(hsts=True)
    r_hsts = TestClient(hsts_app, base_url="http://localhost").get("/")
    if r_hsts.headers.get("strict-transport-security") != "max-age=31536000":
        problems.append("HSTS header missing when enabled")

    if problems:
        return FAIL, "; ".join(dict.fromkeys(problems))
    return PASS, f"security headers, 413, TrustedHost, request IDs verified across {base_checks + 1} paths"


def check_e(opts: Options):
    """Authentication contract: 401 without creds, 401 on invalid token, provisioning."""
    base, engine, session_factory = _temp_sqlite("cp_smoke_auth_")

    def _app():
        a = FastAPI()
        a.include_router(health_router)
        a.include_router(applications_router)

        def override_get_db():
            s = session_factory()
            try:
                yield s
            finally:
                s.close()

        a.dependency_overrides[get_db] = override_get_db
        a.add_middleware(RequestLoggingMiddleware)
        return a

    client = TestClient(_app(), base_url="http://localhost", raise_server_exceptions=False)
    problems = []

    r = client.get("/applications")
    if r.status_code != 401:
        problems.append(f"no token -> {r.status_code}")
    elif "Authorization header required" not in r.text:
        problems.append("missing-token detail changed: expected 'Authorization header required'")

    with mock.patch.object(auth_deps, "verify_firebase_token", side_effect=Exception("simulated expiry")):
        r = client.get("/applications", headers={"Authorization": "Bearer bogus-token"})
        if r.status_code != 401:
            problems.append(f"invalid token -> {r.status_code}")
        if "Traceback" in r.text:
            problems.append("invalid token leaked a traceback")

    token = {"uid": "fb_provision", "email": "provision@test.invalid", "name": "Provision"}
    with mock.patch.object(auth_deps, "verify_firebase_token", return_value=token):
        r1 = client.get("/applications", headers={"Authorization": "Bearer valid-token"})
        if r1.status_code != 200:
            problems.append(f"valid token (first login) -> {r1.status_code} {r1.text!r}")
        r2 = client.get("/applications", headers={"Authorization": "Bearer valid-token"})
        if r2.status_code != 200:
            problems.append(f"valid token (second) -> {r2.status_code}")

    db = session_factory()
    count = db.query(User).filter(User.firebase_uid == "fb_provision").count()
    db.close()
    if count != 1:
        problems.append(f"first-login provisioning created {count} user row(s), expected exactly 1")

    _cleanup_dir(base)
    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "401 on missing/invalid token (no leak); first-login provisioning idempotent"


def check_f(opts: Options):
    """Rate limiting: client-IP middleware 429 and per-user dependency 429."""
    problems = []

    app = FastAPI()

    @app.get("/_ping")
    def _ping():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, enabled=True, anonymous_max=3, window_seconds=60, max_keys=1000)
    client = TestClient(app, base_url="http://testserver", raise_server_exceptions=False)
    statuses = [client.get("/_ping").status_code for _ in range(3)]
    if statuses != [200, 200, 200]:
        problems.append(f"anonymous limit over-tight: {statuses}")
    r = client.get("/_ping")
    if r.status_code != 429:
        problems.append(f"anonymous 4th request -> {r.status_code}")
    if not r.headers.get("retry-after"):
        problems.append("anonymous 429 missing Retry-After")

    base, engine, session_factory = _temp_sqlite("cp_smoke_rate_")
    uploads = base / "uploads"
    uploads.mkdir()
    db = session_factory()
    db.add_all([
        User(id="user_a", firebase_uid="fb_rate", email="rate@test.invalid", name="A"),
        Job(id="job_1", user_id="user_a", title="Dev", company="Acme", description="d", required_skills="python"),
        Application(id="app_a", user_id="user_a", job_id="job_1", status="Applied"),
    ])
    db.commit()
    db.close()

    a2 = FastAPI()
    a2.include_router(applications_router)

    def override_get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    def override_get_current_user():
        s = session_factory()
        try:
            return s.query(User).filter(User.id == "user_a").first()
        finally:
            s.close()

    a2.dependency_overrides[get_db] = override_get_db
    a2.dependency_overrides[get_current_user] = override_get_current_user

    configure_rate_limits(enabled=True, window_seconds=60, authenticated_max=300, expensive_max=2, max_keys=100_000)
    try:
        client2 = TestClient(a2, base_url="http://localhost", raise_server_exceptions=False)
        with mock.patch("app.api.applications.UPLOAD_DIR", str(uploads)):
            for i in range(2):
                r = client2.post(
                    "/applications/app_a/documents/upload",
                    files={"file": ("cv.pdf", b"%PDF-1.4 " + b"a" * 300, "application/pdf")},
                    data={"document_type": "resume"},
                )
                if r.status_code != 201:
                    problems.append(f"upload {i + 1} (under limit) -> {r.status_code} {r.text!r}")
            r = client2.post(
                "/applications/app_a/documents/upload",
                files={"file": ("cv.pdf", b"%PDF-1.4 " + b"a" * 300, "application/pdf")},
                data={"document_type": "resume"},
            )
            if r.status_code != 429:
                problems.append(f"per-user 3rd request -> {r.status_code}")
            if not r.headers.get("retry-after"):
                problems.append("per-user 429 missing Retry-After")
    finally:
        configure_rate_limits(enabled=False)

    _cleanup_dir(base)
    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "client-IP middleware 429 + per-user expensive-route 429 enforced"


def check_g(opts: Options):
    """Offline job discovery: orchestrator isolation, dedup, and no-cred mode."""
    from app.services.job_sources.base import NormalizedJob

    problems = []

    def _job(name, source):
        return NormalizedJob(
            external_id=f"{source}-{name}",
            title="Python Developer",
            company="Acme",
            location="Remote",
            description="Build things in python",
            skills=["python"],
            source=source,
            posted_at="2026-09-01T00:00:00Z",
        )

    class _FakeOk:
        name = None

        def __init__(self, source):
            self.name = source

        @property
        def is_enabled(self):
            return True

        def fetch(self, criteria):
            return [_job("a", self.name)]

    class _FakeBroken:
        name = "FakeFail"

        @property
        def is_enabled(self):
            return True

        def fetch(self, criteria):
            raise SourceUnavailableError("backend down")

    from app.services.job_sources.orchestrator import DiscoveryOrchestrator

    criteria = SearchCriteria(queries=["python"], locations=["Remote"], skills=["python"])
    outcome = DiscoveryOrchestrator(
        [_FakeOk("FakeA"), _FakeOk("FakeB"), _FakeBroken()]
    ).search_filtered(criteria, concurrency=True)

    statuses = sorted(r.status.value for r in outcome["results"])
    if statuses != ["success", "success", "unavailable"]:
        problems.append(f"orchestrator status isolation broken: {statuses}")
    if outcome["errors"] != ["FakeFail was temporarily unavailable."]:
        problems.append(f"errors not sanitized: {outcome['errors']!r}")

    records, dup = discovery_service.dedupe_jobs(outcome["jobs"])
    if len(records) != 1:
        problems.append(f"dedup produced {len(records)} group(s), expected 1")
    if dup != 1:
        problems.append(f"duplicate count was {dup}, expected 1")
    if records and records[0]["sources"] != ["FakeA", "FakeB"]:
        problems.append(f"cross-source provenance wrong: {records[0]['sources']}")

    no_creds = Settings(ADZUNA_APP_ID="", ADZUNA_APP_KEY="", ADZUNA_COUNTRY="us", ADZUNA_TIMEOUT_SECONDS=0.5)
    with mock.patch("app.services.job_sources.adzuna.get_settings", return_value=no_creds):
        src = AdzunaSource()
        if src.is_enabled is not False:
            problems.append("Adzuna without credentials reported enabled")
        fetched = src.fetch(criteria)
        if fetched != []:
            problems.append(f"Adzuna no-credentials fetch returned {len(fetched)} job(s)")

    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "orchestrator isolates failure; cross-source dedup; Adzuna no-creds returns empty"


def check_h(opts: Options):
    """Saved searches: create/list/update/run(new-results semantics)/delete."""
    base, engine, session_factory = _temp_sqlite("cp_smoke_saved_")
    db = session_factory()
    db.add(User(id="u_a", firebase_uid="fb_saved", email="saved@test.invalid", name="A"))
    db.commit()

    problems = []
    try:
        saved = discovery_service.create_saved_search("u_a", db, "Search A", {"queries": ["python"]})
        if saved is None:
            problems.append("create_saved_search returned None")

        lst = discovery_service.list_saved_searches("u_a", db)
        if len(lst) != 1:
            problems.append(f"list_saved_searches -> {len(lst)} row(s)")

        from app.schemas.discovery import DiscoveryJobHit, DiscoveryReport

        canned = DiscoveryReport(
            total=1,
            unique_results=1,
            results=[
                DiscoveryJobHit(
                    canonical_key="python developer|acme|remote",
                    title="Python Developer",
                    company="Acme",
                )
            ],
        )

        def fake_run(user_id, session, request):
            return canned

        with mock.patch.object(discovery_service, "run_filtered_search", side_effect=fake_run) as m:
            first = discovery_service.run_saved_search("u_a", db, saved.id)
            second = discovery_service.run_saved_search("u_a", db, saved.id)
            if first["new_results"] != 1:
                problems.append(f"first run new_results={first['new_results']}, expected 1")
            if second["new_results"] != 0:
                problems.append(f"second run new_results={second['new_results']}, expected 0")
            if m.call_count != 2:
                problems.append(f"run_filtered_search called {m.call_count} time(s)")

        updated = discovery_service.update_saved_search("u_a", db, saved.id, "Renamed", {"queries": ["java"]})
        if updated is None or updated.name != "Renamed":
            problems.append("update_saved_search did not persist rename")

        if discovery_service.delete_saved_search("u_a", db, saved.id) is not True:
            problems.append("delete_saved_search did not return True")
        if list(discovery_service.list_saved_searches("u_a", db)):
            problems.append("saved search still listed after delete")
        if discovery_service.delete_saved_search("u_a", db, saved.id) is not False:
            problems.append("second delete did not return False")
    finally:
        db.close()
        _cleanup_dir(base)

    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "create/list/update/run (1 then 0 new) /delete all correct"


def check_i(opts: Options):
    """Application pipeline: create -> event -> interview -> docs -> timeline -> delete."""
    base, engine, session_factory = _temp_sqlite("cp_smoke_pipe_")
    uploads = base / "uploads"
    uploads.mkdir()
    db = session_factory()
    db.add_all([
        User(id="user_a", firebase_uid="fb_pipe", email="pipe@test.invalid", name="A"),
        User(id="user_b", firebase_uid="fb_other", email="other@test.invalid", name="B"),
        Job(id="job_1", user_id="user_a", title="Dev", company="Acme", description="d", required_skills="python"),
        Resume(
            id="res_1", user_id="user_a", filename="under.pdf", original_filename="under.pdf",
            file_path=str(uploads / "user_a" / "under.pdf"), file_size="10",
            is_master=True, parsing_status="parsed",
        ),
    ])
    db.commit()
    db.close()

    app, holder = _override_db_app(engine, session_factory, [applications_router], "user_a")
    app.add_middleware(RequestLoggingMiddleware)

    problems = []
    try:
        with mock.patch("app.api.applications.UPLOAD_DIR", str(uploads)):
            client = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)

            r = client.post("/applications", json={"job_id": "job_1", "status": "Applied", "notes": "smoke"})
            if r.status_code != 201:
                return FAIL, f"create application -> {r.status_code} {r.text!r}"
            app_id = r.json()["id"]

            events = client.get(f"/applications/{app_id}/events")
            if events.status_code != 200 or not events.json():
                problems.append("auto-created lifecycle event missing")

            ev = client.post(f"/applications/{app_id}/events", json={"event_type": "note_added", "notes": "n"})
            if ev.status_code != 201:
                problems.append(f"create event -> {ev.status_code}")

            iv = client.post(
                f"/applications/{app_id}/interviews",
                json={"kind": "video", "status": "scheduled", "scheduled_at": "2026-10-01T12:00:00+00:00", "notes": "n"},
            )
            if iv.status_code != 201:
                problems.append(f"create interview -> {iv.status_code} {iv.text!r}")

            ref = client.post(
                f"/applications/{app_id}/documents",
                json={"document_type": "resume", "name": "master", "source_resume_id": "res_1"},
            )
            if ref.status_code != 201:
                problems.append(f"attach reference document -> {ref.status_code} {ref.text!r}")

            up = client.post(
                f"/applications/{app_id}/documents/upload",
                files={"file": ("cv.pdf", b"%PDF-1.4 " + b"a" * 300, "application/pdf")},
                data={"document_type": "contract"},
            )
            if up.status_code != 201:
                problems.append(f"upload document -> {up.status_code} {up.text!r}")
            else:
                stored_files = list(uploads.glob("user_a/*.pdf"))
                if len(stored_files) != 1:
                    problems.append("uploaded file not stored under the user's directory")

            docs = client.get(f"/applications/{app_id}/documents")
            if docs.status_code != 200:
                problems.append(f"document list -> {docs.status_code}")
            elif len(docs.json()) != 2:
                problems.append(f"expected 2 documents, got {len(docs.json())}")

            tl = client.get(f"/applications/{app_id}/timeline")
            entries = len(tl.json().get("entries", [])) if tl.status_code == 200 else None
            if tl.status_code != 200 or (entries is not None and entries < 3):
                problems.append(f"timeline -> {tl.status_code} entries={entries}")

            bad = client.post(
                f"/applications/{app_id}/documents/upload",
                files={"file": ("evil.exe", b"MZ" * 10, "application/octet-stream")},
                data={"document_type": "contract"},
            )
            if bad.status_code != 400:
                problems.append(f"disallowed extension -> {bad.status_code}")

            with mock.patch("app.api.applications.MAX_UPLOAD_SIZE", 10):
                big = client.post(
                    f"/applications/{app_id}/documents/upload",
                    files={"file": ("big.pdf", b"%PDF-1.4 " + b"x" * 20, "application/pdf")},
                    data={"document_type": "contract"},
                )
                if big.status_code != 400:
                    problems.append(f"oversized upload -> {big.status_code}")

            holder["id"] = "user_b"
            isolated = client.get(f"/applications/{app_id}/events")
            if isolated.status_code != 404:
                problems.append(f"cross-user read -> {isolated.status_code} (expected 404)")
            holder["id"] = "user_a"

            rdel = client.delete(f"/applications/{app_id}")
            if rdel.status_code != 204:
                problems.append(f"delete application -> {rdel.status_code}")
            elif list(uploads.glob("user_a/*.pdf")):
                problems.append("uploaded file survived application deletion")
    finally:
        _cleanup_dir(base)

    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "create->event->interview->doc(ref+upload)->timeline->delete all correct"


def check_j(opts: Options):
    """Storage safety: containment, atomic writes, size limits, safe deletion."""
    base = Path(tempfile.mkdtemp(prefix="cp_smoke_storage_"))
    root = base / "store"
    root.mkdir()
    problems = []

    try:
        if resolve_user_file_path("u_a", "../escape.txt", root=root) is not None:
            problems.append("parent traversal was not rejected")
        if resolve_user_file_path("u_a", "sub/../../escape.txt", root=root) is not None:
            problems.append("nested traversal was not rejected")
        if resolve_user_file_path("u_a", "/etc/passwd", root=root) is not None:
            problems.append("absolute escape was not rejected")

        ok = resolve_user_file_path("u_a", "ok.txt", root=root)
        if ok is None or not str(ok.resolve()).replace("\\", "/").endswith("store/u_a/ok.txt"):
            problems.append("valid relative path did not resolve inside user dir")

        name = safe_stored_filename(".PDF")
        if not name.endswith(".pdf") or "/" in name or "\\" in name:
            problems.append("safe_stored_filename is not a single safe component")

        if sanitize_name("a\\b/c\x02d") != "abcd":
            problems.append("sanitize_name did not strip separators/control chars")

        def _chunks(payload):
            pos = [0]
            length = len(payload)

            def read():
                if pos[0] >= length:
                    return b""
                chunk = payload[pos[0]:pos[0] + 7]
                pos[0] += 7
                return chunk

            return read

        stored = write_upload_atomic("u_a", "final.pdf", _chunks(b"%PDF-1.4 abc"), max_size=1000, root=root)
        if not Path(stored).is_file():
            problems.append("atomic write did not produce the final file")

        try:
            write_upload_atomic("u_b", "final.pdf", _chunks(b"x" * 500), max_size=100, root=root)
            problems.append("oversized atomic write did not raise ValueError")
        except ValueError:
            pass
        user_b_dir = root / "u_b"
        final = user_b_dir / "final.pdf"
        leftovers = list(user_b_dir.glob("*.tmp-*")) if user_b_dir.is_dir() else []
        if final.exists() or leftovers:
            problems.append("failed upload left a partial/orphan file")

        victim = root / "u_b" / "victim.txt"
        victim.parent.mkdir(parents=True, exist_ok=True)
        victim.write_text("data")
        delete_file_safely("u_a", str(victim), root=root)
        if not victim.exists():
            problems.append("cross-user absolute deletion was not refused")
        delete_file_safely("u_b", str(victim), root=root)
        if victim.exists():
            problems.append("owner deletion did not remove the file")
        delete_file_safely("u_b", str(victim), root=root)  # idempotent
    finally:
        _cleanup_dir(base)

    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "traversal/abs escapes refused; atomic+size-safe writes; cross-user delete refused"


def check_k(opts: Options):
    """Analytics: truthful, user-scoped aggregations (no synthetic data)."""
    base, engine, session_factory = _temp_sqlite("cp_smoke_analytics_")
    db = session_factory()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add_all([
        User(id="user_a", firebase_uid="fb_ana", email="ana@test.invalid", name="A"),
        User(id="user_b", firebase_uid="fb_anb", email="anb@test.invalid", name="B"),
        Job(id="job_1", user_id="user_a", title="Dev", company="Acme", description="d", required_skills="python"),
        Job(id="job_2", user_id="user_b", title="Ops", company="Acme", description="d", required_skills="bash"),
        JobMatch(id="m1", user_id="user_a", job_id="job_1", overall_score=75,
                 matched_skills='["python"]', missing_skills='["sql"]'),
        JobMatch(id="m2", user_id="user_a", job_id="job_1", overall_score=50,
                 matched_skills="[]", missing_skills="[]"),
        Application(id="a1", user_id="user_a", job_id="job_1", status="Saved"),
        Application(id="a2", user_id="user_a", job_id="job_1", status="Applied"),
        Application(id="a3", user_id="user_b", job_id="job_2", status="Applied"),
        ApplicationEvent(id="e1", application_id="a2", user_id="user_a", event_type="created",
                         created_by="user_a", created_at=now),
        ApplicationInterview(id="i1", application_id="a2", user_id="user_a", kind="video",
                             status="scheduled", scheduled_at=now, created_at=now),
        ApplicationDocument(id="d1", application_id="a2", user_id="user_a", document_type="resume",
                            name="r", created_at=now),
    ])
    db.commit()
    db.close()

    app, _ = _override_db_app(engine, session_factory, [analytics_router], "user_a")
    client = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)
    problems = []

    r = client.get("/analytics/dashboard")
    if r.status_code == 200:
        data = r.json()
        if data["total_jobs"] != 1:
            problems.append(f"total_jobs={data['total_jobs']} (user_b leaked or miscounted)")
        if data["total_applications"] != 2:
            problems.append(f"total_applications={data['total_applications']}")
        if data["saved_count"] != 1 or data["applied_count"] != 1:
            problems.append(f"funnel counts Saved/Applied = {data['saved_count']}/{data['applied_count']}")
        if data["high_match_jobs"] != 1:
            problems.append(f"high_match_jobs={data['high_match_jobs']}")
        if data["average_match_score"] != 62:
            problems.append(f"average_match_score={data['average_match_score']}")
    else:
        problems.append(f"dashboard -> {r.status_code}")

    funnel = client.get("/analytics/application-funnel")
    if funnel.status_code == 200:
        stages = {s["stage"]: s["count"] for s in funnel.json()["funnel"]}
        if stages.get("Saved") != 1 or stages.get("Applied") != 1 or funnel.json()["total"] != 2:
            problems.append(f"funnel wrong: {stages} total={funnel.json()['total']}")
    else:
        problems.append(f"funnel -> {funnel.status_code}")

    skills = client.get("/analytics/skills")
    if skills.status_code == 200:
        if skills.json()["total_analyses"] != 2:
            problems.append(f"skills total_analyses={skills.json()['total_analyses']}")
    else:
        problems.append(f"skills -> {skills.status_code}")

    activity = client.get("/analytics/activity")
    if activity.status_code == 200:
        buckets = activity.json().get("buckets", [])
        latest = buckets[-1] if buckets else {}
        if latest.get("applications", 0) != 2:
            problems.append(f"activity latest-week applications={latest.get('applications')}")
        if latest.get("interviews", 0) != 1 or latest.get("documents", 0) != 1:
            problems.append("activity counts wrong")
    else:
        problems.append(f"activity -> {activity.status_code}")

    velocity = client.get("/analytics/velocity")
    if velocity.status_code != 200:
        problems.append(f"velocity -> {velocity.status_code}")

    _cleanup_dir(base)
    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "dashboard/funnel/skills/activity/velocity truthful and user-scoped"


def check_l(opts: Options):
    """Backup & recovery ops: naming, listing, retention, path confinement."""
    from app.ops import config as backup_cfg

    problems = []

    name = backup_cfg.backup_filename("staging")
    if backup_cfg.is_valid_backup_name(name) is not True:
        problems.append(f"generated backup name invalid: {name!r}")

    for bad in ("escape.dump", "careerpilot_x.dump", "careerpilot_stag_20260101.dump",
                "careerpilot_stag_20260101-120000Z.gz", "../careerpilot_stag_20260101-120000Z.dump"):
        if backup_cfg.is_valid_backup_name(bad):
            problems.append(f"invalid backup name accepted: {bad!r}")

    parsed = backup_cfg.parse_backup_name("careerpilot_production_20260907-120000Z.dump")
    if parsed != ("production", "20260907-120000Z"):
        problems.append(f"parse_backup_name -> {parsed}")

    try:
        backup_cfg.assert_database_configured("")
        problems.append("empty DATABASE_URL accepted by assert_database_configured")
    except backup_cfg.BackupError:
        pass
    try:
        backup_cfg.assert_database_configured("sqlite:///x.db")
        problems.append("non-PostgreSQL URL accepted by assert_database_configured")
    except backup_cfg.BackupError:
        pass
    backup_cfg.assert_database_configured("postgresql://u:p@localhost:5432/cp")

    base = Path(tempfile.mkdtemp(prefix="cp_smoke_backup_"))
    backup_dir = base / "backups"
    backup_dir.mkdir()
    try:
        (backup_dir / "careerpilot_stag_20260905-080000Z.dump").write_bytes(b"old")
        (backup_dir / "careerpilot_stag_20260907-120000Z.dump").write_bytes(b"new")
        (backup_dir / "notabackup.txt").write_text("x")
        (backup_dir / ".hidden.dump").write_text("x")

        listed = backup_cfg.list_backups(backup_dir)
        if [f.name for f in listed] != [
            "careerpilot_stag_20260907-120000Z.dump",
            "careerpilot_stag_20260905-080000Z.dump",
        ]:
            problems.append(f"list_backups returned {[f.name for f in listed]}")

        to_prune = backup_cfg.select_old_backups(listed, keep_count=1)
        if [f.name for f in to_prune] != ["careerpilot_stag_20260905-080000Z.dump"]:
            problems.append(f"select_old_backups -> {[f.name for f in to_prune]}")

        for evil in ("..\\escape.dump", "..", "sub/../../out.dump", "/etc/passwd"):
            try:
                backup_cfg.resolve_backup_path(backup_dir, evil)
                problems.append(f"escape path accepted: {evil!r}")
            except backup_cfg.BackupError:
                pass

        good = backup_cfg.resolve_backup_path(backup_dir, "careerpilot_stag_20260908-000000Z.dump")
        if not good.is_absolute() or not str(good).startswith(str(backup_dir.resolve())):
            problems.append("valid relative backup path not confined")

        try:
            backup_cfg.BackupConfig(database_url="postgresql://u:p@localhost/cp",
                                    backup_dir=str(backup_dir), retention_count=0)
            problems.append("retention_count=0 accepted")
        except backup_cfg.BackupError:
            pass
    finally:
        _cleanup_dir(base)

    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "naming/listing/retention/path-confinement/DB-URL guards all correct"


def check_m(opts: Options):
    """Frontend build contract: static contract validated; optionally real build."""
    problems = []
    pkg = REPO_ROOT / "frontend" / "package.json"
    ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"

    if not pkg.is_file():
        return FAIL, "frontend/package.json missing"
    if not ci.is_file():
        return FAIL, ".github/workflows/ci.yml missing"

    scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
    for key, needle in (
        ("test", "resume-contract.mjs"),
        ("test", "api-deploy-contract.mjs"),
        ("build", "vite build"),
        ("lint", "oxlint"),
    ):
        if needle not in scripts.get(key, ""):
            problems.append(f"package.json scripts.{key} missing {needle!r}")

    if not (REPO_ROOT / "frontend" / "scripts" / "validateEnv.mjs").is_file():
        problems.append("frontend/scripts/validateEnv.mjs missing")

    vite = (REPO_ROOT / "frontend" / "vite.config.js")
    if vite.is_file() and "validateProductionEnv" not in vite.read_text(encoding="utf-8"):
        problems.append("vite.config.js does not call validateProductionEnv")

    ci_text = ci.read_text(encoding="utf-8")
    for needle in ("npm test", "npm run build", "npm run lint", "VITE_API_BASE_URL"):
        if needle not in ci_text:
            problems.append(f"ci.yml missing {needle!r}")

    if problems:
        return FAIL, "; ".join(problems)

    if not opts.frontend_build:
        return PASS, "static contract OK; real build is CI's job (pass --frontend-build to run npm here)"

    env = os.environ.copy()
    env["VITE_API_BASE_URL"] = "https://api.careerpilot.app"
    try:
        proc = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(REPO_ROOT / "frontend"),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        return SKIP, "npm not available on PATH"
    except subprocess.TimeoutExpired:
        return FAIL, "frontend production build timed out"
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr).splitlines()[-5:]
        return FAIL, "npm run build failed: " + " | ".join(tail)
    return PASS, "frontend production build succeeded"


def check_n(opts: Options):
    """Repository integrity: whitespace, protected-file baseline, secret scan.

    The release smoke gate must run from a **committed release candidate**.
    ``git diff --check`` inspects the working tree relative to the index and
    the protected-file check uses ``git rev-parse HEAD:<path>`` which reads
    the committed blob only.  Untracked implementation files are therefore
    *not* considered part of the release candidate by this check.
    """
    problems = []

    def _git(args):
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT)] + args,
            capture_output=True,
            text=True,
            timeout=120,
        )

    diff = _git(["diff", "--check"])
    if diff.returncode != 0:
        problems.append("git diff --check reported whitespace/conflict issues")

    for rel, expected in PROTECTED_FILES_AT_HEAD.items():
        proc = _git(["rev-parse", f"HEAD:{rel}"])
        if proc.returncode != 0:
            problems.append(f"unable to resolve HEAD:{rel}")
            continue
        actual = proc.stdout.strip()
        if actual != expected:
            problems.append(
                f"protected file HEAD blob changed for {rel} "
                f"(expected {expected}, got {actual})"
            )

    scan = subprocess.run(
        [sys.executable, "scripts/scan_repo_secrets.py"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if scan.returncode != 0:
        findings = [ln for ln in (scan.stdout + scan.stderr).splitlines() if ln.startswith("FOUND")]
        problems.append("secret scan failed: " + (findings[0] if findings else "non-zero exit"))

    if problems:
        return FAIL, "; ".join(problems)
    return PASS, "diff --check clean; protected-file HEAD baselines intact; secret scan clean"


def check_pg_readiness(opts: Options):
    """Live PostgreSQL reachability. GATED: needs --pg and POSTGRES_TEST_DATABASE_URL."""
    url = (os.environ.get("POSTGRES_TEST_DATABASE_URL") or "").strip()
    if not (getattr(opts, "pg", False) and url):
        return SKIP, "not enabled; pass --pg and set POSTGRES_TEST_DATABASE_URL"
    try:
        from sqlalchemy import create_engine as _create_engine, text as _text

        engine = _create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(_text("SELECT 1"))
        engine.dispose()
        return PASS, "live PostgreSQL SELECT 1 succeeded"
    except Exception as exc:  # noqa: BLE001
        from sqlalchemy.engine import make_url

        try:
            safe = make_url(url).render_as_string(hide_password=True)
        except Exception:  # noqa: BLE001
            safe = "<unparseable POSTGRES_TEST_DATABASE_URL>"
        return FAIL, f"live PostgreSQL unreachable ({safe}): {type(exc).__name__}"


def check_pg_backup(opts: Options):
    """Live pg_dump creation + checksum verification. GATED: needs --pg, URL, and pg_dump on PATH."""
    url = (os.environ.get("POSTGRES_TEST_DATABASE_URL") or "").strip()
    if not (getattr(opts, "pg", False) and url):
        return SKIP, "not enabled; pass --pg and set POSTGRES_TEST_DATABASE_URL"
    if shutil.which("pg_dump") is None:
        return SKIP, "pg_dump not on PATH (backend/backups + docs/backup_recovery.md cover this)"

    base = Path(tempfile.mkdtemp(prefix="cp_smoke_pg_backup_"))
    try:
        from app.ops.backup import create_backup, verify_backup
        from app.ops.config import BackupConfig, checksum_sidecar_name, list_backups

        config = BackupConfig(
            database_url=url,
            backup_dir=str(base),
            retention_count=5,
            environment="smoketest",
        )
        dump = create_backup(config)
        valid, message = verify_backup(dump)
        if not valid:
            return FAIL, f"backup verification failed: {message}"
        if not dump.with_name(checksum_sidecar_name(dump.name)).exists():
            return FAIL, "checksum sidecar was not written"
        if not list_backups(base):
            return FAIL, "created dump was not listed as a valid backup"
        return PASS, f"pg_dump creation + checksum verification succeeded ({dump.name})"
    except Exception as exc:  # noqa: BLE001
        return FAIL, f"pg_dump backup creation failed: {type(exc).__name__}: {exc}"
    finally:
        _cleanup_dir(base)


CHECKS: list[tuple[str, str, callable]] = [
    ("A", "Backend bootstrap & routing", check_a),
    ("B", "Health endpoints", check_b),
    ("C", "Production config fail-fast", check_c),
    ("D", "HTTP security contract", check_d),
    ("E", "Authentication contract", check_e),
    ("F", "Rate limiting", check_f),
    ("G", "Job discovery (offline)", check_g),
    ("H", "Saved searches", check_h),
    ("I", "Application pipeline", check_i),
    ("J", "Storage safety", check_j),
    ("K", "Analytics aggregations", check_k),
    ("L", "Backup & recovery ops", check_l),
    ("M", "Frontend build contract", check_m),
    ("N", "Repository integrity", check_n),
    ("PG.1", "PostgreSQL readiness gate", check_pg_readiness),
    ("PG.2", "PostgreSQL backup creation + verification", check_pg_backup),
]


# ---------------------------------------------------------------------------
# Harness engine
# ---------------------------------------------------------------------------

def _normalize_status(status: str) -> str:
    return (status or "").strip().upper()


def execute_check(check_fn: callable, opts: Options) -> tuple[str, str]:
    """Run one check; any unexpected exception is a FAIL, never a silent pass."""
    try:
        status, message = check_fn(opts)
    except Exception as exc:  # noqa: BLE001
        return FAIL, f"raised {type(exc).__name__}: {exc}"
    return _normalize_status(status), message


def run_checks(opts: Options, registry: list[tuple[str, str, callable]] | None = None) -> list[SmokeResult]:
    registry = registry if registry is not None else CHECKS
    results: list[SmokeResult] = []
    for letter, title, fn in registry:
        status, message = execute_check(fn, opts)
        results.append(SmokeResult(letter=letter, title=title, status=status, message=message))
        if status == FAIL and opts.fail_fast:
            break
    return results


def gate_passed(results: list[SmokeResult]) -> bool:
    return not any(r.status == FAIL for r in results)


def format_report(results: list[SmokeResult]) -> str:
    lines = [
        "",
        "CAREERPILOT RELEASE SMOKE",
        "========================",
        "",
    ]
    for r in results:
        label = r.title.strip()
        pad = max(0, _MAX_TITLE_WIDTH - len(label))
        lines.append(f"  [{r.letter}] {label}{' ' * pad} {r.status}" + (f"  - {r.message}" if r.message else ""))
    passed = sum(1 for r in results if r.status == PASS)
    skipped = sum(1 for r in results if r.status == SKIP)
    failed = sum(1 for r in results if r.status == FAIL)
    lines += [
        "",
        f"  RESULT: {passed} passed, {skipped} skipped, {failed} failed",
        f"  RELEASE GATE: {'PASS' if gate_passed(results) else 'FAIL'}",
        "",
    ]
    return "\n".join(lines)


def format_json(results: list[SmokeResult]) -> str:
    return json.dumps(
        {
            "gate": "PASS" if gate_passed(results) else "FAIL",
            "checks": [r.__dict__ for r in results],
        },
        indent=2,
    )


def build_options(args: argparse.Namespace) -> Options:
    return Options(
        json=args.json,
        fail_fast=args.fail_fast,
        pg=args.pg,
        frontend_build=args.frontend_build,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.release_smoke",
        description=(
            "CareerPilot release smoke harness. Pre-deployment validation only: "
            "deterministic, offline by default, no production credentials."
        ),
        epilog="Exit codes: 0 = RELEASE GATE PASS, 1 = a required check failed, 2 = usage error.",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument("--fail-fast", action="store_true", help="stop running checks after the first FAIL")
    parser.add_argument(
        "--pg",
        action="store_true",
        help="enable the two live-PostgreSQL gated checks (requires POSTGRES_TEST_DATABASE_URL)",
    )
    parser.add_argument(
        "--frontend-build",
        action="store_true",
        help="also run a real `npm run build` (not only the static frontend contract check)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    opts = build_options(args)

    results = run_checks(opts)

    if args.json:
        print(format_json(results))
    else:
        print(format_report(results))

    return 0 if gate_passed(results) else 1


if __name__ == "__main__":
    sys.exit(main())