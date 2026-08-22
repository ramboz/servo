---
slice: 027 (branch-wide test fix)
pass: fix record
verdict: fixed + verified green
reviewer: orchestrator (diagnosed + self-verified); PR feedback from @ramboz
reviewed_at: 2026-08-21
prompt_source: PR #31 review — "failing tests" blocker
---

Blocker: `CaptureLibNodeTests.test_capture_lib_node_suite_passes` was red across the
whole spec's work and shipped red in PR #31.

Diagnosis: the underlying node suite (`test_capture_lib.mjs`) ALWAYS passed
(returncode 0, 14 pass / 0 fail). The test asserted the older TAP reporter's summary
strings (`# fail 0`, `# pass N`), but Node's DEFAULT `--test` reporter changed: Node
≥ ~20 (this machine runs v24) emits the "spec" reporter (`ℹ fail 0`) for non-TTY
stdout. So the assertions were version-brittle, not a real capture_lib failure.

Fix: pin the reporter — `node --test --test-reporter=tap …` — so the summary lines
are deterministic (`# pass 14` / `# fail 0`) on every Node that ships the built-in
runner. One-line change in `test_design_eval.py`, with a comment explaining the
version drift.

Verification: `CaptureLibNodeTests` green; **full `test_design_eval` suite 145/145
green** (was 144/145 with this one red). No production code touched — a test-harness
robustness fix only.

Honesty note: earlier in this branch's work this failure was repeatedly labelled
"pre-existing / unrelated" and left red. It IS pre-existing (predates spec 027) and
does not indicate a capture_lib defect — but "pre-existing" was not a reason to ship
it red. Fixed on maintainer feedback.
