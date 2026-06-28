---
slice: 015-02 — missing-evidence
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-06-28T03:18:00Z
prompt_source: review.py implementation docs/specs/015-edd-suitability/spec.md 015-02 skills/edd-suitability/suitability.py skills/edd-suitability/test_suitability.py (independent subagent; reads worktree, uncommitted)
---

VERDICT: pass

REASONING:
All four ACs for slice 015-02 are met and meaningfully tested. The `kind`
taxonomy is closed and module-exposed (`MISSING_EVIDENCE_KINDS`), fail-closed
against unknown signal keys (verified: a `"weird": True` signal never leaks as a
kind). Items carry the exact `{kind, detail, blocking}` shape with actionable
details, and coherence is made *structural* (not coincidental) by appending
`missing_<kind>` reason codes per blocking item — so the list and verdict cannot
disagree. Determinism/re-runnability is real: stable taxonomy-then-detail sort,
and the CLI re-run flip (`needs_evidence` → `suitable`, list emptied) is
exercised end-to-end. Tests pass, ruff clean, all four named test classes
present, all five taxonomy kinds exercised in v1.

SPECIFIC ISSUES:
- None blocking. Minor (Low):
  `test_blocking_kinds_reflected_in_top_level_reasons` originally asserted a
  prose substring rather than the structural `missing_<kind>` reason code — a
  weaker assertion than the implementation guarantees. **Addressed in-pass**: the
  test now checks reason *codes* (`missing_<kind>`), plus a companion test that
  advisory kinds are NOT forced into reasons.

CROSS-CUTTING:
- Principles check clean — refuse-on-missing-prerequisite / fail-closed (never
  `suitable` on indeterminate input; missing manifest/spec exits 2, no artifact);
  signal-aware-not-prescriptive (lint surfaced as advisory, never required).
- Engineering-practices: scope matches the slice boundary (no caller wired —
  acting on the list stays 015-03); deviation log thorough and verified against
  the code; no new TODO/FIXME; ADR signal correct (extends ADR-0015, no new ADR).

RECONCILIATION NOTES:
- Deviation log accurate; every claim verified against the code (oracle_signal
  umbrella + advisory sub-items; appended `missing_<kind>` reasons; empty list
  for `suitable`/`unsuitable`; `manifest_malformed` explicit test).
- Remaining DoD close-out (not deviations): `docs/specs/README.md` board regen;
  carry the closed taxonomy into board Notes for 015-03; set `last_verified` on
  transition to DONE.
