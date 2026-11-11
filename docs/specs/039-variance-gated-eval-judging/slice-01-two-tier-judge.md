---
status: DRAFT
kind: feature
dependencies: [038-01]
last_verified:
---

## Slice 039-01 — two-tier judge

**Goal:** A frozen eval can declare a cheap first judge and a frontier second
judge, so that only cases whose cheap samples disagree pay for the frontier
judge.

**DoR:**
- Activation trigger in spec 039 met.
- A judge-audit replay of at least one real eval (cheap vs frontier on the same
  cases) shows that low-spread cheap scores agree with the frontier within δ.
  Otherwise the frame (A1) is wrong; stop here.
- An ADR amending ADR-0005 for a two-judge frozen definition.

**Acceptance Criteria (sketch, to sharpen at activation):**

1. `config.json` may carry `judge.second` (same shape as `judge`) and
   `samples.rejudge_stderr` (float ≥ 0). Both are part of `definition_hash`, and
   an eval without them is unchanged.
2. For each case, the cheap judge runs `n` samples. If their stderr is at or
   below `rejudge_stderr`, the case score is the cheap lower bound. Otherwise the
   second judge runs `n` samples and its lower bound is the case score.
3. A second-judge failure is `EnvError` (rc 2). It never falls back to the cheap
   score.
4. Ledger rows record `judges_run`, both sample sets and `rejudged: bool`.
5. `eval_authoring.py` can emit the two-tier shape, with the defaults unchanged.

**DoD:** ACs pass, freeze/stale tests extended, ADR accepted, reviews per
spec-workflow.

**Anti-horizontal-phasing check:** an eval author can halve judge spend on an
eval whose cases are mostly unambiguous, with an auditable record of each
re-judge.
