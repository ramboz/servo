---
status: Proposed
date: 2026-06-26
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0014: Servo as an evaluation compiler — the EDD Compile/Run split

## Status

Proposed

## Context

Servo's documentation has, until now, centered the **autonomous execution
loop**: the README calls servo the "autonomous sibling" that scaffolds
"closed-loop, unattended agent operations," and the product vision leads with
headless iteration against an oracle. The loop is real and load-bearing — but
it is *one consumer* of something more fundamental that servo already does.

That more fundamental thing is **turning an engineering specification into
executable evaluation**. Every servo skill that matters does a version of this:
`/servo:scaffold-init` synthesizes an `oracle.sh` from a project's detected
signals; `/servo:spec-oracle` compiles a spec's acceptance criteria into a
reviewable, deterministic evidence overlay; `/servo:design-eval` compiles "does
the UI match the mockup?" into a frozen scoring component; `/servo:heartbeat`
discovers work and plans dispatch. Only *after* evaluation is compiled does the
loop optimize an implementation against it.

The sibling boundary with jig sharpens the point:

- **Jig owns engineering intent** — understanding problems, designing solutions,
  writing specs, refining architecture. The human-centered workflow.
- **Servo owns engineering evaluation** — given a spec, decide whether the work
  suits Evaluation-Driven Development, compile it into executable evaluation
  artifacts, and execute against them until convergence.

The vocabulary already half-exists. [ADR-0005](adr-0005-eval-oracle-component.md)
uses "eval-driven development (EDD)" — but **narrowly**, to mean only the
*non-deterministic frozen-eval* path (rubric + dataset + judge model, hashed and
approved). That narrow sense is a special case of a larger idea that has not had
a name: the whole practice of modeling success criteria as executable evaluation
before implementation, deterministic and non-deterministic alike.

We need one decision that (a) names that larger idea, (b) makes the
evaluate-then-execute structure first-class rather than implicit, and (c)
demotes the execution loop from "what servo is" to "one stage of how servo
runs."

## Decision

**Servo is an Evaluation-Driven Development (EDD) engine: it compiles
engineering intent into executable evaluation, and execution is one consumer of
the compiled evaluation model.**

### Evaluation-Driven Development

EDD is an engineering process where **success criteria are explicitly modeled as
executable evaluation before implementation**. Rather than relying on humans to
repeatedly judge progress, evaluation becomes executable; implementation is then
optimized toward that executable evaluation. **Evaluation is the source of
truth; execution is an optimization process.**

The narrow ADR-0005 sense (frozen non-deterministic evals) is **subsumed** as
one kind of compiled evaluation — the non-deterministic kind — alongside the
deterministic checks that `oracle.sh` and `/servo:spec-oracle` already produce.
ADR-0005 is not changed; this ADR widens the term it introduced.

### Two phases become a first-class architectural concept

Servo is structured as two conceptual subsystems. This separation is named,
documented, and used to organize the roadmap — it is not merely descriptive.

**Servo Compile** — consumes an engineering specification, produces compiled
evaluation artifacts:

- EDD suitability analysis (is this work EDD-shaped? what evidence is missing?)
- evidence extraction and normalization
- evaluation-model generation
- oracle synthesis / extension
- execution planning

Outputs: an evidence model, an evaluation model, an oracle, and an execution
plan.

**Servo Run** — consumes the compiled artifacts, executes an implementation
against them until convergence or failure:

- orchestration (the portable execution loop, host-scope routing, dispatch)
- evaluation each turn via the oracle
- convergence / plateau detection
- reporting

Outputs: an implementation, evaluation reports, convergence diagnostics, and
recommendations.

The **portable execution loop is one stage inside Servo Run** — an
*interchangeable runtime*, not servo's defining capability. The full pipeline is:

```text
Specification → EDD Suitability → Evidence Compilation → Evaluation Model
            → Oracle Synthesis → Execution Planning → Execution Loop → Evaluation Report
            └──────────────── Servo Compile ────────────────┘  └──────── Servo Run ───────┘
```

### What this does and does not move

This is a **framing** decision. It does **not** change any contract, exit code,
guardrail, file format, or skill behavior. The hard constraint from
[ADR-0008](adr-0008-loop-on-autonomy-primitives.md) still holds: `/goal`'s
transcript-only judge never replaces `oracle.sh`. The deterministic oracle
remains servo's authority surface ([ADR-0011](adr-0011-host-native-phase-hints.md)).
What changes is which abstraction the documentation centers.

## Re-baselining manifest & coverage

> This reframe is, in jig's terms, a **reframe on a load-bearing reference**
> (jig spec 067 / jig ADR-0024): the product's positioning moved and the corpus
> had encoded the old framing as settled truth. This ADR is the keystone; the
> manifest below records every affected artifact's disposition, and the coverage
> statement records what was scanned. Dispositions use jig ADR-0024's vocabulary
> plus a **`rewrite`** disposition for *live, non-record prose* whose framing
> must change (the gap that vocabulary has for documentation-shaped reframes).

**The moved reference.** The vision design brief that repositioned servo from
"autonomous execution loop" to "Evaluation-Driven Development engine" is declared
the authoritative framing **as of 2026-06-26**; the prior loop-centric framing is
superseded by this ADR.

**Manifest.**

| Artifact | Disposition | Note |
|---|---|---|
| `docs/product-vision.md`, `docs/architecture.md`, `README.md`, `docs/specs/ROADMAP.md`, `docs/decisions/README.md` | `rewrite` | Live prose reframed to the EDD-engine / Compile-Run model (commit 8734cee). |
| `skills/scaffold-init/SKILL.md` | `rewrite` | **Initially missed** (commit 8734cee scanned only `docs/` + `README`); the flagship Compile skill still read "closed-loop, unattended agent-operations infrastructure." Caught by the 2026-06-27 coverage sweep and rewritten to the Compile framing. |
| `skills/{agent-loop,oracle-hook,quality-gate,heartbeat}/*`, `agents/{runner,judge}.md`, `CHANGELOG.md` | `reaffirm` | Their "unattended / headless" language describes loop *behavior* (accurate — the loop genuinely runs unattended), compatible with "the loop is one stage of Servo Run." No change. |
| [ADR-0005](adr-0005-eval-oracle-component.md) | `reaffirm` (widened) | Its narrow "EDD" is widened to the product philosophy by this ADR (the frozen-eval sense becomes a special case). Not edited — accepted ADRs are immutable; the reconciliation is stated here. |
| **Emergent work** (net-new, not a disposition of an existing artifact) | — | The reframe *spawned* forward work the new framing revealed: [ADR-0015](adr-0015-edd-suitability-gate.md), [ADR-0016](adr-0016-execution-plan-artifact.md), and scope-capture specs 015–018. |

**Coverage statement.** *Scanned:* all of `docs/` (vision, architecture, README,
ROADMAP, decisions index) in the original pass; then a follow-up grep sweep of
`skills/`, `agents/`, `templates/`, `CHANGELOG.md`, `CONTRIBUTING.md` for the
old-framing tokens (`closed-loop`, `unattended`, `autonomous`, `scaffolder-first`)
with a read of every hit. *Method:* token grep + read; no built corpus-walker.
*Residual uncertainty:* the first pass under-caught (`docs/`-only) and missed one
flagship-skill description — a single data point that a coverage discipline is
worth imposing on reframes (logged to jig as occurrence #2). `templates/` were
checked for vision tokens (none found) but not exhaustively re-toned. Behavior-level
"unattended/headless" wording is **deliberately retained** as accurate, not missed.

## Consequences

**Positive.**

- The thing servo is uniquely good at — compiling intent into executable
  evaluation — becomes the headline, instead of an implementation detail of the
  loop.
- The Compile/Run split gives every existing skill a home and makes the
  evaluation-before-execution ordering legible to new readers.
- The roadmap reorganizes around evaluation capability (compilation,
  intelligence, continuous evaluation) rather than around incremental loop
  features, which matches where the differentiated value is.
- The jig/servo boundary (intent vs evaluation) is stated once, cleanly.

**Negative.**

- "EDD" now spans two scopes in the corpus: the original ADR-0005 frozen-eval
  sense and this wider product sense. Readers of older text must understand the
  former as a special case. Mitigated by stating the reconciliation here and in
  the product vision.
- "Servo Run" (the phase) and `heartbeat.py run` / a future `run` verb (the
  command) share a word. Docs disambiguate by always qualifying the phase as
  "Servo Run."
- A documentation pass touches the vision, architecture, README, and roadmap at
  once; some churn is unavoidable to make the framing consistent.

**Neutral.**

- No code, contract, or test changes. Servo behaves identically; only its
  self-description changes.
- The execution loop is not deprecated or downgraded in capability — it is
  re-situated as Servo Run's runtime stage.

## Alternatives considered

- **Keep the loop-centric framing.** Rejected: it undersells servo's actual
  differentiator and makes the roadmap a list of loop tweaks rather than an
  evaluation-capability ladder.
- **Fold the reframe into [ADR-0008](adr-0008-loop-on-autonomy-primitives.md).**
  Rejected: ADR-0008 decides *where* the loop runs (host autonomy primitives vs
  the portable driver). This ADR decides *what servo is*. Different question,
  different blast radius.
- **Widen ADR-0005 in place instead of a new ADR.** Rejected: accepted ADRs are
  immutable in this repo (Nygard convention). The wider definition is a new
  decision that *references* 0005, not an edit to it.
- **Different names for the phases** (e.g. "author"/"drive", "plan"/"execute").
  Rejected in favor of **Compile/Run** because "compile" captures the
  spec → executable-artifact transformation precisely, and the pairing reads as
  a pipeline.

## Verification

This is a documentation-framing ADR; verification is editorial rather than
test-backed:

- The product vision, architecture, README, and spec roadmap consistently
  present servo as an EDD engine with the Compile/Run split, and present the
  execution loop as one stage of Servo Run.
- No referenced path is broken (the docs stale-path guard in
  `scripts/verify_install_surfaces.sh` stays green).
- No spec frontmatter or status-board content changes as a result of this ADR.

## References

- [ADR-0005](adr-0005-eval-oracle-component.md) — introduces "EDD" in the narrow
  frozen-eval sense this ADR widens.
- [ADR-0008](adr-0008-loop-on-autonomy-primitives.md) — the execution loop is one
  stage of Servo Run; this ADR re-situates it.
- [ADR-0011](adr-0011-host-native-phase-hints.md) — the oracle stays servo's
  authority surface regardless of host-native phase hints.
- [docs/product-vision.md](../product-vision.md), [docs/architecture.md](../architecture.md),
  [docs/specs/ROADMAP.md](../specs/ROADMAP.md) — the artifacts reframed by this decision.
