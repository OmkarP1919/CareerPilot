"""ASGI middleware for request ID management and request logging.

The middleware:

1. Accepts a valid ``X-Request-ID`` header from the client or generates
   a new UUID4.
2. Stores the request ID in a :mod:`contextvars` ContextVar so application
   loggers can access it without threading ``Request`` objects.
3. Logs a single INFO line on every non-health request completion
   containing: request ID, method, path, status, and duration in
   milliseconds.
4. Logs unexpected exceptions at ERROR level with the request ID and a
   full stack trace (server-side only; never exposed to the client).
"""

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_context import set_request_id, get_request_id

logger = logging.getLogger("app.request")

# Maximum accepted length for a client-supplied X-Request-ID.
_MAX_ID_LENGTH = 128

# Paths that do not emit a request-log line (high-frequency probes).
_HEALTH_PATHS = frozenset({"/healthz", "/health", "/health/readyz"})

# Control characters (and newlines) that must never appear in request IDs.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _generate_request_id() -> str:
    """Return a cryptographically random UUID4 string."""
    return str(uuid.uuid4())


def _sanitize_path(path: str) -> str:
    """Return *path* with control characters stripped and no query string."""
    clean = path.split("?", 1)[0].split("#", 1)[0]
    return _CONTROL_RE.sub("", clean)


def _validate_request_id(raw: str) -> str | None:
    """Return the request ID if valid, else ``None`` (caller regenerates).

    A request ID is rejected outright if it is empty, too long, or contains
    any control character (including newlines). It is not "sanitized" by
    stripping those characters - an invalid ID is simply replaced with a
    fresh one so a caller can never smuggle data via the header.
    """
    if not raw or len(raw) > _MAX_ID_LENGTH:
        return None
    if _CONTROL_RE.search(raw):
        return None
    return raw


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach a request ID and emit a per-request log line at completion."""

    async def dispatch(self, request: Request, call_next):
        # --- request ID ---------------------------------------------------
        raw_id = request.headers.get("x-request-id", "")
        request_id = _validate_request_id(raw_id) or _generate_request_id()
        set_request_id(request_id)

        # --- timing -------------------------------------------------------
        start = time.monotonic()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
        except Exception:
            logger.exception(
                "Unhandled request error "
                f"request_id={request_id} method={request.method} "
                f"path={_sanitize_path(str(request.url.path))}",
            )
            raise
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 1)

            # Attach the request ID so clients can use it for support
            # tickets or distributed tracing.
            response.headers["X-Request-ID"] = request_id

            # Skip the log line for high-frequency health probes.
            if _sanitize_path(str(request.url.path)) not in _HEALTH_PATHS:
                logger.info(
                    "request "
                    f"request_id={request_id} method={request.method} "
                    f"path={_sanitize_path(str(request.url.path))} "
                    f"status={status_code} duration_ms={duration_ms}"
                )

        return response
