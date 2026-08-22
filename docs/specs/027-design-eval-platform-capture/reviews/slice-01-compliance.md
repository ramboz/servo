---
slice: 027-01 — shot retention + ledger visibility
pass: compliance
verdict: pass
reviewer: jig:reviewer (in-session independent subagent, no build-conversation access)
reviewed_at: 2026-08-21
prompt_source: independent implementation review of commit 52c0288 against slice-01 ACs
---

PASS — all four ACs satisfied.

- AC1 (runs no longer clobber): `score.py` stamps `app-{id}-{stamp}.png` with one
  shared `run_id` per run; `ShotRetentionTests.test_shots_are_not_clobbered_across_runs`
  asserts ≥2 retained home shots — red if the fixed filename is restored.
- AC2 (ledger points at the judged shot): the per-screen row carries `shot` =
  `relative_to(base_dir).as_posix()`; the test asserts the path resolves to a real
  file, red if the field is dropped.
- AC3 (no capture → null): `shot = None` on the fake-scores arm; `assertIsNone`.
- AC4 (additive): composite math, `validate_freeze`, and the EnvError branches
  unchanged; the change is a stamped filename + one new per-screen ledger field.

DoR coupling honored: the stamped name stays directly under `shots/`, so
`_judge_cli`'s `cwd = app_png.parent.parent` still resolves to `base_dir`
(verified by `test_shots_stay_one_dir_under_base_for_the_cli_judge_cwd`). Each
new test was shown red before implementation (3 failures + 1 error) → green after.
