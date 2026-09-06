# Health / readiness endpoints (Phase 5E.3)

None of the health endpoints require authentication - platform and
load-balancer probes call them without a user token.

## GET /healthz — liveness

- Tells infrastructure only whether the **process is alive**.
- Does **not** touch PostgreSQL or any external provider.
- Returns quickly; response body `{"status": "ok"}`.
- Use when deciding whether to kill/restart an instance.

## GET /health/readyz — readiness

- Tells infrastructure whether the process is alive **and** the database is
  reachable.
- Executes a lightweight `SELECT 1` against the configured `DATABASE_URL`
  engine (PostgreSQL connect attempt is bounded by a 3s `connect_timeout`
  added in `app/database/base.py`, so a dead host cannot hang the probe).
- Response:
  - database reachable -> HTTP 200 `{"status": "ready"}`
  - database unavailable -> HTTP 503 `{"status": "not_ready"}` (raw DB
    errors/credentials never returned; only a generic server log line is
    emitted)
- Use for load balancer traffic-draining / platform readiness checks.

## GET /health — legacy compatibility

- Backward-compatible alias kept so existing consumers are not broken.
- Static liveness only; returns `{"status": "healthy"}`.
- New deployments should prefer `/healthz` + `/health/readyz`.

## Implementation files

- `app/api/health.py` — the three endpoints
- `tests/test_health.py` — liveness, readiness success/failure/no-detail,
  compatibility, and no-auth coverage (DB connectivity mocked)