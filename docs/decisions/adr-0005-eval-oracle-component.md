---
status: Proposed
date: 2026-06-09
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0005: Eval as a frozen oracle component

## Context

servo's oracle is deterministic by construction. `oracle.sh` is a weighted
composite of `score_<name>` components each returning `[0.0, 1.0]`; `gate.py`
compares the composite to a threshold and exits `0/1/2` ([ADR-0002](adr-0002-gate-caller-contract.md)).
[Spec 006 (spec-oracle)](../specs/006-spec-oracle/spec.md) compiles a spec's
acceptance criteria into that same deterministic shape: each AC is classified
into a check family (`command`, `file_presence`, `json_contract`, …) or, when it
cannot be made deterministic, into **`residual_judgment`** — surfaced, blocked
from auto-complete, and waived or sent to a human. Spec 006's core model is
explicit: "deterministic checks remain the source of truth," and it adds no new
exit-code contract.

That leaves a gap. A class of acceptance criteria is real, spec-specific, and
genuinely non-deterministic — "the response is grounded in the retrieved
context," "the summary stays on-topic," "the rewrite preserves meaning." Today
these land in `residual_judgment`: the unattended loop (`/servo:agent-loop`)
**cannot optimize against them at all**. For eval-driven development (EDD) — the
motivating use case — that is the whole point: you want the loop to iterate
toward a non-deterministic target, not just toward "tests still pass."

The naive fix — have an LLM judge score the AC and feed that score to the
composite — is unsafe in an unattended loop for a specific, already-familiar
reason. A single judge call is stochastic; its score wobbles run-to-run even
when nothing changed. Fed raw into the composite, that wobble flaps the result
across `gate.py`'s pass/fail line and corrupts `loop.py`'s plateau detector
(false "improvement" that dodges a real plateau halt, or false plateau that
halts early). This is the **same operational failure class** servo already paid
for once — a stochastic signal driving a halt decision — except here the
non-determinism is inherent, not a test bug.

So the question this ADR settles is *not* "should servo score evals" but **under
what contract is a non-deterministic eval allowed to contribute to the oracle at
all** — such that an unattended, halt-on-threshold loop can trust it.

Two scoping notes:

- **This is the reciprocal servo-side ADR** that jig's ADR-0022
  (pluggable-oracle-boundary, PARKED) explicitly anticipated under "a reciprocal
  servo-side ADR — servo's call." jig's posture (ADR-0019/ADR-0022) is
  *attest-only*: jig records that an oracle ran; **servo runs and scores**, and
  for an eval the *project* authors the scorer. This ADR defines servo's half of
  that contract. It does not change jig's side.
- **This is design-intent recorded ahead of its first consumer.** No EDD spec
  exists yet, and spec 006's eval path is unbuilt (006 ships only the
  deterministic families). The ADR is written *now* precisely to constrain the
  future eval-authoring workflow and the spec-006 eval-family extension before
  either is built. It should move to Accepted when the first real non-deterministic
  spec exercises it — the "integrate on signal" discipline of ADR-0019, not a
  speculative build-out.

## Decision

A non-deterministic eval may contribute to servo's oracle **only as a frozen
eval component** — a `score_<name>` governed by a determinism-and-stability
contract. The contract has the following clauses.

**1. An eval is an ordinary `score_<name>` component — not a new gate and not
the judge agent.** It returns `[0.0, 1.0]` into the weighted composite and obeys
`gate.py`'s existing `0/1/2` contract verbatim. No new exit code, no new wire
format (consistent with spec 006's core model). It is distinct from the
per-iteration `judge` agent ([agents/judge.md](../../agents/judge.md)): the
judge scores *whether an iteration moved toward passing*; an eval component
scores *whether the output meets a specific AC*, over a fixed dataset. The two
must not be conflated — the judge is unfrozen and iteration-relative; an eval
component is frozen and AC-absolute.

**2. Freeze the definition, not the output.** Extending spec 006's freeze model
(slice 006-04: `approval_status` ∈ {draft, approved, stale}, source-hash,
artifact hashes), an approved eval component pins and hashes:

- the **rubric** (judge prompt / scoring criteria),
- the **dataset** it scores over (the fixed set of inputs) and its hash,
- the **judge model id and decoding params** (temperature, etc.) — an unpinned
  judge model is silent contract drift,
- the **sample count `n`** and the **aggregation rule**,
- the **stability margin `δ`** and the AC pass threshold,
- the **score semantics** (what `0.0` and `1.0` mean for this AC).

The *sampled scores themselves are not frozen* — they are inherently variable;
that is the whole point of the contract. A runner iteration may not edit an
approved eval artifact (spec 006 guardrail). A change to the rubric, dataset, or
model hash refuses with `spec_oracle_stale` (exit 2) until re-planned.

**3. n-sample aggregation with lower-bound gating (within-run anti-flap).** A
single judge call never gates. The component samples `n` times over the dataset
and reports, as its `[0,1]` contribution, a **conservative lower bound** of the
sampled distribution (e.g. `mean − k·stderr`, with `k`/`δ` frozen), not the
point estimate. The component therefore only contributes a high score when the
judge is *confident across samples*; scores within `δ` of the line read as "not
yet" rather than flipping run-to-run. The anti-flap logic lives **inside the
component**, so `gate.py`, the composite, and the exit-code contract are
untouched.

**4. Plateau uses a noise floor (across-run anti-flap).** `loop.py`'s plateau
detector treats composite improvements smaller than the eval component's frozen
noise floor `δ` as **flat**. A wobbling eval can thus neither fake progress (to
dodge a real plateau halt) nor fake a plateau (to halt early). This is the one
additive change to existing machinery the contract requires — a noise floor in
plateau detection, not a change to the gate contract.

**5. Infrastructure failure is `env_error`, never a silent zero.** Judge model
unreachable, dataset missing, sampling timeout, or unparseable judge output →
the component returns rc=2 (`env_error`, named in `missing`) → `gate.py`
fail-closed (exit 2), identical to a missing deterministic tool. "Judge
unavailable" must never read as "output scored `0.0`" — that would look like a
genuine quality failure and mislead the loop.

**6. Cost is bounded by the frozen definition and counts against the loop's cost
ceiling.** Per-run eval cost is `n × |dataset|` judge calls — predictable from
the frozen definition, so it can be budgeted up front — and accrues to
`loop.py`'s existing cost-ceiling guardrail.

**7. servo scores; it does not prove (honesty).** A composite pass that includes
an eval component means "the frozen eval scored ≥ threshold *with confidence* on
*this dataset*," not "the output is correct." Each eval run appends the rubric +
dataset + model hashes and the sampled + aggregated scores to spec 006's
`ledger.jsonl`, so a human can audit exactly what was scored and how. This is
ADR-0022's honesty posture and spec 006's "no universal semantic judge,"
restated for the eval case.

Together these define the compile target that a future eval-authoring step can
use to **promote a triaged subset of `residual_judgment` ACs** — the
rubric-able ones — into frozen eval components, leaving genuine taste / policy /
ADR-shaped ACs as human residual judgment (unchanged from spec 006's non-goals).
This ADR does **not** build that authoring workflow, pick a judge framework, or
implement the spec-006 eval family; it fixes the contract they target.

## Consequences

**Positive.**

- Non-deterministic ACs become loop-optimizable for the first time, with a
  signal that is *safe to gate on* in unattended mode.
- The eval's definition is frozen, hashed, and ledgered — reproducible and
  auditable even though its scores are not.
- Rides the existing contracts: no new exit code, no new gate wire format; the
  only additive change is a plateau noise floor (clause 4).
- The anti-flap rules (lower-bound gating + noise floor) directly defend the
  unattended halt decision against the stochastic-signal failure class.
- Gives the future eval-authoring skill and the spec-006 eval-family extension a
  fixed target to compile into, rather than each inventing its own.

**Negative.**

- Eval runs cost tokens/$ every iteration they are scored; `n` amplifies it.
  Mitigated by the cost ceiling and the predictable cost bound, but a careless
  `n`/dataset size can dominate a run's budget (see Open questions on cadence).
- The contract pushes real tuning burden onto the author: too wide a `δ` and the
  component never passes; too narrow and it flaps. Choosing `n`/`δ` well is the
  hard part, and it is now load-bearing.
- A frozen judge model ages — model deprecation forces a re-plan
  (`spec_oracle_stale`). Acceptable (it is honest drift detection) but real
  operational overhead.
- Introduces the first genuinely non-deterministic component into a so-far
  fully-deterministic oracle. servo still cannot *prove* correctness; it only
  scores with confidence.

**Neutral.**

- The dataset *format* and the eval-authoring ergonomics are deliberately not
  pinned here — they belong to the spec-006 eval-family extension and the future
  authoring skill.
- Default values for `n`, `δ`, and `k` are not fixed in this ADR; the first real
  EDD spec sets them, and defaults can crystallize from there.
- Reuses spec 006's freeze/approval machinery rather than adding a parallel one.

## Alternatives considered

- **Reuse the per-iteration `judge` agent as the AC oracle** (its
  `PASS/FAIL/INCONCLUSIVE + score`). Rejected: the judge scores *iteration
  progress*, is unfrozen and iteration-relative, and is not AC-/dataset-specific.
  Using it as the AC signal conflates "did this step help?" with "does the output
  meet this spec?" and yields no frozen, auditable definition.
- **Single-shot LLM judge, point-estimate gating** (no `n`, no lower bound).
  Rejected: too noisy; flaps the composite across the gate line and corrupts
  plateau detection — the exact failure this ADR exists to prevent.
- **Keep `residual_judgment` human-only forever** (spec 006 v1 status quo).
  Retained for the genuinely-taste subset, but rejected as a *ceiling*: it leaves
  the unattended loop unable to optimize against any non-deterministic AC, which
  defeats EDD.
- **A separate eval gate / new exit code outside the composite.** Rejected:
  violates ADR-0002's closed `0/1/2` contract and spec 006's "no new exit-code
  contract," and duplicates the halt logic.
- **jig grows the eval runner.** Rejected on scope: ADR-0019/ADR-0022 fix
  jig as attest-only; servo (and the project's scorer) runs evals. Out of scope.

## Verification

No slice implements this yet; these are the obligations the implementing slice
(a spec-006 eval-family extension) must satisfy:

- **Within-run anti-flap.** A frozen eval component whose *raw* per-sample score
  straddles the threshold, but whose lower bound stays on one side, must **not**
  flip `gate.py`'s pass/fail across repeated runs on unchanged input.
- **env_error vs zero.** An unreachable judge model / missing dataset yields
  component rc=2 → `gate.py` exit 2 (`env_error`, listed in `missing`), never a
  `0.0` score on the pass path.
- **Stale refuses.** A changed rubric / dataset / model hash refuses with
  `spec_oracle_stale` (exit 2) until re-planned.
- **Plateau noise floor.** `loop.py` treats composite deltas smaller than the
  eval's frozen `δ` as no-improvement; a test injects sub-`δ` wobble and asserts
  the plateau halt still fires (no false progress) and does not fire early.
- **Ledger evidence.** Each eval run appends rubric/dataset/model hashes plus
  sampled and aggregated scores to `ledger.jsonl`.

## Open questions

- **Eval cadence.** Should an eval component score every iteration, every `k`
  iterations, or only once the deterministic floor is green — to bound cost
  without starving the signal? Lean: gate eval scoring on a green deterministic
  floor first; revisit if it starves iteration.
- **Residual contribution.** This ADR informs spec 006's open question (does
  `residual_judgment` contribute `0.0`, leave the denominator, or force
  env-error until waived?): a *promoted* residual AC contributes its frozen eval
  score; an un-promoted one stays excluded/waived. The exact denominator rule
  is still spec 006's to settle.
- **Aggregation choice.** Lower-bound of mean (quality-style ACs) vs `pass@k`
  (capability-style ACs) — does the contract pick one, or is the aggregation
  rule a frozen per-component field? Lean: frozen per-component field.
- **Default `n`/`δ`/`k`.** Deferred to the first real EDD spec rather than
  guessed here.
- **Multimodal eval inputs (added 2026-06-11).** Clause 1's "judge model id" and
  clause 2's freeze list (rubric + dataset + hashes) tacitly assume **text** I/O.
  The first concrete consumer on the horizon — a **design-conformance eval** (does
  a rendered UI match a Claude Design `.dc.html` baseline? — surfaced exploring the
  SymPill Android/Compose app) — needs **image inputs** in the frozen dataset
  (design mock + rendered screenshot) and a **multimodal judge model**. The
  *deterministic* rungs of that use case (token-lint against the design-system
  token contract; semantic UI assertions) fit servo's existing oracle with no new
  capability; only this **visual** rung exercises this ADR. Lean: an image set is
  just another hashed dataset artifact (clause 2 already hashes "the dataset … and
  its hash") and the judge id must be a multimodal one — an explicit note, not a
  new clause. Revisit when a real multimodal eval is authored (jig ADR-0022 open
  Q#3 is the reciprocal spec-DONE-gate consumer).

## References

- [ADR-0002 — quality-gate caller contract](adr-0002-gate-caller-contract.md) —
  the `0/1/2` composite contract this rides without change.
- [ADR-0004 — session-state file format](adr-0004-session-state-file-format.md) —
  the per-run state the loop's halting logic reads/writes.
- [Spec 006 — spec-oracle](../specs/006-spec-oracle/spec.md) — core model,
  slice 006-04 freeze/approval model (extended here), the `residual_judgment`
  bucket (the source of promotable ACs), and the open question on residual
  contribution.
- `skills/quality-gate/gate.py` — the composite + closed exit-code contract.
- `skills/agent-loop/loop.py` — plateau + cost-ceiling guardrails (clauses 4, 6).
- [agents/judge.md](../../agents/judge.md) — the per-iteration judge agent, kept
  distinct from an eval component (clause 1).
- jig **ADR-0022 (pluggable oracle boundary, PARKED)** and **ADR-0019 (refactor
  workflow)** in the jig repo — the attest-only posture and the anticipated
  "reciprocal servo-side ADR" this one fulfils.
