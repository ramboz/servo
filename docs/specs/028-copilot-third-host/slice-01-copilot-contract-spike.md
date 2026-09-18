---
status: DONE
kind: spike
dependencies: [adr-0034]
last_verified: 2026-09-18
---

## Slice 028-01 — copilot-contract-spike

**Goal:** Lock the Copilot contract and servo's execution-primitive mappings so
028-02..06 commit to a verified shape. Because **jig shipped its Copilot host
first** (ADR-0061 / spec 113 on jig `main`), most of the contract is no longer an
unknown to discover — it is a shipped artifact to *confirm* and port. This spike
confirms jig's shipped shape against a live `copilot` session and records servo's
own facts (corpus, drivers, target-side hook).

**Time-box:** 1 day.

### Findings (grounded)

**Environment:** `copilot` CLI **1.0.86-2** (also probed 1.0.84-8), `claude` 2.1.x.
jig's shipped package read at `/Users/ramboz/Projects/misc/jig` (`main`).

1. **Contract (confirmed against jig's shipped `hosts/copilot/` + live CLI).**
   - **Layout:** `hosts/copilot/.plugin/plugin.json` (legacy manifest) + components
     under `.github/{skills,agents,scripts,templates}` (jig also ships
     `.github/hooks/` — servo will not; see finding 4). Install: repo-subdir
     `copilot plugin install <owner/repo>:hosts/copilot`, or a repo-root
     `.github/plugin/marketplace.json` (`"source":"./hosts/copilot"`) +
     `copilot plugin marketplace add` / `plugin install jig@jig`.
   - **Manifest fields** (`copilot plugin install --help` + jig's shipped manifest):
     `name`, `version`, `description`, and component-path fields `skills`,
     `agents`, `hooks` pointing into `.github/` (required *because* components sit
     under `.github/`, not Copilot's legacy defaults). servo omits `hooks` (ships
     none).
   - **Skill loader:** rejects a `name:` containing `:` and a `description:` field
     >1024 chars. Discovery roots: `.github/skills/`, `.agents/skills/`,
     `.claude/skills/`.
   - **Agents:** `.github/agents/<name>.agent.md`; frontmatter `description`
     (required) + optional `name`/`tools`/`model`/`user-invocable`; tools mapped
     Claude→Copilot (`Read→view`, `Glob→glob`, `Grep→grep`, `Write→create`,
     `Edit→edit`, `Bash→bash`). No `model:` (neutrality).
   - **Hook JSON schema** (flat, per jig 113-05): `{ "version":1, "hooks":
     {"<camelCaseEvent>":[ {"matcher"?,"type":"command","bash":"…","timeoutSec"?} ]}}`.
     14 events; `Stop`→`agentStop`; `preToolUse.permissionDecision ∈ {allow,deny,ask}`.
   - **Plugin-root:** Copilot exposes **no** plugin-root env var in skill-body /
     fresh-shell context (jig bug 036). jig ships a standalone `jig_root.py`
     locator and injects a fresh-shell locator one-liner into skill root-notes.
2. **`claude -p`→`copilot -p -s` (verified live, AC4).** `copilot -p "<prompt>" -s
   --allow-all-tools` runs headless, exit 0, prints only the response.
   Non-interactive tool use **requires** `--allow-all-tools` (env `COPILOT_ALLOW_ALL`)
   or `--allow-tool` — Copilot's analog of the ADR-0033 permission wall.
   `--agent <name>` is accepted. `--output-format json` emits a **JSONL** event
   stream (`{type,data,id,timestamp,ephemeral}`; filter `ephemeral:true`).
   `--usage-output-file` writes `{totalPremiumRequestCost, totalNanoAiu,
   tokenDetails, codeChanges:{filesModifiedCount,linesAdded,filesModified[]}, …}` —
   a native cost signal **and** an edit signal (`filesModifiedCount==0` ⇒ no edits),
   which maps servo's cost-ceiling and the ADR-0033/0037 edit-permission signal.
3. **`Stop`→`agentStop` (AC2).** Copilot `agentStop` stdin
   `{sessionId,timestamp,cwd,transcriptPath,stopReason,stop_hook_active}`; to
   block/continue emit `{"decision":"block","reason":"…"}` (reason → next prompt) —
   **identical** decision vocab to Claude's `Stop`. Payload differs (camelCase +
   snake_case `stop_hook_active`); jig's `copilot_hook_adapter.py` re-shapes it.
   servo's oracle `meta-judge.sh` reads `hook_event_name`/`stop_hook_active`, so the
   adapter's snake_case reshaping covers it. Live *firing* of a repo hook under
   `copilot -p` is **not reliably observable headless** (jig 113-08 finding) →
   package verification is a static validator; live firing recorded as residual.
4. **Autopilot oracle-gate (AC3 — load-bearing for 028-05).** `--autopilot` /
   `--mode autopilot` exists but is bounded **only** by `--max-autopilot-continues`
   (default 5) + `--max-ai-credits` — **no oracle/eval-gated stop.** Consequence
   (per ADR-0034): servo's **loop driver** is self-driving (Python per-iteration
   gate) and maps to per-iteration `copilot -p -s --agent runner --allow-all-tools`
   — it does not need Autopilot. servo's **goal driver**'s per-turn oracle gate maps
   via the target-side `agentStop` oracle hook (block-while-failing); whether it
   fully reconstructs under Autopilot is validated in 028-05, with the loop-driver
   external-gate path as the honest fallback.
5. **servo-specific facts.** 12 skills; **9 carry `name: servo:<skill>` AND have a
   `description:` >1024** (same 9), so servo must **strip `servo:`** (unlike jig,
   which asserts `:`-free) and apply jig's `loader_safe_description`. **10 skills**
   reference `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/<helper>.py` (uniform shape) →
   rewrite to `$SERVO_ROOT/…` (bug 036). Agents: `runner`, `judge`. servo ships
   **no plugin-level hooks** (`hooks/` is `.gitkeep` only); its one hook (oracle
   `Stop`) is installed **target-side** by `oracle-hook/hook.py`, so its Copilot
   `agentStop` variant + the adapter ship as `oracle-hook` **skill resources**, not
   plugin hooks. No `.mcp.json`.

### Outcome

**028-02..06 unblocked** against jig's shipped, confirmed shape. ADR-0034 open
questions resolved: manifest = jig's legacy shape minus `hooks`; Autopilot has no
oracle gate (loop ports via per-iter `copilot -p`, goal via `agentStop`); no
mapping failed → no ADR amendment. servo diverges from jig only where its surface
differs (strip `servo:`; hook-free plugin; loop.py). The 3 jig post-ship bugs
(034 scaffold-defaults, 035 marketplace-source, 036 `$SERVO_ROOT` path) are
pre-empted from 028-02.

**DoR:**
- ✅ ADR-0034 Accepted.
- ✅ Live `copilot` CLI 1.0.86 + jig's shipped `hosts/copilot/` as the reference.

**Acceptance Criteria:** 1 ✅ (contract confirmed vs jig + live CLI) · 2 ✅
(`Stop`→`agentStop`, live-firing residual recorded) · 3 ✅ (Autopilot no
oracle-gate) · 4 ✅ (`copilot -p -s` exercised) · 5 ✅ (open questions
dispositioned, no amendment).

**DoD:**
- [x] Findings filled with commands + observed output (grounding).
- [x] Outcome set; 028-02..06 ACs updated to the verified jig-aligned shape.
- [x] `docs/refinement-todo.md`: live-hook-firing-under-`copilot -p` residual +
      Autopilot-goal-driver-fidelity carried to 028-05 (recorded at close-out).

**Anti-horizontal-phasing check:** Exempt — `kind: spike`. Unblocks 028-02..06.
