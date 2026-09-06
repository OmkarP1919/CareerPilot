"""Centralized, safe local-filesystem storage for uploaded documents.

Phase 5E.6 hardening. All uploaded-file operations (resolving a user's
storage directory, generating safe stored filenames, resolving stored paths,
atomically writing uploads, and deleting stored files) are performed here so
that:

- user-controlled path components can never escape the storage root
- client-supplied filenames are never treated as filesystem paths
- uploads are written atomically (temp file + rename) so a failed upload
  never leaves a partial final file
- file deletions are idempotent and scoped to the owning user's storage
  directory whenever the target falls under the storage root (cross-user
  deletions inside the root are refused)

Authorization is NOT derived from filesystem paths; database ownership
checks remain authoritative. Filesystem containment is defense-in-depth.

Callers may pass an explicit ``root`` (a resolved storage root Path). When
``root`` is omitted, ``storage_root()`` is used, which reads ``STORAGE_ROOT``
from configuration and defaults to the project-local ``backend/uploads``.
"""

import logging
import os
import re
import uuid
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger("app.storage")

# Characters that are never allowed in a stored/original filename component.
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
# Directory separators (both styles), so a filename can never smuggle a path.
_SEPARATOR_RE = re.compile(r"[/\\]")


def _default_storage_root() -> Path:
    """Return the project-local default storage root (``backend/uploads``).

    Resolves relative to this file: app/core/storage.py -> backend/app/core ->
    backend/app -> backend. The final ``/uploads`` is the legacy location that
    existing samples and dev data already use, so the default preserves
    prior behavior.
    """
    return Path(__file__).resolve().parent.parent.parent / "uploads"


def storage_root() -> Path:
    """Return the configured (or default) storage root as an absolute Path."""
    settings = get_settings()
    configured = (settings.STORAGE_ROOT or "").strip()
    root = Path(configured).expanduser() if configured else _default_storage_root()
    return root.resolve()


def ensure_user_dir(user_id: str, root: Path | None = None) -> Path:
    """Create and return the user-scoped storage directory.

    The user directory lives directly under the storage root
    (``STORAGE_ROOT/<user_id>/``). ``user_id`` is a server-generated UUID from
    the authenticated user record, but it is still forced to stay within the
    root as a defense-in-depth containment check.
    """
    base = (root if root is not None else storage_root()).resolve()
    user_dir = _resolve_within(base, _safe_storage_component(user_id))
    if user_dir is None:
        raise ValueError("Invalid user storage path")
    user_dir.mkdir(parents=True, exist_ok=True)
    # Best-effort restrictive permissions; ignored where unsupported (Windows).
    try:
        os.chmod(user_dir, 0o700)
    except OSError:
        pass
    return user_dir


def safe_stored_filename(extension: str) -> str:
    """Return a generated UUID filename with the given extension.

    ``extension`` must be a validated allow-listed extension (e.g. ``.pdf``);
    it is normalized to lowercase and stripped of any path separators. The
    returned string is safe to use as a single filesystem path component.
    """
    ext = (extension or "").lower()
    ext = _SEPARATOR_RE.sub("", ext)
    return f"{uuid.uuid4()}{ext}"


def resolve_user_file_path(
    user_id: str, filename: str, root: Path | None = None
) -> Path | None:
    """Resolve a stored file path for ``user_id`` under the storage root.

    Returns ``None`` if ``filename`` is empty or would escape the user's
    storage directory. The returned path always sits within
    ``STORAGE_ROOT/<user_id>/``.
    """
    base = (root if root is not None else storage_root()).resolve()
    user_dir = _resolve_within(base, _safe_storage_component(user_id))
    return _resolve_within(user_dir, filename)


def write_upload_atomic(
    user_id: str,
    filename: str,
    read_chunk,
    max_size: int,
    root: Path | None = None,
) -> str:
    """Atomically stream an upload to its final stored location.

    ``read_chunk`` is a zero-argument callable returning the next chunk of
    bytes (``None``/``b""`` when exhausted). Data is written to a temporary
    file inside ``STORAGE_ROOT/<user_id>/`` and renamed to ``filename`` only
    after the whole stream has been read and its size validated.

    Raises ``ValueError`` if ``max_size`` is exceeded. On any failure the
    temporary file is always removed, so no partial or orphan final file is
    left behind. Returns the absolute stored path as a string on success.
    """
    base = (root if root is not None else storage_root()).resolve()
    user_dir = ensure_user_dir(user_id, root=base)
    final_path = _resolve_within(user_dir, filename)
    if final_path is None:
        raise ValueError("Invalid stored filename")

    tmp_path = user_dir / f".{filename}.tmp-{uuid.uuid4().hex}"
    total = 0
    try:
        with open(tmp_path, "wb") as out:
            while True:
                chunk = read_chunk()
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size:
                    raise ValueError("File too large")
                out.write(chunk)
        # Atomically move the fully-written temp file into its final name.
        os.replace(tmp_path, final_path)
    except Exception:
        _safe_unlink(tmp_path)
        raise
    return str(final_path)


def delete_file_safely(
    user_id: str, file_path: str | None, root: Path | None = None
) -> None:
    """Remove a stored file belonging to ``user_id``, safely and idempotently.

    The ``file_path`` must resolve to a real file inside
    ``STORAGE_ROOT/<user_id>/``; anything else (missing, empty, or outside
    the user's directory) is ignored. Missing files are tolerated (no error).
    Logs (never the file contents) on failure.

    Path resolution rules:
    - a RELATIVE ``file_path`` is resolved against the user's storage
      directory and must stay within it;
    - an ABSOLUTE ``file_path`` is the server-recorded location (the database
      row was already verified as owned by ``user_id``, and the caller never
      passes client-supplied filenames here), so it is removed directly -
      but only when it is NOT outside the storage root's *other* user
      directories: a path that resolves inside the current storage root yet
      outside ``user_id``'s own directory is refused (cross-user guard). A
      path that lies outside the storage root entirely is still removed,
      preserving the legacy contract that a file recorded under an earlier
      STORAGE_ROOT keeps being deleted by its owner.
    """
    if not file_path:
        return
    base = (root if root is not None else storage_root()).resolve()
    user_dir = _resolve_within(base, _safe_storage_component(user_id))
    if user_dir is None:
        logger.warning("Invalid stored path for user_id=%s", user_id)
        return

    given = Path(file_path)
    if given.is_absolute():
        resolved = given.resolve()
        if _path_is_within(base, resolved) and not _path_is_within(user_dir, resolved):
            logger.warning(
                "Refusing to delete file outside user storage dir user_id=%s", user_id
            )
            return
    else:
        resolved = _resolve_within(user_dir, file_path)
        if resolved is None:
            logger.warning(
                "Refusing to delete file outside user storage dir user_id=%s", user_id
            )
            return
    _safe_unlink(resolved)


def _safe_storage_component(raw: str) -> str:
    """Return a single safe path component derived from ``raw``.

    Removes control characters and both directory separator styles so a
    user/component value can never traverse or escape the storage root.
    """
    cleaned = _CONTROL_RE.sub("", raw)
    cleaned = _SEPARATOR_RE.sub("", cleaned)
    return cleaned or "unknown"


def sanitize_name(raw: str) -> str:
    """Return ``raw`` with control characters and path separators removed.

    Used to make user-supplied names safe for display/metadata and as a
    building block for safe path components. Does not itself strip ``..``;
    callers that keep only the basename are responsible for traversal safety.
    """
    cleaned = _CONTROL_RE.sub("", raw)
    cleaned = _SEPARATOR_RE.sub("", cleaned)
    return cleaned


def _path_is_within(base: Path, target: Path) -> bool:
    """True if the already-resolved ``target`` lies within ``base``."""
    try:
        target.relative_to(base)
        return True
    except ValueError:
        return False


def _resolve_within(base: Path, target: str) -> Path | None:
    """Resolve ``target`` and return it only if it lies within ``base``.

    Handles both relative targets (joined under ``base`` before resolving) and
    absolute targets (resolved as-is), then verifies containment after
    ``Path.resolve()`` so ``..`` traversal and symlinks can never escape
    ``base``. Returns ``None`` when the target is empty or escapes.
    """
    if not target:
        return None
    base_resolved = base.resolve()
    candidate = Path(target)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        return None
    return resolved


def _safe_unlink(path: Path) -> None:
    """Best-effort removal; tolerates a missing file and only logs failure."""
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not remove file from disk: %s", path.name)
