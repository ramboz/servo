---
status: DONE
dependencies: []
last_verified:
---

## Slice 003-05 — stuck-loop-and-handoff

**STATUS: DONE**

**Goal:** Two final guardrails close the spec.

1. **Oracle-score plateau detection.** Halt the loop when the composite score does not improve over the last M iterations (default M=3). "Improvement" = strict greater-than. Halting on plateau prevents burning the rest of the budget on a clearly-stuck loop that won't converge.
2. **Subagent handoff.** Author full `agents/runner.md` and `agents/judge.md` prompts (currently placeholders); loop driver dispatches each iteration via `claude --agent <name> -p ...`. Each iteration's prompt is **assembled** by the driver from the seed prompt + the last oracle output + the last judge verdict. The runner produces work; the judge produces a structured verdict that feeds the next runner iteration.

End-to-end value: the spec's headline features are real — the loop halts cleanly on a stuck plateau, and the runner/judge roster is no longer placeholder. After this slice, `/servo:agent-loop` is shippable end-to-end.

**DoR:**
- ✅ Slice 003-04 DONE
- ✅ Spike verified `--agent <name>` flag exists on `claude -p` (corrected the initial research brief's false claim)
- ✅ Decision: plateau window default M=3. **Flagged in `docs/refinement-todo.md` for tuning** once real-world plateau data accumulates.
- ✅ Decision: per-iteration agent choice — runner and judge alternate, starting with runner. (Iteration 1: runner. Iteration 2: judge. Iteration 3: runner. Etc.) Configurable via `--agent-pattern` in a future refinement; today the alternation is hardcoded.
- ✅ Decision: `runner.md` and `judge.md` prompts are authored fresh, **not copied from jig's `implementer` / `reviewer`**. Per the existing placeholder files, jig's prompts assume supervised dev; servo's are unattended.

**Acceptance Criteria:**

1. **Plateau detection (default).** Three consecutive iterations with composite ≤ the highest score seen earlier → loop halts with `terminal_reason=oracle_plateau`, `plateau_window=3`, `oracle_score_history` in the summary. (Tested with a mock that emits the same composite for 3+ iterations.)
2. **Plateau detection (override).** `--plateau-window 5` requires 5 consecutive non-improving iterations.
3. **Plateau threshold semantics.** "Non-improving" means `composite ≤ max(prior_composites)`. Improvement = strict greater-than. Equality counts as non-improving. (Documented because the comparison direction is load-bearing.)
4. **Plateau detection (disable).** `--plateau-window 0` disables plateau detection entirely. (Same shape as the other `0` semantics for cost-ceiling / context-fill.)
5. **`runner.md` ships.** `agents/runner.md` is a real prompt that, given a target + last oracle output + last judge verdict, produces output ending with a fenced ```` ```verdict ```` block (per Clarifications Q7) carrying `schema_version: 1` (first field), `verdict: <one of CHANGES_MADE | NO_CHANGES | BLOCKED>`, optional `files_changed: <comma-separated paths>`, and `reasoning: <one-line summary>`. Placeholder banner removed. Prompt structure + block schema documented in the file body. Tested via mock-claude output that ends with the canonical block; `loop.py` parses the block and surfaces the parsed fields in the per-iteration JSON.
6. **`judge.md` ships.** `agents/judge.md` is a real prompt that, given a target + last runner output, produces output ending with a fenced ```` ```verdict ```` block carrying `schema_version: 1` (first field), `verdict: <one of PASS | FAIL | INCONCLUSIVE>`, `score: <float in [0.0, 1.0]>`, and `reasoning: <one-line summary>`. Placeholder banner removed. Output schema documented inline. The block parser shape is shared between `runner.md` and `judge.md` (single regex in `loop.py`); the `verdict:` field's allowed values differ by agent.
7. **Loop dispatch.** Each iteration invokes `claude --agent <runner|judge> -p ...` and captures the JSON. Agent alternation (runner → judge → runner → judge → ...) is verified by inspecting the args passed to the mock `claude` across iterations.
8. **Per-iteration prompt assembly.** The loop driver concatenates the seed prompt (from `--prompt <text>` or `--prompt-file <path>`) + the last `gate.py --json` output + the last judge verdict (if any) into a structured prompt block sent to the next agent. Format pinned in `loop.py` and documented in `runner.md` / `judge.md` so the agents know how to read it.
9. **SKILL.md surface (qa-wizard).** `skills/agent-loop/SKILL.md` exposes the loop to the LLM with trigger phrases ("run an agent loop", "iterate on this codebase", "head-less loop"), anti-greediness tests (does **not** fire on "score this code" → that's `/servo:quality-gate`), Q&A for the seed prompt / overrides, refusal-handling guidance. Surface tests under `skills/agent-loop/test_skill_surface.py`.
10. **Verdict-block `schema_version` enforced (ADR-0003).** The shared parser in `loop.py` extracts `schema_version` as the first key in every verdict block. Three refusal paths, each rc=2 with `reason=verdict_schema_mismatch` and a stderr breadcrumb naming the expected version (`1`) and the observed value: (a) field absent; (b) field present but ≠ 1 (e.g., `schema_version: 2`); (c) field present but wrong type (e.g., `schema_version: "1"` — string instead of int). The mismatch terminates the loop iteration the block belongs to; the loop's overall `terminal_reason` reflects the mismatch and the state file's `last_terminal_reason` captures it for resume forensics.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions in `test_loop.py` slice-003-01..04 cases, `test_gate.py`, `test_scaffold.py`).
- [x] Test coverage per AC under `skills/agent-loop/test_loop.py`: AC1→`PlateauDetectionDefaultTests`, AC2→`PlateauWindowOverrideTests`, AC3→`PlateauThresholdSemanticsTests`, AC4→`PlateauDisabledTests`, AC5→`RunnerVerdictBlockTests`, AC6→`JudgeVerdictBlockTests`, AC7→`AgentAlternationDispatchTests`, AC8→`PromptAssemblyTests`, AC9→`skills/agent-loop/test_skill_surface.py`, AC10→`VerdictSchemaMismatchTests`.
- [x] Reviewed by `jig:reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated (spike Q1/Q2/Q5/Q6 deferred for live-claude verification).

### Close-out (post-DONE)

- [x] **ADR-0003 Accepted.** (Already Accepted pre-implementation per `docs/architecture.md` "Decisions" table; this slice closes the prompt-authoring side of the ADR.)
- [x] SKILL.md anti-greediness tests pass (`python3 skills/agent-loop/test_skill_surface.py`).
- [x] `README.md` skills table row for `agent-loop` flipped to `Spec 003 — DONE`.
- [x] `docs/specs/README.md` status board: spec 003 → DONE.

**Anti-horizontal-phasing check:** After this slice, the user-facing surface is complete — typing a trigger phrase produces a real loop with all guardrails wired, a real subagent roster, and a parseable per-iteration log. This is the slice that closes the spec.

### Deviation log (after reconciliation)

**Slice 003-05 — implemented 2026-05-20.** 51 new tests under `skills/agent-loop/test_loop.py` (151 total) + 26 new tests under `skills/agent-loop/test_skill_surface.py`. Full regression sweep green across 6 suites (151 + 26 + 75 + 40 + 18 + 13 = 323 tests). Both `agents/runner.md` and `agents/judge.md` are authored prompts (previously placeholders) with verdict block schemas documented inline. Plateau detection, agent alternation, per-iteration prompt assembly, and verdict-block schema enforcement all wired into `loop.py`. `skills/agent-loop/SKILL.md` ships with anti-greediness surface tests; ADR-0003 already Accepted (pre-implementation framing) — this slice is the artifact-shipping side of that ADR.

Deviations from spec text and ADR-0003:

- **Lenient "no verdict block" parsing.** AC10 enumerates three refusal paths within a block that exists (field absent, ≠ 1, wrong type). `_parse_verdict_block` returns `(None, None)` when no fenced ```verdict``` block is present at all — treated as informational, not a refusal. The loop continues with `last_verdict=None`; the next iteration's prompt simply omits the verdict section. Rationale: an agent malfunction that produces narrative-only output is a soft failure (the loop can recover with the next runner), while a block-present-but-malformed verdict indicates a schema-incompatible agent that must terminate the run. Pinned by `VerdictSchemaMismatchTests.test_no_block_at_all_is_not_a_refusal`. ADR-0003 doesn't pin the "no block" case explicitly; the lenient interpretation is the more conservative one (refusing on missing-block could break any future agent revision that intentionally suppresses the block, e.g., a "thinking-only" pass).
- **Empty-block rejection added as an implicit fourth refusal path.** A fenced ```verdict``` block with no non-empty lines is rejected with breadcrumb `"verdict block is empty"`. AC10's "field absent" reading covers this implicitly (a block can't satisfy "schema_version as the first key" if there are no keys), but the literal AC text doesn't enumerate this sub-case. Pinned by `ParseVerdictBlockUnitTests.test_empty_block_is_an_error`.
- **Per-iter verdict fields are surfaced as raw strings, except `schema_version` (always cast to `int`).** AC10 only type-enforces `schema_version`. Other fields — `score` (judge), `files_changed` (runner) — pass through as strings (`"0.85"`, `"a.py, b.py"`). The judge prompt declares `score` as a float in `[0.0, 1.0]` but the parser doesn't enforce the range or cast. Documented for the spec 005 race driver, which will need to parse `score` as float and clip to range if it weights variants by judge confidence.
- **`AGENT_RUNNER` / `AGENT_JUDGE` constants and hardcoded alternation.** Iter 1=runner, iter 2=judge, iter 3=runner, etc. Per the slice DoR: "Configurable via `--agent-pattern` in a future refinement; today the alternation is hardcoded." No `--agent-pattern` flag in this slice. Pinned by `AgentAlternationDispatchTests`.
- **Per-iter JSON adds an `agent` field beyond the spec's literal field list.** AC7's text says the alternation is "verified by inspecting the args passed to the mock `claude`." The implementation additionally surfaces the agent name in each per-iter JSON line under key `agent`. Additive; downstream consumers can group lines by role without re-deriving from iteration parity. Pinned by `AgentAlternationDispatchTests.test_per_iter_json_carries_agent_field`.
- **`oracle_score_history` is emitted in every summary line, not just on `oracle_plateau` halts.** AC1's text names `oracle_score_history` in the plateau-halt summary. The implementation includes it on every summary path (matches the slice 003-04 pattern of "summary fields are present uniformly across all halt paths"). Mildly verbose but consistent. Forensic readers get the full history regardless of halt reason.
- **`plateau_window` is emitted in every summary line.** Same generalization as `oracle_score_history`: present even when the plateau brake didn't fire. Spec AC1 lists `plateau_window` as a required field on the `oracle_plateau` halt; emitting it universally is additive.
- **`_assemble_iteration_prompt` adds `Context from prior iteration:` framing header and `---` delimiters.** AC8 says "concatenates the seed prompt + the last `gate.py --json` output + the last judge verdict (if any) into a structured prompt block." The specific framing characters (`---` lines, "Context from prior iteration:" header) are implementation choices, not spec-pinned. Documented in `agents/runner.md` / `agents/judge.md` so the agents know how to read the prompt. Pinned by `PromptAssemblyTests.test_iter_two_prompt_includes_oracle_and_verdict`.
- **`session_id` chain: all iter 2+ invocations use `claude -p --resume <current_session_id>` carrying the most recently observed session.** Slice 003-04 introduced the resume mechanism; slice 003-05 reuses it for in-run iteration continuity (each iteration's response updates `current_session_id`). The spec's slice 003-04 wording is ambiguous about whether within-run iterations carry session; this slice commits to "yes, always" (mirrors the assumption that conversation continuity across iters is desirable). No additional tests added in 003-05 beyond what 003-04 covered.
- **Verdict-block last-match semantics for multi-block agents.** When `_VERDICT_BLOCK_RE.finditer` returns multiple matches, the LAST is parsed. Agent prompts say "the block must be the final content"; the parser is lenient about intermediate blocks. Pinned by `ParseVerdictBlockUnitTests.test_multiple_blocks_last_wins`.
- **Test infrastructure: `_run_loop` defaults `--plateau-window 0` unless the caller passes it.** Legacy 003-01..04 tests use constant-composite mocks that would otherwise trip the default plateau brake at iter 4 instead of running to the test's expected iteration count. Plateau-specific tests opt back in by passing their own `--plateau-window N`. This is purely a test-suite adjustment; production CLI default remains 3 via `DEFAULT_PLATEAU_WINDOW`. Documented in `_run_loop`'s docstring.
- **Test infrastructure: args-log delimiter scheme.** Slice 003-05's multi-line iteration prompts caused the prior `echo "$*"` mock to fragment a single invocation across multiple log lines. The new format uses U+001F (Unit Separator) between args and U+001E (Record Separator) between invocations, so embedded newlines in the prompt no longer confuse `_read_args_log`. Updated `_mock_claude_with_args_log` and `_mock_claude_costs_per_iter` to write the new format; `_read_args_log` parses on the new delimiters.
- **Test infrastructure: triple-backtick Unicode escaping.** The verdict block contains triple backticks. Bash unquoted heredocs trigger command substitution on backticks. To avoid this, test helpers encode triple backticks as ````` in the JSON `result` field; Python's `json.loads` in loop.py decodes them back to literal backticks before the verdict parser sees the block. `_BTICK = "\\u0060\\u0060\\u0060"`. Documented at the constant definition.

**Reviewer caveats (non-blocking):**
- `score` validation: a buggy judge that emits `score: 1.5` (outside `[0.0, 1.0]`) is accepted by the parser. Spec 005's race driver will likely want to clip; could optionally pin a `score`-range check in a future tightening.
- `files_changed` conditional shape: AC5 says it's optional when `verdict: CHANGES_MADE`. The parser doesn't enforce "files_changed must be absent on NO_CHANGES / BLOCKED." Acceptable — the runner prompt is the contract.
- Renderer of last-verdict back into the prompt (`_assemble_iteration_prompt`): if a future field is added to the verdict block (e.g., `confidence`), the renderer at `loop.py:355-358` will round-trip it correctly because it iterates the parsed dict. Documented for clarity.
- The slice description in spec.md's slice 003-05 text says "(iter 3+)" for the runner-reading-judge-verdict case; the implementation includes oracle+verdict on iter 2+ whenever EITHER is non-None. The "judge verdict absent until iter 3" framing in `agents/runner.md` is descriptive (iter 1=runner sees nothing; iter 2=judge sees iter-1 runner output; iter 3=runner sees iter-2 judge verdict).

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-20). All 10 ACs implemented and exercised by the named test classes per the DoD mapping. Plateau detection arithmetic correctly implements the spec's "≤ counts as non-improving" wording (`_check_plateau` at `loop.py:392-419`); verdict parser handles all three AC10 refusal paths with distinct breadcrumbs; agent alternation, prompt assembly, and `--agent` argv dispatch are all verified end-to-end; `agents/runner.md` and `agents/judge.md` are real prompts with their verdict block schemas documented inline; `SKILL.md` satisfies the anti-greediness pattern (positive triggers in scope, negative triggers excluded, sibling skills referenced, no-silent-retry guidance present). Twelve documented deviations from spec text — all non-blocking, all in the deviation log above.

---

