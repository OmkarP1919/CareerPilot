# File storage (Phase 5E.6)

## Overview

All uploaded files (resumes and application documents) are persisted to local
disk under a single configurable storage root, with hard tenant isolation by
user. Filesystem spread and every storage primitive are centralized in
`app/core/storage.py`; the API modules (`app/api/applications.py`,
`app/api/resumes.py`) only decide *what* is stored and rely on the storage
layer for *how* it is safely written and deleted.

## Configuration

- `STORAGE_ROOT` — optional absolute path to the upload root. When empty, the
  project-local default `backend/uploads` is used.
- Files are stored under `<STORAGE_ROOT>/<user_id>/<uuid>.<ext>`:
  - `<user_id>` is a server-side user UUID (never derived from client input).
  - The stored filename is always a server-generated UUID — the client-supplied
    name is used only as display metadata (`original_filename`).
  - The extension comes from a validated allow-list (`.pdf`, `.docx`), never
    from an unvalidated client filename.
- Size limit is enforced while streaming: uploads are read in bounded 1 MB
  chunks and rejected as soon as the cumulative count exceeds the limit,
  instead of buffering the whole body in memory.

## Safety properties

1. **Path containment.** User-supplied names are never treated as filesystem
   paths. `../` traversal, absolute paths, control characters, and both
   separator styles (`/`, `\`) are neutralized, and resolved paths are checked
   to stay within `STORAGE_ROOT/<user_id>/` (defense-in-depth; database
   ownership checks remain authoritative for authorization).
2. **Atomic uploads.** Data is streamed to a temporary file
   (`.<name>.tmp-<random>`) inside the same directory, then renamed to the
   final name only after the whole stream succeeded and passed size checks.
   Any failure removes the temp file, so a failed upload never leaves a
   partial or orphan final file.
3. **Safe deletes.** Deletions are centralized, idempotent, and scoped
   to the owning user: a missing file is tolerated, a path that resolves
   inside the storage root but into another user's directory is refused, and
   only the file name (never contents) is ever logged. A server-recorded
   absolute path that predates the current `STORAGE_ROOT` is still removed
   for its owner (the database records are the authoritative source of
   ownership after the caller's user-scoped query).
4. **Isolation by user.** Uploads and deletes are always scoped to the
   authenticated user's own directory.

## Delete semantics (unchanged)

- Uploaded application document (`file_path` set, no `source_resume_id`):
  deleting the document removes its own file.
- Reference document (`source_resume_id` set): deleting it NEVER removes the
  referenced resume's file.
- Application deletion removes uploaded document files, and only after the
  database delete commits.
- Resume deletion removes the stored PDF only after the transaction commits;
  leftover disk artefacts never surface as API errors.
- Deletes run strictly after a successful commit so a failed transaction never
  leaves the database pointing at a removed file.

## What is NOT stored or logged

- File contents are never written to logs.
- `file_path` is never exposed in API responses (`ApplicationDocumentResponse`
  and `ResumeResponse` both omit it).
- No cloud storage; no background orphan garbage collection — leftovers are
  only ever the product of an already-committed delete being best-effort.

## Tests

`tests/test_storage.py` covers the storage utility against temp directories
(never the real `backend/uploads`): containment, traversal rejection,
atomic writes, temp cleanup, size bounds, idempotent deletes, and user
isolation.

## Files

- `app/core/storage.py` — root resolution, safe path helpers, atomic write,
  safe delete
- `app/api/applications.py`, `app/api/resumes.py` — upload/delete endpoints
  wired through the storage layer
- `app/core/config.py` — `STORAGE_ROOT` setting