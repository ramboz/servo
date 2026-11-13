---
slice: 042-03 — host-driven advisory
pass: arch
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-13T02:51:01Z
prompt_source: review.py arch-review docs/specs/042-campaign-orchestration/spec.md 042-03 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md skills/heartbeat/heartbeat.py --richer-skill none --non-interactive (round 2)
substrate: not-shown
applied_skill: none
---

VERDICT: pass (round 2)

REASONING:
The architecture is coherent and lean. Advisory mode is added purely in campaign.py + docs,
reusing heartbeat.py's canonical `_run_gate_json` read-only (heartbeat.py genuinely
unmodified) via the same lazy `spec_from_file_location` load 042-02 uses — the correct DRY
boundary, test-guarded against static import and confined to the advisory-`passed` branch so
042-01's hot-path-off-heartbeat invariant holds. The three new public surfaces (`brief`,
`record --worktree`, the additive `oracle_recheck` ledger field) are backward-compatible and
documented in the same change-set (SKILL.md, argparse help, architecture.md). All tensions
(AC5 vs the gate-run write, the honest trust-boundary scope, oracle-not-keyed-on-oracle_ref,
the `outcome.result` overwrite) are honestly logged and reconciled against ADR-0049.

SPECIFIC ISSUES:
- Round 1 blocker: `docs/architecture.md` not updated in-slice (broke the 042-01/02
  convention) — FIXED: the campaign paragraph now documents 042-03 advisory dispatch.
- [strength][impl] `_recheck_oracle` fails closed (unknown exit → error; None → rc=2) without
  reimplementing gate logic; re-check runs outside the ledger lock; single-source disclosure.
- [nit][impl] campaign.py couples to heartbeat's private underscore API; lean for two
  consumers, but a 4th consumer would warrant a shared dispatch-commons module. Open question.

RECONCILIATION NOTES:
- AC5-prose-vs-gate-runs-write and the `outcome.result` 040-object overwrite are honestly
  logged (deviation items 7, 10) and reconciled; the coupling-accretion open question is now
  recorded in the deviation log's Deferred/noted section.
