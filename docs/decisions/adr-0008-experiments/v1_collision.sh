#!/usr/bin/env bash
# ADR-0008 V1 — Stop-hook collision. Does /goal's managed session-scoped Stop
# hook compose with servo's shipped meta-judge Stop hook (ADR-0006), or does one
# preempt/suppress the other? Three arms, then analyze.
#
#   A  meta-judge ONLY (no /goal)  — baseline; also proves project hooks fire in -p.
#   B  /goal ONLY (no meta-judge)  — baseline for /goal-driven continuation.
#   C  BOTH                        — the collision test; compare against A and B.
source "$(cd "$(dirname "$0")" && pwd)/common.sh"

RUN_ID="${1:-$(date +%Y%m%dT%H%M%S)}"
OUT="$WORK_DIR/runs/v1-$RUN_ID"
mkdir -p "$OUT"
GOAL='continue until the transcript contains a line that includes "SERVO_ORACLE_VERDICT exit=0 status=pass"'

log "=== V1 Stop-hook collision — run dir: $OUT ==="

ta="$(make_target v1a-mj-only 2)";  install_meta_judge "$ta"
launch_plain_run "$ta" "$OUT/A_mj_only"

tb="$(make_target v1b-goal-only 2)"
launch_goal_run  "$tb" "$OUT/B_goal_only" "$GOAL"

tc="$(make_target v1c-both 2)";     install_meta_judge "$tc"
launch_goal_run  "$tc" "$OUT/C_both" "$GOAL"

log "=== V1 runs complete — analyzing ==="
python3 "$EXP_DIR/analyze.py" v1 "$OUT"
