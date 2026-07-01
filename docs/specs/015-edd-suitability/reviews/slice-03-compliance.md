---
slice: 015-03 — compile-precondition (re-scoped)
pass: compliance
verdict: pass
reviewer: maintainer-self-review
reviewed_at: 2026-06-30T00:00:00Z
prompt_source: AC-by-AC check against the re-scoped 015-03 ACs (ADR-0018); maintainer self-review; read from the working tree on branch 016-01-plan-emit
---

VERDICT: pass

PROVENANCE NOTE:
015-03's implementation surface is the Servo Compile entry point,
`skills/execution-planner/execution_plan.py` (+ `test_execution_plan.py`) — which
is exactly why 015-03 was deferred pending 016. The gate *mechanism* (refuse
unless `suitable`) shipped with 016-01; this slice adds the enrichment the
re-scoped ACs require. Evidence: `test_execution_plan.py` 24 passed (5 new for
015-03); full suite green; `ruff check .` clean.

REASONING (re-scoped AC by AC, ADR-0018):
1. **Compile precondition** — PASS. `CompilePreconditionTests`: a `suitable`
   verdict proceeds (plan emitted); a `needs_evidence`/`unsuitable` verdict exits
   2, writes no plan, and **surfaces the full `reasons` + `missing_evidence`** on
   stderr (verified: the reason code, the missing-evidence `detail`, its `kind`,
   the `blocking` flag, and the re-run instruction all appear). `_format_refusal`
   builds that actionable message from the 015 verdict artifact.
2. **Fail-closed on an unavailable verdict** — PASS. `CompileGateFailClosedTests`:
   a missing artifact (`suitability_missing`) and an unparseable artifact
   (`suitability_malformed`) each exit 2 with no plan — an unavailable verdict is
   treated as non-`suitable`, so a broken analyzer never opens the gate.
3. **Boundary stays honest** — PASS. `BoundaryHonestyTests` asserts
   `heartbeat.py` contains no `suitability` reference (no import, no subprocess) —
   the verdict is a Compile-phase gate only (ADR-0018); the heartbeat keeps
   `gate.py` and 011-02's human-only `skipped` is untouched.

SPECIFIC ISSUES:
(none)

CROSS-CUTTING:
- The retired heartbeat ACs (old AC1–4, AC6) are correctly NOT implemented — no
  heartbeat change, no automated `skipped` writer; the boundary regression test
  guards that invariant going forward.
- No new contract/artifact: the enrichment only changes the stderr text of an
  already-existing refusal path; the `plan.json` schema and exit contract are
  unchanged. No ADR owed (implements ADR-0015 as narrowed by ADR-0018).
