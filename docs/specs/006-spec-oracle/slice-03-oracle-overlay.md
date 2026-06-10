---
status: DRAFT
dependencies: []
last_verified:
---

## Slice 006-03 — oracle-overlay

**Goal:** Compile a checked plan into an installable oracle overlay:
`oracle.sh.fragment` plus generated `checks.py`, with a score function
that can be added to the target's `oracle.sh` as a normal servo
component.

**DoR:**
- ✅ Slice 006-02 DONE.
- ✅ Spec 002 `gate.py` contract remains unchanged.
- ✅ `# SEED:` component convention from spec 001 is still the install
  mechanism.

**Acceptance Criteria:**

1. **Fragment generation.** The helper writes an `oracle.sh.fragment`
   containing a valid `# SEED:start spec_oracle_<id>` /
   `# SEED:end spec_oracle_<id>` block.
2. **Install command.** An explicit install mode adds the generated
   component to `oracle.sh` without disturbing existing baseline
   components.
3. **Score semantics.** The generated score is the check summary score;
   any env-error check returns oracle component rc=2.
4. **Ledger entries.** Each oracle run appends check evidence to
   `.servo/spec-oracles/<spec-id>/ledger.jsonl`.
5. **Gate compatibility.** `gate.py <target> --json` sees the overlay as
   an ordinary oracle component; no `gate.py` special case is required.
6. **Uninstall or disable path.** Users can remove or disable the
   overlay component without deleting the plan/check artifacts.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Tests install the overlay into a temp servo-scaffolded target and
      verify `gate.py --json` pass/fail/env-error paths.
- [ ] Reviewed by `reviewer` subagent.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.

### Close-out (post-DONE)

- [ ] `docs/architecture.md` documents spec-oracle artifacts.
- [ ] `docs/specs/README.md` status board updated.

**Anti-horizontal-phasing check:** After this slice, `/servo:agent-loop`
can optimize against spec-specific AC evidence using the existing gate
contract.

---

