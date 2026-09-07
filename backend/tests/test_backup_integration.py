"""Phase 5E.11 PostgreSQL integration test — backup → verify → restore.

Gated on ``POSTGRES_TEST_DATABASE_URL`` (existing suite convention): the whole
class SKIPS when it is unset, unreachable, or when the PostgreSQL client tools
(pg_dump / pg_restore / psql) are not installed. It NEVER touches the
application's normal ``DATABASE_URL``.

Round-trip exercised:

1. create a tiny known table (``cp_backup_verify``) and seed two rows in the
   test database,
2. pg_dump it (custom format) into a temp backup directory + checksum sidecar,
3. ``verify`` the archive (existence, size, checksum, ``pg_restore --list``),
4. DELETE the seeded rows from the *source* test database,
5. restore the archive into a NEW disposable target database (created on the
   same server via ``--create-target`` semantics) — never into the source,
6. assert the known rows exist again in the disposable target,
7. drop the disposable target and the throwaway table afterwards.

If the environment lacks privileges to CREATE DATABASE, the test reports the
round-trip as SKIPPED for that reason (it must never be reported as a pass).
"""

import os
import secrets
import shutil
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.ops import backup as bk
from app.ops.config import BackupConfig

POSTGRES_TEST_DATABASE_URL = os.environ.get("POSTGRES_TEST_DATABASE_URL")


@unittest.skipUnless(
    POSTGRES_TEST_DATABASE_URL,
    "POSTGRES_TEST_DATABASE_URL is not set",
)
class TestPostgresBackupRecoveryRoundTrip(unittest.TestCase):
    TABLE = "cp_backup_verify"
    SEED = [("alpha", "1"), ("beta", "2")]

    @classmethod
    def setUpClass(cls):
        cls.url = POSTGRES_TEST_DATABASE_URL
        parsed = make_url(cls.url)
        if parsed.get_backend_name() not in ("postgresql", "postgres"):
            raise unittest.SkipTest("POSTGRES_TEST_DATABASE_URL is not PostgreSQL")
        for tool in ("pg_dump", "pg_restore", "psql"):
            if shutil.which(tool) is None:
                raise unittest.SkipTest(f"PostgreSQL client tool not installed: {tool}")
        cls.engine = create_engine(cls.url, pool_pre_ping=True)
        try:
            cls.engine.connect().close()
        except Exception as exc:
            cls.engine.dispose()
            raise unittest.SkipTest(
                f"PostgreSQL test database unreachable ({exc.__class__.__name__}): {exc}"
            )
        with cls.engine.begin() as conn:
            conn.execute(text(f"CREATE TABLE IF NOT EXISTS {cls.TABLE} (item TEXT PRIMARY KEY, value TEXT)"))
            conn.execute(text(f"TRUNCATE {cls.TABLE}"))
            conn.execute(
                text(f"INSERT INTO {cls.TABLE} (item, value) VALUES (:item, :value)"),
                [{"item": item, "value": value} for item, value in cls.SEED],
            )

    @classmethod
    def tearDownClass(cls):
        try:
            with cls.engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {cls.TABLE}"))
        finally:
            cls.engine.dispose()

    def _disposable_target_url(self) -> str:
        name = f"cp_restore_{secrets.token_hex(4)}"
        return make_url(self.url).set(database=name).render_as_string(hide_password=False)

    def _drop_disposable_target(self, target_url: str) -> None:
        target = make_url(target_url)
        maintenance = target.set(database="postgres").render_as_string(hide_password=False)
        self._psql_quiet(maintenance, f'DROP DATABASE IF EXISTS "{target.database.replace(chr(34), chr(34) * 2)}"')

    @staticmethod
    def _psql_quiet(db_url: str, sql: str) -> None:
        bk.run_command(
            ["psql", "--tuples-only", "--no-align", "--quiet", "--dbname", db_url, "--command", sql]
        )

    def test_backup_verify_restore_round_trip(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            backup_dir = Path(tmp)
            config = BackupConfig(
                database_url=self.url,
                backup_dir=str(backup_dir),
                retention_count=5,
                environment="br_integration",
            )

            # 1-2. create + sidecar
            dump_path = bk.create_backup(config)
            self.assertTrue(dump_path.is_file(), "pg_dump archive not created")
            sidecar = dump_path.with_name(bk.checksum_sidecar_name(dump_path.name))
            self.assertTrue(sidecar.is_file(), "checksum sidecar not created")

            # 3. verify (size + checksum + pg_restore --list)
            verified = bk.verify_backup(config, str(dump_path), require_list=True)
            self.assertTrue(verified["ok"], "; ".join(verified["errors"]))
            self.assertEqual(verified["checksum"]["ok"], True)

            # 4. mutate the source database (remove the seeded rows)
            with self.engine.begin() as conn:
                conn.execute(text(f"TRUNCATE {self.TABLE}"))
            with self.engine.begin() as conn:
                remaining = conn.execute(text(f"SELECT count(*) FROM {self.TABLE}")).scalar()
            self.assertEqual(remaining, 0, "source mutation did not apply")

            # 5. restore into a disposable target (never the source)
            target_url = self._disposable_target_url()
            try:
                restored = bk.restore_backup(
                    config,
                    str(dump_path),
                    confirm=True,
                    target_database_url=target_url,
                    create_target=True,
                )
                self.assertTrue(restored["restored"])
                self.assertEqual(restored["target_database"], make_url(target_url).database)

                # 6. known data is back in the disposable target
                target_engine = create_engine(target_url, pool_pre_ping=True)
                try:
                    with target_engine.connect() as conn:
                        rows = conn.execute(
                            text(f"SELECT item FROM {self.TABLE} ORDER BY item")
                        ).scalars().all()
                    self.assertEqual(rows, ["alpha", "beta"])
                finally:
                    target_engine.dispose()

                # source DB remains mutated (restore went to the disposable target)
                with self.engine.begin() as conn:
                    source_count = conn.execute(text(f"SELECT count(*) FROM {self.TABLE}")).scalar()
                self.assertEqual(source_count, 0, "restore must not mutate the source database")
            except bk.BackupError as exc:
                if "could not create target database" in str(exc):
                    self.skipTest(
                        "could not CREATE DATABASE on the test server "
                        f"(insufficient privileges?): {exc}"
                    )
                raise
            finally:
                self._drop_disposable_target(target_url)


if __name__ == "__main__":
    unittest.main()