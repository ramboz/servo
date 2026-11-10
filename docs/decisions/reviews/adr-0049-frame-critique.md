---
adr: 0049
pass: frame-critique
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T22:30:06Z
prompt_source: review.py frame-critique docs/decisions/adr-0049-campaign-orchestration.md
---

VERDICT: needs-changes

REASONING:
Round 1. Riskiest assumption: host-driven Copilot workers get per-node discipline. But the ADR also says host-driven Copilot is "attended" and not blocked by ADR-0048, so those workers never run under loop.py: servo enforces only a prose brief and an oracle re-check of claimed passes. OQ3 ("would have changed the recorded run") rests on that contradiction; A1 and the kill criteria aim at the wrong risk.

SPECIFIC ISSUES:
- [spec] No in-flight brake for host-driven Copilot workers; contradicts ADR-0048 ("precondition for host-driven campaigns"); self-reported ledger fields summed into the aggregate ceiling; "attended" mislabels unwatched host-spawned children; Option B is a straw man vs the new always-loaded campaign instructions. Fix: wrapped (loop.py, enforced) vs advisory (verified passes + ledger, self_reported fields) tiers; no route around ADR-0043.
- [spec] A1 tests forwarding, not adoption (the host orchestrate skill won routing) -> restate as adoption with a firing kill criterion.
- [spec] Unstated: whether campaign items can be oracle-gated (motivating run had no .servo/) -> A4 + kill criterion.
