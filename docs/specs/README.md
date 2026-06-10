# Spec Status Board

> Current state of all servo specs. Each spec lives in `NNN-<slug>/spec.md`
> with one `slice-NN-<slug>.md` file per vertical slice (jig file-per-slice
> shape), and the lifecycle: `DRAFT → READY_FOR_REVIEW →
> READY_FOR_IMPLEMENTATION → IN_PROGRESS → REVIEWED → RECONCILED → DONE`.
> A `DEFERRED` slice is parked with a `**Resolution trigger:**` line and
> re-opens by transitioning back to `DRAFT`.
>
> **This table is generated** — run
> `workflow.py status-board .` after a `workflow.py transition`; do not
> hand-edit slice rows (the Notes column is preserved across regen, so
> curate Notes freely). Planned specs + the jig-gap inventory live in
> [ROADMAP.md](ROADMAP.md).

## Active specs

| Spec | Slice | Status | Notes |
|------|-------|--------|-------|
| [001-scaffold-init](001-scaffold-init/spec.md) | 001-01 — greenfield-scaffold | **DONE** | 12 tests; spike-shaped first slice — weighted-composite-oracle approach validated |
| [001-scaffold-init](001-scaffold-init/spec.md) | 001-02 — template-content | **DONE** | 23 tests; weighted-average composite + `# SEED:` convention; threshold default 0.5 |
| [001-scaffold-init](001-scaffold-init/spec.md) | 001-03 — signal-detection | **DONE** | 34 tests; jig-fallback + built-in detectors for pytest/vitest/jest/cargo/go; ADR-0001 |
| [001-scaffold-init](001-scaffold-init/spec.md) | 001-04 — deferred-decisions | **DONE** | 40 tests; emits `<target>/.servo/refinement-todo.md` (Threshold + Weights + Ambiguous) |
| [001-scaffold-init](001-scaffold-init/spec.md) | 001-05 — qa-wizard | **DONE** | 53 tests total; SKILL.md + anti-greediness surface tests; spec 001 complete |
| [002-quality-gate](002-quality-gate/spec.md) | 002-01 — invoke-passthrough | **DONE** | 20 tests; closed 0/1/2 contract; ADR-0002 |
| [002-quality-gate](002-quality-gate/spec.md) | 002-02 — structured-output | **DONE** | 39 tests; `--json` with `schema_version: 1`; closed `reason` taxonomy emerging |
| [002-quality-gate](002-quality-gate/spec.md) | 002-03 — manifest-aware | **DONE** | 62 tests; `audit` subcommand; `manifest_missing` / `manifest_malformed` / `manifest_invalid_key` reasons |
| [002-quality-gate](002-quality-gate/spec.md) | 002-04 — timeout-safety | **DONE** | 75 tests; SIGTERM → 5s grace → SIGKILL on process group; `SERVO_GATE_TIMEOUT` env var |
| [002-quality-gate](002-quality-gate/spec.md) | 002-05 — qa-wizard | **DONE** | 146 tests across four files; SKILL.md documents all 11 `reason` codes; spec 002 complete |
| [003-agent-loop](003-agent-loop/spec.md) | 003-01 — invoke-loop | **DONE** | 35 tests; mock-claude harness via PATH-injection; `schema_version: 1`; `claude -p` timeout via `SERVO_CLAUDE_TIMEOUT` |
| [003-agent-loop](003-agent-loop/spec.md) | 003-02 — cost-ceiling | **DONE** | 52 tests total; cumulative `total_cost_usd` halt + per-iter `--max-budget-usd` floor; 003-01 forward-reference closed |
| [003-agent-loop](003-agent-loop/spec.md) | 003-03 — context-fill-gate | **DONE** | 83 tests total; pre-iter fail-closed refusal at ratio ≥ threshold; helper fail-opens on six malformed-JSON paths; ADR-0001-style filesystem-only coupling stays intact |
| [003-agent-loop](003-agent-loop/spec.md) | 003-04 — checkpoint-resume | **DONE** | 126 tests total; per-run state at `<target>/.servo/runs/<run-id>/state.json` (atomic write); `--resume <run-id>` + version gates; SIGINT/SIGTERM trap (exit 130); bounded run-id collision retry |
| [003-agent-loop](003-agent-loop/spec.md) | 003-05 — stuck-loop-and-handoff | **DONE** | 151 tests + 26 surface tests; oracle-score plateau (default M=3); real `runner.md` / `judge.md` prompts ship with `schema_version: 1` verdict blocks; `--agent <name>` dispatch alternates runner/judge; `verdict_schema_mismatch` enforcement closes ADR-0003 |
| [006-spec-oracle](006-spec-oracle/spec.md) | 006-01 — evidence-plan | **DONE** | 43 tests; `oracle_plan.py` reads a spec → `plan.md` + `checks.json` under `.servo/spec-oracles/<id>/`; 9-family deterministic (keyword) classifier, residual judgment surfaced with reason + review path; multi-line AC capture (first-line-truncation bug found + fixed in review); read-only over target (AC5 byte-snapshot); model-assist classification deferred to refinement-todo; review PASS |
| [006-spec-oracle](006-spec-oracle/spec.md) | 006-02 — check-library | DRAFT | Stdlib check primitives + JSONL evidence output |
| [006-spec-oracle](006-spec-oracle/spec.md) | 006-03 — oracle-overlay | DRAFT | Install generated checks as an ordinary `oracle.sh` component |
| [006-spec-oracle](006-spec-oracle/spec.md) | 006-04 — freeze-and-controls | DRAFT | Approval, source-hash staleness, artifact hashes, negative controls |
| [006-spec-oracle](006-spec-oracle/spec.md) | 006-05 — skill-and-dogfood | DRAFT | `/servo:spec-oracle` surface + jig 046/047-style worked examples |
| [007-install-surfaces](007-install-surfaces/spec.md) | 007-01 — plugin-contract-verifier | **DONE** | 14 tests; `.claude-plugin/install-contract.json` + plugin verifier; subagent review PASS |
| [007-install-surfaces](007-install-surfaces/spec.md) | 007-02 — release-zip | **DONE** | 23 release-zip tests / 37 script tests; 21-entry deterministic zip; final subagent review PASS |
| [007-install-surfaces](007-install-surfaces/spec.md) | 007-03 — scaffold-runtime | **DONE** | 23 scaffold-runtime + 9 scaffold-verifier tests; `scripts/scaffold_runtime.py` vendors servo- prefixed skills/agents/templates into `<target>/.claude/` + `scaffold-install.json`; `verify_install.py scaffold`; review PASS; 2 fidelity gaps deferred to 007-04 |
| [007-install-surfaces](007-install-surfaces/spec.md) | 007-04 — scaffold-fidelity | **DONE** | 27 new tests; scaffold-aware `_templates_root` makes vendored oracle-install self-contained (closes 007-03 gap); SKILL.md `${CLAUDE_PLUGIN_ROOT}`→`.claude/skills/servo-*` rewrite; vendored-`.md` unresolved-link strip; new `stale_source_reference` verifier reason (distinct from `artifact_missing`); AC2 in-test command classification; review PASS |
| [007-install-surfaces](007-install-surfaces/spec.md) | 007-05 — docs-and-ci | **DONE** | 9 doc-guard tests; README "Installing servo" (3 surfaces + release recipe); two-layer model in vision/architecture/specs; `scripts/verify_install_surfaces.sh` (one command) wired to CI via `.github/workflows/verify.yml`; review PASS — **spec 007 complete** |
