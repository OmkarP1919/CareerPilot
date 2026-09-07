# Backup & Recovery (Phase 5E.11)

Operation runbook for backing up and restoring the CareerPilot **PostgreSQL
database** and its **uploaded files**. It covers the practical foundation
needed for the private beta / initial production deployment —
recoverability, not an enterprise disaster-recovery platform.

> **Read this first.** `Database backup != Uploaded-file backup`. The
> PostgreSQL dump protects the *database rows only*. Uploaded resumes and
> application documents live on disk under `STORAGE_ROOT` and need a separate,
> explicit filesystem backup. See [Uploaded-file recovery](#uploaded-file-recovery).

---

## 1. What this protects

### A. PostgreSQL application data (the database backup)

Everything in the application schema — all tables created by
`python -m app.database.init`:

- `users`, `profiles`, `education`, `skills`, `user_skills`, `projects`,
  `experiences`, `certifications`
- `resumes`
- `jobs`, `job_matches`
- `applications`, `application_documents`, `application_events`,
  `application_interviews`
- `cover_letters`, `resume_job_analyses`, `saved_searches`, `tailored_resumes`

Backups are produced with `pg_dump` (custom-format, `pg_restore`-compatible).
CareerPilot deliberately does not ship its own database backup engine — the
managed-PostgreSQL provider's snapshot/point-in-time tooling can additionally
be configured at the infrastructure layer.

### B. Uploaded files (NOT in the database backup)

Uploaded resumes and application documents are stored under
`STORAGE_ROOT/<user_id>/<uuid>.<ext>` (default `backend/uploads/`). The
database stores only **metadata** (`resumes.file_path`,
`application_documents.file_path`, `original_filename`, `file_size`), never
the bytes. `pg_dump` therefore does **not** back up these files because it
dumps rows, not the filesystem.

**You must back up `STORAGE_ROOT` separately** (see
[Uploaded-file recovery](#uploaded-file-recovery)).

---

## 2. Configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://user:password@localhost:5432/careerpilot` (dev placeholder) | Connection string used by `pg_dump` / `pg_restore` / `psql`. Never put real credentials in source control. |
| `BACKUP_DIR` | `backend/backups` (project-local) | Directory for `.dump` archives and `.dump.sha256` sidecars. **Production must point this at a dedicated volume on the database host (or a mounted backup volume) that is itself backed up off-host.** Gitignored. |
| `BACKUP_RETENTION_COUNT` | `30` | Number of newest valid backups to keep. Must be `>= 1`. |
| `ENVIRONMENT` | `development` | Label embedded in backup filenames. |

All values are optional environment variables (`.env`-aware via the existing
`Settings` contract). No credentials are hardcoded; the tooling refuses to run
against an empty or non-PostgreSQL `DATABASE_URL`.

Backup filenames:

    careerpilot_<environment>_<UTC YYYYmmdd-HHMMSSZ>.dump
    careerpilot_production_20260907-143000Z.dump          <- example

Each archive gets a SHA-256 sidecar written in `sha256sum` format:

    careerpilot_production_20260907-143000Z.dump.sha256

---

## 3. Backup prerequisites

1. PostgreSQL client tools installed on the backup host:
   `pg_dump`, `pg_restore`, `psql` (the `postgresql-client` package).
2. `DATABASE_URL` configured (or `--target-database-url` for restore) and
   reachable from the backup host.
3. `BACKUP_DIR` writable by the operator and on a volume that is itself
   backed up off-host.
4. The schema may be anything — `pg_dump` captures data + schema as-is. The
   application does not need to be stopped for a logical `pg_dump` backup.
5. **Uploaded files:** ensure a filesystem backup of `STORAGE_ROOT` is running
   too (see [Uploaded-file recovery](#uploaded-file-recovery)).

---

## 4. Creating a backup

    cd backend
    python -m app.ops.backup create

Global options come **before** the subcommand:

    python -m app.ops.backup --backup-dir /var/backups/careerpilot create
    python -m app.ops.backup --environment production create

What happens:

- validates `DATABASE_URL`;
- creates `BACKUP_DIR` if needed;
- runs `pg_dump --format=custom --file … --dbname …` to a temp file, then
  atomically renames it to `careerpilot_<env>_<UTC>.dump`;
- refuses to overwrite an existing archive with the same name (retry after a
  second);
- writes `<archive>.dump.sha256`.

A failed `pg_dump` removes the temp file and exits non-zero; no partial
archive is left behind. The backup process never modifies application data.

---

## 5. Verifying a backup

    python -m app.ops.backup verify --dump careerpilot_production_20260907-143000Z.dump

Checks, in order:

1. the file exists and is a regular file;
2. the name matches the backup convention;
3. the file is non-empty;
4. the SHA-256 sidecar matches (when present);
5. `pg_restore --list` can parse the archive (non-destructive; nothing is
   restored). Add `--no-list` to skip step 5 (file/name/size/checksum only).

Exit code `0` = verified, `1` = failed (reasons printed). **Run `verify` on
every archive you intend to restore, and spot-check restores into a
disposable database** (see §7). Log files can be verified with the checksum
tool of your choice (the sidecar is standard `sha256sum` format).

---

## 6. Listing and retention cleanup

List backups (newest first, with size, modification time, sidecar status):

    python -m app.ops.backup list

Prune to the configured retention count (default `BACKUP_RETENTION_COUNT`):

    python -m app.ops.backup cleanup
    python -m app.ops.backup cleanup --dry-run          # preview only

or with an explicit override:

    python -m app.ops.backup cleanup --keep 7

Retention policy:

- keep the newest `N` valid backups, **always** keep the newest;
- deletion is deterministic, oldest first, confined to `BACKUP_DIR`;
- only files matching the strict `careerpilot_*.dump` convention are ever
  removed (sidecars are removed with their archive); unrelated files and
  subdirectories are ignored;
- `--dry-run` removes nothing.

Production object-storage / managed-backup retention (AWS lifecycle policies,
RDS automated backups, etc.) is intentionally **not** implemented inside the
application — configure it at the infrastructure layer.

---

## 7. Restoring into a disposable database (practice run)

Never practice restores against the real database. Use a scratch PostgreSQL
database on the same server (or a local server):

    cd backend

    python -m app.ops.backup restore \
      --dump careerpilot_production_20260907-143000Z.dump \
      --target-database-url postgresql://user:pass@localhost:5432/cp_practice \
      --create-target \
      --verify-first \
      --confirm-restore

- `--create-target` creates `cp_practice` if it does not exist (never drops
  or truncates anything).
- `--verify-first` runs the non-destructive inspection before restoring.
- `--confirm-restore` is **required**; without it the command exits `2`.

Then point a scratch instance of the app (or `psql`) at `cp_practice` and run
the smoke checks in §11. Drop the practice database when done:

    psql postgresql://user:pass@localhost:5432/postgres \
      -c 'DROP DATABASE IF EXISTS "cp_practice"'

---

## 8. Restoring production safely

The restore command **replaces** the contents of the target database:

    cd backend

    python -m app.ops.backup restore \
      --dump careerpilot_production_20260907-143000Z.dump \
      --verify-first \
      --confirm-restore

It connects to the configured `DATABASE_URL` (`--target-database-url` to
override) and runs:

    pg_restore --exit-on-error --clean --if-exists --no-owner \
      --dbname <target> <archive>

- `--clean --if-exists` drops existing objects before restoring — this is
  deliberately destructive and only possible with `--confirm-restore`.
- `--no-owner` avoids ownership failures when the connecting role differs.
- The CLI prints the target database name and a replacement warning before
  doing anything, and refuses (exit `2`) if `--confirm-restore` is absent.

Suggested sequence:

1. Complete the PRE-RESTORE checklist (§11) — pick the backup, verify it,
   confirm the target, schedule a maintenance window.
2. Take a **current** backup first (`create`) and snapshot uploaded files, so
   a failed restore can be rolled back (§12).
3. Run the restore. Restore the **database first**, then uploads (§9) —
   the app expects rows for the files it serves.
4. Run POST-RESTORE checks (§11).

Never restore *into* the live database to "test" a backup; use §7.

---

## 9. Uploaded-file recovery

**Database backup ≠ uploaded-file backup.** Restoring a database dump does not
bring back any files, and restoring files does not bring back rows.

### What to back up

The whole `STORAGE_ROOT` tree. Structure:

    STORAGE_ROOT/
      <user_id>/                     # one directory per user (server-side UUID)
        <server-uuid>.pdf           # stored resume / application document
        <server-uuid>.docx

- The stored filename is always a server-generated UUID; the user-facing name
  lives only in the database (`original_filename`).
- Each file on disk is referenced by exactly one row: `resumes.file_path`
  (NOT NULL) or `application_documents.file_path` (set only for uploaded
  documents; reference documents point at a resume via `source_resume_id`).
- Files for the same user must be restored into the same `<user_id>/`
  directory with byte-identical names — database rows store the **absolute
  path string**.

### Recommended mechanism

- **Simplest for the beta:** an infrastructure-level filesystem backup of
  `STORAGE_ROOT` (volume snapshot, `rsync`/`rclone` to object storage, or the
  hosting platform's disk backup). A cron `rsync -a` onto the same off-host
  volume that holds `BACKUP_DIR` is acceptable.
- Inside this application there is deliberately **no "backup files into
  PostgreSQL"** feature — uploaded bytes are not stored in the database.

### Restore ordering

1. Restore the **database** (rows give the authoritative file paths).
2. Restore **files** into the exact original `STORAGE_ROOT` (`rsync -a` or
   snapshot restore) so `resumes.file_path` / `application_documents.file_path`
   resolve again.
3. Run the checks below.

### Mismatches

- **Metadata exists but the file is missing** (database restored, files not
  yet): the document appears in the UI with an empty file reference; resume
  parsing/re-upload fails until the file is back. Restore the files, then
  re-run any failed parse.
- **File exists but metadata is missing** (files restored from an older
  snapshot than the DB): the file is orphaned — the app ignores it (no
  garbage collector) and the user simply doesn't see that document. Restore a
  filesystem snapshot that matches the database dump time.

---

## 10. Health / readiness verification after restore

The app must boot through the same path as any deployment:

1. `python -m app.database.init` — only needed if restoring into an **empty**
   database (a restored dump already contains the schema). Safe to run either
   way; it only creates missing tables.
2. `GET /healthz` — the app is up.
3. `GET /health/readyz` — the app can reach the database (500 if it cannot).
4. Sign in (Firebase), open Resumes/Applications/Jobs and confirm data loads.
5. Download/open a stored document to confirm uploaded-file recovery.

---

## 11. Operational checklist

### PRE-RESTORE

- [ ] Identify the backup to restore (`list`, `verify`)
- [ ] Backup is verified: `python -m app.ops.backup verify --dump <archive>`
- [ ] A practice restore to a disposable database succeeded (§7)
- [ ] Target database identified and confirmed (`--target-database-url` or
      default `DATABASE_URL`)
- [ ] Environment confirmed (you are on the intended host / environment)
- [ ] Maintenance window agreed; app traffic paused or announced
- [ ] A fresh current backup (`create`) exists — rollback anchor
- [ ] `STORAGE_ROOT` filesystem backup captured and available

### RESTORE

- [ ] Restore performed with `--confirm-restore` (§8)
- [ ] Uploaded files restored into `STORAGE_ROOT` (§9)
- [ ] Schema present (`init` idempotent, not touching the dump)
- [ ] Critical tables populated: `users`, `resumes`, `applications`,
      `application_documents`, `applications`, `jobs`, `saved_searches`
- [ ] Application started
- [ ] `GET /healthz` → 200
- [ ] `GET /health/readyz` → 200 (DB reachable)
- [ ] Authentication works (sign-in succeeds)
- [ ] Uploaded-file availability spot-checked (§9)

### POST-RESTORE

- [ ] Smoke checks: list resumes, open an application, run one discovery or
      match, view job details
- [ ] Logs inspected for restore-era errors
- [ ] Critical application flows verified (upload a small document replaced)
- [ ] Recovery result recorded (backup used, restore time, issues, who ran it)

---

## 12. Rollback considerations

- **Failed/mid-restore:** `pg_restore --exit-on-error` stops on the first
  error and reports the failing object; the target may be partially replaced.
  Because you took a pre-restore backup (§11), restore that backup back into
  the target and re-verify.
- **Wrong backup restored:** restore the correct (previously verified) archive
  into the target; re-run post-restore checks.
- **Files missing after DB restore:** restore the matching `STORAGE_ROOT`
  snapshot; files and rows must be from the same point-in-time for consistency.
- **App misbehaves after restore:** compare `ENVIRONMENT`/config with the
  pre-restore state (CORS/trusted hosts/rate-limit settings are config, not
  data, and are not affected by the DB).

---

## 13. Common failure cases

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ERROR: DATABASE_URL is not configured…` | missing/empty `DATABASE_URL` | set `DATABASE_URL` (or `--target-database-url` for restore) |
| `ERROR: required PostgreSQL client tool not found…` | `pg_dump`/`pg_restore`/`psql` missing | install `postgresql-client` on the backup host |
| `ERROR: refusing to overwrite an existing backup…` | two creates in the same second | retry after a second, or move the existing archive |
| `verify` reports `checksum mismatch` | corrupt archive or mismatched sidecar | do not restore; re-create the backup |
| `verify` reports `pg_restore could not inspect…` | truncated/corrupt archive | do not restore; re-create the backup |
| `ERROR: restore refused: pass --confirm-restore…` | confirmation flag missing | re-run with `--confirm-restore` (only when certain) |
| `could not create target database` | missing CREATEDB privilege | create the scratch DB with an admin role, or run against an existing empty DB |
| `pg_restore failed …` referencing objects | ownership/role differences | run restore as the app/owner role; `--no-owner` is already applied |

---

## 14. What is and is not covered

Covered:

- logical PostgreSQL backup/verify/restore/retention via standard tools;
- checksum sidecars and a documented human-restore workflow;
- `STORAGE_ROOT` filesystem recovery guidance (§9).

Not covered (by design or out of scope for 5E.11):

- no proprietary backup format, no in-app backup engine, no database backup
  API endpoint — restore is an operator task via the CLI, never a web endpoint;
- no cloud object-storage lifecycle management, no provider-managed PITR —
  configure those at the infrastructure layer;
- no encryption of backups at rest by the tool itself (the volume / bucket
  should be encrypted at the infrastructure layer and credentials must stay
  out of the repository);
- no orchestrated multi-host scheduling — run `create` from cron if desired;
  lock/cron overlap is safe because a same-name archive is refused, though two
  simultaneous creates in the same second cannot both succeed.

## Files

- `app/ops/config.py` — configuration, naming, path confinement, listing,
  retention selection
- `app/ops/backup.py` — CLI (`python -m app.ops.backup`): create / list /
  verify / cleanup / restore
- `app/core/config.py` — `BACKUP_DIR`, `BACKUP_RETENTION_COUNT`
- `tests/test_backup.py` — unit tests (no PostgreSQL needed)
- `tests/test_backup_integration.py` — PostgreSQL round-trip (skipped unless
  `POSTGRES_TEST_DATABASE_URL` is set)