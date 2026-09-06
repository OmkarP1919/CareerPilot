"""Explicit database schema initialization.

CareerPilot deliberately does NOT use an ORM migration tool (Alembic) in this
release cycle. ``init_schema`` performs an additive ``Base.metadata.create_all()``:

- it CREATES any tables that do not yet exist
- it NEVER alters or drops existing columns, constraints, or indexes

It is therefore NOT a migration engine (see ``backend/docs/schema_initialization.md``).

Operational model (see app/main.py):

1.  The release process runs ``python -m app.database.init`` once, before any
    application instance starts.
2.  Only after it completes successfully do application instances boot.
3.  The FastAPI application itself never performs implicit schema creation.

Calls to ``init_schema`` are safe to repeat (create_all is incremental for the
tables it defines). Database/connection errors propagate to the caller; they
are never swallowed, so a release can fail instead of continuing against an
unknown schema. No credentials or connection strings are ever printed here.
"""

import logging

from app.database.base import Base, engine

logger = logging.getLogger("app.database.schema_init")


def init_schema(bind=None) -> list[str]:
    """Create any missing tables for the complete application model set.

    ``bind`` may override the engine (tests use an in-memory dialect); the
    default is the application's configured ``engine`` built from
    ``DATABASE_URL``. All models are registered through ``app.models`` before
    ``create_all`` runs, so no table is omitted.

    Returns the sorted names of every table known to ``Base.metadata``.
    Raises on database failure.
    """
    import app.models  # noqa: F401  (registers every model on Base.metadata)

    target = bind if bind is not None else engine
    Base.metadata.create_all(bind=target)
    return sorted(Base.metadata.tables.keys())