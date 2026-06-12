#!/usr/bin/env bash
# ADR-0008 V4 (LOCAL simulation, FREE — no API). Can a *cloned* target run
# servo:quality-gate and the meta-judge from a clean checkout, as a cloud Routine
# would? This de-risks the executable, locally-testable parts; the genuinely
# cloud-only unknowns (Routine hook policy + /goal in-cloud) are in
# v4_routines_probe.md.
#
# Surfaces the key portability finding: the meta-judge is clone-portable ONLY if
# servo's gate.py is VENDORED into <target>/.claude/skills/servo-quality-gate/
# (a path relative to CLAUDE_PROJECT_DIR). A non-vendored install bakes servo's
# ABSOLUTE local path, which won't exist in a cloud clone → the hook fails open
# (never blocks) there.
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
GIT="git -c user.email=adr8@example.invalid -c user.name=adr8"

log "=== V4 clean-clone simulation (no API) ==="

# 1) Build a target, make it a git repo, commit it.
src="$(make_target v4-src 2)"
( cd "$src" && $GIT init -q && $GIT add -A && $GIT commit -qm init ) || die "git init/commit failed"

# 2) Clone to a fresh location — simulates the cloud checkout (no prior local state).
clone="$WORK_DIR/v4-clone"; rm -rf "$clone"
$GIT clone -q "$src" "$clone" || die "git clone failed"
log "cloned $src → $clone"

# 3) servo:quality-gate runs against the clone? (oracle + manifest survived the clone)
printf 'pass' > "$clone/.servo/exp/phase"
out="$(python3 "$GATE_PY" "$clone" --json)"; rc=$?
printf '%s\n' "$out" | grep -q '"status": "pass"' && [ "$rc" = 0 ] \
  && log "gate.py on clone: exit=0 status=pass OK" \
  || die "gate.py on clone failed: rc=$rc out=$out"

# 4a) NON-vendored meta-judge install → inspect the baked gate path.
nv="$WORK_DIR/v4-clone-nonvendored"; rm -rf "$nv"; $GIT clone -q "$src" "$nv"
python3 "$HOOK_PY" install "$nv" >/dev/null
nv_gate="$(grep -E '^GATE=' "$nv/.servo/hooks/meta-judge.sh")"
log "non-vendored baked: $nv_gate"
case "$nv_gate" in
  *'CLAUDE_PROJECT_DIR'*) log "  (relative — unexpected for a non-vendored install)";;
  *) log "  ⚠ ABSOLUTE servo path baked → would NOT exist in a cloud clone → meta-judge fails open there";;
esac

# 4b) VENDORED meta-judge install → relative path → fires correctly post-clone.
v="$WORK_DIR/v4-clone-vendored"; rm -rf "$v"; $GIT clone -q "$src" "$v"
mkdir -p "$v/.claude/skills/servo-quality-gate"
cp "$GATE_PY" "$v/.claude/skills/servo-quality-gate/gate.py"
python3 "$HOOK_PY" install "$v" >/dev/null
v_gate="$(grep -E '^GATE=' "$v/.servo/hooks/meta-judge.sh")"
log "vendored baked:     $v_gate"
case "$v_gate" in
  *'CLAUDE_PROJECT_DIR'*) log "  relative gate path OK (clone-portable)";;
  *) die "vendored install did not bake a relative path: $v_gate";;
esac
# Fire the vendored meta-judge on a FAILING phase → must BLOCK using the relative gate.
printf 'fail' > "$v/.servo/exp/phase"
o="$(printf '%s' '{"stop_hook_active":false}' | CLAUDE_PROJECT_DIR="$v" sh "$v/.servo/hooks/meta-judge.sh")"
printf '%s' "$o" | grep -q '"decision": "block"' \
  && log "vendored meta-judge fires post-clone: BLOCK OK (resolved gate.py relatively)" \
  || die "vendored meta-judge did not block post-clone: [$o]"

log "=== V4 sim PASSED — target artifacts are clone-portable IFF gate.py is vendored. \$0 spent. ==="
log "Cloud-only unknowns remain (Routine hook policy + /goal in-cloud) → v4_routines_probe.md"
