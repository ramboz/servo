---
status: DRAFT
skill: quality-gate
use_cases: []
---

<!-- jig self-defining vocabulary (soft, forward-only): expand each acronym on first use and link the term to docs/memory/glossary.md (or jig's lexicon). See docs/workflow.md "Self-defining vocabulary". -->

# Spec 047: Deterministic-first oracle

> Implements [ADR-0052](../../decisions/adr-0052-deterministic-components-gate-judges.md)
> (Proposed). Investigation record: jig
> [R-002](https://github.com/ramboz/jig/blob/main/docs/research/R-002-claude-code-verification-assessment.md),
> item 10 ("Cheap checks first").
> **Status: recorded, not yet built** — reserved alongside the ADR so the
> decision has a home for its build; the ADR must be Accepted before 047-01
> moves past DRAFT.

## Overview

The Claude Code team runs build, lint and tests before any model review.
servo's compiled oracle scores every component and then averages, so a vision or
text judge runs — and costs `n × |cases|` model calls (ADR-0005 clause 6) — even
when the tests score 0 and the judged score cannot change the verdict.

This spec makes the oracle **deterministic-first**, per ADR-0052 Option D:

1. Each component has a kind, `deterministic` (default) or `judged`. The three
   frozen-eval installers mark their component `judged`.
2. The oracle runs deterministic components first.
3. When their results already decide the exit code — a deterministic component
   unavailable, a required constraint failed, or the quality ceiling (judged
   components at 1.0) below `THRESHOLD` — judged components are skipped, the
   oracle exits as full scoring would for any score the judges could return,
   reports a lower-bound composite, and records what it skipped and why. (The
   one named difference: a judge that would have been unreachable no longer
   turns a decided fail into an env error.)
4. The quality gate and the agent loop surface the skip and the judge calls it
   avoided.

Current state (probed 2026-11-21, working tree at `3e92dfc`):

- Plain oracle: `templates/oracle.sh.template:58-93` scores every component in
  `COMPONENTS` order, then decides. No short-circuit.
- Judged components are registered at the *top* of `COMPONENTS`
  (`skills/_common/fidelity_eval.py:397-409`), via the shared splice that
  design-eval (`design_eval.py:321-322`), content-fidelity
  (`content_fidelity.py:175-176`) and eval-authoring
  (`eval_authoring.py:1384-1385`) all call.
- Required-policy oracle: the template's loop is replaced by an `exec` into the
  vendored required runtime (`oracle_overlay.py:392`), whose `oracle()` scores
  every component once in `COMPONENTS` order (`required_runtime.py:762-823`).
  The gate side then re-derives composite and decision from the published
  payload, matching components *in `COMPONENTS` order* and requiring every
  component to have a score (`required_runtime.py:877-918`).
- `gate.py --json` already carries optional keys (`reason`, `code`,
  `timeout_seconds`; `gate.py:353-369`), and ADR-0002 allows additive optional
  fields at `schema_version: 1`.

**Relationship to spec 039 (DRAFT).** [Spec 039](../039-variance-gated-eval-judging/spec.md)
is parked "until a consumer shows judge cost matters" and works *inside* one
judged component (cheap judge first, frontier judge on high-variance cases).
047 works *across* components (deterministic before any judge). They compose: 047
decides whether a judged component runs this iteration; 039 decides which judge
tier scores each case when it does. 047-03's "judge calls avoided" counts feed
039's activation trigger rather than replacing it.

**Siblings.** jig [spec 129](https://github.com/ramboz/jig/blob/main/docs/specs/129-verification-loop-hardening/spec.md)
(tests green before review) is the jig-side analog for review passes; nothing
here depends on it. servo [spec 046](../046-commit-bound-eval-evidence/spec.md)
(commit-bound evaluation evidence) adds the evaluated tree to the same gate
payload and loop history 047-03 extends — coordinate field placement, no shared
scope. servo [spec 045](../045-base-anchored-freeze/spec.md)-02 pins `oracle.sh`
— including the SEED blocks where 047-01's kind declaration lives — to its base
copy for unattended scoring, so a run cannot re-label its own components (and a
skip can never confer a pass in any case).

**Non-goals.** No green-floor gating (ADR-0052 Option E); no change to frozen
eval definitions or `definition_hash`; no change to suitability (ADR-0050); no
USD metering of oracle spend (the ADR-0041 boundary stays — 047-03 counts calls,
not dollars); no heartbeat or variant-race changes beyond what they inherit from
the gate.

## Assumptions

<!-- Spec 064-02 / ADR-0020 — grounding-by-probe (risk-gated). -->

- **Probed — kind can travel with the installed fragment without touching any
  seal.** SEED blocks are stripped before `driver_identity` hashes the oracle
  prefix (`required_runtime.py:25-31`), and `definition_hash` reads only judge,
  samples, threshold, cases and kind-specific extras (`fidelity_eval.py:245-259`).
  So a `kind_<name>` declaration inside a judged component's SEED block changes
  neither the required-policy `driver_prefix_hash` nor any frozen eval's hash.
  This is the leading mechanism; 047-01's DoR confirms it with arch-review.
- **Probed — the plain-path change only reaches new or re-scaffolded oracles.**
  The required path replaces the template loop with the driver
  (`oracle_overlay.py:392`), and a first required install compares the target's
  `oracle.sh` against the canonical template (`oracle_overlay.py:338-357`). A
  changed template loop would make every older `oracle.sh` look "customized"
  there, so 047-01 must keep accepting the pre-047 loop.
- **Probed — skips must keep a numeric composite.** A `None` composite is exit 2
  in the required path (`required_runtime.py:706-708`) and is ignored by the
  plateau detector (`loop.py:766-770`); ADR-0052 therefore reports a lower bound.
- **Probed — score range.** The required runtime enforces scores in [0, 1] and
  non-negative weights (`required_runtime.py:765`, `:807`, `:888`); the template
  only documents it (`oracle.sh.template:9-13`). The exit-code equivalence
  property (047-01 AC5) assumes the documented contract.
- **Unverified — judge spend matters.** Not yet measured for any real target
  (servo's loop does not meter oracle spend, ADR-0041 Context). 047-03 provides
  the measurement; ADR-0052's third kill criterion uses it.
- **Unverified — judge calls avoided can be estimated from the frozen
  definition** (`samples.n` × scored cases, ADR-0005 clause 6) by reading the
  skipped component's `config.json`. Where that is not readable the count is
  reported as unknown, never guessed.

## Decomposition

SPIDR: **Paths** (the plain bash oracle and the required-policy runtime are
separate execution paths with separate seals) then **Interfaces** (the gate JSON
and loop records that expose the skip). No spike: ADR-0052 fixes the rule, and
every touched surface was probed above.

- **047-01 (Paths: plain oracle)** — the kind declaration in the shared
  installer splice, a two-pass template loop that skips judged components when
  the exit is decided, a stderr skip record, and back-compat for pre-047 oracles.
  End-to-end: a scaffolded target with tests + design-eval stops calling the
  judge while its tests fail.
- **047-02 (Paths: required runtime)** — the same rule in
  `required_runtime.oracle()` plus the gate-side re-derivation, with the
  required-fail condition and honest reason codes. End-to-end: a required-policy
  target whose required check fails no longer runs its judge.
- **047-03 (Interfaces)** — `gate.py --json` reports skipped components; the
  loop records skips per iteration and totals judge calls avoided per run.
  End-to-end: a loop summary says how much judging was avoided.

**Anti-horizontal-phasing.** 047-01 alone delivers the savings for the common
(plain-oracle) target and is observable in oracle stderr; 047-02 alone extends
them to required-policy targets; 047-03 makes the savings visible to callers.
None is an internal-only layer.

## Slices

- [047-01 — plain-oracle-skip](slice-01-plain-oracle-skip.md) — component kind, deterministic-first template loop, decided-outcome skip, pre-047 compatibility.
- [047-02 — required-runtime-skip](slice-02-required-runtime-skip.md) — the same rule in the required runtime and the gate's re-derivation; reason-code honesty.
- [047-03 — surface-skip-and-savings](slice-03-surface-skip-and-savings.md) — gate JSON `skipped`, loop per-iteration skip record, judge calls avoided per run.
