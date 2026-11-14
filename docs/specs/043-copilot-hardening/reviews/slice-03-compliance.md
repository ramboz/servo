---
slice: 043-03 — cross-process resume of a Copilot run
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-14T18:35:51Z
prompt_source: review.py implementation (spec 043-03); R2
---

VERDICT: pass.

All five ACs met and non-vacuously tested (final, post-frame-critique code):
- AC1 (narrowed backend guard allows same-backend copilot resume) — the old
  `any(backend != claude)` is replaced by refuse-on (schema==2 | inconsistent
  discriminators | persisted_backend != host). Covered by the sound-state
  pass-through test (all 4 clean halts reach the version probe) + the e2e headline.
- AC2 (baseline re-established, cumulative continues) — the two-process e2e pins
  final cumulative to 90cr EXACTLY (discriminates reset-to-40 and double-count-to-
  140); the mock reports session-cumulative totalNanoAiu across the process
  boundary via a shared acc file.
- AC3 (ADR-0048 guarantees on a resumed run) — post-iteration ceiling, pre-
  iteration >=30 floor (counter stays at 1 → no second invocation), and fail-closed
  on partial telemetry (cumulative null).
- AC4 (genuine backend change refused both directions) — claude->copilot (new) +
  copilot/native->claude (existing 6-case) all refuse backend_mismatch.
- AC5 (fail closed on (a) unsound value AND (b) non-clean halt) — the
  `if host == HOST_COPILOT:` guard sits after the backend check (so it fires only
  on a true copilot->copilot resume). Empirically reverted the whole guard block:
  BOTH AC5 tests then fail (9 subtest failures), confirming both clauses
  non-vacuous. Value-clause test pins a clean halt; staleness-clause test pins a
  sound value — isolated.

Cross-cutting: host-sync byte-identical across all four loop.py copies;
refinement-todo item 3 honestly resolved (scoped to CLEAN halts, interrupted/killed
fail-closed, resume-after-kill grounding deferred with a trigger); new
`credit_baseline_unavailable` maps to `error` via the total A2 outcome map
(totality test green); no regression across existing resume/accounting classes.
Capability extension within ADR-0048 (no module boundary / public-contract change),
arch_review:false appropriate.

Two non-blocking bookkeeping nits: frontmatter DRAFT (advanced by the lifecycle
transition); pre-invocation fail-closed halts (credit_ceiling_insufficient /
credit_bound_unavailable) are also non-resumable (spec-conformant, fail-closed-safe).

Prompt source: review.py implementation (spec 043-03); round 2 (post frame-critique fix).
