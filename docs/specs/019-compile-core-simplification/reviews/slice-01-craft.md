---
slice: 019-01 — freeze-parsed-acs
pass: craft
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T18:38:56Z
prompt_source: review.py pr-review (jig:spec-workflow craft pass, re-run after doc-drift fix)
---

VERDICT: pass

REASONING:
The implementation matches ADR-0022 and the slice's five ACs exactly: the
raw-file hash block is fully removed from freeze_violation, only the canonicalized
approved_content_hash gates staleness, and plan_content_hash now sorts by AC id
and whitespace-normalizes statement before hashing. Scope was respected precisely
as the DoR demanded -- oracle_overlay.py::approve's own source-fidelity check and
oracle_plan.py's source_hash/source_spec_path fields are untouched. Both
previously-flagged doc drifts are now accurate and internally consistent with the
code, and the "source-faithful" comment-banner issue from the prior pass is gone.
Tests are meaningful -- reordering, whitespace reformatting, actual content edits,
and a genuine subprocess round trip through oracle_overlay.py approve into
checks.py --enforce-freeze.

SPECIFIC ISSUES:
- [nit] skills/spec-oracle/checks.py:829-833 -- _ac_sort_key falls back to "" for
  an item with no id; two such id-less items would sort non-deterministically
  under Python's stable-sort tie-break across different on-disk orderings. Not
  exploitable since the planner always assigns a unique id; worth a one-line
  comment noting the uniqueness assumption.
- [nit] skills/spec-oracle/checks.py:824 -- _canonicalize_ac_item guards
  isinstance(item["statement"], str) but not isinstance(item, dict); consistent
  with the module's existing trust-the-reviewed-artifact convention.
- [strength] skills/spec-oracle/checks.py:836-853 -- plan_content_hash's docstring
  plainly states the tripwire is "NOT adversary-proof" and names the actual
  defense, avoiding the overclaiming that triggered the prior pass's flag.
- [strength] skills/spec-oracle/test_checks.py -- FreezeSurvivesLivingDocMutationTests
  and FreezeStillCatchesACEditTests subclass the existing FreezeEnforcementTests
  fixture rather than duplicating setup, giving true regression coverage for free.
- [strength] skills/spec-oracle/test_checks.py -- the approve-CLI round-trip test
  drives the real oracle_overlay.py approve subprocess and feeds its output
  through checks.py --enforce-freeze --score-only, genuinely verifying AC4
  end-to-end.

RECONCILIATION NOTES:
Doc fixes are faithful to the shipped code and ADR-0022's language -- no further
doc drift found on this pass. Scope stayed exactly within the DoR's stated
boundary. No new deviations beyond what ADR-0022's "Negative" consequences section
already anticipated.
