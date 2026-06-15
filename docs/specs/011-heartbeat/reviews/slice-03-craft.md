---
slice: 011-03 — candidate-dispatch
pass: craft
verdict: pass-with-nits
reviewer: jig:reviewer
reviewed_at: 2026-06-15T20:09:00Z
prompt_source: jig:reviewer subagent (worktree-read, uncommitted slice) — docs/specs/011-heartbeat/slice-03-candidate-dispatch.md skills/heartbeat/heartbeat.py skills/heartbeat/test_heartbeat.py
---

VERDICT: pass-with-nits

REASONING:
The 011-03 dispatch additions are clean, idiomatic, and faithful to the established
011-01/02 house style. They genuinely reuse the existing spine machinery (`_inbox_lock`,
`_atomic_write`, `_normalize_record`, `_read_inbox_for_status`, canonical v2 key order, the
closed `{0,2}` idiom) rather than re-implementing it; `gate.py`/`loop.py` are strictly
subprocessed via a clean `SERVO_HEARTBEAT_{GATE,LOOP}_PY` test seam; every subprocess
failure path returns a structured env-error outcome instead of raising, so the serial pass
degrades safely. `run_dispatch`'s control flow is linear and readable, the constants are
well-documented, and the mock-loop harness (config-file-driven, behaviour-keyed by
finding_id) is maintainable and avoids any live `claude -p` call. The issues below are all
minor — no blockers, no dead code, no footguns.

SPECIFIC ISSUES:
- [strength] heartbeat.py `_dispatch_one` — an exemplary per-candidate pipeline: each stage
  (AC3→AC4→AC5→AC6) returns `_env_error_outcome()` with a distinct, source-naming breadcrumb
  instead of raising, so one bad candidate never aborts the serial pass.
- [strength] heartbeat.py `_env_error_outcome` / `_outcome_from_summary` — both emit the
  exact ADR-0010 key order, and the env-error-summary case (empty history → null composite)
  falls out with no special-casing. `OutcomeRecordingTests.test_outcome_shape_and_key_order`
  pins the order.
- [nit → addressed] `_run_gate_json` / `_run_loop` omit `timeout=` (cf. `_run_subprocess` /
  `_is_git_work_tree` / `_git`, all bounded). Both subprocessed tools self-bound (loop.py via
  caps; gate.py via its own 300s oracle timeout). Docstrings now cross-reference the
  self-bound rationale (the gate-preflight case was added in the fix pass).
- [nit → addressed] the closing summary breadcrumb said "dispatched N" even for candidates
  that env-errored before reaching `loop.py`. Reworded to "processed N … (M env-error, no
  loop run)" so it no longer overstates how many candidates looped.
- [nit] heartbeat.py — `_is_git_work_tree(target)` runs once per candidate inside
  `_dispatch_one`; the target's git-ness is invariant across a pass, so it could be hoisted
  to a single pass-level guard. Cheap + harmless; kept for `_dispatch_one` self-containment.
- [nit → addressed] `_format_ceiling` uses `repr(float(value))`; a comment now explains it is
  chosen for the shortest round-trip-safe decimal (loop.py re-parses it).
- [nit] test `_write_mock_loop` — the behaviour knobs (`emit_summary`/`garbage`/
  `empty_history`/`exit_code`) are documented but not a closed set; a future knob typo would
  be swallowed by the `.get(...)` defaults. Test-only, low risk; optional hardening.
