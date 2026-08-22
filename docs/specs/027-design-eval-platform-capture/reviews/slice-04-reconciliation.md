---
slice: 027-04 — blessed Android capture provider
pass: reconciliation
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: reconciliation review of the deviation log / sweep / DoD vs disk
---

VERDICT: pass — every reconciliation claim verified against disk; one naming-
completeness nit fixed.

Deviation-log honesty: all claims match `score.py` / `pngcrop.py` — the review-fix
list (zlib wrap, `_crop_insets` EnvError, the six added tests), serial pinned once
after `validate_freeze` and into `capture.android` only, screencap captured as
bytes, `capture_command` reuse, device precedence. `pngcrop.py` is stdlib-only and
rejects interlaced/paletted/<8-bit/16-bit.

Sweep completeness: non-no-op rows accurate — `SKILL.md` (android docs + Files-table
`pngcrop.py` row), `design_eval.py` (init() vends `pngcrop.py`), `docs/refinement-todo.md`
(inset-autodetect + settle-delay deferral), `testdata/rgba_filter_sample.png`
(added), `docs/specs/README.md` (deferred). Nothing omitted.

DoD accuracy: the full-suite box honestly discloses the one pre-existing red; the
"red when removed" box is honestly scoped; the live-emulator smoke box is backed by
the recorded emulator narrative (composite/provider/provenance/1080×2250 crop).

Naming-completeness nit (fixed): the review-fix bullet named 3 of the 6 added tests
by name → all six now named.

Note: the reviewer's read-only toolset could not run git; the orchestrator confirmed
the uncommitted set was exactly the slice `.md` + `docs/refinement-todo.md`.
