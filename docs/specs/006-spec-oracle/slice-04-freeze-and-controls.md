---
status: DRAFT
dependencies: []
last_verified:
---

## Slice 006-04 — freeze-and-controls

**Goal:** Add the safety layer that prevents self-grading: approval
state, source-spec hash checks, generated-artifact hashes, and negative
control validation.

**DoR:**
- ✅ Slice 006-03 DONE.
- ✅ The project-owned artifact paths are settled.
- ✅ The first generated check fixtures include at least one controllable
  known-bad case.

**Acceptance Criteria:**

1. **Approval state.** `checks.json` carries `approval_status` with
   values `draft`, `approved`, or `stale`. The oracle overlay refuses to
   score as pass when status is not `approved`.
2. **Source hash validation.** If the source spec content changes after
   approval, the overlay exits with env error and a
   `spec_oracle_stale` message until re-planned.
3. **Artifact hash validation.** Approved generated files carry hashes;
   unexpected modification of `checks.py` or `oracle.sh.fragment`
   refuses with an actionable diagnostic.
4. **Negative-control runner.** A validation command exercises
   generated negative controls and refuses approval if a check cannot be
   made to fail.
5. **Loop protection.** Agent-loop documentation and prompts tell the
   runner not to edit approved spec-oracle artifacts; tests assert the
   prompt contains this constraint.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Tests cover stale source, modified generated artifact, missing
      approval, and negative-control failure.
- [ ] Reviewed by `reviewer` subagent.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.

### Close-out (post-DONE)

- [ ] `docs/architecture.md` documents freeze/approval semantics.
- [ ] `docs/specs/README.md` status board updated.

**Anti-horizontal-phasing check:** After this slice, the oracle overlay
is safe enough to use for unattended implementation without the runner
quietly moving the target.

---

