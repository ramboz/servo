---
status: DRAFT
kind: spike
dependencies: [adr-0034]
last_verified:
---

## Slice 028-01 — copilot-contract-spike

**Goal:** Resolve the external Copilot-owned unknowns — both the shared
install/skill/hook/agent contract and servo's execution-primitive mappings — so
the rendering and loop-mapping slices commit to a verified shape.

**Question:** What contract must servo's committed `hosts/copilot/` present to
install via `/plugin` and load skills/agents/hooks, and do the guide's
execution-primitive mappings (`claude -p`→`copilot -p -s`, `Stop`→`agentStop`,
`/goal`→Autopilot, ADR-0033 preflight→Copilot permissions) actually hold — in
particular, can **Autopilot express an oracle-gated stop**, not just a turn cap?

**Time-box:** 1 day.

**Findings:** _Filled during IN_PROGRESS._

**Outcome:** _Set at DONE — e.g. `spec 028-02..06 unblocked; ADR-0034 open
questions resolved` (or `ADR-0034 amended` if a mapping fails)._

**DoR:**
- ✅ ADR-0034 recorded (Proposed).
- ✅ Access to a licensed Copilot CLI session + GitHub's Copilot hooks/agents/CLI
  reference docs. (Coordinate with jig spec 113-01 to avoid duplicate probing of
  the *shared* contract.)

**Acceptance Criteria:**

1. **Shared contract verified.** Plugin-manifest shape for `/plugin`, skill
   discovery roots, the `:`/>1024 loader rules, agent file form, and the Copilot
   hook JSON schema (event names + payload + allow/deny shape) — each recorded
   with commands run + output. (May cite jig 113-01 where identical.)
2. **`Stop`→`agentStop` verified.** The oracle's Claude `Stop` hook behavior is
   reproduced with a Copilot `agentStop` hook in a live session (or the gap
   recorded).
3. **Autopilot oracle-gate question answered.** Record whether
   `copilot --autopilot` can stop on an **eval/oracle** condition (as servo's
   `/goal` loop needs) or only on a turn/credit cap — the load-bearing finding for
   028-05.
4. **`claude -p`→`copilot -p -s` verified.** A non-interactive `copilot -p -s`
   run with an `--agent` is exercised; permission-model differences (vs ADR-0033's
   preflight) are recorded.
5. **ADR-0034 open questions dispositioned.** Each answered or explicitly carried
   forward; a mapping that fails raises an amendment note, not a silent absorb.

**DoD:**
- [ ] Findings filled with commands + observed output (grounding).
- [ ] Outcome set; 028-02..06 DoR updated with the verified shape; 028-05 DoR
      records the Autopilot verdict.
- [ ] `docs/refinement-todo.md` updated for any deferred decision.

**Anti-horizontal-phasing check:** Exempt — `kind: spike`. Unblocks 028-02..06.
