#!/bin/sh
# ADR-0008 experiment — behavior-preserving instrumentation around servo's REAL
# meta-judge Stop hook (saved beside this file as meta-judge.real.sh by setup).
#
# Logs one JSONL record per Stop firing — the `stop_hook_active` it saw, the
# delegate's exit code, and the exact stdout it emitted (a {"decision":"block"}
# nudge, a {"systemMessage":...} env-warning, or empty for a silent allow) — then
# re-emits that stdout unchanged and exits with the same code. Observability
# only; it never alters what servo's hook decides.
DIR="$(dirname "$0")"
REAL="$DIR/meta-judge.real.sh"
LOG="${SERVO_MJ_LOG:-${CLAUDE_PROJECT_DIR:-$DIR/../..}/.servo/exp/mj-firings.jsonl}"

INPUT="$(cat)"

# Extract stop_hook_active BEFORE delegating. Program comes from -c (argv), so
# the piped INPUT is the only thing on stdin — no heredoc/stdin collision.
SHA="$(printf '%s' "$INPUT" | python3 -c 'import json,sys
try:
    print(json.dumps(json.load(sys.stdin).get("stop_hook_active")))
except Exception:
    print("PARSE_ERR")' 2>/dev/null || echo PARSE_ERR)"

OUT="$(printf '%s' "$INPUT" | sh "$REAL")"
RC=$?

# Log with everything passed via argv (no stdin needed → no collision).
python3 -c 'import json,sys,time
log,sha,rc,out=sys.argv[1:5]
rec={"ts":round(time.time(),3),"stop_hook_active":sha,"delegate_rc":int(rc),"stdout":out}
open(log,"a").write(json.dumps(rec)+"\n")' "$LOG" "$SHA" "$RC" "$OUT" 2>/dev/null || true

printf '%s' "$OUT"
exit "$RC"
