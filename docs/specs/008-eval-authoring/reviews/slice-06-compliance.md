---
slice: 008-06 — judge-audit
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-12T18:02:14Z
prompt_source: review.py implementation ... 008-06
---

VERDICT: pass

Final slice (judge-audit). All six ACs correctly implemented + meaningfully tested.
AC1: audit samples a mixed pass/fail judged set + records human labels (mixed-sample
now directly asserted). AC2: fail-precision = |judge-fail ∩ human-fail|/|judge-fail|,
pass-miss-rate = |human-fail ∩ judge-pass|/|human-fail|, drift = mean|judge-human|
computed only ≥20 numeric-scored labeled cases (else suppressed with a stated caveat);
empty denominators return a stated n/a note, never crash; drift-computed branch now
tested with a hand-verified value. AC3: auto iff fail-precision≥0.70 AND
pass-miss≤0.20 else confirmed-only; fail-closed on undefined metrics; advisory only.
AC4: proven byte-identical config.json + oracle.sh over a real emit→score→audit
pipeline; append-only ledger; auto-demotion deferred (refinement-todo present). AC5:
`kind: judge_audit` ledger record, distinguished from scoring records.

Nit → reconciliation: `--sample-size` even-split + `--scores` override untested;
unmatched labels silently dropped (advisory-notice opportunity).
