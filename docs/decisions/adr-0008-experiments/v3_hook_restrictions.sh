#!/usr/bin/env bash
# ADR-0008 V3 — availability under hook restrictions (LIVE; needs API).
#
# Confirms the Kill-criterion-4 mechanism: a single switch disables BOTH /goal
# (which rides a managed Stop hook) AND servo's meta-judge (a project Stop hook),
# while loop.py (a plain `claude -p` subprocess loop, no hooks) is unaffected.
#
#   baseline        normal settings → both /goal and the meta-judge active.
#   disableAllHooks --settings '{"disableAllHooks":true}' → expect BOTH off.
#
# `allowManagedHooksOnly` is a MANAGED-settings-tier switch (not injectable via
# --settings) — see v4_routines_probe.md / README for the manual managed-file
# method. Its expected effect is the same: /goal off + project meta-judge off.
source "$(cd "$(dirname "$0")" && pwd)/common.sh"

RUN_ID="${1:-$(date +%Y%m%dT%H%M%S)}"
OUT="$WORK_DIR/runs/v3-$RUN_ID"
mkdir -p "$OUT"
GOAL='continue until the transcript contains a line that includes "SERVO_ORACLE_VERDICT exit=0 status=pass"'

log "=== V3 hook-restriction availability — run dir: $OUT ==="

# Arm 1 — baseline control: both hooks active.
t1="$(make_target v3-baseline 2)"; install_meta_judge "$t1"
launch_goal_run "$t1" "$OUT/baseline" "$GOAL"

# Arm 2 — disableAllHooks injected via --settings inline JSON.
t2="$(make_target v3-disableallhooks 2)"; install_meta_judge "$t2"
launch_goal_run "$t2" "$OUT/disableAllHooks" "$GOAL" --settings '{"disableAllHooks":true}'

log "=== V3 runs complete — analyzing ==="
python3 "$EXP_DIR/analyze.py" v3 "$OUT"

cat >&2 <<'NOTE'

[adr8] allowManagedHooksOnly is NOT exercised above (it only binds in the MANAGED
[adr8] settings tier, which --settings cannot reach). To test it manually:
[adr8]   1. Write a managed-settings file (needs admin), e.g. on macOS:
[adr8]      sudo mkdir -p "/Library/Application Support/ClaudeCode"
[adr8]      echo '{"allowManagedHooksOnly": true}' | sudo tee \
[adr8]        "/Library/Application Support/ClaudeCode/managed-settings.json"
[adr8]   2. Re-run an arm; expect /goal unavailable AND the (project) meta-judge silent.
[adr8]   3. CLEAN UP: sudo rm that file afterwards (it is machine-wide).
[adr8] Run ./v3_audit_env.py <target> first to see what is already in effect.
NOTE
