---
slice: 008-04 — frozen-params-and-emit
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-12T16:25:51Z
prompt_source: review.py implementation ... 008-04
---

VERDICT: pass

All six ACs met when AC2/AC4/AC6 are evaluated against the self-freeze + self-install
mechanism (spec-006 has no eval-family compile step — verified). AC1: `params` sets
n/δ/threshold/model with preset-inherited defaults + per-knob trade-off notes. AC2/AC3:
`emit` freezes via fidelity_eval and installs score_<name> by splicing oracle.sh +
copying the runtime (no parallel harness). AC4: stops at an approved definition, does
not run (gate.py runs). AC5: staleness via the inherited validate_freeze (now wired into
score()). AC6: a REAL gate.py invocation over the genuine oracle.sh driver proves the
0/1/2 contract; a per-knob stale battery + idempotent install/uninstall round-trip.

Nits → reconciliation: stale test-file docstring; `_PARAM_TRADEOFFS` omits
max_tokens/transport; freeze permits an all-"EDIT ME"-placeholder dataset without a
warning. Architectural correction (spec-006 has no compile step; self-install via
ADR-0024 harness) must be entered in the deviation log + spec prose corrected.
