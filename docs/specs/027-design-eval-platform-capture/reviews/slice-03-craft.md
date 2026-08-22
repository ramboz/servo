---
slice: 027-03 — custom-command capture provider
pass: craft
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: independent implementation review of commit 0c3723f (craft pass)
---

PASS on the code; two tests did not enforce their claim and were FIXED before DONE
(commit 6a28d94), not deferred.

- `_run_capture_subprocess` extraction preserves the web provider's exact error
  substrings (`node` / `timed out` / `capture failed`) that the pre-existing
  `CaptureAppHonestyTests` assert; config threading through `capture_app`'s 4th/5th
  params keeps the 2-arg callers working; `capture.command` is validated twice
  (score() + `_capture_command_argv`, defence in depth).

Nits (fixed):
1. `test_command_spawn_shape` asserted flag MEMBERSHIP, not ORDER → tightened to
   pin the exact ordered tail `… --screen <id> --out <path>.png`.
2. `test_missing_command_fails_closed_before_capture` used a monkeypatch that never
   reached the module `_capture_main` loads (a fresh score.py copy) → rewritten to
   drive `score.score()` directly so the "no capture before validation" guard is
   live, with a separate `test_missing_command_env_errors_through_main` retaining
   the rc-2/main() honesty check. (8 → 9 tests.)
