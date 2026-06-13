---
slice: 011-01 — discover-and-inbox
pass: craft
verdict: pass
reviewer: general-purpose (pr-review skill)
reviewed_at: 2026-06-12T23:52:25Z
prompt_source: review.py pr-review docs/specs/011-heartbeat/spec.md 011-01 skills/heartbeat/heartbeat.py skills/heartbeat/test_heartbeat.py
---

Clean, idiomatic spike-slice that faithfully mirrors the house style of
`gate.py` / `loop.py` (schema_version-first records, closed {0,2} exit contract,
atomic `os.replace` writes, bounded subprocess, stderr breadcrumbs). Read-only
posture enforced structurally and verified by a byte-snapshot test. The 52-test
suite exercises real behavior, not line coverage.

Strengths called out: the `_run_subprocess` abstraction (one honest skip path
for FileNotFound/non-zero/timeout/OSError), the `_build_finding` +
`_DISCOVERY_SOURCES` dispatch-table seam, and the PATH-injected fake gh/git
harness with a guard test asserting the mock matches the real `gh --json` field
names.

Findings were nits only (no blockers):
- [nit, ADDRESSED post-review] empty-stdout vs `[]` asymmetry: a `gh` source
  exiting 0 with truly empty stdout hit `json.loads("")` and was mislabeled
  `skipped (unparseable JSON)` instead of `ran (0 findings)`. Fixed in both
  `_discover_ci` / `_discover_issues` (coerce empty/whitespace stdout to `[]`)
  + regression test `SourceDegradationTests::test_empty_stdout_reports_ran_not_skipped`.
- [nit, conscious divergence] `_run_subprocess` uses `subprocess.run(timeout=)`
  (direct-child kill) rather than gate.py's process-group kill — deliberately
  reserved for the untrusted oracle shell; matches loop.py's precedent. Left as-is.
- [nit, conscious divergence] `_atomic_write` has no explicit fsync before
  os.replace — matches loop.py's `_atomic_write_state` exactly. Left as-is for
  house-style parity.

VERDICT: pass (nits only; per jig block rule [nit]s don't block REVIEWED).
