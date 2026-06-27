# Servo spec roadmap

> Planned specs and the jig-gap inventory. Moved out of the status board
> (`docs/specs/README.md`) so `workflow.py status-board` can own that
> file's table without destroying this hand-maintained content.

Servo is an **Evaluation-Driven Development engine** with two phases —
**Servo Compile** (spec → executable evaluation) and **Servo Run** (execute
against it to convergence). The roadmap is organized around **evaluation
capability**, not incremental loop features; the four phases below map onto that
pipeline. See [docs/product-vision.md](../product-vision.md#roadmap) and
[ADR-0014](../decisions/adr-0014-evaluation-compiler.md). Descriptions name the
cross-cutting AI-native concerns each spec addresses — not just the skill it
ships — so the gap inventory stays visible during spec authoring.

## Phase 1 — Execution Runtime *(Servo Run; largely shipped)*

The runtime that executes an implementation against the compiled evaluation: a
portable loop, oracle execution, and the agent abstraction.

| Spec | Description |
|---|---|
| [002-quality-gate](002-quality-gate/spec.md) | **DONE.** Runtime invocation of the scaffolded `oracle.sh` with normalized `{0,1,2}` exit codes and a versioned `--json` contract ([ADR-0002](../decisions/adr-0002-gate-caller-contract.md)) — the evaluation-execution primitive specs 003/004/005 consume. |
| [003-agent-loop](003-agent-loop/spec.md) | **DONE.** The portable execution loop: headless iteration under hard guardrails (iteration cap, cost ceiling, context-fill refusal, plateau detection, refuse-on-dirty-tree), checkpoint/resume state, and the [ADR-0008](../decisions/adr-0008-loop-on-autonomy-primitives.md) rebase onto `/goal` + host-scope routing. An *interchangeable runtime* — one stage of Servo Run, not the product. |
| [004-oracle-hook](004-oracle-hook/spec.md) | **DONE.** Claude Code hook installer (idempotent install/uninstall/status). Installs a **meta-judge `Stop` hook** that grades every assistant turn against the scaffolded oracle and feeds back a **structured retry hint** (block + reason) — the deterministic replacement for ad-hoc transcript-regex scans. Fails **open** so a broken oracle never traps a session. |
| [005-variant-race](005-variant-race/spec.md) | **DRAFT scope-capture, parked.** N-worktree parallel race with quality-gate scoring and winner selection — best-of-N against the oracle. Owns worktree-race coordination, variant-lease management, and winner promotion (the unattended cousin of jig's parallel-spec-number reservation). An **optimization, not an EDD prerequisite**; activates when a real target shows single-shot loop convergence is the bottleneck. |

## Phase 2 — Evaluation Compilation *(Servo Compile; in progress)*

Turning a spec into executable evaluation: oracle synthesis, spec → evidence
overlays, and eval authoring.

| Spec | Description |
|---|---|
| [015-edd-suitability](015-edd-suitability/spec.md) | **DRAFT scope-capture, parked.** The first Compile step: decide whether the work suits EDD and identify missing evidence, emitting a closed three-state, fail-closed **suitability verdict** that gates the pipeline ([ADR-0015](../decisions/adr-0015-edd-suitability-gate.md)). Stops the worst unattended failure mode — a meaningless green oracle on un-evaluable work. Likely grounding consumer: the heartbeat refusing un-evaluable findings. |
| [001-scaffold-init](001-scaffold-init/spec.md) | **DONE.** Probe a target's signals (tests/lint/CI/language) and synthesize a tailored `oracle.sh` + `.servo/install.json`, signal-aware rather than a generic stub. The MVP. |
| [006-spec-oracle](006-spec-oracle/spec.md) | **DONE.** Compile a spec/slice into a reviewable, deterministic **evidence overlay**: AC→check mapping, check engine, negative controls, freeze/approval, and an installable `score_spec_oracle_<id>` component. Turns acceptance criteria into runnable evaluation so loops optimize against the *spec*, not just the baseline suite. |
| [008-eval-authoring](008-eval-authoring/spec.md) | **DRAFT scope-capture, parked.** Human-in-the-loop front-end that turns an eval-able `residual_judgment` AC into an [ADR-0005](../decisions/adr-0005-eval-oracle-component.md) frozen eval component: triage, rubric shaping, statistical reference-set collection, and frozen `n`/`δ`/threshold/judge-model — then hands off to `/servo:spec-oracle`. Activates on the first real EDD spec (same trigger as ADR-0005). |
| [012-design-eval](012-design-eval/spec.md) | **DRAFT.** Compile UI-vs-mockup intent into a frozen `score_design_fidelity` oracle component (pinned vision model, n-sampled, confidence lower bound), riding ADR-0005's frozen-eval contract ([ADR-0009](../decisions/adr-0009-design-fidelity-eval-recipe.md)). The non-deterministic sibling of the deterministic component templates. |
| [016-execution-planner](016-execution-planner/spec.md) | **DRAFT scope-capture, parked.** The last Compile step: compile a durable, reviewable **execution plan** (`.servo/plans/<spec-id>/plan.json`) that Servo Run consumes ([ADR-0016](../decisions/adr-0016-execution-plan-artifact.md)) — making "Execution Planning" a real stage instead of a bag of CLI flags. Reciprocal to the per-run `state.json`; clamps but never loosens a brake. Likely grounding consumer: heartbeat plan-reuse or 017 adaptive planning. |

## Phase 3 — Evaluation Intelligence *(scope-captured; seeds shipped)*

Making the compiled evaluation smarter and explainable: oracle debugging,
convergence analysis, adaptive planning, evaluation explainability, and cost
optimization.

| Spec | Description |
|---|---|
| [017-evaluation-intelligence](017-evaluation-intelligence/spec.md) | **DRAFT scope-capture, parked.** Umbrella over the five Phase-3 capabilities; reasons *about* the compiled evaluation (diagnose non-convergence, debug a misbehaving oracle, rewrite the 016 plan from convergence signals within the clamp-don't-loosen contract, assemble the human-readable **evaluation report**, allocate budget where it moves the score most). **Expected to split** into per-capability specs (and per-capability ADRs) as each is grounded. |

Seeds already in the tree that this spec builds on:

- **Convergence analysis** — the oracle-score plateau / noise-floor heuristic
  (003-05; [ADR-0005](../decisions/adr-0005-eval-oracle-component.md) plateau δ).
- **Cost optimization** — the heartbeat whole-pass cost ceiling
  ([ADR-0012](../decisions/adr-0012-heartbeat-whole-pass-cost-ceiling.md)).
- **Oracle explainability** — the `gate.py --json` reason taxonomy and the
  spec-oracle `ledger.jsonl` evidence trail.

## Phase 4 — Continuous Evaluation *(seeded by the heartbeat)*

Evaluation that runs on its own — on a schedule, against the repo's live signals.

| Spec | Description |
|---|---|
| [011-heartbeat](011-heartbeat/spec.md) | **DONE. Routines-as-trigger / the loop's missing front-end.** Servo owns the middle and tail of the loop (loop / oracle / race / state) but nothing that *surfaces work on a schedule*. A Routine wakes servo; servo does a **read-only** discovery pass over project signals (CI failures, open issues, recent commits) → a servo-owned **triage inbox** (the state spine: dedupe + `open`/`tried`/`passed`/`skipped` so the next run resumes) → **oracle-gated dispatch** of each actionable finding into an isolated worktree loop, under **one whole-heartbeat cost ceiling**. Distinct from jig's `inbox.md` (cross-session continuity, not scheduled-discovery triage). Tier-2 (explicit opt-in). The first surface of continuous evaluation. |
| [018-continuous-evaluation](018-continuous-evaluation/spec.md) | **DRAFT scope-capture, parked.** Where the heartbeat leads: repository monitoring (a standing cross-wake view of compiled-evaluation state), automatic recompilation when a spec or its signals drift past the compiled evaluation (fail-closed — refuse the stale plan, don't silently optimize toward an outdated oracle), regression execution, and long-running multi-wake evaluation workflows. Inherits every heartbeat control (read-only discovery, whole-pass ceiling, refuse-without-oracle, suitability gate). **Expected to split**; activates on real scheduled use. |

## Cross-cutting platform & release hygiene

Not EDD-phase capabilities — the platform underneath all phases. Specs 009–010
are the **reverse-alignment** specs (servo adopting jig's release/CI maturity);
see the section below.

| Spec | Description |
|---|---|
| [007-install-surfaces](007-install-surfaces/spec.md) | **DONE.** Two install layers kept distinct (servo runtime install vs project oracle install), three runtime surfaces (plugin / zip / project-local scaffold) behind one data-driven contract and one verifier. |
| [009-ci-hardening](009-ci-hardening/spec.md) | **CI correctness.** Run servo's _full_ test suite (not just the install-surface subset) across a declared Python matrix, plus a ruff lint floor. Closes the gap where the 13 skill test files — the loop/gate/oracle/scaffold logic — never run in CI. |
| [010-release-automation](010-release-automation/spec.md) | **Release orchestration.** Conventional-commit PR-title gate → release-please (version bump + CHANGELOG + tag + GitHub release) → build/smoke/upload the release zip. Adopts jig's proven pipeline ([ADR-0007](../decisions/adr-0007-align-release-with-jig.md)); servo's `build_release_zip.py` is already release-ready, so this is orchestration only. |

## Sequencing rationale

Phase 1 (Servo Run) shipped first because a portable, guardrailed loop is the
runtime every other phase optimizes through; 001 (the first Compile step) is the
foundation it all depends on. Within Run, 003 precedes 005 because race reuses
loop primitives, and 004 is parallelizable with 003 (depends only on 001).
Phase 2 deepens compilation: 006 turns specs into evidence overlays, and 008 is
parked behind the first real EDD spec (depends on 006 + ADR-0005). Phase 4's
heartbeat (011) depends on 003 (the dispatch target it composes). Like 005 and
008, the heartbeat's later slices wait for a grounding consumer to pin
acceptance criteria; its spike slice (011-01, read-only discovery → triage
inbox) was fleshed to implementation-ready so the front-end shape could be
validated before the rest was committed. The cross-cutting platform specs run
independently: 009 is CI hygiene — run it before 010 so release automation gates
on a green full-suite CI; 010 depends on 007 + 009 and implements ADR-0007.

The Compile-phase frontier (Phase 2) is specs **015** (EDD suitability — the
gate before everything) and **016** (execution planner — the Compile→Run handoff
artifact); each is anchored by an ADR
([ADR-0015](../decisions/adr-0015-edd-suitability-gate.md),
[ADR-0016](../decisions/adr-0016-execution-plan-artifact.md)) and parked behind a
grounding consumer, like 005/008. Specs **017** (evaluation intelligence) and
**018** (continuous evaluation) are umbrella scope-captures for Phases 3 and 4 —
deliberately broad, expected to split into per-capability specs (with their own
ADRs) as real use grounds them. None of 015–018 is queued work yet; they record
the path from "servo compiles + runs evaluation today" to "servo reasons about
and continuously runs evaluation."

## How these specs close jig's long-running-session gaps

Servo's planned specs intentionally close the gaps that surface when an
agent runs without a human — gaps that jig's supervised workflow doesn't
need to solve at the same severity. Source: 2026-05-18 AI-native review
of jig.

| Gap surfaced in jig review | Servo home | Notes |
|---|---|---|
| Context-fill hard refusal gate | 003-agent-loop | Hard refusal; jig keeps a soft warning in `jig-context-check.sh` |
| Session checkpoint / resume across invocations | 003-agent-loop | On-disk state at `<target>/.servo/runs/<run-id>/state.json` (ADR-0004) |
| Stuck-loop detection | 003-agent-loop | Oracle-score-plateau heuristic |
| Token / cost ceiling enforcement | 003-agent-loop | Hard guardrail (defaults: max-iterations=5, cost-ceiling=$2 per architecture.md) |
| Subagent handoff state across iterations | 003-agent-loop | What `runner` / `judge` receive each spawn, what survives |
| `Stop`-hook grading (oracle-scored, structured retry hints) | 004-oracle-hook | The original meta-judge pattern; structured replacement for ad-hoc Stop-hook regex |
| Worktree-race coordination + winner selection | 005-variant-race | Variant-lease pattern; same family as jig's spec-number reservation but for ephemeral worktrees |
| Spec-specific judging | 006-spec-oracle | Turns acceptance criteria into deterministic evidence overlays so loops optimize against the spec, not just the baseline suite |
| Install surface drift | 007-install-surfaces | Two install layers kept distinct — *servo runtime install* (plugin root / release zip / project-local `.claude/` scaffold) vs *project oracle install* (`/servo:scaffold-init` → `oracle.sh` + `.servo/install.json`). All three runtime surfaces share one data-driven contract (`.claude-plugin/install-contract.json`) and one verifier (`scripts/verify_install.py`); `scripts/verify_install_surfaces.sh` runs them in CI |

Gaps that stay with jig (primer-doc hygiene, supervised slice-level drift
detection, parallel-worktree spec-numbering, memory-recall, PostToolUse
edit verification) are tracked in jig's own spec series and refinement-todo.

## Reverse alignment: servo adopting jig's release/CI maturity

The table above closes gaps where servo _leads_ jig (unattended-loop
concerns). Specs 009–010 close the opposite direction — release and CI
orchestration jig already solved and servo deferred (see 007-05's
deviation log). Source: 2026-06-11 release/CI alignment review.

| Gap (servo behind jig) | Servo home | Notes |
|---|---|---|
| CI runs only the install-surface subset, not the full suite | 009-ci-hardening | The 13 skill test files (loop/gate/oracle/scaffold) never run in CI today |
| No Python version matrix / declared floor | 009-ci-hardening | Recommend 3.11 + 3.12 (jig parity) |
| No Python lint floor (only shellcheck) | 009-ci-hardening | `ruff.toml` mirroring jig |
| No release automation (manual version + build; no changelog/tags/GitHub release) | 010-release-automation | release-please + conventional-commit gate; [ADR-0007](../decisions/adr-0007-align-release-with-jig.md) |

One axis flows the other way (servo → jig): servo's data-driven
`.claude-plugin/install-contract.json` — one file consumed by the builder,
the verifier, and the scaffolder — is the cleaner single-source pattern.
Jig's builder (`build_release_zip.py`) hardcodes its own include/exclude
list and keeps it equal to its `install_contract.py` contract via a
consistency test; jig logged consolidating that duplication as cosmetic in
slice 047-01. A jig-side follow-on to make jig's builder consume its
contract directly is tracked in jig's own spec series (pending
confirmation).
