---
status: DONE
dependencies: [032-02]
last_verified: 2026-09-18
# arch_review: true  # introduces the hook-protocol translation layer
---

## Slice 032-04 — hooks

**Goal:** servo's oracle gate works under Copilot. servo's Copilot **plugin
package is hook-free** (source `hooks/` is empty); its one hook — the oracle
`Stop` — is installed **target-side** by the `oracle-hook` skill. So this slice
teaches `oracle-hook` to install a Copilot **`agentStop`** hook (via a ported
`copilot_hook_adapter.py`) when scaffolding a Copilot target, with the one-entry
mapped-or-unmappable inventory recorded.

**DoR:**
- ✅ 032-02 done (renderer + skeleton; `_render_copilot_skill` + package shape).
- ✅ 032-01 recorded the Copilot hook JSON schema, the `Stop`→`agentStop` event +
  identical `{decision,reason}` output, and the adapter payload-reshaping need.

**Acceptance Criteria:**

1. **Ported adapter (`copilot_hook_adapter.py`).** servo ships a
   `copilot_hook_adapter.py` (ported from jig — **stdin-reshaping half only**:
   re-shape Copilot camelCase stdin `sessionId`/`stop_hook_active`/… into the
   snake_case servo's `meta-judge.sh` reads, export `CLAUDE_PROJECT_DIR` from
   `cwd`/`workingDirectory`, exec the target script, forward its **stdout**; **no**
   SessionStart root-publisher half). **Advisory posture (jig-faithful):** servo's
   oracle hook is advisory — its gate decision travels in the child's stdout
   `{"decision":"block","reason":…}` body, never in the exit code — so the adapter
   **always exits 0** (a Stop hook must never trap the session; forwarding a
   non-zero child exit is not done). It lives as an `oracle-hook` skill resource
   (installed into a target), not a plugin hook. A test drives synthetic Copilot
   `agentStop` stdin through it and asserts the reshaped payload, the forwarded
   stdout decision, and the always-0 advisory exit even when the child exits
   non-zero.
2. **`oracle-hook` installs an `agentStop` hook for a Copilot target.**
   `oracle-hook/hook.py` gains a Copilot mode: instead of a Claude `Stop` entry in
   `.claude/settings.json`, it writes a `.github/hooks/*.json` (flat schema
   `{version:1,hooks:{agentStop:[{type:"command",bash:"…copilot_hook_adapter.py Stop \"…meta-judge.sh\"",timeoutSec?}]}}`)
   + installs the adapter + `meta-judge.sh` into the target. `install`/`uninstall`
   remain idempotent + backed up (existing 004-03/04 contract). A test asserts the
   Copilot-target install emits the `agentStop` JSON and reverses cleanly.
3. **Mapped-or-unmappable inventory (invariant).** An enumerated inventory over
   servo's hook set is recorded (in `docs/architecture.md`): today the single
   entry `Stop→agentStop` (mapped, identical decision vocab), residual set empty.
   No hook silently dropped or mechanically renamed. A test/assert enumerates the
   source hook set so a future added hook forces an inventory entry.
4. **Host selection.** `oracle-hook` chooses Claude `Stop` vs Copilot `agentStop`
   from the target's host (Copilot target detected by `.github/` config / an
   explicit flag), defaulting to Claude for existing targets (no behavior change
   for Claude users). Live `agentStop` firing under headless `copilot -p` is a
   known non-observable (jig 113-08) → verified via the adapter unit test + a
   static install check; live firing recorded as a residual.

**DoD:**
- [x] All ACs pass; full suite green (venv pytest); new tests fail when the feature is removed.
- [x] Adapter drift-pin test (reverse tool-name map / event map) if servo carries maps.
- [x] Inventory in `docs/architecture.md`; residual (live-firing) cross-linked to refinement-todo.
- [x] Reviewed by `reviewer` subagent (compliance + craft + arch) — PASS; evidence in `reviews/slice-04-{compliance,craft,arch}.md`. Finding 1 (advisory exit) resolved: adapter now always exits 0 (jig-faithful advisory posture) so a non-zero meta-judge exit can never trap the session; the gate decision is stdout-only. Finding 2 (uninstall whole-file unlink drops user top-level keys) accepted as low-risk: `servo-oracle.json` is servo-owned and a single backup is taken before mutation.
- [x] Deviation log + reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice servo's oracle gate installs
+ (statically) works for a Copilot target, or the residual is documented.

## Deviation log

**Slice 032-04 (hooks) — what built, AC→test mapping, deviations, residuals.**
Implemented via TDD (failing tests first, then implementation, then green) in the
`interesting-noyce-2b8f83` worktree. Tree left dirty (not committed), per task.

### What built

1. **Ported adapter `skills/oracle-hook/copilot_hook_adapter.py`** (new) — jig's
   `copilot_hook_adapter.py` stdin-reshaping half only: reshapes Copilot camelCase
   `agentStop` stdin → snake_case (`sessionId`→`session_id`,
   `transcriptPath`→`transcript_path`, `stop_hook_active` passthrough,
   `hook_event_name` from argv); exports `CLAUDE_PROJECT_DIR` from the payload's
   `cwd` (fallback `workingDirectory`); execs the target script (`bash` for `.sh`,
   `python3` for `.py`); forwards stdout + exit code **verbatim**. Fail-open
   throughout (a `Stop` hook must never trap the session): translation errors
   forward raw bytes; a too-few-args invocation, a missing target script, or a
   spawn exception all return exit 0. **Not ported** (servo is hook-free): jig's
   SessionStart root-publisher half (`merge_root_context`) and the enforcing
   (`--enforce`/`permissionDecision`) mode.
2. **`skills/oracle-hook/hook.py` Copilot mode** — added `--host {claude,copilot}`
   (default `claude`, zero change for existing installs). `--host copilot`:
   `install` writes `<target>/.github/hooks/servo-oracle.json`
   (`{version:1,hooks:{agentStop:[{type:"command",bash:"python3 .servo/hooks/copilot_hook_adapter.py Stop \".servo/hooks/meta-judge.sh\"",timeoutSec}]}}`)
   and installs the adapter + `meta-judge.sh` into `.servo/hooks/`; `uninstall`
   reverses (marker-matched removal, single backup, scripts left on disk, dedicated
   `servo-oracle.json` removed when emptied); `status`/report recognizes the
   Copilot install. Idempotent-merge + single-backup + stable-marker mirror the
   Claude 004-03/04 contract. Claude path unchanged.
3. **Inventory** — `docs/architecture.md` gained "Copilot host hook inventory
   (mapped-or-unmappable)": enumerated `{Stop→agentStop}` (mapped, identical
   `{decision,reason}`), residual set empty; source of truth is `hook.py`'s
   `CLAUDE_TO_COPILOT_HOOK_EVENTS` + `COPILOT_HOOK_RESIDUAL`, pinned by a test.
4. **Host packages regenerated** (`scripts/build_host_packages.py`); `--check`
   clean. The adapter ships to all three hosts (byte-identical; inert for
   Claude/Codex). Only oracle-hook (SKILL.md + hook.py) + the new adapter changed
   under `hosts/`; no other skill/agent perturbed.
5. Supporting: `.claude-plugin/install-contract.json` lists the adapter as an
   oracle-hook runtime file; `docs/refinement-todo.md` records the live-firing
   residual; `skills/oracle-hook/SKILL.md` documents `--host copilot`.

### AC → test mapping

- **AC1 (ported adapter)** — `skills/oracle-hook/test_copilot_hook_adapter.py`:
  `TranslatePayloadTests` (field reshaping + fail-open), `ProjectDirFromPayloadTests`
  (`cwd`/`workingDirectory`), `AdapterMainTests` (subprocess in front of a fake
  target: `CLAUDE_PROJECT_DIR` exported from `cwd`, `stop_hook_active` reaches the
  child, stdout + exit code forwarded verbatim, block body preserved, fail-open on
  missing/too-few-args), `InterpreterSelectionTests`.
- **AC2 (Copilot install)** — `test_hook.py::CopilotInstallTests` (emits `agentStop`
  JSON with adapter-wrapped bash; installs adapter + meta-judge; idempotent; backup;
  refuses unscaffolded) + `CopilotUninstallStatusTests` (uninstall reverses; leaves
  scripts; backup; idempotent; status states).
- **AC3 (inventory)** — `test_hook.py::HookInventoryTests` (map, residual empty,
  install-uses-mapped-event, full-set enumeration drift-pin, architecture.md grep).
- **AC4 (host selection)** — `test_hook.py::ClaudePathUnchangedByHostFlagTests`
  (default host writes only the Claude `Stop` entry, no Copilot artifacts; explicit
  `--host claude` matches default). Live-firing recorded as residual.

Mutation-verified: the CLAUDE_PROJECT_DIR-from-cwd export, `stop_hook_active`
passthrough, exit-code forwarding, servo-marker identification, backup-before-mutate,
and the inventory drift-pin each fail the relevant test when broken (recorded in the
implementer run; reverted after).

### Deviations from the spec

- **Reverse tool-name map not ported (DoD bullet 2 satisfied via the *event* map).**
  jig's adapter carries `_COPILOT_TO_CLAUDE_TOOL_NAME` because jig has tool-matched
  (`preToolUse`/`postToolUse`) hooks. servo's only hook is `Stop`→`agentStop`, which
  has **no tool fields** (spike 032-01), so the adapter ports no tool-name map — it
  would be untethered dead code. The map servo *does* carry is the **event** map
  (`Stop→agentStop`), drift-pinned by `HookInventoryTests`. This matches the DoD's
  conditional "…if servo carries maps" and the ADR's naming of the reshaped fields
  (`sessionId`/`transcriptPath`/…, not tool fields).
- **`project_dir_from_payload` accepts `cwd` OR `workingDirectory`** (jig reads only
  `workingDirectory`). servo's `agentStop` stdin uses `cwd` (spike 032-01), so `cwd`
  is preferred with `workingDirectory` as a faithful fallback.
- **No `--enforce` mode** ported — servo has no enforcing (deny) hook; the `Stop`
  hook expresses its decision in stdout, covered by a single verbatim-forward path.
- **Fail-open uses a pre-spawn existence check** for the target script: a missing
  meta-judge would make `bash` exit 127, which for a `Stop` hook could read as a
  block; the adapter returns 0 instead (packaging error must not trap the session),
  while a *present* script's exit code is forwarded verbatim.
- **`servo-oracle.json` is removed on uninstall when emptied** (vs the Claude path
  leaving the user's `settings.json`) — it is servo's own dedicated file, so an empty
  `{version,hooks:{}}` husk would be detritus; any co-located non-servo hook events
  are preserved.
- **Touched `install-contract.json` + `SKILL.md`** (beyond the 4 build items): the
  adapter is a required runtime resource, so the contract lists it and the skill
  documents the new `--host copilot` surface. In-scope for the oracle-hook skill.

### Residuals

- **Live `agentStop` firing under headless `copilot -p` is not observable**
  (jig 113-08). Verified statically (emitted-JSON + adapter unit test); recorded in
  `docs/refinement-todo.md` and cross-linked from the architecture.md inventory. No
  live `copilot -p` run was attempted (per task).
- The meta-judge's baked `gate.py` path under Copilot falls back to servo's absolute
  path (no `.claude/`-vendored gate on a Copilot target) — orthogonal pre-existing
  gate-portability concern (ADR-0008 vendored gate), not in this slice's scope.
