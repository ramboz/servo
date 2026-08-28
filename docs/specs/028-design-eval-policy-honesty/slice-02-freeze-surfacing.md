---
status: DRAFT
dependencies: [028-01, adr-0033]
last_verified:
frame_review: true
---

## Slice 028-02 — freeze-surfacing

**Goal:** Make `freeze` surface the exclusion list to an approver *distinct from
the authoring agent*, and record whether a freeze was independently reviewed or
self-approved — so the "prevention" property (a distinct approver vetoes an
over-broad ignore-list before it ships) is real for the exclusion path, and a
self-approved freeze is honestly marked as auditability-only.

**DoR:**
- ✅ 028-01 DONE (structured `dimensions`/`ignore` exists to surface).
- ✅ ADR-0033 §4 approver-distinctness settled: the deliberateness bypass is a
  human-owner acknowledgement, **not** a self-ack channel for the authoring agent.

**Acceptance Criteria:**

1. **`freeze` prints the exclusion list and requires acknowledgement.** It emits
   "this eval excludes N dimensions: [id — reason]…; scores M dimensions: […] —
   confirm" and refuses to stamp `approved` without an explicit acknowledgement
   (flag or interactive confirm). A test asserts the list content and the refusal.
2. **The acknowledgement records *who* approved, distinct from the author.** The
   frozen config records an approval provenance: `reviewed` (a party other than the
   authoring agent — human owner, or the 028-03 independent reviewer) vs
   `self_approved` (the authoring identity acked its own freeze). A test asserts
   both paths write the correct marker.
3. **A self-approved freeze is marked as carrying auditability only, not
   prevention.** The marker is legible downstream (ledger + config), so a consumer
   can tell a reviewed freeze from a self-approved one. A `self_approved` freeze
   still scores (it is not blocked — ADR-0011 gate model), but it never claims to
   have been independently vetoed.
4. **The deliberateness bypass is a human-owner signal, not an author self-ack.**
   The `JIG_*`-style bypass (consistent with servo's other soft gates) clears the
   interactive confirm for a human owner; using it is recorded as `self_approved`
   unless a distinct-reviewer verdict (028-03) is present. A test asserts the
   bypass does not silently upgrade `self_approved` to `reviewed`.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Tests mutation-checked; host packages rebuilt + drift clean.
- [ ] Implementation + craft review passed.
- [ ] Deviation log + reconciliation sweep produced.

**Assumptions:**
- None load-bearing beyond 028-01's (this slice is surfacing + recording over an
  existing structured policy; no new runnable-surface claim). `frame_review` may
  derive `false` if `## Assumptions` is "None" — set the flag from
  `workflow.py frame-review-needed` at authoring time rather than by hand.

**Anti-horizontal-phasing check:** After this slice, a human (or distinct
reviewer) approving a freeze sees the explicit ignore-list and can veto it, and
every frozen eval carries an honest reviewed/self-approved marker — the reported
failure (filter/background silently excluded) is now catchable at freeze.

### Deviation log (after reconciliation)

_TODO at reconciliation._

### Reconciliation sweep

_TODO at reconciliation._
