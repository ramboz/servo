---
slice: 027-03 — custom-command capture provider
pass: implementation (compliance + craft)
verdict: pass
reviewer: jig:reviewer (in-session independent subagent, no build-conversation access)
reviewed_at: 2026-08-21
prompt_source: implementation review of commit 0c3723f against slice-03 ACs
---

VERDICT: pass — all six ACs satisfied; two test-tightness nits raised and FIXED
post-review (commit 6a28d94), not deferred.

Compliance (AC1–AC6):
- AC1: the command is invoked per screen as `[*capture.command, --screen <id>,
  --out <path>]`, cwd = eval dir, shot retained + ledger-linked by 027-01 plumbing.
- AC2: servo does NO seeding and NO cropping — the command provider runs no
  Playwright/preflight, reads no `setup`, post-processes nothing.
- AC3: fail-closed on non-zero/timeout/not-found/no-output AND on missing/empty
  `capture.command`, the latter surfaced up front in `score()` before the loop.
- AC4: ledger `capture_provider: "command"` + `capture_command` argv; null on
  non-command runs; `capture.command` not in `definition_hash`.
- AC5: an unattested command records `not_attested`, never a fake engine.
- AC6: web path unchanged; composite/freeze/env_error/0-1-2 intact.

Craft: `_run_capture_subprocess` extraction preserves the web provider's exact
error strings (`node`/`timed out`/`capture failed`); config threading through
`capture_app` keeps the 2-arg callers working; `capture.command` validated twice
(score() + `_capture_command_argv`).

Test-tightness nits (FIXED in 6a28d94):
- `test_command_spawn_shape` asserted flag membership, not order → tightened to pin
  the exact ordered `--screen <id> --out <path>` tail.
- `test_missing_command_fails_closed_before_capture` used a monkeypatch that never
  reached the module `_capture_main` loads → rewritten to drive `score.score()`
  directly (live guard), with a separate `test_missing_command_env_errors_through_main`
  for the rc-2/main() path.
