---
status: DRAFT
dependencies: [011]
last_verified:
---

# Spec 018 — continuous-evaluation

> Phase 4 of the EDD roadmap: evaluation that runs on its own. A scope-capture
> umbrella over the capabilities that grow out of the heartbeat (011) —
> repository monitoring, automatic recompilation when the spec or signals drift,
> regression execution, and long-running evaluation workflows. The heartbeat is
> the first surface here; this spec captures where it leads. **Expected to
> split** into per-capability specs once a grounding consumer forces real
> acceptance criteria.

> **Status: DRAFT — scope capture, parked.** This is the "continuous evaluation"
> tier of [ADR-0014](../../decisions/adr-0014-evaluation-compiler.md)'s roadmap,
> the highest-risk and least-grounded. It depends on the heartbeat (011) being
> in real scheduled use; until a target actually runs servo on an interval and
> hits the drift / regression / recompilation needs below, this is captured
> direction, not queued work. The slice sketch is pre-SPIDR (goals only, no ACs),
> and every slice is Tier-2 (explicit opt-in) and ADR-gated.

## Why this spec

The heartbeat (011) gave servo a **schedule-triggered** surface: a Routine wakes
servo, it discovers work read-only, and dispatches actionable findings through
the oracle-gated pipeline. That is the *entry point* to continuous evaluation,
but it stops at "discover and dispatch once per wake." It does not notice when a
spec changes and its compiled evaluation goes stale, it does not re-run a past
evaluation to catch a regression, and it has no notion of an evaluation workflow
that spans many wakes.

The brief names these as Phase 4: **continuous evaluation, repository monitoring,
automatic recompilation, regression execution, long-running evaluation
workflows.** They share one shape — evaluation as a *standing process* over the
repository's life, not a one-shot a human kicks off — and one elevated risk
profile, since servo is now both choosing work *and* running unattended on a
clock. This spec captures that tier so the heartbeat's natural extensions have a
home, with the controls they will require stated up front.

## Goals (provisional)

1. **Repository monitoring.** Watch the project's evaluation-relevant state
   across wakes — which specs have compiled evaluation, which oracles exist, what
   the last verdicts were — as a standing view, not a per-wake rediscovery.
2. **Automatic recompilation.** Detect when a spec or its signals have drifted
   past the compiled evaluation (the freshness question 015 and the spec-oracle
   freeze raise) and re-run Servo Compile — re-analyze suitability, regenerate the
   overlay, rebuild the execution plan — fail-closed (stale ⇒ refuse to run the
   old plan, don't silently optimize toward an outdated oracle).
3. **Regression execution.** Re-run a previously-passing evaluation to catch a
   regression introduced elsewhere; record the result against the triage inbox /
   evaluation history.
4. **Long-running evaluation workflows.** Coordinate evaluation that spans many
   heartbeat wakes (multi-stage work, dependent findings) with durable state,
   building on the triage inbox state spine (ADR-0010) and the execution plan
   (ADR-0016).
5. **Keep the heartbeat's non-negotiables.** Everything here inherits the 011
   controls: read-only discovery, whole-pass cost ceiling (ADR-0012),
   refuse-without-oracle and refuse-on-dirty-tree at dispatch, untrusted-data
   framing, and the EDD suitability gate (015) per finding. Continuous ≠ relaxed.

## Non-goals

- **Not owning the scheduler.** Servo ships the heartbeat; the Routine/cron/CI
  `schedule:` is the clock (unchanged from 011). Continuous evaluation is what
  servo *does* each wake, not a scheduler servo runs.
- **Not auto-installing.** Tier-2, explicit opt-in only — same posture as the
  heartbeat and races.
- **Not loosening any brake to "keep things moving."** A stale/dirty/unsuitable
  state refuses; it does not degrade into running the old plan.
- **Not a monolith.** Umbrella scope-capture; each capability graduates to its own
  spec (and likely ADR) when grounded.

## Core model

Continuous evaluation is the heartbeat plus standing state and a recompilation
trigger:

```
   Routine wakes servo (the clock — not servo's)
        │
        ▼
[011 discover read-only] ──→ triage inbox (state spine, ADR-0010)
        │
[018 repository monitoring]  standing view of compiled-evaluation state
        │
   spec / signals drifted past compiled evaluation?
        │ yes                                  │ no
        ▼                                      ▼
[018 automatic recompilation]          [018 regression execution]
 re-run Servo Compile (015→001/006→016) re-run a passing evaluation
 fail-closed if still stale                    │
        └───────────────┬──────────────────────┘
                        ▼
        [011-03 oracle-gated dispatch] under the whole-pass ceiling (ADR-0012)
                        ▼
            evaluation history / reports (017)
```

All of it inherits the heartbeat's read-only-discovery + fail-closed-dispatch
controls; "continuous" raises the cadence, never lowers the guardrails.

## Provisional slice sketch (pre-SPIDR — likely splits into separate specs)

> Goals only, no ACs. Each row is a candidate standalone spec once scheduled use
> forces acceptance criteria.

| Slice / future spec | Title | Goal |
|---|---|---|
| 018-a | repository-monitoring | Standing cross-wake view of compiled-evaluation state (specs, oracles, last verdicts). |
| 018-b | drift-and-recompile | Detect spec/signal drift past compiled evaluation; re-run Servo Compile fail-closed. **ADR-gated.** |
| 018-c | regression-execution | Re-run a previously-passing evaluation; record regressions to history/inbox. **ADR-gated.** |
| 018-d | long-running-workflows | Multi-wake evaluation coordination on the inbox state spine + execution plan. **ADR-gated.** |

## Open questions

- **ADR candidates.** A recompilation *trigger* contract (what counts as "drift,"
  what fail-closed means when the new compile is still stale) and a regression
  *baseline* contract (what "previously passing" is pinned against) are each
  hard-to-reverse — own ADRs when scheduled use forces them. Not pre-written here.
- **Drift signal.** Spec-content hash (the spec-oracle freeze already hashes the
  source spec) is the obvious trigger; do signal changes (new tests, changed lint
  config) also trigger recompile, and how cheaply are they detected each wake?
- **History store.** Does evaluation history live in the triage inbox, a new
  `.servo/history/` artifact, or 017's evaluation reports? Reuse before inventing.
- **Cost across wakes.** ADR-0012 bounds one pass; continuous evaluation runs many
  passes — is there a higher-level budget across wakes, or is per-pass enough?
- **Relationship to CI regression suites.** Servo feeds CI but isn't CI; where is
  the line between continuous evaluation and the project's own regression CI?

## References

- [ADR-0014 — evaluation compiler](../../decisions/adr-0014-evaluation-compiler.md)
  — names this Phase 4 tier.
- [Spec 011 — heartbeat](../011-heartbeat/spec.md) — the first surface and the
  controls this inherits; [ADR-0010 — triage-inbox schema](../../decisions/adr-0010-triage-inbox-schema.md)
  (state spine), [ADR-0012 — heartbeat whole-pass cost ceiling](../../decisions/adr-0012-heartbeat-whole-pass-cost-ceiling.md)
  (the budget posture).
- [Spec 015 — edd-suitability](../015-edd-suitability/spec.md) (per-finding gate +
  freshness), [Spec 016 — execution-planner](../016-execution-planner/spec.md)
  (what recompilation rebuilds), [Spec 017 — evaluation-intelligence](../017-evaluation-intelligence/spec.md)
  (the reports history feeds).
