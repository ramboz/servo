#!/usr/bin/env bash
# ADR-0008 — FREE preflight (no API spend). Validates the whole deterministic
# substrate (oracle ↔ gate.py ↔ meta-judge ↔ instrumentation) and records the
# claude flag surface, so the live V1/V2 runs can be trusted before spending.
source "$(cd "$(dirname "$0")" && pwd)/common.sh"

log "=== preflight (no API spend) ==="

# 1) claude availability + version + flag surface (a V2 data point on its own).
command -v claude >/dev/null 2>&1 || die "claude not on PATH"
log "claude: $(claude --version 2>/dev/null || echo '?')"
HELP="$(claude --help 2>/dev/null || true)"
for flag in --max-budget-usd --max-turns --include-hook-events --permission-mode; do
  if printf '%s' "$HELP" | grep -q -- "$flag"; then
    log "flag $flag: PRESENT"
  else
    log "flag $flag: not-in-help$([ "$flag" = "--max-turns" ] && echo '  (NOTE: --max-turns is HIDDEN from --help but IS functional — verify by invocation, not --help; see ADR V2)')"
  fi
done

# 2) deterministic substrate via gate.py (oracle fail → pass).
t="$(make_target preflight 2)"
log "built target: $t"

out_fail="$(python3 "$GATE_PY" "$t" --json)"; rc_fail=$?
printf '%s\n' "$out_fail" | grep -q '"status": "below_threshold"' && [ "$rc_fail" = "1" ] \
  && log "gate(fail): exit=1 status=below_threshold OK" \
  || die "gate(fail) unexpected: rc=$rc_fail out=$out_fail"

osout="$("$t/oracle.sh")"
printf '%s\n' "$osout" | grep -q 'SERVO_ORACLE_VERDICT exit=1 status=fail' \
  && log "oracle(fail): sentinel present OK" || die "oracle(fail) sentinel missing: $osout"

"$t/work_step.sh" >/dev/null; "$t/work_step.sh" >/dev/null   # 2 steps → phase=pass
out_pass="$(python3 "$GATE_PY" "$t" --json)"; rc_pass=$?
printf '%s\n' "$out_pass" | grep -q '"status": "pass"' && [ "$rc_pass" = "0" ] \
  && log "gate(pass): exit=0 status=pass OK" \
  || die "gate(pass) unexpected: rc=$rc_pass out=$out_pass"

# 3) meta-judge install + instrumentation + behavior (still no API).
t2="$(make_target preflight-mj 2)"
install_meta_judge "$t2"
[ -f "$t2/.servo/hooks/meta-judge.real.sh" ] || die "real meta-judge body not saved"
export SERVO_MJ_LOG="$t2/.servo/exp/mj-firings.jsonl"; : > "$SERVO_MJ_LOG"
export CLAUDE_PROJECT_DIR="$t2"

o1="$(printf '%s' '{"stop_hook_active": false}' | sh "$t2/.servo/hooks/meta-judge.sh")"
printf '%s' "$o1" | grep -q '"decision": "block"' \
  && log "meta-judge(fail, first stop): BLOCK OK" || die "expected block, got: [$o1]"

o2="$(printf '%s' '{"stop_hook_active": true}' | sh "$t2/.servo/hooks/meta-judge.sh")"
[ -z "$o2" ] && log "meta-judge(fail, repeat stop): SUPPRESS OK" || die "expected suppress, got: [$o2]"

"$t2/work_step.sh" >/dev/null; "$t2/work_step.sh" >/dev/null   # → phase=pass
o3="$(printf '%s' '{"stop_hook_active": false}' | sh "$t2/.servo/hooks/meta-judge.sh")"
[ -z "$o3" ] && log "meta-judge(pass): silent allow OK" || die "expected silent allow, got: [$o3]"

n="$(grep -c . "$SERVO_MJ_LOG" 2>/dev/null || echo 0)"
[ "$n" -ge 3 ] && log "mj firing log captured $n records OK" || die "mj log under-captured: $n"

# stop_hook_active must be captured correctly (regression guard for the heredoc
# bug that logged PARSE_ERR): firing 1 saw false, firing 2 saw true.
sha_ok="$(python3 -c '
import json,sys
recs=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]
print("OK" if recs[0]["stop_hook_active"]=="false" and recs[1]["stop_hook_active"]=="true" else "BAD:%r,%r"%(recs[0]["stop_hook_active"],recs[1]["stop_hook_active"]))
' "$SERVO_MJ_LOG" 2>/dev/null || echo PYERR)"
[ "$sha_ok" = "OK" ] && log "stop_hook_active capture: false→true OK" \
  || die "stop_hook_active not captured correctly: $sha_ok"

log "=== preflight PASSED — substrate valid, \$0 spent. Safe to run v1/v2. ==="
