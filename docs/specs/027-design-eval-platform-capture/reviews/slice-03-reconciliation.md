---
slice: 027-03 — custom-command capture provider
pass: reconciliation
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: reconciliation review of the deviation log / sweep / DoD vs disk
---

VERDICT: pass — reconciliation artifacts faithful; one caveat-accuracy nit raised
and FIXED.

Deviation-log honesty: matches `score.py` line-for-line — the shared
`_run_capture_subprocess`, the widened `(base_dir, screen, run_id, config)` provider
signature, `capture_app`'s 5th `config` param, up-front `score()` command
validation threaded to `_ledger(capture_command=…)`, and `capture` absent from
`_EXTRA_HASH_FIELDS`. The two post-review test tightenings are real (`CaptureCommandProviderTests`
holds 9 tests). SKILL.md + refinement-todo document exactly what the sweep says.

Caveat-accuracy nit (FIXED before DONE): the DoD's "red when removed" caveat
grouped `test_web_run_records_null_capture_command` with the definition-hash test
as regression-guards, but the former asserts `capture_command is None` and so goes
red (KeyError) if the ledger field is removed — it is feature-bearing. The caveat
was corrected to name only `test_capture_command_not_in_definition_hash` as the
pure regression-guard.

Sweep completeness: non-no-op rows correct (`SKILL.md` updated, `docs/refinement-todo.md`
updated, `docs/specs/README.md` deferred). DoD full-suite box honestly names the
one pre-existing red.
