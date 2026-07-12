#!/usr/bin/env bash
# scripts/verify_install_surfaces.sh — focused gate that proves servo's
# three runtime-install surfaces (plugin root / release zip / project-local
# scaffold) stay coherent. `scripts/ci_check.py` is the canonical full local CI
# mirror; this helper is one named step in that gate and in ci.yml.
#
# Steps, in order, failing on the first failure:
#   1. verify the canonical source root against the install contract;
#   2. validate all four host manifests and committed-package drift;
#   3. run the install-surface test suites (host packages, release zips,
#      plugin/scaffold verifiers, and the docs stale-path guard).
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

echo "==> validate dual-host manifests"
python3 scripts/validate_manifests.py

echo "==> verify committed host packages are current"
python3 scripts/build_host_packages.py --check

echo "==> install-surface test suite (${pytest_cmd[*]})"
"${pytest_cmd[@]}" \
  scripts/test_verify_install.py \
  scripts/test_validate_manifests.py \
  scripts/test_build_host_packages.py \
  scripts/test_build_release_zip.py \
  scripts/test_scaffold_runtime.py \
  scripts/test_docs_install.py

echo "==> install surfaces OK"
