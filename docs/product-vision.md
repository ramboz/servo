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
- Putting that loop on a **schedule** — letting servo surface work from the project's own signals (CI failures, open issues, recent commits) and queue it unattended, instead of hand-kicking each loop

Servo is **not** for users who haven't yet adopted spec-driven dev. The risk profile is materially higher, and the prerequisites (composable quality signals, slice-shaped work) come from the supervised practice servo builds on.

### New surface — scheduled, self-directed discovery (the heartbeat)

Servo's first surfaces are all **human-triggered**: a dev decides what to work on and kicks off a loop. The **heartbeat** adds a **schedule-triggered** surface — a Routine (cron, a scheduled agent, a CI `schedule:` trigger) wakes servo on an interval; servo does a **read-only** discovery pass over the project's own signals (CI failures, open issues, recent commits), writes findings to a servo-owned **triage inbox**, and hands each *actionable* one to the oracle-gated runtime in an isolated worktree. This is a materially **higher-risk surface** — servo now decides *what* to work on, not just *how* — so it carries its own non-negotiable controls (see the design principle below) and is Tier-2 (explicit opt-in only). Servo ships the heartbeat; the Routine is the clock. See backlog #7 and [spec 011](specs/011-heartbeat/spec.md).

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
4. **`/servo:spec-oracle`** — compile a spec/slice into a reviewable, deterministic evidence overlay on top of the baseline oracle. *Spec 006 — DONE.*
5. **`/servo:oracle-hook`** — Claude Code hook installer (idempotent install / uninstall / status). *Spec 004 — DONE.*
6. **`/servo:variant-race`** — N-worktree parallel race with quality-gate scoring and winner selection. *Future spec.*
7. **`/servo:heartbeat`** — Routine-triggered, read-only discovery pass over project signals (CI failures, open issues, recent commits) → servo-owned triage inbox → oracle-gated dispatch of each actionable finding into an isolated worktree loop, under one whole-heartbeat cost ceiling. The scheduled **front-end** that surfaces work; servo's middle/tail (loop / oracle / race / state) consume what it queues. *Spec 011 — DONE.*

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
- **Schedule-triggered is a distinct surface from human-triggered.** Servo's first six skills assume a human kicks off the loop. The heartbeat (spec 011) lets a *schedule* trigger it — so servo decides *what* to work on, not just *how*. That new audience/risk surface carries its own non-negotiable controls: discovery is strictly **read-only** (it proposes via the triage inbox, it never executes), the hard cost ceiling bounds the **whole heartbeat** (discovery + every spawned loop, not per-loop), and **refuse-without-oracle** still holds at the dispatch boundary (no finding spawns a loop without passing the oracle). Servo ships the heartbeat; it does **not** own the scheduler — same as it can feed CI but isn't a CI.
