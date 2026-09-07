"""Phase 5E.11 unit tests — backup & recovery tooling.

These tests exercise the operational tooling's logic (path/name handling,
command construction, verification, restore safety, retention) WITHOUT
PostgreSQL or its client binaries. PostgreSQL integration is covered by
``test_backup_integration.py`` (gated on POSTGRES_TEST_DATABASE_URL).
"""

import hashlib
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from app.ops import backup as bk
from app.ops.backup import prune_backups
from app.ops.config import (
    BackupConfig,
    BackupError,
    RestoreAborted,
    assert_database_configured,
    backup_filename,
    checksum_sidecar_name,
    is_valid_backup_name,
    list_backups,
    parse_backup_name,
    resolve_backup_path,
    sanitize_environment_label,
)

TEST_DB = "postgresql://user:pass@localhost:5432/cp_test"


def _completed(returncode=0, stdout="", stderr="", command=None):
    return subprocess.CompletedProcess(
        args=command or [], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _write_dump(directory: Path, name: str, data: bytes = b"ARCHIVEDATA\n") -> Path:
    """Create a valid-named dump (+ matching checksum sidecar) in ``directory``."""
    path = directory / name
    path.write_bytes(data)
    sidecar = directory / checksum_sidecar_name(name)
    sidecar.write_text(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n", encoding="utf-8"
    )
    return path


def _make_config(backup_dir, database_url=TEST_DB, environment="test_env", retention_count=30):
    return BackupConfig(
        database_url=database_url,
        backup_dir=str(backup_dir),
        retention_count=retention_count,
        environment=environment,
    )


def _five_names():
    """Five valid backup names for days 2026-09-01..05, oldest first."""
    return [f"careerpilot_prod_2026090{day}-000000Z.dump" for day in range(1, 6)]


class ConfigAndNamingTests(unittest.TestCase):
    def test_config_defaults_resolve_backup_dir(self):
        config = BackupConfig(database_url=TEST_DB)
        self.assertTrue(config.backup_dir.is_absolute())
        self.assertGreaterEqual(config.retention_count, 1)

    def test_retention_count_validation(self):
        with self.assertRaises(BackupError):
            BackupConfig(database_url=TEST_DB, retention_count=0)
        with self.assertRaises(BackupError):
            BackupConfig(database_url=TEST_DB, retention_count=-1)

    def test_missing_database_url_rejected(self):
        with self.assertRaises(BackupError):
            assert_database_configured("")
        with self.assertRaises(BackupError):
            assert_database_configured("   ")

    def test_non_postgres_database_url_rejected(self):
        with self.assertRaises(BackupError):
            assert_database_configured("mysql://user:pass@localhost/db")

    def test_malformed_database_url_rejected(self):
        with self.assertRaises(BackupError):
            assert_database_configured("not a url at all")

    def test_environment_label_sanitized(self):
        self.assertEqual(sanitize_environment_label("Production"), "production")
        self.assertEqual(sanitize_environment_label("prod.us-1"), "prod_us_1")
        self.assertEqual(sanitize_environment_label("  ..//  "), "development")

    def test_backup_filename_format_and_sortability(self):
        now = datetime(2026, 9, 7, 14, 30, 0, tzinfo=timezone.utc)
        name = backup_filename("production", now=now)
        self.assertEqual(name, "careerpilot_production_20260907-143000Z.dump")
        self.assertTrue(is_valid_backup_name(name))
        self.assertEqual(parse_backup_name(name), ("production", "20260907-143000Z"))
        later = backup_filename("production", now=datetime(2026, 9, 8, 0, 0, 0, tzinfo=timezone.utc))
        self.assertLess(name, later)  # chronological == lexicographic

    def test_strict_name_validation(self):
        self.assertTrue(is_valid_backup_name("careerpilot_prod_20260907-123456Z.dump"))
        self.assertFalse(is_valid_backup_name("careerpilot_prod_20260907-123456Z.dump.sha256"))
        self.assertFalse(is_valid_backup_name("notes.txt"))
        self.assertFalse(is_valid_backup_name("careerpilot_prod_20260907-123456Z"))
        self.assertFalse(is_valid_backup_name("../careerpilot_prod_20260907-123456Z.dump"))
        self.assertFalse(is_valid_backup_name("careerpilot_prod_20260907-123456Z.dump/.."))
        self.assertIsNone(parse_backup_name(""))

    def test_invalid_backup_path_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaises(BackupError):
                resolve_backup_path(base, "")
            with self.assertRaises(BackupError):
                resolve_backup_path(base, "../escape.dump")
            with self.assertRaises(BackupError):
                resolve_backup_path(base, "..\\escape.dump")
            outside = Path(tempfile.gettempdir()) / "careerpilot_outside_20260907-000000Z.dump"
            with self.assertRaises(BackupError):
                resolve_backup_path(base, str(outside))

    def test_valid_backup_path_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            name = "careerpilot_prod_20260907-000000Z.dump"
            self.assertEqual(resolve_backup_path(base, name), (base / name).resolve())
            self.assertEqual(
                resolve_backup_path(base, f"sub/{name}"), (base / "sub" / name).resolve()
            )


class CommandConstructionTests(unittest.TestCase):
    def test_pg_dump_command(self):
        cmd = bk.pg_dump_command(TEST_DB, Path("/bk/out.dump"))
        self.assertEqual(cmd[0], "pg_dump")
        self.assertIn("--format=custom", cmd)
        self.assertIn("--file", cmd)
        self.assertIn(str(Path("/bk/out.dump")), cmd)
        self.assertIn(TEST_DB, cmd)

    def test_pg_restore_list_command(self):
        cmd = bk.pg_restore_list_command(Path("/bk/x.dump"))
        self.assertEqual(cmd[0], "pg_restore")
        self.assertIn("--list", cmd)

    def test_pg_restore_restore_command_has_destructive_flags(self):
        cmd = bk.pg_restore_restore_command(TEST_DB, Path("/bk/x.dump"))
        self.assertEqual(cmd[0], "pg_restore")
        for flag in ("--exit-on-error", "--clean", "--if-exists", "--no-owner"):
            self.assertIn(flag, cmd)
        self.assertIn(TEST_DB, cmd)

    def test_credential_redaction(self):
        redacted = bk.redact_database_url("postgresql://scott:supersecret@db:5432/cp")
        self.assertNotIn("supersecret", redacted)
        self.assertIn("scott", redacted)
        self.assertIn("cp", redacted)
        self.assertEqual(bk.redact_database_url(""), "")
        preview = bk._command_preview(
            ["pg_dump", "--dbname", "postgresql://u:hunter2@h:5432/d"]
        )
        self.assertNotIn("hunter2", preview)


class BackupLifecycleTests(unittest.TestCase):
    def test_backup_directory_creation_and_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup_dir = Path(tmp) / "nested" / "backups"
            config = _make_config(backup_dir)
            calls = []

            def fake_run(command, timeout=0):
                calls.append(command)
                if command[0] == "pg_dump":
                    out = command[command.index("--file") + 1]
                    Path(out).write_bytes(b"PGDATA")
                return _completed(command=command)

            with mock.patch.object(bk, "_require_program", return_value=None), \
                 mock.patch.object(bk, "run_command", side_effect=fake_run):
                path = bk.create_backup(config)
            self.assertTrue(path.is_file())
            self.assertTrue(backup_dir.is_dir())
            sidecar = path.with_name(checksum_sidecar_name(path.name))
            self.assertTrue(sidecar.is_file())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertIn(digest, sidecar.read_text())
            self.assertEqual(calls[0][0], "pg_dump")

    def test_no_overwrite_of_existing_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            backup_dir = Path(tmp)
            config = _make_config(backup_dir)
            fixed_name = "careerpilot_test_env_20260907-000000Z.dump"

            def fake_dump_run(command, timeout=0):
                if command[0] == "pg_dump":
                    Path(command[command.index("--file") + 1]).write_bytes(b"X")
                return _completed(command=command)

            with mock.patch.object(bk, "backup_filename", return_value=fixed_name), \
                 mock.patch.object(bk, "_require_program", return_value=None), \
                 mock.patch.object(bk, "run_command", side_effect=fake_dump_run):
                bk.create_backup(config)  # first create succeeds
                run_calls = []
                with mock.patch.object(bk, "run_command", side_effect=lambda c, timeout=0: run_calls.append(c) or _completed(command=c)):
                    with self.assertRaises(BackupError):
                        bk.create_backup(config)  # second must refuse to overwrite
            self.assertEqual(run_calls, [])  # pg_dump never invoked again


class VerificationTests(unittest.TestCase):
    def test_verify_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = _make_config(Path(tmp))
            result = bk.verify_backup(config, "careerpilot_ghost_20260907-000000Z.dump")
            self.assertFalse(result["ok"])
            self.assertTrue(any("does not exist" in e for e in result["errors"]))

    def test_verify_invalid_name_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "notes.txt").write_text("hello")
            config = _make_config(Path(tmp))
            result = bk.verify_backup(config, "notes.txt", require_list=False)
            self.assertFalse(result["ok"])
            self.assertTrue(any("backup convention" in e for e in result["errors"]))

    def test_verify_empty_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_dump(Path(tmp), "careerpilot_prod_20260907-000000Z.dump", data=b"")
            config = _make_config(Path(tmp))
            result = bk.verify_backup(config, "careerpilot_prod_20260907-000000Z.dump", require_list=False)
            self.assertFalse(result["ok"])
            self.assertTrue(any("empty" in e for e in result["errors"]))

    def test_verify_ok_with_checksum_and_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_dump(Path(tmp), "careerpilot_prod_20260907-000000Z.dump")
            config = _make_config(Path(tmp))

            def fake_run(command, timeout=0):
                self.assertEqual(command[0], "pg_restore")
                return _completed(stdout="; catalog entry\n", command=command)

            with mock.patch.object(bk, "_require_program", return_value=None), \
                 mock.patch.object(bk, "run_command", side_effect=fake_run):
                result = bk.verify_backup(config, "careerpilot_prod_20260907-000000Z.dump")
            self.assertTrue(result["ok"])
            self.assertEqual(result["checksum"]["ok"], True)
            self.assertEqual(result["size"], len(b"ARCHIVEDATA\n"))

    def test_verify_checksum_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            name = "careerpilot_prod_20260907-000000Z.dump"
            directory.joinpath(name).write_bytes(b"REALDATA")
            directory.joinpath(checksum_sidecar_name(name)).write_text(
                "0" * 64 + f"  {name}\n", encoding="utf-8"
            )
            config = _make_config(directory)
            result = bk.verify_backup(config, name, require_list=False)
            self.assertFalse(result["ok"])
            self.assertTrue(any("checksum mismatch" in e for e in result["errors"]))

    def test_verify_archive_inspection_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_dump(Path(tmp), "careerpilot_prod_20260907-000000Z.dump")
            config = _make_config(Path(tmp))

            def fake_run(command, timeout=0):
                return _completed(returncode=1, stderr="could not open input", command=command)

            with mock.patch.object(bk, "_require_program", return_value=None), \
                 mock.patch.object(bk, "run_command", side_effect=fake_run):
                result = bk.verify_backup(config, "careerpilot_prod_20260907-000000Z.dump")
            self.assertFalse(result["ok"])
            self.assertTrue(any("inspect" in e for e in result["errors"]))


class RestoreSafetyTests(unittest.TestCase):
    def _valid_dump(self, directory):
        _write_dump(directory, "careerpilot_prod_20260907-000000Z.dump")
        return _make_config(directory)

    def test_restore_refused_without_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._valid_dump(Path(tmp))
            ran = []
            with mock.patch.object(bk, "_require_program", return_value=None), \
                 mock.patch.object(
                     bk, "run_command",
                     side_effect=lambda command, timeout=0: ran.append(command) or _completed(command=command),
                 ):
                with self.assertRaises(RestoreAborted):
                    bk.restore_backup(
                        config, "careerpilot_prod_20260907-000000Z.dump", confirm=False
                    )
            self.assertEqual(ran, [])  # pg_restore never executed

    def test_restore_refused_even_with_create_target_without_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._valid_dump(Path(tmp))
            with mock.patch.object(bk, "create_target_database") as create_target, \
                 self.assertRaises(RestoreAborted):
                bk.restore_backup(
                    config,
                    "careerpilot_prod_20260907-000000Z.dump",
                    confirm=False,
                    create_target=True,
                )
            create_target.assert_not_called()

    def test_missing_dump_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._valid_dump(Path(tmp))
            with self.assertRaises(BackupError):
                bk.restore_backup(config, "careerpilot_p_20260908-000000Z.dump", confirm=True)

    def test_unverified_archive_rejected_with_verify_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            name = "careerpilot_prod_20260907-000000Z.dump"
            directory.joinpath(name).write_bytes(b"")  # empty -> unverifiable
            directory.joinpath(checksum_sidecar_name(name)).write_text(
                "0" * 64 + f"  {name}\n", encoding="utf-8"
            )
            config = _make_config(directory)
            with mock.patch.object(bk, "_require_program", return_value=None), \
                 mock.patch.object(bk, "run_command", return_value=_completed(stdout="catalog\n")), \
                 self.assertRaises(BackupError):
                bk.restore_backup(
                    config, name, confirm=True, target_database_url=TEST_DB, verify_first=True
                )

    def test_restore_with_confirmation_executes_pg_restore_to_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._valid_dump(Path(tmp))
            calls = []

            def fake_run(command, timeout=0):
                calls.append(command)
                return _completed(command=command)

            with mock.patch.object(bk, "_require_program", return_value=None), \
                 mock.patch.object(bk, "run_command", side_effect=fake_run):
                result = bk.restore_backup(
                    config, "careerpilot_prod_20260907-000000Z.dump", confirm=True
                )
            self.assertTrue(result["restored"])
            restore_cmd = calls[0]
            self.assertEqual(restore_cmd[0], "pg_restore")
            self.assertIn("--clean", restore_cmd)
            self.assertIn("--if-exists", restore_cmd)
            self.assertIn(TEST_DB, restore_cmd)
            self.assertEqual(result["target_database"], "cp_test")

    def test_restore_failure_message_does_not_leak_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self._valid_dump(Path(tmp))

            def failing_run(command, timeout=0):
                return _completed(returncode=1, stderr="password authentication failed", command=command)

            with mock.patch.object(bk, "_require_program", return_value=None), \
                 mock.patch.object(bk, "run_command", side_effect=failing_run), \
                 self.assertRaises(BackupError) as ctx:
                bk.restore_backup(
                    config, "careerpilot_prod_20260907-000000Z.dump", confirm=True
                )
            message = str(ctx.exception)
            self.assertIn("pg_restore failed", message)
            self.assertNotIn("user:pass@", message)

    def test_create_target_database_commands(self):
        calls = []

        def fake_run(command, timeout=0):
            calls.append(command)
            if len(calls) == 1:
                return _completed(stdout="", command=command)  # not present
            return _completed(stdout="CREATE DATABASE", command=command)

        with mock.patch.object(bk, "_require_program", return_value=None), \
             mock.patch.object(bk, "run_command", side_effect=fake_run):
            created = bk.create_target_database("postgresql://u:p@localhost:5432/cp_restore_t1")
        self.assertTrue(created)
        self.assertEqual(calls[0][0], "psql")
        self.assertIn("SELECT 1 FROM pg_database", " ".join(calls[0]))
        self.assertIn('CREATE DATABASE "cp_restore_t1"', " ".join(calls[1]))
        # the argv necessarily carries connection credentials for psql; what
        # must never leak is OUR human-facing output.
        preview = bk._command_preview(
            ["psql", "--dbname", "postgresql://u:p@localhost:5432/postgres", "--command", "SELECT 1"]
        )
        self.assertNotIn("u:p@", preview)
        self.assertIn("u:***", preview)


class RetentionTests(unittest.TestCase):
    def test_retention_keeps_newest_and_removes_oldest(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            names = _five_names()
            for name in names:
                _write_dump(directory, name)
            config = _make_config(directory, retention_count=2)
            removed, sidecars = prune_backups(config)
            self.assertEqual(len(removed), 3)
            self.assertEqual(len(sidecars), 3)
            remaining = sorted(p.name for p in directory.glob("*.dump"))
            self.assertEqual(remaining, sorted(names[-2:]))
            self.assertEqual(len(list(directory.glob("*.sha256"))), 2)

    def test_newest_backup_never_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            names = _five_names()
            for name in names:
                _write_dump(directory, name)
            config = _make_config(directory, retention_count=1)
            removed, _ = prune_backups(config)
            self.assertEqual(len(removed), 4)
            remaining = [p.name for p in directory.glob("*.dump")]
            self.assertEqual(remaining, [names[-1]])

    def test_retention_invalid_count_rejected_and_never_deletes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in _five_names():
                _write_dump(directory, name)
            config = _make_config(directory, retention_count=30)
            with self.assertRaises(BackupError):
                prune_backups(config, keep_count=0)
            self.assertEqual(len(list(directory.glob("*.dump"))), 5)

    def test_retention_ignores_unrelated_files_and_subdirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in _five_names():
                _write_dump(directory, name)
            (directory / "notes.txt").write_text("keep me")
            subdir = directory / "sub"
            subdir.mkdir()
            _write_dump(subdir, "careerpilot_nested_20260907-000000Z.dump")
            config = _make_config(directory, retention_count=1)
            removed, _ = prune_backups(config)
            self.assertNotIn("notes.txt", [p.name for p in removed])
            self.assertTrue((directory / "notes.txt").exists())
            self.assertTrue((subdir / "careerpilot_nested_20260907-000000Z.dump").exists())

    def test_dry_run_removes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in _five_names():
                _write_dump(directory, name)
            config = _make_config(directory, retention_count=2)
            removed, sidecars = prune_backups(config, dry_run=True)
            self.assertEqual(len(removed), 3)
            self.assertGreater(len(sidecars), 0)
            self.assertEqual(len(list(directory.glob("*.dump"))), 5)

    def test_list_backups_only_valid_names_ordered_newest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            names = _five_names()
            for name in names:
                _write_dump(directory, name)
            (directory / "notes.txt").write_text("nope")
            backups = list_backups(directory)
            self.assertEqual(len(backups), 5)
            self.assertEqual(backups[0].name, names[-1])
            self.assertEqual(backups[-1].name, names[0])


class CliTests(unittest.TestCase):
    def test_restore_without_confirm_returns_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write_dump(directory, "careerpilot_prod_20260907-000000Z.dump")
            code = bk.main(
                ["--backup-dir", str(directory), "restore",
                 "--dump", "careerpilot_prod_20260907-000000Z.dump"]
            )
            self.assertEqual(code, 2)

    def test_verify_missing_returns_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = bk.main(
                ["--backup-dir", str(tmp), "verify",
                 "--dump", "careerpilot_ghost_20260907-000000Z.dump"]
            )
            self.assertEqual(code, 1)

    def test_list_empty_returns_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = bk.main(["--backup-dir", str(tmp), "list"])
            self.assertEqual(code, 0)

    def test_unknown_command_errors(self):
        with self.assertRaises(SystemExit) as ctx:
            bk.main(["--backup-dir", ".", "frobnicate"])
        self.assertEqual(ctx.exception.code, 2)


if __name__ == "__main__":
    unittest.main()