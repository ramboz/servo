---
slice: 036-01 - bound-card-evidence
pass: compliance
verdict: needs-changes
reviewer: general-purpose/card-compliance
reviewed_at: 2026-10-15T23:36:40Z
prompt_source: review.py implementation docs/specs/036-deterministic-design-evidence/spec.md 036-01 (compliance-prompt.txt in closeout session)
---

VERDICT: needs-changes

REASONING:
AC1 is met by the reviewed installation flow and genuine baseline pass; AC2 is partially met—the preserved measurements match all 28 approved constraints, but visible-title enforcement has the AC4 gap below; AC3 is met by the normal/open observations, completed action and measured crop (`card_install.py:425-589`, `card_capture.py:114-264`, final proof’s `baseline/` records).
AC4 needs changes because ancestor overflow clipping can hide required title text without producing a named failure; AC5 otherwise has meaningful refusal/inventory controls, and AC6 has source/policy/driver seals, loaded-byte verification and independently selected delivery (`card_evidence.py:195-365`, `required_runtime.py:72-244`, `nojudge-controls/receipt.json`).
AC7 is met by immutable same-run raw/component/envelope bindings; AC8 follows ordinary shared/vendor installation and bounded documentation; AC9 is materially demonstrated by all three actual runs—pass0, component-pass/quality-fail1, and required-fail1 despite passing quality (`gate_consumer.py:66-158`, `examples/bound-card.md`, final proof’s three `actual-run-receipt.json` and bound gate/envelope/native-reply records).
I verified the index hash, all 678 indexed artifact hashes, nine independent record pairs and eight canonical producer files; the supplied validation receipts pass, but none establishes the missing clipping behavior.

SPECIFIC ISSUES:
- High confidence — AC2/AC4: `skills/design-eval/card_capture.py:64-88`. Visibility checks constrain text rectangles to the card frame and reject several paint effects, but never account for ancestor `overflow` clipping. Wrapping `[data-part="title"]` inside `<div style="height:0;overflow:hidden">` leaves the title’s own box and text rectangles intact and inside the 44px card, while completely hiding its pixels. `checkVisibility()` does not detect overflow clipping, so `visible` can remain true and `card_evidence.py:72-110` can pass every title constraint. Detect this clipping and emit named required failures; add a live-browser regression and installed-gate veto control.

RECONCILIATION NOTES:
Preserve existing proof unchanged. After correcting visibility, refresh affected evaluator approval and bound proof; retain the documented trusted-local scope and downstream Jig119 boundary. No evaluations, judges or writes were performed during this review.
