---
slice: 042-03 — host-driven advisory
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-13T02:51:01Z
prompt_source: review.py frame-critique docs/specs/042-campaign-orchestration/spec.md 042-03 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md skills/heartbeat/heartbeat.py (round 2)
---

VERDICT: pass (round 2)

REASONING:
The single highest-risk load-bearing assumption is A5 as it bears on the advisory oracle
re-check: that re-running `gate.py` on the worker-supplied `--worktree` delivers meaningful
verification. The strongest attack is real — the worker controls the worktree and its oracle,
so a `confirmed: passed` proves only "the installed oracle passed on the named worktree," not
"the briefed work passed." But every load-bearing artifact (slice deviation-log point 3,
`_recheck_oracle` docstring, architecture.md, the emitted brief text, ADR-0049 A5 + the
Option-B contrast) explicitly scopes the claim to exactly that — "servo runs the oracle
itself (catching honest/hallucinated false-passes), never binding provenance; provenance is
the verified-wrapped tier (042-04)." The frame never claims the trust boundary the attack
targets, so it survives: a settled residual (ADR-0049 A5 + deviation log), not a blocker.

SPECIFIC ISSUES:
- PRIMARY: "the advisory oracle re-check verifies the worker's claimed pass" is NOT an
  over-claim as recorded — it is consistently scoped to "servo ran the oracle on the named
  worktree," with advisory cost never enforced even on a cheated pass. Frame holds.
- SECONDARY (R2 residual, now fixed): SKILL.md retained the wrapped-tier "can no longer be
  verified" phrase in its advisory brief summary — corrected to the brief's honest rationale.
- Known residual (not re-blocked): A1 adoption (a host actually calls brief/record before
  committing) is unverified with a matching ~80% kill criterion in ADR-0049 A1 + slice A1.
