---
status: ACTIVE
last_verified: 2026-07-12
---

# Product vision: servo

> Status: Active. Refined as specs land.

## Vision

A Claude Code and Codex plugin that **compiles engineering intent into executable
evaluation** — and then executes against it. Servo is an **Evaluation-Driven
Development (EDD) engine**. Its input may be a goal, curated acceptance
criteria, an existing engineering spec, or the quality signals already present
in a project. It helps author and review missing criteria, decides whether the
work suits EDD, compiles approved intent into an oracle + evidence + execution
plan, and can run an implementation against that evaluation until it converges.
A user-authored spec is a strong input, not a prerequisite or the product
boundary.

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
Engineering intent (goal | criteria | spec)
            → Criteria authoring / curation → EDD Suitability ───────┐
Project signals (tests | lint | CI | artifacts) ──────────────────────┤
            ┌──────────────────── Servo Compile ──────────────────────┴─┐  ┌────────── Servo Run ──────────┐
            Evidence Compilation → Evaluation Model → Oracle Synthesis
            → Execution Planning → Execution Loop → Evaluation Report
```

- **Servo Compile** consumes approved engineering intent plus project evidence
  and produces an *evidence model*, an *evaluation model*, an *oracle*, and an
  *execution plan*. If the input is only a goal, eval-authoring first proposes a
  minimal criteria artifact for independent review and human approval. Existing
  criteria/specs enter farther downstream; project signals feed evidence
  compilation directly.
- **Servo Run** consumes those compiled artifacts and executes an implementation
  against them until convergence or failure: orchestration (the portable loop,
  host-scope routing, dispatch), per-turn evaluation via the oracle, convergence
  detection, and reporting. It produces an *implementation*, *evaluation
  reports*, *convergence diagnostics*, and *recommendations*.

## Responsibilities

The ownership boundary is clean: **humans and upstream workflows own product
intent; Servo owns engineering evaluation.**

| Servo owns | Servo does **not** own (human/upstream territory) |
|---|---|
| EDD suitability analysis | Product discovery |
| Evidence extraction & normalization | Feature design |
| Evaluation compilation | Requirements gathering |
| Oracle synthesis & explainability | Architectural exploration |
| Execution planning & autonomous execution | Engineering judgment about *what* to build |
| Convergence detection & evaluation reporting | |

Specs from an upstream workflow are excellent Servo inputs, but they are not the
only entry point. Servo can also begin with a goal, existing criteria, or project
signals. Servo may help *author evaluation criteria*, but the human still owns
product intent and approves what success means.

## Target users

Developers and teams who have an engineering goal or existing artifact they want
to evaluate repeatably. They want to:

- Turn a goal into reviewed, human-approved evaluation criteria
- Compile existing criteria or a spec into an executable oracle instead of
  re-judging progress by hand each iteration
- Run agent loops headlessly against that compiled evaluation
- Install meta-judge hooks that score every `Stop` and emit retry suggestions
- Race worktree variants in parallel and pick the winner by score
- Put the whole evaluate-then-execute pipeline on a **schedule** — letting
  servo surface work from the project's own signals (CI failures, open issues,
  recent commits) and queue it unattended, instead of hand-kicking each loop

Servo is **not** a substitute for deciding what to build, and generated criteria
must never silently become product truth. The prerequisite is *evaluable intent*:
human-approved success criteria and evidence capable of distinguishing success
from failure. Unattended execution additionally requires the suitability gate,
composable quality signals, and hard budget/termination controls.

Continuous evaluation extends that audience to teams that want scheduled,
read-only discovery with explicitly opted-in, oracle-gated follow-up. Servo
ships the heartbeat, not the scheduler; its mechanics and controls are defined
in [architecture](architecture.md#runtime-artifacts) and
[spec 011](specs/011-heartbeat/spec.md).

## Core problem

Turning engineering intent into executable evaluation—and running against
it—is exactly the infrastructure devs rebuild on every project:

1. Writing a project-specific `oracle.sh` that composes the right signals (which
   signals does this project even *have*?)
2. Tuning weights and thresholds by hand
3. Turning a goal into trustworthy criteria, or translating existing criteria
   into executable evidence instead of relying on a generic judge
4. Wiring loop drivers, hook installers, and race orchestrators that consume the
   compiled evaluation
5. Repeating all of the above on the next project

The same scars, every project. Servo encodes the compilation + execution
scaffolding so the dev sets weights and prompts — not infrastructure.

## Competitive landscape

- **jig** — supervised engineering workflow; owns discovery, design, and
  specification. Sibling and optional upstream, not a dependency or competitor.
  Servo owns engineering *evaluation* and can consume Jig output or start from
  other intent/evidence inputs.
- **claude-flow, agent-frameworks, autogen** — heavyweight, opinionated execution
  runtimes. Servo is the opposite shape: it compiles evaluation and stays a thin
  scaffolder with no runtime lock-in, living in the project's own scripts.
- **GitHub Actions / CI recipes for agents** — distribution mechanism, not an
  evaluation compiler. Servo could feed into them, but isn't one.

## Product direction

Servo develops along four capability horizons: execution runtime, evaluation
compilation, evaluation intelligence, and continuous evaluation. The first two
form today's core; the latter two deepen explainability and scheduled operation.
Live status, dependencies, and per-spec scope belong in the
[roadmap](specs/ROADMAP.md), not this vision document.

## Design principles

- **Evaluation before execution.** Servo compiles approved intent and project
  evidence into executable evaluation first; the loop optimizes against that
  compiled evaluation. The
  oracle is the source of truth, never the transcript-only judge
  ([ADR-0008](decisions/adr-0008-loop-on-autonomy-primitives.md),
  [ADR-0011](decisions/adr-0011-host-native-phase-hints.md)).
- **Plugin first, project setup second.** Installation makes Servo available;
  `/servo:scaffold-init` creates project-owned evaluation. Package topology and
  compatibility surfaces belong in [architecture](architecture.md#install-surfaces).
- **Per-project artifacts beat plugin-owned runtime.** The dev's `oracle.sh` is
  theirs; servo only compiles and scaffolds it.
- **Refuse-on-missing-prerequisite.** If servo's runtime skills can't find
  `oracle.sh`, they exit non-zero. No silent degradation — no execution without a
  compiled evaluation.
- **Reversibility.** Hooks install and uninstall cleanly. Race worktrees clean up
  by default.
- **Signal-aware, not signal-prescriptive.** Probe what's there. If lint isn't
  configured, don't compile it into the composite.
- **Scheduled operation is a separate risk surface.** It is explicit opt-in,
  read-only while discovering work, and oracle- and budget-gated before
  execution. Detailed enforcement belongs in architecture and spec 011.

## Vision statement

> Servo does not automate software development. Servo automates the
> transformation of engineering intent into executable evaluation. Autonomous
> execution is a consequence of executable evaluation — not the primary goal.
