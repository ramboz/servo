---
status: DONE
kind: feature
dependencies: [035-01, adr-0044]
last_verified: 2026-10-15
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
   preserve the overall v2 policy verdict/reason, gate run/digest and
   run/digest-bound component references, not a component's standalone verdict. Quality 0.99
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
   A passing deterministic component plus failed quality threshold is overall
   `fail`, not a dispatched `passed` outcome or completion evidence; preserve
   this run for Jig119's no-rerun/no-rescore attestation refusal control.
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
- [x] Every discovered in-repository consumer is covered by a fixture or a
      documented no-op with evidence; negative controls cannot falsely pass.
- Evidence: [consumer implementation receipt](consumer-implementation-receipt.md).
- [x] Witnessed regression tests and compliance/craft/architecture reviews pass.
- [x] Deviation log and reconciliation cover runtime, generated packages,
      install templates, live docs and reporting; review clears.

## Assumptions

- Additive result references can fit existing loop/heartbeat versioning
  without breaking old records. AC5 must validate actual reader behavior,
  not infer it from permissive JSON parsing.

**Anti-horizontal-phasing check:** A user running a supported consumer can
correct the failed constraint from its own final handoff, rather than having
to rerun a different evaluator to discover why it stopped.

### Deviation log

- The shared consumer-only reader is beside quality-gate and reuses existing
  read-only identity helpers. It never grades, reruns assertions or introduces
  a registry. Overall `oracle` and exact `gate_ref` are additive to consumer
  records; gate schema2, component schema1 and checkpoint schema1 stay distinct.
- Legacy no-policy unversioned minimal gateway adapters retain their old shape.
  Explicit unknown versions and enabled-policy downgrades refuse. Historical
  v1 checkpoints remain supported but cannot attest newly enabled policy
  without a current evaluation.
- Absolute external component sidecars refuse heartbeat isolation rather than
  redirecting evaluation into the original checkout or rewriting approval.
  Approved target-relative sidecars and existing external evaluator pins keep
  their identities. Custom hooks remain unchanged with explicit migration.
- Compliance recovery fixed preserved-evidence promotion after later failure,
  interruption and zero-new-iteration resume. Current unavailability is
  persisted separately; a fresh bound run can recover. Missing overall report
  payloads also refuse. Genuine non-clearing reviews are preserved in commits
  `b3897fd` and `48b4d19`, not fabricated into prior passes.
- Hook fallback quoting now handles spaces/apostrophes; non-object JSON warns
  visibly while turn handling stays fail-open. The craft nit added structured
  planner refusal for malformed policy pins. The arch receipt-pointer nit was
  resolved by executing the actual final-source runtime command, not relabeling
  an older result. All corrections have witnessed red/green receipts.

### Reconciliation sweep

| Surface | Disposition | Evidence / rationale |
|---------|-------------|----------------------|
| Canonical consumer inventory | updated | Plan inventory and consumer receipt map every declared reader to installed fixtures or bounded no-op evidence. External consumers are not claimed. |
| Loop/goal/history/resume/sentinel/plateau | updated | Original overall payload, run/digest refs and separate final availability; current-source controls and legacy failure/resume/interruption regressions pass. |
| Heartbeat provision/verification/handoff/triage | updated | Policy/sidecar closure, no old runs, honest refusal/correction evidence, preserved cost/dispatch timestamps and quarantine behavior. |
| Hook install/template and advisory Copilot adapter | updated | Real installed high-score block, visible unavailable warning, custom migration and shell-safe fallback; turn fail-open is not attestation. |
| Planner and runner/judge guidance | updated | Approved policy/config/evaluator/source references, typed malformed-pin refusal, no served-build claims or component-based completion. |
| Generated Claude/Codex/Copilot packages and project vendor | updated | Only the ordinary builder writes generated hosts; install contract and vendor include the reader. Final runtime/drift checks pass. |
| Live architecture/README/skills/carrier example | updated | Source-backed consumer semantics, repair-vs-refusal instructions, version namespaces and explicit limitations. Architecture follows Accepted ADR0044; no new load-bearing decision or competing boundary was introduced. |
| Producer gate/runtime/scaffold/overlay, design/common seams | no-op | Producer bytes remain the pinned 035-01 source; no producer API gap or sibling036 changes. Final smoke hashes verify unchanged gate/runtime. |
| Accepted ADRs, DONE records, conventions | no-op | Not amended. This implements the accepted decision; no convention or additional ADR/lightweight product decision is needed. |
| Inbox and use-case coverage | no-op | No resolved inbox item; helper reports zero inbox items. Coverage helper explicitly no-ops because the vision has no use-case breadth section. |
| Memory | updated | `memory.py add-learning` persists source-backed unavailable-evidence/readback lessons; summary reports 11 learnings, zero glossary/inbox entries. |
| Team memory advisory | deferred | `team-check` reports missing people.md for six contributors; skip this optional unrelated bootstrap without creating files or a permanent opt-out. |
| Primers/close-out | no-op | Plugin-only scaffold has no AGENTS.md/CLAUDE.md active-spec primer to compress. No unrelated template or convention change. Durable invariants are in live guidance, memory and this slice. |
| External adoption, real design/current-delivery proof | deferred | Coordinator/sibling036/Jig119 own integrated validation. This slice proves command fixtures, not general design convergence or served/current-build attestation. |

**Leanness:** One consumer reader and one fixture file serve existing callers;
no new producer, gate, DSL, registry, scheduler, dependency, generic design
adapter or native autonomy was added. Existing tests are preserved except
adding the real stdlib `importlib` to two dependency allowlists.

**Final source-epoch evidence:** `035-02-final-source-controls.txt` records
107 tests / 50 subtests; Python-floor receipt 34 / 26; runtime receipt
148 / 73. Lint, generated-host drift and whitespace pass. Exact byte hashes
and installed final-report controls are in the final-source smoke receipt.
Earlier broader targeted results are kept with their own source epochs,
not summed or substituted for current proof.

Fresh independent reconciliation returned pass, covering doc faithfulness,
honest source/review chronology and bounded scope. Its durable verdict and
subsequent lifecycle states are helper-owned.

### Close-out (post-DONE)

- [x] Regenerate board and reconcile complete consumer inventory and live docs.
- [x] Record genuine deferred external-consumer work without marking it done.
