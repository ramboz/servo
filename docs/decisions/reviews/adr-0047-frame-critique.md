---
adr: 0047
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-10T19:46:32Z
prompt_source: review.py frame-critique docs/decisions/adr-0047-per-node-model-tiering-and-escalation-ladder.md (round 2)
---

VERDICT: pass

REASONING:
Round 2. The round-1 primary is fixed: the fair-window guard stops a ladder from turning a plateau into a budget halt under default sizing (worked example 4/7/11 verified against _check_plateau's window+1 rule), and D5 catches brake-truncated ladders. D2-A's new grounding holds (agent-switch cache miss is expected when the tool list differs). The frame survives; notes folded in before Accepted.

SPECIFIC ISSUES:
- [spec] Kill-criterion denominator assumed every escalated run had a fair trial; cost could starve top rungs. Folded in: cost condition added to the guard; escalated runs bucketed converted / fair failure / cut short, cut-short excluded from the rate.
- [spec] D5 narrower than its rationale (invocation failure / verdict mismatch at a rung fell to sticky tried). Folded in: both quarantine and stop the pass rc=2.
- [spec] spec.md still said clamp-never-loosen (fixed).
- [spec] A1 "mirrors" overstated -> "partly mirrors" (stuck tree carried over).
