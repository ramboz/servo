---
status: DRAFT
dependencies: [028-03, 028-04]
last_verified:
# arch_review: true  # maps Claude-only execution primitives onto Copilot; ADR-0028 residual
---

## Slice 028-05 — execution-primitive-mapping

**Goal:** servo's *optional* unattended loop/oracle runs under Copilot — the
Claude-specific execution primitives ADR-0028 carved out are mapped to their
Copilot equivalents where one exists, and any true residual is recorded honestly.

**DoR:**
- ✅ 028-03 done (a Copilot `runner` agent exists).
- ✅ 028-04 done (`agentStop` translation proven).
- ✅ 028-01 recorded the Autopilot oracle-gate verdict and the `copilot -p -s`
  permission-model differences.

**Acceptance Criteria:**

1. **`claude -p`→`copilot -p -s`.** Where servo subprocesses `claude -p --agent
   runner`, the Copilot rendering invokes `copilot -p -s --agent runner` (or the
   verified equivalent). A test asserts the Copilot rendering emits the Copilot
   command form, not the Claude one.
2. **`/goal`→Autopilot, honestly.** The long-running loop maps to
   `copilot --autopilot … --max-ai-credits N` **iff** 028-01 confirmed Autopilot
   can honor servo's oracle-gated stop; if it cannot, this slice records the loop
   as a documented **residual** (Claude-only under Copilot) rather than shipping a
   loop that runs past its oracle. Either outcome is captured explicitly.
3. **Preflight → Copilot permissions.** The ADR-0033 headless edit-permission
   preflight is expressed via Copilot's permission controls
   (`--allow-tool`/`--deny-tool` / Assisted approvals), or recorded as residual.
4. **Residual recorded.** Any primitive that does not port is listed in the
   ADR-0028-style inventory (extends 028-04's), never silently renamed.

**DoD:**
- [ ] All ACs pass; full suite green; new tests fail when the feature is removed.
- [ ] The Autopilot/loop verdict and any residual documented in architecture.md.
- [ ] Reviewed by `reviewer` subagent (compliance + craft; arch pass).
- [ ] Deviation log + reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice a Copilot user can run servo's
(mapped) unattended loop — or knows precisely what stays Claude-only and why.
