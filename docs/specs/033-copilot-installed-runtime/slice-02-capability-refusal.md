---
status: IN_PROGRESS
kind: feature
dependencies: [adr-0039]
last_verified:
arch_review: true
claimed_by: claude/adr-0034-specs-028-jig-fe54d4
---

## Slice 033-02 - capability-refusal

**Goal:** A Copilot autonomous-launch request cannot silently lose its monetary,
context, permission or state-identity safeguards.

**DoR:**
- ADR-0039 accepted; Copilot limits probe retained as durable evidence.

**Acceptance Criteria:**

1. **Fail before dispatch.** All public --host copilot loop/goal/background/
   Routine/resume launch paths refuse unsupported autonomy with exit 2 and
   structured env_error before subprocess calls, target writes or state creation.
   Zero-valued limits, --resume-anyway, plans and readiness bypasses do not
   defeat the refusal. Explain-routing describes this host honestly.
2. **No fabricated accounting.** Refusal output uses schema_version 2, explicit
   backend copilot, an actionable capability breadcrumb and null unavailable
   spend/context; no zero-cost successful native invocation.
3. **Safe identified resume.** Explicit non-Claude backend/host metadata or
   native version-2 state cannot resume through Claude, even with --resume-anyway.
   New Claude version-1 state records additive backend identity. Legacy unmarked
   version-1 state retains the Claude interpretation for compatibility; September
   prototype state did not persist identity, so its origin cannot always be
   recovered. Document this limitation, do not claim universal recovery and do
   not migrate historical state to convert sessions.
4. **Compatibility.** Claude defaults, execution-plan clamps, heartbeat whole-pass
   authority, edit-permission-wall diagnosis, frozen protections and gate 0/1/2
   remain unchanged. No native provider fallback or blanket permission grant.
5. **Honest scope.** Docs and PR explain the minimum-30 soft credit cap is not
   USD enforcement; native loop/checkpoints/planner/heartbeat remain incomplete.
   Internal September adapter fixtures are not evidence of a supported launch.

**DoD:**
- [ ] Launch/refusal/resume fixtures show witnessed red-to-green.
- [ ] Required compliance, craft and architecture reviews pass.
- [ ] Existing loop/planner/heartbeat tests and generated-host drift clear.
- [ ] Final reconciliation review confirms live claims and incomplete scope.

## Assumptions

None for refusal. No inference of future native budget/control support.

**Anti-horizontal-phasing check:** A user gets an actionable safe refusal
instead of unknowingly funding a run without the requested limits.

### Deviation log (after reconciliation)

1. Replaced the September warning-only native launch posture with an explicit
   pre-dispatch refusal, including direct run_loop and read-only explanation.
   This completes the refusal contract, not the deferred native loop.
2. Compliance found two identity gaps; conflicting backend/host fields and goal
   state identity were witnessed red, fixed and independently re-reviewed.
   Full historical loop plus new guard tests passed 402 tests and 17 subtests
   before the supplemental initial-loop identity coverage.
3. Craft nits (initial-loop identity coverage, unreachable native routing) and
   architecture's unproved hook-continuation prose were corrected. Existing
   Claude driver/default/budget/permission-wall behavior remains unchanged.
4. Legacy unmarked v1 origin is genuinely unrecoverable in some prototype cases;
   compatibility is retained and that limitation is explicitly documented.

### Reconciliation sweep

| Surface | Disposition | Rationale |
|---------|-------------|-----------|
| Native main/direct loop/explain launch | updated | Schema2 env_error/null accounting before dispatch/writes. |
| State construction / identified resume | updated | Additive Claude backend identity; independent fields/v2 checked before bypassable schema checks. |
| Legacy unmarked state | no-op | Preserve v1 compatibility; do not fabricate provenance or migrate sessions. |
| Existing planner/heartbeat | no-op | Native propagation remains 033-03 DEFERRED; old clamps/whole-pass authority unchanged. |
| Skill / README / architecture / refinement | updated | Current support boundary, soft-credit evidence, advisory hooks and precise reactivation triggers. |
| Generated hosts | updated | Source-owned regeneration, no implicit provider switch. |
| Memory / board / ADR index | updated | Honest capability knowledge and derived lifecycle metadata. |
| Primer/conventions/inbox | no-op | Absent; no unrelated bootstrap. |
| Full CI / final reconciliation | deferred | Required after remaining native evaluation integration, before DONE. |

### Close-out (post-DONE)

- [ ] Preserve unavailable native autonomy in board/PR, not native-loop DONE.
