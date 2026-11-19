---
adr: 0050
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-19T16:14:47Z
prompt_source: review.py frame-critique docs/decisions/adr-0050-eval-is-signal-not-evaluability.md (4 fresh rounds)
---

Frame-critique ran FOUR rounds against fresh, independent reviewers, each verifying grounding against the real code. The decision — reject Option B: the stochastic vision judge never satisfies `n_evaluable` — held through all four rounds; each round caught a real, distinct implementation-mechanism defect, corrected before the next:

- **R1 (needs-changes):** the originally-recommended deterministic-AC rung is only presence/text on a design target (fidelity ACs classify `residual_judgment`) — orthogonal to fidelity. Reshaped toward crediting the deterministic fidelity check.
- **R2 (needs-changes):** that check is the static-source-contract observer, which per ADR-0046 is a component-agnostic REQUIRED-POLICY check (`family: command`), NOT an `install.json` component; the only fidelity component there is the stochastic judge. Re-anchored Option C on reading the required-runtime check plan.
- **R3 (needs-changes):** `n_evaluable` is per-SPEC but the static `checks.json` is per-TARGET, so an unqualified credit would pass an unrelated all-residual spec on an instrumented target — reintroducing B's false pass. Added spec-attribution as a load-bearing constraint; stated the decision as three constraints (deterministic, spec-attributed, judge-excluded) and deferred the integration to the implementing slice.
- **R4 (PASS):** the spec-attribution constraint is satisfiable (the vellum single-redline-per-target identity, or an explicit binding the slice adds) — not provably impossible; the deferral is honest, backstopped by the fully-specified Option A fallback and the first Kill criterion.

Verified-held across rounds: reject-B is sound (the ADR-0033 0.7998/0.80 field report + ADR-0036 self-reported-`reviewed` residuals are real); the static-source-contract check is a genuine deterministic fidelity floor (renders via Chromium, compares computed CSS within tolerance); the required-runtime plan is reliably readable at a fixed path; the judge is cleanly excluded.

Applied before recording this pass (R4 secondary, non-blocking): corrected the attribution-handle example — attribution is via the single-redline-per-target identity or an explicit new binding, NOT the static contract's own `source_spec_path`/`spec_id` (synthetic redline literals that collide in name with the feature-spec `source_spec_path`).

Verdict: **pass.** The decision and its three constraints are sound; the exact integration is the implementing slice's load-bearing work, under test. Acceptance (`adr.py accept`) remains the owner's call.
