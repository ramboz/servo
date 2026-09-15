---
status: DRAFT
dependencies: [028-02]
last_verified:
# arch_review: true  # introduces the hook-protocol translation layer
---

## Slice 028-04 — hooks

**Goal:** servo's hooks fire under Copilot — the oracle `Stop` and any
quality-gate hooks translated onto Copilot's event model and emitted as
`.github/hooks/*.json`, with every hook mapped or explicitly recorded as
unmappable.

**DoR:**
- ✅ 028-02 done (renderer + skeleton).
- ✅ 028-01 recorded the Copilot hook JSON schema and the `Stop`→`agentStop`
  behavior.

**Acceptance Criteria:**

1. **Event + payload translation.** The renderer maps servo's Claude hook events
   to Copilot camelCase (notably `Stop`→`agentStop`) and adapts the payload/field
   access the hook scripts read. A test asserts a translated hook emits
   Copilot-shaped JSON.
2. **Oracle Stop hook ports.** servo's oracle-gate `Stop` behavior is emitted as a
   Copilot `agentStop` hook and fires in a Copilot session (or deterministic
   substitute).
3. **Mapped-or-unmappable inventory (invariant).** Every servo hook is either
   mapped with equivalent enforcement or recorded as unmappable with the residual
   documented (ADR-0028's honesty invariant). No hook silently dropped or
   mechanically renamed.

**DoD:**
- [ ] All ACs pass; full suite green; new tests fail when the feature is removed.
- [ ] Inventory written where a maintainer will find it (architecture.md and/or
      the slice); residuals cross-linked to refinement-todo if follow-up remains.
- [ ] Reviewed by `reviewer` subagent (compliance + craft; arch pass).
- [ ] Deviation log + reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice servo's oracle/quality gates
work for a Copilot user (or are documented as degraded).
