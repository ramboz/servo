---
status: DONE
dependencies: [028-01, adr-0033]
last_verified: 2026-08-28
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
- [x] All ACs pass; full test suite green (178 tests).
- [x] Tests mutation-checked (refuse-without-ack + env-bypass-stays-self_approved +
      the no-SELF-APPROVED negative guard go red when neutered); hosts rebuilt + drift clean.
- [x] Implementation + craft review passed (independent jig:reviewers).
- [x] Deviation log + reconciliation sweep produced.

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

1. **`reviewed` is an ASSERTED, UNENFORCED marker in 028-02 — enforcement is
   028-03.** `--reviewer <id>` is honor-system: the config carries no author
   identity to compare against, so an adversarial author could pass
   `--reviewer <own-id>` to earn `reviewed` and dodge the loud `SELF-APPROVED`
   advisory. This is the ADR-0033 boundary — 028-02 *surfaces* + records; the
   **enforced independent re-enumerating reviewer** (whose recorded verdict truly
   earns `reviewed` and defends the omission path) is **028-03**. Surfaced honestly
   in SKILL.md ("asserted, unenforced … until 028-03 lands") so no consumer reads a
   `reviewed` freeze as independently vetoed before 028-03. Compliance + craft both
   flagged this; it is a scoped deferral, not an overclaim.
2. **CLI freeze refusal made clean (craft nit).** `main()`'s `freeze` branch now
   catches `EnvError`/`StaleError`/`FileNotFoundError` → `design-eval: freeze
   refused — …` + rc 2 (mirroring the `advisory` branch), instead of an uncaught
   traceback. Tested (`test_cli_freeze_refusal_is_clean_line_not_traceback`).
3. **`_exclusion_summary` SCORES-line + zero-exclusions path** now directly tested
   (craft nit), not only the non-zero `EXCLUDES`/`device-chrome` path.
4. **Migration: ~70 existing `de.freeze(tmp)` call sites → `acknowledge=True`.**
   Freeze now unconditionally surfaces the exclusion list + requires an ack; the
   migration did **not** mask the refusal path — a dedicated no-ack test exercises
   it. Cosmetic residual (craft nit, left as-is): some migrated sites don't
   `redirect_stderr`, so the suite prints surfacing text — harmless noise, not
   worth a 70-site churn.
5. **`approval_provenance` is advisory, never hashed** — it is bookkeeping
   alongside `approval_status` (excluded from `definition_hash`), so editing it does
   not re-freeze; it rides in the ledger row for downstream legibility.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Front door untouched. |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board` at close-out. |
| `docs/product-vision.md` | `no-op` | No behavior/scope drift. |
| `docs/architecture.md` | `no-op` | No module-boundary change — freeze gains flags + a bookkeeping field; the shared `fidelity_eval` is untouched. |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / templates | `no-op` | Spec 028 still in flight (028-03 open); no primer refs to 028. |
| `docs/inbox.md` | `no-op` | Nothing resolved by this slice. |
| `docs/refinement-todo.md` | `no-op` | No new deferred decision (the `reviewed`-enforcement deferral is 028-03's scope, tracked by that slice, not a refinement-todo). |
| `docs/memory/**` | `no-op` | No new durable term/learning beyond the ADR/spec record. |
| `docs/decisions/README.md` / ADR index | `no-op` | No ADR touched (realizes accepted ADR-0033). |
| `skills/design-eval/{design_eval.py,score.py,test_design_eval.py,SKILL.md}` | `updated` | Freeze surfacing/refusal/provenance + CLI flags + exclusion summary + self-approved advisory + ledger field + tests; host packages rebuilt (drift clean). |
| `skills/design-eval/templates/config.example.json` | `no-op` | Owned by 028-01 (the v2 `dimensions`/`ignore` example); appears in `main...HEAD` only as bundled-branch over-report, untouched by 028-02. |
