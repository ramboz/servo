---
status: Proposed
dependencies: ["adr-0028-committed-dual-host-plugin-packages"]
last_verified: 2026-09-18
frame_review: true
---

# ADR-0034: GitHub Copilot CLI as a third committed host

## Status

Proposed (2026-09-15; re-aligned to jig's shipped keystone 2026-09-18)

> Filed as part of the cross-repo GitHub Copilot migration. **jig ADR-0061 / spec
> 113 are now SHIPPED** (Accepted and merged to jig `main`; committed
> `hosts/copilot/`, 9 slices, plus post-ship fixes for scaffold defaults,
> marketplace-source schema, and skill-helper paths). jig ADR-0061 explicitly
> names servo's adoption as a **sibling decision that mirrors this pattern**, so
> this ADR mirrors jig's final, shipped layout and mechanism rather than an
> independently-derived shape. servo's own load-bearing facts (corpus exposure,
> loop/goal-driver mapping) were additionally re-verified against a live `copilot`
> CLI (1.0.84-8). Owner runs frame-critique + accept.

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
  installs Claude-format plugins (jig's shipped package layout — see Assumptions).
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
   chars (verified max 726). Both fixes, not just the name-strip: a namespace-only
   render would ship 9 skills whose descriptions silently fail Copilot's loader,
   violating this ADR's own "degrade *visibly*, never silently" invariant. **Note
   the Codex renderer *drops* description paragraphs 2+** (it skips the remainder,
   not relocating them), relying on the body already duplicating that detail; to
   honor the same invariant here, the Copilot renderer must **append any dropped
   description paragraphs to the skill body** so no routing/trigger nuance is
   silently lost (a fidelity refinement over Codex, tested in 028-02).
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
host renderer + committed `hosts/copilot/` package that renders into Copilot's
**`.github/` layout** (mirroring jig's shipped `hosts/copilot/`), drift guard, and
a host-explicit release archive — the render layer absorbing loader limits, hook
translation, and the execution-primitive mapping.
- **Pros:** symmetric with Claude/Codex; honors `.github/` as Copilot's durable
  config home (instructions, skills, agents, hooks, settings — the same home
  Copilot's cloud agent + code review read); keeps servo's guardrails/oracles
  working under Copilot; extends ADR-0028 + spec 022's release parity to tri-host
  **following jig ADR-0061 / spec 113's shipped, proven pattern** (jig-first,
  servo mirrors).
- **Cons:** a third package to build/drift-guard/version/release; the hook +
  execution-primitive translation is real engineering and must be validated
  against a live Copilot session.

### Option D: A separate Copilot-only artifact
- **Cons:** source divergence + double maintenance — what ADR-0028's
  single-source model prevents. Rejected.

## Recommended Decision

Adopt **Option C**, mirroring jig's shipped `hosts/copilot/`. servo's builder
gains a Copilot arm + host renderer producing this committed layout (the same
shape jig spec 113 ships):

```text
repo root/
  .github/plugin/marketplace.json   Copilot marketplace descriptor: source "./hosts/copilot" (bug 035)
  hosts/copilot/
    .plugin/plugin.json             legacy manifest: name/version/description + component paths
                                    skills=".github/skills" agents=".github/agents" hooks=".github/hooks/hooks.json"
    .github/
      skills/<name>/SKILL.md        loader-safe (name `:`-free, description ≤1024); $SERVO_ROOT paths
      agents/<name>.agent.md        rendered Copilot custom agents (model-neutral; tools mapped)
      hooks/*.json + hooks.json     (only if servo ships plugin hooks — see below) via the adapter
      hooks/scripts/                copilot_hook_adapter.py, servo_root helpers (if hooks shipped)
      scripts/servo_root.py         $SERVO_ROOT fresh-shell locator (bug 036)
      templates/                    UNRENDERED (canonical ${CLAUDE_PLUGIN_ROOT} intact — bug 036)
```

The renderer (mirroring jig's `build_copilot_plugin.py` + `CopilotScaffoldRenderer`,
ported as functions into servo's function-based builder):

- renders skills loader-safe: **strip the `servo:` invocation namespace from the
  loaded `name:`** (servo's source names carry it, unlike jig's — then assert the
  result is `:`-free), and enforce the ≤1024 `description:` limit with jig's
  **keep-or-truncate-and-preserve** rule (keep the full description byte-for-byte
  if ≤1024; else truncate the frontmatter value at a word boundary + suffix **and
  append the full original description to the SKILL.md body** as a note, so no
  routing/trigger text is lost). This is servo's 9-of-12 over-limit skills' fix;
  it is a *different* rule from `_render_codex_skill`'s first-paragraph collapse,
  so it is a separate `_render_copilot_skill`.
- **rewrites plugin-mode helper paths (bug 036):** servo's 10 skills document
  `${CLAUDE_PLUGIN_ROOT}/skills/.../*.py` — a path that does **not** resolve under
  Copilot plugin-mode (Copilot exposes no plugin-root env var). The renderer
  rewrites them to `$SERVO_ROOT/skills/.../*.py`, ships a `servo_root.py`
  fresh-shell locator, publishes `$SERVO_ROOT` via a `SessionStart` carrier, and
  injects a root-resolution note into each skill that uses the var. Templates ship
  **unrendered** (canonical `${CLAUDE_PLUGIN_ROOT}` intact). (servo ships no
  `.mcp.json`, so no MCP config is rendered; the empty-set is recorded, not
  silently skipped.)
- **maps servo's hooks via the adapter mechanism** (`copilot_hook_adapter.py`,
  ported near-verbatim from jig): Claude PascalCase → Copilot camelCase events
  (notably `Stop`→`agentStop`), the flat `{version,hooks:{<event>:[{matcher?,type,
  bash,timeoutSec?}]}}` schema, and camelCase→snake_case payload re-shaping so the
  hook script reads its expected fields. **servo ships no plugin-level hooks
  today** (source `hooks/` is empty); its one hook — the oracle `Stop` — is
  installed *target-side* by the `oracle-hook` skill, so the translation teaches
  that skill to emit an `agentStop` hook (+ the adapter) for a Copilot target. A
  **mapped-or-explicitly-unmappable inventory** enumerates the source set so none
  is silently dropped; today that set is `{Stop→agentStop}` and the residual is
  empty. (The permissions floor is likewise an **enforcing `preToolUse` hook** if
  servo needs one — Copilot has no persistent tool-deny setting to write — not a
  `settings.json`.)
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
- servo's **goal driver** (ADR-0008) delegates *continuation* to the host's
  native long-running mode but **keeps oracle authority via a per-turn gate** —
  ADR-0008's explicit load-bearing invariant: the loop body prints the oracle
  verdict into the transcript every turn, the host's stopping-judge stops the turn
  the oracle passes, and the meta-judge `Stop` hook blocks a premature stop while
  the oracle fails. Copilot **Autopilot** (`--autopilot`, bounded by
  `--max-autopilot-continues` / `--max-ai-credits`) has **no oracle-gated stop** —
  it self-stops when it judges the task complete, bounded by those caps, with no
  `/goal`-style transcript-judge stop-on-oracle-pass (verified live). So the goal
  driver's gate does **not** map to Autopilot's caps as-is (mapping it that way
  would silently drop the per-turn gate — the failure this ADR's honesty invariant
  forbids). The gate's *block-while-failing* half reconstructs via the
  `Stop`→`agentStop` hook (the same 028-04 translation; `agentStop`'s
  `{decision:block,reason}` re-drives exactly as the meta-judge does); whether a
  per-continuation `agentStop` can fully reconstruct the per-turn gate under
  Autopilot is a **028-01/05 validation item**. If it cannot, the goal driver
  under Copilot **falls back to the loop driver's external-gate path** (servo
  drives per-iteration `copilot -p` and gates in its own Python — a servo feature
  that ports regardless), or is recorded as a Claude-only residual. Either way the
  user keeps oracle-gated autonomy; nothing degrades silently.
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
  gate and the **loop driver** work under Copilot (external Python gate +
  per-iteration `copilot -p`) rather than silently no-op'ing. The **goal driver**'s
  per-turn-gated autonomy ports iff a per-continuation `agentStop` gate
  reconstructs it under Autopilot (028-01/05); if not, Copilot users get the loop
  driver's equivalent oracle-gated autonomy, or the goal driver is a documented
  Claude-only residual — never a silently un-gated run.
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
  build output, never hand-edited; Claude/Codex output byte-unchanged.
- **The committed artifact is `hosts/copilot/`, whose *internal* structure is
  Copilot's `.github/` layout** (`.github/{skills/, agents/*.agent.md, scripts/,
  templates/}`, plus `.github/hooks/` only if servo ships plugin hooks) and a
  `.plugin/plugin.json` legacy manifest with component-path fields — mirroring
  jig's shipped package. This `.github/` tree lives **inside the `hosts/copilot/`
  build-output directory**, so it does not touch (or collide with) the
  *repository-root* `.github/`; ADR-0028's root-is-canonical-source invariant is
  preserved. Following jig's shipped rulings, the package ships **no** pre-rendered
  `copilot-instructions.md` (a `/plugin` install must not impose instructions on
  the consuming repo; templates ship unrendered) and **no** `copilot/settings.json`
  (Copilot has no persistent tool-deny setting — a permissions floor, if needed,
  is an enforcing `preToolUse` hook). The repo-root `.github/plugin/marketplace.json`
  descriptor (`source: ./hosts/copilot`) is the install entry point (bug 035).
- The render layer enforces Copilot loader limits + schema.
- Every servo hook and Claude-specific primitive is mapped or recorded as
  residual — enumerated over the source set, never silently dropped or
  mechanically renamed.

## Assumptions

<!-- Grounding: live `copilot` CLI 1.0.84-8 probe during frame-critique, plus
     Adobe's migration guide + terminology map (read 2026-09-15). Spec 028-01
     records the evidence (commands + output) formally. -->

- **Package layout — mirrors jig's shipped `hosts/copilot/` (ADR-0061 / spec 113).**
  The committed package is `hosts/copilot/` with a **legacy** `.plugin/plugin.json`
  manifest carrying `name`/`version`/`description` **plus the three required
  component-path fields** (`skills: ".github/skills"`, `agents: ".github/agents"`,
  `hooks: ".github/hooks/hooks.json"` — required because components live under
  `.github/`, not Copilot's legacy defaults), and components under `.github/`:
  `skills/<name>/SKILL.md`, `agents/<name>.agent.md`, `scripts/servo_root.py`,
  `templates/` (unrendered), and `hooks/` only if servo ships plugin hooks. No
  `mcp.json` (servo ships no MCP config); no `copilot-instructions.md`; no
  `copilot/settings.json`. A repo-root `.github/plugin/marketplace.json`
  (`source: ./hosts/copilot`) is the marketplace entry point. This is no longer an
  open shape — it is the layout jig already ships; 028-01 confirms the exact field
  set against jig's package and a live `copilot plugin install`.
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
- A per-continuation `agentStop` hook cannot reconstruct the goal driver's
  **per-turn oracle-gated stop** under Autopilot (e.g. `agentStop` does not fire
  between Autopilot continuations, or cannot re-drive) → the goal driver under
  Copilot falls back to the **loop driver's external-gate path**, or is documented
  as a Claude-only residual; the loop driver and eval/oracle skills port regardless.

## Open questions

- Exact `.plugin/plugin.json` field set — **resolved by mirroring jig's shipped
  manifest**; 028-01 copies jig's field set and confirms against a live `copilot
  plugin install`. (jig's post-ship bug 035 fixed a marketplace-source-schema
  issue — servo inherits that fix rather than re-discovering it.)
- Which servo hooks/primitives, if any, have **no** Copilot equivalent (the
  enumerated inventory is a 028-04/05 deliverable). On current evidence the oracle
  `Stop`→`agentStop` and both loop drivers port; the residual set may be empty.
