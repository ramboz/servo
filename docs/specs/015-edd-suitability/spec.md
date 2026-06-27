---
status: DRAFT
dependencies: [001, 006]
last_verified:
---

# Spec 015 — edd-suitability

> The first step of Servo Compile: given an engineering specification, decide
> whether the work is suitable for Evaluation-Driven Development and identify the
> evidence it is missing. Emits a structured, fail-closed **suitability verdict**
> (`suitable` / `needs_evidence` / `unsuitable`) that gates the rest of the
> Compile/Run pipeline — per
> [ADR-0015](../../decisions/adr-0015-edd-suitability-gate.md). Provisional
> skill: `/servo:edd-suitability`.

> **Status: DRAFT — scope capture, parked.** Recorded as the Compile-phase
> entry point named by [ADR-0014](../../decisions/adr-0014-evaluation-compiler.md).
> It activates when a real target needs servo to *refuse* un-evaluable work
> before spending budget — most concretely, when the heartbeat (011) dispatches
> work no human chose and an unsuitable finding must be turned away at the
> boundary. Until then this is captured intent; the slice sketch is pre-SPIDR
> (goals only, no ACs).

## Why this spec

[ADR-0014](../../decisions/adr-0014-evaluation-compiler.md) makes Servo Compile a
first-class phase, and the vision assigns it two responsibilities that have no
home today: *determine whether the work suits EDD* and *identify missing
evidence*. `/servo:scaffold-init` (001) always emits an oracle (a no-signal
target gets a comment-only oracle that exits 2); `/servo:spec-oracle` (006)
classifies a spec's ACs but never judges the spec *as a whole*. Nothing answers
"should this go through EDD at all, and if not, what's missing?" before
unattended execution starts.

That question matters because the worst unattended failure mode is a **false
pass** — a green oracle on work that cannot be meaningfully evaluated (success is
pure taste, the only signals are vacuous, every AC is human-residual). The loop
will happily optimize toward a meaningless target and report success.
[ADR-0015](../../decisions/adr-0015-edd-suitability-gate.md) settles the
*contract* (a closed three-state gate, fail-closed, with a `missing_evidence`
list); this spec builds the analyzer that produces it.

## Goals (provisional)

1. **Produce the suitability verdict.** From a spec (and the target's detected
   signals + any spec-006 classification), emit the ADR-0015 verdict:
   `suitable` / `needs_evidence` / `unsuitable`, with per-reason rationale.
2. **Identify missing evidence.** When EDD-shaped-but-not-ready, list the
   blocking gaps as actionable `missing_evidence` items (no test signal, no
   oracle signals, eval-able ACs lacking a reference set, …) — the actionable
   half of EDD onboarding.
3. **Fail closed.** Indeterminate input never yields `suitable`; it resolves to
   `needs_evidence` (nameable gap) or `unsuitable` (not EDD-shaped). No silent
   degradation into execution.
4. **Gate the pipeline.** The verdict is the dispatch precondition: Compile
   proceeds only on `suitable`; the heartbeat records an `unsuitable` /
   `needs_evidence` finding as `skipped` with an `actionable_reason` (ADR-0010)
   rather than spawning a loop.
5. **Stay deterministic-first, auditable.** Start with an ordered rule table
   (the spec-006 pattern) so the verdict is explainable and reproducible; leave a
   documented extension point for an optional model-assisted pass behind a flag.
6. **Be re-runnable.** Re-analysis after evidence is acquired flips the verdict;
   the artifact is project-owned and inspectable.

## Non-goals

- **Not synthesizing the oracle.** That stays 001; suitability runs upstream and
  consults 001's signal detection.
- **Not classifying ACs.** That stays 006; suitability consults its output.
- **Not a suitability *score*.** ADR-0015 chose a closed gate over a threshold on
  purpose — no "close enough" auto-proceed.
- **Not deciding the jig-vs-servo authoring home** for shaping un-evaluable ACs
  into evaluable ones (same open question as spec 008) — decided when a real case
  forces it.

## Core model

Where this sits in Servo Compile (the gate before everything else):

```
spec  ─┐
       ├─→ [015: EDD suitability analysis] ──→ verdict
signals┘                                        │
                            ┌───────────────────┼───────────────────┐
                       suitable            needs_evidence        unsuitable
                            │                    │                    │
              proceed to Compile         emit missing_evidence   route to human / jig
              (001 oracle, 006 overlay,  (acquire, re-analyze)   (no compile, no run)
               016 plan, then Run)
```

In the heartbeat, the verdict is consulted per finding *before* the 011-03
oracle-gated dispatch; a non-`suitable` finding is recorded `skipped`, never
dispatched.

## Provisional slice sketch (pre-SPIDR — not ready for implementation)

> Goals only, no ACs. A grounding consumer (most likely the heartbeat needing to
> refuse un-evaluable findings) is needed to pin acceptance criteria.

| Slice | Title | Goal |
|---|---|---|
| 015-01 | verdict-contract | Emit the ADR-0015 verdict JSON from a spec + signals; closed three-state enum; `schema_version`; fail-closed default. Deterministic rule table v1. |
| 015-02 | missing-evidence | Populate `missing_evidence` with actionable, blocking-flagged items keyed to a closed `kind` taxonomy. |
| 015-03 | pipeline-gate | Wire the verdict as the Compile precondition + the heartbeat per-finding gate (record `skipped` with `actionable_reason`, no dispatch). |
| 015-04 | skill-and-explain | `/servo:edd-suitability` surface (human + `--json`), `--explain` rationale, re-run flow; document the rule-table extension point. |

## Open questions

- **Deterministic rules vs model-assist.** Start rule-table-only (explainable,
  reproducible) — but some suitability signals ("is success irreducibly taste?")
  resist deterministic rules. When does the optional model-assist layer earn its
  place, and how is its non-determinism bounded (cf. ADR-0005)?
- **Human override of a `needs_evidence` / `unsuitable` gate.** A waiver
  mechanism (and its audit trail) — borrow spec-006's waiver posture, or new?
- **Verdict freshness.** Does the verdict expire when the spec or signals drift
  (links to 018 continuous-evaluation's recompilation trigger)?
- **Where the artifact lives.** Standalone `.servo/suitability/<spec-id>.json`,
  or folded into the 016 execution plan as its `suitability_verdict` field
  (currently referenced there)?

## References

- [ADR-0015 — EDD suitability is a fail-closed gate](../../decisions/adr-0015-edd-suitability-gate.md)
  — the contract this spec implements.
- [ADR-0014 — evaluation compiler](../../decisions/adr-0014-evaluation-compiler.md)
  — the Compile phase this is the entry point of.
- [Spec 001 — scaffold-init](../001-scaffold-init/spec.md) — signal detection the
  analysis consults; [Spec 006 — spec-oracle](../006-spec-oracle/spec.md) — AC
  classification it consults.
- [Spec 011 — heartbeat](../011-heartbeat/spec.md) — the likely grounding
  consumer (per-finding suitability gate).
