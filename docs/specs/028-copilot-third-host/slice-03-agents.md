---
status: DRAFT
dependencies: [028-02]
last_verified:
---

## Slice 028-03 — agents

**Goal:** servo's agents — notably the loop `runner`, plus any review roster —
render as Copilot custom agents under `.github/agents/`, so the mapped loop
(028-05) has a Copilot `runner` to invoke.

**DoR:**
- ✅ 028-02 done (renderer + skeleton).
- ✅ 028-01 finding fixed the agent file form and honored frontmatter fields.

**Acceptance Criteria:**

1. **Agents rendered.** Each servo source agent renders to the verified Copilot
   agent form under `hosts/copilot/.github/agents/`, frontmatter mapped to the
   fields Copilot honors (tools, description, edit/read-only posture).
2. **Model-id neutrality.** No rendered agent hard-codes `opus`/`sonnet`; model
   selection defers to Copilot's `/model`. A test asserts no Claude-specific model
   id leaks into Copilot agent output.
3. **`runner` present for the loop.** The loop `runner` agent exists in the
   Copilot rendering so `copilot -p --agent runner` (028-05) can resolve it.

**DoD:**
- [ ] All ACs pass; full suite green; new tests fail when the feature is removed.
- [ ] Reviewed by `reviewer` subagent (compliance + craft).
- [ ] Deviation log + reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice a Copilot user can invoke
servo's agents — new end-to-end capability.
