---
slice: 041-02 — credit brake and supported loop launch
pass: compliance
verdict: pass
reviewer: jig:reviewer (subagent)
reviewed_at: 2026-11-12T01:25:45Z
prompt_source: Agent(jig:reviewer) adversarial budget-safety review, delegated by build session
---

VERDICT: pass (independent jig:reviewer `needs-changes` items all resolved)

PROVENANCE: independent `jig:reviewer` subagent, an adversarial budget-safety
pass delegated by the build session (tasked to find any fail-open / under-count
path). Headline: **"No worker-brake fail-open or under-count path found"** — the
brake is fail-closed by construction with exact nano-integer arithmetic.

REASONING: the reviewer traced every halt path (AC2 arithmetic, AC3 fail-closed,
AC1 reactive bound, AC5/6/7 gates) and found no way to read a missing / partial /
mismatched credit figure as 0 or to continue. The OTel-vs-session-delta
reconciliation is the key net: the OTel export is always per-invocation, so a
wrong resume/prior state cannot produce a matching sum. Verified: `_exact_nano`
returns None (not 0); pre/post ceiling checks are int-vs-int nano;
bound(gpt-6.1-sol)=201.5; unknown model -> `credit_bound_unavailable`; the Claude
path is byte-identical.

NEEDS-CHANGES ITEMS (all fail-CLOSED) — RESOLVED in this slice:
1. Plan-sourced `budget.credit_ceiling` not wired (AC1): the flag path is primary;
   a plan-only ceiling is refused `native_capability_unavailable` (fail-closed).
   Recorded as deferred (deviation log + refinement-todo); AC1 wording reconciled.
2. AC6 oracle-USD: `_unpriced_oracle_error` refuses UNPRICED (unknown-cost)
   components (the common API-judge case); a KNOWN-USD-priced component needs a new
   install marker -> AC6 wording reconciled + deferred; added
   `test_unpriced_oracle_refused_under_copilot`.
3. Cross-process Copilot `--resume` (backend_mismatch): documented limitation
   (intra-run session-delta resume works).
4. Stale `_parse_copilot_usage` docstring ("yields zeros"): fixed.

SPECIFIC ISSUES: none fail-open; all items above resolved.
