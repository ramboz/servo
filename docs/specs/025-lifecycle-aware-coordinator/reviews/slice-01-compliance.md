---
slice: 025-01 — priority ranking and lifecycle-aware normalization
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-06T18:30:12Z
prompt_source: independent compliance review (025-01)
---

Independent compliance review of slice 025-01 (jig:reviewer, read-only, no impl-conversation access).

VERDICT: pass

All four ACs implemented + covered by non-vacuous tests. AC1: `priority` field + SCHEMA_VERSION 2→3
with genuine UPGRADE-IN-PLACE migration (`test_v2_inbox_upgraded_in_place_preserves_sticky` proves a
tried/attempts:2 record survives; v4 refused rc=2); ladder sort in `_select_candidates`. AC2:
structured jig-shaped / built-in records with the untrusted-data framing preserved. AC3:
`_claimed_in_jig_board` reads servo_finding_id/claimed_by/status, fail-open + open-only quarantine
skip. AC4: cap composes with rank.

Reconciliation notes folded into the slice: (a) AC2 is jig-record-SHAPED + filesystem-only, never
invokes jig (ADR-0011) — spec prose updated to match; (b) `_JIG_SKIP_STATUSES` is a hard-coded
frozenset (forward-compatible), not env-configurable — logged as a scoped-down deviation; (c) the
label-derived priority rung (CI→2, security-label→3) is unit-tested in isolation + the ladder is
order-tested via seeded rungs (minor: no single end-to-end discover-a-security-issue→priority:3 test).
