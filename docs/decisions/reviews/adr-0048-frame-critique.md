---
adr: 0048
pass: frame-critique
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T20:09:04Z
prompt_source: review.py frame-critique docs/decisions/adr-0048-copilot-credit-budget-contract.md (round 2)
---

VERDICT: needs-changes

REASONING:
Round 2. All round-1 findings addressed; direction sound. Riskiest remaining: A6's "single-threaded => k = 1" — tool denial can block subagents but not compaction (background model work that fires near full context, exactly when the crossing call is largest), and the short 041-01 probe would never reach it.

SPECIFIC ISSUES:
- [spec] Bound restated as (1 + c) x per-call max with c = 1 (compaction) unless observed otherwise; per-call max priced at max(input, cache-write) x window; spawning not deniable -> refuse (no observed-k fallback).
- [spec] Kill line measured a different quantity (overrun vs 1x cap) -> now compares overrun to the stated bound; 041-02 emits overrun_exceeds_bound so later runs can trigger it.
- [spec] Derived partial check could not see per-call partials from per-model JSON -> per-call OTel nano_aiu is the source; A5 kill fires if unavailable for -p runs.
