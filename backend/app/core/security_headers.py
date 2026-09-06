"""Security response-header middleware.

Adds conservative, production-safe security headers to every HTTP response
(normal and rejected alike):

- ``X-Content-Type-Options: nosniff``
- ``X-Frame-Options: DENY``
- ``Referrer-Policy: strict-origin-when-cross-origin``
- ``Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'``

The CSP is an API-only policy (``default-src 'none'`` plus frame/base
restrictions). It deliberately does NOT attempt to govern the separately
deployed frontend, so no client-source allowlists are invented here.

The interactive documentation endpoints (``/docs``, ``/redoc``,
``/oauth2-redirect``) load their UI from external CDNs with inline scripts and
styles that ``default-src 'none'`` would block. Those responses keep the other
security headers but intentionally do NOT receive the restrictive CSP so the
documentation stays usable.

- ``Strict-Transport-Security`` is only emitted when HSTS is explicitly
  configured (``ENABLE_HSTS``), which should only happen on an HTTPS
  deployment. It is never inferred from an arbitrary request header, and the
  default ``max-age=31536000`` deliberately avoids ``includeSubDomains``/
  ``preload`` unless the whole domain hierarchy is controlled.

Security headers never expose secrets or internal paths - they are static,
config-derived values only.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Static API-only CSP. frame-ancestors 'none' and base-uri 'none' harden
# clickjacking/base-tag injection; default-src 'none' disables all resource
# loading from API responses.
_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
_HSTS = "max-age=31536000"

# Interactive documentation routes render UIs from external CDNs + inline
# scripts/styles, which the restrictive CSP would block. They keep the other
# headers but are excluded from the CSP so Swagger UI / ReDoc remain usable.
_DOC_UI_PATHS = {
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security response headers.

    ``hsts_enabled`` controls whether ``Strict-Transport-Security`` is set.
    Providing an explicit runtime value keeps the middleware injectable and
    testable without importing app configuration directly.
    """

    def __init__(self, app, hsts_enabled: bool = False):
        super().__init__(app)
        self.hsts_enabled = bool(hsts_enabled)

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.url.path not in _DOC_UI_PATHS:
            response.headers.setdefault("Content-Security-Policy", _CSP)
        if self.hsts_enabled:
            response.headers.setdefault("Strict-Transport-Security", _HSTS)
        return response
