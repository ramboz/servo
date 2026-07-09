# Bug Status Board

| ID | slug | severity | tier | status | reproduces? | regression test | claimed_by | escalated_to | Notes |
|----|------|----------|------|--------|-------------|-----------------|------------|--------------|-------|
| 001 | agent-loop-masks-auth-error-as-plateau | high | standard | DONE | yes | skills/agent-loop/test_loop.py::ClaudeErrorEnvelopeTests | main |  |  |
| 002 | agent-loop-no-permission-mode | high | standard | DONE | yes | skills/agent-loop/test_loop.py::LoopForwardsTargetSettingsTests | main |  |  |
| 003 | spec-oracle-parser-zero-acs-on-preamble | medium | standard | DONE | yes | skills/spec-oracle/test_oracle_plan.py::ACPreambleToleranceTests | main |  |  |
| 004 | goal-driver-masks-errors-and-drops-settings | medium | standard | DONE | yes | skills/agent-loop/test_loop.py::GoalDriverParityTests | claude/festive-payne-860961 |  |  |
| 005 | evaluation-model-stale-overlay-path | medium | standard | DONE | yes | skills/execution-planner/test_execution_plan.py::PlanShapeTests::test_evaluation_model_from_colocated_overlay | claude/actionable-specs-adrs-b28ed5 |  |  |
