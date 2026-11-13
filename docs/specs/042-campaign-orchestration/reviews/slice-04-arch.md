---
slice: 042-04 — host-driven verified-wrapped
pass: arch
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-13T05:43:12Z
prompt_source: review.py arch-review --richer-skill none --non-interactive docs/specs/042-campaign-orchestration/spec.md 042-04 skills/agent-loop/loop.py skills/heartbeat/campaign.py skills/agent-loop/test_loop.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md docs/architecture.md
substrate: non-interactive
---

VERDICT: pass (round 1)

Sound architecture. The dependency-free skill invariant is preserved: campaign.py
reaches loop.py only via the established dynamic loader (`_load_fingerprint_fn` ->
loop.py's OWN `_content_fingerprint`), so the halt record and the verifier's
recompute are one implementation with no drift. All touched contracts (loop
state.json additive fields, the ledger entry's `wrapped_verification`, the
persisted wrapped-brief record) are updated in the same change-set, and the docs
gap that blocked the 042-03 arch pass is CLOSED (architecture.md adds a full
042-04 paragraph; SKILL.md documents the tier, the loader boundary and the AC6
disclosure). Lean design — every fingerprint component is load-bearing,
verification fails closed, no speculative abstraction.

Nit (FIXED): the `_state_cost`/`_status_summary` comments said credit spend is
"re-derived in 042-04" while the shipped behavior records `cost_usd: null`;
corrected to the per-run 041-02 brake framing (matches architecture.md).

Reconciliation notes (settled residuals, recorded in the deviation log):
- AC6 wording vs credit: for the credit/Copilot case the entry records
  cost_usd=null so it never enters `enforced_cost_usd` (USD-only); the enforced
  ROW exists (tier=wrapped, self_reported=false) and the actual bounding is the
  per-run 041-02 credit brake, not a campaign-level credit aggregate (aggregate
  ceilings are deferred to 042-05). Coherent and documented.
- Threat-model boundary: verification is not adversarial-proof (a worker
  controlling its worktree can forge a self-consistent state.json). Now
  explicitly scoped to the honest-worker model (ADR-0049 A5) in the slice,
  architecture.md, SKILL.md and the code docstrings; the kill-criterion covers
  honest non-compliance, not forgery.
