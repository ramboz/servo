---
adr: 0049
pass: frame-critique
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T22:32:13Z
prompt_source: review.py frame-critique docs/decisions/adr-0049-campaign-orchestration.md (round 2)
---

VERDICT: needs-changes

REASONING:
Round 2. Round-1 findings resolved (honest advisory tier; no "attended" route around ADR-0043; ADR-0048 consistent; Option B real; A1 adoption; A4 oracle coverage). The highest-risk assumption moved into the wrapped tier: brakes bind only the loop.py subprocess a host-spawned (unbraked) worker chooses to start, and campaign record could not tell a real loop line from a hand-written one.

SPECIFIC ISSUES:
- [spec] Wrapped must be verified, not declared (run_id + tree fingerprint at halt); wrapper-session spend and post-halt edits fall outside every ceiling; add A5 worker compliance + kill criterion; soften OQ3.
- [spec] Wrapped-on-Claude likely dominated by servo-driven mode on the same host — order servo-driven first.
- [spec] Stale lines: Consequences tierless claim; spec 042 "unattended" wording; slice 042-01 AC2 ledger lacks tier/self_reported.
