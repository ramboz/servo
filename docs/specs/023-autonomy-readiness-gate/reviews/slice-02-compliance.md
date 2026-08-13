---
slice: 023-02 — loop.py readiness preflight (the two unattended surfaces)
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-08-12T19:49:07Z
prompt_source: review.py implementation docs/specs/023-autonomy-readiness-gate/spec.md 023-02 (re-review after fail-closed-coverage fix)
---

VERDICT: pass

REASONING:
All five ACs hold and are exercised by non-vacuous, per-AC tests. The previously-missing
fail-closed branch is now closed end-to-end: `ReadinessBackgroundGateTests
.test_refuses_when_the_readiness_check_itself_fails` (and its `--emit-routine-prompt` sibling)
drives a missing target through `main()` so `readiness.py check` returns a real rc=2, asserting
rc=2 + `terminal_reason=readiness_check_unavailable` + `target_missing` breadcrumb + no run dir /
no `/goal` emission — a genuine end-to-end refusal, no monkeypatching. Red-capability confirmed
independently by deleting the `if readiness_rc != 0:` branch (loop.py:3405-3415): both tests
fail. The guard is correctly ordered (after flag-shape validation guaranteeing `args.prompt`
non-None on both gated surfaces, before the emit/detach handlers); the detached child re-exec is
exempt by construction; the subprocess consumes `check` rather than re-deriving `_goal_id`; and
the new `(rc, detail)` return preserves fail-closed semantics (rc=1 → unapproved, everything-else
→ unavailable) with a bounded stderr detail — verified by `ReadinessCheckDetailUnitTests`. No
design-principle violation; disclosed emit-time-only limit recorded in refinement-todo.md:781-787.

SPECIFIC ISSUES:
(none blocking)

RECONCILIATION NOTES:
- Fill the slice's Deviation log + Reconciliation sweep during RECONCILED: record the
  `(rc, detail)` widening of `_readiness_check_rc` (bare `int` → `tuple[int, str]`) and the
  `ReadinessCheckDetailUnitTests` addition as the response to the prior fail-closed-coverage
  finding; note the test-harness seam (`_run_loop`/`_run_raw` default `SERVO_READINESS_GATE=0`).
- DoD item 5 (disclosed emit-time-only limit) satisfied via refinement-todo.md:781-787.
- Close-out items (README/product-vision note; status-board regen) remain post-DONE.

NOTE (audit trail): this pass supersedes an earlier `needs-changes` verdict on the same slice
whose single High finding — the untested fail-closed `readiness_check_unavailable` branch — was
addressed by the fix-up round (2 end-to-end tests + 5 unit tests, shown red-capable) before this
re-review.
