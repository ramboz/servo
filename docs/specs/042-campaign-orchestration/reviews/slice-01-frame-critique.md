---
slice: 042-01 — plan and ledger
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-12T20:50:04Z
prompt_source: review.py frame-critique docs/specs/042-campaign-orchestration/spec.md 042-01 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md
---

VERDICT: pass (round 2; round 1 was needs-changes — one real bug + one gap)

Round 1 (needs-changes): the plan + append-only ledger + status approach is sound and
stands alone (A4 verified structurally). PRIMARY (load-bearing, FALSE against loop.py):
AC2's rule that an outcome's budget denomination is recoverable from `cost_usd` null-ness
("null ⇔ credit/Copilot, numeric ⇔ USD") is false — loop.py's refusal/preflight helpers
hardcode `cumulative_cost_usd: 0.0` regardless of host, and `_unpriced_oracle_preflight` is
host-agnostic, so a legitimate credit/Copilot run that halts at a preflight emits numeric
`cost_usd: 0.0`; the old rule rejected it rc=2 and dropped it from the ledger (reproduced
live with `unpriced_oracle_components` on a credit item — exactly the unbraked-Copilot stop
ADR-0049 exists to capture). The symmetric direction (USD → null) was checked and is safe.
SECONDARY: AC2 promises "servo and VERIFIED wrapped", but `record --tier wrapped` was a
trusted self-assertion counted as enforced spend with no verifier until 042-04.

Round 2 (pass, verified against source + live repro): both resolved. `_cost_unit_error` now
keys only on the reliable signals — `cost_usd is None` ⇒ credit (wrong unit on USD),
`cost_usd > 0` ⇒ real USD spend (wrong unit on credit), `0.0` accepted on either — sound and
total against loop.py's emission behavior, so no real outcome is dropped and genuine
misroutes still refuse. The exact round-1 case now records rc=0; credit+0.42 and USD+null
still rc=2. `--tier` gated to {servo, advisory}, closing the wrapped self-declaration path
while the ledger vocabulary + accounting stay 042-04-ready — now MORE faithful to "verified
wrapped". A4 note addressed: `status` marks credit items ("spend tracked in AI credits,
re-derived in 042-04") instead of implying $0. No new exposure (0.0 on a credit item adds
nothing to enforced spend). needs-changes cleared.

Reviewer: general-purpose subagent (read-only; adversarial frame-critique), two rounds.
