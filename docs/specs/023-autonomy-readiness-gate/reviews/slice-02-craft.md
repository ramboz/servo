---
slice: 023-02 — loop.py readiness preflight (the two unattended surfaces)
pass: craft
verdict: pass
reviewer: pr-review
reviewed_at: 2026-08-12T19:26:39Z
prompt_source: review.py pr-review docs/specs/023-autonomy-readiness-gate/spec.md 023-02 --richer-skill pr-review
substrate: non-interactive
---

VERDICT: pass

REASONING:
The slice gates only the two pinned unattended launch surfaces, fails closed on any
non-permit result, and threads a bypass seam — with no scope creep into the heartbeat
or the detached child. Craft closely mirrors established sibling idioms (`_refuse_plan`,
`GATE_PATH`→`READINESS_PATH`, `sys.executable` subprocessing) and refuses before any
run-dir/emit/detach. Tests are meaningful and non-vacuous: negative paths assert rc=2 +
a specific `terminal_reason`; positive paths drive the real `readiness.py check`
subprocess. Only cosmetic nits remain.

SPECIFIC ISSUES:
- [nit][impl] skills/agent-loop/loop.py:1153-1155 — `... in (_READINESS_GATE_BYPASS_VALUES)`
  redundant parens (single name, not a tuple). Drop for clarity.
- [nit][impl] skills/agent-loop/loop.py:1170-1177 — `_readiness_check_rc` doesn't register
  the child as `_active_subprocess` (as `_invoke_gate` does), so a SIGINT during preflight
  waits up to the 30s timeout. Benign — preflight runs before signal handlers install and
  before any run starts. Noted for symmetry.
- [nit][impl] skills/agent-loop/loop.py:3390-3394 — `readiness_check_unavailable` message
  lumps "exited N, or failed to spawn / timed out"; since spawn/timeout fold into rc=2
  upstream, a reader can't distinguish a real env-error from a spawn failure. Fail-closed is
  correct either way.

STRENGTHS:
- Single-source-of-truth: subprocesses `check` instead of re-deriving `_goal_id` sha256,
  rationale documented inline — structurally prevents goal-id-scheme drift.
- Fail-closed posture explicit and defended; exemptions (detached re-exec, synchronous
  `--prompt`) exempt by construction, not an easily-broken conditional.
- Positive-path tests seed a real schema-valid artifact and exercise the actual
  `readiness.py check` subprocess end-to-end (not a mock).
- AC4 surface-set pin asserted directly, so a future third surface can't silently escape.

RECONCILIATION NOTES:
No blockers — safe for REVIEWED. The three nits are cosmetic/defensive → deviation log.
Carry the already-disclosed limit (`--emit-routine-prompt` gates at emit time only,
frame-critique follow-up #2) to refinement-todo as planned — a known, accepted boundary,
not a craft defect.
