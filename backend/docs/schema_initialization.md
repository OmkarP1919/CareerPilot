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

## Additive-only policy & controlled column evolution (Phase 7.0D.3)

`create_all` creates missing tables:

- okay: new tables appear on an existing database
- NOT handled by `create_all`: evolving existing columns/constraints/indexes
- NOT handled: destructive changes (drops/renames/type changes)

To evolve existing tables without introducing Alembic or destructive migrations,
CareerPilot uses a **controlled additive schema evolution mechanism** inside
`init_schema()` (`app/database/schema_init.py`):

- It defines explicit additive columns for the release:
  - `job_matches.work_mode_score` (INTEGER, nullable)
  - `job_matches.education_score` (INTEGER, nullable)
  - `job_matches.score_version` (VARCHAR, nullable)
  - `resume_job_analyses.score_version` (VARCHAR, nullable)
- On PostgreSQL databases, it executes:
  `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...`
- On SQLite (testing/local), it checks column existence via SQLAlchemy inspector
  before executing `ALTER TABLE ... ADD COLUMN ...`.
- It is completely **idempotent**: running `python -m app.database.init` multiple
  times is safe and produces no errors or duplicate columns.
- It is completely **additive and non-destructive**: existing rows remain intact,
  and new nullable columns default to `NULL` (e.g. existing `score_version` remains
  `NULL` until explicitly recomputed by canonical scoring).

## Production schema release procedure

During production release of Phase 7.0D.3:

1. Ensure the PostgreSQL database is reachable via `DATABASE_URL`.
2. Execute the release command once before starting or restarting web workers:

       python -m app.database.init

   (Alternatively, the equivalent idempotent SQL statements may be applied directly:
   `ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS work_mode_score INTEGER;`
   `ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS education_score INTEGER;`
   `ALTER TABLE job_matches ADD COLUMN IF NOT EXISTS score_version VARCHAR;`
   `ALTER TABLE resume_job_analyses ADD COLUMN IF NOT EXISTS score_version VARCHAR;`)
3. Only after `python -m app.database.init` exits with code 0, deploy/start the application instances.

## Failure behavior

If the schema-init command cannot connect or cannot create the schema, it
fails loudly (non-zero exit). A deployment must stop rather than continue
against an unknown schema.

## Files

- `app/database/schema_init.py` — callable `init_schema()`
- `app/database/init.py` — CLI entry point
- `tests/test_schema_init.py` — model-registration, creation, idempotence,
  engine-default, CLI, and failure-propagation tests