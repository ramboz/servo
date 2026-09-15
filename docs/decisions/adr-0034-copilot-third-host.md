---
status: Proposed
dependencies: ["adr-0028-committed-dual-host-plugin-packages"]
last_verified: 2026-09-15
frame_review: true
---

# ADR-0034: GitHub Copilot CLI as a third committed host

## Status

Proposed (2026-09-15)

> Filed as part of the cross-repo GitHub Copilot migration. jig ADR-0061 is the
> keystone pattern; servo mirrors it. Owner should run the frame-critique +
> accept flow before adopting.

## Context

Adobe disables Claude Code on **2026-09-28** and makes GitHub Copilot the primary
coding agent (internal migration hub, read 2026-09-15). servo ships today as
committed Claude + Codex packages ([ADR-0028](adr-0028-committed-dual-host-plugin-packages.md)).
To remain installable and usable after the cutover, servo must add **GitHub
Copilot CLI** as a third host.

servo is more exposed than a pure skill pack. ADR-0028 explicitly carved out
Claude-specific execution primitives as non-portable: *"Several Servo behaviors
are genuinely Claude-specific (`claude -p`, `/goal`, and Claude `Stop` hooks)."*
The Adobe migration guide changes that calculus — it maps each to a Copilot
equivalent:

- `claude -p "…"` → `copilot -p "…" -s` (non-interactive run).
- Claude `Stop` hook → Copilot **`agentStop`** (one of Copilot's 14 hook events).
- `/goal` (Goal mode: long-running autonomous work) → Copilot **Autopilot**
  (`copilot --autopilot <objective> --max-ai-credits N`).
- The ADR-0033 headless edit-permission preflight maps onto Copilot's *separate*
  permission controls (`--allow-tool`/`--deny-tool`; experimental Assisted
  approvals) — autonomy and tool-permission are distinct dials in Copilot.

So the "Claude-specific" residual ADR-0028 recorded is **smaller** under Copilot
than under Codex. But the guide is explicit that these are *"conceptual
equivalents, not identical runtimes,"* that hook payloads differ, and that each
hook must be tested — so servo must **translate and validate**, and record any
genuine residual honestly, the same discipline ADR-0028 applied.

The shared Copilot facts (from jig ADR-0061, same sources) hold for servo too:
Copilot reads Claude-format `SKILL.md`, `CLAUDE.md`, and `.mcp.json` directly and
installs Claude-format plugins via `/plugin`; skill-loader limits (`:` in name,
description >1024 chars); hooks are 14 camelCase events with differing payloads;
custom agents render to `.github/agents/`; and `.github/` is the durable config
home.

**Scope:** GitHub Copilot **CLI** (matching Adobe's scope and servo's CLI-first
eval tooling). IDE-surface parity is out of scope.

## Decision Options Considered

### Option A: Cross-tool reliance only — no new host package
Lean on Copilot reading `.claude/` + `/plugin`; fix only loader breakers.
- **Pros:** smallest change; fastest to cutover.
- **Cons:** privileges the Claude shape (the asymmetry ADR-0028 rejected); the
  oracle `Stop` hook and the loop's `claude -p` primitives degrade silently under
  Copilot; nothing renders into `.github/`.

### Option B: Advisory / instructions-only
Emit `.github/copilot-instructions.md`; don't port hooks/loop natively.
- **Pros:** trivial.
- **Cons:** servo *is* executable guardrails and oracles; the guide warns
  "instruction files are not security controls." Rejected.

### Option C (chosen): Copilot as a third committed host under `hosts/copilot/`
Extend ADR-0028's committed-per-host model to a tri-host layout, adding a Copilot
host renderer + committed `hosts/copilot/` package, drift guard, and a
host-explicit release archive — the render layer absorbing loader limits, hook
translation, and the execution-primitive mapping.
- **Pros:** symmetric with Claude/Codex; honors `.github/` as Copilot's durable
  home; keeps servo's guardrails/oracles working under Copilot; extends ADR-0028
  + spec 022's release parity to tri-host along the pattern jig ADR-0061 sets.
- **Cons:** a third package to build/drift-guard/version/release; the hook +
  execution-primitive translation is real engineering and must be validated
  against a live Copilot session.

### Option D: A separate Copilot-only artifact
- **Cons:** source divergence + double maintenance — what ADR-0028's
  single-source model prevents. Rejected.

## Recommended Decision

Adopt **Option C**, mirroring jig ADR-0061. servo's builder gains a Copilot arm
and a Copilot host renderer that:

- renders skills (loader-safe: namespace-safe names, ≤1024-char descriptions with
  full text preserved in the body), instructions, and MCP config into the
  `.github/` homes — leaving Claude/Codex output byte-unchanged;
- translates servo's hooks (the oracle `Stop`→`agentStop`; any quality-gate
  `preToolUse`/`permissionRequest`) to Copilot's event/decision schema, with a
  **mapped-or-explicitly-unmappable inventory**;
- maps the optional loop/oracle **execution primitives** to their Copilot
  equivalents where the guide provides one (`claude -p`→`copilot -p -s`;
  `/goal`→Autopilot; the ADR-0033 preflight→Copilot's permission model), and
  records any primitive that genuinely does not port as an explicit residual;
- adds the drift guard, a `servo-copilot-vX.Y.Z.zip` release archive, and a
  per-host install/smoke verification, extending ADR-0028 + spec 022's release
  parity to three hosts.

**Preserve ADR-0028's honesty invariant.** Host packaging maps an execution
primitive only where a *documented* Copilot equivalent exists, and records the
rest as explicit residual — never a silent mechanical rename (ADR-0028's rejected
"mechanically replace every Claude reference" option). Gates and primitives
degrade *visibly*, never silently.

## Consequences

**Becomes easier:**
- servo survives the cutover and installs natively for Copilot CLI; its oracle
  gates and (mapped) loop work under Copilot rather than silently no-op'ing.
- Copilot's cloud agent + code review pick up servo's `.github/` config.

**Becomes harder:**
- A third generated package to drift-guard, version, and release.
- The hook + execution-primitive translation must be re-validated as Copilot's
  surface evolves (the guide warns behavior changes quickly).

**Invariants:**
- Repository root stays canonical source; `hosts/copilot/` is drift-guarded
  build output.
- The render layer enforces Copilot loader limits + schema; Claude/Codex output
  unchanged.
- Every servo hook and Claude-specific primitive is mapped or recorded as
  residual — never silently dropped or mechanically renamed.

## Assumptions

<!-- Grounding-by-probe (risk-gated). -->

- Copilot capability facts come from Adobe's migration guide + terminology map
  (read 2026-09-15, Copilot CLI ~1.0.84), not a servo-run probe — **re-verify at
  implementation** (spec 028 spike).
- The execution-primitive mappings (`claude -p`→`copilot -p -s`;
  `Stop`→`agentStop`; `/goal`→Autopilot) come from the guide's command/terminology
  tables and are its own stated *"conceptual equivalents"* — they must be
  validated against a live `copilot` session before servo's loop relies on them.
- servo's optional loop subprocesses `claude -p --agent runner` today (ADR-0033);
  mapping it to `copilot -p --agent runner` presupposes the runner agent exists as
  a Copilot agent (depends on the agent-rendering slice).

## Kill criteria

- Adobe reverses/postpones the Claude Code disablement → priority drops.
- Copilot **Autopilot cannot express the oracle-gated continuation** servo's
  `/goal` loop needs (only a turn/credit cap, no eval-gated stop) → servo's
  unattended loop stays Claude-only under Copilot, documented as residual (a
  partial fall-back to ADR-0028's "not portable" posture for the loop
  specifically), while the eval/oracle skills still port.
- `/plugin` can't install servo's Claude-format package and no `.github/`-native
  path works → rethink the package shape (shared with jig's spike).

## Open questions

- Exact Copilot plugin/marketplace manifest shape (shared with jig spec 113-01).
- Does Copilot Autopilot support an **oracle-gated** stop condition, or only a
  turn/credit cap? (Validate — it decides whether servo's loop ports.)
- Which servo hooks/primitives have no Copilot equivalent (inventory is a spec
  deliverable).
