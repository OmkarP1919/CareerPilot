#!/usr/bin/env bash
# CI scope guard for CareerPilot (Phase 5E.12).
#
# Two checks in one script:
#   1. `git diff --check` (whitespace / conflict-marker cleanliness) over the
#      change range passed as $1.
#   2. Protected-file regression guard: fails if any of the Resume Parsing 2.0
#      baseline files appears in the change range, unless the change is an
#      explicitly authorized corrective restoration (see
#      AUTHORIZED_PROTECTED_COMMITS below).
#
# Usage (from a fresh CI checkout, full history available):
#     bash scripts/check_ci_scope.sh "<range>"
#
# <range> is passed by .github/workflows/ci.yml:
#   - pull_request: <base sha>...HEAD   (three-dot: PR changes only)
#   - push:         <before sha>..HEAD  (two-dot: pushed commits only)
#
# The guard compares the *repository baseline* (committed HEAD) against the
# proposed change. CI always runs from a clean checkout, so a developer's local
# uncommitted modifications are never part of the comparison.
#
# Exit codes:
#   0  - clean
#   1  - whitespace/whitespace-error check failed (git diff --check)
#   3  - one or more protected files changed (and the change is not a
#        SHA-pinned, baseline-restoring authorization)

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "${REPO_ROOT}"

RANGE="${1:-}"

if [[ -z "${RANGE}" ]] || [[ "${RANGE}" == "0000000000000000000000000000000000000000.."* ]]; then
  RANGE="HEAD^..HEAD"
fi

# ---------------------------------------------------------------------------
# Check 1: whitespace / marker cleanliness over the change range.
# ---------------------------------------------------------------------------
git diff --check "${RANGE}"

# ---------------------------------------------------------------------------
# Check 2: protected-file regression guard.
# ---------------------------------------------------------------------------
declare -ra PROTECTED_FILES=(
  "backend/app/services/resume_parser.py"
  "backend/tests/test_resume_parser.py"
  "frontend/src/pages/ResumesPage.jsx"
)

# ---------------------------------------------------------------------------
# Authorized protected-file changes (explicit human authorization).
#
# docs/ci_cd.md section 6 declares protected files immutable unless the change
# is explicitly authorized. This list is that authorization record, bound to
# the specific commit SHA(s) that deliberately restored a protected file to
# its pinned Resume Parsing 2.0 baseline. A protected-file change passes the
# guard ONLY when:
#   1. every commit in the examined range that touches the file is listed
#      here, AND
#   2. the file's committed HEAD blob still equals its pinned baseline
#      (mirrors backend/scripts/release_smoke.py PROTECTED_FILES_AT_HEAD).
#
# The second condition means this exception can only ever permit *restorations*
# to the protected baseline - never arbitrary edits, which still require the
# documented full authorization flow (removing the path from PROTECTED_FILES).
# ---------------------------------------------------------------------------

# Commits whose protected-file changes were human-authorized as corrective
# restorations to the pinned baseline:
declare -ra AUTHORIZED_PROTECTED_COMMITS=(
  # "fix: restore protected file integrity" - restored the three protected
  # files to their baseline blobs after accidental inclusion in 0ce1aa5.
  "2f59bf72422379e702b742e2772033f3edb5e476"
  # "fix: restore protected resume page baseline" - restored the protected
  # ResumesPage.jsx to its pinned baseline after the 7.0D.5 heading polish.
  "6156373e07b9b54895249418d332edcdf0f4fbee"
)

# Pinned protected HEAD blobs (path|blob). Keep in sync with
# backend/scripts/release_smoke.py PROTECTED_FILES_AT_HEAD.
declare -ra PROTECTED_HEAD_BLOBS=(
  "backend/app/services/resume_parser.py|8b993dedf6460c0c87460ef8804a39dac43d4ef3"
  "backend/tests/test_resume_parser.py|f7f18c8e33d9c79743f198dc7ed2ede4b5f1dcfb"
  "frontend/src/pages/ResumesPage.jsx|e318462452d5df17f64d5049ecb13ecf67fc1b13"
)

# 0 if the change to a protected file is an authorized baseline restoration.
protected_change_is_authorized() {
  local file="$1"
  local entry="" path="" pinned=""
  local commit="" authorized=""

  # Every commit in the range that touched this file must be in the allowlist.
  while IFS= read -r commit; do
    [[ -z "${commit}" ]] && continue
    authorized=""
    for entry in "${AUTHORIZED_PROTECTED_COMMITS[@]}"; do
      if [[ "${commit}" == "${entry}" ]]; then
        authorized="1"
        break
      fi
    done
    if [[ -z "${authorized}" ]]; then
      return 1
    fi
  done < <(git log --format='%H' "${RANGE}" -- "${file}" 2>/dev/null)

  # The committed HEAD blob must still equal the pinned baseline.
  for entry in "${PROTECTED_HEAD_BLOBS[@]}"; do
    path="${entry%%|*}"
    if [[ "${path}" == "${file}" ]]; then
      pinned="${entry##*|}"
      break
    fi
  done
  if [[ -z "${pinned}" ]]; then
    return 1
  fi
  [[ "$(git rev-parse "HEAD:${file}" 2>/dev/null)" == "${pinned}" ]]
}

CHANGED="$(git diff --name-only "${RANGE}")"

violation=0
while IFS= read -r changed_file; do
  [[ -z "${changed_file}" ]] && continue
  for protected in "${PROTECTED_FILES[@]}"; do
    if [[ "${changed_file}" == "${protected}" ]]; then
      if protected_change_is_authorized "${changed_file}"; then
        echo "authorized protected-file change for ${changed_file} in ${RANGE} (SHA-pinned baseline restoration)"
      else
        echo "::error file=${changed_file}::PROTECTED-FILE VIOLATION: ${changed_file} changed in ${RANGE}"
        violation=1
      fi
    fi
  done
done <<< "${CHANGED}"

if [[ "${violation}" -eq 1 ]]; then
  echo ""
  echo "One or more protected Resume Parsing 2.0 files were modified by this change."
  echo "These files require explicit human authorization (see docs/ci_cd.md)."
  exit 3
fi

echo "Protected-file guard: OK (no unauthorized protected files changed in ${RANGE})"