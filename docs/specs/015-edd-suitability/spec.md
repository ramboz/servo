---
status: DONE
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

> **Status: DONE (all slices).** 2026-06-29: the analyzer + evidence list + skill
> surface ship (015-01/02/04 DONE); the 015-05 spike landed
> [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md)
> — **suitability gates Compile, not the heartbeat** — and re-scoped **015-03** to
> the Compile precondition. 2026-06-30: **015-03 DONE** — spec 016-01 landed the
> Compile entry (`execution_plan.py compile`), and 015-03 enriched it to surface
> `reasons`/`missing_evidence` on refusal, fail-closed on an unavailable verdict,
> with a heartbeat-boundary regression guard. **Reconciliation note:** Goal 4 and the
> Core model below still describe the original *heartbeat* per-finding gate; that
> mapping is **retired** by ADR-0018 (heartbeat findings are spec-less) — read
> them as the Compile-gate now. Both anchoring ADRs remain Accepted
> ([ADR-0014](../../decisions/adr-0014-evaluation-compiler.md),
> [ADR-0015](../../decisions/adr-0015-edd-suitability-gate.md)).

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

## SPIDR split

The work is **Rules-first** (the verdict logic, simple → rich), then a **Path**
slice (the gate path through to the real heartbeat consumer), then an
**Interface** slice (the skill surface). Every slice is vertical — each emits or
acts on a verdict a user/caller can observe.

> **Correction (2026-06-28).** The original split claimed "No spike: ADR-0015
> settled the *contract*, and the consumer (011) is shipped, so the unknowns are
> pinned." 015-03's pre-implementation frame-critique falsified this: 011 being
> *shipped* doesn't make it *able to consume* a spec-centric verdict for
> spec-less findings. The S axis was needed after all — **spike 015-05** resolved
> the heartbeat-boundary unknown with data and landed
> [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md):
> **suitability gates Compile, not the heartbeat.** 015-03 is re-scoped to the
> Compile precondition (heartbeat gate retired); the heartbeat keeps `gate.py` and
> 011-02's `skipped` invariant is preserved.

| Slice | Title | Axis | Goal |
|---|---|---|---|
| [015-01](slice-01-verdict-contract.md) | verdict-contract | Rules | Emit the ADR-0015 verdict JSON from a spec + 001 signals + 006 classification; closed three-state enum; `schema_version`; fail-closed default; deterministic rule table v1; standalone `.servo/suitability/<spec-id>.json` artifact. **DONE.** |
| [015-02](slice-02-missing-evidence.md) | missing-evidence | Rules | Populate `missing_evidence` with actionable, blocking-flagged items keyed to a closed `kind` taxonomy; verdict ⇔ list coherence; re-runnable. **DONE.** |
| [015-03](slice-03-pipeline-gate.md) | compile-precondition | Path | **DONE (2026-06-30).** Gates the **Servo Compile** entry (016-01's `execution_plan.py compile`) on a `suitable` verdict — halts + surfaces `reasons`/`missing_evidence` otherwise; fail-closed on an unavailable verdict; heartbeat-boundary regression guard. Heartbeat per-finding gate **retired** (ADR-0018). |
| [015-04](slice-04-skill-and-explain.md) | skill-and-explain | Interface | `/servo:edd-suitability` surface (human + `--json`), `--explain` rule trace, re-run dogfood; document the model-assist extension point + waiver posture. Closes spec 015. |
| [015-05](slice-05-suitability-boundary-spike.md) | suitability-at-the-boundary | **Spike** | **DONE.** Resolved with data (36 real findings) that suitability is Compile-phase-only, not a heartbeat gate; landed [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md) + re-scoped 015-03. |

## Open questions

- **Deterministic rules vs model-assist.** Start rule-table-only (explainable,
  reproducible) — but some suitability signals ("is success irreducibly taste?")
  resist deterministic rules. When does the optional model-assist layer earn its
  place, and how is its non-determinism bounded (cf. ADR-0005)?
- **Human override of a `needs_evidence` / `unsuitable` gate.** A waiver
  mechanism (and its audit trail) — borrow spec-006's waiver posture, or new?
- **Verdict freshness.** Does the verdict expire when the spec or signals drift
  (links to 018 continuous-evaluation's recompilation trigger)?
- ~~**Where the artifact lives.**~~ **Resolved (015-01):** standalone
  `<target>/.servo/suitability/<spec-id>.json`; ADR-0016's execution plan
  *references* it rather than copying it. Folding it into the plan is deferred to
  spec 016.

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
