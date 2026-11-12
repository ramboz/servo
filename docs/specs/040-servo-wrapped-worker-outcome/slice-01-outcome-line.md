---
status: DONE
kind: feature
frame_review: true
dependencies: [038-03, 041-02]
last_verified: 2026-11-12
---

## Slice 040-01 — outcome line

**Goal:** `loop.py --outcome-line <path|->` writes one typed outcome record that
a host-spawned worker can forward to its orchestrator in place of a narrative.

**DoR:**
- Activation trigger in spec 040 met.
- loop.py's terminal-reason taxonomy enumerated, and the mapping to
  `passed|plateau|blocked|budget|error` agreed (A2) — see **A2 mapping** below.

## A2 — terminal-reason → `result` mapping (total)

`result` is derived from the summary's `terminal_reason` **and**
`final_oracle_status` (both ride every summary line — `loop.py` `_summary_payload`
/ `_goal_summary`). The map is **total** over loop.py's closed terminal-reason
taxonomy — the `REASON_*` constants plus the three string-literal reasons
`oracle_evaluation_refused`, `native_capability_unavailable`, `backend_mismatch` —
with `error` as the fail-safe default, so the map stays total as the taxonomy
grows. Enumerated against loop.py at the spec 041-02 base (the credit reasons are
041-02 / [ADR-0048](../../decisions/adr-0048-copilot-credit-budget-contract.md)).

Each bucket is the campaign coordinator's reading of the worker's stop (spec 040
anti-horizontal check — one line per worker, not a thread):

- **passed** — the oracle cleared the bar.
- **plateau** — the oracle ran, scored the tree, and stayed below the bar (tried,
  didn't converge).
- **budget** — a resource allowance was exhausted while the oracle *was* scoring;
  raising that resource is the lever (iterations / turns / USD / credits → raise
  the cap; `context_full` → compaction, a larger-context model, or task
  decomposition — the same "resource ran out" family, a different lever).
- **blocked** — an environment / host / permission precondition refused; *fix the
  environment* and retry.
- **error** — a fault, malformed input, or integrity violation; *investigate*.

**Oracle-availability override (keys on `final_oracle_status` + `iterations`).**
The `budget` and `plateau` readings both presuppose the oracle actually produced a
verdict. But `max_iterations_reached` / `oracle_plateau` / `cost_ceiling_reached` /
`context_full` (and the goal `iteration_cap_reached`) are *overloaded* strings:
`loop.py` emits them both for a clean below-threshold stop **and** for a run whose
oracle ran but never produced a valid verdict —
`final_oracle_status ∈ {env_error, unknown_interrupted}`, which the loop itself
halts as `EXIT_ENV_ERROR` with a `required_evidence_unavailable` breadcrumb
(`loop.py` `_finalize` `unavailable` branch, ~`:4105–4117`). A benign budget/plateau
reading is *false* there — more budget cannot help a worker whose oracle didn't
evaluate; the remedy is to fix the oracle/environment. So a `budget`/`plateau`
terminal whose `final_oracle_status` is `env_error`/`unknown_interrupted` is
re-read as **error** (mirroring the loop's own exit code), **gated on a scoring
attempt** (`iterations ≥ 1`): a budget halt that fired *before* any scoring
iteration — a `--credit-ceiling` set below the model's runnable floor halts
`credit_ceiling_reached` at `iterations == 0` with the default `env_error` status
— is a genuine budget stop (remedy: raise the ceiling), not a broken oracle, so it
stays `budget`. `passed` requires a `pass` status and `blocked`/`error` reasons
already carry their meaning regardless, so the override touches only the
budget/plateau buckets. This is the same principle the credit decisions below
apply — unmeasurable ≠ exhausted.

| `result` | `terminal_reason` values (final bucket after the oracle-availability override) |
|---|---|
| `passed` | `oracle_passed` (loop), `oracle_pass` (goal) |
| `plateau` | `oracle_plateau` (loop), `oracle_below_threshold` (goal — clean `EXIT_OK`, below bar) — demoted to `error` when the oracle ran but returned `env_error`/`unknown_interrupted` |
| `budget` | `max_iterations_reached`, `iteration_cap_reached` (goal), `cost_ceiling_reached`, `context_full`, `credit_ceiling_reached`, `credit_ceiling_insufficient` — demoted to `error` when a scoring iteration ran (`iterations ≥ 1`) but the oracle returned `env_error`/`unknown_interrupted`; a pre-scoring starved halt (`iterations == 0`, e.g. a sub-floor `--credit-ceiling`) stays `budget` |
| `blocked` | `edit_permission_unavailable`, `dirty_tree`, `readiness_unapproved`, `readiness_check_unavailable`, `goal_driver_unsupported_host`, `goal_unavailable`, `goal_resume_unsupported` |
| `error` (default) | `interrupted`, `verdict_schema_mismatch`, `claude_invocation_failed`, `gate_invocation_failed`, `gate_vendor_failed`, `oracle_disagreement`, `oracle_evaluation_refused`, `credit_usage_unavailable`, `credit_bound_unavailable`, `target_missing`, `target_not_directory`, `manifest_missing`, `oracle_missing`, `unpriced_components_invalid`, `unpriced_oracle_components`, `state_missing`, `state_schema_mismatch`, `claude_version_mismatch`, `backend_mismatch`, `run_id_collision`, `plan_missing`, `plan_malformed`, `plan_schema_mismatch`, `plan_requires_clamp`, `plan_value_invalid`, `models_invalid`, `native_capability_unavailable`, `detached`, `detach_failed`, **plus** any budget/plateau reason whose oracle ran (`iterations ≥ 1`) but returned `env_error`/`unknown_interrupted` |

`detached` is **taxonomy-only** — it is in the table for totality but is never
emitted as a `result`: the `--background` parent prints a plain `detached` launch
summary (unhooked), and the detached child emits the real outcome via its own
terminal (040-01 forwards `--outcome-line` to the child). `detach_failed` *is*
reachable — a parent spawn failure routed through `_refuse_goal` → `error`.

**Deliberate decisions (the A2 re-enumeration against the current taxonomy):**

- **Oracle-availability override (the two-key rule).** `result` is a function of
  `(terminal_reason, final_oracle_status)`, not `terminal_reason` alone: the
  "clean" budget/plateau reason strings are overloaded across a real
  below-threshold stop and an oracle-never-scored halt that `loop.py` separates by
  `final_oracle_status` + exit code. Reporting a broken-oracle run as `budget`
  would tell a coordinator "give it more room," and it would burn a second full
  budget on a run that cannot score — the wasted-spend failure spec 040 exists to
  kill. So an `env_error`/`unknown_interrupted` oracle status demotes a
  budget/plateau terminal to `error` (see **Oracle-availability override** above).
- The 041-02 credit **ceiling** halts are the credit analogues of
  `cost_ceiling_reached` → **budget**: `credit_ceiling_reached` (spend reached the
  ceiling) and `credit_ceiling_insufficient` (ceiling set below the model's
  overrun bound — the remedy the loop prints is "raise `--credit-ceiling`", i.e.
  *more budget*).
- The 041-02 credit **fail-closed-unmeasurable** halts → **error**, NOT budget:
  `credit_usage_unavailable` (spend could not be measured — a missing/partial
  usage report or a disagreeing span; `cumulative_credits` is reported `null`, not
  "used up") and `credit_bound_unavailable` (the worker model has no shipped
  overrun bound — unverifiable). `budget` must mean a *real* allowance was
  exhausted so a coordinator can trust it as "give it more room"; these two are
  accounting / configuration faults whose remedy is to fix telemetry or the
  model-bound table, so they read as `error` with the catch-all.
- `oracle_below_threshold` (goal driver, clean `EXIT_OK`) → **plateau**, not
  `error`: it is the goal-driver analogue of the loop's below-threshold stop (the
  run ended and the oracle stayed under the bar), not a fault.
- `goal_driver_unsupported_host` / `goal_unavailable` / `goal_resume_unsupported`
  → **blocked**: host-capability / unsupported-mode refusals whose remedy is
  environmental (switch host or `--driver loop`; drop `--resume`), matching the
  sketch's "readiness refusals → blocked" theme.

**Acceptance Criteria:**

1. With `--outcome-line <path|->`, the loop writes exactly one JSON object
   (`servo_outcome: 1`) after its terminal summary — to `<path>`, or to stdout for
   `-`. Without the flag, stdout is **byte-identical** to today (stderr unchanged).
2. `result` is derived only from the summary's `terminal_reason`,
   `final_oracle_status`, and `iterations`, per the **A2 mapping** above (total;
   `error` is the default; a budget/plateau terminal whose oracle ran
   (`iterations ≥ 1`) but returned `env_error`/`unknown_interrupted` is demoted to
   `error`, while a pre-scoring starved halt stays in its bucket). The original
   `terminal_reason` is preserved verbatim as `reason`.
3. The record carries: `rung` / `rungs` from spec 038's escalation ladder
   (`rung: 0`, `rungs: 1` when no ladder is configured); `iterations` (the loop
   driver's `iterations_completed`, the goal driver's `num_turns`); `cost_usd` (the
   run's `cumulative_cost_usd`, which spec 038 made accurate); `composite` /
   `threshold` (the final oracle reading, `null` when none); and `run_id` (already
   on the summary line). Fields degrade to `null` when the summary lacks them (a
   preflight refusal has no oracle score or run dir).
4. Both drivers emit it. The goal driver reports `rung: 0`.
5. Documentation (SKILL.md and all host copies) shows a host forwarding the line (a
   Claude Code `claude -p` example) and restates the no-`/servo:crew`, no-fan-out
   boundary (spec 040 Boundaries): the loop only *renders* its existing summary;
   the host owns the worker tree.

**Scope (040-01 only):** the outcome line. The content fingerprint at halt (HEAD +
diff + untracked) that spec 042's campaign verifier needs is scoped to **042-04**
(host-driven verified-wrapped), not here; the line owes the verifier only
`run_id`, which it already carries.

**DoD:** ACs pass; reviews per spec-workflow.

**Anti-horizontal-phasing check:** a campaign coordinator receives one line per
worker (passed / plateau@rung / blocked, plus cost) instead of a message thread.

### Deviation log (after reconciliation)

Original ACs preserved above. Deviations and load-bearing choices made during
implementation:

- **A2 is keyed on `(terminal_reason, final_oracle_status, iterations)`, not
  `terminal_reason` alone** (the sketch's AC2). The pre-implementation
  frame-critique proved the reason string overloaded: `max_iterations_reached` /
  `oracle_plateau` / `cost_ceiling_reached` / `context_full` / goal
  `iteration_cap_reached` are emitted both for a clean below-threshold stop
  (→ budget/plateau) and for a run whose oracle ran but never scored
  (`final_oracle_status ∈ {env_error, unknown_interrupted}`, which loop.py halts
  `EXIT_ENV_ERROR`). The map demotes those to `error`, **gated on a scoring
  attempt** (`iterations ≥ 1`) so a pre-scoring starved budget halt (e.g. a
  sub-floor `--credit-ceiling` halting `credit_ceiling_reached` at
  `iterations == 0`) stays `budget`. The gate addressed a non-blocking
  frame-critique note and removed an internal inconsistency with the
  `credit_ceiling_reached → budget` decision.
- **Credit-reason buckets (the 041-02 taxonomy growth the sketch predates):**
  `credit_ceiling_reached` / `credit_ceiling_insufficient` → `budget` (credit
  analogues of `cost_ceiling_reached`; remedy "raise `--credit-ceiling`");
  `credit_usage_unavailable` / `credit_bound_unavailable` → `error` (spend/bound
  *unmeasurable*, `cumulative_credits` null — not "exhausted"; remedy is to fix
  telemetry / the model-bound table).
- **Emission: one outcome line per terminal summary, at every terminal path** —
  hooked inside `_finalize_state_and_summary` (loop driver), the goal driver's
  `_finalize` closure, and the five refusal helpers (`_refuse_preflight`,
  `_refuse_copilot_capability`, `_refuse_plan`, `_refuse_readiness`,
  `_refuse_goal`). The per-iteration line and the `--background` parent's
  `_detach_summary` are deliberately NOT hooked: the former is not terminal, the
  latter would mislabel a successful `detached` launch as `result: error`.
- **`--background`: `--outcome-line` is forwarded to the detached child**
  (`_build_detached_child_argv`), which owns the real terminal, so it writes the
  one record at its halt. Sinks differ by mode: `--outcome-line <path>` → the
  child writes the file (poll it beside `state.json`); `--outcome-line -` → the
  child's stdout = the run-dir `background.log`, NOT the parent's captured stdout
  (the parent prints only the `detached` launch summary). A spec-042 campaign host
  wiring a background worker should prefer the **`<path>`** form. (A review found
  this documented-but-unwired; the fix made the SKILL.md contract true.)
- **Module-global sink `_OUTCOME_LINE_TARGET`**, set once in `main()`, read by
  `_emit_outcome_line` / `_build_detached_child_argv`. Intentional — avoids
  threading a parameter through every halt signature; self-resets on each
  `main()` call (unconditional assignment), so repeated in-process calls are safe.
- **`cost_usd` is `null` under `--host copilot`** (spec 041 tracks spend in
  credits, not USD). The record keeps spec 040's fixed field set (no schema
  extension); the SKILL.md notes the credit spend lives in `state.json`
  (`cumulative_credits`), which a campaign ledger re-derives by `run_id` anyway.
- **No content fingerprint.** Deferred to **042-04** (host-driven
  verified-wrapped); the stale `spec.md` "042-03" wording was corrected inline
  (live prose, ADR-0010).

### Reconciliation sweep

Drift-prone surfaces checked:

- **Host packages (4× `loop.py`, 4× `SKILL.md`)** — `updated`: regenerated via
  `scripts/build_host_packages.py`; the four `loop.py` copies are byte-identical
  and the sync-gate (`scripts/test_build_host_packages.py`) is green.
- **`skills/agent-loop/SKILL.md`** — `updated`: new "Outcome line" section (host
  forwarding example + no-`/servo:crew`/no-fan-out boundary, AC5), Options-table
  row, accurate `--background` behaviour, and the Copilot `cost_usd` note.
- **`skills/agent-loop/test_loop.py`** — `updated`: TDD coverage for the A2 map
  (totality + override + starved exception), the record shape, emission (stdout /
  file / byte-identical no-flag), both drivers, and the `--background` forwarding.
- **`docs/specs/040-.../reviews/`** — `new` (process artifact, not landed
  behaviour): the recorded review evidence (frame-critique, compliance, craft,
  reconciliation verdicts).
- **`docs/specs/040-.../spec.md` Consumer section** — `updated`: corrected the
  stale fingerprint ownership ("042-03" → "042-04"; the fingerprint is not
  040-01's).
- **Architecture impact** — `no-op`: no module boundary or public-contract change
  — one additive CLI flag plus pure rendering helpers; the loop stays
  trigger-agnostic (spec 040 Boundaries). No new ADR (the mapping decision lives
  in the A2 section and references ADR-0048 / ADR-0049). No new `TODO`/`FIXME`.
- **Leanness** — `no-op`: nothing beyond the ACs — no content fingerprint
  (deferred to 042-04), no credit-field schema extension, no speculative config.
- **Glossary / memory / inbox / conventions** — `no-op`: no new domain terms,
  rules, or inbox items.
- **Close-out (spec 040 closes — 040-01 is its only slice)** — `no-op`: the
  primer surfaces (`CLAUDE.md`, `AGENTS.md`) carry no active spec-040 section to
  compress.
