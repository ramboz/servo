---
slice: 026-01 — runtime-preflight-guidance
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-20T01:09:41Z
prompt_source: review.py implementation (spec 026-01, round 2 after needs-changes)
---

Round 2, after a round-1 needs-changes. All ACs met.

Round 1 found a genuine shipped defect: AC4's middle-elision branch was
arithmetically dead — `half = (budget-5)//2` produced a `budget-1` line and the
fit check charged a separator the first line does not need, so every over-long
line was skipped whole and a SOLE over-long survivor returned "" — an empty
diagnostic, strictly worse than the `[:200]` it replaces and the exact outcome
AC4's floor exists to prevent. Reproduced (521-char cause -> '') before fixing.

Fixed by charging the separator only when emitted, sizing the elision to the room
actually available, guarding half > 0, and adding a non-empty-kept-but-empty-out
fallback. Re-derived by the reviewer: a 500-char survivor now yields 197 + " ... "
+ 197 = 399 <= 400 and is appended rather than skipped.

Round 1 also found the parity control missed the one constant that had actually
drifted (`^\s+at\s` vs AC4's literal `^\s+at `) plus an undeclared `re.I`. Both
corrected and pinned by tests, each mutation-verified to fail on reintroduction.

Evidence gaps closed: fixture (iii) committed; rank-1 exact-match now derived
from the committed fixture rather than a hardcoded prefix; a BEHAVIOURAL wiring
test (a revert of capture_app to `[:200]` now fails the suite); an AC4a guard
asserting the judge path still carries `[:200]`; an end-to-end rc-2/empty-stdout
preflight test; SKILL.md pointing at the runtime guidance; and the probe argv
pinned so a rewrite to a browser launch cannot pass.

Residuals recorded in the deviation log rather than blocking: fixture (ii) is a
labelled reconstruction (Playwright is not installable here), fixture (iii)'s
error shape is likewise constructed and now labelled as such, and the
refinement-todo owner is role-based rather than a named person.
