# Logging & request tracing (Phase 5E.5)

## Configuration

`LOG_LEVEL` controls the application root logger. Acceptable values:
`DEBUG`, `INFO` (default), `WARNING`, `ERROR`, `CRITICAL`.

Uvicorn's own loggers are unaffected; their levels are set by Uvicorn
command-line flags.

## Request ID

Every incoming request is assigned a request ID:

- If the client sends a valid `X-Request-ID` header (max 128 chars,
  no control characters), it is preserved.
- Otherwise a UUID4 is generated.
- The request ID is returned in the `X-Request-ID` response header.
- Application loggers can access it via
  `app.core.request_context.get_request_id()`.

## Request log line

Every non-health request produces a single INFO line at completion:

```
2026-09-06 20:00:00 INFO request request_id=... method=GET path=/jobs status=200 duration_ms=42
```

Fields logged: request ID, HTTP method, normalized path, status code,
duration in milliseconds.

Health endpoints (`/healthz`, `/health`, `/health/readyz`) are
deliberately excluded from request logs to reduce noise.

## What is NOT logged

- Authorization / Bearer tokens
- Query parameters
- Request or response bodies
- Cookies
- Uploaded file contents
- DATABASE_URL
- Firebase credentials
- AI provider API keys

Sensitive header values in the logging filter are replaced with
`[REDACTED]`.

## Files

- `app/core/logging_config.py` — formatter, filter, `setup_logging()`
- `app/core/request_context.py` — `ContextVar`-based request ID
- `app/core/request_middleware.py` — request ID assignment + log line
