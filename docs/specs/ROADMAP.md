# Servo spec roadmap

> Planned specs and the jig-gap inventory. Moved out of the status board
> (`docs/specs/README.md`) so `workflow.py status-board` can own that
> file's table without destroying this hand-maintained content.

Servo is an **Evaluation-Driven Development engine** with two phases —
**Servo Compile** (engineering intent + project evidence → executable
evaluation) and **Servo Run** (execute against it to convergence). The roadmap is organized around **evaluation
capability**, not incremental loop features; the four phases below map onto that
pipeline. See [docs/product-vision.md](../product-vision.md#product-direction) and
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
| [013-host-phase-aware-loops](013-host-phase-aware-loops/spec.md) | **DRAFT — 013-01 DONE (2026-07-01); 013-02/03 DEFERRED.** Lets servo consume host-native planning/implementation modes (Claude Plan Mode, Codex approval modes) as **advisory phase hints** (`plan`/`run`/`evaluate`/`triage`) layered on top of — never replacing — `gate.py`, `oracle.sh`, run state, triage state, and frozen eval ledgers ([ADR-0011](../decisions/adr-0011-host-native-phase-hints.md), Accepted). 013-01 shipped the docs-only contract (`docs/architecture.md` § Host-native phase hints); 013-02 (agent-loop adapter hints) and 013-03 (design-eval/heartbeat guidance) stay parked behind a real host-adapter caller. |

## Phase 2 — Evaluation Compilation *(Servo Compile; in progress)*

Turning goals, curated criteria, existing specs, and project signals into
executable evaluation: goal→criteria authoring, oracle synthesis, evidence
overlays, and frozen eval definitions.

| Spec | Description |
|---|---|
| [015-edd-suitability](015-edd-suitability/spec.md) | **DONE (2026-06-30).** The first Compile step: decide whether the work suits EDD and identify missing evidence, emitting a closed three-state, fail-closed **suitability verdict** ([ADR-0015](../decisions/adr-0015-edd-suitability-gate.md), Accepted). Ships `/servo:edd-suitability` with `--json`/`--explain`. Gates **Servo Compile**, not the heartbeat — [ADR-0018](../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md) narrowed the original two-call-site design after a 36-finding spike (015-05) showed the heartbeat's spec-less findings degenerate to `needs_evidence` for every candidate; the heartbeat keeps gating evaluability via `gate.py` instead. |
| [001-scaffold-init](001-scaffold-init/spec.md) | **DONE.** Probe a target's signals (tests/lint/CI/language) and synthesize a tailored `oracle.sh` + `.servo/install.json`, signal-aware rather than a generic stub. The MVP. |
| [006-spec-oracle](006-spec-oracle/spec.md) | **DONE.** Compile a spec/slice into a reviewable, deterministic **evidence overlay**: AC→check mapping, check engine, negative controls, freeze/approval, and an installable `score_spec_oracle_<id>` component. Turns acceptance criteria into runnable evaluation so loops optimize against the *spec*, not just the baseline suite. |
| [008-eval-authoring](008-eval-authoring/spec.md) | **DONE.** The generic, kind-agnostic eval-authoring surface `/servo:eval-authoring` ([ADR-0026](../decisions/adr-0026-generic-eval-authoring-surface.md)): expand a goal into curated, independently-reviewed, human-approved ACs ([ADR-0027](../decisions/adr-0027-goal-to-eval-assisted-authoring.md)); triage eval-able vs human-residual; shape the rubric; collect the reference set; set frozen `n`/`δ`/threshold/model; then emit, freeze, and install a `score_<name>` component through the shared ADR-0024 harness ([ADR-0005](../decisions/adr-0005-eval-oracle-component.md), [ADR-0024](../decisions/adr-0024-extract-frozen-eval-harness.md)). `/servo:spec-oracle` remains the upstream deterministic-criteria classifier; it does not compile judged evals. The skill also ships a light advisory judge-audit. |
| [012-design-eval](012-design-eval/spec.md) | **DRAFT.** Compile UI-vs-mockup intent into a frozen `score_design_fidelity` oracle component (pinned vision model, n-sampled, confidence lower bound), riding ADR-0005's frozen-eval contract ([ADR-0009](../decisions/adr-0009-design-fidelity-eval-recipe.md)). The non-deterministic sibling of the deterministic component templates. |
| [020-content-fidelity-eval](020-content-fidelity-eval/spec.md) | **DONE (2026-07-03).** The second eval kind ADR-0009 anticipated: extracted design-eval's already-modality-agnostic freeze/hash/aggregate/ledger/install harness into a shared `skills/_common/fidelity_eval.py` ([ADR-0024](../decisions/adr-0024-extract-frozen-eval-harness.md), Accepted), then shipped `/servo:content-fidelity` — a sibling skill compiling "does this text match the rubric?" into a frozen `score_content_fidelity` component judged by a pinned text model. Two known, disclosed gaps tracked in `docs/refinement-todo.md`: the file-or-command config shape is unvalidated against a real consumer, and `command`-backed cases have no structural cross-run determinism guarantee. |
| [016-execution-planner](016-execution-planner/spec.md) | **ACTIVE WORK DONE — 016-01..04 DONE; 016-05 DEFERRED.** The last Compile step emits a durable, reviewable **execution plan** (`.servo/plans/<spec-id>/plan.json`) that Servo Run consumes ([ADR-0016](../decisions/adr-0016-execution-plan-artifact.md), Accepted). The shipped path covers plan emission, Run consumption, human-edit validation, clamp-without-loosening, and the discoverable `/servo:execution-planner` surface. Only prompt rendering remains deferred. |

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
| [009-ci-hardening](009-ci-hardening/spec.md) | **DONE. CI correctness.** Full suite across the Python floor/latest bracket plus Ruff; spec 022 adds `scripts/ci_check.py` as the canonical local mirror of the named workflow gates. |
| [010-release-automation](010-release-automation/spec.md) | **DONE. Release orchestration.** Conventional PR-title gate → release-please (four synchronized manifests + CHANGELOG + tag + GitHub release) → build/smoke/upload the host-explicit Claude and Codex archives. Spec 022 supplies the current dual-host package boundary. |
| [022-dual-host-release-parity](022-dual-host-release-parity/spec.md) | **IN PROGRESS.** Committed generated Claude/Codex packages, one CI-equivalent local gate, synchronized manifests, host-explicit release assets, and a marketplace-first public install path ([ADR-0028](../decisions/adr-0028-committed-dual-host-plugin-packages.md)). |

## Sequencing rationale

Phase 1 (Servo Run) shipped first because a portable, guardrailed loop is the
runtime every other phase optimizes through; 001 (the first Compile step) is the
foundation it all depends on. Within Run, 003 precedes 005 because race reuses
loop primitives, and 004 is parallelizable with 003 (depends only on 001).
Phase 2 deepens compilation: 006 turns specs into evidence overlays, and 008
(the generic eval-authoring surface) was activated 2026-07-11 by
[ADR-0026](../decisions/adr-0026-generic-eval-authoring-surface.md)/[ADR-0027](../decisions/adr-0027-goal-to-eval-assisted-authoring.md)
on top of 006 + ADR-0005 + the ADR-0024 harness. Phase 4's
heartbeat (011) depends on 003 (the dispatch target it composes). Like 005,
the heartbeat's later slices wait for a grounding consumer to pin
acceptance criteria; its spike slice (011-01, read-only discovery → triage
inbox) was fleshed to implementation-ready so the front-end shape could be
validated before the rest was committed. The cross-cutting platform specs run
independently: 009 is CI hygiene — run it before 010 so release automation gates
on a green full-suite CI; 010 depends on 007 + 009 and implements ADR-0007.

The Compile-phase frontier (Phase 2) was specs **015** (EDD suitability — the
gate before everything) and **016** (execution planner — the Compile→Run handoff
artifact); each is anchored by an accepted ADR
([ADR-0015](../decisions/adr-0015-edd-suitability-gate.md),
[ADR-0016](../decisions/adr-0016-execution-plan-artifact.md)). **015 is now
DONE** (closed 2026-06-30; a pre-implementation spike, 015-05, narrowed its
scope to gating Compile rather than the heartbeat — [ADR-0018](../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md));
**016-01..04 are DONE**: plan emission, Run consumption, clamp/review, and the
skill surface all landed; only 016-05 prompt rendering is deferred. The first
slice also gave 015-03 the Compile-gate mechanism it needed to close.
**013** (host-phase-aware loops) followed the same pattern on
2026-07-01: its contract-defining first slice (013-01) shipped once
[ADR-0011](../decisions/adr-0011-host-native-phase-hints.md) was accepted,
while 013-02/03 stay parked behind a real host-adapter caller. Specs
**017** (evaluation intelligence) and **018** (continuous evaluation) are umbrella
scope-captures for Phases 3 and 4 — deliberately broad, expected to split into
per-capability specs (with their own ADRs) as real use grounds them. They record
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
| Install surface drift | 007-install-surfaces + 022-dual-host-release-parity | Public flow is marketplace plugin install → fresh target-project session → `/servo:scaffold-init`. Release archives and project-local runtime vending remain verified maintainer/compatibility surfaces. `scripts/ci_check.py` mirrors CI and includes the focused install contract gate. |

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
| CI runs only the install-surface subset, not the full suite | 009-ci-hardening + 022-dual-host-release-parity | Closed: full suite plus one `scripts/ci_check.py` local mirror of CI's named gates |
| No Python version matrix / declared floor | 009-ci-hardening | Closed: Python 3.9 floor + latest supported 3.x bracket |
| No Python lint floor (only shellcheck) | 009-ci-hardening | `ruff.toml` mirroring jig |
| No release automation (manual version + build; no changelog/tags/GitHub release) | 010-release-automation | release-please + conventional-commit gate; [ADR-0007](../decisions/adr-0007-align-release-with-jig.md) |
| One Claude-shaped plugin/archive; no Codex artifact or package drift guard | 022-dual-host-release-parity | Committed `hosts/claude` + `hosts/codex`, host-explicit release assets, synchronized manifests; [ADR-0028](../decisions/adr-0028-committed-dual-host-plugin-packages.md) |

One axis flows the other way (servo → jig): servo's data-driven
`.claude-plugin/install-contract.json` — one file consumed by the builder,
the verifier, and the scaffolder — is the cleaner single-source pattern.
Jig's builder (`build_release_zip.py`) hardcodes its own include/exclude
list and keeps it equal to its `install_contract.py` contract via a
consistency test; jig logged consolidating that duplication as cosmetic in
slice 047-01. A jig-side follow-on to make jig's builder consume its
contract directly is tracked in jig's own spec series (pending
confirmation).
