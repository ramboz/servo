# Decisions

> Architectural Decision Records. Nygard convention: immutable after acceptance.
> New decisions supersede old ones — never edit an accepted ADR.
> Filenames follow `adr-NNNN-<kebab-slug>.md`; titles use the form
> `# ADR-NNNN: <Title>`.

## Index

- [ADR-0001: (untitled)](adr-0001-reuse-jig-test-detector.md) — Servo's slice 001-03 needs to classify a target project's test framework so the scaffolded `oracle.sh` includes the right `score_<framework>` block. ((unknown))
- [ADR-0002: (untitled)](adr-0002-gate-caller-contract.md) — Spec 002 (`/servo:quality-gate`) ships `gate.py`, the runtime wrapper around the scaffolded `oracle.sh`. ((unknown))
- [ADR-0003: (untitled)](adr-0003-fresh-subagent-roster.md) — Servo is a Claude Code plugin and a sibling to [jig](https://github.com/ramboz/jig). ((unknown))
- [ADR-0004: (untitled)](adr-0004-session-state-file-format.md) — Spec 003 (`/servo:agent-loop`) ships `loop.py`, a headless iteration driver that subprocesses `claude -p --output-format json` against a target under hard guardrails (iteration cap, cumulative cost ceiling, context-fill refusal gate, stuck-loop detection). ((unknown))
- [ADR-0005: Eval as a frozen oracle component](adr-0005-eval-oracle-component.md) — servo's oracle is deterministic by construction. ((unknown))
- [ADR-0006: (untitled)](adr-0006-meta-judge-output-contract.md) — Spec 004 (`/servo:oracle-hook`) installs a Claude Code `Stop` hook — the "meta-judge" — that scores every assistant turn against the scaffolded oracle (via `gate.py`, ADR-0002) and feeds a retry hint back when the work is below threshold. ((unknown))
- [ADR-0007: (untitled)](adr-0007-align-release-with-jig.md) — Servo releases are entirely manual: a maintainer hand-edits the version in `.claude-plugin/plugin.json`, runs `python3 scripts/build_release_zip.py` to build and smoke-test `dist/servo-v<version>.zip`, and stops there. ((unknown))
- [ADR-0008: (untitled)](adr-0008-loop-on-autonomy-primitives.md) — Servo's agent-loop (spec 003, DONE) is a hand-rolled headless iteration driver. ((unknown))
- [ADR-0009: Design-fidelity as a first-class eval recipe (`/servo:design-eval`)](adr-0009-design-fidelity-eval-recipe.md) — [ADR-0005](adr-0005-eval-oracle-component.md) settled *under what contract* a non-deterministic eval may enter servo's oracle: a frozen `score_<name>` component with a hashed definition, confidence-lower-bound scoring, a plateau noise floor, and `env_error`-never-a-silent-zero honesty. ((unknown))
- [ADR-0010: (untitled)](adr-0010-triage-inbox-schema.md) — Spec 011 (`/servo:heartbeat`) is the scheduled front-end of the servo loop. ((unknown))
- [ADR-0011: Host-native phase hints stay advisory under servo's oracle authority](adr-0011-host-native-phase-hints.md) — Servo orchestrates autonomous coding loops by keeping deterministic authority outside the LLM host: `gate.py` invokes the project-owned `oracle.sh`, loop state is written under `.servo/runs/`, and heartbeat triage state is written under `.servo/triage/`. (2026-07-01, Accepted)
- [ADR-0012: Heartbeat uses one whole-pass cost ceiling](adr-0012-heartbeat-whole-pass-cost-ceiling.md) — Spec 011 turns servo into a scheduled front-end: `heartbeat.py run` discovers project signals, dispatches actionable findings into isolated loop worktrees, and records outcomes back to the triage inbox. (Accepted)
- [ADR-0013: Servo availability breadcrumb](adr-0013-servo-available-breadcrumb.md) — Jig wants to nudge a user toward `/servo:scaffold-init` when servo is available on the machine but the current project has not yet been servo-scaffolded. (Accepted)
- [ADR-0014: Servo as an evaluation compiler — the EDD Compile/Run split](adr-0014-evaluation-compiler.md) — Servo's documentation has, until now, centered the **autonomous execution loop**: the README calls servo the "autonomous sibling" that scaffolds "closed-loop, unattended agent operations," and the product vision leads with headless iteration against an oracle. (2026-06-27, Accepted)
- [ADR-0015: EDD suitability analysis is a fail-closed gate, not a score](adr-0015-edd-suitability-gate.md) — [ADR-0014](adr-0014-evaluation-compiler.md) makes Servo Compile a first-class phase: spec → executable evaluation. (2026-06-27, Accepted)
- [ADR-0016: The execution plan is the Compile→Run handoff artifact](adr-0016-execution-plan-artifact.md) — [ADR-0014](adr-0014-evaluation-compiler.md) names the outputs of Servo Compile as an *evidence model*, an *evaluation model*, an *oracle*, and an *execution plan*. (2026-06-30, Accepted)
- [ADR-0017: Conformance scores + trend ledger — servo decorates the jig conformance graph](adr-0017-conformance-scores-ledger.md) — When an LLM builds a UI incrementally from a canonical design, the work must be **locally scoped but globally convergent**: each slice implements a portion, yet the app must converge toward the final design rather than drift into a pile of individually-correct, collectively-inconsistent screens. (Proposed)
- [ADR-0018: EDD suitability gates Compile, not the heartbeat](adr-0018-suitability-gates-compile-not-heartbeat.md) — [ADR-0015](adr-0015-edd-suitability-gate.md) defined the EDD **suitability verdict** — a closed three-state gate (`suitable` / `needs_evidence` / `unsuitable`), fail-closed, with a `missing_evidence` list — and asserted it gates the pipeline at **two** call sites: the Servo Compile precondition **and** the heartbeat's per-finding dispatch boundary ("a finding that is `unsuitable` / `needs_evidence` is recorded `skipped` rather than spawning a loop"). (2026-06-28, Accepted)
- [ADR-0019: Eval authoring stays entirely servo-owned](adr-0019-eval-authoring-servo-owned.md) — [Spec 008 (eval-authoring)](../specs/008-eval-authoring/spec.md) is the human-in-the-loop bridge [ADR-0005](adr-0005-eval-oracle-component.md) anticipated: given a spec's `residual_judgment` AC (from [spec 006](../specs/006-spec-oracle/spec.md)'s classifier), triage which ones are eval-able, shape a rubric, collect a statistical reference set, set the frozen `n`/`δ`/threshold/judge-model, and emit a definition `/servo:spec-oracle` compiles into a frozen `score_<name>` component. (2026-07-01, Accepted)
- [ADR-0020: Minimum supported Python is 3.9](adr-0020-python-39-floor.md) — Servo is distributed as a Claude Code / Codex plugin, not a pip package. (2026-07-01, Accepted)
- [ADR-0021: Servo is oracle-first; the agent-loop is one optional consumer](adr-0021-oracle-first-agent-loop-optional-consumer.md) — The agent-loop ([spec 003](../specs/003-agent-loop/spec.md), [ADR-0008](adr-0008-loop-on-autonomy-primitives.md)) drives edits by shelling out to `claude -p`. (2026-07-02, Accepted)
- [ADR-0022: Freeze the spec-oracle against parsed ACs, not the raw spec file](adr-0022-freeze-against-parsed-acs.md) — `checks.py --enforce-freeze` ([spec 006-04](../specs/006-spec-oracle/spec.md)) freezes a spec-oracle and refuses to score (`spec_oracle_stale`) when the source spec has changed since approval. (2026-07-02, Accepted)
- [ADR-0023: Co-locate durable spec-oracle artifacts with the spec; keep only ephemeral state under .servo/](adr-0023-colocate-durable-spec-oracle-artifacts.md) — A spec-oracle's durable artifacts (`plan.md`, `checks.json`) live under `<target>/.servo/spec-oracles/<spec-id>/`, spatially disconnected from the spec they evaluate (`docs/specs/<spec>/slice-NN.md`). (2026-07-02, Accepted)
- [ADR-0024: Extract the frozen-eval harness into a shared module for the second eval kind](adr-0024-extract-frozen-eval-harness.md) — [ADR-0005](adr-0005-eval-oracle-component.md) fixed the *contract* a non-deterministic eval must satisfy to enter servo'… (2026-07-03, Accepted)
- [ADR-0025: Runner records load-bearing assumptions; judge verifies them](adr-0025-runner-records-judge-verifies-assumptions.md) — servo's agent-loop is **headless**. (2026-07-12, Accepted)
- [ADR-0026: Eval authoring generalizes to one kind-agnostic authoring surface](adr-0026-generic-eval-authoring-surface.md) — Three ADRs already bound the non-deterministic eval story: (Accepted)
- [ADR-0027: Goal→eval is assisted authoring, gated by independent review and human curation](adr-0027-goal-to-eval-assisted-authoring.md) — Servo's eval pipeline is **spec/AC-centric**. (Accepted)
- [ADR-0028: Commit generated Claude and Codex plugin packages](adr-0028-committed-dual-host-plugin-packages.md) — Servo's canonical repository is also its Claude install payload, while its release pipeline publishes one Claude-shaped archive and has no Codex plugin manifest or native Codex marketplace bundle. (2026-07-12, Accepted)

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
by the conformance-scores ledger ADR, `0018` is Accepted (suitability gates
Compile, not the heartbeat), `0019` is Accepted (eval authoring stays
entirely servo-owned), and `0020` is Accepted (minimum supported Python is
3.9), `0021` is Accepted (oracle-first / agent-loop optional consumer),
`0022` is Accepted (freeze against parsed ACs), `0023` is Accepted
(co-locate durable spec-oracle artifacts), and `0024` is Accepted (extract
the frozen-eval harness), `0025` is reserved (Proposed) by the
runner-records / judge-verifies-assumptions ADR, `0026` is Accepted (generic eval-authoring-surface), `0027` is Accepted (goal→eval assisted authoring), and `0028` is reserved by the dual-host package ADR, so the next free number is `0029`:

- **A future ADR — Why `oracle.sh` stays project-owned plain bash.** Crystallizes if anyone proposes a Python or Node oracle alternative.

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
