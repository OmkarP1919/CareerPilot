"""Operational backup & recovery CLI (Phase 5E.11).

Usage (all commands):

    python -m app.ops.backup create                       # new backup + checksum sidecar
    python -m app.ops.backup list                         # list valid backups
    python -m app.ops.backup verify --dump <path>         # validate an archive
    python -m app.ops.backup cleanup [--keep N] [--dry-run]
    python -m app.ops.backup restore --dump <path> --confirm-restore

Implementation notes:

- This is an administrator/operations tool, NOT a FastAPI endpoint and NOT an
  application import. The running application never performs backups/restores.
- PostgreSQL client tools (pg_dump, pg_restore, psql) are invoked as argument
  arrays via ``subprocess.run`` — never through a shell, so URLs/filenames
  cannot trigger shell injection.
- Backups are custom-format dumps (pg_restore-friendly) with a SHA-256 sidecar.
  The dump is written to a temp file in the backup directory then atomically
  renamed; an existing backup name is never overwritten.
- Restore requires an explicit ``--confirm-restore`` flag and refuses to act
  without it. It warns that target data may be replaced, and ``--verify-first``
  runs a non-destructive ``pg_restore --list`` check before restoring.
- Paths, filenames, and every deletion are constrained to the backup directory;
  deletion only ever touches files matching the strict backup naming convention.
- DATABASE_URL values and error output are redacted before reaching the user.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

from app.ops.config import (
    BackupConfig,
    BackupError,
    RestoreAborted,
    assert_database_configured,
    backup_filename,
    checksum_sidecar_name,
    is_valid_backup_name,
    list_backups,
    resolve_backup_path,
    select_old_backups,
)

_DEFAULT_TIMEOUT_SECONDS = 900


# Redaction helpers ------------------------------------------------------------

def redact_database_url(database_url: str | None) -> str:
    """Render ``database_url`` with its password (and passphrase) hidden."""
    value = (database_url or "").strip()
    if not value:
        return ""
    try:
        return make_url(value).render_as_string(hide_password=True)
    except Exception:
        return "<invalid-database-url>"


def database_name(database_url: str | None) -> str:
    """Return the database name from a URL, or ``<unknown>``."""
    try:
        parsed = make_url(database_url or "")
        return parsed.database or "<unknown>"
    except Exception:
        return "<invalid-database-url>"


def _command_preview(command: list[str]) -> str:
    """Human-readable preview of a subprocess command with URLs redacted."""
    parts: list[str] = []
    for part in command:
        if "://" in part and part.split(":", 1)[0].lower() in ("postgresql", "postgres"):
            parts.append(redact_database_url(part))
        else:
            parts.append(part)
    return " ".join(parts)


def _stderr_tail(stderr: str, limit: int = 800) -> str:
    trimmed = (stderr or "").strip()
    return trimmed[-limit:] if len(trimmed) > limit else trimmed


# Subprocess helpers -----------------------------------------------------------

def _require_program(name: str) -> None:
    if shutil.which(name) is None:
        raise BackupError(
            f"required PostgreSQL client tool not found: {name} "
            "(install postgresql-client on the host)"
        )


def run_command(
    command: list[str],
    timeout: int = _DEFAULT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    """Run ``command`` as an argument array (never a shell string).

    Raises ``BackupError`` with a redacted preview on start/timeout failures.
    The caller inspects ``returncode``/``stderr``; nothing here prints either.
    """
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        raise BackupError(f"required program not found: {command[0]}") from None
    except subprocess.TimeoutExpired:
        raise BackupError(f"command timed out: {_command_preview(command)}") from None
    except OSError as exc:
        raise BackupError(
            f"command could not be started ({exc}): {_command_preview(command)}"
        ) from None


# Command construction (asserted by unit tests) --------------------------------

def pg_dump_command(database_url: str, output_path: Path) -> list[str]:
    """Build the pg_dump argv for a custom-format archive at ``output_path``."""
    return [
        "pg_dump",
        "--format=custom",
        "--file", str(output_path),
        "--dbname", database_url,
    ]


def pg_restore_list_command(dump_path: Path) -> list[str]:
    """Build the non-destructive archive-inspection argv."""
    return ["pg_restore", "--list", str(dump_path)]


def pg_restore_restore_command(database_url: str, dump_path: Path) -> list[str]:
    """Build the argv that restores an archive into ``database_url``.

    ``--clean --if-exists`` replaces existing objects (deliberately destructive
    — restore always gates on ``--confirm-restore``). ``--no-owner`` avoids
    ownership errors when the connecting role differs from the dump's.
    """
    return [
        "pg_restore",
        "--exit-on-error",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--dbname", database_url,
        str(dump_path),
    ]


def pg_restore_sql_command(dump_path: Path, output_path: Path) -> list[str]:
    """Build the argv that extracts an archive into a plain SQL script.

    Mirrors the destructive restore flags used by the direct restore path
    (``--clean --if-exists``) and ``--no-owner``; no database is touched. Used
    only by the PostgreSQL 16 compatibility path, which filters the extracted
    SQL before executing it with ``psql``.
    """
    return [
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--file", str(output_path),
        str(dump_path),
    ]


def psql_run_script_command(database_url: str, script_path: Path) -> list[str]:
    """Build the argv that executes a SQL script with errors treated as fatal.

    ``ON_ERROR_STOP`` makes ``psql`` abort (non-zero exit) on ANY unexpected
    error, so the compatibility path can never hide arbitrary restore errors.
    """
    return [
        "psql",
        "--set", "ON_ERROR_STOP=1",
        "--dbname", database_url,
        "--file", str(script_path),
    ]


# PostgreSQL 17 clients embed this session-setting in the dump header; servers
# before PostgreSQL 17 reject it as an unrecognized configuration parameter.
# Only the exact whole-line statement is ever removed by the compatibility path.
_TRANSACTION_TIMEOUT_SET_RE = re.compile(
    rb"^[ \t]*SET[ \t]+transaction_timeout[ \t]*=[ \t]*0[ \t]*;?[ \t]*\r?$",
    re.IGNORECASE,
)


def filter_pg16_transaction_timeout(sql: bytes) -> tuple[bytes, int]:
    """Remove the exact ``SET transaction_timeout = 0;`` statement from ``sql``.

    The statement is matched as a single anchored whole line (case-insensitive,
    allowing surrounding whitespace), so unrelated SQL is never modified.
    Returns ``(filtered_sql, removed_count)``.
    """
    lines = sql.splitlines(keepends=True)
    kept = [line for line in lines if _TRANSACTION_TIMEOUT_SET_RE.match(line) is None]
    return b"".join(kept), len(lines) - len(kept)


# Checksums --------------------------------------------------------------------

def compute_sha256(path: Path) -> str:
    """Return the lowercase hex SHA-256 of ``path``."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksum_sidecar(dump_path: Path) -> Path:
    """Write ``<dump>.sha256`` in ``sha256sum`` format next to the archive."""
    digest = compute_sha256(dump_path)
    sidecar = dump_path.with_name(checksum_sidecar_name(dump_path.name))
    sidecar.write_text(f"{digest}  {dump_path.name}\n", encoding="utf-8")
    return sidecar


def verify_checksum(dump_path: Path) -> tuple[bool | None, str]:
    """Validate ``<dump>.sha256`` against the archive contents.

    Returns ``(None, reason)`` when no sidecar exists (informational, not a
    failure — older backups may predate sidecars), otherwise ``(True|False, detail)``.
    """
    sidecar = dump_path.with_name(checksum_sidecar_name(dump_path.name))
    if not sidecar.is_file():
        return None, "no checksum sidecar present (skipped)"
    try:
        expected = sidecar.read_text(encoding="utf-8").split()[0].strip().lower()
    except (OSError, IndexError):
        return False, "checksum sidecar is unreadable or malformed"
    actual = compute_sha256(dump_path)
    if actual == expected:
        return True, "checksum ok"
    return False, f"checksum mismatch (expected {expected}, got {actual})"


# Backup -----------------------------------------------------------------------

def ensure_backup_dir(config: BackupConfig) -> Path:
    """Create/config-check the backup directory; returns it resolved."""
    target = config.backup_dir
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackupError(f"could not create backup directory {target}: {exc}") from None
    return target


def execute_pg_dump(config: BackupConfig, output_path: Path) -> None:
    """Run pg_dump writing a custom-format archive at ``output_path``.

    On failure raises ``BackupError`` carrying a redacted tail of pg_dump's
    stderr (the URL is never included). No application data is modified.
    """
    _require_program("pg_dump")
    command = pg_dump_command(config.database_url, output_path)
    result = run_command(command)
    if result.returncode != 0:
        raise BackupError(
            f"pg_dump failed (exit {result.returncode}): {_stderr_tail(result.stderr)}"
        )


def create_backup(config: BackupConfig) -> Path:
    """Create a timestamped backup + SHA-256 sidecar in ``config.backup_dir``.

    Refuses to overwrite an existing archive. The dump is written to a
    temporary file inside the backup directory and atomically renamed, so a
    failed pg_dump never leaves a partial final archive and concurrent creates
    cannot interleave. Returns the final archive path.
    """
    assert_database_configured(config.database_url)
    backup_dir = ensure_backup_dir(config)
    name = backup_filename(config.environment)
    final = backup_dir / name
    if final.exists():
        raise BackupError(
            f"refusing to overwrite an existing backup: {name} "
            "(wait one second and retry, or archive the existing file)"
        )
    temp = backup_dir / f".{name}.tmp-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    try:
        execute_pg_dump(config, temp)
        os.replace(temp, final)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
    write_checksum_sidecar(final)
    return final


# Verification -----------------------------------------------------------------

def verify_backup(
    config: BackupConfig,
    dump_input: str | None,
    *,
    require_list: bool = True,
) -> dict:
    """Non-destructively validate a backup archive.

    Checks (in order): existence, file (not dir), strict naming convention,
    non-zero size, checksum sidecar (validate when present), and — unless
    ``require_list`` is False — that ``pg_restore --list`` can parse the
    archive. Safe to run for any backup; nothing is ever restored here.
    Returns a plain dict ``{ok, path, errors: [...], checksum, size}``.
    """
    path = resolve_backup_path(config.backup_dir, dump_input)
    result: dict = {
        "ok": False,
        "path": str(path),
        "size": None,
        "checksum": None,
        "errors": [],
    }
    if not (path.is_file() and not path.is_dir()):
        result["errors"].append("backup file does not exist or is not a regular file")
        return result
    result["size"] = path.stat().st_size
    if not is_valid_backup_name(path.name):
        result["errors"].append(
            "file name does not match the backup convention "
            "(careerpilot_<env>_<YYYYmmdd-HHMMSSZ>.dump)"
        )
        return result
    if result["size"] <= 0:
        result["errors"].append("backup file is empty")
        return result

    checksum_ok, detail = verify_checksum(path)
    result["checksum"] = {"ok": checksum_ok, "detail": detail}
    if checksum_ok is False:
        result["errors"].append(detail)

    if require_list:
        _require_program("pg_restore")
        list_result = run_command(pg_restore_list_command(path))
        if list_result.returncode != 0 or not list_result.stdout.strip():
            result["errors"].append(
                "pg_restore could not inspect the archive "
                f"(exit {list_result.returncode})"
            )

    result["ok"] = not result["errors"]
    return result


# Retention --------------------------------------------------------------------

def prune_backups(
    config: BackupConfig,
    keep_count: int | None = None,
    *,
    dry_run: bool = False,
) -> tuple[list[Path], list[Path]]:
    """Remove valid backups beyond the retention count under ``config.backup_dir``.

    Deletion is deterministic (oldest first), confined to the backup directory,
    limited to names matching the strict convention, and always preserves the
    newest ``keep_count`` backups (never the newest when ``keep_count >= 1``).
    Each removed archive also removes its checksum sidecar. Returns
    ``(removed_paths, removed_sidecars)``; ``dry_run`` computes but deletes
    nothing.
    """
    keep = config.retention_count if keep_count is None else keep_count
    backups = list_backups(config.backup_dir)
    removed = select_old_backups(backups, keep)
    removed_paths: list[Path] = []
    removed_sidecars: list[Path] = []
    for backup in removed:
        removed_paths.append(backup.path)
        if backup.checksum_path.is_file():
            removed_sidecars.append(backup.checksum_path)
        if not dry_run:
            try:
                backup.path.unlink(missing_ok=True)
                backup.checksum_path.unlink(missing_ok=True)
            except OSError as exc:
                raise BackupError(
                    f"could not remove backup {backup.name}: {exc}"
                ) from None
    return removed_paths, removed_sidecars


# Restore ----------------------------------------------------------------------

def _psql(argv_tail: list[str]) -> subprocess.CompletedProcess:
    _require_program("psql")
    return run_command(["psql"] + argv_tail)


def _maintenance_database_url(database_url: str) -> str:
    """Return the ``postgres`` maintenance URL for ``database_url``'s server."""
    parsed = make_url(database_url)
    if not parsed.database:
        raise BackupError("target database URL has no database name")
    return parsed.set(database="postgres").render_as_string(hide_password=False)


def _server_version_num(database_url: str) -> int:
    """Read-only probe of the target server's version (e.g. ``160015``).

    Connects to the server's ``postgres`` maintenance database so the probe
    works even before a not-yet-created target database exists.
    """
    probe = _psql(
        [
            "--tuples-only",
            "--no-align",
            "--quiet",
            "--dbname", _maintenance_database_url(database_url),
            "--command", "SHOW server_version_num",
        ]
    )
    if probe.returncode != 0:
        raise BackupError(
            f"could not determine server version: {_stderr_tail(probe.stderr)}"
        )
    try:
        return int((probe.stdout or "").strip())
    except ValueError:
        raise BackupError("could not parse server version from psql output") from None


def server_supports_transaction_timeout(database_url: str) -> bool:
    """True when the target server is PostgreSQL 17+ (owns ``transaction_timeout``).

    Keeps the strict direct ``pg_restore --exit-on-error`` path for servers
    that accept the parameter and reserves the narrowly-scoped SQL-filter path
    for older servers (PG16 and below) where PG17-created archives would
    otherwise abort before restoring anything.
    """
    return _server_version_num(database_url) >= 170000


def restore_archive_pg16_compat(database_url: str, dump_path: Path) -> None:
    """Restore an archive on PostgreSQL < 17 servers via filtered SQL.

    PG17-created custom archives embed ``SET transaction_timeout = 0;`` in the
    dump header, which PostgreSQL 16 (and earlier) servers reject. Running
    ``pg_restore`` directly with ``--exit-on-error`` therefore aborts on the
    very first statement without restoring anything.

    This path extracts the archive to SQL with the same destructive semantics
    as the direct restore (``--clean --if-exists --no-owner``), strips ONLY the
    single known-inert statement, and executes the result with psql
    ``ON_ERROR_STOP`` so every OTHER error still aborts the restore with a
    non-zero exit. Real restore failures are never converted into success.
    """
    _require_program("pg_restore")
    _require_program("psql")
    with tempfile.TemporaryDirectory(prefix="cp_restore_") as tmp:
        extracted = Path(tmp) / "restore.sql"
        extract_result = run_command(pg_restore_sql_command(dump_path, extracted))
        if extract_result.returncode != 0:
            raise BackupError(
                "pg_restore SQL extraction failed "
                f"(exit {extract_result.returncode}): "
                f"{_stderr_tail(extract_result.stderr)}"
            )
        raw = extracted.read_bytes()
        filtered, removed = filter_pg16_transaction_timeout(raw)
        script = extracted
        if removed:
            script = Path(tmp) / "restore.filtered.sql"
            script.write_bytes(filtered)
        result = run_command(psql_run_script_command(database_url, script))
        if result.returncode != 0:
            raise BackupError(
                f"restore failed (exit {result.returncode}): "
                f"{_stderr_tail(result.stderr)}"
            )


def create_target_database(database_url: str) -> bool:
    """Create the target database from ``database_url`` if it does not exist.

    Connects to the server's ``postgres`` maintenance database and creates the
    requested database (identifier is properly quoted). Returns False when it
    already exists (no-op). Never drops, truncates, or replaces anything.
    """
    parsed = make_url(database_url)
    target_db = parsed.database
    if not target_db:
        raise BackupError("target database URL has no database name")
    maintenance_url = _maintenance_database_url(database_url)
    check = _psql(
        [
            "--tuples-only",
            "--no-align",
            "--quiet",
            "--dbname", maintenance_url,
            "--command",
            f"SELECT 1 FROM pg_database WHERE datname = '{target_db.replace(chr(39), chr(39) * 2)}'",
        ]
    )
    if check.returncode == 0 and check.stdout.strip() == "1":
        return False
    identifier = target_db.replace('"', '""')
    created = _psql(
        [
            "--dbname", maintenance_url,
            "--command",
            f'CREATE DATABASE "{identifier}"',
        ]
    )
    if created.returncode != 0:
        raise BackupError(
            f"could not create target database {database_name(maintenance_url)!r} "
            f"(exit {created.returncode})"
        )
    return True


def restore_backup(
    config: BackupConfig,
    dump_input: str | None,
    *,
    confirm: bool = False,
    target_database_url: str | None = None,
    create_target: bool = False,
    verify_first: bool = False,
) -> dict:
    """Restore ``dump_input`` into a target database.

    Safety chain, in order:
    1. target database is configured and PostgreSQL,
    2. dump path exists, is a file, and matches the naming convention inside
       the backup directory,
    3. optional non-destructive ``--verify-first`` archive inspection,
    4. explicit ``confirm`` (True only via the CLI ``--confirm-restore`` flag)
       — otherwise ``RestoreAborted``,
    5. optional target-database creation (never destructive),
    6. ``pg_restore --clean --if-exists --no-owner`` into the target.

    The CLI prints a replacement warning before invoking this. Returns a short
    status dict. Failures raise ``BackupError``; nothing is ever force-pushed.
    """
    target = target_database_url if target_database_url is not None else config.database_url
    assert_database_configured(target)

    path = resolve_backup_path(config.backup_dir, dump_input)
    if not (path.is_file() and not path.is_dir()):
        raise BackupError(
            f"backup file does not exist or is not a regular file: {path.name}"
        )
    if not is_valid_backup_name(path.name):
        raise BackupError(
            "refusing to restore a file that does not match the backup naming convention"
        )

    if verify_first:
        verified = verify_backup(config, str(path), require_list=True)
        if not verified["ok"]:
            raise BackupError(
                "refusing to restore an unverified archive: "
                + "; ".join(verified["errors"])
            )

    if not confirm:
        raise RestoreAborted(
            "restore refused: pass --confirm-restore to acknowledge that the "
            "target database may be replaced"
        )

    if create_target:
        create_target_database(target)

    _require_program("pg_restore")
    if server_supports_transaction_timeout(target):
        restore_result = run_command(pg_restore_restore_command(target, path))
        if restore_result.returncode != 0:
            raise BackupError(
                f"pg_restore failed (exit {restore_result.returncode}): "
                f"{_stderr_tail(restore_result.stderr)}"
            )
    else:
        restore_archive_pg16_compat(target, path)
    return {
        "restored": True,
        "dump": path.name,
        "target_database": database_name(target),
    }


# CLI --------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ops.backup",
        description=(
            "CareerPilot database backup & recovery (pg_dump / pg_restore / psql wrapper). "
            "Operational tooling only; never invoked by the running application."
        ),
    )
    parser.add_argument(
        "--backup-dir",
        help="override the backup directory (default: backend/backups or BACKUP_DIR)",
    )
    parser.add_argument(
        "--environment",
        help="override the environment label used in backup filenames",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "create",
        help="create a new custom-format backup and its SHA-256 sidecar",
    )
    sub.add_parser("list", help="list valid backups in the backup directory")

    verify = sub.add_parser("verify", help="validate a backup archive non-destructively")
    verify.add_argument("--dump", required=True, help="backup name or path within the backup directory")
    verify.add_argument(
        "--no-list",
        action="store_true",
        help="skip the pg_restore --list inspection (checks file/name/size/checksum only)",
    )

    cleanup = sub.add_parser("cleanup", help="prune old backups to the retention count")
    cleanup.add_argument("--keep", type=int, help="override BACKUP_RETENTION_COUNT for this run")
    cleanup.add_argument("--dry-run", action="store_true", help="show what would be removed without deleting")

    restore = sub.add_parser(
        "restore",
        help="restore a backup into a database (DESTRUCTIVE - may replace existing data)",
    )
    restore.add_argument("--dump", required=True, help="backup name or path within the backup directory")
    restore.add_argument(
        "--target-database-url",
        help="target PostgreSQL URL (default: configured DATABASE_URL)",
    )
    restore.add_argument(
        "--create-target",
        action="store_true",
        help="create the target database if it does not already exist",
    )
    restore.add_argument(
        "--verify-first",
        action="store_true",
        help="run a non-destructive pg_restore --list check before restoring",
    )
    restore.add_argument(
        "--confirm-restore",
        action="store_true",
        help="REQUIRED: explicitly acknowledge that existing target data may be replaced",
    )
    return parser


def _make_config(args: argparse.Namespace) -> BackupConfig:
    return BackupConfig(
        backup_dir=getattr(args, "backup_dir", None),
        environment=getattr(args, "environment", None),
    )


def _run_command(args: argparse.Namespace) -> int:
    command = args.command
    if command == "create":
        config = _make_config(args)
        path = create_backup(config)
        print(f"Backup created: {path.name}")
        print(f"  size:        {path.stat().st_size} bytes")
        print(f"  checksum:    {checksum_sidecar_name(path.name)}")
        print(f"  directory:   {path.parent}")
        return 0

    if command == "list":
        config = _make_config(args)
        backups = list_backups(config.backup_dir)
        if not backups:
            print(f"No backups found in {config.backup_dir}")
            return 0
        print(f"Backups in {config.backup_dir}:")
        for backup in backups:
            sidecar = "ok" if backup.checksum_path.is_file() else "missing"
            when = datetime.fromtimestamp(backup.modified_at, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%SZ"
            )
            print(
                f"  {backup.name}  {backup.size:>12} bytes  "
                f"modified {when}  checksum={sidecar}"
            )
        return 0

    if command == "verify":
        config = _make_config(args)
        verified = verify_backup(config, args.dump, require_list=not args.no_list)
        if verified["ok"]:
            print(f"Backup OK: {verified['path']}")
            print(f"  size:      {verified['size']} bytes")
            checksum = verified["checksum"] or {}
            print(f"  checksum:  {checksum.get('detail', 'n/a')}")
            return 0
        print(f"Backup FAILED verification: {verified['path']}")
        for error in verified["errors"]:
            print(f"  - {error}")
        return 1

    if command == "cleanup":
        config = _make_config(args)
        keep = getattr(args, "keep", None)
        removed_paths, removed_sidecars = prune_backups(
            config, keep_count=keep, dry_run=args.dry_run
        )
        if args.dry_run:
            print(
                f"[dry-run] would remove {len(removed_paths)} backup(s) "
                f"(retention {config.retention_count}):"
            )
        else:
            print(
                f"Removed {len(removed_paths)} backup(s) "
                f"(retention {config.retention_count}):"
            )
        for path in removed_paths:
            print(f"  - {path.name}")
        for path in removed_sidecars:
            print(f"  - {path.name} (checksum sidecar)")
        if not removed_paths:
            print("  (nothing to remove)")
        return 0

    if command == "restore":
        config = _make_config(args)
        target = args.target_database_url or config.database_url
        print("WARNING: restore may REPLACE existing data in the target database.")
        print(f"  target database: {database_name(target)}")
        print(f"  restore archive: {args.dump}")
        if not args.confirm_restore:
            print("ERROR: --confirm-restore is required to proceed.")
            return 2
        restored = restore_backup(
            config,
            args.dump,
            confirm=args.confirm_restore,
            target_database_url=args.target_database_url,
            create_target=args.create_target,
            verify_first=args.verify_first,
        )
        print(
            f"Restore complete: {restored['dump']} -> database "
            f"{restored['target_database']}"
        )
        return 0

    raise BackupError(f"unknown command: {command}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return _run_command(args)
    except RestoreAborted as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except BackupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())