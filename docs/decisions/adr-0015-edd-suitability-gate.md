---
status: Accepted
date: 2026-06-26
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0015: EDD suitability analysis is a fail-closed gate, not a score

## Status

Accepted (2026-06-27)

## Context

[ADR-0014](adr-0014-evaluation-compiler.md) makes Servo Compile a first-class
phase: spec → executable evaluation. The brief that prompted it names two
responsibilities Servo Compile must own *before* it synthesizes an oracle:

1. **determine whether the work is suitable for Evaluation-Driven Development**,
   and
2. **identify missing evidence**.

Today servo has neither as a named step. `/servo:scaffold-init` (001) probes
signals and *always* emits an oracle — a no-signal target gets a comment-only
oracle that exits 2. `/servo:spec-oracle` (006) classifies ACs into deterministic
families vs `residual_judgment`, but it does not judge whether the *spec as a
whole* is EDD-shaped. Nothing answers "should this work go through EDD at all,
and if not, why?" before unattended execution begins.

That question is load-bearing because EDD's risk profile is asymmetric. Running
the loop against a spec that *cannot* be meaningfully evaluated (success is pure
taste, the only signals are vacuous, the ACs are all human-residual) burns budget
and produces a green oracle that means nothing — a **false pass**, the worst
failure mode for an unattended system. The heartbeat (011) makes this sharper:
it dispatches work *no human chose*, so an unsuitable finding must be refused at
the boundary, not optimized against.

The repo already has the contract shape this should follow: ADR-0002's closed
exit-code + closed `reason` taxonomy, fail-closed by default. Suitability should
be the same kind of artifact — a structured, auditable verdict — not a fuzzy
number.

## Decision

Servo Compile runs an **EDD suitability analysis** as its first step, producing a
structured **suitability verdict** that **gates** the rest of the pipeline. It is
a gate, not a score: the loop never runs against work the analysis cannot vouch
for.

### The verdict is a closed three-state gate

```json
{
  "schema_version": 1,
  "verdict": "suitable" | "needs_evidence" | "unsuitable",
  "reasons": ["..."],
  "missing_evidence": [
    {"kind": "tests" | "lint" | "ci" | "oracle_signal" | "reference_set" | "...",
     "detail": "...", "blocking": true}
  ],
  "spec_id": "...",
  "analyzed_at": "<ISO8601>"
}
```

- **`suitable`** — the work is EDD-shaped and has enough compilable evidence;
  Compile proceeds.
- **`needs_evidence`** — EDD-shaped *in principle*, but blocking evidence is
  missing (e.g. no test signal, ACs that are eval-able but lack a reference set).
  Compile **does not proceed**; servo emits the `missing_evidence` list as the
  actionable next step (acquire the evidence, then re-analyze).
- **`unsuitable`** — the work is not EDD-shaped (success is irreducibly human
  taste / policy / ADR judgment). Servo routes it back to the human/jig and
  **does not compile or execute**.

### Fail-closed default

Indeterminacy resolves to **not `suitable`**. An analysis that cannot establish
suitability with evidence yields `needs_evidence` (if the gap is nameable) or
`unsuitable` (if not) — never an optimistic `suitable`. This mirrors servo's
refuse-on-missing-prerequisite posture and the loop's fail-closed brakes: no
silent degradation into unattended execution.

### It gates, including at the heartbeat boundary

The verdict is the **dispatch precondition**. The heartbeat's oracle-gated
dispatch (011-03, Guardrail #3) already refuses a finding without an oracle; the
suitability verdict is the upstream sibling — a finding that is `unsuitable` or
`needs_evidence` is recorded back to the triage inbox (mapping naturally onto the
existing `skipped` lifecycle with an `actionable_reason`) rather than spawning a
loop.

### What this ADR does *not* decide

- The exact heuristics/judge that produce the verdict (deterministic rules vs a
  model-assisted pass) — left to spec 015, which may grow an ordered rule table
  the way spec 006 did.
- Whether suitability authoring is shared with jig — same open
  jig-vs-servo-home question spec 008 raised; decided when a real case forces it.

## Consequences

**Positive.**

- The worst unattended failure mode — a meaningless green oracle on
  un-evaluable work — is refused before any budget is spent.
- `missing_evidence` turns "this isn't ready" into a concrete checklist, which is
  the actionable half of EDD onboarding.
- One auditable artifact; consumers (Compile, heartbeat dispatch) branch on a
  closed enum, not a threshold.

**Negative.**

- A new refusal surface can block work a human judges fine; mitigated by
  `needs_evidence` being *actionable* (and overridable by acquiring evidence or
  an explicit human waiver, to be specced).
- Another `.servo/` artifact + schema to version.

**Neutral.**

- Does not change `oracle.sh`, `gate.py`, or loop behavior — it sits *upstream*
  of them.
- Subsumes no existing step; 001 still synthesizes the oracle, 006 still
  classifies ACs. Suitability consults their outputs.

## Alternatives considered

- **A suitability *score* in `[0,1]`.** Rejected: a threshold invites "close
  enough" auto-proceed, which is exactly the false-pass risk. A closed gate is
  safer for an unattended system.
- **No explicit gate — let the oracle's emptiness speak.** Rejected: a
  comment-only oracle that exits 2 is an *env error*, indistinguishable from a
  broken oracle; it does not say "this work is not EDD-shaped," and it gives the
  user no `missing_evidence` to act on.
- **Fold into `/servo:scaffold-init` (001).** Rejected: 001 is signal probing for
  *oracle synthesis*; suitability is a *spec-level* judgment that also runs for
  already-scaffolded targets (e.g. per-finding in the heartbeat). Different input,
  different cadence.

## Verification

To be established by spec 015. At minimum: the verdict is a closed three-state
enum with a `missing_evidence` list; indeterminate input yields a non-`suitable`
verdict; an `unsuitable`/`needs_evidence` finding in the heartbeat is recorded
`skipped` (not dispatched); the artifact carries `schema_version`.

## References

- [ADR-0014](adr-0014-evaluation-compiler.md) — the Compile/Run split this is the
  first step of.
- [ADR-0002](adr-0002-gate-caller-contract.md) — the closed-taxonomy, fail-closed
  contract shape this mirrors.
- [ADR-0010](adr-0010-triage-inbox-schema.md) — the `skipped` lifecycle +
  `actionable_reason` an unsuitable finding maps onto.
- [Spec 006 — spec-oracle](../specs/006-spec-oracle/spec.md) — AC classification
  the analysis consults; [Spec 015 — edd-suitability](../specs/015-edd-suitability/spec.md)
  — the consumer.
