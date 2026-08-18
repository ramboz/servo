---
slice: 012-04 — guided-skill-surface
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-18T22:47:28Z
prompt_source: independent subagent review (spec-012 retro-ceremony, round 2 after needs-changes)
---

VERDICT: pass

Round 2, after a round-1 `needs-changes`. All three ACs met.

Round 1 blocked on the slice's own DoD and retro-note asserting the opposite of
what was committed — they claimed design-eval ships no SKILL.md surface tests
while `test_skill_surface.py` was already in the tree. Corrected: the record
now states 25 surface tests in the sibling-skill anti-greediness pattern, with
two capabilities the siblings lack — assertions scoped by document section
rather than matched globally, and drift tripwires checking prose against code.

The craft-blocking defect is also fixed here: after 012-03's `capture_lib.mjs`
extraction, SKILL.md's Flow step 1 and Files table still listed only
`score.py` + `capture.mjs`, so a reader following the doc would provision a
target whose `capture.mjs` could not import at run time. Both now list the
full vendored runtime, guarded by `DocumentedFilesMatchInitVendoringTests`,
which parses `init()`'s real copy tuple rather than a hardcoded list.

Host mirrors verified in sync. The bare `name: design-eval` (vs the `servo:`
prefix most skills use) is disclosed as out of scope for a reconciliation.
