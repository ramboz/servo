---
slice: 041-01 — Copilot contract probe
pass: craft
verdict: pass
reviewer: jig:reviewer (subagent)
reviewed_at: 2026-11-12T00:03:21Z
prompt_source: Agent(jig:reviewer) craft review, delegated by build session
substrate: non-interactive
---

VERDICT: pass (nits addressed)

REASONING: clear write-up; every claim tied to a specific run/evidence file. The
A2 "two cost signals, different scopes" finding is genuinely valuable and
correctly framed as the Claude bug-007 analogue. Account-spend accounting
correctly sums per-invocation OTel new-credits, avoiding double-counting the
resumed session.

NITS RAISED AND RESOLUTION:
1. "Sigma per-call = totalNanoAiu exactly on every run" could be misread as
   per-invocation-file equality for the resumed run. FIXED: the Findings now
   state the session-level reconciliation explicitly (Run B OTel Σ 24.283 +
   prior snapshot 12.893 = usage 37.176).
2. AC5's span-token-vs-`modelMetrics` check was not explicitly recorded. FIXED:
   the Findings now cite the exact reconciliation (Run A 5249/98920,
   Run D 21287/157218 — matched).
3. ACs mis-numbered (7 before 6): left as authored — frame-reviewed AC block,
   cosmetic, content correct.
4. Per-run argv/caps were prose-only. FIXED: added `evidence/commands.md` with
   the exact invocations, caps and termination per run.

DEVIATIONS LOGGED (faithful, beneficial): `aiCreditsStatus` re-scoped as the
PRIMARY partial gate (ADR part 3 assumed no self-marker existed); subagent
control is `--fleet` omission, not a tool-denial flag (ADR part 2 wording
superseded). Both are recorded in the slice Findings and ADR-0048 A6.
