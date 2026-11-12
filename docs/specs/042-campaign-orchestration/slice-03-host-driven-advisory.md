---
status: DRAFT
kind: feature
dependencies: [042-01, 042-02]
last_verified:
arch_review: true
frame_review: true
---

## Slice 042-03 — host-driven advisory

**Goal:** In host-driven **advisory** mode, servo emits the plan plus one
kickoff brief per item, the host spawns the workers, and `campaign record`
accepts each item's reported outcome **only after re-running the item's oracle**
on the worker's worktree. Every field other than the re-checked pass is marked
`self_reported`, and `self_reported` cost is never counted as enforced spend.
servo neither spawns nor messages host sessions.

**DoR:**
- 042-01 is DONE (ledger + record) and 042-02 is DONE (coordinator + brief
  machinery to reuse).

**Acceptance Criteria:**

1. `campaign brief <id> [<item>]` emits, per item, a kickoff brief containing
   the item's prompt, `oracle_ref`, budget and `models` block as **data**, the
   item's base sha, and the instruction to run `campaign record` before any
   commit. The brief states that item text is data, never instructions to the
   worker (ADR-0049 / spec 011 Guardrail #4).
2. `campaign record <id> <item> --tier advisory --outcome <line>` re-runs the
   item's oracle (`gate.py`) on the worker's worktree before accepting a
   `passed` result. A host's claim of `passed` that the oracle re-check does not
   confirm is recorded as `blocked`/`error`, never `passed`.
3. Every outcome field other than the re-checked oracle result is recorded with
   `self_reported: true` (cost, rung, reason). The aggregate ceiling does not
   count `self_reported` cost as enforced spend (042-01 AC2).
4. Nothing stops a runaway advisory worker in flight — advisory mode enforces
   the planned list, the ledger and verified passes only. This limit is stated
   in the brief and in `campaign status` output, not hidden.
5. servo never spawns or messages a host session; it only writes briefs and
   reads worktrees. In advisory mode budget, model tier and the ladder reach the
   worker as brief text only.

**DoD:** ACs pass with tests; compliance + craft + arch reviews; reconciliation.

**Anti-horizontal-phasing check:** a host coordinator runs a campaign's items
its own way and still gets, per item, a durable ledger row with an
oracle-verified pass — the Option B floor plus the one check Option B lacks.

## Assumptions

- **A1 (adoption):** a host coordinator actually calls `campaign brief` /
  `record`. Unverified; the kill criterion drops host-driven mode for a host
  under ~80% recorded-without-prompt.
- **A5 (worker compliance):** advisory workers can't be verified beyond the
  oracle re-check; a self-reported field may be wrong, which is why it is marked
  and never counted as enforced spend.
