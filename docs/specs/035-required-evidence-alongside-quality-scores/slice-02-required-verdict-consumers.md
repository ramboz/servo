---
status: DRAFT
kind: feature
dependencies: [035-01, adr-0044]
last_verified:
frame_review: true
arch_review: true
---

## Slice 035-02 - required-verdict-consumers

**Goal:** A developer using a supported execution or reporting surface sees the
same required veto and actionable evidence as the installed CLI gate, without a
high score falsely completing the work.

**DoR:**
- 035-01 DONE; v1/v2 gate fixtures and result references available.
- Enumerate canonical readers and generated/vendored consumers of gate status,
  oracle summaries, completion, plateau and retry hints. Record the bounded
  inventory; external consumers remain an explicit compatibility assumption.
- Native Copilot autonomy refusal remains in force; do not use a static hook
  adapter as proof of live continued execution.

**Acceptance Criteria:**

1. **Loop authority and recovery.** For supported loop and goal drivers,
   initial/final gate, iteration history, checkpoint/resume and final summary
   preserve v2 verdict/reason and required evidence references. Quality 0.99
   plus required fail cannot halt as success or produce a pass sentinel.
   Unknown/stale evidence halts as evaluation refusal, not convergence;
   budget, context and iteration brakes remain unchanged.
2. **Plateau honesty.** Required failures at high or flat quality may still
   reach the existing bounded non-convergence stop, but it is never pass.
   Reports retain failed IDs/reasons and distinguish diagnostic score plateau
   from fulfilled requirements. No new adaptive scheduler is introduced.
3. **Hooks.** Supported oracle-hook installation and meta-judge rendering
   use required verdict/reasons, not "raise the score" for a high-score veto.
   Exit 1 produces a relevant block/retry hint. Existing env-error fail-open
   turn handling stays unchanged and visibly reports unavailable evidence;
   it never emits completion attestation. Copilot's advisory hook limitations
   and native autonomy refusal remain explicit.
4. **Planner and reports.** Execution-planner evaluation references, heartbeat
   provision/verify/final handoff, triage human/JSON reporting and runner/judge
   guidance preserve required policy and invocation-bound evidence. A
   dispatched required-fail run is not `passed`; unknown evidence remains
   unavailable. Existing terminal reasons and quarantine/budget behavior
   remain compatible, with structured oracle cause carried separately.
5. **Version compatibility.** Old v1 checkpoints/results continue working.
   Enabled v2 readers refuse unknown versions or unavailable mandatory
   references. Generated host packages and supported project-vendored
   consumers are updated through normal generation/install mechanisms;
   existing customized installations receive explicit migration guidance
   instead of silent replacement.
6. **User-facing correction path.** Skill/help/report documentation shows
   how to inspect a failed required assertion, repair the implementation and
   rerun, versus repair acquisition/bindings on refusal. Changing policy is
   an explicit reviewed reapproval, never the default correction. A real
   supported consumer smoke proves the high-score negative control is
   surfaced through final reporting.

**DoD:**
- [ ] Every discovered in-repository consumer is covered by a fixture or a
      documented no-op with evidence; negative controls cannot falsely pass.
- [ ] Witnessed regression tests and compliance/craft/architecture reviews pass.
- [ ] Deviation log and reconciliation cover runtime, generated packages,
      install templates, live docs and reporting; review clears.

## Assumptions

- Additive result references can fit existing loop/heartbeat versioning
  without breaking old records. AC5 must validate actual reader behavior,
  not infer it from permissive JSON parsing.

**Anti-horizontal-phasing check:** A user running a supported consumer can
correct the failed constraint from its own final handoff, rather than having
to rerun a different evaluator to discover why it stopped.

### Close-out (post-DONE)

- [ ] Regenerate board and reconcile complete consumer inventory and live docs.
- [ ] Record genuine deferred external-consumer work without marking it done.
