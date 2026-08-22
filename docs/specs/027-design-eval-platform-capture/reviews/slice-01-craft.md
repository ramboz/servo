---
slice: 027-01 — shot retention + ledger visibility
pass: craft
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: independent implementation review of commit 52c0288 (craft pass)
---

PASS — no real defects.

- `_run_stamp()` collision across two back-to-back runs is not a real defect:
  microsecond resolution (`int((t % 1) * 1e6)`), and two full `score()` calls are
  separated by real work (freeze validation, per-screen capture + judge, ledger
  write), so distinct stamps are effectively guaranteed on darwin/linux. The
  localtime/fractional split is correct — the microsecond suffix comes from
  `t % 1`, timezone-independent.
- `run_id` threading and the `per_screen` 4→5 tuple change are internally
  consistent; no stale 4-tuple unpacking remains anywhere in the skill
  (grep-confirmed).
- Rationale for the unfrozen shot output is documented in-code and consistent with
  the DoR (shots are not part of the frozen definition; no ADR needed).
