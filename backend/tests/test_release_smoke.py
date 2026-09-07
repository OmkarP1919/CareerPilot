"""Tests for the 5E.13 release smoke harness (scripts.release_smoke)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import release_smoke as rs

BACKEND_DIR = Path(__file__).resolve().parent.parent
EXPECTED_LETTERS = [*"ABCDEFGHIJKLMN", "PG.1", "PG.2"]


class RegistryTests(unittest.TestCase):
    def test_registry_covers_every_letter_once(self):
        letters = [letter for letter, _title, _fn in rs.CHECKS]
        self.assertEqual(letters, EXPECTED_LETTERS)
        self.assertEqual(len(letters), len(set(letters)))

    def test_pg_checks_are_last_and_gated_functions(self):
        self.assertEqual(rs.CHECKS[-1][0], "PG.2")
        self.assertIs(rs.check_pg_readiness, rs.CHECKS[-2][2])
        self.assertIs(rs.check_pg_backup, rs.CHECKS[-1][2])

    def test_protected_files_mapping_matches_docs_contract(self):
        self.assertEqual(set(rs.PROTECTED_FILES_AT_HEAD), {
            "backend/app/services/resume_parser.py",
            "backend/tests/test_resume_parser.py",
            "frontend/src/pages/ResumesPage.jsx",
        })


class DefaultRunTests(unittest.TestCase):
    def test_default_run_has_no_failures_and_gates_pg(self):
        results = rs.run_checks(rs.Options())
        failed = [r for r in results if r.status == rs.FAIL]
        self.assertEqual(failed, [])
        self.assertTrue(rs.gate_passed(results))
        pg = {r.letter: r.status for r in results if r.letter.startswith("PG.")}
        self.assertEqual(pg, {"PG.1": rs.SKIP, "PG.2": rs.SKIP})

    def test_run_as_module_passes_and_exits_zero(self):
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.release_smoke"],
            cwd=str(BACKEND_DIR), capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("RELEASE GATE: PASS", proc.stdout)

    def test_json_output_parses(self):
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.release_smoke", "--json"],
            cwd=str(BACKEND_DIR), capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["gate"], "PASS")
        self.assertEqual(len(payload["checks"]), len(rs.CHECKS))
        for check in payload["checks"]:
            self.assertIn(check["status"], {rs.PASS, rs.SKIP, rs.FAIL})

    def test_unknown_flag_is_usage_error_exit_two(self):
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.release_smoke", "--bogus"],
            cwd=str(BACKEND_DIR), capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage:", proc.stderr)


class HarnessEngineTests(unittest.TestCase):
    def setUp(self):
        def _boom(_opts):
            raise ValueError("nope")

        self.ok = ("ok", "ok title", lambda _opts: (rs.PASS, "fine"))
        self.skip_now = ("skip", "skip title", lambda _opts: (rs.SKIP, "why not"))
        self.boom = ("boom", "boom title", _boom)

    def test_gate_passed_allows_skips(self):
        self.assertTrue(rs.gate_passed([
            rs.SmokeResult("A", "a", rs.PASS, ""),
            rs.SmokeResult("B", "b", rs.SKIP, "reason"),
        ]))

    def test_gate_passed_rejects_any_fail(self):
        self.assertFalse(rs.gate_passed([
            rs.SmokeResult("A", "a", rs.PASS, ""),
            rs.SmokeResult("B", "b", rs.FAIL, "broken"),
            rs.SmokeResult("C", "c", rs.SKIP, "why not"),
        ]))

    def test_exception_inside_check_is_fail(self):
        status, message = rs.execute_check(self.boom[2], rs.Options())
        self.assertEqual(status, rs.FAIL)
        self.assertTrue(message.startswith("raised ValueError"))

    def test_fail_fast_stops_after_first_failure(self):
        results = rs.run_checks(rs.Options(fail_fast=True), [self.ok, self.boom, self.ok])
        self.assertEqual([r.letter for r in results], ["ok", "boom"])
        self.assertFalse(rs.gate_passed(results))

    def test_without_fail_fast_all_checks_run(self):
        results = rs.run_checks(rs.Options(), [self.ok, self.boom, self.ok])
        self.assertEqual([r.letter for r in results], ["ok", "boom", "ok"])

    def test_report_shape(self):
        results = rs.run_checks(rs.Options(), [self.ok, self.skip_now])
        report = rs.format_report(results)
        self.assertIn("CAREERPILOT RELEASE SMOKE", report)
        self.assertIn("RELEASE GATE: PASS", report)
        self.assertIn("[ok]", report)
        self.assertIn("1 passed, 1 skipped, 0 failed", report)

    def test_format_json_shape(self):
        results = rs.run_checks(rs.Options(), [self.ok, self.skip_now])
        payload = json.loads(rs.format_json(results))
        self.assertEqual(payload["gate"], "PASS")
        self.assertEqual([c["status"] for c in payload["checks"]], [rs.PASS, rs.SKIP])


class PgGatingTests(unittest.TestCase):
    def test_disabled_without_flag(self):
        self.assertEqual(rs.execute_check(rs.check_pg_readiness, rs.Options())[0], rs.SKIP)
        self.assertEqual(rs.execute_check(rs.check_pg_backup, rs.Options())[0], rs.SKIP)

    def test_disabled_when_url_missing(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("POSTGRES_TEST_DATABASE_URL", None)
            status, message = rs.execute_check(rs.check_pg_readiness, rs.Options(pg=True))
            self.assertEqual(status, rs.SKIP)
            self.assertIn("pass --pg", message)
            self.assertEqual(rs.execute_check(rs.check_pg_backup, rs.Options(pg=True))[0], rs.SKIP)

    def test_backup_skips_when_pg_dump_absent(self):
        with mock.patch.dict(os.environ, {"POSTGRES_TEST_DATABASE_URL": "postgresql://u:p@localhost/db"}, clear=False):
            with mock.patch.object(rs.shutil, "which", return_value=None):
                status, message = rs.execute_check(rs.check_pg_backup, rs.Options(pg=True))
        self.assertEqual(status, rs.SKIP)
        self.assertIn("pg_dump", message)

    def test_skip_never_blocks_the_gate(self):
        results = rs.run_checks(rs.Options(), [
            ("A", "a", lambda _opts: (rs.PASS, "ok")),
            ("PG.1", "pg", rs.check_pg_readiness),
        ])
        self.assertTrue(rs.gate_passed(results))


class RouteDiscoveryTests(unittest.TestCase):
    def test_collect_paths_sees_mounted_prefixes_and_root(self):
        app = rs._build_full_app()
        paths = rs._collect_paths(app)
        for prefix in ("/", "/applications", "/healthz", "/jobs/discovery", "/auth"):
            self.assertTrue(
                any(p.startswith(prefix) for p in paths),
                f"no mounted route starts with {prefix!r}",
            )


class CheckMFrontendContractTests(unittest.TestCase):
    """Check M reads the real repo; exercise it against an isolated temp repo.

    The real static contract is validated on every run, and any static problem
    must return FAIL even when --frontend-build is absent (5E.13 audit, HIGH).
    """

    HEALTHY_PKG = {
        "scripts": {
            "test": "node tests/resume-contract.mjs && node tests/api-deploy-contract.mjs",
            "build": "vite build",
            "lint": "oxlint .",
        }
    }

    HEALTHY_CI = (
        "jobs:\n"
        "  test:\n"
        "    - run: npm test\n"
        "    - run: npm run build\n"
        "    - run: npm run lint\n"
        "    - run: echo $VITE_API_BASE_URL\n"
    )

    def _make_repo(self, *, healthy_vite=True, healthy_build_script=True):
        root = Path(tempfile.mkdtemp(prefix="cp_smoke_checkm_"))
        frontend = root / "frontend"
        (frontend / "scripts").mkdir(parents=True)
        (root / ".github" / "workflows").mkdir(parents=True)

        pkg = json.loads(json.dumps(self.HEALTHY_PKG))
        if not healthy_build_script:
            pkg["scripts"]["build"] = "tsc --noEmit"
        (frontend / "package.json").write_text(
            json.dumps(pkg), encoding="utf-8"
        )
        (frontend / "scripts" / "validateEnv.mjs").write_text(
            "export function validateProductionEnv(){}\n", encoding="utf-8"
        )
        (frontend / "vite.config.js").write_text(
            "import { validateProductionEnv } from './scripts/validateEnv.mjs';\n"
            if healthy_vite
            else "export default {}\n",
            encoding="utf-8",
        )
        (root / ".github" / "workflows" / "ci.yml").write_text(
            self.HEALTHY_CI, encoding="utf-8"
        )
        return root

    def _cleanup(self, root):
        shutil.rmtree(root, ignore_errors=True)

    def test_healthy_static_contract_passes_without_build_flag(self):
        root = self._make_repo()
        try:
            with mock.patch.object(rs, "REPO_ROOT", root):
                status, message = rs.execute_check(rs.check_m, rs.Options())
            self.assertEqual(status, rs.PASS, message)
            self.assertIn("static contract OK", message)
        finally:
            self._cleanup(root)

    def test_broken_static_contract_fails_without_build_flag(self):
        root = self._make_repo(healthy_vite=False)
        try:
            with mock.patch.object(rs, "REPO_ROOT", root):
                status, message = rs.execute_check(rs.check_m, rs.Options())
            self.assertEqual(status, rs.FAIL, message)
            self.assertIn("validateProductionEnv", message)
        finally:
            self._cleanup(root)

    def test_broken_build_script_fails_without_build_flag(self):
        root = self._make_repo(healthy_build_script=False)
        try:
            with mock.patch.object(rs, "REPO_ROOT", root):
                status, message = rs.execute_check(rs.check_m, rs.Options())
            self.assertEqual(status, rs.FAIL, message)
            self.assertIn("scripts.build", message)
        finally:
            self._cleanup(root)

    def test_missing_package_json_fails_without_build_flag(self):
        root = self._make_repo()
        try:
            (root / "frontend" / "package.json").unlink()
            with mock.patch.object(rs, "REPO_ROOT", root):
                status, message = rs.execute_check(rs.check_m, rs.Options())
            self.assertEqual(status, rs.FAIL, message)
            self.assertIn("package.json missing", message)
        finally:
            self._cleanup(root)

    def test_broken_contract_fails_even_with_build_flag(self):
        root = self._make_repo(healthy_vite=False)
        try:
            with mock.patch.object(rs, "REPO_ROOT", root):
                status, message = rs.execute_check(rs.check_m, rs.Options(frontend_build=True))
            self.assertEqual(status, rs.FAIL, message)
            self.assertIn("validateProductionEnv", message)
        finally:
            self._cleanup(root)

    def test_build_flag_still_runs_npm_build_when_static_ok(self):
        root = self._make_repo()
        try:
            with mock.patch.object(rs, "REPO_ROOT", root):
                with mock.patch.object(rs.subprocess, "run") as mocked:
                    mocked.return_value = mock.Mock(returncode=0, stdout="built", stderr="")
                    status, message = rs.execute_check(rs.check_m, rs.Options(frontend_build=True))
            self.assertEqual(status, rs.PASS, message)
            self.assertIn("build succeeded", message)
            invoked = mocked.call_args
            self.assertEqual(invoked.args[0], ["npm", "run", "build"])
            self.assertEqual(invoked.kwargs["cwd"], str(root / "frontend"))
        finally:
            self._cleanup(root)

    def test_build_flag_skips_when_npm_unavailable(self):
        root = self._make_repo()
        try:
            with mock.patch.object(rs, "REPO_ROOT", root):
                with mock.patch.object(rs.subprocess, "run", side_effect=FileNotFoundError):
                    status, message = rs.execute_check(rs.check_m, rs.Options(frontend_build=True))
            self.assertEqual(status, rs.SKIP, message)
            self.assertIn("npm not available", message)
        finally:
            self._cleanup(root)

    def test_build_flag_fails_when_npm_build_fails(self):
        root = self._make_repo()
        try:
            with mock.patch.object(rs, "REPO_ROOT", root):
                with mock.patch.object(rs.subprocess, "run") as mocked:
                    mocked.return_value = mock.Mock(returncode=1, stdout="err out", stderr="oops")
                    status, message = rs.execute_check(rs.check_m, rs.Options(frontend_build=True))
            self.assertEqual(status, rs.FAIL, message)
            self.assertIn("npm run build failed", message)
        finally:
            self._cleanup(root)


if __name__ == "__main__":
    unittest.main()