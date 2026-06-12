#!/usr/bin/env bash
# ADR-0008 experiment fixture — the ONLY state mutator in the loop.
#
# Each call advances a progress counter; once it reaches `pass_after`, the phase
# flips fail→pass so the *next* oracle run passes. Keeping mutation out of the
# oracle is what lets the meta-judge score on every Stop without driving the loop.
set -u

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
EXP="$SELF_DIR/.servo/exp"
mkdir -p "$EXP"

progress="$(cat "$EXP/progress" 2>/dev/null || echo 0)"
progress=$((progress + 1))
printf '%s' "$progress" > "$EXP/progress"

pass_after="$(cat "$EXP/pass_after" 2>/dev/null || echo 2)"
if [ "$progress" -ge "$pass_after" ]; then
  printf 'pass' > "$EXP/phase"
fi

printf 'work-step: progress=%s pass_after=%s phase=%s\n' \
  "$progress" "$pass_after" "$(cat "$EXP/phase" 2>/dev/null || echo fail)"
