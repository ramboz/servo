---
slice: 044-02 — required-policy-has-signal
pass: craft
verdict: pass
reviewer: pr-review
reviewed_at: 2026-11-20T02:02:13Z
prompt_source: review.py pr-review docs/specs/044-required-policy-evaluability/spec.md 044-02 --richer-skill none (craft)
substrate: non-interactive
---

Craft pass (fresh general-purpose reviewer, pr-review baseline, read-only).

VERDICT: pass

No blockers. The implementation matches the slice's honest scope exactly — a
coordinated set of pure-layer edits (`has_signal` disjunct, `eval_only`
redefinition, `policy_is_signal` branch + provenance-accurate messages, dead-code
removal, `render_human` signal line, docstrings, SKILL.md), every one gated on
`policy_evaluable` so non-`fidelity_contract` specs stay byte-identical. 142-test
suite green; the reviewer empirically mutation-tested the safety claim (reverting
the `has_signal` disjunct flips `test_static_contract_only_is_suitable` from
suitable to needs_evidence); host-package parity clean.

Strengths: (1) the single `policy_evaluable` boolean feeds both legs so a
`suitable` via this path can never credit `has_signal` while leaving `n_evaluable`
unmet — the safety invariant enforced by construction; (2) `_policy_credit`
centralizes the +1 so n_evaluable / ac_evaluable cannot drift; (3) fail-closed
coverage is a real mutation matrix + the byte-identity test carries an explicit
non-vacuity assertion; (4) message provenance named accurately across all three
cases, closing 044-01's hardcoded "test/CI signal is present" string.

Three NON-BLOCKING nits:
- nit 1 (render_human re-derived the det test inline instead of `_SIGNAL_KEYS`, a
  latent drift risk) — APPLIED (now `any(bool(signals.get(k)) for k in _SIGNAL_KEYS)`).
- nit 2 (ASCII hyphen vs the file's em-dash comment convention, suitability.py:103/306
  + test ~1557) — APPLIED (em-dashes).
- nit 3 (the `det or eval or policy` triplication across `_rule_table` / `build_trace`
  / `decide`) — NO-OP: pre-existing from 030-01 (which deliberately did not extract);
  a helper for a three-term boolean is not warranted (ADR-0002 third-caller trigger
  was 030-01, not this slice), and the leanness sweep cautions against it.

The reviewer confirmed clean dead-code removal (zero shipped references) and
host-package drift clean.
