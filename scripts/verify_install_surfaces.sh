#!/usr/bin/env bash
# scripts/verify_install_surfaces.sh — single entry point that proves servo's
# three runtime-install surfaces (plugin root / release zip / project-local
# scaffold) stay coherent. Slice 007-05 (docs-and-ci); this is the one
# documented local command behind AC3, and CI (the install-surfaces job in
# .github/workflows/ci.yml) runs exactly this script.
#
# Steps, in order, failing on the first failure:
#   1. verify the live checked-out plugin root against the install contract;
#   2. run the install-surface test suites (plugin verifier, zip builder,
#      scaffold verifier/runtime, and the docs stale-path guard).
#
# Run from the repo root:
#     bash scripts/verify_install_surfaces.sh
#
# pytest is preferred as `python3 -m pytest` so the script works in CI (where
# pytest is installed into the active environment). When that module is not
# importable — the common local case, where the suite is run via uv — the
# script falls back to `uvx pytest`. It does not hard-code uvx as the only
# path.

set -euo pipefail

# Resolve the repo root from this script's own location so the command works
# regardless of the caller's current working directory.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"

# Choose how to run pytest: prefer the in-environment module (CI installs it),
# fall back to uvx (local dev) so the single command runs in both places.
pytest_cmd=()
if python3 -c "import pytest" >/dev/null 2>&1; then
  pytest_cmd=(python3 -m pytest)
elif command -v uvx >/dev/null 2>&1; then
  pytest_cmd=(uvx pytest)
else
  echo "error: pytest is not importable and uvx is not available" >&2
  exit 127
fi

echo "==> verify plugin root (.)"
python3 scripts/verify_install.py plugin .

echo "==> install-surface test suite (${pytest_cmd[*]})"
"${pytest_cmd[@]}" \
  scripts/test_verify_install.py \
  scripts/test_build_release_zip.py \
  scripts/test_scaffold_runtime.py \
  scripts/test_docs_install.py

echo "==> install surfaces OK"
