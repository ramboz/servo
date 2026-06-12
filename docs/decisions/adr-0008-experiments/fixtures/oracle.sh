#!/usr/bin/env bash
# ADR-0008 experiment fixture — a *read-only* controllable oracle.
#
# The verdict is driven entirely by <target>/.servo/exp/phase ("fail" | "pass").
# Reading it never mutates state, so servo's meta-judge (which runs this oracle
# on every Stop) and the agent's own loop-body run never confound each other —
# only ./work_step.sh advances the phase.
#
# Honors servo's oracle exit contract (templates/oracle.sh.template):
#   exit 0  composite >= THRESHOLD (pass)
#   exit 1  composite <  THRESHOLD (below threshold)
# Prints the `oracle: composite=X threshold=Y` line gate.py parses, PLUS the
# SERVO_ORACLE_VERDICT sentinel the (proposed) /goal condition fact-checks.
set -u

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
PHASE_FILE="$SELF_DIR/.servo/exp/phase"
THRESHOLD="${THRESHOLD:-0.5}"

phase="$(cat "$PHASE_FILE" 2>/dev/null || echo fail)"
if [ "$phase" = "pass" ]; then
  composite="1.0"; status="pass"; rc=0
else
  composite="0.0"; status="fail"; rc=1
fi

# Sentinel first (the transcript fact the /goal evaluator reads), then the
# gate.py-parseable summary line. Both on stdout so an agent echoing the oracle's
# output surfaces the sentinel into the transcript.
printf 'SERVO_ORACLE_VERDICT exit=%s status=%s composite=%s threshold=%s\n' \
  "$rc" "$status" "$composite" "$THRESHOLD"
printf 'oracle: composite=%s threshold=%s\n' "$composite" "$THRESHOLD"
exit "$rc"
