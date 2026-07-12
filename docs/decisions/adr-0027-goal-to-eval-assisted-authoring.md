---
status: Accepted
date: 2026-07-11
deciders: ramboz
supersedes:
superseded-by:
last_verified: 2026-07-11
---

# ADR-0027: Goal→eval is assisted authoring, gated by independent review and human curation

## Status

Accepted (2026-07-11). Frame-critique pass recorded (pass, round 3, after two
amendment rounds — see [reviews/adr-0027-frame-critique.md](reviews/adr-0027-frame-critique.md)).

Decides [spec 008](../specs/008-eval-authoring/spec.md) slice 008-05
(goal-to-criteria). Paired with
[ADR-0026](adr-0026-generic-eval-authoring-surface.md) (the generic surface this
front-end feeds).

## Context

Servo's eval pipeline is **spec/AC-centric**. Both
[edd-suitability (spec 015)](../specs/015-edd-suitability/spec.md) and
[spec-oracle (spec 006)](../specs/006-spec-oracle/spec.md) consume a spec with
*acceptance criteria*. A free-form **goal** — "make the onboarding copy
friendlier," "the summary should be faithful to the source" — has no ACs, so
there is an impedance: you cannot point servo at a goal without first hand-writing
the criteria, which is precisely the EDD setup cost spec 008 exists to lower.

Closing that gap means a **goal→eval** step: expand a free-form goal into a set of
acceptance criteria, tagged by how each can be evaluated, that then flow into the
existing suitability + classify + authoring pipeline.

**The hazard.** Goal→criteria is itself a non-deterministic LLM step. It can:
- **hallucinate** a criterion the goal never implied;
- **mis-tag** an irreducibly human taste/policy call as machine-"evaluable";
- **drift** — produce criteria that sound related but don't actually cover the goal.

If any of those flow unchecked into a frozen eval, servo has manufactured a
**false criterion** — the authoring-time analogue of the false-pass that
[ADR-0015](adr-0015-edd-suitability-gate.md)'s suitability gate exists to prevent.
An eval that faithfully scores the *wrong* criterion is worse than no eval, because
it launders a bad target as a green number. Servo's whole posture is fail-closed
against false-pass; goal→eval must not open a false-*criterion* hole on the way in.

**Prior art / posture.** The surveyed external system (Mystique) *deliberately
refuses* goal→eval — it hard-stops and forces a human to supply inputs — so this is
net-new, and it must not regress into the very autonomy that caution avoided.
Separately, jig gates much of its work with a **fresh independent-reviewer
subagent** (`jig:independent-review`); the reviewer reasons without the authoring
conversation's context and catches what the author and the generating model, who
share blind spots, both miss. This ADR adopts that pattern for the eval frame.

## Decision

1. **Goal→eval is an authoring assist, never an autonomous step.**
   `/servo:eval-authoring from-goal <goal>` expands a goal into a **proposed** AC
   set — each AC tagged `deterministic | judged | human-only` with a one-line
   rationale. A proposal, not a committed artifact.

2. **A fresh independent-reviewer subagent runs an advisory fresh-eyes pass — NOT
   an epistemic guarantee.** It receives the **goal text and the proposed AC set**
   (but not the expansion's chain-of-thought) and reads them critically. Its *reliable* value is on the **structural**
   failure modes that need no external ground truth, only careful reading:
   - an AC tagged `judged`/`deterministic` that is self-evidently taste/policy by
     its own wording;
   - an AC with no measurable predicate;
   - an AC that merely restates the goal without operationalizing it;
   - **surface-literal** coverage gaps — a requirement spelled out in the goal text
     but dropped from the ACs (an *implicit* gap the goal only implies is epistemic,
     below).
   **It does NOT reliably catch a plausible-but-unfaithful criterion, nor an
   *implicit* coverage gap** (a requirement the goal implies but never spells out —
   the dual of a hallucination) — a second
   same-distribution model reading the *same vague goal* (whose under-specification
   is the reason expansion was needed) shares the generating model's blind spots,
   so its independence is contextual, not epistemic. Catching subtle unfaithfulness
   is the human's job (point 3), not the reviewer's. It emits advisory flags, never
   a verdict the human can rubber-stamp. Reuse `jig:independent-review` when jig is
   co-installed (the filesystem-hint coupling
   [ADR-0001](adr-0001-reuse-jig-test-detector.md) established), else a built-in
   servo eval-frame-review prompt — servo does not hard-depend on jig.

3. **The human is the sole gate and must approve each AC positively.** The proposal
   + reviewer flags go to the human, who edits, accepts, rejects, **or adds** each AC
   **individually** — adding is essential — an *omitted* criterion has no row to reject, so the human,
   not the reviewer, is the backstop against coverage gaps of intent. There is no
   wholesale "accept the green verdict" path,
   precisely so the reviewer's presence cannot induce automation complacency and
   *weaken* the human backstop below the no-reviewer baseline. Only the curated set
   proceeds, and **nothing is frozen without recorded per-AC human approval**
   (consistent with ADR-0005, ADR-0019, and spec 008 goal 6). The reviewer aids
   this step; it does not replace it.

4. **Then the existing pipeline runs unchanged.** The curated AC set is emitted as
   a lightweight, project-owned, spec-shaped artifact that flows into
   `edd-suitability` (015 — "is this goal even eval-compatible?") → `spec-oracle`
   classify (006) → 008 triage/rubric/reference/emit → frozen `score_<name>`.
   Goal→eval *produces* the AC set the spec-centric pipeline already expects; it
   changes no downstream contract. **What it does NOT do is claim a full
   suitability verdict at expansion time.**
   Per [ADR-0015](adr-0015-edd-suitability-gate.md)'s taxonomy, an eval-able AC
   with no **reference set** resolves to `needs_evidence` — and the reference set is
   collected only later (008-03), so a *full* verdict at goal-expansion time would
   be `needs_evidence` across the board, uselessly.
   ([ADR-0018](adr-0018-suitability-gates-compile-not-heartbeat.md) is the companion
   caution: it measured a *different* degeneration — spec-less findings with zero
   ACs — but the lesson, don't expect a real verdict from a synthesis missing its
   inputs, is the same.) So goal→eval
   surfaces only the half of suitability it legitimately can — the
   **evaluable-vs-human-residual criteria split** over the proposed ACs (015's
   AC-classification input) — and the *full* `suitable | needs_evidence |
   unsuitable` verdict is produced later, once the target's signals and reference
   set exist. Front-loading the split still tells the author early whether a goal is
   *mostly taste* (few evaluable ACs → stop) vs *mostly evaluable*.

5. **The review is advisory-to-authoring, not an oracle gate.** Like
   [ADR-0025](adr-0025-runner-records-judge-verifies-assumptions.md)'s
   judge-verifies-assumptions, it lives in the authoring/agent layer and never
   becomes part of `gate.py`/`oracle.sh`
   ([ADR-0021](adr-0021-oracle-first-agent-loop-optional-consumer.md) /
   [ADR-0011](adr-0011-host-native-phase-hints.md) / ADR-0005 boundary preserved).
   Its teeth are procedural: no freeze without human approval, and the reviewer's
   flags are recorded alongside the curated artifact.

## Consequences

### Positive
- Closes the goal-vs-spec impedance: servo can start from a goal, not only a
  hand-authored spec — lowering the EDD setup cost that is the real adoption barrier.
- A **structural** false-criterion guard (mis-tagging by wording, unmeasurable
  predicates, goal-restatement, surface-literal coverage gaps) plus a human gate for
  the epistemic residue (unfaithfulness + implicit omission) — matching servo's
  fail-closed-against-false-pass ethos at
  criterion-authoring time, one stage earlier than ADR-0015.
- Leapfrogs the surveyed prior art's admitted gap **without** regressing into the
  unreviewed autonomy it avoided — the reviewer + human curation is the safety it
  was missing.
- Reuses jig's reviewer, the suitability gate, and the spec-oracle classifier — the
  new surface area is one expansion step plus a review hand-off.

### Negative
- Adds an authoring step and a subagent round-trip. Acceptable because goal→eval is
  **attended** authoring, not the headless loop — latency and a human wait are fine
  here in a way they are not in an unattended run.
- The independent reviewer mitigates **structural** defects (mis-tagging by wording,
  unmeasurable predicates, goal-restatement, surface-literal coverage gaps), **not**
  epistemic faithfulness or implicit coverage of intent — a plausible-but-wrong
  criterion, or an implied-but-omitted one, can pass both the generator and a
  same-distribution reviewer. The human curator is the only real guard against that,
  so goal→eval's safety is no stronger than the human's per-AC review; the ADR does
  not claim otherwise.

### Neutral
- Goal→eval is **opt-in**: an author who already has hand-written ACs skips it and
  enters at 008-01 triage.
- The emitted AC artifact is a lightweight spec-shaped file, project-owned; it does
  not require a full jig spec to exist first.

## Alternatives considered

- **Autonomous goal→eval (no review, no curation).** Rejected: the false-criterion
  risk is exactly what servo is built to refuse, and it discards the caution even
  the prior art that *has* no reviewer still enforced by hard-stopping.
- **Human-only, no LLM assist.** Rejected: no assist value; the whole point is to
  lower the setup cost, not restate it.
- **LLM + human curation but no independent reviewer.** Rejected, but narrowly: a
  fresh reviewer does **not** fix the shared-blind-spot problem on *faithfulness*
  (see Decision #2), so it is not a safety guarantee. It earns its place on the
  **structural** checks — mis-tagging by wording, unmeasurable predicates,
  goal-restatement, surface-literal coverage gaps — which a fresh reader catches more reliably than
  the author re-reading their own frame, at low cost. Kept as an advisory aid to the
  human gate, not as the gate.
- **Put the frame review in `gate.py`/the oracle.** Rejected: frame review is
  judgment and belongs in the authoring layer; the ADR-0021/0011/0005 boundary
  keeps `gate.py` deterministic.

## Verification

Implemented by spec 008 slice 008-05 (+ the reviewer reuse). Obligations:

- `from-goal` emits a curated, tagged AC set that `spec-oracle classify` consumes
  unchanged, and whose evaluable-vs-residual split feeds 015's criteria half (not a
  full verdict at expansion time — ADR-0018).
- A **structurally** mis-tagged taste-call (one whose own wording marks it
  policy/taste — e.g. "requires a senior editor's sign-off" tagged `deterministic`) is flagged by
  the reviewer; a plausible-but-unfaithful criterion is NOT assumed caught — the test
  instead asserts the human-curation gate blocks *any* AC from freezing without a
  recorded per-AC approval, and that the human can **add** a criterion the expansion
  omitted (coverage-of-intent is the human's backstop, not the reviewer's).
- No eval component is frozen without a recorded human approval of the AC set.
- The review path degrades cleanly when jig is absent (built-in prompt) and never
  invokes `gate.py`/`oracle.sh`.

## References
- [ADR-0005](adr-0005-eval-oracle-component.md) — the frozen-eval contract; no freeze without approval.
- [ADR-0015](adr-0015-edd-suitability-gate.md) — the false-pass posture this extends to false-criterion, and the suitability verdict the curated ACs feed.
- [ADR-0018](adr-0018-suitability-gates-compile-not-heartbeat.md) — the off-switch precedent (signal-less synthesized spec → `needs_evidence` for all) goal→eval must not repeat; grounds the criteria-split-not-full-verdict scope.
- [ADR-0019](adr-0019-eval-authoring-servo-owned.md) — eval authoring is servo-owned; goal→eval is one more servo authoring step.
- [ADR-0025](adr-0025-runner-records-judge-verifies-assumptions.md) — the advisory-review-in-the-agent-layer precedent.
- [ADR-0001](adr-0001-reuse-jig-test-detector.md) — the filesystem-hint jig-reuse posture the reviewer sourcing follows.
- [ADR-0021](adr-0021-oracle-first-agent-loop-optional-consumer.md) / [ADR-0011](adr-0011-host-native-phase-hints.md) — the oracle boundary the review stays outside of.
- [ADR-0026](adr-0026-generic-eval-authoring-surface.md) — the generic surface this front-end feeds.
- [Spec 006](../specs/006-spec-oracle/spec.md), [Spec 008](../specs/008-eval-authoring/spec.md), [Spec 015](../specs/015-edd-suitability/spec.md).
