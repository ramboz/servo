---
slice: 029-01 — manual-capture
pass: craft
verdict: pass
reviewer: jig:reviewer (craft)
reviewed_at: 2026-08-28T01:22:52Z
prompt_source: review.py pr-review 029-01 --richer-skill none
substrate: non-interactive
---

Craft pass (independent jig:reviewer): no blockers. Two nits fixed: (1) capture.manual.crop now hashes the supplied input once BEFORE crop (single read, no TOCTOU; manual_sha256 names the input, retained shot is the cropped/judged bytes, source links them) + added test_manual_crop_hashes_input_not_cropped_shot; (2) redundant double read removed. Strengths: reuses provider seam idioms; guards mutation-testable.
