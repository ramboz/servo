---
slice: 012-03 — capture-and-judge-runtime
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-18T22:47:28Z
prompt_source: independent subagent review (spec-012 retro-ceremony, round 2 after needs-changes)
---

VERDICT: pass

Round 2, after a round-1 `needs-changes`. All five ACs met.

Round 1 blocked on two ACs describing something other than the shipped code:
AC1 attributed `setup`-seeding to `capture_app` (the seeding is in
`capture.mjs`; `capture_app` is the Python driver), and AC4 claimed bounded
retry for "transport failures" when `_judge_cli` has no retry at all and no
test. Both reworded to match the code, and `JudgeCliTransportTests` now covers
the cli transport across six paths (happy, clamp, non-zero rc, `is_error`
envelope, unparseable reply, missing binary). The previously-undocumented cli
transport is now documented in SKILL.md.

The round-1 "capture.mjs has zero automated coverage" headline is corrected to
a narrow, honest residual: the pure geometry now lives in `capture_lib.mjs`
(imported by `capture.mjs`, so the tests exercise the shipped path) with 10
node tests including null-box and crop-exceeds-box guards; only the browser body
remains hand-verified, which is disclosed rather than smoothed over.

Two robustness items are deliberately deferred with disclosure and accepted as
non-blocking: the `1600×1600` reference-render constant (an authoring-time
knob with no runtime honesty consequence), and `capture.mjs`'s silently
optional per-screen `setup` (a latent gap in code that shipped this way
through 0.8.0, not a regression; a properly authored config gives every screen a
setup). Both carry resolution triggers in the deviation log and refinement-todo.
