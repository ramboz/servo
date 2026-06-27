---
status: DRAFT
last_verified: 2026-06-26
---

# Product vision: servo

> Status: Draft. Refined as specs land.

## Vision

A Claude Code plugin that **compiles engineering intent into executable
evaluation** — and then executes against it. Servo is an **Evaluation-Driven
Development (EDD) engine**: given an engineering specification, it decides
whether the work suits EDD, compiles the spec into oracle + evidence + execution
plan, and runs an implementation against that compiled evaluation until it
converges — so devs can move past supervised spec-driven dev into headless
iteration without hand-building the evaluation infrastructure each time.

The autonomous execution loop is **one consumer** of the compiled evaluation, not
the headline. Evaluation is the source of truth; execution is an optimization
process against it. See [ADR-0014](decisions/adr-0014-evaluation-compiler.md).

## Evaluation-Driven Development

**Evaluation-Driven Development is an engineering process where success criteria
are explicitly modeled as executable evaluation before implementation.** Rather
than relying on humans to repeatedly judge progress, evaluation becomes
executable; implementation is then optimized toward that executable evaluation.

- **Evaluation is the source of truth.**
- **Execution is an optimization process** against that truth.

EDD spans both deterministic evaluation (the checks `oracle.sh` and
`/servo:spec-oracle` produce) and non-deterministic evaluation (the frozen,
hashed-and-approved judge components of
[ADR-0005](decisions/adr-0005-eval-oracle-component.md), which is the narrow
original sense of "EDD" — now one special case of the wider practice).

## Two phases: Servo Compile and Servo Run

Servo is structured as two conceptual subsystems. The portable execution loop is
**one stage inside Servo Run**, not the product.

```text
            ┌──────────────────── Servo Compile ─────────────────────┐  ┌────────── Servo Run ──────────┐
Specification → EDD Suitability → Evidence Compilation → Evaluation Model
            → Oracle Synthesis → Execution Planning → Execution Loop → Evaluation Report
```

- **Servo Compile** consumes an engineering specification and produces an
  *evidence model*, an *evaluation model*, an *oracle*, and an *execution plan*:
  EDD suitability analysis, evidence extraction/normalization, evaluation-model
  generation, oracle synthesis, execution planning.
- **Servo Run** consumes those compiled artifacts and executes an implementation
  against them until convergence or failure: orchestration (the portable loop,
  host-scope routing, dispatch), per-turn evaluation via the oracle, convergence
  detection, and reporting. It produces an *implementation*, *evaluation
  reports*, *convergence diagnostics*, and *recommendations*.

## Responsibilities

Servo and jig divide cleanly: **jig owns engineering intent, servo owns
engineering evaluation.**

| Servo owns | Servo does **not** own (jig's territory) |
|---|---|
| EDD suitability analysis | Product discovery |
| Evidence extraction & normalization | Feature design |
| Evaluation compilation | Requirements gathering |
| Oracle synthesis & explainability | Architectural exploration |
| Execution planning & autonomous execution | Engineering judgment about *what* to build |
| Convergence detection & evaluation reporting | |

Jig remains the human-centered engineering workflow (understand → design →
specify → refine). Servo picks up at the spec and turns it into executable
evaluation.

## Target users

Developers who already practice spec-driven, supervised AI development (the jig
audience) and want to graduate to:

- Compiling a spec's success criteria into an executable oracle instead of
  re-judging progress by hand each iteration
- Running agent loops headlessly against that compiled evaluation
- Installing meta-judge hooks that score every `Stop` and emit retry suggestions
- Racing worktree variants in parallel and picking the winner by score
- Putting the whole evaluate-then-execute pipeline on a **schedule** — letting
  servo surface work from the project's own signals (CI failures, open issues,
  recent commits) and queue it unattended, instead of hand-kicking each loop

Servo is **not** for users who haven't yet adopted spec-driven dev. The risk
profile is materially higher, and the prerequisites (composable quality signals,
slice-shaped work) come from the supervised practice servo builds on.

### Continuous evaluation — the heartbeat

Servo's first surfaces are all **human-triggered**: a dev decides what to work on
and kicks off the pipeline. The **heartbeat** adds a **schedule-triggered**
surface and is the seed of *continuous evaluation* — a Routine (cron, a scheduled
agent, a CI `schedule:` trigger) wakes servo on an interval; servo does a
**read-only** discovery pass over the project's own signals, writes findings to a
servo-owned **triage inbox**, and hands each *actionable* one through the
oracle-gated Servo Run pipeline in an isolated worktree. This is a materially
**higher-risk surface** — servo now decides *what* to evaluate, not just *how* —
so it carries its own non-negotiable controls (see the design principle below)
and is Tier-2 (explicit opt-in only). Servo ships the heartbeat; the Routine is
the clock. See Phase 4 below and [spec 011](specs/011-heartbeat/spec.md).

## Core problem

Compiling a real spec into executable evaluation — and running against it — is
exactly the infrastructure devs rebuild on every project:

1. Writing a project-specific `oracle.sh` that composes the right signals (which
   signals does this project even *have*?)
2. Tuning weights and thresholds by hand
3. Translating each spec's acceptance criteria into executable evidence instead
   of relying on a generic judge
4. Wiring loop drivers, hook installers, and race orchestrators that consume the
   compiled evaluation
5. Repeating all of the above on the next project

The same scars, every project. Servo encodes the compilation + execution
scaffolding so the dev sets weights and prompts — not infrastructure.

## Competitive landscape

- **jig** — supervised spec-driven dev; owns engineering *intent*. Sibling, not
  competitor. Servo owns engineering *evaluation* and picks up where jig stops.
- **claude-flow, agent-frameworks, autogen** — heavyweight, opinionated execution
  runtimes. Servo is the opposite shape: it compiles evaluation and stays a thin
  scaffolder with no runtime lock-in, living in the project's own scripts.
- **GitHub Actions / CI recipes for agents** — distribution mechanism, not an
  evaluation compiler. Servo could feed into them, but isn't one.

## Roadmap

The roadmap is organized around **evaluation capability**, not incremental loop
features. Phases map onto the Compile/Run pipeline; see
[docs/specs/ROADMAP.md](specs/ROADMAP.md) for the per-spec breakdown.

### Phase 1 — Execution Runtime *(largely shipped)*

The Servo Run stage: a portable loop, oracle execution, and the agent
abstraction. Specs 002 (`/servo:quality-gate`), 003 (`/servo:agent-loop`), 004
(`/servo:oracle-hook`) — all **DONE**. 005 (`/servo:variant-race`) is the parked
best-of-N optimization.

### Phase 2 — Evaluation Compilation *(in progress)*

The Servo Compile stage: turning a spec into executable evaluation. Oracle
synthesis from signals (001 `/servo:scaffold-init` — **DONE**), spec → evidence
overlay (006 `/servo:spec-oracle` — **DONE**), the human-in-the-loop eval
authoring front-end (008 — parked), design-fidelity eval compilation (012
`/servo:design-eval`). The two named-but-unbuilt Compile steps are now specced:
the **EDD suitability analyzer** (015 + [ADR-0015](decisions/adr-0015-edd-suitability-gate.md))
as the fail-closed gate before everything, and the **execution planner** (016 +
[ADR-0016](decisions/adr-0016-execution-plan-artifact.md)) as the durable
Compile→Run handoff artifact — both DRAFT scope-capture, parked behind a grounding
consumer.

### Phase 3 — Evaluation Intelligence *(scope-captured; seeds shipped)*

Making the compiled evaluation smarter and explainable: oracle debugging,
convergence analysis (the plateau / noise-floor work in 003-05 + ADR-0005 is the
seed), adaptive planning, evaluation explainability, and cost optimization (the
heartbeat whole-pass ceiling, ADR-0012, is a seed). Captured as the umbrella spec
017, expected to split into per-capability specs as each is grounded.

### Phase 4 — Continuous Evaluation *(seeded by the heartbeat)*

Evaluation that runs on its own: continuous evaluation, repository monitoring,
automatic recompilation when the spec or signals drift, regression execution, and
long-running evaluation workflows. The heartbeat (011) is the first surface here;
where it leads is captured as spec 018, which inherits every heartbeat control.

## MVP scope

Spec 001 (`/servo:scaffold-init`) only — oracle synthesis from detected signals,
the first Compile step. Other skills come later, gated on 001 landing.

## Design principles

- **Evaluation before execution.** Servo compiles a spec into executable
  evaluation first; the loop optimizes against that compiled evaluation. The
  oracle is the source of truth, never the transcript-only judge
  ([ADR-0008](decisions/adr-0008-loop-on-autonomy-primitives.md),
  [ADR-0011](decisions/adr-0011-host-native-phase-hints.md)).
- **Two install layers, named explicitly.** *Servo runtime install* (getting
  servo's own skills/agents/templates onto a machine — via plugin root, release
  zip, or a project-local `.claude/` scaffold) is a different thing from *project
  oracle install* (`/servo:scaffold-init` dropping a tailored `oracle.sh` +
  `.servo/install.json` into a target repo). All three runtime surfaces share one
  contract and one verifier (`scripts/verify_install.py`); see
  [architecture.md](architecture.md) and the README for the chooser. *Spec 007 —
  DONE.*
- **Per-project artifacts beat plugin-owned runtime.** The dev's `oracle.sh` is
  theirs; servo only compiles and scaffolds it.
- **Refuse-on-missing-prerequisite.** If servo's runtime skills can't find
  `oracle.sh`, they exit non-zero. No silent degradation — no execution without a
  compiled evaluation.
- **Reversibility.** Hooks install and uninstall cleanly. Race worktrees clean up
  by default.
- **Signal-aware, not signal-prescriptive.** Probe what's there. If lint isn't
  configured, don't compile it into the composite.
- **Schedule-triggered is a distinct surface from human-triggered.** Servo's
  first six skills assume a human kicks off the pipeline. The heartbeat (spec 011)
  lets a *schedule* trigger it — so servo decides *what* to evaluate, not just
  *how*. That new audience/risk surface carries its own non-negotiable controls:
  discovery is strictly **read-only** (it proposes via the triage inbox, it never
  executes), the hard cost ceiling bounds the **whole heartbeat** (discovery +
  every spawned loop, not per-loop), and **refuse-without-oracle** still holds at
  the dispatch boundary (no finding spawns a loop without passing the oracle).
  Servo ships the heartbeat; it does **not** own the scheduler — same as it can
  feed CI but isn't a CI.

## Future scope

- Grounding and building the parked Compile-phase specs — the EDD suitability
  analyzer (015) and the execution planner (016)
- Spec-specific evidence overlays (`/servo:spec-oracle`) extended with
  auto-generated negative controls
- A short architecture-doc section "Why no crew skill" + post-mortem template
  (multi-agent crew coordination doesn't yet generalize enough to ship as a skill)
- Pull-hint integration with jig's `slice-land prepare`

## Vision statement

> Servo does not automate software development. Servo automates the
> transformation of engineering intent into executable evaluation. Autonomous
> execution is a consequence of executable evaluation — not the primary goal.
