---
slice: 042-01 — plan and ledger
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-12T20:50:04Z
prompt_source: review.py implementation docs/specs/042-campaign-orchestration/spec.md 042-01 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md
---

VERDICT: pass (round 2 re-verification; round 1 also pass with one MINOR note)

Round 1: all four ACs verified MET; no vacuous tests (fail-closed tests assert the
campaign dir is ABSENT, the concurrency test asserts all 10 run_ids land, the parity
test compares against loop.py's actual `_validate_models`). One MINOR note —
`_validate_outcome` did not independently require `rung`/`reason` (AC2 enumerates them);
kept lenient on purpose (over-strict gating could reject valid future 040 lines) and
logged in the deviation log.

Round 2 (after the cost-unit fix, `--tier` restriction, ledger guard, credit marker):
AC1–AC4 remain MET, AC3 additionally hardened. Independently confirmed the AC2 cost-unit
fix against loop.py — `_refuse_preflight`/`_refuse_plan`/`_refuse_readiness`/`_refuse_goal`
hardcode `cumulative_cost_usd: 0.0` regardless of host (1365/1419/1523/4552) while Copilot
nulls it in normal operation (1137) and the outcome `cost_usd` derives from that field
(1283), so a legitimate credit/Copilot preflight refusal really does emit `cost_usd: 0.0`;
the new rule (USD rejects null; credit rejects positive; 0.0 accepted either way) records
it instead of dropping it, and genuine misroutes (null-on-USD, positive-on-credit) still
refuse rc=2 with the ledger unchanged. `--tier` gated to {servo, advisory}; `wrapped`
stays in the schema + enforced-spend accounting for 042-04's verifier. `_read_ledger` now
makes `status` fail closed rc=2 on a corrupt line. Non-vacuous: reverting each fix fails
its pinned test. The round-1 unreachable edge (negative cost_usd accepted) was
subsequently closed by a `_validate_outcome` guard rejecting cost < 0.

Reviewer: general-purpose subagent (read-only), two rounds.
