---
status: DONE
dependencies: [008-04, adr-0005]
last_verified: 2026-07-12
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
  **pass-miss-rate**, and (where the sample clears a stated minimum floor —
  provisional **≥20 labeled cases**) **score-vs-human drift** — over the labeled
  sample.
- **AC3** Emits a recommendation `auto` (trust the judge) vs `confirmed-only`
  (require human confirmation), derived from stated thresholds (provisional, from
  the surveyed prior art: fail-precision ≥ 0.70, pass-miss-rate ≤ 0.20), as
  **advisory output** — printed/returned, not enforced.
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

### Deviation log (after reconciliation)

Original ACs preserved above.

- **`audit <eval>` subcommand (advisory only).** Reads the eval dir's `config.json`
  (for `threshold`) + the most recent scoring run from `ledger.jsonl`, selects a
  mixed pass/fail sample (verdict = `pass` iff judged score ≥ threshold), records
  human labels from a `--labels` file (`case_id → "pass"|"fail"`, or an object form
  carrying a numeric `score` for drift; an optional `--scores` override lets it run
  with no prior ledger). Metrics: **fail-precision** = |judge-fail ∩ human-fail| /
  |judge-fail|; **pass-miss-rate** = |human-fail ∩ judge-pass| / |human-fail|;
  **drift** = mean |judge − human| over labeled cases carrying a numeric score.
  **Recommendation:** `auto` iff fail-precision ≥ 0.70 AND pass-miss ≤ 0.20, else
  `confirmed-only`; **fail-closed** to `confirmed-only` when either metric is
  undefined. Advisory — printed + returned + laddered to the ledger, never enforced.
- **Empty-denominator + drift-floor honesty.** An undefined ratio returns `None` +
  a stated `*_note` (never `ZeroDivisionError`). Drift is computed only when the
  numeric-scored labeled count clears the provisional floor (**≥20**); below it,
  `drift` is `None` with a stated caveat rather than a spurious number.
- **AC4 — composite provably unchanged.** `audit_target` only *reads* `config.json`
  and *appends* to `ledger.jsonl`; it never opens `oracle.sh`. Proven byte-for-byte
  over a real emit→score→audit pipeline (config.json + oracle.sh identical
  before/after). Auto-demotion of an untrusted judge stays **deferred** — already
  recorded in `docs/refinement-todo.md` ("Judge-audit → composite gating") + spec 008
  Open questions; a future ADR + slice decides the demotion semantics.
- **AC5 ledger record.** Appended via the shared `fidelity_eval.write_ledger` with a
  `"kind": "judge_audit"` marker; score.py's scoring records carry no `kind`, so a
  re-audit never mistakes its own prior record for a scoring run (guarded by both the
  absent-`kind` check AND an `isinstance(cases, list)` guard, backed by a drift-guard
  test asserting score.py writes no `kind`).

**AC-wording deviation (logged):** AC2 reads "≥20 **labeled cases**"; the drift floor
is applied to labeled cases carrying a **numeric human score** (`drift_inputs`), which
is more correct (drift is undefined without numeric scores) — a deliberate refinement.

**Nits logged (non-blocking, from both review passes):**

- `--sample-size` even-split has an odd-size off-by-one (`--sample-size 1` → 2 cases).
  The split path itself IS covered (`SelectAuditSampleMixedTests` calls
  `sample_size=4`); the `--scores` override loader remains untested.
- Unmatched `--labels` ids are silently dropped — an "N labels matched no sampled
  case" advisory would help an author catch a typo. (UX, deferred.)
- `audit_target` reaches `write_ledger` via `_load_score()._fe` (execs score.py) —
  heavyweight indirection, but matches the established `content_fidelity.py::_load_score`
  precedent; left as-is.

### Reconciliation sweep

- **`docs/architecture.md`** — `deferred → close-out`. The stale
  `/servo:eval-authoring (008, parked)` label refresh + the `eval/<spec_id>/` artifact
  dir note are handled in the **spec close-out** step immediately following this slice
  (all six slices now DONE), together with the SKILL.md surface.
- **`.claude-plugin/install-contract.json` + `SKILL.md`** — `deferred → close-out`.
  Spec 008 has no dedicated skill-surface slice (flagged since 008-01); the
  `/servo:eval-authoring` SKILL.md + install-contract registration are authored in the
  spec close-out step (the reconciliation-checklist "Primer hygiene" gate for a
  spec whose last slice is going DONE), verified by `verify_install_surfaces.sh`.
- **`docs/refinement-todo.md`** — `updated at close-out`. The judge-audit→composite
  deferral is already present; the 008-05 un-timed-subprocess nit + the audit nits
  above are surfaced at close-out.
- **Load-bearing decision / ADR trigger** — `no-op`. Advisory metrics + provisional
  thresholds are derivations of the surveyed prior art + ADR-0005; the composite-gating
  decision is explicitly deferred to a future ADR (recorded), not made here.
- **Status board** — `deferred`. Regenerated at close-out after `DONE`.
