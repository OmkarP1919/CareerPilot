# Security hardening (Phase 5E.7)

Applies production-safe request/response hardening at the ASGI layer without
touching application logic.

## Security response headers

Applied to **every** HTTP response (normal and rejected) via
`app/core/security_headers.py`:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'`

The CSP is an API-only policy. It deliberately does not govern the separately
deployed frontend, so no client-source allowlists are guessed. `frame-ancestors
'none'` and `base-uri 'none'` harden clickjacking and base-tag injection.

The interactive documentation endpoints (`/docs`, `/redoc`,
`/docs/oauth2-redirect`) render UIs from external CDNs with inline scripts and
styles that `default-src 'none'` would block, so they keep the other security
headers but intentionally do NOT receive the restrictive CSP, keeping Swagger
UI and ReDoc usable. `/openapi.json` is an API response and does receive the
CSP.

## HSTS

`Strict-Transport-Security` is **only** emitted when explicitly enabled via
`ENABLE_HSTS=true`, which should happen exclusively on an HTTPS production
deployment. It is never inferred from a request header, and is off by default —
including in production — so plain-HTTP deployments are never told to upgrade.

`max-age=31536000` (1 year). `includeSubDomains`/`preload` are deliberately NOT
included unless the entire domain hierarchy is controlled.

## TRUSTED_HOSTS

`TRUSTED_HOSTS` is a comma-separated list of allowed `Host` header values
(e.g. `api.careerpilot.app`, or `*.careerpilot.app` for wildcard subdomains)
and is enforced by Starlette's `TrustedHostMiddleware` before any route runs.

- **development/test + empty:** defaults to `localhost`, `127.0.0.1`, `::1`.
- **production/staging + empty:** startup fails fast with a clear configuration
  error (via `Settings.allowed_trusted_hosts`). The wildcard `*` is never a
  production fallback.
- Explicit values are validated (no scheme/path/whitespace; `*` alone is
  rejected) and de-duplicated.

Configure the public hostname(s) of the backend in production.

## MAX_REQUEST_BODY_BYTES

A global, defensive request-body cap (default **16 MiB** = 16,777,216 bytes),
enforced by `app/core/body_limit.py` without buffering the whole body:

- A `Content-Length` above the cap is rejected immediately with **HTTP 413**
  without invoking the application (so nothing is written to storage).
- Chunked (no `Content-Length`) bodies are byte-counted while streaming; once
  the cap is crossed, no further bytes are forwarded and a 413 is returned.
- Malformed/non-numeric `Content-Length` is treated as absent (stream-counted).

The 413 body is a small JSON `{"detail":"Request body too large"}`. Only safe
request metadata is ever logged; no body, query, or header content.

### Difference from the file-upload limit

This is a **global** cap and is intentionally larger than the **per-file 10 MiB**
upload limit applied by the application for resumes and application documents.
The per-file limit is unchanged; the global cap is a coarse, early, defensive
stop for oversized or malicious bodies.

## Reverse-proxy note

This ASGI limit stops requests at the application boundary. Production
deployments should **also** configure a matching (or tighter) body limit at the
reverse proxy / load balancer to drop oversized requests before they reach the
application. This is infrastructure configuration, outside the scope of this
phase.

## Middleware order

Outermost → innermost (see `backend/app/main.py`):

1. `RequestLoggingMiddleware` — request ID + per-request log line
   (runs first so rejected requests still get a request ID).
2. `TrustedHostMiddleware` — Host validation before routing.
3. `RequestBodyLimitMiddleware` — oversized-body rejection before handlers.
4. `SecurityHeadersMiddleware` — security headers on all responses.
5. `CORSMiddleware` — unchanged 5E.1 behavior.
6. Application routes.

## Local development defaults

- No `TRUSTED_HOSTS` needed (localhost defaults apply).
- `MAX_REQUEST_BODY_BYTES` = 16 MiB.
- HSTS off.

## Files

- `app/core/config.py` — `TRUSTED_HOSTS`, `MAX_REQUEST_BODY_BYTES`,
  `ENABLE_HSTS` + resolution helpers.
- `app/core/security_headers.py` — `SecurityHeadersMiddleware`.
- `app/core/body_limit.py` — `RequestBodyLimitMiddleware`.
- `app/main.py` — middleware wiring.
- `tests/test_security_hardening.py` — 5E.7 coverage.
