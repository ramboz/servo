---
slice: 015-05 — suitability-at-the-boundary (spike)
pass: craft
verdict: pass
reviewer: maintainer-self-review
reviewed_at: 2026-06-28T04:11:00Z
prompt_source: spike methodology review (kind: spike); maintainer self-review
---

VERDICT: pass

REASONING:
The spike's method is sound and its conclusion follows from the evidence. It
tested the real falsifiable hypothesis (ephemeral-spec synthesis degenerates to
`needs_evidence`) against the **real** `suitability.py` analyzer over **real**
discovered findings, rather than reasoning from a chair — 36/36 is a decisive,
reproducible result, not a hand-wave. It correctly scoped the survey to the
candidates a gate actually sees (the 3 actionable findings), avoiding the trap of
the loose 17/36 token match (correctly attributed to servo's own commit messages,
a non-generalizing artifact). The marginal-value argument is grounded in the
actual dispatch code (`gate.py` preflight + worktree verification), not assumed.

CRAFT NOTES:
- Followed the `kind: spike` body shape (Question / Time-box / Findings / Outcome)
  faithfully; Outcome names the ADR + the 015-03 disposition.
- The decision is appropriately narrow: it narrows ADR-0015's heartbeat clause
  without disturbing the verdict contract (closed gate / fail-closed /
  missing_evidence), and leaves a clean future door (finding-shaped check → 018,
  gated on showing value over gate.py).
- Disposition is internally consistent across artifacts: ADR-0018, ADR-0015
  amendment, 015-03 re-scope, spec.md SPIDR row, decisions index, and the stale
  015-02 board note (corrected) all tell the same story.

No blocking craft issues. Scratch prototypes kept out of the repo.
