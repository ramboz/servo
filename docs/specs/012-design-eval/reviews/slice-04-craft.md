---
slice: 012-04 — guided-skill-surface
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-18T22:47:28Z
prompt_source: independent subagent review (spec-012 retro-ceremony, round 2 after needs-changes)
---

VERDICT: pass

Round 2, after a round-1 `needs-changes`. Reviewed across all four slices of
spec 012.

The one blocking item is closed: SKILL.md's Flow step 1 and Files table now list
`capture_lib.mjs` and `fidelity_eval.py`, and
`DocumentedFilesMatchInitVendoringTests` parses `init()`'s copy tuple with
the same regex discipline as the verb-drift test — a real tripwire, not a
substring check, and mutation-verified.

All four named pass-bar nits resolved: trigger assertions scope to a
`description:`-only scalar via `_description()`; the vacuous re-inline guard
is replaced with one a real re-inline would trip; `computeClip` throws named
errors for the null-box and crop-exceeds-box cases with two new degenerate node
tests; and `capture.mjs`'s `fail()` now throws through
`finally { browser.close() }` instead of `process.exit(2)`, so no chromium
process leaks. Volunteered extras landed cleanly: `main()`'s env_error
wrapper, the redundant `JSONDecodeError` removal, and test hygiene
(`patch.dict` + `addCleanup`, deduped import, pinned node pass count).

The `capture_lib.mjs` extraction is a textbook seam — pure geometry out, side
effects left in `capture.mjs` — and the new tests are behavioural rather than
string-presence theatre: `bash -n` on the spliced oracle, retry-vs-4xx call
counting, the sha256 definition-hash pin, and manifest/splice idempotence would
all catch genuine regressions.

Deferred cross-skill refactors (the `judge_transport`/`_prompt` duplication
shared with content-fidelity) and shipped-runtime robustness nits are
legitimately out of scope for a reconciliation pass and are honestly recorded in
the slice deviation logs and refinement-todo, each with a resolution trigger —
an acceptable basis for the DONE transition.
