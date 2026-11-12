---
slice: 041-02 — credit brake and supported loop launch
pass: reconciliation
verdict: pass
reviewer: build-session reconciliation (cites jig:reviewer compliance+craft+arch pass)
reviewed_at: 2026-11-12T01:26:38Z
prompt_source: ADR-0014 §5 reconciliation sweep
---

VERDICT: pass

Reconciliation of 041-02 (the Copilot AI-credit brake — a feature slice: code +
tests + docs).

DEVIATION LOG — attested. Each deviation is beneficial or fail-closed: the
REACTIVE bound guard (the admin-pinned worker model is unknown pre-launch,
041-01), the shipped per-model bound table (an unknown model fails closed), AC7 =
refuse a `--models` block whole, `aiCreditsStatus` as the primary partial gate
with the OTel Σ reconciled against the session-DELTA on resume, USD fields null
under Copilot, a Copilot invocation failure mapped to `credit_usage_unavailable`,
and AC6 oracle-USD via the existing unpriced-components preflight. Three
fail-closed deferrals (plan-sourced ceiling, known-USD-priced oracle refusal,
cross-process resume) are recorded in the deviation log + refinement-todo, each
surfaced by the independent compliance review.

RECONCILIATION SWEEP — attested. Artifacts are consistent: `loop.py` (Claude path
byte-identical, Copilot additive), `test_loop.py` (unit tests on real 041-01
evidence + e2e subprocess runs; full suite green), agent-loop `SKILL.md` +
`architecture.md`, and regenerated host packages (`--check` in sync). All seven
ACs are implemented and tested; the three `needs-changes` items from the
compliance review are resolved (oracle-refusal test added, docstring fixed,
deferrals documented).

No unresolved fail-open path; DoD met (modulo the documented fail-closed
deferrals). Note: the branch must be rebased onto origin/main before landing.
