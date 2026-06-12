# ADR-0008 experiment harness — shared helpers. Sourced by the runners; not
# meant to be executed directly. No `set -e` on purpose: this harness runs many
# intentionally-nonzero commands (the oracle exits 1 on "fail"), so callers check
# explicitly and the live `claude` calls manage their own exit handling.

EXP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$EXP_DIR/../../.." && pwd)"
WORK_DIR="$EXP_DIR/_work"
FIXTURES="$EXP_DIR/fixtures"

GATE_PY="$REPO_ROOT/skills/quality-gate/gate.py"
HOOK_PY="$REPO_ROOT/skills/oracle-hook/hook.py"

# Wall-clock guard so an interactive-waiting / hung invocation can't block forever.
RUN_TIMEOUT_SECS="${ADR8_RUN_TIMEOUT_SECS:-240}"
# Cheap model by default; override with ADR8_MODEL for a more compliant agent.
CLAUDE_MODEL="${ADR8_MODEL:-claude-haiku-4-5-20251001}"

# Scope the nested agent to ONLY the two fixture scripts — NOT a blanket
# `--permission-mode bypassPermissions`. A full bypass would make these
# autonomous nested agents unsafe (and is the kind of thing a permission
# classifier should, and does, refuse when an agent infers it on its own).
# This allowlist is the deliberate, minimal grant the experiment actually needs.
ADR8_ALLOWED_TOOLS="${ADR8_ALLOWED_TOOLS:-Bash(./oracle.sh) Bash(./work_step.sh) Bash(bash ./oracle.sh) Bash(bash ./work_step.sh)}"

log() { printf '\033[1m[adr8]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[adr8] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# The loop body every run shares. Deliberately minimal so the agent's compliance
# is not the variable under test — the only choices it makes are oracle→work_step.
LOOP_BODY='You are in a deterministic work loop in the current directory. On EACH turn do EXACTLY these steps and NOTHING else:
1. Run the command:  ./oracle.sh   — and print its complete output verbatim.
2. If that output contains "status=fail": run  ./work_step.sh  once (print its output), then STOP your turn.
3. If that output contains "status=pass": STOP your turn immediately and run nothing else.
Never create, edit, or delete any other file. Never run any other command.'

# make_target <name> <pass_after> → prints the absolute target path on stdout.
make_target() {
  name="$1"; pass_after="$2"
  t="$WORK_DIR/$name"
  rm -rf "$t"
  mkdir -p "$t/.servo/exp"
  cp "$FIXTURES/oracle.sh"    "$t/oracle.sh";    chmod +x "$t/oracle.sh"
  cp "$FIXTURES/work_step.sh" "$t/work_step.sh"; chmod +x "$t/work_step.sh"
  printf 'fail'        > "$t/.servo/exp/phase"
  printf '0'           > "$t/.servo/exp/progress"
  printf '%s' "$pass_after" > "$t/.servo/exp/pass_after"
  printf '{"installed_tier": "tier-0", "components": ["demo"], "servo_version": "adr8-exp", "signals": {}}\n' \
    > "$t/.servo/install.json"
  printf '%s' "$t"
}

# install_meta_judge <target> — REAL install via hook.py, then instrument the
# installed script with the logging wrapper (real body kept as meta-judge.real.sh).
install_meta_judge() {
  t="$1"
  python3 "$HOOK_PY" install "$t" >&2 || die "hook.py install failed for $t"
  hook_dir="$t/.servo/hooks"
  cp "$hook_dir/meta-judge.sh" "$hook_dir/meta-judge.real.sh"
  cp "$FIXTURES/mj_wrapper.sh" "$hook_dir/meta-judge.sh"
  chmod +x "$hook_dir/meta-judge.sh" "$hook_dir/meta-judge.real.sh"
  python3 "$HOOK_PY" status "$t" >&2 || true
}

# run_with_timeout <secs> <cmd...>
run_with_timeout() {
  secs="$1"; shift
  if command -v timeout  >/dev/null 2>&1; then timeout  "$secs" "$@"; return $?; fi
  if command -v gtimeout >/dev/null 2>&1; then gtimeout "$secs" "$@"; return $?; fi
  "$@" & pid=$!
  ( sleep "$secs"; kill -TERM "$pid" 2>/dev/null ) & watcher=$!
  wait "$pid"; rc=$?
  kill -TERM "$watcher" 2>/dev/null || true
  return "$rc"
}

# _capture_run <target> <out_dir> <prompt> [extra claude args...]
_capture_run() {
  t="$1"; out="$2"; prompt="$3"; shift 3
  mkdir -p "$out"
  budget="${ADR8_MAX_BUDGET_USD:-0.50}"
  export SERVO_MJ_LOG="$t/.servo/exp/mj-firings.jsonl"; : > "$SERVO_MJ_LOG"
  log "run → $out  (target=$t budget=\$$budget model=$CLAUDE_MODEL)"
  ( cd "$t" && run_with_timeout "$RUN_TIMEOUT_SECS" \
      claude -p "$prompt" \
        --output-format stream-json --verbose --include-hook-events \
        --allowedTools "$ADR8_ALLOWED_TOOLS" \
        --model "$CLAUDE_MODEL" \
        --max-budget-usd "$budget" \
        "$@" ) > "$out/stream.jsonl" 2> "$out/stderr.log"
  rc=$?
  echo "$rc" > "$out/exit_code"
  cp -f "$SERVO_MJ_LOG"            "$out/mj-firings.jsonl" 2>/dev/null || : > "$out/mj-firings.jsonl"
  cp -f "$t/.servo/exp/phase"      "$out/final_phase"      2>/dev/null || true
  cp -f "$t/.servo/exp/progress"   "$out/final_progress"   2>/dev/null || true
  printf '%s\n' "$prompt" > "$out/prompt.txt"
  log "  exit_code=$rc  final_phase=$(cat "$t/.servo/exp/phase" 2>/dev/null)"
}

# launch_goal_run <target> <out_dir> <goal_condition> [extra args...]
launch_goal_run() {
  t="$1"; out="$2"; goal="$3"; shift 3
  _capture_run "$t" "$out" "/goal ${goal}

${LOOP_BODY}" "$@"
}

# launch_plain_run <target> <out_dir> [extra args...] — same workload, NO /goal.
launch_plain_run() {
  t="$1"; out="$2"; shift 2
  _capture_run "$t" "$out" "$LOOP_BODY" "$@"
}
