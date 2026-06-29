---
status: Accepted
date: 2026-06-28
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0018: EDD suitability gates Compile, not the heartbeat

## Status

Accepted (2026-06-28)

Narrows [ADR-0015](adr-0015-edd-suitability-gate.md) (still Accepted for the
verdict contract it defines). Decided by the spec **015-05** spike.

## Context

[ADR-0015](adr-0015-edd-suitability-gate.md) defined the EDD **suitability
verdict** — a closed three-state gate (`suitable` / `needs_evidence` /
`unsuitable`), fail-closed, with a `missing_evidence` list — and asserted it
gates the pipeline at **two** call sites: the Servo Compile precondition **and**
the heartbeat's per-finding dispatch boundary ("a finding that is `unsuitable` /
`needs_evidence` is recorded `skipped` rather than spawning a loop"). Spec
015-01/02 shipped the verdict + evidence artifact; spec 015-03 was to wire it
into those two consumers.

015-03's pre-implementation frame-critique (slice declared `frame_review: true`)
found the heartbeat half rests on an assumption that does not hold, and the
**015-05 spike** confirmed it with data:

- The verdict is **spec-centric**: `suitability.py decide()` keys off **AC
  classification** (`oracle_plan.py classify` over a `spec.md`) plus the target's
  signals. It needs a spec with acceptance criteria.
- A heartbeat **finding is spec-less**: `heartbeat.py discover` enumerates CI
  failures / open issues / recent commits and frames each *directly* as a
  `loop.py --prompt`. It has no `spec.md` and no ACs.

Spike measurements (`ramboz/servo`, 36 real findings; the gate sees only the **3
actionable** ones):

- **finding→spec linkage:** **0 / 3** actionable findings carry any recoverable
  spec reference (all are CI failures with evidence
  `{run_url, workflow, branch, event}`). Not available in practice.
- **ephemeral-spec synthesis** (synthesize a `spec.md` from a finding, run the
  real analyzer against a tests+ci+lint target): **`needs_evidence` for 36 / 36**
  findings — a finding has no ACs, so `n_evaluable == 0`. The gate would skip
  **100%** of work. An off switch, not a gate.
- **marginal value over the existing oracle preflight:** the heartbeat **already**
  refuses dispatch without a passing-capable oracle (`gate.py <target>` preflight,
  Guardrail #3) and re-verifies the provisioned worktree (`gate.py <worktree>`);
  a loop that cannot satisfy the oracle is recorded `tried`, never falsely
  `passed`. The "vacuous green oracle / false pass" risk ADR-0015 cites is a
  **spec-level** risk (all-residual ACs + a vacuous oracle) that manifests at
  **Compile**, where a spec with ACs exists — not at the already-oracle-anchored,
  spec-less heartbeat boundary.

## Decision

**The suitability verdict gates Servo Compile, not the heartbeat.**

1. The verdict (015-01/02) is consumed at the **Compile precondition** only:
   Compile proceeds on `suitable`, and halts on `needs_evidence` / `unsuitable`,
   surfacing `reasons` + `missing_evidence`.
2. The **heartbeat does not consult the suitability verdict** per finding. It
   keeps `gate.py` (oracle preflight + worktree verification) as its sole
   evaluability gate. The planned per-finding suitability `skipped` writer is
   **retired** — so **011-02's `skipped`-is-human-only contract stands unchanged**
   (no inbox-contract evolution, no new automated `skipped` setter).
3. A **finding-shaped** evaluability check (a *new* analyzer over finding features
   — source type, evidence, target signals — not this spec-centric verdict) is
   **out of scope** here and deferred to spec **018 (continuous-evaluation)**. It
   must first demonstrate value **over** the existing `gate.py` preflight before
   it earns a place.

This narrows ADR-0015's "it gates, including at the heartbeat boundary" clause.
The rest of ADR-0015 — the closed three-state verdict, fail-closed default,
"gate not score," and the `missing_evidence` contract — remains in force.

## Consequences

**Positive.**

- The gate is wired only where it is coherent (a real spec with ACs), so it can
  never degenerate into a 100%-skip off switch at the heartbeat.
- The inbox contract is *simpler*: 011-02's human-only `skipped` invariant is
  preserved; no first-automated-`skipped`-writer evolution to reconcile.
- The decision is evidence-backed (the 015-05 spike), not a guess.

**Negative.**

- Servo has no enforced suitability gate on heartbeat-dispatched work *beyond*
  the oracle preflight. Accepted: the oracle preflight already covers the
  evaluability question for spec-less findings; the residual (spec-shape) risk
  does not apply to them.
- The "two call sites" promise of ADR-0015 is reduced to one until a Compile
  entry point exists.

**Neutral.**

- Spec **015-03 is re-scoped** to the Compile precondition only (heartbeat ACs
  retired) and stays **DEFERRED pending spec 016** (which will own the Compile
  entry point the precondition gates). Spec 015-04 (skill surface) no longer
  depends on a heartbeat gate.
- No code changes from this ADR; 015-01/02 ship unchanged.

## Alternatives considered

- **Ephemeral-spec synthesis from a finding.** Rejected on data — degenerates to
  `needs_evidence` for 36/36 findings (no ACs to classify).
- **Explicit finding→spec linkage.** Rejected for v1 — 0/3 actionable findings
  carry one; it would require a new triage-enrichment step that does not exist.
- **A finding-shaped suitability variant at the heartbeat.** Not rejected outright
  but deferred to 018: it is a different analyzer, and its marginal value over the
  existing `gate.py` preflight is unproven. Building it now would be speculative.
- **Keep ADR-0015 as-is and force the heartbeat wiring.** Rejected — it produces
  an off switch (every finding `skipped`), the worst kind of silent failure.

## Verification

- The 015-05 spike Findings record the measurements above (reproducible from the
  scratch survey + synthesis prototype).
- When the Compile precondition is implemented (re-scoped 015-03, against spec
  016), its test proves Compile proceeds only on `suitable` and halts otherwise.
- A regression check that `heartbeat.py` does **not** import or subprocess
  `suitability.py` keeps the boundary honest.

## References

- [ADR-0015](adr-0015-edd-suitability-gate.md) — the suitability verdict contract
  this narrows (heartbeat clause); its `## Amendments` flags the same gap.
- [ADR-0014](adr-0014-evaluation-compiler.md) — the Compile/Run split; the
  Compile phase this gate belongs to.
- [ADR-0016](adr-0016-execution-plan-artifact.md) — the execution-plan / Compile
  entry (spec 016) the re-scoped precondition will gate.
- [Spec 015 — edd-suitability](../specs/015-edd-suitability/spec.md): slice
  **015-05** (the spike that decided this), **015-03** (re-scoped, deferred).
- [ADR-0010](adr-0010-triage-inbox-schema.md) — the `skipped` lifecycle whose
  human-only invariant this decision preserves.
