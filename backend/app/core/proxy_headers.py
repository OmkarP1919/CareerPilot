"""ASGI middleware for reverse-proxy forwarded-header trust.

When the application sits behind a TLS-terminating reverse proxy (such as
Azure App Service), the proxy receives the client's HTTPS connection and
forwards the request to the backend over plain HTTP, attaching forwarding
headers:

- ``X-Forwarded-Proto: https`` (the original client-facing scheme)
- ``X-Forwarded-For: <client-ip>`` (the original client IP)
- ``X-Forwarded-Host: <original-host>`` (the original Host header)

Without intervention, the ASGI application sees ``http://`` and generates
``http://`` Location headers on 307 redirects, causing **mixed-content**
errors in browsers.

This middleware solves the problem by reading ``X-Forwarded-Proto`` and
updating ``scope["scheme"]`` so downstream code (including Starlette's
redirect logic) sees the correct scheme.

Security:

- Forwarded headers are only trusted when the connecting client IP is in
  ``allowed_ips``.  Set to ``["*"]`` to trust all IPs (appropriate when
  the backend is not directly exposed to the internet, e.g. Azure App
  Service with ``FORWARDED_ALLOW_IPS=*``).
- When ``allowed_ips`` is empty or the connecting IP is not trusted,
  forwarded headers are **silently ignored** (no error, no logging) —
  the request is handled as-is.
- Only ``X-Forwarded-Proto`` is used to mutate the scope.  ``X-Forwarded-For``
  and ``X-Forwarded-Host`` are not consumed by this middleware; they remain
  available for application-level logging if needed.
"""

import logging

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("app.proxy_headers")

_TRUST_ALL = frozenset({"*"})


class ProxyHeadersMiddleware:
    """Trust ``X-Forwarded-Proto`` from a configurable set of proxy IPs.

    Parameters
    ----------
    app:
        The downstream ASGI application.
    allowed_ips:
        Client IPs whose ``X-Forwarded-Proto`` header is trusted.
        Use ``["*"]`` to trust all (safe when the backend is not directly
        exposed).  An empty list disables forwarded-header processing.
    """

    def __init__(self, app: ASGIApp, allowed_ips: list[str] | None = None):
        self.app = app
        raw = allowed_ips or []
        self._trust_all = "*" in raw
        self._allowed: frozenset[str] = frozenset(
            ip for ip in raw if ip != "*"
        ) if not self._trust_all else _TRUST_ALL

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._trust_all is False and not self._allowed:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else None

        if client_ip and (self._trust_all or client_ip in self._allowed):
            headers = dict(scope.get("headers", []))
            forwarded_proto = headers.get(b"x-forwarded-proto", b"").decode("latin-1").strip().lower()
            if forwarded_proto in ("https", "http"):
                if scope["scheme"] != forwarded_proto:
                    logger.debug(
                        "proxy_headers: updating scope scheme %s -> %s (client=%s)",
                        scope["scheme"],
                        forwarded_proto,
                        client_ip,
                    )
                    scope["scheme"] = forwarded_proto

        await self.app(scope, receive, send)
