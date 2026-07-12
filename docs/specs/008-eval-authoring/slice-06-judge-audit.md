---
status: READY_FOR_REVIEW
dependencies: [008-04, adr-0005]
last_verified:
---

## Slice 008-06 — judge-audit

**Goal:** A light, **advisory** judge-trust audit: sample an authored eval's judged
cases for human spot-checking, compute agreement metrics, and recommend whether the
judge can be trusted to run `auto` or should be `confirmed-only`. Advisory only in
this MVP — it reports and recommends; it does **not** gate the composite or change
`gate.py`/`oracle.sh` behavior (that would touch the
[ADR-0005](../../decisions/adr-0005-eval-oracle-component.md) contract and is
deferred). Borrowed in shape from the surveyed prior art's judge-monitoring, kept
light.

### Acceptance criteria

- **AC1** `eval_authoring.py audit <eval>` samples a **mixed pass/fail** set of the
  eval's judged cases for human spot-checking, and records the human labels
  alongside the judge scores.
- **AC2** Computes advisory judge-trust metrics — **fail-precision**,
  **pass-miss-rate**, and (where the sample clears a stated minimum floor)
  **score-vs-human drift** — over the labeled sample.
- **AC3** Emits a recommendation `auto` (trust the judge) vs `confirmed-only`
  (require human confirmation), derived from stated thresholds, as **advisory
  output** — printed/returned, not enforced.
- **AC4** The audit does **not** alter the composite, the frozen definition, or
  `gate.py`/`oracle.sh` behavior. Auto-demotion of an untrusted judge is explicitly
  **deferred** and recorded in `docs/refinement-todo.md` and spec 008 Open questions
  (a future ADR + slice if a real audit surfaces an untrustworthy judge).
- **AC5** Audit results (sampled scores, human labels, metrics, recommendation)
  append to the eval's `ledger.jsonl` for auditability (ADR-0005 evidence trail).
- **AC6** Tests cover: a trustworthy judge yielding `auto`; a judge disagreeing with
  human labels yielding `confirmed-only`; a below-floor sample suppressing the drift
  metric with a stated caveat rather than reporting a spurious number; the composite
  being provably unchanged by an audit run.

> The teeth are deferred by design: the MVP makes judge-trust *visible*; whether an
> untrusted judge should be demoted in the composite is a separate, ADR-gated call.
