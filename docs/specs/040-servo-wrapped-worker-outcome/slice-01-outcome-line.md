---
status: DRAFT
kind: feature
dependencies: [038-03]
last_verified:
---

## Slice 040-01 — outcome line

**Goal:** `loop.py --outcome-line <path|->` writes one typed outcome record that
a host-spawned worker can forward to its orchestrator in place of a narrative.

**DoR:**
- Activation trigger in spec 040 met.
- loop.py's terminal-reason taxonomy enumerated, and the mapping to
  `passed|plateau|blocked|budget|error` agreed (A2).

**Acceptance Criteria (sketch):**

1. With `--outcome-line`, the loop writes exactly one JSON object
   (`servo_outcome: 1`) after its summary, to the path or stdout. Without the
   flag, output is byte-identical.
2. `result` is derived only from the summary:
   - `oracle_passed` / `oracle_pass` → `passed`;
   - `oracle_plateau` → `plateau`, with `rung`/`rungs` from spec 038;
   - `cost_ceiling_reached` / `max_iterations_reached` / `context_full` →
     `budget`;
   - `edit_permission_unavailable` / `dirty_tree` / readiness refusals →
     `blocked`;
   - every other reason → `error`.

   The original `terminal_reason` is kept as `reason`.
3. `cost_usd` is the run's `cumulative_cost_usd`, which spec 038 made accurate.
4. Both drivers emit it. The goal driver reports `rung: 0`.
5. Documentation shows a host forwarding the line (Claude Code example) and
   states the no-crew boundary.

**DoD:** ACs pass; reviews per spec-workflow.

**Anti-horizontal-phasing check:** a campaign coordinator receives one line per
worker (passed / plateau@rung / blocked, plus cost) instead of a message
thread.
