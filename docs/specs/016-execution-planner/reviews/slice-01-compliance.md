---
slice: 016-01 — plan-emit
pass: compliance
verdict: pass
reviewer: maintainer-self-review
reviewed_at: 2026-06-30T00:00:00Z
prompt_source: AC-by-AC compliance check against slice-01-plan-emit.md; maintainer self-review (no independent subagent requested); reviewer read the working tree (uncommitted), not git HEAD
---

VERDICT: pass

PROVENANCE NOTE:
Maintainer self-review of `skills/execution-planner/{execution_plan.py,
test_execution_plan.py}` against the seven ACs. Read from the working tree
(uncommitted at review time). Evidence: new tests 19 passed; full suite 1110
passed; `ruff check .` clean (0.15.17).

REASONING (AC by AC):
1. **Plan artifact shape** — PASS. `PlanShapeTests` asserts every ADR-0016 field
   (`schema_version:1`, `spec_id`, `compiled_at`, `suitability_ref`, `oracle`
   `{path,components,threshold}`, `evaluation_model`, `budget`, `driver`,
   `prompt_ref`, `provenance:"compiled"`), the populated overlay case
   (`ac_count`/`residual`), the **null** overlay case, threshold parsed from
   `oracle.sh`, and stable key order (schema_version first).
2. **References, not copies** — PASS. `suitability_ref` is the relative path
   `.servo/suitability/<id>.json`, not the verdict string; no `verdict` key in the
   plan; overlay referenced by `spec_oracle_id` + counts, not check bodies.
3. **`suitable`-only precondition (the 015-03 seam)** — PASS. `needs_evidence`,
   `unsuitable`, and a missing artifact each exit 2 with the right reason
   (`suitability_not_suitable` / `suitability_missing`) and write **no** plan;
   `suitable` emits. This is the Compile gate 015-03 was deferred to build.
4. **Budget from the guardrail source of truth** — PASS. `budget` equals
   `loop.py`'s public defaults (`5/2.0/0.75/3`); the test duplicates them as a
   tripwire so a loop.py default change reddens here.
5. **Git-ignored, atomic, read-only** — PASS (with note). Atomic (no leftover
   `.tmp`), read-only (install.json / oracle.sh / suitability bytes unchanged),
   and the plan lands under `.servo/plans/<id>/`. *Note:* the "git-ignored" claim
   is satisfied by writing under `.servo/` — which **scaffold-init (001)** marks
   ignored in the target; 016-01 writes to that conventional location and does not
   manage the target's `.gitignore` (out of scope). Verified in the servo repo
   itself where `.servo/` is ignored.
6. **Closed env-error contract** — PASS (with additive reason codes). `spec_missing`
   / `manifest_missing` / `suitability_missing` / `suitability_not_suitable` all
   exit 2 with no partial write; never exit 1. Two **additional** fail-closed
   reasons ship beyond the AC's enumerated set — `oracle_missing` and
   `suitability_malformed` — logged as deviations (sound extensions, same spirit
   as 015-01's `manifest_malformed`).
7. **Idempotent recompile** — PASS. `PlanRecompileIdempotentTests` shows a second
   compile is byte-stable except `compiled_at`; `provenance` stays `compiled`.

SPECIFIC ISSUES:
(none blocking) — see the deviation log for the two additive reason codes and the
`prompt_ref` absolute-path limitation; both are craft/reconciliation items, not
compliance failures.

CROSS-CUTTING:
- Scope honest: touched only `skills/execution-planner/` (new skill helper) + the
  spec/ADR/board docs. No existing caller changed (016-02 teaches Run to read the
  plan; not this slice). `git status` confirms.
- Dependency-free invariant preserved: `loop.py` budget defaults are duplicated as
  constants, not imported (mirrors heartbeat.py).
- Contract surface: adds one new artifact (`plan.json`) exactly per ADR-0016; no
  change to `oracle.sh` / `gate.py` / `loop.py` behavior, so no ADR owed
  (implements the accepted ADR-0016).
