---
adr: 0048
pass: frame-critique
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T20:05:42Z
prompt_source: review.py frame-critique docs/decisions/adr-0048-copilot-credit-budget-contract.md
---

VERDICT: needs-changes

REASONING:
Round 1. Direction holds (never-converted AI-credit brake enforced between invocations, fail-closed telemetry, mirrors the USD brake). The weak point was the overrun claim the owner is asked to accept ("one over-cap response plus compaction"): read off help text, not in the Assumptions ledger, not probed, plausibly wrong in count (parallel subagents share the cap) and size (crossing call is the run's largest context).

SPECIFIC ISSUES:
- [spec] Overrun bound unestablished -> A6 added; restated as k x per-call max; single-threaded worker (k=1); 041-01 AC6 measures overrun + concurrency; kill multiple stated (1x cap); Q1 merged with the missing-context-brake question.
- [spec] Kill criterion 1 contradicted the contract (session-delta and interrupted cases are already handled) -> rewritten: no report for completed runs / subagent+compaction omitted.
- [spec] Partial reports: derived check (modelMetrics tokens with zero credits) + kill arm when undetectable.
- [spec] Oracle/judge USD spend uncovered under Copilot -> part 5 refuses USD-priced oracle components by default (owner Q5).
- [spec] Lift clause silently dropped 034-03's "context" evidence and "hard in-flight bounds" -> now explicit.
- [spec] Probe authorization too small -> 150 AI credits with arithmetic.
