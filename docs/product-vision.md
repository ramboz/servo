---
status: DRAFT
last_verified:
---

# Product vision: servo

> Status: Draft. Refined as specs land.

## Vision

A Claude Code plugin that scaffolds **closed-loop, unattended agent operations** into existing projects — tailored to each project's available signals — so devs can move past supervised spec-driven dev into headless iteration without rebuilding the infrastructure each time.

## Target users

Developers who already practice spec-driven, supervised AI development (the jig audience) and want to graduate to:

- Running agent loops headlessly against a quality oracle
- Installing meta-judge hooks that score every `Stop` and emit retry suggestions
- Racing worktree variants in parallel and picking the winner by score

Servo is **not** for users who haven't yet adopted spec-driven dev. The risk profile is materially higher, and the prerequisites (composable quality signals, slice-shaped work) come from the supervised practice servo builds on.

## Core problem

Each of the four unattended-agent patterns (oracle scoring, headless iteration, meta-judge hooks, worktree races) is well-documented in the abstract. Adopting them on a real project means:

1. Writing a project-specific `oracle.sh` that composes the right signals (which signals does this project even *have*?)
2. Tuning weights and thresholds by hand
3. Translating each spec's acceptance criteria into executable evidence instead of relying on a generic judge
4. Wiring loop drivers, hook installers, and race orchestrators
5. Repeating all of the above on the next project

The same scars, every project. Servo encodes the scaffolding so the dev sets weights and prompts — not infrastructure.

## Competitive landscape

- **jig** — supervised spec-driven dev. Sibling, not competitor. Servo picks up where jig stops.
- **claude-flow, agent-frameworks, autogen** — heavyweight, opinionated runtimes. Servo is the opposite shape: thin scaffolder, no runtime lock-in, lives in the project's own scripts.
- **GitHub Actions / CI recipes for agents** — distribution mechanism, not a scaffolder. Servo could feed into them, but isn't one.

## Backlog (prioritized)

1. **`/servo:scaffold-init`** — probe target signals, run Q&A, drop tailored `oracle.sh` (and optionally agent-loop / hook installer / race driver stubs) into target. *Spec 001 — DONE.*
2. **`/servo:quality-gate`** — runtime invocation of the scaffolded oracle, normalized exit codes. *Spec 002 — DONE.*
3. **`/servo:agent-loop`** — headless iteration driver with iteration cap, cost ceiling, checkpoint/resume. *Spec 003 — DONE.*
4. **`/servo:spec-oracle`** — compile a spec/slice into a reviewable, deterministic evidence overlay on top of the baseline oracle. *Spec 006 — DRAFT.*
5. **`/servo:oracle-hook`** — Claude Code hook installer (idempotent install / uninstall / status). *Future spec.*
6. **`/servo:variant-race`** — N-worktree parallel race with quality-gate scoring and winner selection. *Future spec.*

## MVP scope

Spec 001 (`/servo:scaffold-init`) only. Drops `oracle.sh` into target with signal-aware weights. Other M-* skills come later, gated on 001 landing.

## Future scope

- Runtime and spec-overlay skills (2–6 above)
- Spec-specific evidence overlays (`/servo:spec-oracle`) that turn acceptance criteria into runnable checks before unattended loops begin
- A short architecture-doc section "Why no crew skill" + post-mortem template (multi-agent crew coordination doesn't yet generalize enough to ship as a skill)
- Pull-hint integration with jig's `slice-land prepare`

## Design principles

- **Two install layers, named explicitly.** *Servo runtime install* (getting servo's own skills/agents/templates onto a machine — via plugin root, release zip, or a project-local `.claude/` scaffold) is a different thing from *project oracle install* (`/servo:scaffold-init` dropping a tailored `oracle.sh` + `.servo/install.json` into a target repo). All three runtime surfaces share one contract and one verifier (`scripts/verify_install.py`); see [architecture.md](architecture.md) and the README for the chooser. *Spec 007 — DONE.*
- **Per-project artifacts beat plugin-owned runtime.** The dev's `oracle.sh` is theirs; servo only scaffolds it.
- **Refuse-on-missing-prerequisite.** If servo's runtime skills can't find `oracle.sh`, they exit non-zero. No silent degradation.
- **Reversibility.** Hooks install and uninstall cleanly. Race worktrees clean up by default.
- **Signal-aware, not signal-prescriptive.** Probe what's there. If lint isn't configured, don't include it in the composite.
