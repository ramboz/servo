---
status: DRAFT
dependencies: [adr-0029, adr-0015, adr-0018, adr-0026]
last_verified: 2026-08-04
---

# Spec 023 — autonomy-readiness-gate

> **Status: recorded, not yet built.** Implements [ADR-0029](../../decisions/adr-0029-autonomy-readiness-gate.md)
> (Proposed). This spec is reserved; the `autonomy-readiness` skill and the
> `loop.py` / `heartbeat.py` preflight are not implemented in the branch that
> introduced this record. Left DRAFT deliberately. Part of the long-horizon
> autonomy bridge (the `oh-my-cli` follow-on); mirrors jig ADR-0051 / jig spec 106
> on identity separation.

## Why this spec

Servo can prove *done* (the oracle) and *evaluable* (`edd-suitability`), but not
*ready to run unattended*. The most common way a long-horizon run wastes a day is
a faithfully-converging loop pointed at a badly-scoped goal — or an
identity-collapsed setup where every downstream owner-approval gate is fictional.
[ADR-0029](../../decisions/adr-0029-autonomy-readiness-gate.md) decides the fix: a
Compile-phase `autonomy-readiness` gate upstream of `edd-suitability` that reviews
the scope + initial prompt and refuses to start on a bad premise.

## Goals (provisional)

1. A new `autonomy-readiness` skill emits a closed three-state verdict
   `ready | needs_tightening | unsafe_for_autonomy`, exit `{0,2}`, atomic artifact
   at `<target>/.servo/readiness/<goal-id>.json`, human-owned
   (`approval_status: proposed → approved`, never auto-approved).
2. Deterministic checks: oracle present/executable/≥1 approved component; finite
   budget/iteration/`max-candidates` caps; clean-tree + worktree isolation;
   explicit mutation perimeter; **run-identity ≠ merge-identity** (else
   `unsafe_for_autonomy`).
3. Model-judged checks score the *prompt itself*: Precision, Scope-boundedness,
   Stop/escalation conditions, Safety surface, Internal contradiction — reusing
   `eval-authoring`'s expand-then-independent-review two-call pattern.
4. `loop.py` / `heartbeat.py` refuse unattended dispatch without an `approved`
   readiness artifact (sibling of the refuse-without-oracle preflight).
5. Reuse seams: shell to jig `clarify` + `frame_review` when jig is co-installed
   (subprocess + filesystem only, ADR-0011 boundary); built-in rubric otherwise.

## Vertical slices

- **023-01 — readiness verdict + artifact + human approval:** the skill, the
  three-state verdict, the atomic `<target>/.servo/readiness/<goal-id>.json`,
  the deterministic + model-judged tiers (including the identity check), and the
  proposed→approved human gate. See the slice file for ACs.

## Notes

- The identity check is the executable form of jig ADR-0051's precondition:
  when the loop's principal can also merge to the base branch, no downstream
  owner-approval gate is real — return `unsafe_for_autonomy`.
- Refuse-without-readiness preflight wiring into `loop.py`/`heartbeat.py` may
  split into a second slice (023-02) if it proves independently sizable.
