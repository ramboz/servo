---
slice: 044-02 — required-policy-has-signal
pass: reconciliation
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-20T02:11:36Z
prompt_source: review.py reconciliation docs/specs/044-required-policy-evaluability/spec.md 044-02
---

Reconciliation review (fresh general-purpose reviewer, read-only).

VERDICT: pass

The deviation log is an accurate, honest account of slice 044-02. Every claimed
code change is present in the live tree exactly as described — the `has_signal`
disjunct (`decide` / `_rule_table` / `build_trace`), the `eval_only` redefinition
excluding `policy_evaluable`, the `_facts` signal-phrase, the `render_human`
policy/judged-only lines, both reason-code-constant collapses, the
provenance-accurate messages, and the full removal of the dead
`evaluable_required_policy_with_eval_signal` code (its only remaining references
are in `DeadReasonCodeUnreachableTests`, which prove non-emission). All 5 new test
classes and 3 re-pinned 044-01 tests exist and are non-vacuous, mapping cleanly to
AC1–AC6; 142 edd-suitability tests pass; host packages drift-clean; the SKILL.md
`has_signal` paragraph + surface test landed. The three review summaries
(frame-critique R1→R2, compliance, craft) are faithfully reproduced, and the
no-ADR / g5-stand-down framing matches R2's exact correction (trigger-recomputation
over the widened signal set, not mechanism-equivalence). No silent changes: every
actual slice-02 path (10 committed + the uncommitted spec/slice/reviews/board)
appears in the sweep with credible dispositions.

Leanness: clean (the `has_signal` triplication no-op is a credible call —
pre-existing from 030-01, ADR-0002's third-caller trigger fired there, not here).
Principles: aligns with "the oracle is the source of truth, never the
transcript-only judge". Approach follows the re-scoped "What the change actually
is" exactly. No-new-ADR corollary call credibly recorded and honest.

No blocking issues. Non-blocking notes (all handled at close-out): (1) the board
regen must run so the committed README reflects DONE (not the stale DRAFT) — done
via `workflow.py status-board`; (2) this reconciliation evidence is recorded now,
ticking the final DoD box; (3) the `.candidates/` sidecar is correctly excluded as
regenerable scratch.
