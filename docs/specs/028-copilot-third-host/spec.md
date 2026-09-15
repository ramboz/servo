---
status: DRAFT
skill:
use_cases: []
---

# Spec 028: GitHub Copilot CLI as a third committed host

> Implements [ADR-0034](../../decisions/adr-0034-copilot-third-host.md).
> Extends the dual-host model of
> [ADR-0028](../../decisions/adr-0028-committed-dual-host-plugin-packages.md) to
> a tri-host layout. Mirrors jig spec 113 (the keystone).

## Overview

Adobe disables Claude Code on **2026-09-28** and makes GitHub Copilot the primary
coding agent. servo must ship as a first-class **GitHub Copilot CLI** host: a
committed, drift-guarded `hosts/copilot/` package rendered from canonical source,
installable via `/plugin`, with a `servo-copilot-vX.Y.Z.zip` release archive.

Per ADR-0034, most of servo's surface carries over (Copilot reads Claude-format
skills/`CLAUDE.md`/`.mcp.json` directly), but servo-specific behavior needs a
render layer: skill-loader compatibility, hook translation onto Copilot's 14
events, and — uniquely for servo — **mapping the optional loop/oracle execution
primitives** ADR-0028 had called Claude-only. The Adobe guide maps them:
`claude -p`→`copilot -p -s`, Claude `Stop`→`agentStop`, `/goal`→Autopilot, and
the ADR-0033 preflight→Copilot's permission model. Those mappings are the guide's
own "conceptual equivalents" and must be validated, with any true residual
recorded honestly (ADR-0028's invariant).

**Scope:** Copilot **CLI** only. This spec covers **servo**; jig (spec 113) is
the keystone and shaper mirrors separately.

## Assumptions

<!-- Grounding-by-probe (risk-gated). -->

- Copilot capability facts come from Adobe's migration guide + terminology map
  (read 2026-09-15, CLI ~1.0.84), not a servo-run probe. **Slice 028-01 (spike)
  re-verifies the load-bearing ones — especially whether Autopilot supports an
  oracle-gated stop — against a live `copilot` session before the loop-mapping
  slice commits.**
- The execution-primitive mappings are the guide's stated "conceptual
  equivalents"; servo's loop must not rely on them until 028-01 validates them.

## Decomposition

Host-adapter infrastructure: "vertical" = a Copilot user can install and use
progressively more of servo. Primarily **Interface** (install+skills → agents),
**Rules** (hook translation), and one servo-specific **Path** slice (the
execution-primitive mapping for the optional loop), with one **Spike** for the
external Copilot-contract + primitive-mapping unknowns and a final **parity**
slice.

- **S (028-01)** — verify the Copilot install/skill/hook/agent contract **and**
  the `claude -p`/`Stop`/`/goal`→`copilot -p`/`agentStop`/Autopilot mappings,
  especially the oracle-gated-stop question, against a live session.
- **I (028-02)** — renderer + minimal committed `hosts/copilot/`: skills +
  instructions load (loader-compat invariant).
- **I (028-03)** — render servo's agents (the loop `runner`, review roster) to
  `.github/agents/` (model-neutral).
- **R (028-04)** — translate servo's hooks (oracle `Stop`→`agentStop`,
  quality-gate) to Copilot events; mapped-or-unmappable inventory.
- **P (028-05)** — map the optional loop/oracle execution primitives to their
  Copilot equivalents (or record residual): the servo-specific slice.
- **Parity (028-06)** — committed package + drift guard + CI + release archive +
  per-host verification.

**Deadline-aware ordering.** 028-01→05 is the "works under Copilot" core;
028-06 (drift/release automation) may land at/just after the cutover.
**Anti-horizontal-phasing:** every non-spike slice leaves a Copilot user able to
do something new end-to-end.

## Slices

- [028-01 — copilot-contract-spike](slice-01-copilot-contract-spike.md) — verify Copilot contract + the execution-primitive mappings.
- [028-02 — renderer-and-skeleton](slice-02-renderer-and-skeleton.md) — host renderer + minimal `hosts/copilot/` (skills + instructions load).
- [028-03 — agents](slice-03-agents.md) — render servo agents to `.github/agents/` (model-neutral).
- [028-04 — hooks](slice-04-hooks.md) — translate servo hooks to Copilot events; mapped-or-unmappable inventory.
- [028-05 — execution-primitive-mapping](slice-05-execution-primitive-mapping.md) — map the optional loop/oracle primitives (`claude -p`→`copilot -p`, `/goal`→Autopilot) or record residual.
- [028-06 — committed-package-and-release](slice-06-committed-package-and-release.md) — drift guard + CI + release archive + per-host verification.
