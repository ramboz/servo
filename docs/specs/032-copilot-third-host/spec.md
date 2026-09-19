---
status: DONE
skill:
use_cases: []
---

# Spec 032: GitHub Copilot CLI as a third committed host

> Implements [ADR-0038](../../decisions/adr-0038-copilot-third-host.md).
> Extends the dual-host model of
> [ADR-0028](../../decisions/adr-0028-committed-dual-host-plugin-packages.md) to
> a tri-host layout. **Mirrors jig's SHIPPED keystone** (jig ADR-0061 / spec 113,
> merged to jig `main`): servo ports jig's proven `hosts/copilot/` mechanism —
> the `.github/` layout, the `copilot_hook_adapter.py`, the loader-safe skill
> render, the `$SERVO_ROOT` plugin-mode path rewrite, and the marketplace
> descriptor — adapting each to servo's smaller surface and function-based builder.

## Overview

servo ships today as committed Claude + Codex packages (ADR-0028). This spec adds
a first-class **GitHub Copilot CLI** host: a committed, drift-guarded
`hosts/copilot/` package rendered from canonical source into Copilot's `.github/`
home, installable via `copilot plugin install`/marketplace, with a
`servo-copilot-vX.Y.Z.zip` release archive. **The bar is parity with Claude/Codex,
not a survival install** (parity, not the 2026-09-28 cutover, is the justification
— see ADR-0038).

Most of servo's surface carries over (Copilot reads Claude-format `SKILL.md` /
`CLAUDE.md` directly), but servo-specific behavior needs a render layer that
mirrors jig's shipped solution:

- **Loader-safe skills** — strip the `servo:` invocation namespace from the loaded
  `name:` (servo's 9 namespaced source skills), and enforce the ≤1024-char
  `description:` limit with jig's keep-or-truncate-and-preserve rule (append the
  full text to the body; never drop). 9 of 12 servo skills are over the limit.
- **`$SERVO_ROOT` plugin-mode path rewrite (jig bug 036)** — servo's 10 skills
  document `${CLAUDE_PLUGIN_ROOT}/skills/.../*.py`; that variable does **not**
  resolve under Copilot plugin-mode, so the renderer rewrites to `$SERVO_ROOT`,
  ships a `servo_root.py` fresh-shell locator, and injects a self-contained
  locator one-liner into each affected skill's root-note. Unlike jig, servo's
  Copilot package is **hook-free**, so there is **no `SessionStart` carrier** —
  the locator one-liner is the sole resolution path. Templates ship **unrendered**
  (canonical marker intact).
- **Agents** rendered to `.github/agents/<name>.agent.md` (tools mapped, model-neutral).
- **Hooks via the adapter** — servo's oracle `Stop` maps to Copilot `agentStop`
  through `copilot_hook_adapter.py` (ported from jig); because servo's hook is
  installed *target-side* by the `oracle-hook` skill (servo ships no plugin-level
  hooks), the translation teaches that skill to emit an `agentStop` hook for a
  Copilot target.
- **Execution primitives (servo-specific)** — the optional loop's `claude -p
  --agent runner` maps to `copilot -p -s --agent runner --allow-all-tools`
  (`--output-format json` parseable output; `--usage-output-file` exposes cost
  **and** a native `codeChanges.filesModifiedCount` edit-signal). The goal driver's
  per-turn oracle gate maps via `agentStop`; residual recorded honestly.
- **Package/release parity** — a `.plugin/plugin.json` legacy manifest with
  component-path fields, a repo-root `.github/plugin/marketplace.json` (jig bug
  035), `servo-copilot-vX.Y.Z.zip`, drift guard, and release-please lockstep.

**Pre-empt jig's 3 post-ship fixes** from the first slice: scaffold host-inference
(034), the marketplace descriptor (035), and the `$SERVO_ROOT` path rewrite (036).

**Scope:** Copilot **CLI** only. IDE-surface parity out of scope.

## Assumptions

- **Copilot contract is now KNOWN from jig's shipped `hosts/copilot/`** (ADR-0061 /
  spec 113 on jig `main`), not merely from the Adobe guide. The `.github/` layout,
  legacy `.plugin/plugin.json` component paths, flat hook schema, `agentStop`
  event, `.agent.md` form, loader limits, and the 3 bug fixes are all verifiable
  in jig's committed package. Slice 032-01 confirms them against jig's package +
  a live `copilot` 1.0.84+ session and records servo's own facts (corpus, loop).
- **servo diverges from jig where its surface differs:** servo strips a `servo:`
  name prefix (jig asserts `:`-free — jig has no source prefix); servo ships no
  plugin-level hooks (its `hooks/` source is empty; the oracle hook is target-side
  via `oracle-hook`); servo has a loop.py + goal driver jig lacks.
- **Static smoke, not live** — headless `copilot -p` does not reliably fire repo
  hooks, so package verification is a static `validate_copilot_package`-style
  check (per jig); live-CLI hook firing is recorded as an honest residual.

## Decomposition

Host-adapter infrastructure, mirroring jig spec 113's decomposition scoped to
servo's smaller surface (servo's single oracle hook collapses jig's advisory +
enforcing + live-hook + transcript slices into one; jig's plugin-component-
discovery folds into servo's renderer slice as manifest-component-path +
install-smoke ACs).

- **S (032-01)** — confirm the Copilot contract (reusing jig's shipped, verified
  shape) and servo's execution-primitive mappings against a live session; record
  servo's corpus + loop facts.
- **I (032-02)** — Copilot renderer + committed `hosts/copilot/` skeleton: skills
  load loader-safe, `$SERVO_ROOT` rewrite, `.plugin/plugin.json` with component
  paths, `.github/plugin/marketplace.json`, scaffold host-inference — installs +
  a skill is invocable (folds jig 113-02 + 113-07 + bugs 034/035/036).
- **I (032-03)** — render servo's agents (`runner`, `judge`) to
  `.github/agents/*.agent.md` (tools mapped, model-neutral).
- **R (032-04)** — servo's oracle `Stop`→`agentStop` via the ported
  `copilot_hook_adapter.py`, taught to the `oracle-hook` skill for Copilot
  targets; mapped-or-unmappable inventory (folds jig 113-04/05/08/09).
- **P (032-05)** — map the optional loop's execution primitives (`claude -p`→
  `copilot -p -s`, cost + edit-signal, goal-driver/`agentStop`) or record residual:
  the servo-specific slice (no jig analogue).
- **Parity (032-06)** — committed package + drift guard + CI + `servo-copilot`
  release archive + marketplace validation + per-host static smoke + docs.

**Anti-horizontal-phasing:** every non-spike slice leaves a Copilot user able to
do something new end-to-end.

## Slices

- [032-01 — copilot-contract-spike](slice-01-copilot-contract-spike.md) — confirm Copilot contract (vs jig's shipped) + servo's execution-primitive mappings.
- [032-02 — renderer-and-skeleton](slice-02-renderer-and-skeleton.md) — Copilot renderer + committed `hosts/copilot/` (loader-safe skills, `$SERVO_ROOT`, manifest+marketplace, install smoke).
- [032-03 — agents](slice-03-agents.md) — render servo agents to `.github/agents/*.agent.md` (model-neutral).
- [032-04 — hooks](slice-04-hooks.md) — oracle `Stop`→`agentStop` via the ported adapter, in `oracle-hook`; mapped-or-unmappable inventory.
- [032-05 — execution-primitive-mapping](slice-05-execution-primitive-mapping.md) — loop `claude -p`→`copilot -p -s`, cost/edit-signal, goal-driver/`agentStop` or residual.
- [032-06 — committed-package-and-release](slice-06-committed-package-and-release.md) — drift guard + CI + release archive + marketplace validation + static smoke + docs.
