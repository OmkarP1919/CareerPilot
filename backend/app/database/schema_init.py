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
from typing import Any, List, Tuple
from sqlalchemy import inspect, text

from app.database.base import Base, engine

logger = logging.getLogger("app.database.schema_init")

# Phase 7.0D.3 additive columns for existing production tables:
# (table_name, column_name, column_sql_type)
ADDITIVE_COLUMNS_7_0D_3: List[Tuple[str, str, str]] = [
    ("job_matches", "work_mode_score", "INTEGER"),
    ("job_matches", "education_score", "INTEGER"),
    ("job_matches", "score_version", "VARCHAR"),
    ("resume_job_analyses", "score_version", "VARCHAR"),
]


def _apply_additive_columns(target: Any) -> None:
    """Safely and idempotently apply additive columns to existing tables.

    Compatible with PostgreSQL (using ALTER TABLE ... ADD COLUMN IF NOT EXISTS)
    and SQLite (checking column existence before ALTER TABLE ... ADD COLUMN).
    Never drops or modifies existing columns. Existing rows remain valid and
    unmodified (new nullable columns default to NULL).
    """
    insp = inspect(target)
    existing_tables = set(insp.get_table_names())
    dialect_name = getattr(getattr(target, "dialect", None), "name", "")

    for table_name, col_name, col_type in ADDITIVE_COLUMNS_7_0D_3:
        if table_name not in existing_tables:
            continue
        existing_cols = {c["name"] for c in insp.get_columns(table_name)}
        if col_name in existing_cols:
            continue

        if dialect_name == "postgresql":
            ddl = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
        else:
            ddl = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"

        if hasattr(target, "begin"):
            with target.begin() as conn:
                conn.execute(text(ddl))
        elif hasattr(target, "execute"):
            target.execute(text(ddl))
        else:
            with target.connect() as conn:
                with conn.begin():
                    conn.execute(text(ddl))

        logger.info("Applied additive column: %s.%s (%s)", table_name, col_name, col_type)


def init_schema(bind=None) -> list[str]:
    """Create any missing tables and apply additive columns for the complete model set.

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
    _apply_additive_columns(target)
    return sorted(Base.metadata.tables.keys())