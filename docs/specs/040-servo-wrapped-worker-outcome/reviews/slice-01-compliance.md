---
slice: 040-01 — outcome line
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-12T18:42:10Z
prompt_source: review.py implementation docs/specs/040-servo-wrapped-worker-outcome/spec.md 040-01
---

VERDICT: pass (re-review, after the revision resolved the round-1 `needs-changes` blocker)

Round 1 (`needs-changes`): the SKILL.md `--background` paragraph (+ 3 host copies)
promised outcome-line behaviour the code never wired — `_build_detached_child_argv`
did not forward `--outcome-line` to the detached child and the parent's
`_detach_summary` was (correctly) unhooked, so `--background --outcome-line …`
silently produced no outcome line. The foreground ACs were all verified MET.

Round 2 (PASS): the blocker is resolved via option (a). `_build_detached_child_argv`
now appends `["--outcome-line", _OUTCOME_LINE_TARGET]` guarded by
`if _OUTCOME_LINE_TARGET is not None`, so the detached child — which owns the real
terminal — emits the one record at its halt via the already-correct foreground
path, while the parent's `_detach_summary` stays unhooked (a successful `detached`
launch is never mislabeled `result: error`). SKILL.md and all 3 host copies now
describe this accurately. All 23 outcome tests pass, including the new end-to-end
`test_background_child_writes_the_outcome_file` (spawns a real detached child,
asserts the parent emits no outcome line, polls the file). The foreground contract
(byte-identical no-flag, total map + oracle-availability override, record shape,
both drivers) remains intact.

Regressions attacked, none found: relative `--outcome-line` path resolves
identically for parent and child (Popen inherits cwd); argv is a list (no shell
injection); the global is set in main() before the `--background` route; the new
tests are non-vacuous and non-flaky.

Foreground AC verification (all MET): AC1 `_OUTCOME_LINE_TARGET is None` gate +
byte-identical test; AC2 total map via `else: error` + override gated on
`(iterations or 0) >= 1 and status in {env_error, unknown_interrupted}`, swept over
every REASON_* + the 3 literals + unknown across all statuses and iterations∈{0,2};
AC3 exact field set/order, loop composite via last-scored `oracle_score_history`,
goal via flat `oracle_composite`, nulls on preflight; AC4 both drivers + the five
refusal helpers emit exactly once, per-iteration + detach-launch correctly
excluded; AC5 `claude -p` forwarding example + no-/servo:crew/no-fan-out boundary.

Principles check: aligns with "evaluation before execution" (result keys on oracle
verdict; the override privileges oracle availability over an overloaded reason
string). No new TODO/FIXME.

Reviewer: general-purpose subagent (read-only), two rounds.
