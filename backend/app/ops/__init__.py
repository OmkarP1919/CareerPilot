"""Operational tooling (Phase 5E.11 — Backup & Recovery).

This package is deliberately NOT imported by the FastAPI application; it is
run by administrators via ``python -m app.ops.backup``. It wraps the standard
PostgreSQL client tools (pg_dump, pg_restore, psql) — it does not implement a
database backup engine, and it never touches application data itself.
"""