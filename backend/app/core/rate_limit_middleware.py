"""Global anonymous/client-IP rate-limit middleware (Phase 5E.9).

Enforces the anonymous (client-IP) limit on all requests except health
probes. The middleware runs in the ASGI layer (after security headers,
before routing) so 429 responses receive the full safety envelope: request
IDs, CORS, security headers.

Health paths (``/healthz``, ``/health``, ``/health/readyz``) are always
exempt so load-balancer probes are never blocked.

The middleware does NOT perform Firebase token verification and does NOT
attempt to detect whether a request is authenticated — that capability
belongs to the per-user dependency (``app.core.rate_limit_deps``). For
unauthenticated / invalid-token requests the middleware is the only limiter
in the request path, which is the desired behavior.

Client IP is taken directly from the ASGI ``scope["client"]`` tuple.
``X-Forwarded-For`` / ``X-Real-IP`` are NOT trusted by default because
the application does not yet enforce a trusted-proxy boundary; set
``RATE_LIMIT_TRUST_PROXY=true`` to opt in once a reverse-proxy is in place.
"""
import logging
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.rate_limit import MemoryRateLimitBackend, RateLimiter

logger = logging.getLogger("app.rate_limit")

_HEALTH_PATHS = frozenset({"/healthz", "/health", "/health/readyz"})


def _client_ip(scope: Scope) -> str:
    """Extract a rate-limit key from the ASGI client address."""
    client = scope.get("client")
    if client:
        return client[0]
    return "unknown"


class RateLimitMiddleware:
    """Global per-client-IP rate limiter enforced as ASGI middleware.

    ``anonymous_max`` requests per ``window_seconds`` are allowed from each
    direct client IP. Health endpoints are always exempt.
    """

    def __init__(
        self,
        app: ASGIApp,
        enabled: bool = True,
        anonymous_max: int = 120,
        window_seconds: int = 60,
        max_keys: int = 20000,
    ):
        self.app = app
        self.enabled = enabled
        self.limiter = None
        if enabled:
            self.limiter = RateLimiter(
                MemoryRateLimitBackend(max_keys=max_keys)
            )
            self.anonymous_max = anonymous_max
            self.window_seconds = window_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _HEALTH_PATHS:
            await self.app(scope, receive, send)
            return

        if not self.enabled:
            await self.app(scope, receive, send)
            return

        ip = _client_ip(scope)
        result = self.limiter.check(ip, self.anonymous_max, self.window_seconds)
        if result.allowed:
            await self.app(scope, receive, send)
            return

        body = b'{"detail":"Too many requests"}'
        retry_after = int(max(1, result.retry_after))
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode("ascii")],
                    [b"retry-after", str(retry_after).encode("ascii")],
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})
