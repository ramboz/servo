---
status: DRAFT
dependencies: [028-01, adr-0034]
last_verified:
# arch_review: true  # adds the Copilot host renderer + dispatch wiring
---

## Slice 028-02 — renderer-and-skeleton

**Goal:** A Copilot user can install servo and invoke its skills — the walking
skeleton: a Copilot host renderer wired into servo's builder that emits a minimal
committed `hosts/copilot/` whose skills and instructions load under Copilot CLI.

**DoR:**
- ✅ 028-01 done: verified plugin-manifest shape, skill discovery root, and the
  namespace/description loader rules.

**Acceptance Criteria:**

1. **Renderer + dispatch.** A Copilot host renderer exists and servo's host
   builder resolves it alongside the Claude/Codex renderers; Claude/Codex output
   is unchanged.
2. **Loader-compat invariant.** Every emitted Copilot skill has a namespace-safe
   name (no `:`) and a description ≤1024 chars, full text preserved in the body;
   a source skill that would violate either is transformed by the render layer,
   not the source. A test proves an over-limit description renders ≤1024 for
   Copilot while Claude/Codex stay byte-unchanged.
3. **Instructions rendered.** `hosts/copilot/.github/copilot-instructions.md` is
   generated from canonical source without double-loading against the `CLAUDE.md`
   Copilot also reads.
4. **Skeleton installs + runs.** The rendered package installs in a Copilot
   session (or deterministic substitute, recorded honestly) and at least one
   servo skill loads and is invocable.

**DoD:**
- [ ] All ACs pass; full suite green; new tests fail when the feature is removed.
- [ ] Claude/Codex host output unchanged (drift guard clean for those hosts).
- [ ] Reviewed by `reviewer` subagent (compliance + craft; arch pass).
- [ ] Deviation log + reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice a Copilot user installs servo
and runs a skill — observable end-to-end value.
