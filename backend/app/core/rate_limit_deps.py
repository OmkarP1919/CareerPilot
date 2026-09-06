"""Per-user rate-limit FastAPI dependencies (Phase 5E.9).

These dependencies limit requests keyed by the *verified* Firebase UID. They
must run on routes that are already behind ``get_current_user`` (or include
it themselves) so the identity is trusted and cannot be spoofed by a caller
editing a header.

Two categories:

- ``"authenticated"``: an upper bound on total per-user requests across the
  protected surface (``RATE_LIMIT_AUTHENTICATED_MAX`` per window).
- ``"expensive"``: a stricter bound for costly/sensitive operations such as
  AI resume tailoring, job discovery/matching, and file parsing
  (``RATE_LIMIT_EXPENSIVE_MAX`` per window).

Both share the same storage backend instance so a single app never spawns
multiple in-memory tables.
"""
import logging

from fastapi import Depends, HTTPException, status, Request

from app.core.rate_limit import MemoryRateLimitBackend, RateLimiter
from app.dependencies.auth import get_current_user
from app.models.user import User

logger = logging.getLogger("app.rate_limit")

# Lazy singleton shared across all categories so one request hitting both the
# authenticated and expensive dependency reuses the same counter table.
_limiter = RateLimiter(MemoryRateLimitBackend(max_keys=20_000))

# Config knobs updated once at startup by the factory in main.py. Rate limiting
# is DISABLED by default so pre-existing tests that import these routers without
# calling configure_rate_limits are never throttled. Production always calls
# configure_rate_limits (from main.py) before serving requests, which enables it.
_WINDOW_SECONDS = 60
_AUTH_MAX = 300
_EXPENSIVE_MAX = 30
_ENABLED = False


def configure_rate_limits(
    enabled: bool = True,
    window_seconds: int = 60,
    authenticated_max: int = 300,
    expensive_max: int = 30,
    max_keys: int = 20_000,
) -> None:
    """Set runtime limits. Called once during application startup."""
    global _WINDOW_SECONDS, _AUTH_MAX, _EXPENSIVE_MAX, _ENABLED, _limiter
    _ENABLED = bool(enabled)
    _WINDOW_SECONDS = window_seconds
    _AUTH_MAX = authenticated_max
    _EXPENSIVE_MAX = expensive_max
    _limiter = RateLimiter(MemoryRateLimitBackend(max_keys=max_keys))


def rate_limit(category: str = "expensive"):
    """Return a FastAPI dependency enforcing a per-user limit category."""

    def dependency(
        request: Request,
        user: User = Depends(get_current_user),
    ) -> None:
        if not _ENABLED:
            return
        uid = user.firebase_uid
        limit = _AUTH_MAX if category == "authenticated" else _EXPENSIVE_MAX
        # Per-user limit checks are only applied once per request (FastAPI
        # caches the dependency result for a given request).
        result = _limiter.check(uid, limit, _WINDOW_SECONDS)
        if not result.allowed:
            from fastapi.responses import JSONResponse  # local: no circular import

            headers = {"Retry-After": str(int(max(1, result.retry_after)))}
            logger.warning(
                "rate_limit_exceeded category=%s user=%s retry_after=%s",
                category,
                uid,
                int(result.retry_after),
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers=headers,
            )

    return dependency


# Pre-built reusable dependencies for route wiring.
expensive_rate_limiter = rate_limit("expensive")
authenticated_rate_limiter = rate_limit("authenticated")