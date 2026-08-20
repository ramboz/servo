---
slice: 026-01 — runtime-preflight-guidance
pass: craft
verdict: pass
reviewer: jig:reviewer (pr-review shape)
reviewed_at: 2026-08-20T01:09:41Z
prompt_source: review.py pr-review (spec 026-01, round 2 after needs-changes)
substrate: non-interactive
---

Round 2, after a round-1 needs-changes. All three blockers closed.

R1 blockers: (1) the elision arithmetic guaranteed budget-1 characters while the
fit check charged an unconditional separator, making elision dead and allowing an
empty return — reproduced and fixed; (2) the test that named the skip-whole rule
used a 380-char line against a 400 budget, so it never entered the branch it
appeared to guard, and both its assertions were tautological; (3) nothing
asserted capture_app routed through the helper, so a revert to `[:200]` would
have left the suite green.

All three fixed: the arithmetic re-derived (head/tail slices provably never
overlap), a genuinely 500-char case pinning non-empty/elision-marker/head/tail/
length, and a behavioural wiring test that fails on revert.

Nits applied: no-op self-replace deleted; parity extended to the drifted
constants and both mutation-verified; four PreflightTests no longer depend on a
real node on PATH; the box translation table hoisted; the `_preflighted` latch
removed entirely in favour of the existing `if fake is None:` block;
`salient_stderr` re-exported in house style; fixture provenance corrected; the
skip-whole test made falsifiable; and comments added for the deliberate
three-way normalization and the value-dedup in the rank stage.

Not done, by agreement: the three-way normalization was left unrefactored under
review (it is now commented instead), and the caret regex remains a local literal
outside the parity control — the one remaining hole, low value to chase now.
