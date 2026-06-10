---
status: DONE
dependencies: []
last_verified:
---

## Slice 001-02 — template-content

**Goal:** Replace the placeholder `oracle.sh` with a real weighted-composite template: configurable component blocks, threshold gate, normalized exit codes (0 pass / 1 below-threshold / 2 env error), and a documented `# SEED:` annotation convention for project-specific signal functions. End-to-end value: the generated `oracle.sh` is actually useful (composes signals into a score), not just a stub.

**DoR:**
- ✅ Slice 001-01 DONE
- ✅ Exit-code convention agreed (0 / 1 / 2)
- ✅ Weight schema agreed (component name → weight float; threshold float)

**Acceptance Criteria:**

1. **Scaffolded `oracle.sh` runs.** Against a target with at least one detected component, the scaffolded script exits 0, 1, or 2 (never another code) and prints a single-line composite-score summary.
2. **Threshold gate works.** With `THRESHOLD=1.0` and one component scoring 0.0, the script exits 1. With `THRESHOLD=0.0` and the same input, it exits 0.
3. **Env error is distinguishable from below-threshold.** If a component's command isn't installed, the script exits 2 (not 1) and prints which component is missing.
4. **`# SEED:` blocks are clearly demarcated.** The template includes at least one `# SEED:start <name>` / `# SEED:end <name>` block with a placeholder shell function, and the README section explains how a project adds their own.
5. **No bashisms-that-bite.** Script passes `shellcheck` with severity ≥ warning silent.

**DoD:** _(same shape as 001-01)_
- [x] All ACs pass; full test suite green. _23/23 in `test_scaffold.py` (1 skipped → re-verified via Docker shellcheck)._
- [x] Test coverage per AC: AC1→`WeightedCompositeTests`, AC2→`ThresholdGateTests`, AC3→`EnvErrorDistinguishableTests`, AC4→`SeedBlockTests` + `SeedDocumentationTests`, AC5→`ShellcheckTests`.
- [x] Deviation log produced under this slice heading.
- [x] Reviewer subagent review. _jig:reviewer agent, 2026-05-15 — PASS-WITH-CAVEATS. Two non-blocking deferrals tracked in `docs/refinement-todo.md`._
- [x] Implementation review passed.
- [x] Reconciliation review passed. _Reviewer evaluated deviation log; two minor gaps (quoted command-string dispatch; `set -e` interaction) added post-review._
- [x] `docs/refinement-todo.md` updated. _New entries: shellcheck-skip-on-dev-box; patched-template env-error test; threshold-default-of-0.5._

### Close-out (post-DONE)

- [x] Architecture doc's "open question" about weighting heuristic resolved (or moved to ADR). _Resolved in-line in `docs/architecture.md`: weighted average, equal-weight default, tuning deferred to 001-04's refinement-todo._

**Anti-horizontal-phasing check:** After this slice, the generated oracle is something a project could actually adopt — not a phase that needs slice 003 to be useful.

### Deviation log (after reconciliation)

**Slice 001-02 — implemented 2026-05-15.** 23 tests green (1 skip → shellcheck-via-Docker confirms warning-clean separately). Dogfood smoke covers all three exit paths:
- Default → `composite=1.0000 threshold=0.5 exit=0`
- `THRESHOLD=1.0 PLACEHOLDER_SCORE=0.5` → exit 1
- Missing-tool injection → exit 2 + "missing components: placeholder" on stderr

Deviations from spec text:
- **Composite is a weighted *average***, not a weighted sum. Picked so any `THRESHOLD` in `[0, 1]` remains meaningful regardless of how many components are registered. Recorded in `docs/architecture.md` "Open questions".
- **Default `THRESHOLD=0.5`** chosen as the placeholder default (spec didn't dictate a value). 001-04 will surface this in `refinement-todo.md` per its AC #2 ("Threshold default is flagged").
- **`PLACEHOLDER_SCORE` env hook** added to the placeholder component so tests and dogfood smokes can vary the score without re-editing the template. Documented in the template's comment.
- **shellcheck verification ran via Docker** (`koalaman/shellcheck:stable`) since the local Homebrew install is missing the binary. The test class `ShellcheckTests` skips when the binary is absent; CI / future runners with shellcheck installed will exercise it directly.
- **`scaffold.py` unchanged** — template copy-verbatim still satisfies this slice. Component injection by signal-detection is 001-03's job.
- **Quoted command-string dispatch** (added during reviewer pass): the driver invokes each component via `score="$("score_${name}")"` — a quoted-string command form that bash resolves by expanding the variable, then executing the resulting token as a command. Functionally correct but unconventional; preferred over `eval` because it doesn't require escaping. If a future refactor splits per-component scripts out of the single template, this dispatch shape will go away.
- **`set -e` interaction with scoring functions** (added during reviewer pass): the driver wraps each invocation in `if score="$(...)"; then ... else rc=$?; ... fi`. Under `set -e`, this `if` context is a "tested command" — non-zero exits don't abort the script. Correct today; future component authors writing complex `score_*` functions need to be aware that *their* function still runs under `set -e` (inherited from the script), so internal command failures may abort the function before it can `return 2`. README's "Adding a component" example shows the `command -v ... || return 2` idiom that avoids this trap.

**Open follow-ups (tracked in [docs/refinement-todo.md](../../refinement-todo.md)):**
1. Shellcheck verification falls back to skip on dev machines without local binary.
2. Env-error test patches the template — should drive a real shipped component once 001-03 lands.

**Reviewer verdict:** PASS-WITH-CAVEATS (independent review, jig:reviewer subagent, 2026-05-15). ACs substantively met; both caveats are tracked deferrals, not blockers for this slice.

---

