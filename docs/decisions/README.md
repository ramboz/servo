# Decisions

> Architectural Decision Records. Nygard convention: immutable after acceptance.
> New decisions supersede old ones — never edit an accepted ADR.
> Filenames follow `adr-NNNN-<kebab-slug>.md`; titles use the form
> `# ADR-NNNN: <Title>`.

## Index

- [ADR-0001: Reuse jig's `tdd.py detect` for test-framework detection when jig is co-installed](adr-0001-reuse-jig-test-detector.md) — Servo prefers jig's detector via subprocess when `${CLAUDE_PLUGIN_ROOT}/jig/skills/tdd-loop/tdd.py` exists, falls back to a built-in matcher otherwise. Establishes the filesystem-only coupling pattern. (2026-05-15, Accepted)
- [ADR-0002: Quality-gate caller contract — closed exit codes and versioned JSON schema](adr-0002-gate-caller-contract.md) — `gate.py` exits only `0/1/2` (unexpected oracle exits remap to `2`); `--json` payloads carry `schema_version: 1` from day one. The contract specs 003 / 004 / 005 consume. (2026-05-18, Accepted)
- [ADR-0003: Why a fresh subagent roster, not reused from jig](adr-0003-fresh-subagent-roster.md) — Servo ships two fresh agents (`runner`, `judge`) because their machine-parseable verdict-block output diverges from jig's narrative `implementer` / `reviewer`. Architect calls delegate to `jig:architect` directly — no servo-side architect prompt. (2026-05-19, Accepted)
- [ADR-0004: Session-state file format on disk](adr-0004-session-state-file-format.md) — Per-run loop scoreboard at `<target>/.servo/runs/<run-id>/state.json`, referencing Claude Code sessions by `session_id` only. Atomic-write contract, `state_schema_version`, run-id collision policy. Filesystem-only coupling with Claude Code. (2026-05-19, Accepted)
- [ADR-0005: Eval as a frozen oracle component](adr-0005-eval-oracle-component.md) — A non-deterministic eval enters the composite only as a *frozen* `score_<name>`: its definition (rubric + dataset + judge model + `n` + `δ`) is hashed and approved, it reports a confidence lower bound rather than a raw judge score, and `loop.py` gains a plateau noise floor. The reciprocal servo-side ADR to jig's ADR-0022. (2026-06-09, Accepted 2026-06-13)
- [ADR-0006: Meta-judge Stop-hook output contract & fail-open posture](adr-0006-meta-judge-output-contract.md) — Spec 004's `Stop` hook blocks with a structured composite/threshold hint on below-threshold (`{"decision":"block"}`, not `additionalContext`), fails **open** on any env-error (a `systemMessage` warning, never a block, so it can't trap a session), and nudges at most once per stop sequence (respects/biases-on `stop_hook_active`). The interactive inverse of agent-loop's fail-closed brakes. (2026-06-10, Accepted)
- [ADR-0007: Adopt release-please + conventional-commit enforcement for servo releases (align with jig)](adr-0007-align-release-with-jig.md) — Replaces servo's fully manual release (hand-edited `plugin.json` version, local zip build, no tags/changelog) with jig's model: an enforced conventional-commit PR-title gate plus release-please for version / `CHANGELOG.md` / tag / GitHub release. Implemented by spec 010. (2026-06-11, Accepted)
- [ADR-0008: Rebase agent-loop orchestration onto Claude Code autonomy primitives](adr-0008-loop-on-autonomy-primitives.md) — Delegates continuation (`/goal`), detachment (`/background`), and scheduling (Routines) to the shipped primitives; servo keeps *only* the deterministic guardrail + oracle layer, and retains the external-driver path as the portable layer for hook-restricted / non-Claude-Code hosts (e.g. Codex). Hard constraint: `/goal`'s transcript-only judge never replaces `oracle.sh`. All four verification gates cleared (V1 hooks stack; V2 `/goal` engages headless + both `--max-turns`/`--max-budget-usd` bind; V3 mechanism confirmed live; V4 by-design — `gate.py` is the in-Routine authority). (2026-06-12, Accepted)
- [ADR-0009: Design-fidelity as a first-class eval recipe (`/servo:design-eval`)](adr-0009-design-fidelity-eval-recipe.md) — Ships `/servo:design-eval`, a guided skill (+ reusable `score.py` / `design_eval.py` / `capture.mjs`) that turns "does the built UI match the design mockup?" into a frozen `score_design_fidelity` oracle component — the non-deterministic sibling of servo's deterministic component templates. Captures app-vs-reference screenshots, judges fidelity with a pinned vision model (n-sampled, confidence-lower-bound), sha256-freezes the definition, and installs into `oracle.sh` (rc 0/1/2 unchanged; `env_error` never a silent `0.0`). Rides ADR-0005's frozen-eval contract; first consumer is food-log's slice 002-01. (2026-06-12, Accepted)
- [ADR-0010: Triage-inbox state-file schema & dedupe identity](adr-0010-triage-inbox-schema.md) — The `/servo:heartbeat` triage inbox (`.servo/triage/inbox.jsonl`) as append-and-update cross-run state: `schema_version: 2`; the ratified `finding_id` fingerprint (CI = `workflowName+headBranch`, issue = `number`, commit = `sha`); a *sticky* `open`/`tried`/`passed`/`skipped` lifecycle kept separate from a *recomputed* `actionable` verdict and an *immutable* `provenance` trust marker (Guardrail #4); one uniform merge + retention rule (keep live-or-lifecycle-bearing, evict stale `open`) that bounds growth across all sources; and `flock` double-fire safety. Reciprocal to ADR-0004; crystallizes spec 011-02. (2026-06-15, Accepted)
- [ADR-0011: Host-native phase hints stay advisory under servo's oracle authority](adr-0011-host-native-phase-hints.md) — Servo may consume host-native planning / implementation modes as adapter hints for planning, running, and evaluating loops, but `gate.py`, `oracle.sh`, run state, and triage state remain the authoritative control surfaces. (2026-06-17, Accepted 2026-07-01)
- [ADR-0012: Heartbeat uses one whole-pass cost ceiling](adr-0012-heartbeat-whole-pass-cost-ceiling.md) — `heartbeat.py run` applies one heartbeat-level budget across discovery and all dispatched loops in the current pass, leaving remaining candidates open when the budget is spent. (2026-06-18, Accepted)
- [ADR-0013: Servo availability breadcrumb](adr-0013-servo-available-breadcrumb.md) — Servo writes a best-effort host-neutral marker at `${XDG_STATE_HOME:-$HOME/.local/state}/servo/available.json` so jig can cheaply detect "servo probably available" without Claude-specific plugin registries or subprocesses. (2026-06-18, Accepted)
- [ADR-0014: Servo as an evaluation compiler — the EDD Compile/Run split](adr-0014-evaluation-compiler.md) — Reframes servo as an **Evaluation-Driven Development engine**: it compiles engineering intent into executable evaluation, and the autonomous execution loop is one consumer of the compiled model. Makes the two-phase **Servo Compile** (spec → evidence/evaluation model + oracle + execution plan) / **Servo Run** (execute to convergence) split a first-class architectural concept, and widens ADR-0005's narrow "EDD" to the product philosophy (the frozen-eval sense becomes a special case). Framing only — no contract, guardrail, or behavior change. (2026-06-26, Accepted 2026-06-27)
- [ADR-0015: EDD suitability analysis is a fail-closed gate, not a score](adr-0015-edd-suitability-gate.md) — The first Servo Compile step decides whether work suits EDD and identifies missing evidence, emitting a closed three-state **suitability verdict** (`suitable` / `needs_evidence` / `unsuitable`) that *gates* the pipeline. Fail-closed (indeterminate ⇒ not `suitable`), a gate not a threshold (no "close enough" auto-proceed), and the per-finding precondition at the heartbeat dispatch boundary. Anchors spec 015; mirrors ADR-0002's closed-taxonomy posture. (2026-06-26, Accepted 2026-06-27)
- [ADR-0016: The execution plan is the Compile→Run handoff artifact](adr-0016-execution-plan-artifact.md) — Servo Compile emits a durable, reviewable **execution plan** at `<target>/.servo/plans/<spec-id>/plan.json` that Servo Run consumes — making "Execution Planning" a real stage with an output instead of a bag of CLI flags. References (not copies) the oracle + spec-oracle overlay + the suitability verdict (015), is human-editable before Run, and **cannot loosen a hard guardrail past its safe ceiling** (clamped, never honored). Consumer scoped to Compile→Run for a real spec — *not* the heartbeat (findings are spec-less, ADR-0018). Reciprocal to ADR-0004 (plan vs outcome); opt-in (no plan ⇒ today's behavior). Anchors spec 016. (2026-06-26, Accepted 2026-06-30)
- [ADR-0017: Conformance scores + trend ledger — servo decorates the jig conformance graph](adr-0017-conformance-scores-ledger.md) — The **servo half** of a paired decision (jig **ADR-0032** owns the conformance-graph topology). When an LLM builds a UI incrementally from a canonical design, the work must be locally scoped but globally convergent; servo writes per-node **fidelity scores** (the frozen `/servo:design-eval` verdict jig attests) + a **convergence trend ledger** (gap-to-canonical over design versions) onto the jig graph, while jig owns the deterministic topology/coverage. Reuses ADR-0005/0009; attest-only boundary unchanged. Recorded ahead of a committed consumer; demand-gated. (2026-06-27, Proposed)
- [ADR-0018: EDD suitability gates Compile, not the heartbeat](adr-0018-suitability-gates-compile-not-heartbeat.md) — **Narrows ADR-0015.** A pre-impl frame-critique + the **015-05 spike** (36 real findings) showed the suitability verdict is spec-centric but heartbeat findings are spec-less: ephemeral-spec synthesis degenerates to `needs_evidence` for 36/36 (an off switch), 0/3 actionable findings carry a recoverable spec, and the heartbeat already gates evaluability via `gate.py`. So the verdict gates **Compile only**; the heartbeat keeps `gate.py` and **011-02's human-only `skipped` stands** (no inbox-contract change). 015-03 re-scoped to the Compile precondition (deferred pending 016); a finding-shaped check is deferred to 018. (2026-06-28, Accepted)

## Pending

ADR candidates (numbers are *hints* of the next likely allocation order,
not reservations — the next accepted ADR claims the next free number
regardless of which candidate fires first). `0005` is Accepted (the
eval-oracle-component ADR), `0009` is Accepted (the design-fidelity-eval
recipe), `0010` is Accepted (triage-inbox-schema), `0011` is Accepted
(host-native phase hints), `0012` is Accepted
(heartbeat whole-pass cost ceiling), `0013` is Accepted (servo availability
breadcrumb), `0014` is Accepted (the evaluation-compiler / EDD reframe
ADR), `0015` is Accepted (the EDD suitability gate), and `0016` is Accepted
(the execution-plan artifact ADR), `0017` is reserved (Proposed)
by the conformance-scores ledger ADR, and `0018` is Accepted (suitability gates
Compile, not the heartbeat), so the next free number is `0019`:

- **A future ADR — Why `oracle.sh` stays project-owned plain bash.** Crystallizes if anyone ever proposes a Python or Node oracle alternative. Listed in `docs/architecture.md` under "Pending (ADR candidates)".

## Format

Each ADR carries a frontmatter block (`status`, `date`, `deciders`,
`supersedes`, `superseded-by`) plus body sections: Context, Decision,
Consequences (positive / negative / neutral), Alternatives considered,
Verification, References.

## When to write an ADR

- Hard-to-reverse decisions (file formats, contracts, public-API shapes)
- Decisions that affect multiple modules or downstream callers
- When a contract changes in a breaking way
- When the architect agent (`jig:architect` per ADR-0003) produces a proposal that is accepted
