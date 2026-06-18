---
status: DRAFT
last_verified:
---

# Architecture: servo

> Status: Draft — evolves as specs land.

## Shape

Servo is a Claude Code plugin in the same shape as [jig](https://github.com/ramboz/jig):

```
servo/
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       └── <helper>.py
├── agents/                 (deferred — runtime skills will populate)
├── hooks/                  (deferred — Spec 003 will populate)
├── templates/              (per-project artifacts copied into target)
├── scripts/                (verification, install helpers)
├── docs/
│   ├── product-vision.md
│   ├── architecture.md
│   ├── decisions/          (ADRs — deferred until first hard-to-reverse choice)
│   └── specs/
│       └── <NNN>-<name>/spec.md
├── README.md
└── LICENSE
```

## Install surfaces

Servo has two distinct install layers; conflating them is the easiest way to
ship a broken install:

| Layer | What is installed | Destination | Owner |
|---|---|---|---|
| **Servo runtime install** | Skills, agents, templates, scripts, descriptors | Plugin root, release zip, or `<target>/.claude/` | Servo |
| **Project oracle install** | `oracle.sh`, `.servo/install.json`, refinement notes | Target project root | Project |

The **project oracle install** is `/servo:scaffold-init` (spec 001) and is
covered by [Install manifest](#install-manifest) below. The **servo runtime
install** (spec 007) has three surfaces — plugin root, release zip, and
project-local scaffold — that are three projections of one data-driven
contract (`.claude-plugin/install-contract.json`) checked by one verifier
(`scripts/verify_install.py {plugin,zip,scaffold}`). `scripts/build_release_zip.py`
packages the deterministic archive and `scripts/scaffold_runtime.py` vendors
the `servo-`prefixed runtime into a target's `.claude/`. The single repo
verification command `scripts/verify_install_surfaces.sh` runs the plugin
verifier plus the install-surface test suites and is wired into CI on push and
pull request. See the README's "Installing servo" section for the
user-facing chooser.

## Skill split

Servo is **scaffolder-first, runtime second**. The runtime skills all presuppose artifacts the scaffolder dropped into the target.

| Skill | Role | Spec |
|---|---|---|
| `/servo:scaffold-init` | Probe → Q&A → tailored install of `oracle.sh` (+ optional agent-loop/hook/race stubs) | 001 |
| `/servo:quality-gate` | Runtime invocation of scaffolded `oracle.sh`; normalized exit codes | 002 |
| `/servo:agent-loop` | Headless iteration driver | 003 |
| `/servo:oracle-hook` | Claude Code hook installer | 004 |
| `/servo:variant-race` | N-worktree parallel race | future |
| `/servo:spec-oracle` | Compile a spec/slice into AC-mapped deterministic checks and an oracle overlay | 006 |
| `/servo:heartbeat` | Routine-triggered read-only discovery → triage inbox → oracle-gated dispatch (the scheduled **front-end**) | 011 |

## Project vs servo-core split

This is the load-bearing distinction. Servo ships **templates and orchestration**; the project owns **content and policy**.

| Project owns | Servo owns |
|---|---|
| `oracle.sh` content, weights, threshold | Template + signal-detection logic |
| Custom signal functions | `# SEED:` annotation convention |
| Domain-specific lint configs | Normalized exit codes |
| Spec-specific acceptance criteria policy, waivers, and residual judgment | AC classification helpers, check primitives, evidence schema |
| Prompt templates for loops | Loop driver, guardrail defaults |
| Cap + ceiling overrides | Defaults (max-iterations=5, cost-ceiling=$2, context-fill-threshold=0.75) |
| Hook event choice, retry phrasing | Hook script template, settings.json mutation + backup |
| Variation strategy, variant count | Worktree management, subagent spawning, scoring |
| The schedule (the Routine), what counts as an "actionable" finding, the heartbeat cost ceiling | Read-only discovery, the triage-inbox state spine, oracle-gated dispatch orchestration, whole-heartbeat ceiling enforcement |

## Tier model

Mirrors jig's tier-based scaffolding:

- **Tier 0** — `oracle.sh` only. Always installs. Composite score of whatever signals are detected.
- **Tier 1** — Tier 0 + agent-loop driver stub. Offered when the project has signals dense enough to make iteration meaningful (tests + lint + types, or similar).
- **Tier 2** — Tier 1 + hook installer + race driver + heartbeat. **Offered explicitly only.** These are higher-risk surfaces (mutates `settings.json`, races real worktrees, lets a *schedule* spawn loops) and should never auto-install.

## Signal detection

**Status:** implemented in slice 001-03 (`scaffold.py:detect_signals`).

Probe the target for:

- **Test framework** (pytest / vitest / jest / cargo / go) — prefer jig's `tdd.py detect` via subprocess if `${CLAUDE_PLUGIN_ROOT}/jig/skills/tdd-loop/tdd.py` exists, fall back to built-in detectors otherwise. Decision recorded in [ADR-0001](decisions/adr-0001-reuse-jig-test-detector.md).
- **Lint configs** — eslint (`.eslintrc*`, `eslint.config.{js,mjs}`, `package.json#eslintConfig`); ruff (`[tool.ruff]` in `pyproject.toml`, `ruff.toml`, `.ruff.toml`).
- **CI** — `.github/workflows/`, `.gitlab-ci.yml`, `.circleci/config.yml`.
- **Language** — coarse heuristic from highest-signal file (`pyproject.toml`/`*.py` → python, `package.json`/`*.ts`/`*.js` → javascript, `Cargo.toml` → rust, `go.mod` → go).
- **`oracle.sh` already at target root** → refuse install without `--force` (slice 001-01).
- **`.servo/install.json`** (servo's own manifest, like jig's `scaffold.json`).

Detected components drive which `score_<name>` fragments are spliced into the generated `oracle.sh`. Fragments live under `templates/components/<name>.sh.fragment`. A no-signal target gets a comment-only oracle that exits 2 with `no signals detected — populate # SEED: blocks manually`.

**Audit subcommand:** `scaffold.py detect <target>` prints the full detection payload as JSON (signals + components + per-component weights + which detector ran) without writing anything to disk. Useful for debugging or wizard-mode previews.

## Install manifest

After install, the target gets `.servo/install.json` with:

```json
{
  "servo_version": "0.1.0",
  "timestamp": "<ISO8601>",
  "installed_tier": "tier-0" | "tier-1" | "tier-2",
  "offered_tiers": [...],
  "signals": { "tests": true, "lint": false, "ci": false, "language": "python" },
  "components": ["pytest", "coverage"]
}
```

This is the analog of jig's `scaffold.json` and is what later runtime skills consult to know what was installed.

## Subagents

Servo ships two fresh agents — `runner.md` and `judge.md` — rather than reusing jig's `implementer.md` / `reviewer.md`. Reason: jig's subagent prompts assume **supervised** TDD (narration, clarifying questions, deferring ambiguous calls to the user). Servo's loops are **unattended** (every iteration costs money, no human watching, loop driver needs machine-parseable signals to decide whether to iterate again). The prompts diverge enough at the output-schema level that copy-and-rewrite is cleaner than parameterize-and-share. Architectural calls are *not* fresh — they reuse `jig:architect` directly per the filesystem-only-coupling pattern from ADR-0001, since ADRs are human-read documents in both projects and any format wrapping is post-hoc. Documented in [ADR-0003](decisions/adr-0003-fresh-subagent-roster.md).

| Servo agent | Jig analog | Why different |
|---|---|---|
| `runner` | `implementer` | Terse, no soliloquy, exit-non-zero on blocker |
| `judge` | `reviewer` | Machine-parseable verdict (PASS/FAIL/INCONCLUSIVE + score) |
| _(delegated)_ | `architect` | Reused via `claude --agent jig:architect`; output post-processed into servo's ADR shape |

Current state: both runner and judge are **placeholders**. Full prompts are authored alongside the specs that need them (spec 003 needs `runner` + `judge`; spec 005 reuses `judge`).

## Runtime artifacts

Runtime and spec-overlay skills produce these at the *target* project
(not in servo's plugin repo):

- `<target>/.servo/runs/<run-id>/state.json` — agent-loop per-run scoreboard (slice 003-04, [ADR-0004](decisions/adr-0004-session-state-file-format.md)). Atomically rewritten after every iteration via `.tmp + os.replace`. Schema: `state_schema_version`, `run_id`, `started_at`, `last_updated_at`, `target_path`, `prompt`, `current_session_id` (the Claude Code session id `claude -p --resume` consumes), `iteration_count`, `max_iterations`, `cost_ceiling_usd`, `cumulative_cost_usd`, `cumulative_input_tokens`, `cumulative_output_tokens`, `context_fill_threshold`, `last_context_fill_ratio`, `oracle_score_history`, `last_terminal_reason`, `claude_version`. Run-id shape: `YYYYMMDDTHHMMSS-XXXX` (15-char timestamp + 4-hex suffix); collision retry is bounded at 3 attempts. A `--background` detached run (slice 003-08) carries `detached: true` and writes the detached child's stdout/stderr to a sibling `background.log`; the parent pre-allocates the run-id and seeds `state.json`, the child rewrites it as it progresses.
- `<target>/.servo/hooks/meta-judge.sh` — the **meta-judge** `Stop` hook (spec 004, [ADR-0006](decisions/adr-0006-meta-judge-output-contract.md)). `/servo:oracle-hook install` copies it from `templates/meta-judge.sh.template` and registers a `hooks.Stop[]` entry in `<target>/.claude/settings.json` that points at it via `$CLAUDE_PROJECT_DIR`. **Install model:** `settings.json` is backed up to `settings.json.servo-bak` before the first mutation; the merge is non-clobbering (other top-level keys, hook events, and Stop entries survive); `uninstall` removes only servo's marker-matched entry and **leaves the script on disk** (it may be customized); `status` reports `installed` / `not_installed` / `inconsistent`; the closed exit contract is `0` ok / `2` env-error (no exit 1). **Decision table (per turn-stop):** `stop_hook_active` true (or indeterminate stdin) → silent; oracle `pass` → silent; oracle `below_threshold` → **block** with a composite/threshold (+`missing`) hint; oracle `env_error` / uninvocable gate → **fail open** with a `systemMessage` to the user (never a block, so it can't trap a live session) — nudging at most once per stop sequence. Block (v1 default) vs `additionalContext` soft-context is a project-owned knob; the project owns the script after install. The interactive inverse of `/servo:agent-loop`'s fail-closed brakes.
- `<target>/.claude/skills/servo-quality-gate/gate.py` — a **vendored, clone-portable copy** of servo's `gate.py`, written by the agent-loop driver's preflight (slice 003-07, [ADR-0008](decisions/adr-0008-loop-on-autonomy-primitives.md) V4). The goal/Routine driver runs the oracle through this relative path (and the meta-judge install — [`hook.py:_resolve_gate_py`](../skills/oracle-hook/hook.py) — already prefers it), so the oracle resolves *relative to `$CLAUDE_PROJECT_DIR`* after a clone instead of baking servo's absolute install path (which would fail open in a clone). Vendoring is idempotent — a byte-identical copy is left untouched; a stale or absent copy is (re)written. The loop (external-driver) path keeps using servo's own in-repo `gate.py`. (Untracked in the target by design — see the dirty-tree note below.)
- `<target>/.servo/races/<race-id>/` — per-variant scores and metadata from `/servo:variant-race`.
- `<target>/.servo/triage/inbox.jsonl` (+ a generated `inbox.md` view) — the **triage inbox** from `/servo:heartbeat` (spec 011): the scheduled-discovery state spine, schema governed by [ADR-0010](decisions/adr-0010-triage-inbox-schema.md) (reciprocal to [ADR-0004](decisions/adr-0004-session-state-file-format.md)). One JSONL record per finding, `schema_version: 2`, in three volatility classes: **immutable** (`finding_id` — a stable `sha256(...)[:16]` fingerprint, `source`, `provenance` `first_party`/`contributor`, `discovered_at` first-seen), **sticky** (`status` `open`/`tried`/`passed`/`skipped`, `attempts`, `outcome`), **volatile** (`title`, `detail`, `evidence`, `last_seen_at`, `actionable`, `actionable_reason`). Re-running `discover` **merges** by `finding_id` (preserve immutable+sticky, refresh volatile) rather than overwriting, so the next heartbeat resumes; a uniform retention rule evicts unseen `open` findings while retaining lifecycle-bearing (`tried`/`passed`/`skipped`) ones. A `fcntl.flock` on a separate persistent `.inbox.lock` guards a double-fired Routine. The read-only `discover` pass writes here and **nowhere else** in the target (atomic `.tmp` + `os.replace`); the read-only `heartbeat.py status` verb reads it back (human or `--json`); oracle-gated dispatch (011-03) records each candidate's `outcome` back to it.
- `<target>/.servo/dispatch/<finding_id>/` — per-candidate **dispatch worktree** from `/servo:heartbeat dispatch` (slice 011-03), beside `runs/` / `races/` / `triage/` under the git-ignored `.servo/`. This is the heartbeat's **one execution edge**: for each `actionable AND open` finding, `dispatch` runs a `gate.py <target> --json` oracle preflight (refuse-without-oracle refuses the whole pass, ADR-0002 taxonomy — Guardrail #3), then creates a **fresh linked git worktree** of the target at HEAD on a dedicated branch `servo/heartbeat/<finding_id>`, **provisions** the oracle into it (copies `oracle.sh` + all of `.servo/` *except* the volatile/recursive dirs `runs`/`races`/`triage`/`dispatch` — because `.servo/` is git-ignored the HEAD checkout carries neither the manifest nor any `.servo/`-resident oracle sidecars), **verifies** the provisioned worktree with `gate.py <worktree> --json` (an `exit 2` records a per-candidate env-error and skips — never scores a broken oracle), and dispatches `loop.py <worktree>` (spec 003) with an **untrusted-data-framed** prompt (discovered text is labelled, delimited DATA, never instructions — Guardrail #4; `loop.py` does not sanitize `--prompt`, so the dispatcher owns the framing). The loop's edits land only inside the worktree — the target's own working tree is **never** mutated. **Heartbeat composes the loop; the loop stays trigger-agnostic** (the spec-003 boundary): `loop.py` is invoked per candidate exactly as a human would invoke it, and the dispatch target is kept pluggable so `race.py` (spec 005) can slot in later. The outcome (`{run_id, oracle_status, oracle_composite, cost_usd, dispatched_at}` — the ADR-0010-reserved shape; `attempts += 1`; `status = passed` iff the loop's `final_oracle_status == pass`, else `tried`) is recorded back to `triage/inbox.jsonl` through 011-02's locked (`fcntl.flock`) atomic (`.tmp` + `os.replace`) merge. Dispatch is **serial** in v1 and forwards a **per-loop** `--cost-ceiling` (not a whole-pass ceiling — that is 011-04's `run` verb); the worktree is **retained** (v1) so a human can inspect/land the result (GC/retention is a deferred follow-up — see `docs/refinement-todo.md`). Closed `{0,2}` exit: `2` only on a pass-level env error (target missing/not-a-dir, refuse-without-oracle, unreadable/unsupported-schema inbox); `0` otherwise, including below-threshold loops (recorded `tried`) and per-candidate env-errors.
- `<target>/.servo/spec-oracles/<spec-id>/` — spec-specific evidence overlay from `/servo:spec-oracle` (specs 006-01..03). Contents: `plan.md` (human-reviewable AC→check map) and `checks.json` (machine plan) from the planner (006-01); `checks.py` (a self-contained copy of the stdlib check engine, 006-02) and `oracle.sh.fragment` (the generated `# SEED:start spec_oracle_<id>` / `# SEED:end spec_oracle_<id>` block) from the overlay compiler (006-03); and append-only `ledger.jsonl` (one JSONL evidence record per AC per run, stamped with a run `ts`). Install splices the fragment into `<target>/oracle.sh` as an ordinary component — a `score_spec_oracle_<id>` function plus a `COMPONENTS` entry — so `gate.py` / `loop.py` score it with **no special-casing**: the component returns the composite check score, or rc=2 if any check env-errors. The overlay is project-owned and reviewable before `/servo:agent-loop` consumes it; uninstall removes the component but keeps the artifacts. Before the loop may score it the overlay must be **approved**, and the installed component runs the engine with `--enforce-freeze` — see *Spec-oracle freeze & approval* below.

These paths are reserved now (in `.gitignore`) so later specs don't have to renegotiate them. Which driver writes the vendored `gate.py` (and when the loop runs at all) is decided by the agent-loop's **host-scope routing** — see the routing matrix under [Agent-loop guardrails](#host-scope-routing-spec-003-07).

## Spec-oracle freeze & approval (slice 006-04)

A generated spec-oracle is **draft** until explicitly approved. `/servo:spec-oracle approve` (`oracle_overlay.py approve`):

1. verifies the source spec still hashes to the value recorded at plan time — else it refuses (re-plan, don't approve);
2. runs each check's **negative control** — a spec-override that must turn the check *failing* — and refuses approval if any check cannot be made to fail (a check that can't fail would let the loop self-grade);
3. records `approval_status: approved`, sha256 hashes of `checks.py` + `oracle.sh.fragment` (`approved_artifacts`), and a content hash of the checks themselves (`approved_content_hash`).

The installed component runs `checks.py --enforce-freeze`, which refuses with **rc=2** (a distinct `reason` each) on: not-approved (`spec_oracle_unapproved`), changed source spec (`spec_oracle_stale`), modified generated artifact (`spec_oracle_artifact_modified`), or relaxed checks (`spec_oracle_plan_modified`). Bare `checks.py` (planning / inspection) does **not** enforce — only the installed overlay does, so authoring stays frictionless.

**Threat model.** The hashes are *tripwires for honest drift*: an iteration that incidentally edits the engine, the source spec, or the checks is caught and the oracle refuses rather than passing silently. They are not a sandbox — a runner that writes arbitrary files could rewrite both an artifact and its recorded hash. The defense against a *deliberately* self-rewriting runner is the `runner.md` constraint (it is told not to edit approved spec-oracle artifacts, and that doing so is self-grading) plus the human approval flow, consistent with [ADR-0001](decisions/adr-0001-reuse-jig-test-detector.md)'s filesystem-only trust model. v1 leniency: a check with no negative control is approved without a falsifiability proof — the planner does not yet auto-generate controls (see [refinement-todo](refinement-todo.md)).

## Quality-gate JSON contract

Spec 002 shipped `/servo:quality-gate` — the runtime wrapper around `<target>/oracle.sh` that specs 003 / 004 / 005 will all consume. The contract callers can rely on:

**Exit codes** — closed `{0, 1, 2}` set per [ADR-0002](decisions/adr-0002-gate-caller-contract.md). Unexpected oracle exits (signal kill, bash 126/127, app bug returning 99) remap to gate exit 2 with `reason=unexpected_exit code=<N>`.

**Default JSON payload** (`gate.py <target> --json`) — one line, keys always present unless noted:

```json
{
  "schema_version": 1,
  "exit_code": 0,
  "status": "pass" | "below_threshold" | "env_error",
  "composite": 0.95 | null,
  "threshold": 0.5 | null,
  "missing": [],
  "reason": "..." (optional, only on env_error),
  "code": 99 (optional, only on reason=unexpected_exit),
  "timeout_seconds": 1.0 (optional, only on reason=timeout),
  "raw": {"stdout": "...", "stderr": "..."} (optional, only with --verbose)
}
```

**Closed `reason` taxonomy** (all 11 codes; surfaced when `status="env_error"`):

| `reason` | When |
|---|---|
| `target_missing` | Target path doesn't exist |
| `target_not_directory` | Target exists but isn't a directory |
| `manifest_missing` | `<target>/.servo/install.json` absent |
| `manifest_malformed` | Manifest exists but isn't valid JSON |
| `manifest_invalid_key` | Manifest valid JSON but missing required key (`installed_tier` or `components`) |
| `oracle_missing` | `<target>/oracle.sh` absent (but manifest is present) |
| `oracle_not_executable` | `oracle.sh` exists but lacks the executable bit |
| `invocation_failed` | OS-level error invoking the oracle (rare) |
| `timeout` | Oracle exceeded `--timeout` (or env-var / 300s default) |
| `unexpected_exit` | Oracle exited with a code outside `{0, 1, 2}` |
| `unparseable_oracle_output` | Oracle exited 0 but produced no `composite=X threshold=Y` line |

**Audit JSON** (`gate.py audit <target> --json`) — emits the install manifest verbatim (no `schema_version` field; the manifest has its own schema versioning via `servo_version`). One-line JSON for shape consistency with the invocation `--json`.

**Timeout machinery** — default 300s (5 min), overridable via `--timeout <seconds>` flag or `SERVO_GATE_TIMEOUT` env var. Flag wins on conflict. `--timeout 0` disables the bound. Kill sequence: `SIGTERM` → 5s grace → `SIGKILL`, applied to the oracle's process group (`os.killpg`) so any backgrounded subprocesses are killed too.

**Stateless** — the gate writes nothing to disk. Per-iteration / per-variant persistence is the caller's responsibility (specs 003 / 005).

## Agent-loop guardrails

Spec 003 ships `/servo:agent-loop` — the headless iteration driver that subprocesses `claude -p --output-format json` against a target under hard guardrails. Each guardrail fails-closed (halt) rather than fails-open (keep burning budget); a user can fire-and-forget a loop and trust it will stop on its own.

| Guardrail | Mechanism | Default | Disable | Terminal reason |
|---|---|---|---|---|
| Iteration cap | Counted `for` loop | 5 | (no disable) | `max_iterations_reached` |
| Cumulative cost ceiling | Sum of `total_cost_usd` per iteration | $2.00 | `--cost-ceiling 0` | `cost_ceiling_reached` |
| Per-iteration budget | `claude -p --max-budget-usd <remaining>` | derived from ceiling | n/a | `cost_ceiling_reached` |
| Context-fill refusal | `(usage.input + cache_read + cache_create) / modelUsage.<model>.contextWindow` ≥ threshold | 0.75 | `--context-fill-threshold 0` | `context_full` |
| Oracle pass | `gate.py --json` exit 0 | always | n/a | `oracle_passed` |
| Stuck-loop / plateau (spec 003-05) | No improvement over M iterations | M=3 | `--plateau-window 0` | `oracle_plateau` |
| Refuse-on-dirty-tree (spec 003-07) | `git status --porcelain` — any tracked-file change | on | `--allow-dirty` | `dirty_tree` |

The **refuse-on-dirty-tree** preflight (slice 003-07, [ADR-0008](decisions/adr-0008-loop-on-autonomy-primitives.md) V4) guards both drivers: a scheduled / unattended run against a git target with uncommitted changes to *tracked* files refuses (rc=2 / `dirty_tree`, the breadcrumb names the paths) rather than scoring leftover state as a spurious immediate pass. Untracked files don't count (so servo's own `.servo/` + the vendored `gate.py` never self-trip it), a non-git target skips the check, and `--allow-dirty` opts out. Loop-mode **resume** skips the check — a resumed loop's tree is legitimately dirty from the prior iterations' agent mutations.

The **context-fill refusal gate** is the **hard cousin** of jig's soft `jig-context-check.sh` warning. Jig's heuristic counts MCP-server entries to estimate tool-description overhead; servo's gate reads the actual per-iteration `usage` + `modelUsage.<model>.contextWindow` and refuses iteration N+1 when the prior iteration's context-fill ratio is at-or-above the threshold. Failures to compute the ratio (missing `usage`, malformed `modelUsage`, missing `contextWindow`) fail-open for *this specific gate* — the iteration cap and cost ceiling still apply.

Each iteration emits one JSON line to stdout (carrying `iteration`, `session_id`, `cost_usd`, `cumulative_cost_usd`, `context_fill_ratio`, `oracle_exit_code`, `oracle_status`, `oracle_composite`); a final summary line carries `terminal_reason`, `iterations_completed`, `cumulative_cost_usd`, `cost_ceiling_usd`, `context_fill_threshold`, `context_fill_ratio`, `final_oracle_status`, `run_id`. The `schema_version: 1` first key on every line mirrors gate.py's ADR-0002 contract.

### Host-scope routing (spec 003-07)

Since the ADR-0008 rebase the driver has three modes. `--driver auto` (the **default**) runs a deterministic host-support probe and picks the path; `loop` and `goal` force a specific path. The probe is auditable without running anything via `loop.py <target> --explain-routing`, and is productionized from [`adr-0008-experiments/v3_audit_env.py`](decisions/adr-0008-experiments/v3_audit_env.py). Two facts decide eligibility:

- **`/goal` available** — `claude --version` ≥ 2.1.139 (the release that shipped `/goal`). A non-Claude host (e.g. Codex) or an older binary fails this.
- **hooks permitted** — the settings hierarchy (user → project → project-local → managed) carries neither `disableAllHooks` (truthy at any layer) nor `allowManagedHooksOnly` (truthy in the managed tier). Either switch disables **both** `/goal` and servo's project meta-judge (ADR-0008 V3), so only the no-hooks loop driver survives.

| `--driver` | `/goal` available **and** hooks permitted | Otherwise |
|---|---|---|
| `auto` (default) | → goal driver | → loop driver (fail-safe downgrade; reason logged to stderr) |
| `goal` (explicit) | → goal driver | **refuses** rc=2 / `goal_unavailable` (names the forcing factor) |
| `loop` (explicit) | → loop driver | → loop driver |

The downgrade is **fail-safe** (the always-works external driver), and the refusal is **fail-closed** (an explicit `--driver goal` never silently degrades) — both consistent with spec 003's "brakes wired in from day one" posture. The loop driver remains the **portable cross-host layer** ([ADR-0008](decisions/adr-0008-loop-on-autonomy-primitives.md) Assumption 7), demoted from default to one of two first-class paths.

### Execution matrix by host (spec 003-08)

The host-scope *routing* above picks **which driver** runs. This matrix records the
complementary contract — **what enforces the oracle** in each execution context.
Servo's deterministic guardrail + oracle layer is the constant; the mechanism that
carries it depends on how the host runs the agent:

| Host / execution context | Continuation owner | servo's authority mechanism | Spec |
|---|---|---|---|
| **Claude Code, interactive** | human (+ optional `/goal`) | meta-judge `Stop` hook (backstop) + `gate.py` | 004 / [ADR-0006](decisions/adr-0006-meta-judge-output-contract.md) |
| **Claude Code, headless `claude -p`** | `/goal` (goal driver) | hard caps on the outer call + a **final `gate.py`** run | 003-06 |
| **Routine / continuous invocation** | `/goal` (one continuous session) | **`gate.py`** — loop-body run each turn + (local driver) a final run; meta-judge **moot** (no per-turn `Stop`) | 003-08 |
| **Hook-restricted / non-Claude host** (e.g. Codex) | external `loop.py` driver | servo's hand-rolled loop — every brake servo-side, no hooks, no `/goal` | 003-01..05 |

Two load-bearing [ADR-0008](decisions/adr-0008-loop-on-autonomy-primitives.md) V4
findings fix the bottom two rows:

- **In a Routine the meta-judge is moot.** A Routine runs the task as a *single
  continuous agent invocation* — no per-turn `Stop` event — so the project
  meta-judge `Stop` hook never fires there, *independent of the cloud's hook
  policy*. The deterministic authority is `gate.py` (the loop-body run each turn +,
  for the local goal driver, a final authoritative run), never the `Stop` hook.
  The meta-judge stays the **interactive-only** backstop.
- **Scheduled reruns need a clean baseline.** A scheduled run reusing a persistent
  tree can inherit a dirty working tree from a prior run → a spurious immediate
  pass. Each scheduled run must start from a **clean committed baseline** — a
  **fresh clone**, or `git reset --hard` to the committed state — and servo's
  **refuse-on-dirty-tree** brake (003-07) enforces this fail-closed (`--background`
  runs the check *before* detaching). Routines are **vendored-`gate.py`-portable**
  (003-07): the oracle resolves relative to `$CLAUDE_PROJECT_DIR` after the cloud
  clone.

**Detached + scheduled surfaces (003-08).** `loop.py --background` launches the goal
driver in a new OS session (`start_new_session`) — the headless analog of the
*interactive* `/background` agent-view action (there is **no** headless
`--background` flag on `claude -p`, verified on 2.1.175). The run-id + `state.json`
are the inspect/await surface; the detached child's output goes to
`<target>/.servo/runs/<run-id>/background.log`. **Routines** themselves are created
from the web/desktop app, not the CLI (no `routine` / `schedule` subcommand);
`loop.py --emit-routine-prompt` makes a target Routine-ready (vendors `gate.py`) and
emits the paste-ready `/goal` prompt with a portable relative gate command.

## Decisions

| ADR | Status | Captures |
|---|---|---|
| [ADR-0001](decisions/adr-0001-reuse-jig-test-detector.md) | Accepted | Reuse jig's `tdd.py detect` via subprocess when co-installed; fall back to built-in detectors otherwise. The first concrete instance of the filesystem-only coupling. |
| [ADR-0002](decisions/adr-0002-gate-caller-contract.md) | Accepted | Quality-gate caller contract: `gate.py` exits only 0/1/2 (unexpected oracle exits remap to 2); `--json` output carries `schema_version` from day one. The contract specs 003/004/005 will consume. |
| [ADR-0003](decisions/adr-0003-fresh-subagent-roster.md) | Accepted | Servo ships two fresh agents (`runner`, `judge`) rather than reusing jig's `implementer` / `reviewer` — the runtime output schemas diverge (machine-parseable verdict block vs narrative). Architect calls are delegated to `jig:architect` directly; the wrapping format is post-processed into servo's ADR shape. |
| [ADR-0004](decisions/adr-0004-session-state-file-format.md) | Accepted | Servo's per-run state at `<target>/.servo/runs/<run-id>/state.json`. References Claude Code's session by `session_id`, doesn't copy the transcript. Versioned via `state_schema_version`; filesystem-only coupling with Claude Code per ADR-0001 framing. |
| [ADR-0005](decisions/adr-0005-eval-oracle-component.md) | Accepted | A non-deterministic eval enters the composite only as a *frozen* `score_<name>` (rubric + dataset + judge model + `n` + `δ` hashed and approved), reporting a confidence lower bound; `loop.py` gains a plateau noise floor. Reciprocal to jig's ADR-0022. |
| [ADR-0006](decisions/adr-0006-meta-judge-output-contract.md) | Accepted | Meta-judge `Stop`-hook output contract (spec 004): block with a composite/threshold hint on below-threshold (not `additionalContext`), fail **open** on env-error (a `systemMessage`, never a block — can't trap a session), nudge once per stop sequence. The interactive inverse of agent-loop's fail-closed brakes. |
| [ADR-0007](decisions/adr-0007-align-release-with-jig.md) | Accepted | Adopt release-please + an enforced conventional-commit PR-title gate for servo releases (align with jig), replacing the hand-edited version / local-zip / no-tag flow. Implemented by spec 010. |
| [ADR-0008](decisions/adr-0008-loop-on-autonomy-primitives.md) | Accepted | Rebase agent-loop orchestration onto Claude Code's autonomy primitives (`/goal`, `/background`, Routines); servo keeps only the deterministic guardrail + oracle layer and retains the external loop driver as the portable path for hook-restricted / non-Claude-Code hosts. Hard constraint: `/goal`'s transcript-only judge never replaces `oracle.sh`. |
| [ADR-0009](decisions/adr-0009-design-fidelity-eval-recipe.md) | Accepted | Design-fidelity as a first-class eval recipe (`/servo:design-eval`): compiles "does the built UI match the mockup?" into a frozen `score_design_fidelity` oracle component (pinned vision model, n-sampled, confidence lower bound), riding ADR-0005's frozen-eval contract. |
| [ADR-0010](decisions/adr-0010-triage-inbox-schema.md) | Accepted | Triage-inbox state-file schema & dedupe identity (spec 011): `schema_version: 2`; ratified `finding_id`; sticky `status` lifecycle separate from a recomputed `actionable` verdict + immutable `provenance` marker (Guardrail #4); one uniform merge + retention rule; `flock` double-fire safety; reserves `outcome.cost_usd` for 011-04. Reciprocal to ADR-0004. |

### Pending (ADR candidates)

Numbers below are *hints* of the next likely allocation order, not reservations — the next accepted ADR claims the next free number (now `0011`) regardless of which candidate fires first. (ADR-0010's inbox-schema "Runtime artifacts" prose is finalized to the shipped `schema_version: 2` shape above; the Decisions-table status flips Proposed → Accepted at slice 011-02 close-out.)

- **A future ADR — Why `oracle.sh` stays project-owned plain bash.** Servo scaffolds it; the project owns it forever after. Driving factors: zero servo runtime dependency for the most-invoked artifact, dev can grep + edit without learning a DSL, version-control friendly. Crystallizes if anyone ever proposes a Python or Node oracle alternative.

## Open questions (not yet ADR-worthy)

- **Composite weighting heuristic** — **resolved (slice 001-02):** weighted *average* (`sum(weight*score) / sum(weight)`), with `"name:weight"` registered in a `COMPONENTS` bash array. Equal weights are the scaffold default; tuning is deferred to the user (and surfaced as a `Weights` decision in 001-04's `refinement-todo.md`). Picked weighted average over weighted sum so any threshold in `[0, 1]` is meaningful regardless of how many components are present.
- **`.servo/install.json` checked in vs ignored** — currently `.gitignore`d; revisit when team-shared servo installs become a use case.
- **Scaffold-init interaction with jig-scaffolded projects** — likely fine (no path collisions) but worth an explicit slice-level test in 001-03 or 001-05.
- **Agent-loop driver: shell vs Python.** **Resolved (slice 003-01 DoR):** Python, same shape as `scaffold.py` / `gate.py`. JSON parsing + state-file management in 003-04 was materially easier in Python than bash.

## Why no crew skill

Multi-agent crews (hand-off / voting / leader-follower coordination) don't yet generalize enough to scaffold. Servo ships a one-page [post-mortem template](../templates/crew-postmortem.md) for capturing ad-hoc crew experiments, but no `/servo:crew` skill. If post-mortems start showing a consistent pattern, that's a future spec; today it would be premature.

## Internal scoping reference

> Internal-only — kept here to anchor scope decisions during spec
> authoring. Not a public framing of servo; should not leak into
> user-facing docs (README, product-vision, templates).

Each runtime skill traces back to a specific pattern in private learning notes:

| Spec | Skill | Source pattern |
|---|---|---|
| 001 | `/servo:scaffold-init` | (spans the four runtime patterns' setup) |
| 002 | `/servo:quality-gate` | oracle scoring |
| 003 | `/servo:agent-loop` | headless iteration ("Ralph") |
| 004 | `/servo:oracle-hook` | meta-judge hook |
| 005 | `/servo:variant-race` | worktree race |
| 006 | `/servo:spec-oracle` | spec-to-evidence compiler |
| 011 | `/servo:heartbeat` | (none — the scheduled *front-end*; Routines-as-trigger, not one of the four runtime patterns) |
| n/a | (teams pattern covered) | by jig's `agents/` |
| n/a | (crews pattern skipped) | post-mortem template only |

Decisions land in [docs/decisions/](decisions/) as ADRs once they're hard to reverse.
