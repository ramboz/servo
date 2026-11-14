---
slice: 043-01 — refuse known-USD-priced oracle components under Copilot
pass: arch
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-14T01:41:02Z
prompt_source: review.py arch-review spec.md 043-01 loop.py test_usd_priced_oracle.py --non-interactive --richer-skill none
substrate: non-interactive
---

VERDICT: pass (round 1)

All five architectural questions resolve in the implementation's favor. Module
boundaries in `docs/architecture.md` are preserved; all three host trees vendored
byte-identically. Only non-blocking maintainability/doc nits remain.

Strengths (load-bearing decisions, all correct):
- Correct host discriminator: the gate keys on `host == HOST_COPILOT`, not
  `cost_ceiling is None`. Under `--host copilot` `--cost-ceiling` is a hard parser
  error so cost_ceiling is always None there; a `--host claude` run that omits
  `--cost-ceiling` ALSO reaches the gate with cost_ceiling None (defaulted to the
  USD default only later), so a ceiling-keyed discriminator would false-refuse an
  ordinary claude run and regress AC4. Host-keying is the only correct choice.
- Clean reader/policy split riding the existing `_refuse_preflight` contract
  (same summary shape, rc=EXIT_ENV_ERROR, spec-040 outcome-line).
- Correct precedence (usd_priced after the host-agnostic unpriced preflight, so
  ADR-0041's stricter rule wins when both present — AC5) + system-wide chokepoint
  coverage: `main`→`run_loop` forces the loop driver under copilot, direct
  programmatic entry hits the same gate, and campaign dispatch launches `loop.py`
  subprocesses that re-enter through it; `_invoke_copilot` has no caller outside
  run_loop.
- Sound deferral boundary: shipping reader+refusal while deferring the auto-writer
  is not horizontal phasing — the marker has a working writer today (hand-edit /
  explicit registration), the refusal fires end-to-end from a seeded manifest,
  servo ships no USD-priced component so there is no auto-producer to mirror, and
  pulling in fidelity_eval.py's knob now would be premature generality. Replays
  ADR-0041's guard-vs-registrar slice split.

Nits (non-blocking, logged):
- Within-file reader duplication (~80% copy of `_unpriced_oracle_error`);
  defensible at two markers (ADR-0041 clause 6 sets the extraction bar at a third
  client) but the validator now spans 8 copies — a third marker or validator fix
  should trigger extraction.
- run_loop comment imprecision (`--emit-routine-prompt` is not *refused* under
  copilot, it runs no oracle) — corrected to "runs no oracle".

Open question (out of scope, future ADR-0005 revisit, not a gate on 043-01):
under `--host claude --cost-ceiling 0` the cumulative USD ceiling is DISABLED, yet
a usd_priced component proceeds — is ADR-0005 clause 6 sufficient to bound a
USD-priced oracle when the cumulative ceiling is disabled, and does such spend
flow into `total_cost_usd`? Undecidable (servo ships no USD-priced component); the
slice correctly scopes claude as unchanged.

Nothing blocks the REVIEWED transition.
