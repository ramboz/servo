---
adr: 0049
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-10T22:35:14Z
prompt_source: review.py frame-critique docs/decisions/adr-0049-campaign-orchestration.md (round 4)
---

VERDICT: pass

REASONING:
Round 4. Round-3 findings resolved: verification is a content fingerprint (HEAD at halt + diff + untracked contents), record-before-commit with a moved HEAD downgrading to advisory, and the record re-rendered from the run state.json. The frame survives: tiers state honestly what servo enforces; wrapper spend declared outside every ceiling; OQ3 does not oversell the baseline; A1/A4/A5 have kill criteria that can fire. Sound enough to put before the owner (ADR stays Proposed pending explicit owner acceptance).

SPECIFIC ISSUES:
- [spec] Verification covered halt->record but not base->loop-start (a worker could do the work, commit, then run loop.py) — folded in: start HEAD must equal the brief base sha and --allow-dirty unset.
- [spec] Minor: A5 kill wording and an over-long line — fixed.
