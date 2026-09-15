---
status: Proposed
dependencies: ["adr-0028-committed-dual-host-plugin-packages"]
last_verified: 2026-09-15
frame_review: true
---

# ADR-0034: GitHub Copilot CLI as a third committed host

## Status

Proposed (2026-09-15)

> Filed as part of the cross-repo GitHub Copilot migration. jig ADR-0061 / spec
> 113 establish the same tri-host pattern **in parallel** (jig ADR-0061 is
> Accepted on its own branch, not yet on jig `main`); servo does **not** inherit
> jig's grounding — the load-bearing Copilot facts below were re-verified against
> a live `copilot` CLI (1.0.84-8) during this ADR's frame-critique, and servo's
> own corpus exposure was measured directly. Owner runs frame-critique + accept.

## Context

servo ships today as committed Claude + Codex packages under the source-derived,
one-package-per-host model of
[ADR-0028](adr-0028-committed-dual-host-plugin-packages.md). This ADR adds
**GitHub Copilot CLI** as a third committed host.

**The bar is full parity with the Claude and Codex hosts**, not a survival
install. Every servo capability Copilot can express is rendered natively into
Copilot's homes; the irreducible residual (any primitive or hook event Copilot
has no equivalent for) is explicitly inventoried and degrades *visibly*, never
silently. This is ADR-0028's own honesty invariant, extended to a third host —
the symmetry argument that motivated committing the Codex peer in the first
place. Adobe's retirement of Claude Code (Copilot becomes the primary coding
agent **2026-09-28**, Claude Code disabled that date; internal migration hub,
read 2026-09-15) is the *occasion* that makes adopting Copilot now the priority —
it is **not** the load-bearing justification for the decision and does **not**
set the quality bar. A deadline reversal would lower the priority, not change
that a third host should reach parity (see kill criteria).

servo is more exposed than a pure skill pack, so "Copilot reads the files" is not
"servo behaves correctly." The shared Copilot facts hold for servo as they do for
jig, but were **verified against live `copilot` 1.0.84-8** (not inherited):

- Copilot reads Claude-format `SKILL.md`, `CLAUDE.md`, and `.mcp.json` directly,
  and discovers skills from `.github/skills/`, `.agents/skills/`, **and
  `.claude/skills/`**; `/plugin` (`copilot plugin install owner/repo:path`)
  installs Claude-format plugins (Agent-Plugins-1.0 layout — see Assumptions).
- Custom agents render to `.github/agents/<name>.agent.md` (`description`
  required; `name`/`tools`/`model`/`user-invocable`/… optional).
- Hooks are **14 camelCase events** with differing payloads and decision schemas;
  repo config lives at `.github/hooks/*.json`.

Three servo-specific things break or degrade under Copilot as-is:

1. **Skill-loader limits.** Copilot fails to load a skill whose name contains `:`
   or whose `description:` **field** exceeds 1,024 characters. A **probe of servo
   source (2026-09-15)** found servo carries **both** hazards, co-located on the
   same skills: **9 of 12 skills are namespaced `servo:<skill>` AND have a full
   `description:` field over the limit** (1,043–2,138 chars: `agent-loop` 2138,
   `autonomy-readiness` 2019, `execution-planner` 1616, `edd-suitability` 1557,
   `oracle-hook` 1408, `spec-oracle` 1401, `quality-gate` 1129, `heartbeat` 1087,
   `scaffold-init` 1043); the other 3 (`content-fidelity`, `eval-authoring`,
   `design-eval`) carry bare names and short (<730-char) descriptions. So the
   render layer must apply **the same treatment the Codex renderer already does**
   (`build_host_packages._render_codex_skill`, `_CODEX_DESCRIPTION_MAX = 1024`):
   strip the `servo:` namespace from the loaded name **and** collapse the
   multi-paragraph `description:` to its first (routing-summary) paragraph — ≤1024
   chars (verified max 726) — with the full description text preserved in the
   skill body. Both fixes, not just the name-strip: a namespace-only render would
   ship 9 skills whose descriptions silently fail Copilot's loader, violating this
   ADR's own "degrade *visibly*, never silently" invariant.
2. **Hooks port but differ.** servo's oracle gate is a Claude `Stop` hook; Copilot
   has `agentStop`. The **decision output is identical** — both take
   `{"decision":"block","reason":…}` where `reason` becomes the next turn's prompt
   — but the input payload differs (Copilot camelCase `sessionId`/`transcriptPath`
   + `stopReason`/`cwd`/`timestamp`; Claude snake_case). A translated hook and any
   payload-field access must be adapted and validated, not mechanically renamed.
3. **Execution primitives.** ADR-0028 carved `claude -p`, `/goal`, and Claude
   `Stop` hooks out as "genuinely Claude-specific." Copilot narrows that residual
   (see the mapping in Decision), but the mapping is real engineering, not a
   rename, and must be validated against a live session.

**Scope:** GitHub Copilot **CLI** (matching Adobe's scope and servo's CLI-first
eval tooling). IDE-surface parity is out of scope.

## Decision Options Considered

### Option A: Cross-tool reliance only — no new host package
Lean on Copilot reading `.claude/` + `/plugin`; fix only loader breakers.
- **Pros:** smallest change.
- **Cons:** privileges the Claude shape (the asymmetry ADR-0028 rejected); the
  oracle `Stop` hook and the loop's execution primitives degrade **silently**
  under Copilot; nothing renders into `.github/`. This is the "just installs,
  gates silently degraded" lifeboat — rejected on parity grounds, not kept as a
  deadline hedge.

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
- **Pros:** symmetric with Claude/Codex (an installed plugin package, as they
  are); honors Copilot's native config homes as its durable
  home; keeps servo's guardrails/oracles working under Copilot; extends ADR-0028
  + spec 022's release parity to tri-host along the same pattern jig ADR-0061 /
  spec 113 establish in parallel.
- **Cons:** a third package to build/drift-guard/version/release; the hook +
  execution-primitive translation is real engineering and must be validated
  against a live Copilot session.

### Option D: A separate Copilot-only artifact
- **Cons:** source divergence + double maintenance — what ADR-0028's
  single-source model prevents. Rejected.

## Recommended Decision

Adopt **Option C**. servo's builder gains a Copilot arm and a Copilot host
renderer that:

- renders skills loader-safe (`servo:`-namespace stripped from the loaded name
  **and** the multi-paragraph `description:` collapsed to its ≤1024-char first
  paragraph, full text preserved in the skill body — reusing the Codex renderer's
  treatment) plus a Copilot instructions file, **into the committed
  `hosts/copilot/` plugin package** (Agent-Plugins-1.0 layout — see Assumptions),
  leaving Claude/Codex output byte-unchanged. (servo ships no `.mcp.json`, so no
  MCP config is rendered; the empty-set is recorded, not silently skipped.)
- translates servo's oracle `Stop` hook to Copilot `agentStop` (identical
  `{decision,reason}` output; adapted input-payload access), plus any quality-gate
  `preToolUse`/`permissionRequest`, with a **mapped-or-explicitly-unmappable
  inventory** that enumerates *every* source hook so none is silently dropped.
  (servo ships **no** plugin-level hooks today — its one hook, the oracle `Stop`,
  is installed target-side by the `oracle-hook` skill; the translation therefore
  teaches that skill to emit an `agentStop` hook for a Copilot target. The
  inventory over the source set is a one-entry map, but the enumeration guard
  still holds.)
- maps the optional loop/oracle **execution primitives** to their Copilot
  equivalents (see below), recording any primitive that genuinely does not port as
  an explicit residual;
- adds the drift guard, a `servo-copilot-vX.Y.Z.zip` release archive, and a
  per-host install/smoke verification, extending ADR-0028 + spec 022's release
  parity to three hosts.

**Execution-primitive mapping (grounded, live `copilot` 1.0.84-8).**

- `claude -p "…"` → `copilot -p "…" -s` (non-interactive; `--output-format json`
  gives the loop parseable per-line output, `--usage-output-file` the cost).
  **Non-interactive tool use requires `--allow-all-tools`** (or specific
  `--allow-tool`) or edits are refused — this is Copilot's analog of the ADR-0033
  permission wall and where that preflight maps.
- servo's **loop driver** subprocesses `claude -p --agent runner` per iteration
  and gates on the oracle *in servo's own Python loop* — it is self-driving and
  maps cleanly to per-iteration `copilot -p -s --agent runner --allow-all-tools`.
  **It does not need, and should not use, Copilot Autopilot.**
- servo's **goal driver** (ADR-0008) delegates continuation to the host's native
  long-running mode and wraps it with caps + a final oracle check. Copilot's
  native equivalent is **Autopilot** (`--autopilot`, bounded by
  `--max-autopilot-continues` and `--max-ai-credits`). Autopilot exposes **only a
  turn/credit cap — no oracle-gated internal stop** (verified live). That is
  sufficient for the goal driver *because the goal driver never gated internally
  either* (it caps + final-checks); the exact fidelity of that mapping is a spec
  028-01 / 028-05 validation item, not an assumption.
- The ADR-0033 headless edit-permission preflight → Copilot's permission dials
  (`--allow-all-tools` / `--allow-tool` / `--deny-tool`; experimental
  `--assisted-approval`). Autonomy and tool-permission are distinct dials.

**Preserve ADR-0028's honesty invariant.** Host packaging maps an execution
primitive or hook only where a *documented, verified* Copilot equivalent exists,
and records the rest as explicit residual — never a silent mechanical rename
(ADR-0028's rejected "mechanically replace every Claude reference" option). The
hook inventory is enumerated over the source set so an omission is a caught gap,
not a silent drop. Gates and primitives degrade *visibly*.

## Consequences

**Becomes easier:**
- servo installs natively for Copilot CLI at parity with Claude/Codex; its oracle
  gate and *both* loop drivers work under Copilot (the loop driver via
  per-iteration `copilot -p`; the goal driver via Autopilot's caps + final oracle)
  rather than silently no-op'ing.
- A servo-scaffolded target that commits Copilot config (`.github/`) has it
  picked up by Copilot's cloud agent + code review — a downstream scaffold-time
  benefit, distinct from the installed `hosts/copilot/` plugin package this ADR
  builds.

**Becomes harder:**
- A third generated package to drift-guard, version, and release.
- The hook + execution-primitive translation must be re-validated as Copilot's
  surface evolves (the guide warns behavior changes quickly).

**Invariants:**
- Repository root stays canonical source; `hosts/copilot/` is drift-guarded
  build output; Claude/Codex output byte-unchanged.
- **The committed artifact is an installed *plugin package* under `hosts/copilot/`**
  (Agent-Plugins-1.0: `plugin.json` + `skills/` + `com.github.copilot/{agents,hooks}`),
  **not** repo-root `.github/`. Rendering into the repository root would collide
  with ADR-0028's root-is-canonical-source invariant; repo-native `.github/`
  discovery (`.github/skills`, `.github/agents`, `.github/hooks`,
  `.github/copilot-instructions.md`) is a *scaffolded-target* concern, orthogonal
  to this host package.
- The render layer enforces Copilot loader limits + schema.
- Every servo hook and Claude-specific primitive is mapped or recorded as
  residual — enumerated over the source set, never silently dropped or
  mechanically renamed.

## Assumptions

<!-- Grounding: live `copilot` CLI 1.0.84-8 probe during frame-critique, plus
     Adobe's migration guide + terminology map (read 2026-09-15). Spec 028-01
     records the evidence (commands + output) formally. -->

- **Plugin layout (Agent Plugins 1.0):** a `hosts/copilot/` package presents
  `plugin.json` (with `$schema:
  https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`), `skills/<name>/SKILL.md`,
  and `com.github.copilot/{agents/<name>.agent.md, hooks/hooks.json}` — no
  `mcp.json` (servo ships no MCP config). Confirmed from GitHub's plugin docs +
  `copilot plugin install --help`; the exact marketplace-descriptor field set is
  re-checked in 028-01 (shared unknown with jig spec 113-01).
- **Autopilot has no oracle-gated stop** (verified: only `--max-autopilot-continues`
  / `--max-ai-credits`). Load-bearing consequence already absorbed in the mapping
  above — the loop driver ports without Autopilot; the goal driver's cap+final
  model fits Autopilot's caps. 028-01/05 validate the goal-driver fidelity.
- Mapping `copilot -p --agent runner` presupposes the `runner` agent renders as a
  Copilot agent (depends on the agent-rendering slice, 028-03).

## Kill criteria

- Adobe reverses/postpones the Claude Code disablement → the *priority* drops;
  the parity case for a third host stands regardless (parity, not deadline, is the
  justification).
- `/plugin` cannot install servo's package and no `.github/`-native path works →
  rethink the package shape (shared unknown with jig spec 113-01).
- The goal driver's `/goal`→Autopilot mapping proves infidelitous under live test
  (e.g. Autopilot cannot honor servo's outer caps + final oracle check) → the
  **goal driver** stays Claude-only under Copilot, documented as residual; the
  **loop driver** still ports via per-iteration `copilot -p`, and the eval/oracle
  skills port regardless.

## Open questions

- Exact Copilot plugin/marketplace-descriptor field set for `/plugin` install
  (shared with jig spec 113-01; resolved to the Agent-Plugins-1.0 layout above,
  descriptor specifics confirmed in 028-01).
- Which servo hooks/primitives, if any, have **no** Copilot equivalent (the
  enumerated inventory is a 028-04 deliverable). On current evidence the oracle
  `Stop`→`agentStop` and both loop drivers port; the residual set may be empty.
