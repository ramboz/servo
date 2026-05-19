---
status: SPIKE_FINDINGS
date: 2026-05-18
informs: docs/specs/003-agent-loop/spec.md (when drafted)
---

# Pre-spec research spike — `/servo:agent-loop`

> Goal: identify what Claude Code's headless mode exposes to a loop driver, so spec 003 can be sliced with confidence and ADR-0005 (session-state file format) can be drafted with an accurate picture of what already exists on disk.

## Method

1. Spawned `claude-code-guide` subagent with a structured research brief (seven questions covering invocation, cost, context, resume, ceilings, hooks, subagents).
2. **Cross-checked claims empirically** against `claude --help` and a live `claude -p ... --output-format json` invocation. Several agent claims turned out to be hallucinated; this section is therefore not the agent's report but the verified subset.
3. Read jig's `jig-context-check.sh` (referenced from `docs/specs/README.md` as the soft cousin of servo's planned context-fill gate).

## Empirical findings — Claude Code headless surface

### Invocation

```bash
claude -p "<prompt>"  # one-shot, exits after assistant turn(s)
```

Relevant flags (verified in `claude --help`, 2026-05-18):

| Flag | Purpose |
|---|---|
| `-p, --print` | Non-interactive single-result mode. Skips workspace trust dialog. |
| `--model <name>` | Pin model (e.g. `sonnet`, `opus`, or full name). |
| `--agent <name>` | **Invoke a specific subagent directly headless.** Overrides the `agent` setting for the session. |
| `--agents <json>` | Define ad-hoc agents inline. |
| `--append-system-prompt <text>` | Append to default system prompt. |
| `--system-prompt <text>` | Replace default system prompt entirely. |
| `--max-budget-usd <amount>` | **Per-invocation** cost cap (works with `--print` only). |
| `--output-format <fmt>` | `text` (default), `json` (single result), `stream-json` (realtime). |
| `--input-format <fmt>` | `text` or `stream-json` (only with `--print`). |
| `--json-schema <schema>` | Structured-output validation. |
| `-c, --continue` | Continue the most recent conversation in cwd. |
| `-r, --resume [session-id]` | Resume by session ID, or interactive picker. |
| `--fork-session` | With `--resume`/`--continue`: create new session ID (don't reuse). |
| `--session-id <uuid>` | Use a specific session UUID for the conversation. |
| `--no-session-persistence` | Don't save session to disk (only with `--print`). |
| `--effort <level>` | `low`/`medium`/`high`/`xhigh`/`max`. |
| `--include-hook-events` | Include all hook lifecycle events in stream (only with `--output-format=stream-json`). |
| `--allowedTools` / `--disallowedTools` | Tool gating. |
| `--add-dir <dirs...>` | Extra tool-accessible dirs. |
| `--dangerously-skip-permissions` | Bypass permission checks. |

### `--output-format json` schema (empirically captured)

`claude -p "say only the word PING" --output-format json --max-budget-usd 0.10` returned (single JSON object, formatted for readability):

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "api_error_status": null,
  "duration_ms": 3413,
  "duration_api_ms": 1702,
  "ttft_ms": 2074,
  "num_turns": 1,
  "result": "PING",
  "stop_reason": "end_turn",
  "session_id": "78c746cb-8e56-438e-bb92-f18fea60dcec",
  "total_cost_usd": 0.07695149999999999,
  "usage": {
    "input_tokens": 3,
    "cache_creation_input_tokens": 20498,
    "cache_read_input_tokens": 0,
    "output_tokens": 5,
    "server_tool_use": { "web_search_requests": 0, "web_fetch_requests": 0 },
    "service_tier": "standard",
    "cache_creation": { "ephemeral_1h_input_tokens": 20498, "ephemeral_5m_input_tokens": 0 },
    "inference_geo": "",
    "iterations": [ { /* per-message usage breakdown */ } ],
    "speed": "standard"
  },
  "modelUsage": {
    "claude-sonnet-4-6": {
      "inputTokens": 3,
      "outputTokens": 5,
      "cacheReadInputTokens": 0,
      "cacheCreationInputTokens": 20498,
      "webSearchRequests": 0,
      "costUSD": 0.07695149999999999,
      "contextWindow": 200000,
      "maxOutputTokens": 32000
    }
  },
  "permission_denials": [],
  "terminal_reason": "completed",
  "fast_mode_state": "off",
  "uuid": "4bcbd62c-a20d-4ea8-bab0-73d3253ac408"
}
```

Load-bearing fields for spec 003:

- **`session_id`** — what `--resume` consumes; needed for checkpoint/resume.
- **`total_cost_usd`** — per-invocation cost; loop driver sums across iterations for the cumulative ceiling.
- **`num_turns`** — agentic-turn count *within this invocation* (one `--print` call can include multiple tool-use→response turns).
- **`usage.input_tokens` + `usage.cache_read_input_tokens` + `usage.cache_creation_input_tokens`** — total prompt tokens that hit the model.
- **`modelUsage.<model>.contextWindow`** — total context-window size for the model used (200000 for sonnet-4-6).
- **`stop_reason`** (`end_turn`, presumably others like `max_tokens`, `tool_use`) — what ended the last assistant message.
- **`terminal_reason`** (`completed`, presumably others like `budget_exceeded`, `error`) — what ended the whole invocation.

### Session storage on disk

Sessions are persisted under `~/.claude/projects/<project-slug>/<session-id>.jsonl`. The project slug is the absolute path with `/` replaced by `-` (e.g., `/Users/ramboz/Projects/misc/servo` → `-Users-ramboz-Projects-misc-servo`). Each session is a JSONL file (one event per line). Existence verified.

### Hooks: `Stop` event with `additionalContext`

`settings.json` hooks block (project- or user-scoped):

```json
{
  "hooks": {
    "Stop": [
      { "matcher": "*", "hooks": [ { "type": "command", "command": "/path/to/script.sh" } ] }
    ]
  }
}
```

Hook script exits 0 and prints JSON on stdout:

```json
{
  "continue": true,
  "suppressOutput": false,
  "hookSpecificOutput": {
    "hookEventName": "Stop",
    "additionalContext": "Text pushed into the next assistant turn"
  }
}
```

This is the surface spec 004 (`/servo:oracle-hook`) will install. **Verified empirically by reading `jig-context-check.sh`**, which uses the same shape (`additionalContext`).

## Corrections to the initial research brief

The `claude-code-guide` subagent's first pass had three load-bearing errors that empirical verification caught:

| Agent claim | Reality |
|---|---|
| `--max-turns N` caps agentic-turn depth | **Does not exist.** Confirmed via `claude --help \| grep -E "max-turns\|max-tokens\|max-cost\|max-iter"` returning nothing. Spec 003's iteration cap is **purely external**. |
| "Subagents can only be invoked via the Agent tool, not directly from CLI" | **`--agent <name>` flag exists.** Spec 003's loop driver can invoke `runner` / `judge` directly headless. |
| "Context-fill % is not exposed; must spawn `/context` subagent or track externally" | **It IS exposed.** `--output-format json` returns `usage` + `modelUsage.<model>.contextWindow`; the loop driver computes the ratio externally. No subprocess gymnastics needed. |

Additional finding from reading jig's actual context-check:

> Jig's `jig-context-check.sh` is **not a context-fill measurement**. It counts MCP server entries in `.mcp.json` + `.claude/settings.json` + `.claude/settings.local.json` and warns when the count exceeds 8, because tool-description overhead from many MCP servers pushes the context toward >40% fill. It's a **heuristic on tool-description bloat**, not a real fill % gauge. Servo's hard refusal gate (spec 003) can do **strictly better** by reading `usage.input_tokens + cache_*` / `modelUsage.<model>.contextWindow` from the JSON output of the previous turn and refusing iteration N+1 when the ratio exceeds a threshold.

## Spec 003 guardrails — mechanism mapping

| Guardrail | Mechanism today | Verdict |
|---|---|---|
| **Iteration cap** | External counter in loop driver. No CLI cap (`--max-turns` doesn't exist). Each `claude -p` call = 1 outer iteration (may contain multiple agentic turns internally per `num_turns`). | ✅ Clean — trivial counter |
| **Cost ceiling** (per iteration) | `--max-budget-usd <X>` on each `claude -p` invocation. | ✅ Clean |
| **Cost ceiling** (cumulative across iterations) | Loop driver sums `total_cost_usd` from each invocation's JSON output. Stops when cumulative exceeds target. | ✅ Clean (external) |
| **Context-fill refusal gate** | Read `usage.input_tokens + cache_read_input_tokens + cache_creation_input_tokens` and divide by `modelUsage.<model>.contextWindow`. Refuse next iteration when ratio > N%. | ✅ Clean (external; **better than jig's MCP-count heuristic**) |
| **Checkpoint** | `session_id` from JSON output. Persist alongside servo's per-run state. | ✅ Clean |
| **Resume** | `claude -p --resume <session-id> ...`. Loop driver reads the last session_id from its state file. | ✅ Clean |
| **Stuck-loop detection** | External: track oracle composite-score history from `gate.py --json` across iterations. Halt when no improvement over M iterations. | ✅ Clean — uses existing spec-002 surface |
| **Subagent handoff** | `claude --agent <name> -p "<prompt>"` per iteration. Loop driver decides which agent to invoke + what prompt to pass. | ✅ Clean |
| **Token ceiling** | Loop driver sums `usage.input_tokens + output_tokens` from JSON. Refuse when cumulative exceeds target. | ✅ Clean (external) |

**Net:** every guardrail named in spec 003's planned scope is implementable with today's surface. None is blocked on a Claude Code feature gap. Everything goes through `--output-format json` + external accounting in the loop driver.

## ADR-0005 implications (session-state file format)

The architecture-pending ADR was framed as "spec 003 invents the on-disk format for checkpoint/resume." The spike changes this:

- **Claude Code already owns the conversation transcript** at `~/.claude/projects/<slug>/<session-id>.jsonl`. Servo doesn't re-store the transcript.
- **Servo's per-run state** is the **loop-driver scoreboard**: which session_id is current, cumulative cost, oracle-score history, iteration count, current model, last terminal_reason, last context-fill %. None of this is in Claude Code's session JSONL.
- **Servo's path** for the scoreboard: `<target>/.servo/runs/<run-id>/state.json` (reserved in `docs/architecture.md` "Runtime artifacts").

Proposed ADR-0005 shape (sketch, not yet drafted):

> **Decision:** Servo's per-run state lives at `<target>/.servo/runs/<run-id>/state.json` and references the Claude Code session by `session_id` rather than copying conversation content. Schema includes: `run_id`, `started_at`, `current_session_id`, `iteration_count`, `cumulative_cost_usd`, `cumulative_input_tokens`, `cumulative_output_tokens`, `oracle_score_history: [composite, ...]`, `context_fill_pct_history: [...]`, `last_terminal_reason`, `state_schema_version`. On `--resume`, the loop driver reads `current_session_id` and passes it to `claude -p --resume`. **Coupling:** filesystem-only — servo never imports Claude Code's session JSONL parsing; it just hands the ID back.

This is materially smaller scope than what architecture.md suggested (no transcript marshaling, no Anthropic-format compatibility) and matches ADR-0001's "filesystem-only coupling" framing.

## Open questions (would warrant verification before/during slice 003-NN)

1. **`terminal_reason` taxonomy.** Empirical sample showed `"completed"`. What are the others? `budget_exceeded`, `error`, `interrupted`, `timeout`? Slice 003-XX (cost-ceiling) needs to assert the exact string `claude -p` emits when `--max-budget-usd` is hit, so the loop driver can detect that path and emit a sensible refusal reason. **Verify with:** `claude -p "loop infinitely please" --max-budget-usd 0.001 --output-format json | jq '.terminal_reason'`.
2. **`stop_reason` taxonomy.** Sample had `"end_turn"`. Anthropic API docs name `max_tokens`, `tool_use`, `stop_sequence`, `pause_turn`, others. Which surface to the JSON output? Less load-bearing than `terminal_reason` but informs the structured-summary the loop driver emits per iteration.
3. **Stream-json vs single-result-json semantics.** `--output-format stream-json` emits multiple events; cost/usage may arrive at the end or per-event. Spec 003 will probably stick with single-result JSON (one invocation = one summary) but worth confirming once an iteration includes meaningful tool use.
4. **Session JSONL portability.** Are session IDs portable across Claude Code versions / machines? Spec 003's checkpoint/resume contract says "across invocations" — does that include across machine reboots? Across `claude` version upgrades? Architecture says "filesystem-only coupling" which implies "best-effort: if the JSONL is gone, restart fresh."
5. **`--max-budget-usd` granularity.** Does it stop *before* the next API call would exceed the budget (clean halt), or partway through with a partial response? Affects whether the loop driver can rely on `total_cost_usd` being ≤ the budget on the budget-exhausted exit path.
6. **`--agent <name>` + permissions.** Does invoking `--agent runner -p "..."` inherit the parent's `--allowedTools` / `--disallowedTools`, or is the agent's own `tools:` frontmatter authoritative? Slice 003-XX (subagent handoff) needs to know what the runner can actually do when servo's loop spawns it.

## Implications for spec 003 slicing

The planned 5-slice cadence (mirroring spec 001 / 002) still holds, but **slice ordering and scope shift** based on spike findings:

| Planned focus | After-spike reframe |
|---|---|
| **003-01 invoke-loop**: spawn `claude -p` in a counted loop, capture JSON, stop after N | Same. Spike-shaped: validates the "loop driver subprocesses Claude Code" assumption. Trivial counter for iteration cap; no Claude Code feature needed. |
| **003-02 cost-ceiling**: external accounting from `total_cost_usd` | Confirmed implementable. Add per-iteration `--max-budget-usd` for defense-in-depth; cumulative tracking in state file. |
| **003-03 context-fill gate**: external ratio from `usage` + `modelUsage.contextWindow` | Confirmed implementable. Spec the threshold (e.g., 60%? 75%?) as a refinement-todo entry at scaffold time. |
| **003-04 checkpoint/resume**: state file at `<target>/.servo/runs/<run-id>/state.json` referencing `session_id` | Confirmed implementable. ADR-0005 drafted alongside. |
| **003-05 stuck-loop + subagent handoff**: oracle-score-plateau detection + `runner`/`judge` agent prompts | Confirmed implementable. Authors `agents/runner.md` and `agents/judge.md` (currently placeholders) — this slice ALSO closes the architecture-pending "fresh subagent roster" ADR candidate. |

**No slice is blocked on a Claude Code feature**, no slice needs a workaround for missing APIs. Spec 003 is **ready to draft**.

## Risk register (residual)

- **Claude Code CLI surface might evolve.** The flags above are verified against the version present 2026-05-18; a future `claude` upgrade could rename or remove any of them. Mitigation: pin the spec 003 implementation against the **documented flag names** and add a `claude --version` capture to the state file so a future debug session can pin the discrepancy.
- **`terminal_reason` taxonomy gap.** Open question #1 above; if `--max-budget-usd` halt emits a string different from what we expect, the cost-ceiling slice's refusal-reason mapping needs to update. Mitigation: empirical verification in slice 003-02 (cost-ceiling) before writing the AC.
- **JSON schema drift.** Anthropic could change the JSON shape between versions. Mitigation: capture the version + schema fingerprint in the state file; refuse to resume sessions written by an incompatible version.

## Recommendation

**Spec 003 is implementable today.** All five planned guardrails map cleanly to today's `claude` CLI surface — primarily via `--output-format json` + external accounting in a Python loop driver. Drafting the spec is the next step; ADR-0005 (session-state file format) should land alongside slice 003-04 (checkpoint/resume), drafted to the sketch above.

Two side-effects worth noting at the architecture level:

1. **The "fresh subagent roster" ADR candidate** (architecture.md, currently numbered ADR-0003) crystallizes at slice 003-05 when `runner` / `judge` ship.
2. **The architecture.md "Open questions" entry** about "agent-loop driver: shell vs Python" can be resolved in favor of Python — the JSON parsing + state file management is materially easier in Python than bash, and there's no dependency on Tier-1 vs Tier-2 anymore since the CLI surface is uniform.
