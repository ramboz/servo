---
slice: 041-01 — Copilot contract probe
pass: compliance
verdict: pass
reviewer: jig:reviewer (subagent)
reviewed_at: 2026-11-12T00:03:21Z
prompt_source: Agent(jig:reviewer) independent evidence re-derivation, delegated by build session
---

VERDICT: pass

PROVENANCE: independent `jig:reviewer` subagent (read-only Read/Glob/Grep),
delegated by the build session. The reviewer re-derived every numeric claim from
the raw JSON/JSONL evidence, not from the author's conclusions. `kind: spike`
research slice — compliance checks the spike ACs and evidence fidelity, not test
coverage (015-05 precedent).

REASONING: all seven numeric checks reconcile EXACTLY at the nano level.
- A2: run-a 12,893,040,000 + run-b per-invocation OTel Σ 24,282,650,000 =
  run-b usage 37,175,690,000 (usage report is session-cumulative; the cap is
  invocation-scoped, corroborated by the Run B vs Run D cap contrast).
- A5: run-a 4 `chat` spans sum to totalNanoAiu exactly; `aiCreditsStatus` present
  ("complete"); span token sums match `modelMetrics` (run-a 5249/98920,
  run-d 21287/157218).
- A6: run-d 31.005 cr vs cap 30 -> overrun 1.005; spans strictly non-overlapping
  (c=0 observed); `agentMetrics` holds only `main`.
- A3: run-c usage file 0 bytes; OTel has partial spend; no `invoke_agent` root.
- Prices/bound: run-d call-1 prediction matches to ~0.0006 cr; 272000x250/1e6=68;
  (1+1)x(81..101)=162..202.
- Redaction: zero ramboz/julien/home hits; sensitive attrs `<redacted>`.
- Outcome: no ADR-0048 kill criterion fired -> `041-02 unblocked`.
CLI-help grounding verified (billing/limits/parallel-work). Account spend
85.013 cr <= 150 authorized.

SPECIFIC ISSUES: none affecting correctness.
