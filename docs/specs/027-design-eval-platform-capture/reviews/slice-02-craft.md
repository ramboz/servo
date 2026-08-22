---
slice: 027-02 — capture-provider seam + web default
pass: craft
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: independent implementation review of commit a6950a2 (craft pass)
---

PASS — no blocking defects; three non-defect observations, dispositioned.

- The judge-transport key check (missing `ANTHROPIC_API_KEY` / `claude` bin) runs
  BEFORE provider validation, so a run with both a missing key and an unknown
  provider surfaces the key error first. Both are env_error rc 2, so AC4's
  "before any preflight/capture" still holds; ordering is not spec-constrained.
  Not a defect.
- The fake-scores arm leaves `provider = None` and never validates the transport,
  so an unknown provider combined with `SERVO_DESIGN_EVAL_FAKE_SCORES` is not
  caught. Consistent with AC4 ("before any per-screen capture" — no capture runs)
  and AC5 (fake arm records `null`). By design; fake-scores is the offline/test
  hook.
- The AC4 test is double-guarded (both `score()` and `capture_app` validate), so
  it proves fail-closed but does not ISOLATE the "before preflight" ordering.
  Honest classification: feature-driven, but weaker than the other five.

The registry/dispatch design and the required keyword-only `provider` on `_ledger`
(no caller can silently omit it) are sound.
