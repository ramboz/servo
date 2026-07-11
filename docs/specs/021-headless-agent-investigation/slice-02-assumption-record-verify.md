---
status: DRAFT
dependencies: [003, adr-0003, adr-0025]
last_verified: 2026-07-11
arch_review: true
---

## Slice 021-02 - record and verify load-bearing assumptions

**Goal:** Have the runner RECORD its load-bearing assumptions in the verdict
block, and the judge VERIFY them. The loop is headless — there is no human to
answer a clarifying question — so instead of silently interpreting an ambiguous
prompt (the current "no clarifying questions" posture), the runner surfaces the
assumption it acted on, and the judge checks it against the code/oracle and
reflects the result in its verdict/reasoning. Amends the ADR-0003 verdict-block
contract; the field shape and any `schema_version` bump are decided in
[ADR-0025](../../decisions/adr-0025-runner-records-judge-verifies-assumptions.md).

**DoR:**
- [ ] ADR-0025 is **Accepted** (decides the `assumptions:` field shape, whether
      it is optional under `schema_version: 1` or forces a bump to `2`, and how
      the judge reflects a violated assumption).

**Acceptance Criteria:**

1. **Runner records.** `agents/runner.md`'s verdict block carries an
   `assumptions:` field (shape/optionality exactly per ADR-0025), reconciled
   with `loop.py`'s strict `schema_version` parser so no valid block is refused.
2. **Runner posture amended.** The "No clarifying questions — make the most
   reasonable interpretation and proceed" guidance is updated to "surface the
   load-bearing assumption in the verdict block instead of silently interpreting."
3. **Judge verifies.** `agents/judge.md` instructs the judge to check the
   runner's recorded assumptions against the code and oracle output, and to
   reflect a violated/unsupported assumption in its verdict and reasoning.
4. **Parser compatibility.** `loop.py`'s `schema_version` refusal path is intact
   — no `verdict_schema_mismatch` regression; if ADR-0025 chooses a bump to
   `schema_version: 2`, `loop.py` accepts `2` and the tests prove both the
   accept and the still-refuse-on-missing-field paths.
5. **Tests.** Surface tests for the runner/judge prompt changes, plus a `loop.py`
   parse test for the new field (accept valid, refuse malformed).

**DoD:**
- [ ] All ACs met; full suite green.
- [ ] ADR-0025 Accepted and linked.
- [ ] Reviewed (compliance + craft + arch, since the verdict-block contract
      changes); evidence recorded.
- [ ] Deviation log + reconciliation sweep under this slice.

**Anti-horizontal-phasing check:** After this slice, a headless run's runner
emits the assumptions it relied on and the judge audits them — an observable,
end-to-end reliability change in the loop's own artifacts, not scaffolding for a
later slice.

### Deviation log (after reconciliation)

_TODO: filled during reconciliation._

### Reconciliation sweep

_TODO: record drift-prone surfaces checked (agent prompts, loop.py parser, ADR
index, README, status board)._
