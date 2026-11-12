---
status: DRAFT
kind: feature
dependencies: [042-03, 041-02]
last_verified:
arch_review: true
frame_review: true
---

## Slice 042-04 — host-driven verified-wrapped

**Goal:** In host-driven **verified-wrapped** mode, the host-spawned worker runs
its item under `loop.py`, and `campaign record` accepts it as `wrapped` only
when the run is **verified**: a `loop.py` run id exists in the item's worktree,
the worktree's content fingerprint equals the one the loop recorded at halt, and
the loop started at the brief's base sha without `--allow-dirty`. The outcome is
re-rendered from the loop's `state.json`; anything that fails verification is
downgraded to advisory. This is the tier that bounds the loop's own spend on
Copilot (the recorded runaway), so it ships in the parity release.

**DoR:**
- 042-03 is DONE (advisory record + briefs).
- Spec 041 is DONE — `loop.py --host copilot` runs under the credit brake
  (041-02), so a Copilot worker can be wrapped (ADR-0043 is no longer a block).

**Acceptance Criteria:**

1. **`loop.py` records a content fingerprint at halt** in `state.json`: the HEAD
   sha at halt, a hash of the working-tree diff against that HEAD, and the
   contents of untracked, non-ignored files. Bookkeeping paths (`.servo/`,
   caches) are excluded. All of it comes from read-only git queries. The loop
   also records the HEAD sha it saw at start.
2. `campaign record <id> <item> --tier wrapped` accepts the item as `wrapped`
   **iff all** hold, else it is recorded as advisory (`self_reported`):
   - a `loop.py` state with the forwarded `run_id` exists in the item's
     worktree;
   - the worktree's recomputed content fingerprint equals the loop's recorded
     halt fingerprint;
   - the loop's recorded start HEAD equals the item's base sha from the kickoff
     brief, and `--allow-dirty` was not set.
3. **Record before commit.** If HEAD has moved since the halt (the worker
   committed first), the item cannot be verified and is recorded as advisory.
   The kickoff brief states the record-before-commit order.
4. **The record is re-rendered from the loop's state.** For a verified item,
   `result`, `rung`, iterations and cost come from that run's `state.json`; the
   forwarded line is used only to locate the run, and its own field values are
   never trusted.
5. A post-halt edit to a file the loop already changed alters the fingerprint
   (it is content, not a `git status` porcelain set), so it fails verification
   and downgrades to advisory.
6. Verified `wrapped` cost counts as enforced spend in the aggregate ceiling;
   the worker **session's** own spend, and any edits after the loop halts, stay
   outside every ceiling (wrapped binds the `loop.py` subprocess, not the
   session above it). `campaign status` states this boundary.

**DoD:** ACs pass with tests (fingerprint computed from a real git worktree, not
a mock; verification and downgrade paths covered); compliance + craft + arch
reviews; reconciliation. On Copilot, an end-to-end wrapped run is exercised
against spec 041's brake.

**Anti-horizontal-phasing check:** a host spawns a Copilot worker, servo
verifies from the loop's own state that the recorded work happened inside the
braked loop at the declared base, and the ledger carries an enforced-spend row —
the recorded runaway is now bounded on the motivating host.

## Assumptions

- **A5 (worker compliance):** a host-spawned worker actually runs its item under
  `loop.py`, stops when the loop halts, and forwards the loop's line unchanged.
  Verification detects non-compliance after the fact; it cannot prevent it. Kill
  criterion: under ~80% of a host's wrapped items verifying, treat that host as
  advisory-only.
