---
slice: 027-05 — blessed iOS capture provider
pass: reconciliation
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: reconciliation review of the deviation log / sweep / DoD vs disk
---

VERDICT: pass — reconciliation artifacts faithful; spec-close correctly flagged as
the pending next step.

Deviation-log honesty: matches `score.py` — the file-vs-stdout capture with in-place
crop and `not out.is_file()` guard, `text=True` on the screenshot subprocess, target
precedence udid→env→"booted", the generalized `_crop_insets(crop, *, where=…)` with
the android caller updated to `where="capture.android.crop"`, the `ios` registry +
score() branch recording `capture_command`, and the review-fix "produced no output
file" message.

Sweep completeness: non-no-op rows accurate — `SKILL.md` (ios docs),
`docs/refinement-todo.md` (deferred iOS live-simulator smoke with a resolution
trigger), `docs/specs/README.md` (deferred to spec-close). `pngcrop.py`/`design_eval.py`
correctly `no-op` (reused from 027-04; the `xcrun` mention in pngcrop's docstring
predates this slice — confirmed the 05 commits did not touch pngcrop.py).

DoD accuracy: full-suite box honest about the one pre-existing red; DEFERRED live
smoke honestly represented (never ticked as done).

Spec-level close-out correctly PENDING at review time: this slice closes spec 027
(all five slices DONE), so the orchestrator's next step flips the slice to DONE and
runs the spec-close (spec.md status; status-board regen deferred to land-time).
