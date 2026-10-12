# Capability compliance, initial verdict (2026-10-12)

Independent `jig:reviewer` delivery-guard-compliance returned **needs-changes**
for 034-02. Valid native launches already refused before dispatch/mutation,
schema2/null output and bounded legacy compatibility were correct.

Two concrete blockers:

1. Resume predicate preferred backend over host, so `backend: claude` could hide
   `host: copilot`. Check both fields independently; reject before probing/writes.
2. `_build_goal_state` omitted backend from new Claude goal/background state.
   Add identity to that shared construction path.

Both regressions were witnessed red, corrected, and the independent narrow
state-identity-recheck returned **pass**. Full existing loop then passed
402 tests and 17 subtests. No historical state was migrated.
