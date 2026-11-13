---
slice: 042-03 — host-driven advisory
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-13T02:51:00Z
prompt_source: review.py pr-review docs/specs/042-campaign-orchestration/spec.md 042-03 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md skills/heartbeat/heartbeat.py --richer-skill none --non-interactive
substrate: not-shown
applied_skill: none
---

VERDICT: pass

REASONING:
The slice faithfully implements its scope: `campaign brief` emits per-item data-framed
kickoff briefs, `cmd_record --tier advisory` re-runs the oracle via heartbeat's canonical
`_run_gate_json` before accepting a claimed pass and downgrades unconfirmed passes, every
non-result field stays tier-derived `self_reported` with cost excluded from enforced
spend, and the runaway limit is disclosed in both brief and status. Logic is correct,
fail-closed, and well-structured; the re-check runs before the ledger flock (no lock held
during a slow oracle); all three vendored host copies carry the new code byte-identically.

SPECIFIC ISSUES:
- [nit][impl] the AC5 no-spawn record/brief tests were vacuous (RUNNER_RAN sentinel never
  produced by the stub) — hardened in R2 to assert a real no-spawn trace.
- [nit][impl] on a downgrade, `outcome.reason` keeps the host's self-reported value next to
  servo's overwritten `result`; authoritative verdict is in `oracle_recheck`. Logged.
- [nit][impl] `_load_heartbeat` docstring omitted the re-check's new dependency — fixed.
- [strength][impl] re-check runs before the blocking ledger lock; canonical `_run_gate_json`
  reuse (fresh run_id, no worker-supplied verdict trusted); real-`gate.py` integration tests.

RECONCILIATION NOTES:
- Delimiter-injection in the brief's UNTRUSTED block is unmitigated, consistent with the
  pre-existing `_build_item_prompt` framing it mirrors; no new risk. Host-parity confirmed.
