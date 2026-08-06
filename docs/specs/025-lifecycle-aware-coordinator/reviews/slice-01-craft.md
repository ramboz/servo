---
slice: 025-01 — priority ranking and lifecycle-aware normalization
pass: craft
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-08-06T18:30:13Z
prompt_source: independent craft review (025-01), re-verified after fixes
---

Independent craft/code-quality review of slice 025-01 (general-purpose, Opus, no impl-conversation access).

VERDICT: pass (after one needs-changes round, re-verified)

Round 1 (needs-changes) found one real must-fix: `_claimed_in_jig_board` read a foreign jig-board
file with `read_text()`, so a non-UTF-8 file raised UnicodeDecodeError (a ValueError, not OSError)
past the `except OSError` → crashed unattended dispatch, contradicting the fail-open + {0,2} exit
contract. Plus polish: stale `_normalize_record` docstring (v2→v3), a `source` value entering a
trusted-position label unclamped, and untested fail-soft branches.

Round 2 (re-verified pass): the must-fix is genuinely fixed via `read_text(errors="replace")` with a
faithful `\xff\xfe` reproduction test; `source` clamped to `_KNOWN_SOURCES`; docstring corrected;
fail-soft branches (`_read_frontmatter`, whitespace-only critical-labels env) now unit-tested. ruff
clean; full suite 210 green. #4 (memoize per-pass board read) and #5 (surface priority in `status`)
agreed non-blocking polish.

Strengths (round 1): priority threaded consistently through every record path; the mixed-version
regression correctly guarded (whole-set normalize-on-read); migration genuinely upgrade-in-place;
ranking tests assert order (reverse-FIFO seed) with a failability demonstration; idiom fit excellent.
