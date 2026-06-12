#!/usr/bin/env bash
# ADR-0008 V2 — does /goal engage headlessly, and do hard caps bind a /goal run?
#
#   a  engage         /goal + pass_after=3 (needs ~4 turns). Did it drive >1 turn
#                     in -p mode at all, and did it stop exactly when the
#                     SERVO_ORACLE_VERDICT pass sentinel appeared (fact-check OK)?
#   b  budget_cap     /goal + pass_after far out + a tiny --max-budget-usd. Does
#                     spend halt the run mid-goal (hard cap binds a /goal run)?
#   c  plain_control  same workload, NO /goal — turn-count baseline for `a`.
#
# NOTE: this script exercises only the *budget* cap (arm b). `--max-turns` IS
# functional (though hidden from `claude --help`) and DOES bind a /goal run —
# verified separately to halt with subtype=error_max_turns at the cap. Probe it
# with:  launch_goal_run <unreachable-target> <out> "$GOAL" --max-turns 3
source "$(cd "$(dirname "$0")" && pwd)/common.sh"

RUN_ID="${1:-$(date +%Y%m%dT%H%M%S)}"
OUT="$WORK_DIR/runs/v2-$RUN_ID"
mkdir -p "$OUT"
GOAL='continue until the transcript contains a line that includes "SERVO_ORACLE_VERDICT exit=0 status=pass"'

log "=== V2 /goal headless + cap binding — run dir: $OUT ==="

t_a="$(make_target v2a-engage 3)"
launch_goal_run  "$t_a" "$OUT/a_engage" "$GOAL"

t_b="$(make_target v2b-budget 99)"
ADR8_MAX_BUDGET_USD="${ADR8_V2B_BUDGET:-0.08}" launch_goal_run "$t_b" "$OUT/b_budget_cap" "$GOAL"

t_c="$(make_target v2c-plain 3)"
launch_plain_run "$t_c" "$OUT/c_plain_control"

log "=== V2 runs complete — analyzing ==="
python3 "$EXP_DIR/analyze.py" v2 "$OUT"
