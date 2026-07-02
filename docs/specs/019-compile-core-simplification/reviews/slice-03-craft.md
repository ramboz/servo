---
slice: 019-03 — behavioral-ac-recall
pass: craft
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T20:22:11Z
prompt_source: review.py pr-review
---

VERDICT: pass

REASONING:
The new rule 7b in _classify_family is narrowly anchored, correctly placed
after the more-specific structural families and the affirmative command rule,
and before text_invariant -- precedence claims in the code comments match the
actual code order, and existing-family-precedence tests confirm no
reclassification of already-matching ACs. Tests genuinely assert classification
outcomes across positive cases, negative-guard cases, and an integration test
proving suitability.py's n_evaluable count moves with the same fix via the real
classifier -- no scope creep into unrelated systems.

SPECIFIC ISSUES:
- [nit] test_oracle_plan.py's "is excluded" tests didn't include a case
  combining "excluded" with "package" (rule 5's archive_inventory trigger word)
  -- added test_is_excluded_does_not_collide_with_archive_inventory during
  reconciliation; confirmed no actual collision (rule 5 keys on "excludes",
  not "excluded").
- [nit] Bug 003's record didn't yet cross-link to this slice as the "shared,
  documented AC grammar" follow-up it called for -- added during
  reconciliation.

RECONCILIATION NOTES:
AC3's "regression guard" is a new test against an already-true invariant (per
the slice's own corrected DoR, suitability.py never had a private parser) --
stated plainly in the deviation log so a future reader doesn't assume
re-plumbing occurred.
