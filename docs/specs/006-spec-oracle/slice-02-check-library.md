---
status: DRAFT
dependencies: []
last_verified:
---

## Slice 006-02 — check-library

**Goal:** Implement the deterministic check primitives and compile
planned checks into a runnable stdlib-only `checks.py` that emits one
JSON line per AC plus a summary score.

**DoR:**
- ✅ Slice 006-01 DONE.
- ✅ `checks.json` schema from 006-01 is stable enough for first
  implementation.
- ✅ Check primitives do not require network access.

**Acceptance Criteria:**

1. **Primitive coverage.** `checks.py` supports command, file presence,
   text invariant, JSON contract, archive inventory, Markdown local-link,
   generated-artifact command, and runtime-reference scan checks.
2. **Structured output.** A run emits JSONL evidence with
   `schema_version`, `check_id`, `ac_id`, `status`
   (`pass`/`fail`/`env_error`/`not_applicable`), and an actionable
   `message`.
3. **Composite score.** The final summary reports
   `passed_checks`, `failed_checks`, `env_errors`, `not_applicable`,
   and `score` in `[0.0, 1.0]`.
4. **Fixture-proven failures.** Each primitive has at least one passing
   and one failing fixture test, and failing diagnostics name the
   offending path/command/key.
5. **Dependency-free.** The generated runner uses only Python stdlib.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Test coverage per primitive, including failure diagnostics.
- [ ] Reviewed by `reviewer` subagent.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` status board updated.

**Anti-horizontal-phasing check:** After this slice, a generated plan can
be executed manually and produce AC-level evidence, even before it is
wired into `oracle.sh`.

---

