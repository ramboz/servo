---
slice: 036-01 - bound-card-evidence
pass: compliance
verdict: needs-changes
reviewer: jig:reviewer/card-compliance-checkpoint
reviewed_at: 2026-10-15T15:04:32Z
prompt_source: review.py implementation docs/specs/036-deterministic-design-evidence/spec.md 036-01 (deliverables in session 036-01-compliance-prompt.txt)
---

VERDICT: needs-changes

REASONING:
Per-AC disposition at the reviewed checkpoint: AC1 unmet; AC2 partial; AC3 met;
AC4 partial; AC5 partial; AC6 unmet; AC7 partial; AC8 partial; AC9 unmet.
Live overall pass, component-pass/quality-below-threshold, and complete package/
reinstall/uninstall acceptance were unwitnessed. The initial OAuth failure is
a separate runtime blocker, not a waiver. Historical epochs are not final-code
proof and unfinished controls receive no credit.

SPECIFIC ISSUES:
- card_install.py: generation had not bound the approved0.8 threshold, leaving
  scaffold default0.5. Required-pass with quality0.7 could pass.
- card_evidence.py: a relabelled pre-existing run tree could be accepted without
  a gate-owned independent acquisition claim/receipt.
- card_capture.py: visible parent textContent could contain hidden descendants.
- Review requested nominal browser±1.01 controls; the original assignment already
  explicitly authorizes measured outside-boundary±1.02 controls for Chromium
  quantization and pure exact±1.01 kernels. This is not a policy deviation.

RECONCILIATION NOTES:
Keep IN_PROGRESS; do not claim overall completion or Jig DONE. Subsequent
source fixes, tests and new prepared epochs must not rewrite these historical
reviewed facts. A later narrow resolution review accepted threshold/ownership
fixes but identified modern transparent text and display:contents false failure;
both received witnessed red/green tests afterward. No later full compliance
pass has been obtained at the time this checkpoint is recorded.
