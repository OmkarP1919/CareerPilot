# CareerPilot CI/CD

Phase 5E.12 lays the CI foundation for the repository.

- **Status:** validation only. CI never deploys the application, publishes
  artifacts, or connects to production databases/credentials.
- **Trigger policy:** CI runs on every pull request targeting `main` and on
  every push to `main`. There are no scheduled jobs, no deployment triggers,
  and no release automation (release smoke testing arrives in phase 5E.13).

## 1. What CI checks

| Job               | Checks                                                                                                  |
| ----------------- | ------------------------------------------------------------------------------------------------------- |
| `backend`         | Python 3.12 install, pinned `requirements.txt`, `compileall` syntax check, full `unittest` suite         |
| `frontend`        | Node 22 LTS, `npm ci`, contract tests (`npm test`), production build (`npm run build`), lint (`npm run lint`) |
| `repository-security` | `git diff --check` over the change range, protected-file regression guard, credential-shaped content scan |

All three jobs run in parallel and are independent. A job fails when any of its
checks fail; failures are never masked with `|| true`.

Workflow file: `.github/workflows/ci.yml`.

## 2. How to reproduce CI locally

Run these commands from the repository root (`D:\CareerPilot`). They are the
same commands the workflow runs.

Backend (from `backend/`):

```powershell
python -m pip install -r requirements.txt
python -m compileall -q app
python -m unittest discover -s tests -p "test_*.py"
```

Frontend (from `frontend/`):

```powershell
npm ci
npm test
$env:VITE_API_BASE_URL = "https://api.careerpilot.app"   # required by npm run build
npm run build
npm run lint
```

Repository:

```powershell
git diff --check
```

Local parity is intentionally a documented command sequence - there is no
separate local CI framework.

## 3. Supported versions

### Python: 3.12

The repository does not declare a Python version anywhere
(no `.python-version`, `pyproject.toml`, or equivalent). The code requires
Python >= 3.10 (union-pipe typing `X | None` is used throughout) and uses no
3.11+ or 3.12-only features. CI targets **Python 3.12** as the most
conservative widely-available version that is still in security support and that
every pinned dependency ships wheels for. The local developer interpreter may
differ (e.g. 3.14); the CI baseline is 3.12.

### Node: 22 LTS

`package.json` declares no `engines`. The pinned toolchain sets the floor:
`vite@8.2.2` requires `^20.19.0 || >=22.12.0` and the lockfile markers require
`>=20.0.0`. CI targets **Node 22 LTS** (22.x, the latest 22 line satisfies
`>=22.12.0`). Dependencies were not upgraded to add CI.

## 4. Dependency reproducibility

- **Backend:** `backend/requirements.txt` is fully pinned with `==`. CI installs
  exactly that file with `python -m pip install -r requirements.txt`. No
  undeclared package is installed.
- **Frontend:** `frontend/package-lock.json` exists (lockfile v3), so CI uses
  `npm ci` (never `npm install`). The npm cache is keyed by the lockfile.

No dependency declarations needed changes in 5E.12.

## 5. Why PostgreSQL tests may be skipped

The standard backend suite runs entirely against SQLite (in-memory or on-disk
test engines) and needs **no** database and **no** external service.

Optional PostgreSQL round-trip tests (e.g. `test_application_pipeline_api.py`,
`test_backup_integration.py`) skip themselves with `unittest.SkipTest` when
`POSTGRES_TEST_DATABASE_URL` is unset or empty. CI sets it to the empty string
on purpose, so those tests are always reported as **SKIPPED**, never faked as
green. Running them requires a disposable PostgreSQL instance:

```powershell
$env:POSTGRES_TEST_DATABASE_URL = "postgresql://user:pass@localhost:5432/careerpilot_test"
python -m unittest discover -s tests -p "test_*.py"
```

## 6. Protected-file policy and the regression guard

Three files carry pre-existing Resume Parsing 2.0 work and are **immutable**
until that work is deliberately landed:

- `backend/app/services/resume_parser.py`
- `backend/tests/test_resume_parser.py`
- `frontend/src/pages/ResumesPage.jsx`

The committed baseline of these files is in git history. Developer machines may
carry additional uncommitted local modifications; CI runs from a clean checkout,
so the guard always compares the **repository baseline** against the change as
proposed by the PR/push - never a local working tree.

Mechanism: `scripts/check_ci_scope.sh` is run by the `repository-security` job
with a change range (`<base>...HEAD` for pull requests, `<before>..HEAD` for
pushes). If any of the three paths appears in that range the job fails with a
clear `PROTECTED-FILE VIOLATION` message (exit code 3).

Authorization: the guard's job is to make a protected-file change **impossible
to ship accidentally**. An intentional change is allowed only through an
explicit human decision: the change must be reviewed by the team and merged by
removing the affected path from `PROTECTED_FILES` in
`.github/workflows/ci.yml` + `scripts/check_ci_scope.sh`, in a separate,
well-documented commit, together with the deliberate Resume Parsing 2.0 change.
The guard therefore never blocks forever - it forces a conscious, reviewed
action instead of a silent inclusion.

## 7. Secret / configuration scanning

`scripts/scan_repo_secrets.py` (stdlib-only Python) scans the working tree for
**credential-shaped** content and is run in the `repository-security` job.

It looks for:

- PEM private-key blocks (`-----BEGIN ... PRIVATE KEY-----`)
- OpenAI-style `sk-...` keys
- AWS access key IDs (`AKIA...`)
- GitHub personal access tokens (`ghp_...`) and fine-grained tokens
  (`github_pat_...`)
- Google service-account JSON (`"type": "service_account"` **and**
  `"private_key"` in the same file)
- Remote database URLs that embed a password
  (`scheme://user:password@remote-host`, where the host is not
  `localhost`/`127.0.0.1`/`::1`)

Deliberate false-positive controls (documented so the behavior is predictable):

- Files under `backend/tests/` and `frontend/tests/` are exempt **only** from
  the remote-database-URL rule because those suites intentionally contain
  `user:pass` fixture connection strings; every other rule still applies to
  them.
- Localhost placeholder URLs such as
  `postgresql://user:password@localhost:5432/careerpilot` (documented in
  `.env.example`, README, and docs) are not flagged.
- Git-ignored content (`.env`, `node_modules`, uploads, backups, build output,
  caches) is skipped; those files cannot reach a commit.

Scope guarantees:

- The scanner prints only `path:line:rule`, never the matched value, so
  findings are never echoed to CI logs.
- Nothing is uploaded to any external scanning service.

If a real-looking secret is committed, the job fails with `FOUND` lines. To
resolve: remove the secret, rotate it if it ever left the machine, and re-push.

## 8. Workflow security

- `permissions: contents: read` at the workflow level; no job requests more.
- **No repository secrets are used anywhere.** CI runs without secrets, so fork
  PRs cannot exfiltrate anything.
- Third-party actions are pinned to commit SHAs (verified against the published
  tags):
  - `actions/checkout@11d5960a326750d5838078e36cf38b85af677262` (v4)
  - `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065` (v5)
  - `actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020` (v4)
- The change range interpolated into the guard step comes only from trusted
  GitHub context (`pull_request.base.sha`, `event.before`), never from
  untrusted PR content.
- No artifacts are uploaded and the workflow has no deployment side effects.
- `VITE_API_BASE_URL` is set to the documented shared placeholder
  `https://api.careerpilot.app` (the same value in `frontend/.env.example`).
  It satisfies the production-build environment validation in
  `frontend/scripts/validateEnv.mjs`; the bundle is a throwaway CI artifact and
  is never deployed. Using a real origin would not strengthen the check and
  would add an unnecessary external dependency.
- The npm/pip caches are scoped to their respective jobs and never leave the
  runner.

## 9. Investigating failures

- **Backend job:** read the failing test/output from `python -m unittest`.
  Reproduce with the local commands in section 2. Python 3.12 is the CI
  interpreter - reproduce against 3.12 if 3.14-only syntax/behavior is suspected.
- **Frontend job:** `npm ci` failures mean a broken lockfile or registry
  problem; `npm test` failures mean a contract regression; `npm run build`
  failure means a bundle error (often a missing `VITE_API_BASE_URL`);
  `npm run lint` failure means oxlint violations.
- **Repository job:** `git diff --check` reports whitespace/conflict marker
  issues in the range. `PROTECTED-FILE VIOLATION` means a protected path was
  touched; read section 6. `FOUND ...: <rule>` lines mean credential-shaped
  content; read section 7.
- **Skipped tests:** PostgreSQL round-trip tests report as SKIPPED in every CI
  run by design (section 5). A check is only green because of skips is safe
  here: the SQLite suite covers the application behavior and no fake success is
  reported.

## 10. Boundaries

- No deployment, no releases, no scheduled runs, no production access.
- No repository secrets are read by CI.
- Protected Resume Parsing 2.0 files are guarded, never modified by CI scripts.