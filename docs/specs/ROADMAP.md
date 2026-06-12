# Servo spec roadmap

> Planned specs and the jig-gap inventory. Moved out of the status board
> (`docs/specs/README.md`) so `workflow.py status-board` can own that
> file's table without destroying this hand-maintained content.

## Planned specs

Descriptions name the cross-cutting AI-native concerns each spec
addresses — not just the skill it ships — so the gap inventory stays
visible during spec authoring.

| Spec | Description |
|---|---|
| [004-oracle-hook](004-oracle-hook/spec.md) | Claude Code hook installer (idempotent install/uninstall/status). Installs a **meta-judge `Stop` hook** that grades every assistant turn against the scaffolded oracle and feeds back a **structured retry hint** (block + reason) — the deterministic replacement for ad-hoc transcript-regex scans. Fails **open** so a broken oracle never traps a session. |
| [005-variant-race](005-variant-race/spec.md) | **DRAFT scope-capture, parked.** N-worktree parallel race with quality-gate scoring and winner selection — best-of-N against the oracle. Owns worktree-race coordination, variant-lease management, and winner promotion (the unattended cousin of jig's parallel-spec-number reservation). An **optimization, not an EDD prerequisite**; activates when a real target shows single-shot loop convergence is the bottleneck. |
| [008-eval-authoring](008-eval-authoring/spec.md) | **DRAFT scope-capture, parked.** Human-in-the-loop front-end that turns an eval-able `residual_judgment` AC into an [ADR-0005](../decisions/adr-0005-eval-oracle-component.md) frozen eval component: triage, rubric shaping, statistical reference-set collection, and frozen `n`/`δ`/threshold/judge-model — then hands off to `/servo:spec-oracle`. Activates on the first real EDD spec (same trigger as ADR-0005). |
| [009-ci-hardening](009-ci-hardening/spec.md) | **CI correctness.** Run servo's _full_ test suite (not just the install-surface subset) across a declared Python matrix, plus a ruff lint floor. Closes the gap where the 13 skill test files — the loop/gate/oracle/scaffold logic — never run in CI. |
| [010-release-automation](010-release-automation/spec.md) | **Release orchestration.** Conventional-commit PR-title gate → release-please (version bump + CHANGELOG + tag + GitHub release) → build/smoke/upload the release zip. Adopts jig's proven pipeline ([ADR-0007](../decisions/adr-0007-align-release-with-jig.md)); servo's `build_release_zip.py` is already release-ready, so this is orchestration only. |
| [011-heartbeat](011-heartbeat/spec.md) | **Routines-as-trigger / the loop's missing front-end.** Servo owns the middle and tail of the loop (loop / oracle / race / state) but nothing that *surfaces work on a schedule*. A Routine wakes servo; servo does a **read-only** discovery pass over project signals (CI failures, open issues, recent commits) → a servo-owned **triage inbox** (the state spine: dedupe + `open`/`tried`/`passed`/`skipped` so the next run resumes) → **oracle-gated dispatch** of each actionable finding into an isolated worktree loop, under **one whole-heartbeat cost ceiling**. Distinct from jig's `inbox.md` (cross-session continuity, not scheduled-discovery triage). **DRAFT — overview ready for review; slice 011-01 (read-only discovery → inbox) implementation-ready, 011-02..05 goals-only pending a grounding consumer.** Tier-2 (explicit opt-in). |

Sequencing rationale: 001 is the foundation everything else depends
on; 003 before 005 because race reuses loop primitives; 004 is
parallelizable with 003 (depends only on 001). 008 is parked behind the
first real EDD spec and depends on 006 + ADR-0005. 009 is independent CI
hygiene — run it before 010 so release automation gates on a green
full-suite CI. 010 depends on 007 + 009 and implements ADR-0007. 009 and
010 are the reverse-alignment specs (servo adopting jig's release/CI
maturity); see the section below. 011 (heartbeat) depends on 003 (the
dispatch target it composes) and is the **front-end** the loop / race /
state consume from — the Routines-as-trigger layer. Like 005 and 008, its
later slices wait for a grounding consumer to pin acceptance criteria; its
spike slice (011-01, read-only discovery → triage inbox) is fleshed to
implementation-ready so the front-end shape can be validated before the
rest is committed.

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
