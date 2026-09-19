---
status: DONE
dependencies: [032-03, 032-04]
last_verified: 2026-09-18
# arch_review: true  # maps Claude-only execution primitives onto Copilot; ADR-0028 residual
---

## Slice 032-05 — execution-primitive-mapping

**Goal:** servo's *optional* unattended loop runs under Copilot. This is the
servo-specific slice with no jig analogue: servo's `loop.py` subprocesses
`claude -p --agent runner` and gates on the oracle. Map that to Copilot per the
spike's resolved findings, recording any true residual honestly.

**DoR:**
- ✅ 032-03 done (a Copilot `runner` agent renders, so `--agent runner` resolves).
- ✅ 032-04 done (target-side `agentStop` oracle hook + adapter).
- ✅ 032-01 resolved: Autopilot has **no** oracle-gated stop (only
  `--max-autopilot-continues`/`--max-ai-credits`); `copilot -p -s` needs
  `--allow-all-tools`; `--output-format json` = JSONL; `--usage-output-file`
  exposes cost + `codeChanges.filesModifiedCount`.

**Acceptance Criteria:**

1. **`claude -p`→`copilot -p -s` (loop driver).** `loop.py` gains a Copilot host
   mode: it invokes `copilot -p -s --agent runner --allow-all-tools` (+
   `--output-format json` for parseable output, `--usage-output-file` for cost)
   instead of `claude -p --agent runner`, selected by host, defaulting to Claude
   (no change for Claude users). A test asserts the Copilot invocation form is
   emitted (and the Claude form is unchanged for Claude host). The loop's own
   Python per-iteration oracle gate is unchanged — it does **not** use Autopilot.
2. **Cost + edit-signal parse.** The loop parses `copilot`'s
   `--usage-output-file` JSON for cost (`totalPremiumRequestCost`/`totalNanoAiu`)
   toward its ceiling, and reads `codeChanges.filesModifiedCount` as the native
   edit-signal (maps the ADR-0033/0037 "did the runner edit?" check). A test
   covers parsing a sample usage JSON (fixture from the spike's live run).
3. **`/goal`→Autopilot, honestly (resolved).** The goal driver's per-turn oracle
   gate maps via the **target-side `agentStop` oracle hook** (032-04), with
   Autopilot's `--max-autopilot-continues`/`--max-ai-credits` as the outer bound —
   **not** via any (nonexistent) Autopilot oracle-gated stop. Whether `agentStop`
   fully reconstructs the gate under Autopilot is **not headlessly verifiable**
   (jig 113-08) → the goal-driver-under-Copilot path is shipped behind the same
   host selection but its live fidelity is recorded as an explicit **residual**;
   the loop driver (AC1) is the fully-supported Copilot path. Captured explicitly,
   never a silently un-gated run.
4. **Preflight → Copilot permissions.** servo's ADR-0033/0037 edit-permission
   posture maps to `--allow-all-tools` (required for headless tool use) +
   `codeChanges.filesModifiedCount` as the post-hoc edit-signal; recorded in the
   execution-primitive inventory. Any primitive that does not port is listed in
   the ADR-0028-style inventory (extends 032-04's), never silently renamed.

**DoD:**
- [x] All ACs pass; full suite green (venv pytest); new tests fail when the feature is removed.
- [x] The Autopilot/goal-driver verdict + residuals documented in `docs/architecture.md`
      + refinement-todo.
- [x] Reviewed by `reviewer` subagent (compliance + craft + arch) — PASS; evidence in `reviews/slice-05-{compliance,craft,arch}.md`. Findings resolved: #2 (mkstemp raise) guarded; #4 (symmetric `--cost-ceiling`-under-copilot launch advisory) added; #3 pinned with `test_copilot_not_on_path`; #1 (soft-error-envelope guard) deferred to refinement-todo (needs live Copilot error-envelope data).
- [x] Deviation log + reconciliation sweep produced (in this slice; reviewer reconciliation notes recorded; residuals in refinement-todo + architecture.md).

**Anti-horizontal-phasing check:** After this slice a Copilot user runs servo's
loop driver end-to-end (per-iteration `copilot -p`), and knows precisely what of
the goal driver stays a documented residual and why.

## Deviation log

**Implemented 2026-09-18.** `skills/agent-loop/loop.py` gains a `--host
{claude,copilot}` mode (default `claude` — zero change for Claude users) plus a
Copilot-only `--max-ai-credits`. The Claude loop/goal paths are byte-unchanged
for `--host claude` (verified: `--max-budget-usd` still emitted, no Copilot
tokens leak; the mutation of `_invoke_claude`'s host branch and the routing
override both fail a test when removed). loop.py flows byte-identically into all
three host packages; regenerated via `scripts/build_host_packages.py` (`--check`
clean). Full servo suite green; ruff clean.

### What built (AC1/AC2/AC4 fully; AC3 as an explicit refusal)

- **AC1 — loop driver Copilot mode.** `_invoke_claude(host=…)` delegates to
  `_invoke_copilot`, which builds `["copilot","-p",<prompt>,"-s",
  "--allow-all-tools","--agent",<name>,"--output-format","json",
  "--usage-output-file",<tmp>]` (`-p` takes the prompt as its VALUE — verified
  against `copilot --help` 1.0.86, not the loose `["-p","-s",…]` reading), runs
  it via the SAME `Popen`/`_active_subprocess` SIGINT-forwarding pattern, parses
  the JSONL (`_parse_copilot_jsonl`, filters `ephemeral:true`, takes the terminal
  non-ephemeral event text), reads the usage file, and normalizes into
  `_invoke_claude`'s exact result-dict shape (`_normalize_copilot_result`) so the
  loop body is untouched. `--resume=<session>` is mapped when a session id is
  carried (Copilot's `-r/--resume` verified present; `=` form used because its
  value is optional → space-separated would be ambiguous).
- **AC2 — cost + edit-signal.** `_parse_copilot_usage` reads
  `totalPremiumRequestCost` / `totalNanoAiu` / `codeChanges.filesModifiedCount` /
  `tokenDetails` (tolerant: missing file → zeros, never a crash). The edit-signal
  + native cost are surfaced per iteration on stderr.
- **AC4 — preflight/permissions.** `--allow-all-tools` recorded as the
  headless-edit enabler (ADR-0033 wall analog) and `codeChanges.filesModifiedCount`
  as the post-hoc edit-signal (ADR-0033/0037) in the new
  `docs/architecture.md` "Copilot host execution-primitive inventory".

### Cost-unit decision (AC2, resolved honestly)

Copilot reports **premium-requests / nano-AIU**, not USD, and there is no
faithful conversion. Decision: **do not fabricate USD** — the normalized
`total_cost_usd` is `0.0`, so the cumulative USD `--cost-ceiling` stays honest
and simply **does not brake Copilot** (documented residual). The Copilot loop is
bounded by `--max-iterations` (host-neutral) + the optional per-invocation
`--max-ai-credits` (Copilot's real credit cap; forwarded when set). Native cost +
edit-signal are parsed and surfaced. A *cumulative Copilot-native ceiling* is
deferred (refinement-todo).

### Goal-driver AC3 choice: refuse, explicitly

Chose **refuse** over best-effort-map. Autopilot has no oracle-gated stop
(032-01, live) and the target-side `agentStop` gate's live firing is unverifiable
headless (jig 113-08), so a best-effort Autopilot map risks a silent un-gated run
— the exact failure ADR-0038's honesty invariant forbids. The `/goal` family
(`--driver goal`, `--background`, `--emit-routine-prompt`) refuses under
`--host copilot` (`goal_driver_unsupported_host`) and points to `--driver loop`,
which ports fully and delivers equivalent oracle-gated autonomy under Copilot.
`--driver auto` under Copilot forces the loop driver (skips the Claude-specific
`/goal` host probe).

### AC → test mapping (`skills/agent-loop/test_loop.py`, all subprocess/importlib style)

- **AC1:** `CopilotBuildCmdTests` (argv form, resume mapping),
  `CopilotJsonlParseTests` (ephemeral filter, terminal text, session id, noise
  tolerance), `CopilotLoopDriverIntegrationTests::test_copilot_argv_form_emitted`
  / `::test_claude_argv_unchanged_for_default_host`, `CopilotHostSelectionTests`
  (default=claude, bogus-host reject, auto→loop-under-copilot).
- **AC2:** `CopilotUsageParseTests` (cost, edit-signal, zero-edit signal,
  missing-file), `CopilotNormalizeTests::test_no_usd_fabrication` /
  `::test_native_cost_and_edit_signal_surfaced`,
  `CopilotBuildCmdTests::test_max_ai_credits_forwarded_when_set`,
  `CopilotHostSelectionTests::test_max_ai_credits_validation`,
  `CopilotLoopDriverIntegrationTests::test_downstream_verdict_and_edit_signal`
  (files_modified breadcrumb).
- **AC3:** `CopilotGoalFamilyRefusalTests` (`--driver goal` / `--background` /
  `--emit-routine-prompt` refuse; summary reason `goal_driver_unsupported_host`).
- **AC4:** `CopilotBuildCmdTests::test_argv_form` (`--allow-all-tools`),
  `::test_downstream_verdict_and_edit_signal` (edit-signal), +
  `docs/architecture.md` inventory.
- **Downstream unchanged (loop body untouched):**
  `CopilotNormalizeTests::test_claude_shaped_fields_present` /
  `::test_result_text_feeds_verdict_parser`,
  `CopilotLoopDriverIntegrationTests::test_downstream_verdict_and_edit_signal`.

Six guards mutation-verified (cost honesty, goal-family refusal, host dispatch,
edit-signal parse, host default, routing override) — each fails a named test when
removed.

### Residuals (also in architecture.md + refinement-todo.md)

1. **Cost-unit:** USD ceiling inert under Copilot; no cumulative Copilot-native
   ceiling; `--max-ai-credits` live efficacy on a single `copilot -p` not
   live-verified (fixture-tested only, per the no-live-run rule).
2. **Goal driver:** refuses under Copilot (Autopilot has no oracle gate;
   `agentStop`-under-Autopilot fidelity unverifiable headless). Loop driver is
   the supported Copilot path.
3. **Context-fill gate:** Copilot's usage has no `contextWindow` → the gate fails
   open under Copilot (documented fail-open; iteration + credit caps still apply).
4. **Resume / host persistence:** Copilot's JSONL is not documented to carry a
   session id (mapped when present, else fresh session per iteration; context is
   re-assembled into the prompt regardless); `--host` is not persisted in run
   state, so a resumed loop must re-pass `--host copilot`.
5. **Live end-to-end:** no live `copilot -p` loop was run (hooks don't fire
   headless, spends credits, slow) — recorded as an honest residual; the JSONL
   terminal-event `data` text field is read defensively and should be
   re-validated against live output.

**Deviations from the slice text:** (a) the slice's AC1 argv sketch shows
`["copilot","-p","-s",…]`; the shipped form places the prompt as `-p`'s value
(`copilot -p <prompt> -s …`) per the live `--help` — `-p` requires a value, so
`-p -s` would consume `-s` as the prompt. (b) Added a Copilot-only
`--max-ai-credits` flag (default off, so the AC1 default argv is unchanged) as
the honest per-invocation brake. (c) Chose AC3's *refuse* option (not
best-effort-map). No other deviations. Nothing parked in `docs/inbox.md`.
