---
status: DEFERRED
dependencies: [031-02]
last_verified:
---

## Slice 031-03 — goal-driver-advisory-preflight

**Goal:** Give the **goal driver** an optional best-effort *ex-ante* capability
check that can refuse *before* spending the goal budget when a permission wall is
confidently detectable — strictly **advisory and fail-open** (a confident denial
refuses early; anything uncertain proceeds to the 031-02 post-hoc relabel), so it
can never block a capable run.

**Resolution trigger:** Field data shows walled **goal-driver** runs waste
meaningful budget before their terminal halt (i.e., the 031-02 post-hoc relabel,
which fires only after the single goal run completes, is measured to be too
late for the goal driver's single-long-invocation cost profile). Per
[ADR-0037](../../decisions/adr-0037-agent-loop-permission-preflight.md) Open
Question 1, v1 ships the post-hoc relabel only and defers this optimization until
that waste is measured.

**Why DEFERRED (not built now):** The 031-01/02 post-hoc relabel already closes
the *diagnosis* hole for both drivers (correct terminal reason + fix breadcrumb).
This advisory is a pure goal-budget *cost* optimization and reintroduces the
resolution-fidelity complexity ADR-0037 spent four frame-critique rounds
containing (an ex-ante check must model `claude -p`'s real permission resolution).
Keeping it advisory/fail-open bounds the risk, but the value is unproven until
goal-driver pre-halt waste is observed in the field. Building it now would be
speculative.

**Acceptance Criteria (sketch — to be refined on re-open):**

1. Before `_invoke_claude_goal` spends, a best-effort capability probe runs; on a
   **confident** denial it refuses early with `edit_permission_unavailable` + the
   breadcrumb (no goal budget spent).
2. The check is **fail-open**: any uncertainty (probe inconclusive, non-git
   target, resolution ambiguity) proceeds to the goal run and the 031-02 post-hoc
   relabel. It never blocks a run on its own → no false-negative regression.
3. The advisory path is covered by tests including an explicit "uncertain →
   proceed" case proving it cannot block a capable run.

**DoD (on re-open):** standard — ACs pass, suite green, ruff clean, guards
mutation-checked, review passed.
