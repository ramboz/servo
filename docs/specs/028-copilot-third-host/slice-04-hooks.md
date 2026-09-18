---
status: IN_PROGRESS
dependencies: [028-02]
last_verified:
# arch_review: true  # introduces the hook-protocol translation layer
---

## Slice 028-04 — hooks

**Goal:** servo's oracle gate works under Copilot. servo's Copilot **plugin
package is hook-free** (source `hooks/` is empty); its one hook — the oracle
`Stop` — is installed **target-side** by the `oracle-hook` skill. So this slice
teaches `oracle-hook` to install a Copilot **`agentStop`** hook (via a ported
`copilot_hook_adapter.py`) when scaffolding a Copilot target, with the one-entry
mapped-or-unmappable inventory recorded.

**DoR:**
- ✅ 028-02 done (renderer + skeleton; `_render_copilot_skill` + package shape).
- ✅ 028-01 recorded the Copilot hook JSON schema, the `Stop`→`agentStop` event +
  identical `{decision,reason}` output, and the adapter payload-reshaping need.

**Acceptance Criteria:**

1. **Ported adapter (`copilot_hook_adapter.py`).** servo ships a
   `copilot_hook_adapter.py` (ported from jig — **stdin-reshaping half only**:
   re-shape Copilot camelCase stdin `sessionId`/`stop_hook_active`/… into the
   snake_case servo's `meta-judge.sh` reads, export `CLAUDE_PROJECT_DIR` from
   `workingDirectory`, exec the target script, forward exit/stdout; **no**
   SessionStart root-publisher half). It lives as an `oracle-hook` skill resource
   (installed into a target), not a plugin hook. A test drives synthetic Copilot
   `agentStop` stdin through it and asserts the reshaped payload + preserved exit.
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
- [ ] All ACs pass; full suite green (venv pytest); new tests fail when the feature is removed.
- [ ] Adapter drift-pin test (reverse tool-name map / event map) if servo carries maps.
- [ ] Inventory in `docs/architecture.md`; residual (live-firing) cross-linked to refinement-todo.
- [ ] Reviewed by `reviewer` subagent (compliance + craft + arch).
- [ ] Deviation log + reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice servo's oracle gate installs
+ (statically) works for a Copilot target, or the residual is documented.
