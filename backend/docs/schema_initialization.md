# Database schema initialization (Phase 5E.2)

CareerPilot does NOT use an ORM migration tool (Alembic) in the current cycle.
Schema creation is an **explicit, repeatable release operation** rather than an
application-startup side effect.

## The command

    python -m app.database.init

Run from the `backend/` directory (or with `backend/` on `PYTHONPATH`). It:

- loads the same `DATABASE_URL` / `Settings` configuration as the FastAPI app
- imports every model through `app.models` (users, profiles, education,
  skills, user_skills, projects, experiences, certifications, resumes, jobs,
  job_matches, resume_job_analyses, tailored_resumes, cover_letters,
  applications, application_events, application_interviews,
  application_documents, saved_searches)
- executes `Base.metadata.create_all(bind=engine)`
- exits non-zero if the database is unreachable or schema creation fails
- never prints credentials or the connection string

## When it must run

- **Development:** after setting up a new local database:

      python -m app.database.init

- **Production deployment:** as an ordered **pre-deploy/release step, once**,
  before any FastAPI/uvicorn instance starts:

      1. provision the managed PostgreSQL database + credentials
      2. run `python -m app.database.init` against it (release command)
      3. only after it succeeds, start backend instances

  Application startup no longer performs schema initialization. Because the
  release step runs exactly once, multiple application instances never race to
  create the schema.

## Additive-only policy — `create_all` is NOT a migration engine

`create_all` only **creates missing tables**:

- okay: new tables appear on an existing database
- NOT handled: evolving existing columns/constraints/indexes
- NOT handled: destructive changes (drops/renames/type changes)

Non-additive schema changes require a deliberate, controlled migration
strategy in a future cycle. Do not rely on `create_all` for those.

## Failure behavior

If the schema-init command cannot connect or cannot create the schema, it
fails loudly (non-zero exit). A deployment must stop rather than continue
against an unknown schema.

## Files

- `app/database/schema_init.py` — callable `init_schema()`
- `app/database/init.py` — CLI entry point
- `tests/test_schema_init.py` — model-registration, creation, idempotence,
  engine-default, CLI, and failure-propagation tests