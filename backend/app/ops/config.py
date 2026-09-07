"""Backup & recovery configuration and pure path/naming logic (Phase 5E.11).

Design:

- All path/name decisions live here so they can be unit-tested without a
  database or PostgreSQL client binaries.
- ``BackupConfig`` resolves deployment values from existing application
  settings (``DATABASE_URL``, ``ENVIRONMENT``) plus the Phase 5E.11 settings
  ``BACKUP_DIR`` / ``BACKUP_RETENTION_COUNT``. Every field may be overridden
  explicitly (the CLI and tests use overrides; nothing here writes to the
  environment).
- Backup filenames follow a strict, parseable convention:
  ``careerpilot_<environment>_<YYYYmmdd-HHMMSSZ>.dump``. Only files matching
  this convention are ever considered backups; everything else under a backup
  directory is ignored (never listed, never deleted).
- Every user-supplied backup path is confined to the resolved backup
  directory. Resolve-then-contain logic rejects ``..`` traversal, absolute
  escapes, and symlink escapes.
- No credentials or connection strings are ever printed or stored here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_settings


class BackupConfig:
    """Resolved, override-able configuration for backup/restore operations.

    Values resolve from application settings unless explicitly provided:

    - ``database_url``  — str, default ``settings.DATABASE_URL``
    - ``backup_dir``    — str/None, default ``settings.BACKUP_DIR`` or the
      project-local ``backend/backups``
    - ``retention_count``— int, default ``settings.BACKUP_RETENTION_COUNT``
    - ``environment``   — str label used in filenames; default
      ``settings.ENVIRONMENT`` lowered, sanitized downstream.
    """

    def __init__(
        self,
        database_url: str | None = None,
        backup_dir: str | None = None,
        retention_count: int | None = None,
        environment: str | None = None,
    ) -> None:
        settings = get_settings()
        self.database_url = (
            database_url if database_url is not None else (settings.DATABASE_URL or "")
        ).strip()
        self.backup_dir = resolve_backup_dir(
            backup_dir if backup_dir is not None else (settings.BACKUP_DIR or "")
        )
        env = environment or getattr(settings, "ENVIRONMENT", None) or "development"
        self.environment = sanitize_environment_label(env)
        if retention_count is not None:
            self.retention_count = retention_count
        else:
            self.retention_count = settings.BACKUP_RETENTION_COUNT
        if (
            not isinstance(self.retention_count, int)
            or isinstance(self.retention_count, bool)
            or self.retention_count < 1
        ):
            raise BackupError("retention count must be a positive integer (>= 1)")


class BackupError(Exception):
    """Operational backup/recovery failure with a safe (redacted) message."""


class RestoreAborted(Exception):
    """A restore operation was refused by a safety guard (confirmation missing)."""


# Naming conventions ---------------------------------------------------------

_BACKUP_NAME_RE = re.compile(
    r"^careerpilot_([a-z0-9][a-z0-9_-]{0,47})_(\d{8}-\d{6}Z)\.dump$"
)


def sanitize_environment_label(raw: str | None) -> str:
    """Return a filesystem-safe environment label derived from ``raw``.

    Lowercases, collapses runs of non-alphanumerics to ``_``, strips leading/
    trailing underscores, and falls back to ``development`` for empty input.
    The result matches ``[a-z0-9][a-z0-9_-]*`` so it can never traverse a path.
    """
    cleaned = re.sub(r"[^a-z0-9]+", "_", (raw or "").strip().lower())
    cleaned = cleaned.strip("_")
    return cleaned or "development"


def backup_filename(environment: str | None, now: datetime | None = None) -> str:
    """Return a timestamped backup filename for ``environment``.

    The timestamp is UTC and formatted ``YYYYmmdd-HHMMSSZ`` so filenames sort
    lexicographically in chronological order. Two backups created within the
    same second share a name; the no-overwrite guard in ``create_backup``
    refuses to clobber, so a retry after a second is required (or an error).
    """
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%SZ")
    return f"careerpilot_{sanitize_environment_label(environment)}_{timestamp}.dump"


def parse_backup_name(name: str | None) -> tuple[str, str] | None:
    """Parse a backup filename into ``(environment, timestamp)`` or ``None``.

    Returns ``None`` (never raises) for any name that does not match the
    strict convention — including names containing path separators, dot-dot
    segments, leading dots, or unrecognized suffixes. ``timestamp`` is the
    sortable ``YYYYmmdd-HHMMSSZ`` string.
    """
    match = _BACKUP_NAME_RE.match(name or "")
    if not match:
        return None
    return match.group(1), match.group(2)


def is_valid_backup_name(name: str | None) -> bool:
    """True only for names matching the strict backup filename convention."""
    return parse_backup_name(name) is not None


def checksum_sidecar_name(dump_name: str) -> str:
    """Return the SHA-256 sidecar filename for a dump (``<name>.sha256``)."""
    return f"{dump_name}.sha256"


# Backup directory ------------------------------------------------------------

def default_backup_dir() -> Path:
    """Project-local default backup directory: ``backend/backups``."""
    return Path(__file__).resolve().parent.parent.parent / "backups"


def resolve_backup_dir(configured: str | None) -> Path:
    """Absolute backup directory: the configured value or the project default."""
    value = (configured or "").strip()
    if value:
        return Path(value).expanduser().resolve()
    return default_backup_dir().resolve()


def resolve_backup_path(backup_dir: Path, user_input: str | None) -> Path:
    """Resolve a user-supplied backup path, confined to ``backup_dir``.

    A relative input is resolved under the backup directory; an absolute input
    must resolve inside it (``Path.resolve`` neutralizes ``..`` and symlinks).
    Raises ``BackupError`` for empty input or anything that escapes.
    """
    raw = (user_input or "").strip()
    if not raw:
        raise BackupError("a backup file path is required")
    if "\\" in raw:
        # Backslash is a path separator on Windows but a literal filename
        # character on POSIX. Rejecting it here stops Windows-style traversal
        # ("..\\escape.dump") from bypassing containment on Linux without
        # weakening the resolve-then-contain check below.
        raise BackupError(f"backup path must not contain backslashes: {raw!r}")
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (backup_dir / candidate).resolve()
    base = backup_dir.resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise BackupError(
            f"backup path is outside the backup directory: {raw!r}"
        ) from None
    return resolved


@dataclass
class BackupFile:
    """A single valid backup on disk (name, location, metadata)."""

    path: Path
    name: str
    environment: str
    timestamp: str  # sortable 'YYYYmmdd-HHMMSSZ'
    size: int
    modified_at: float

    @property
    def checksum_path(self) -> Path:
        return self.path.with_name(checksum_sidecar_name(self.name))


def list_backups(backup_dir: Path) -> list[BackupFile]:
    """List valid backups directly under ``backup_dir``, newest first.

    Only direct children whose name matches the strict convention are
    returned. Subdirectories, temp files, sidecar files, and unrecognized
    names are ignored. Ordering is deterministic: newest timestamp first,
    ties broken by name ascending.
    """
    base = backup_dir.resolve()
    if not base.is_dir():
        return []
    found: list[BackupFile] = []
    for entry in base.iterdir():
        if not entry.is_file():
            continue
        parsed = parse_backup_name(entry.name)
        if parsed is None:
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        found.append(
            BackupFile(
                path=entry,
                name=entry.name,
                environment=parsed[0],
                timestamp=parsed[1],
                size=stat.st_size,
                modified_at=stat.st_mtime,
            )
        )
    found.sort(key=lambda f: (f.timestamp, f.name), reverse=True)
    return found


# Retention ------------------------------------------------------------------

def select_old_backups(backups: list[BackupFile], keep_count: int) -> list[BackupFile]:
    """Return the backups a ``keep_count`` retention policy would remove.

    ``backups`` must already be sorted newest-first (as ``list_backups``
    returns). The newest ``keep_count`` are retained and the remainder is
    returned oldest-first so deletion order is deterministic. ``keep_count``
    must be >= 1 so the newest valid backup can never be pruned.
    """
    if not isinstance(keep_count, int) or isinstance(keep_count, bool) or keep_count < 1:
        raise BackupError("retention count must be a positive integer (>= 1)")
    if len(backups) <= keep_count:
        return []
    return list(backups[keep_count:])


# Database URL sanity checks ---------------------------------------------------

def assert_database_configured(database_url: str) -> None:
    """Fail loudly when ``database_url`` is unusable for backup/restore.

    Only PostgreSQL URLs are accepted (the tooling is a thin wrapper around
    pg_dump/pg_restore/psql). Empty/malformed values raise ``BackupError``
    before any subprocess is spawned. The URL itself is never echoed.
    """
    value = (database_url or "").strip()
    if not value:
        raise BackupError(
            "DATABASE_URL is not configured; set it (or pass --target-database-url) before backup/restore"
        )
    try:
        backend = make_url(value).get_backend_name()
    except Exception:
        raise BackupError("DATABASE_URL is not a valid database URL") from None
    if backend not in ("postgresql", "postgres"):
        raise BackupError("backup tooling requires a PostgreSQL DATABASE_URL")