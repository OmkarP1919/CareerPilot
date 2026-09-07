#!/usr/bin/env bash
# CI scope guard for CareerPilot (Phase 5E.12).
#
# Two checks in one script:
#   1. `git diff --check` (whitespace / conflict-marker cleanliness) over the
#      change range passed as $1.
#   2. Protected-file regression guard: fails if any of the Resume Parsing 2.0
#      baseline files appears in the change range.
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
#   3  - one or more protected files changed

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

CHANGED="$(git diff --name-only "${RANGE}")"

violation=0
while IFS= read -r changed_file; do
  [[ -z "${changed_file}" ]] && continue
  for protected in "${PROTECTED_FILES[@]}"; do
    if [[ "${changed_file}" == "${protected}" ]]; then
      echo "::error file=${changed_file}::PROTECTED-FILE VIOLATION: ${changed_file} changed in ${RANGE}"
      violation=1
    fi
  done
done <<< "${CHANGED}"

if [[ "${violation}" -eq 1 ]]; then
  echo ""
  echo "One or more protected Resume Parsing 2.0 files were modified by this change."
  echo "These files require explicit human authorization (see docs/ci_cd.md)."
  exit 3
fi

echo "Protected-file guard: OK (no protected files changed in ${RANGE})"