---
slice: 024-01 — cross-run quarantine record, quarantined status, and evidence-gated re-admission
pass: arch
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-08-06T17:43:06Z
prompt_source: independent arch review (024-01), re-verified after fixes
---

Independent architecture review of slice 024-01 (general-purpose, Opus, no impl-conversation access).
New durable state (.servo/quarantine/) + a servo↔jig boundary contract (arch_review: true).

VERDICT: pass (after one needs-changes round, re-verified)

Round 1 (needs-changes): the core design was found boundary-clean (no jig import; string-contract
plateau signal; servo-owned schema; fail-open), atomically durable, correctly layered
(heartbeat writes, not loop.py), and well-tested. One load-bearing gap: AC3's *automatic*
evidence-gated re-admission is inert for both real sources (CI/issue stable-evidence projection
equals the finding_id inputs), this was undisclosed, and the human release gesture (delete the
record) did not work (a record-less quarantined finding parked forever).

Round 2 (re-verified pass): all three fixes verified analytically —
1. `_reconcile_quarantine` now releases on record-gone OR pointer-change (human release gesture
   works, torn records self-heal), co-designed with the `run_dispatch` write-failure→`tried`
   fallback so a persistent write failure cannot thrash (invariant: a `quarantined` status always
   implies a live record). Bounded (max-candidates + cost ceiling; re-plateau re-parks). "Sound."
2. The v1-disclosure block lands accurately in ADR-0030 Decision A + spec.md AC3 + slice-01 AC3.
   "My disclosure finding is fully resolved."
3. `test_plateau_reason_matches_loop_py` pins loop.REASON_ORACLE_PLATEAU == heartbeat's ==
   "oracle_plateau" (loop.py:176). "Exactly the behavioral cross-skill guard I asked for."
Host packages byte-identical across skills/ + hosts/claude + hosts/codex; ruff clean; suite green (189).

No redesign of the durable-state or servo↔jig boundary was required.
