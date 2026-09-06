# Rate Limiting (Phase 5E.9)

Fixed-window rate limiting protects the API at three levels:

1. **Global / anonymous (client IP)** — enforced as ASGI middleware on every
   non-health request, whether or not the request carries a valid token. This
   is the outermost defense against floods and covers requests with missing or
   invalid tokens that never reach a per-user dependency.
2. **Authenticated (per user)** — a per-verified-Firebase-UID ceiling over the
   protected surface.
3. **Expensive (per user)** — a stricter, per-verified-Firebase-UID ceiling on
   costly or sensitive operations (AI tailoring, discovery/matching, resume
   parsing, document uploads).

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `true` | Master switch for all three levels. |
| `RATE_LIMIT_BACKEND` | `memory` | Backend namespace; only `memory` is shipped. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Fixed-window length (s). |
| `RATE_LIMIT_AUTHENTICATED_MAX` | `300` | Per-UID ceiling (`5/s` avg). |
| `RATE_LIMIT_ANONYMOUS_MAX` | `120` | Per-client-IP ceiling (`2/s` avg). |
| `RATE_LIMIT_EXPENSIVE_MAX` | `30` | Per-UID expensive ceiling. |
| `RATE_LIMIT_MAX_KEYS` | `20000` | Memory-backend bucket cap. |
| `RATE_LIMIT_TRUST_PROXY` | `false` | Reserved; proxy-header parsing not yet performed. |

## Design notes

- **Fixed window** counters are cheap and deterministic. `time.monotonic()` is
  used so limits are immune to wall-clock/NTP changes.
- **Keys are salted-hashed** (SHA-256) in the backend so Firebase UIDs and IPs
  are never stored in plaintext in memory.
- **Client IP is taken directly from the ASGI `scope["client"]` tuple.**
  `X-Forwarded-For` / `X-Real-IP` are **not trusted** because the app does not
  yet enforce a trusted-proxy boundary. `RATE_LIMIT_TRUST_PROXY` is reserved
  for the future addition of proxy-header parsing.
- **Health endpoints** (`/health`, `/healthz`, `/health/readyz`) are always
  exempt so load-balancer probes are never blocked.
- **429 responses** carry `Retry-After` and application JSON; because the
  middleware sits inside `RequestLogging` and `SecurityHeaders`, a 429 also
  receives a request ID and the full security-header envelope. `TrustedHost`
  is outside the limiter, so a rejected `Host` never consumes a counter.
- **Memory bound** — the in-memory table never exceeds `RATE_LIMIT_MAX_KEYS`
  buckets; when full with no reclaimable buckets it fails open (allows) and
  warns, so the limiter itself cannot be used to cause an outage.
- **Distributed limits** — `memory` is single-process only. A multi-instance
  production deployment MUST use a shared backend (e.g. Redis), added behind
  the same `RateLimitBackend` interface. Running `production`/`staging` with
  `RATE_LIMIT_BACKEND=memory` logs a startup warning rather than failing so a
  single-instance beta deploy is not blocked while remaining honest that the
  limiter is not distributed.

## Wiring

- `app/core/rate_limit.py` — `RateLimiter`, `RateLimitBackend`,
  `MemoryRateLimitBackend`, `RateLimitResult`.
- `app/core/rate_limit_middleware.py` — `RateLimitMiddleware` (anonymous/IP
  ASGI limiter).
- `app/core/rate_limit_deps.py` — `rate_limit(category)` dependency factory,
  `expensive_rate_limiter`, `authenticated_rate_limiter`,
  `configure_rate_limits(...)`.
- Added to `main.py` middleware chain and `configure_rate_limits` at startup.
- Applied to the expensive/sensitive routes via
  `dependencies=[Depends(expensive_rate_limiter)]` (see the route list in the
  [implementation report](../../docs/security_hardening.md) / code).

> **Important:** per-user limits are keyed by the *verified* Firebase UID from
> `get_current_user`. A caller cannot spoof the identity by editing headers.
