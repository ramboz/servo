---
status: Proposed
date: 2026-08-04
deciders: ramboz
supersedes:
superseded-by:
frame_review: true
last_verified: 2026-08-04
---

# ADR-0029: Autonomy-readiness pre-flight gate

## Status

Proposed (2026-08-04)

> **Recorded, not yet built.** This ADR captures the servo-side decision for the
> long-horizon-autonomy bridge (the `oh-my-cli` follow-on). It is paired with the
> DRAFT [spec 023](../specs/023-autonomy-readiness-gate/spec.md) and mirrors jig
> ADR-0051 (identity separation). No skill or `loop.py` code ships with this
> record.

## Context

Servo's Compile phase already asks *"can this spec be evaluated?"* — the
`edd-suitability` gate ([ADR-0015](adr-0015-edd-suitability-gate.md),
[ADR-0018](adr-0018-suitability-gates-compile-not-heartbeat.md)) emits a
three-state verdict and gates Compile. But nothing asks the prior question:
*"is the SCOPE and the INITIAL PROMPT itself precise and bounded enough to hand
to an unattended loop for a long horizon?"*

This is the most common way a long-horizon run wastes a day: not a weak oracle,
but a faithfully-converging loop pointed at a badly-scoped goal. `oh-my-cli`'s
16-day run worked partly because a human tightened the brief up front. Servo has
a hardened, human-approved definition of *done* (the oracle) and a hardened
definition of *evaluable* (`edd-suitability`), but no hardened definition of
*ready to run unattended*. A `loop.py` / `heartbeat.py` will happily start on a
one-line "make it better" brief with no cost ceiling and no scope perimeter.

A second, host-level hazard compounds this: **identity collapse** (jig ADR-0051).
If the loop runs under the same principal that can merge its output, every
"owner-approval" safety gate downstream is fictional — there is no second party
to approve. A readiness gate that ignores this would bless an unsafe setup.

## Decision

Add a new Compile-phase skill, **`autonomy-readiness`**, positioned **upstream of
`edd-suitability`**, that reviews the scope + initial prompt and refuses to let an
unattended loop start on a bad premise. It mirrors the shapes servo already uses,
so it composes rather than reinvents.

**Contract.** A closed three-state verdict `ready | needs_tightening |
unsafe_for_autonomy`, exit `{0,2}` (fail-closed like `edd-suitability`), written
atomically to `<target>/.servo/readiness/<goal-id>.json`. Human-owned: the
artifact starts `approval_status: proposed`; a human reviews the scorecard and
flips it to `approved` (reusing the `eval-authoring` proposed→approved +
`criteria-check` mechanics). It **never** auto-approves.

**Two check tiers**, matching servo's existing deterministic-vs-model split:

- *Deterministic / offline:* an oracle exists, is executable, and has ≥1
  approved (non-draft) component (surface `checks.py --enforce-freeze` at
  readiness time); budget / iteration / `max-candidates` caps are **finite** (a
  24h run with no cost ceiling is unsafe); clean tree + base branch + worktree
  isolation are available (reuse `loop.py`'s dirty-tree preflight); an explicit
  **mutation perimeter** exists (allowlisted paths + protected denylist — ties to
  jig ADR-0051's `protected_paths`); and a **run-identity ≠ merge-identity**
  check — when the principal that would run the loop is also the one that can
  merge to the base branch, return `unsafe_for_autonomy` (identity collapse).
- *Model-judged* (reuse `eval-authoring`'s expand-then-independent-review
  two-call pattern — nothing scores the *prompt itself* today): **Precision**
  (specific + bounded vs "make it better"); **Scope-boundedness** (does the brief
  name what is OUT of scope? a long run needs a hard perimeter); **Stop /
  escalation conditions** (does the brief say when to stop rather than thrash?);
  **Safety surface** (secrets / deploys / data migrations / external side-effects
  → require human checkpoints, downgrade to `needs_tightening`); **Internal
  contradiction**.

**Refuse-without-readiness preflight.** `loop.py` / `heartbeat.py` gain a
preflight (sibling to the existing refuse-without-oracle): unattended dispatch
refuses unless an `approved` readiness artifact exists for the goal.

**Reuse seams (do not duplicate):** when jig is co-installed, probe for and shell
to jig's `clarify` skill (a six-category precision scanner) — filesystem probe in
the style of the existing jig-skill detection — and fold in a jig `frame_review`
critique of the brief's assumptions; otherwise ship a built-in rubric.

## Consequences

### Positive

- A long-horizon run can no longer *start* on an unscoped premise or an
  identity-collapsed setup — the cheapest possible insurance against the most
  expensive failure mode.
- Useful even without the loop: "is this brief precise enough to hand to anyone?"
  is valuable for supervised runs too.
- Puts servo ahead of `oh-my-cli` on the thing that matters most — the premise —
  by making readiness an executable, human-approved artifact rather than a
  habit.

### Negative

- Another human-approval gate before autonomy unlocks (intended friction).
- The model-judged tier costs tokens at Compile time; must stay a one-shot
  scorecard, not a loop.

### Neutral

- Reuses `edd-suitability` / `eval-authoring` artifact and approval shapes; no new
  approval mechanism invented.
- The identity check reads host signals but decides nothing about *how* identities
  are provisioned (that is the operator's / jig ADR-0051's concern).

## Alternatives considered

- **Fold prompt-readiness into `edd-suitability`.** Rejected: suitability answers
  "is this evaluable?", a different question with a different verdict vocabulary;
  overloading it would blur both. Readiness sits *upstream* and hands off to it.
- **Make it advisory (print warnings, never refuse).** Rejected: an advisory gate
  is exactly today's state (nothing stops a bad-premise run). Fail-closed with a
  human approval flip is the point.
- **Auto-tighten the brief with the model instead of refusing.** Rejected:
  silently rewriting the human's goal is the wrong authority; surface the
  scorecard and let a human tighten and approve.

## Verification

- Golden-case fixtures: a good brief → `ready`; an open-ended brief →
  `needs_tightening`; a secrets-touching brief → `unsafe_for_autonomy`; a
  single-identity setup → `unsafe_for_autonomy`.
- `loop.py` / `heartbeat.py` refuse-without-readiness proven red→green.
- Artifact schema round-trips; the human-approval gate blocks while
  `approval_status: proposed`.
- Boundary integrity: no servo→jig Python import; jig `clarify` / `frame_review`
  reached by subprocess + filesystem only.

## References

- [Spec 023 — autonomy-readiness-gate](../specs/023-autonomy-readiness-gate/spec.md)
- [ADR-0015 — EDD suitability is a fail-closed gate](adr-0015-edd-suitability-gate.md)
- [ADR-0018 — suitability gates Compile, not the heartbeat](adr-0018-suitability-gates-compile-not-heartbeat.md)
- [ADR-0026 — generic eval-authoring surface](adr-0026-generic-eval-authoring-surface.md)
- jig ADR-0051 — autonomy governance plane and identity separation (sibling, `ramboz/jig`)
