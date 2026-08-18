---
slice: 012-02 — authoring-cli-and-install
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-18T22:47:28Z
prompt_source: independent subagent review (spec-012 retro-ceremony, round 2 after needs-changes)
---

VERDICT: pass

Round 2, after a round-1 `needs-changes`. All five ACs satisfied.

Round 1 blocked on the record underselling the delivery (DoD still claimed
"3 unit tests" and the retro-note asserted an open thin-coverage gap that had
already been closed), and on `capture_refs` being the one CLI verb with
neither error handling nor a test. Both resolved: the DoD now itemizes 19 tests
across five classes, the retro-note states the gap closed, and `capture_refs`
returns `ENV_ERROR_RC` (2) on a missing `node` instead of escaping as an
uncaught `FileNotFoundError` — mirroring `score.capture_app` — covered by
`CaptureRefsTests`.

The install path is now genuinely hardened: `bash -n` validity before and
after uninstall, SEED-block balance, manifest de-duplication on re-install,
uninstall idempotence, config preservation across `install()`'s `init()`
step, and the fail-closed error paths are all directly asserted. The spliced
component remains an ordinary `score_<name>` — `gate.py` contains zero
design-eval references.
