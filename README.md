# servo

> A Claude Code plugin that scaffolds closed-loop, unattended agent operations into existing projects.

**servo** (noun): a closed-loop control system — measures a signal, compares it to a target, and adjusts until they match.

## Why servo exists

[jig](https://github.com/ramboz/jig) handles **supervised** spec-driven development — the M1–M6 territory of the agentic learning path. Past that boundary, the curriculum stops talking about specs and starts talking about **unattended agent loops**: oracle scoring (M7), headless iteration (M8), hook-as-meta-judge (M9), worktree race (M10).

Those patterns share a different risk profile, maturity, and audience from jig's surface — they spawn N parallel agents, install hooks that fire every `Stop`, race worktrees that cost real money. Bundling them into jig would silently expand jig's scope. Servo is the **autonomous sibling** that keeps the contract explicit: installing servo means crossing the line into unattended operation.

## What it does

Servo's primary entry point is a **scaffolder**, not a runtime. It probes the target project's signals (tests, lint, CI, language, project size) and drops a tailored set of artifacts — `oracle.sh`, agent-loop driver, hook installer, race driver — that reflect what the project actually has, instead of a generic stub the dev has to rewrite.

| Curriculum | Servo skill | Status |
|---|---|---|
| (scaffold) | `/servo:scaffold-init` | Spec 001 — DRAFT |
| M7 oracle | `/servo:quality-gate` | Future spec |
| M8 Ralph loop | `/servo:agent-loop` | Future spec |
| M9 meta-judge hook | `/servo:oracle-hook` | Future spec |
| M10 worktree race | `/servo:variant-race` | Future spec |

## Relationship to jig

Servo is a **sibling plugin**, not a dependency. They coexist in `${CLAUDE_PLUGIN_ROOT}` and reference each other only via filesystem hints — no cross-plugin registration mechanism, no hard dependency.

- Install servo without jig (oracle/headless only) or jig without servo (current default, supervised only).
- Servo reuses jig's `tdd.py detect` (via subprocess) when jig is installed; falls back to its own minimal test-runner detection otherwise.
- Jig's `slice-land prepare` emits soft pull-hints for servo artifacts when servo-style infrastructure is missing — that's the entirety of the coupling.

## Design philosophy

> Scaffold first, runtime later. Per-project, signal-aware artifacts — never generic stubs.

- Composite oracle score that reflects available signals (tests, lint, coverage, CI, seeded-issues)
- Hard guardrails on loops: iteration cap, cost ceiling, refuse on dirty tree, refuse without an oracle
- Hooks installed explicitly (never auto-installed); reversible install/uninstall
- Worktree races bounded (default 3 variants, hard cap 5)

See [docs/product-vision.md](docs/product-vision.md) for the vision and [docs/architecture.md](docs/architecture.md) for the mechanics. See [docs/specs/](docs/specs/) for spec state.

## License

[MIT](LICENSE)
