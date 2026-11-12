---
status: DRAFT
kind: feature
dependencies: [042-02]
last_verified:
arch_review: false
frame_review: true
---

## Slice 042-06 — wave integration-review brief

**Goal:** Before a wave's PRs go out, `campaign review <id>` emits one
fresh-context integration-review brief over the wave's diffs — a single brief
servo produces, not a reviewer it runs. Running the reviewer is the host's or
jig's job (ADR-0049 A3).

**DoR:**
- 042-02 is DONE (a "wave" is the set of items a coordinator dispatched and
  recorded).

**Acceptance Criteria:**

1. `campaign review <id>` collects the diffs of the wave's recorded items (their
   worktrees against their base shas) and emits one brief that asks a fresh
   reviewer to look across the wave for integration problems the per-item oracle
   can't see (cross-item API drift, duplicated or conflicting changes).
2. The brief is host-agnostic text written to a file or stdout; servo does not
   spawn or run a reviewer, and does no git operations beyond read-only diff
   queries.
3. The brief names each item, its outcome and its diff range, so the reviewer
   has the wave's scope without servo summarising the changes for it.
4. `campaign review` is read-only on the ledger and worktrees; it records
   nothing and merges nothing.

**DoD:** ACs pass with tests; compliance + craft reviews (no arch — emits a
brief, changes no contract); reconciliation.

**Anti-horizontal-phasing check:** after a wave finishes, a human gets one
review brief spanning all the wave's diffs and hands it to a fresh reviewer
before any PR publishes — the cross-PR check the recorded run did by hand.

## Assumptions

- **A3 (integration review as an emitted brief):** the integration review is
  useful as a step servo emits — a brief — not one it runs. Unverified;
  running a reviewer is the host's or jig's job.
