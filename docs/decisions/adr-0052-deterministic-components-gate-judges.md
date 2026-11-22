---
status: Proposed
dependencies: []
last_verified: 2026-11-21
frame_review: true
---

# ADR-0052: Deterministic components gate judged components

## Status

Proposed (2026-11-21). **Recorded, not yet built** — implemented by
[spec 047](../specs/047-deterministic-first-oracle/spec.md); this ADR must be
Accepted before 047-01 moves past DRAFT. Investigation record: jig
[R-002](https://github.com/ramboz/jig/blob/main/docs/research/R-002-claude-code-verification-assessment.md),
item 10 ("Cheap checks first").

## Context

The Claude Code team runs the cheap deterministic checks — build, lint, tests —
before any model review (R-002 item 10). servo's compiled oracle does the
opposite of "cheap first": it scores every component, every time, and averages.

What the code does today (probed 2026-11-21, working tree at `3e92dfc`):

- **Plain oracle.** `templates/oracle.sh.template:58-75` loops over `COMPONENTS`
  in array order, calls every `score_<name>`, and only afterwards decides: any
  rc-2 component → exit 2 (`:77-80`), otherwise the weighted average is compared
  to `THRESHOLD` (`:87-93`). Nothing short-circuits.
- **Judged components tend to run first.** The three frozen-eval installers
  (design-eval, content-fidelity, eval-authoring) all register through
  `fidelity_eval.splice_components_entry`, which inserts the new entry at the
  *top* of `COMPONENTS` (`skills/_common/fidelity_eval.py:397-409`).
- **Required-policy oracle.** Once a required policy is installed, everything
  after the `weighted_sum="0"` anchor is replaced by an `exec` into the vendored
  `.servo/required_runtime.py` (`skills/spec-oracle/oracle_overlay.py:392`;
  `skills/quality-gate/required_runtime.py:20-23`). Its `oracle()` again runs
  each component once in `COMPONENTS` order (`required_runtime.py:762-823`), and
  the gate side re-derives the composite and decision from the payload,
  comparing the component list *in `COMPONENTS` order* (`:877-918`).
- **A judged component costs `n × |cases|` model calls per scoring**
  ([ADR-0005](adr-0005-eval-oracle-component.md) clause 6), plus capture time
  for design-eval. The loop does not meter that spend: it accrues runner/judge
  session cost only (`skills/agent-loop/loop.py:4785`), which
  [ADR-0041](adr-0041-unpriced-oracles-refuse-usd-execution.md)'s Context
  already records ("Current loop reads coding-agent spend, not a priced native
  oracle ledger").

So when a loop iteration leaves the tests at 0, the vision or text judge still
runs, its score cannot change the gate's verdict, and its cost is invisible.

Prior decisions shape the answer:

- **ADR-0005 left this open.** Its Open questions ask about eval cadence and
  lean: "gate eval scoring on a green deterministic floor first; revisit if it
  starves iteration." This ADR answers that question in a narrower form.
- **[ADR-0044](adr-0044-required-constraints-cannot-be-averaged-away.md)**
  already makes a failed deterministic requirement decide the gate
  (`required_constraints_failed`) whatever the quality average says.
- **[ADR-0002](adr-0002-gate-caller-contract.md)** fixes the closed `0/1/2`
  exit contract every consumer (loop, oracle-hook, heartbeat, variant-race)
  relies on.
- **A `None` composite is not neutral.** In the required path it means
  `required_evidence_unavailable`, exit 2 (`required_runtime.py:706-708`); the
  loop's plateau detector ignores non-numeric composites (`loop.py:766-770`).
- **[Spec 039](../specs/039-variance-gated-eval-judging/spec.md)** (DRAFT,
  parked "until a consumer shows judge cost matters") is a *different* axis:
  inside one judged component, a cheap judge before a frontier judge, per case,
  gated on sample variance. This ADR is *across* components: deterministic
  before any judge, gated on whether the verdict is already decided.

## Decision Options Considered

### Option A: Status quo — score everything, then average
- **Pros:** no change; every iteration carries a judged score for the runner and
  the judge agent to read; one code path.
- **Cons:** pays for judges whose score cannot change the verdict; judged
  components often run *first* (installer order), so a red build still waits on
  a screenshot-and-judge cycle; the waste is unmetered.

### Option B: Ordering only — deterministic first, judges always run
- **Pros:** trivially verdict-preserving; deterministic failures show up earlier
  in stderr; small change.
- **Cons:** saves nothing — every judge still runs. Ordering alone does not do
  what the post describes.

### Option C: Skip judges when deterministic checks fail; composite from deterministic components only
- **Pros:** saves the spend; simple to explain.
- **Cons:** re-normalizing over deterministic weights can *raise* the composite
  above the full one — a skip could turn a fail into a pass unless the exit is
  forced separately; composites stop being comparable across iterations (some
  over all weights, some over a subset), which corrupts plateau detection
  (ADR-0005 clause 4).

### Option D: Skip judges only when the deterministic results already decide the gate; fail explicitly (chosen)
Run deterministic components first. Skip every judged component **iff no score
in [0, 1] for the judged components could change the gate's exit code**. Exit
as full scoring would have; record which components were skipped and why.
- **Pros:** verdict-preserving over every score the judges could return —
  testable as a property; saves the spend in exactly the case the post targets
  (red tests); never confers a pass; no new knob for authors.
- **Cons:** two runtimes (bash template, required runtime) plus the gate's
  re-derivation must implement the same rule; the composite on a skipped run is
  a lower bound, not the full average; the runner gets no judged feedback while
  the deterministic floor is red; a judge that is down goes unnoticed until the
  deterministic floor clears (see constraint 4).

### Option E: Green-floor gating — judges run only when every deterministic component scores 1.0
- **Pros:** closest to "cheap checks first" as the post states it; ADR-0005's
  own lean; maximum savings.
- **Cons:** changes outcomes: a target that passes today on tests 0.9 + judge
  1.0 could no longer pass, so it is a policy change to the gate, not a cost
  optimization; it can starve the judged signal, the risk ADR-0005 named.

## Recommended Decision

**Option D**, with these constraints. The exact mechanism (where the kind is
declared, field names) is spec 047's work, under test.

1. **Each component has a kind: `deterministic` (default) or `judged`.** The
   kind lives with the *installed component*, not in the frozen eval definition.
   It decides execution order and skip eligibility — **never** the verdict, so a
   wrong or missing label can cost savings but cannot change an exit code
   (beyond constraint 4's named unavailable-judge case).
2. **Deterministic components run first.** Required-policy components
   (ADR-0044) are always deterministic and are never skipped.
3. **The skip rule.** After the deterministic pass, skip all judged components
   iff the exit code is already decided:
   - a deterministic component is unavailable (rc 2 / `unknown`) → exit 2;
   - a required constraint failed → exit 1 (ADR-0044);
   - the quality ceiling — the weighted average with every judged component at
     1.0, rounded as the composite is — is below `THRESHOLD` → exit 1.
4. **What a skipped run reports.** The exit code equals what full scoring would
   have produced whenever every skipped component would have returned a score.
   The one named difference: if a skipped judged component would have been
   unavailable (rc 2), full scoring exits 2 (`env_error`) and the skipped run
   exits 1 — the judge's unavailability surfaces on the first iteration that
   actually needs it, and is never read as a 0.0 score. The composite is the
   **lower bound**: skipped components
   contribute 0 to the numerator and keep their weight in the denominator, so it
   stays numeric (no accidental exit 2) and comparable across iterations. The
   result names each skipped component and the reason. In the required path a
   required failure is reported as `required_and_quality_failed` only when the
   quality ceiling is also below the threshold; otherwise as
   `required_constraints_failed`, because quality was not evaluated and must not
   be reported as failed (ADR-0044's side-by-side honesty).
5. **A skip never yields a pass,** and the gate's independent re-derivation
   (`required_runtime.py:877-918`) verifies that any recorded skip was decided;
   an undecided skip is an env error.

**Existing frozen evals.** The kind is not part of `config.json`, and
`definition_hash` covers only judge, samples, threshold, cases and the kind's
extra fields (`fidelity_eval.py:245-259`), so **no frozen eval goes stale and
nothing is re-frozen**. A plain-oracle target opts in by re-installing a judged
component (re-splicing its fragment with the kind) and re-scaffolding
`oracle.sh`; until then it behaves exactly as today. `oracle.sh` stays the
developer's file (product-vision "Per-project artifacts beat plugin-owned
runtime").

**Existing required-policy approvals.** These are different: every approved
required binding pins the bytes of the required runtime it was approved with
(`required_runtime.py:450-451`, written at `oracle_overlay.py:513-518`). So the
required-path change (047-02), like any change to `required_runtime.py`, means
each required-policy target re-approves and reinstalls its required checks
once. Until it does, it either keeps today's behaviour (a vendored runtime pin)
or refuses with an env error (a shared-runtime pin that no longer matches) —
never a silent change in what is scored.

**Relationship to existing ADRs — none superseded.**
- **ADR-0002:** exit codes unchanged; the skip record is an additive optional
  field. Whether the lower-bound composite is a "semantic shift" that warrants a
  `schema_version` bump is an open question below.
- **ADR-0005:** answers its "eval cadence" open question with the
  verdict-preserving variant (Option D), not its green-floor lean (Option E).
  Clause 1 holds (an eval stays an ordinary `score_<name>`); clause 5 holds (a
  skip is a recorded decision, not unavailability read as 0.0).
- **ADR-0044:** builds on it — the required veto is one of the three decided
  conditions; required components are never skipped.
- **ADR-0041 / [ADR-0048](adr-0048-copilot-credit-budget-contract.md):**
  unchanged. A skip-eligible component can still run, so the up-front
  unpriced/USD refusals stay.
- **[ADR-0050](adr-0050-eval-is-signal-not-evaluability.md):** unchanged;
  suitability legs are untouched.

**Composition with spec 039.** The two compose: ADR-0052 decides *whether* a
judged component runs on this iteration; when it runs, 039 (if activated)
decides *which judge tier* scores each case. Neither reads the other's state.
047-03's skip telemetry is also part of the measurement 039's activation
trigger asks for (judge spend as a share of a run).

## Consequences

**Becomes easier:**
- A loop with red tests stops paying for judged scoring every iteration, and the
  iteration finishes sooner (no capture/judge wait).
- The runner gets a clearer instruction: fix the deterministic floor first.
- Judge spend becomes visible as "calls avoided" (047-03), the first per-run
  signal of how much judge cost a target carries.

**Becomes harder:**
- The rule must be implemented identically in the bash template, the required
  runtime, and the gate's re-derivation, and kept in sync.
- Shipping the required-runtime half costs every required-policy target one
  re-approval and reinstall (see above). Batch 047-02 with other
  required-runtime changes where possible.
- `oracle_overlay`'s canonical-template check (`oracle_overlay.py:356`) must
  accept both the pre-047 and the new template, or existing targets cannot take
  a first required install.
- On skipped runs the composite reads lower than full scoring would; consumers
  that rank or plateau on it (loop plateau and the 038 escalation ladder,
  variant-race ranking, the judge agent's prompt) see that. A loop that keeps
  tests red while improving judged quality now plateaus rather than continuing —
  intended (progress the gate cannot see yet) but a behaviour change.
- The judged signal is withheld while deterministic checks decide the fail, and
  so is a judge outage: a run that full scoring would end as `env_error` (judge
  unreachable) ends as `below_threshold` until the deterministic floor clears.

## Assumptions

- **Scores lie in [0, 1] and weights are non-negative.** The verdict-preservation
  argument depends on it. The template states it as the contract
  (`oracle.sh.template:9-13`) but does not enforce it; the required runtime
  enforces it (`required_runtime.py:765`, `:807`, `:888`). The three
  frozen-eval scorers clamp their composite to [0, 1]
  (`skills/design-eval/score.py:999`, `skills/content-fidelity/score.py:337`,
  `skills/eval-authoring/score.py:623`).
- **Judge spend is material for real targets.** Unmeasured, the same premise as
  spec 039's activation trigger. 047-03's telemetry measures it.
- **Withholding judged feedback while the deterministic floor is red does not
  slow convergence.** Unmeasured; see Kill criteria.
- **A per-component kind declaration can travel with the installed fragment**
  without touching `definition_hash` or the required-policy seal: SEED blocks
  are already stripped from `driver_identity` (`required_runtime.py:25-31`).
  Spec 047 confirms the exact mechanism at 047-01's DoR.

## Kill criteria

- A skipped run ever produces a different exit code than full scoring on the
  same inputs, other than the named judged-unavailable case (the property fails
  in a real case). Fall back to Option B.
- Judged-heavy targets measurably need more iterations to converge, or
  plateau-halt early, with skipping than without. Revisit — likely limit
  skipping to the env-error and required-fail conditions.
- 047-03 telemetry shows skips are rare or the calls avoided are negligible
  across real runs. The machinery is not earning its upkeep; keep ordering only.

## Open questions

- Does the lower-bound composite on skipped runs count as an ADR-0002 "semantic
  shift" requiring a `schema_version` bump, or is the explicit skip record
  enough? Lean: no bump (exit semantics are unchanged and the basis is marked);
  arch-review on 047-03 decides.
- Should a target be able to opt into Option E (green floor) as an explicit,
  reviewed policy? Out of scope; it changes outcomes and needs its own decision.
- Should plateau detection treat skipped iterations differently (exclude them,
  or count them only against the deterministic part)?
- Should heartbeat's whole-pass ceiling ([ADR-0012](adr-0012-heartbeat-whole-pass-cost-ceiling.md))
  report calls avoided across dispatched loops?
