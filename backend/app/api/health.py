"""Health endpoints for production infrastructure.

- GET /healthz        liveness  - is the process alive? Never touches the DB.
- GET /health/readyz  readiness - is the process alive AND the database reachable?
- GET /health         legacy    - backward-compatible liveness alias.

None of these endpoints require authentication; platform/load-balancer probes
must be able to call them without a user token.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database.base import engine

logger = logging.getLogger("app.api.health")

router = APIRouter()


@router.get("/healthz")
def liveness():
    """Liveness probe. Returns immediately with HTTP 200; never queries the DB.

    Used to decide whether the process itself is alive (safe to restart).
    """
    return {"status": "ok"}


@router.get("/health")
def health_compat():
    """Backward-compatible legacy liveness endpoint (original contract)."""
    return {"status": "healthy"}


@router.get("/health/readyz")
def readiness():
    """Readiness probe. Executes a lightweight ``SELECT 1`` against the
    configured database engine.

    - Database reachable  -> HTTP 200 {"status": "ready"}
    - Database unavailable -> HTTP 503 {"status": "not_ready"}

    Only a safe, generic log line is emitted on failure; raw database errors,
    credentials, and connection strings are never exposed to the response.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.warning("Readiness check failed: database is unreachable")
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}
