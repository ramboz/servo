---
slice: 027-01 — shot retention + ledger visibility
pass: implementation (compliance + craft)
verdict: pass
reviewer: jig:reviewer (in-session independent subagent, no build-conversation access)
reviewed_at: 2026-08-21
prompt_source: implementation review of commit 52c0288 against slice-01 ACs
---

VERDICT: pass — all four ACs satisfied, no blocking issues.

Compliance (AC1–AC4):
- AC1 (no clobber): `score.py` `app-{id}-{stamp}.png` with one shared `run_id` per
  run; `ShotRetentionTests.test_shots_are_not_clobbered_across_runs` asserts ≥2
  retained home shots — goes red if the fixed filename is restored.
- AC2 (ledger points at judged shot): `relative_to(base_dir).as_posix()`; the test
  asserts the path resolves to a real file, red if the field is dropped.
- AC3 (no capture → null): `shot = None` on the fake arm; `assertIsNone` test.
- AC4 (additive): composite math, `validate_freeze`, and the EnvError branches
  unchanged.

DoR coupling honored: the stamped name stays directly under `shots/`, so
`_judge_cli`'s `cwd=app_png.parent.parent` still resolves to `base_dir` (verified
by the dedicated `test_shots_stay_one_dir_under_base_for_the_cli_judge_cwd`).

Craft: `_run_stamp()` collision across two back-to-back runs is not a real defect
(microsecond resolution, real work between runs). `run_id` threading and the 4→5
`per_screen` tuple change are internally consistent; no stale 4-tuple unpacking
remains (grep-confirmed).

Note: the pre-existing `CaptureLibNodeTests.test_capture_lib_node_suite_passes`
failure is a Node output-format mismatch independent of this slice (commit
52c0288 touches only `score.py`). [Later fixed on-branch by pinning the TAP
reporter — see `reviews/node-suite-reporter-fix.md`.]
