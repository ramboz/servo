---
status: DONE
dependencies: [032-02]
last_verified: 2026-09-18
---

## Slice 032-03 — agents

**Goal:** servo's agents (`runner`, `judge`) render as Copilot custom agents under
`hosts/copilot/.github/agents/<name>.agent.md`, so the mapped loop (032-05) has a
Copilot `runner`/`judge` to invoke — mirroring jig's `render_copilot_agent`.

**DoR:**
- ✅ 032-02 done (Copilot renderer + package skeleton; `build_all` copilot arm).
- ✅ 032-01 fixed the agent file form (`.agent.md`, frontmatter fields Copilot
  honors) + the Claude→Copilot tools map.

**Acceptance Criteria:**

1. **Agents rendered.** Each source `agents/<name>.md` (`runner`, `judge`) renders
   to `hosts/copilot/.github/agents/<name>.agent.md`; the manifest's
   `agents: ".github/agents"` path resolves to real files. Body preserved.
2. **Tools mapped.** Frontmatter `tools:` are mapped Claude→Copilot
   (`Read→view`, `Glob→glob`, `Grep→grep`, `Write→create`, `Edit→edit`,
   `Bash→bash`); an unmapped tool raises (mapped-or-explicit, no silent pass). A
   test asserts `runner`'s `[Read,Write,Edit,Bash,Glob,Grep]` → `[view,create,edit,
   bash,glob,grep]` and `judge`'s read-only `[Read,Glob,Grep]` → `[view,glob,grep]`.
3. **Model-id neutrality.** No rendered agent carries a `model:` field or a
   hard-coded `opus`/`sonnet` id (servo's source agents already omit `model:` —
   assert it stays absent). A test asserts no Claude model id leaks into any
   rendered `.agent.md`.
4. **Read-only posture preserved.** `judge`'s read-only tool set (no
   `create`/`edit`/`bash`) is preserved in the rendering (a test asserts `judge`
   has no write/exec tool).
5. **Drift + Claude/Codex unchanged.** `build_host_packages.py --check` clean after
   regenerating; Claude/Codex output byte-unchanged.

**DoD:**
- [x] All ACs pass; full suite green (1811 passed + inline-tools guard test); new tests fail when the feature is removed (mutation-verified).
- [x] `--check` clean; Claude/Codex byte-unchanged.
- [x] Reviewed by `reviewer` subagent (compliance + craft) — PASS; evidence in `reviews/slice-03-{compliance,craft}.md`; finding-1 hardened (inline-`tools:` guard).
- [x] Deviation log + reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice a Copilot user can invoke
servo's `runner`/`judge` agents — new end-to-end capability, and 032-05's
`copilot -p --agent runner` can resolve.

## Deviation log

Implemented ACs 1–5 as written, TDD (failing tests first, confirmed red,
then implementation, confirmed green). Suite green + both new guards
mutation-verified. Not committed (working tree left dirty for owner review).
DoD checkboxes left unticked pending the `reviewer` subagent pass — this
implementer pass covers the code + test half only.

### What was built
- `scripts/build_host_packages.py` (+~130 lines):
  - `CLAUDE_TO_COPILOT_TOOLS` — module-level map (`Read→view`, `Glob→glob`,
    `Grep→grep`, `Write→create`, `Edit→edit`, `Bash→bash`), covering exactly
    the tools servo's `agents/runner.md` and `agents/judge.md` use (no
    `WebSearch`/other jig-only entries added — servo's agents don't use
    them).
  - `_copilot_tool_names(claude_tools)` — pure mapper over that dict;
    raises `ValueError` on any name absent from the map (mapped-or-explicit,
    no silent pass-through — mirrors jig's `CopilotAgentToolError` stance
    and this file's own `_copilot_safe_skill_name` guard).
  - `_frontmatter_list(frontmatter, key)` — targeted reader for a YAML
    block list (`key:` followed by `  - item` lines), the list-valued
    counterpart to the existing scalar `_frontmatter_value`.
  - `_replace_tools_block(frontmatter, new_tools)` — surgical replace of
    just the `tools:` block, leaving every other line (`name:`,
    `description:`, comments) untouched. Same "touch only what changes"
    style as the existing `_replace_name_line` / `_replace_description_field`.
  - `_render_copilot_agent(data, name)` — pure fn, the new render entry
    point: splits frontmatter/body via the existing `_split_frontmatter`,
    raises if frontmatter is absent or carries a `model:` field (the
    model-neutrality assert), maps `tools:` via `_copilot_tool_names` +
    `_replace_tools_block`, and returns `frontmatter + body` — body is
    never touched, so it is preserved byte-for-byte.
  - `_copy_copilot_tree`: added an agents loop (source `agents/<name>.md` →
    `_render_copilot_agent` → `.github/agents/<name>.agent.md`), positioned
    between the existing skills loop and the templates loop; docstring
    updated (no longer forward-references "populated by slice 032-03").
  - `validate_copilot_package`'s docstring: one-line wording fix — it
    referenced agents as "slice 032-03's deliverable" (now current, not
    future); left its actual validation logic untouched, since extending it
    to check agent files is not required by any AC here (would be scope
    creep on a function this slice doesn't need to touch).
- `hosts/copilot/.github/agents/runner.agent.md`,
  `hosts/copilot/.github/agents/judge.agent.md` (new, regenerated committed
  package output). `hosts/claude/**` and `hosts/codex/**` unchanged (git
  status shows only the new `hosts/copilot/.github/agents/` directory as
  untracked; no modified files under `hosts/claude` or `hosts/codex`).
- `scripts/test_build_host_packages.py` (+13 new tests): 5 build-level tests
  in `HostPackageTests` (exercise the full `build_all` output) + 8
  pure-function tests in `CopilotRenderUnitTests` (exercise
  `_copilot_tool_names` / `_render_copilot_agent` directly, no build).

### AC → gating test names
- **AC1** (agents rendered; body preserved; manifest path resolves to real
  files): `HostPackageTests::test_copilot_agents_rendered_with_mapped_tools`,
  `::test_copilot_agent_name_description_and_body_preserved`,
  `::test_copilot_manifest_agents_path_resolves_to_real_files`;
  `CopilotRenderUnitTests::test_render_copilot_agent_maps_tools_preserves_name_description_body`,
  `::test_render_copilot_agent_is_deterministic`,
  `::test_render_copilot_agent_no_frontmatter_raises`.
- **AC2** (tools mapped; unmapped tool raises; runner's full 6-tool list ->
  `[view,create,edit,bash,glob,grep]`):
  `HostPackageTests::test_copilot_agents_rendered_with_mapped_tools`;
  `CopilotRenderUnitTests::test_copilot_tool_names_maps_claude_to_copilot_vocabulary`,
  `::test_copilot_tool_names_rejects_unmapped_tool`,
  `::test_render_copilot_agent_rejects_unmapped_tool`.
- **AC3** (model-id neutrality; no `model:`/`opus`/`sonnet` in any rendered
  `.agent.md`): `HostPackageTests::test_copilot_agents_carry_no_model_field_or_id`;
  `CopilotRenderUnitTests::test_render_copilot_agent_rejects_model_field`.
- **AC4** (judge's read-only tool set preserved; `[Read,Glob,Grep]` ->
  `[view,glob,grep]`, no create/edit/bash):
  `HostPackageTests::test_copilot_judge_agent_has_no_write_or_exec_tool`,
  `::test_copilot_agents_rendered_with_mapped_tools`;
  `CopilotRenderUnitTests::test_copilot_tool_names_preserves_order_for_read_only_subset`.
- **AC5** (drift + Claude/Codex unchanged): pre-existing
  `HostPackageTests::test_copilot_arm_leaves_claude_and_codex_byte_identical`
  (still green, untouched by this slice) + pre-existing
  `DriftTests::test_check_passes_in_sync_without_mutation`; manually
  confirmed via `build_host_packages.py --check` after regenerating (see
  Verification below).

### Deviations / interpretations
1. **Surgical edit, not rebuild-from-scratch (deviation from jig's
   `render_copilot_agent`).** jig's version reconstructs the whole
   frontmatter from parsed fields and re-serializes `description` via
   `json.dumps(...)` (a quoted YAML scalar). servo's `_render_copilot_agent`
   instead reuses this file's established "surgical replace" style
   (`_replace_name_line`, `_replace_description_field`): it locates and
   replaces only the `tools:` block, leaving `name:`/`description:`/body as
   literal, untouched bytes. Chosen because the task's own framing said
   "preserve `name`/`description`/body" (not "reformat them"), it matches
   this file's existing idiom more closely than jig's parse-and-rebuild
   approach, and it sidesteps a real hazard jig's approach doesn't hit:
   `json.dumps` would quote-and-escape servo's descriptions, which is an
   unforced formatting change for a field the AC says should be preserved.
   Net effect is identical to jig's for servo's two agents (no quoting was
   needed either way, since neither description contains YAML-reserved
   characters) — this is a mechanism deviation, not an output deviation.
2. **Model-neutrality enforced as a source-side raise, not silent
   omission.** Because rendering is surgical (fields other than `tools:`
   pass through unchanged), a `model:` field in a future source agent would
   otherwise leak into the rendered `.agent.md` untouched. `_render_copilot_agent`
   guards against this explicitly (raises `ValueError` if the source
   frontmatter matches `^model:`), rather than relying on "the source
   happens not to have one" — mutation-verified (see Verification). This is
   stricter than the AC's literal wording ("assert it stays absent," which
   could be read as test-side only) but matches the task's explicit ask for
   a "model-neutrality assert" as a guard, and mirrors this file's existing
   fail-loud stance for unmapped tools and residual `:` in skill names.
3. **`CLAUDE_TO_COPILOT_TOOLS` omits jig's `WebSearch→fetch` entry.** jig's
   map carries a 7th entry for a hook-only tool no jig agent's `tools:` list
   uses. servo's `runner.md`/`judge.md` use exactly `Read`, `Write`, `Edit`,
   `Bash`, `Glob`, `Grep` — all six are mapped; nothing else is used, so
   nothing else was added (avoids an unexercised, untested map entry).
4. **`validate_copilot_package` left functionally unchanged.** Its
   docstring's forward-reference to "slice 032-03's deliverable" was
   corrected to present tense, but its logic still does not check agent
   files (skills-only, as before). No AC in this slice requires extending
   it, and doing so unasked would be scope creep on a function this slice
   doesn't otherwise need to touch.

### Verification
- Targeted (`test_build_host_packages.py`): 46 passed, 52 subtests passed
  (13 new test methods; 2 use `subTest` over runner/judge, contributing 4 of
  the subtest count). Confirmed red before implementation (all 13 new tests
  failed/errored on `AttributeError`/`AssertionError` against the
  pre-slice code), green after.
- Mutation-verified both new guards, each restored immediately after:
  - Tools-map guard: replaced the `try/except KeyError→raise` in
    `_copilot_tool_names` with a silent `dict.get(tool, tool)` fallback →
    `test_copilot_tool_names_rejects_unmapped_tool` and
    `test_render_copilot_agent_rejects_unmapped_tool` both went red
    (`AssertionError: ValueError not raised`) → reverted, re-green.
  - Model-neutrality assert: removed the `re.search(r"^model:", ...)` raise
    from `_render_copilot_agent` →
    `test_render_copilot_agent_rejects_model_field` went red
    (`AssertionError: ValueError not raised`) → reverted, re-green.
- `build_host_packages.py` (regenerate): `OK: built Claude, Codex, and
  Copilot host packages`. `--check`: `OK: committed host packages are in
  sync with source.` `git status --porcelain hosts/`: only
  `?? hosts/copilot/.github/agents/` (untracked, new); no modified paths
  under `hosts/claude` or `hosts/codex` — byte-identical, also covered by
  the pre-existing `test_copilot_arm_leaves_claude_and_codex_byte_identical`.
- `ruff==0.15.17 ruff check scripts/`: all checks passed.
- Full venv suite (`pytest -q`, repo root): **1811 passed, 2 skipped, 101
  subtests passed** (438s) — up from slice-02's recorded 1798
  passed/97 subtests baseline by exactly the 13 new test methods/4 new
  subtests added here; the 2 skips are pre-existing (unrelated to this
  slice).

### Not in scope (later slices)
Oracle `Stop`→`agentStop` hook + adapter (032-04), execution-primitive
mapping (032-05), release zip / release-please / per-host smoke (032-06).
`validate_copilot_package` agent-file checks: not requested by this slice's
ACs; left as a residual for whichever later slice wants stronger static
validation of `.github/agents/`.
