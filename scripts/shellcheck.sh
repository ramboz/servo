#!/usr/bin/env bash
# scripts/shellcheck.sh — invoke shellcheck via the local binary if installed,
# else fall back to the `koalaman/shellcheck:stable` Docker image. Designed to
# be called from the test suite so AC #5 of slice 001-02 stops silently
# skipping on dev machines without a local install.
#
# Contract: takes shellcheck flags followed by exactly one file path as the
# last argument. Exits with shellcheck's exit code, or 127 if neither the
# local binary nor docker is available.

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: $0 [shellcheck-flags...] <file>" >&2
  exit 2
fi

file="${!#}"
flags=()
if [ "$#" -gt 1 ]; then
  flags=("${@:1:$(($# - 1))}")
fi

if command -v shellcheck >/dev/null 2>&1; then
  exec shellcheck "${flags[@]:+${flags[@]}}" "$file"
fi

if command -v docker >/dev/null 2>&1; then
  abs_file="$(cd "$(dirname "$file")" && pwd)/$(basename "$file")"
  dir="$(dirname "$abs_file")"
  name="$(basename "$abs_file")"
  exec docker run --rm -v "$dir:$dir:ro" -w "$dir" \
    koalaman/shellcheck:stable "${flags[@]:+${flags[@]}}" "$name"
fi

echo "shellcheck: neither local binary nor docker is available" >&2
exit 127
