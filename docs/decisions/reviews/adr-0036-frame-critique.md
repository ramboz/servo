---
adr: 0036
pass: frame-critique
verdict: pass
reviewer: jig:reviewer subagent, fresh per round x3 (claude-fable-5)
reviewed_at: 2026-08-31T19:09:42Z
prompt_source: review.py frame-critique docs/decisions/adr-0036-frozen-evals-satisfy-suitability-signal.md
---

Three-round adversarial frame-critique, fresh `jig:reviewer` subagent(s) per
round (claude-fable-5), prompt built by `review.py frame-critique`. The ADR was
revised between rounds (Proposed → still Proposed; acceptance remains the
owner's call).

## Round 1 — two independent reviewers, both `needs-changes` (same primary)

Both critics independently converged on the same load-bearing hole in the
first draft ("v1 counts both `reviewed` and `self_approved`", OQ1 deferred):
**the eval leg was self-mintable.** `approval_status: "approved"` does not
encode a second party — `content_fidelity.py:94-115` and
`eval_authoring.py:1266` stamp `approved` with no provenance recorded at all,
and design-eval's `self_approved` path is a self-ack flag
(`SERVO_DESIGN_EVAL_ACK_EXCLUSIONS=1`) — while accepted ADR-0033 rules a
self-approved freeze auditability-only ("in a detached loop with [no
reviewer], a rigged score still passes"). An unattended agent on a testless
target could author → freeze → install → register an eval and mint its own
`suitable` end-to-end: the exact move the draft's own Alternatives section
claimed the ceremony prevents. Shared secondary: the "self-inconsistent
checklist" motivation misread `oracle_signal`'s detail (which asks for a
*deterministic* gate, `suitability.py:112-114`). Critic A also flagged the
`scaffold-init --force` desync as an unverified corner of the symmetry
assumption.

**Revision:** OQ1 decided — only `approval_provenance: "reviewed"` credits
(predicate `tests OR ci OR reviewed_frozen_eval`); self-approved and
provenance-less freezes contribute nothing; the rejected first draft recorded
as an Alternatives entry; the overstated motivation withdrawn; spec 030
synced (AC1 provenance fixture, AC2 grown to five negative fixtures).

## Round 2 — fresh reviewer, `needs-changes` (decision defensible, three supports wrong)

Verified the revision's mechanics but showed three supporting claims false:
(1) "reviewed closes the on-rails self-mint" is not a *structural* property —
`record_reenumeration` (`design_eval.py:141-166`) accepts self-reported
reviewer/author strings (distinctness = string inequality), so a fabricated
record mints `reviewed` on CLI rails; (2) the cited `runner.md` prohibition
covers spec-oracle artifacts only, not eval configs or re-enumeration
records; (3) the `--force` "orphaned registration" description had the
failure backwards — `scaffold.py:543-551` rewrites `install.json` wholesale,
erasing the registration *with* the splice, so the true failure is a
fail-closed false refusal, never a phantom credit.

**Revision:** guardrail 4 reframed honestly — the barrier is **normative,
not structural**: no honest path mints a signal; every dishonest one requires
affirmatively fabricating a review record and leaves a falsifiable artifact
(ADR-0033's auditability-not-prevention grade; OQ6 explicitly named as
unresolved); the `--force` limit corrected to the fail-closed direction and
the Verification fence re-aimed accordingly.

## Round 3 — fresh reviewer, `pass`

All mechanical citations re-verified against the code (including
`execution_plan.py:135-136` keying on `verdict`, so the
suitable-with-advisory relaxation cannot misfire in the shipped consumer).
The two residuals — fabricated re-enumeration records, and loop-time
gameability of a reviewed frozen judge — are named in the ADR with the
correct grade, a detection story, and a kill criterion: priced risk, not
ungrounded assumption.

**Reviewer notes for the acceptance decision (recorded, not blocking):**

1. **OQ6 conditionality.** "Reviewed provenance is a barrier worth crediting"
   sits on unresolved ADR-0033 OQ6 in *both* directions: if a reviewer
   subagent may NOT clear a freeze unattended, the fully *autonomous* pilot
   class arrives self-approved and stays refused (the headline benefit for
   that class fails to materialize — and the kill criteria cover false
   passes, not persistent false refusals); if it MAY, a spawned nominal
   reviewer makes the barrier near-costless, leaving the fabrication-audit
   trail as the real floor. The attended-freeze / unattended-loop split gives
   the near-term vellum class a workable path; accept with this conditional
   in view.
2. **Implementation seam (spec 030).** Guardrail 5's advisory cannot
   literally "reuse" the existing `tests`/`ci` emission — today those items
   exist only inside `if not has_signal:` (`suitability.py:109-129`); the
   judged-only case needs a new branch that emits them while suppressing the
   blocking `oracle_signal` item. Noted in slice 030-01's assumptions.
