#!/usr/bin/env python3
"""CI secret/credential-shaped content scanner for CareerPilot (Phase 5E.12).

Runs in the `repository-security` job of .github/workflows/ci.yml and locally:

    python scripts/scan_repo_secrets.py [path ...]

With no arguments it walks the current directory, skipping generated and
git-ignored content (node_modules, dist, __pycache__, venvs, uploads,
backups, .env files, ...). With explicit paths it scans only those.

Design notes (see docs/ci_cd.md):

  - The scanner is deliberately narrow: it flags *credential-shaped* content
    (private key blocks, API-key patterns, service-account JSON, remote
    database URLs that embed a password), never every key-shaped string.
    Documented placeholders such as
    ``postgresql://user:password@localhost:5432/careerpilot`` are not flagged.
  - Files under backend/tests and frontend/tests are exempt from the remote
    database-URL rule only: those suites intentionally contain user:pass
    fixture connection strings. All other rules still apply to test files.
  - Content is never sent anywhere. The scanner only prints path:line:rule
    (never the matched value) and exits non-zero when anything is found.

Exit codes: 0 = clean, 1 = one or more credential-shaped findings.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys

# Directories never scanned, in any invocation mode.
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "coverage",
        "dist",
        ".next",
        "env",
        "ENV",
        "htmlcov",
        "node_modules",
        "uploads",
        "backups",
        ".idea",
        ".vscode",
    }
)

# Extensions never scanned (binary / generated files).
EXCLUDED_EXTENSIONS = frozenset(
    {
        ".db",
        ".dll",
        ".dump",
        ".eot",
        ".exe",
        ".gif",
        ".gz",
        ".ico",
        ".jpeg",
        ".jpg",
        ".p12",
        ".pdf",
        ".pfx",
        ".png",
        ".pyc",
        ".pyo",
        ".so",
        ".sqlite",
        ".sqlite3",
        ".ttf",
        ".woff",
        ".woff2",
        ".zip",
    }
)

DB_URL_FAMILIES = (
    "postgres",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "rediss",
    "mssql",
)

RULES = (
    (
        "private-key-block",
        re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----"),
    ),
    (
        "openai-api-key",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}\b"),
    ),
    (
        "aws-access-key-id",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "github-personal-access-token",
        re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    ),
    (
        "github-fine-grained-token",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    ),
    (
        "remote-database-url-with-password",
        re.compile(
            r"(?i)(?:%s)://[^@/:\s]+:[^@/\s]+@"
            r"(?!localhost|127\.0\.0\.1|\[::1\]|::1)" % "|".join(DB_URL_FAMILIES)
        ),
    ),
)

# Google service-account JSON: both markers must appear in the same file.
SERVICE_ACCOUNT_TYPE = re.compile(r'"type"\s*:\s*"service_account"')
SERVICE_ACCOUNT_PRIVATE_KEY = re.compile(r'"private_key"\s*:')
SERVICE_ACCOUNT_RULE_NAME = "google-service-account-json"


def _is_binary(path):
    try:
        with open(path, "rb") as handle:
            return b"\x00" in handle.read(2048)
    except OSError:
        return True


def _should_exclude_dir(name):
    return name in EXCLUDED_DIRS


def _should_exclude_file(name):
    return os.path.splitext(name)[1].lower() in EXCLUDED_EXTENSIONS


def _git_ls_files():
    """Lines (as str) for all files git would commit from the current dir.

    Combines tracked files (`git ls-files -z`) with untracked non-ignored
    files (`git ls-files --others --exclude-standard -z`). This is exactly
    the set a commit could contain, so ignored secrets (a real .env, a
    service-account JSON) are skipped the same way a commit would skip them.
    """
    files = []
    for cmd in (
        ("git", "ls-files", "-z"),
        ("git", "ls-files", "--others", "--exclude-standard", "-z"),
    ):
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError("git ls-files failed; run from the repo root")
        files.extend(proc.stdout.split(b"\x00"))
    return sorted(
        {f.decode("utf-8", errors="replace") for f in files if f}
    )


def collect_files(roots):
    """Return the list of paths to scan.

    With no positional paths this returns the repository *commit set* (tracked
    plus untracked-and-not-ignored). With explicit paths it walks only those
    files/directories (generated directories are skipped).
    """
    if not roots:
        return _git_ls_files()

    out = []
    for item in roots:
        item = item.rstrip("/\\")
        if os.path.isfile(item):
            out.append(item)
        elif os.path.isdir(item):
            for dirpath, dirnames, filenames in os.walk(item):
                dirnames[:] = [
                    d for d in dirnames if not _should_exclude_dir(d)
                ]
                for filename in filenames:
                    if _should_exclude_file(filename):
                        continue
                    out.append(
                        os.path.join(dirpath, filename).replace(os.sep, "/")
                    )
        else:
            raise SystemExit(f"no such path: {item}")
    return sorted(set(out))


def scan_file(path):
    """Return a list of (line_number, rule_name) findings for a file."""
    findings = []
    saw_service_account_type = False
    saw_service_account_private_key = False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        return findings

    for index, line in enumerate(lines, start=1):
        for rule_name, pattern in RULES:
            if rule_name.startswith("remote-database-url") and (
                fnmatch.fnmatch(path.replace("\\", "/"), "backend/tests/*")
                or fnmatch.fnmatch(path.replace("\\", "/"), "frontend/tests/*")
            ):
                continue
            if pattern.search(line):
                findings.append((index, rule_name))
        if SERVICE_ACCOUNT_TYPE.search(line):
            saw_service_account_type = True
        if SERVICE_ACCOUNT_PRIVATE_KEY.search(line):
            saw_service_account_private_key = True

    if saw_service_account_type and saw_service_account_private_key:
        findings.append((1, SERVICE_ACCOUNT_RULE_NAME))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Scan a repository for credential-shaped content. "
            "Prints path:line:rule findings only (never matched values)."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files/directories to scan (default: whole repo, skipping ignored content)",
    )
    args = parser.parse_args(argv)

    files = list(collect_files(args.paths))

    all_findings = []
    for path in files:
        if _is_binary(path):
            continue
        all_findings += [(path, line, rule) for line, rule in scan_file(path)]

    if all_findings:
        for path, line, rule in sorted(all_findings):
            print(f"FOUND {path}:{line}: {rule}")
        print(
            f"\n{len(all_findings)} credential-shaped finding(s) detected. "
            "Review each one; commit only documented placeholders."
        )
        return 1

    print(f"OK: no credential-shaped content in {len(files)} scanned file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())