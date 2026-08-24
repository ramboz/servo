---
slice: 027-03 — custom-command capture provider
pass: compliance
verdict: pass
reviewer: jig:reviewer (in-session independent subagent, no build-conversation access)
reviewed_at: 2026-08-21
prompt_source: independent implementation review of commit 0c3723f against slice-03 ACs
---

PASS — all six ACs satisfied.

- AC1: the command is invoked per screen as `[*capture.command, --screen <id>,
  --out <path>]`, cwd = eval dir, shot retained + ledger-linked by 027-01 plumbing.
- AC2: servo does NO seeding and NO cropping — the command provider runs no
  Playwright/preflight, reads no `setup`, and post-processes nothing (ADR-0032
  §4/§5).
- AC3: fail-closed on non-zero/timeout/not-found/no-output AND on missing/empty
  `capture.command`, the latter surfaced up front in `score()` before the loop.
- AC4: ledger `capture_provider: "command"` + `capture_command` (resolved argv);
  null on non-command runs; `capture.command` not in `definition_hash`.
- AC5: an unattested command records per-screen `not_attested`, never a fake
  engine.
- AC6: web path unchanged; composite/freeze/env_error/0-1-2 intact.

Tests feature-bearing; `test_capture_command_not_in_definition_hash` is the one
regression-guard. `test_web_run_records_null_capture_command` is feature-bearing
(asserts `capture_command is None` → KeyError if the field is removed).
