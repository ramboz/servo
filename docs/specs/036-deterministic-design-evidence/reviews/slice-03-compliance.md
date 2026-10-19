---
slice: 036-03 - static-source-contract-app
pass: compliance
verdict: needs-changes
reviewer: jig:reviewer/static-app-compliance-checkpoint
reviewed_at: 2026-10-19T23:23:20Z
prompt_source: review.py implementation spec036 036-03 at7239; no APP proof presumed
---

VERDICT: needs-changes

REASONING:
The finite property/role-driven implementation is present, but two acquisition-error paths violate the specified failure/refusal semantics. AC1 and AC3 are partial/unverified; AC2 and AC4 have implementation defects and outstanding approval/runtime gates; AC5 is unmet; AC6 and AC7 remain partial/unverified. Tests and SOURCE-only acceptance do not establish genuine APP approval or installed-gate compliance, and DoD remains incomplete. No commands were executed or files written by the reviewer.

SPECIFIC ISSUES:
- [High; AC2/4] At reviewed source7239 static_contract.py125, invalid selector '[' passes binding validation, querySelectorAll throws while row retains count0 (297-308), then compare checks absence before error. Incorrect fail1 instead of unknown2.
- [High; AC4/6] At reviewed source7239 static_contract.py344, required instability raises before436 assignment returns observations; consistently absent role and sampled facts disappear instead of retaining known contradiction beside unknown.
- [High; AC1-4] Snapshot/provenance preparation is not APP observation/installed verdict. Exact-policy approval, unchanged Dashboard measurements, browser-loaded response verification and installed discrimination remain unverified.
- [High; AC5] Eleven-fact SOURCE approval is not APP policy or installed positive/mutation/restoration proof. New15 was unapproved at review. No positive APP proof exists.
- [High; AC6/7, DoD] Actual Generic/current readback controls, reinstall/uninstall/native0/1/2, immutable evidence index, postreviews/reconciliation and unmerged PR remain unestablished.

RECONCILIATION NOTES:
Retain IN_PROGRESS/checkpoint status and record error-handling discrepancies without waiving criteria. Keep ADR approach acceptance, immutable SOURCE approvals, pending APP policies and new15 separate. Preserve backend, whole-view and Jig nonclearance.

Provenance: genuine fresh-context jig:reviewer/static-app-compliance-checkpoint, generated implementation checkpoint prompt, reviewed committed7239 plus explicitly named pending artifacts. This durable NONPASS is not reinterpreted as approval because later TDD addressed code defects or SOURCE approval arrived.
