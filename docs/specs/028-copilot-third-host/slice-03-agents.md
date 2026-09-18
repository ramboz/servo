---
status: IN_PROGRESS
dependencies: [028-02]
last_verified:
---

## Slice 028-03 — agents

**Goal:** servo's agents (`runner`, `judge`) render as Copilot custom agents under
`hosts/copilot/.github/agents/<name>.agent.md`, so the mapped loop (028-05) has a
Copilot `runner`/`judge` to invoke — mirroring jig's `render_copilot_agent`.

**DoR:**
- ✅ 028-02 done (Copilot renderer + package skeleton; `build_all` copilot arm).
- ✅ 028-01 fixed the agent file form (`.agent.md`, frontmatter fields Copilot
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
- [ ] All ACs pass; full suite green (venv pytest); new tests fail when the feature is removed.
- [ ] `--check` clean; Claude/Codex byte-unchanged.
- [ ] Reviewed by `reviewer` subagent (compliance + craft).
- [ ] Deviation log + reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice a Copilot user can invoke
servo's `runner`/`judge` agents — new end-to-end capability, and 028-05's
`copilot -p --agent runner` can resolve.
