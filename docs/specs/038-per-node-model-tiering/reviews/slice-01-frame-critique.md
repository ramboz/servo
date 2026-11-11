---
slice: 038-01 — per-iteration accounting
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-10T19:43:19Z
prompt_source: review.py frame-critique docs/specs/038-per-node-model-tiering/spec.md 038-01 (round 2)
---

VERDICT: pass

REASONING:
Round 2. Both round-1 assumptions are now probe-settled: `--max-budget-usd` is per-invocation (a two-turn resumed call under a $0.0025 cap succeeded against a $0.0032 session running total), and the AC3 identity held exactly on a multi-turn invocation (94,070 + 63,629 = 157,699). `cost_basis` + the fallback breadcrumb make a proof failure visible. The frame survives.

SPECIFIC ISSUES:
- [spec] "never under-counts" overstated: a same-id resume WITHOUT reloaded totals plus modelUsage-only advisor/subagent tokens could pass the proof — softened to "under the probed resume semantics" with the residual named (folded in).
- [spec] AC5 off-by-one: the --max-budget-usd value first differs at iteration 3 (folded in).
- [spec] AC3 did not say the snapshot persists in state.json (folded in).
- [spec] Advisor attribution best-effort (iterations = final API call only) — known residual, A1.
