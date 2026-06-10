---
status: DRAFT
dependencies: []
last_verified:
---

## Slice 006-05 — skill-and-dogfood

**Goal:** Expose the workflow as `/servo:spec-oracle` with clear
anti-greediness bounds, and dogfood it on jig-style specs 046/047 as
worked examples.

**DoR:**
- ✅ Slices 006-01 through 006-04 DONE.
- ✅ At least one jig dogfood target is available locally.
- ✅ The skill name and trigger surface are agreed.

**Acceptance Criteria:**

1. **SKILL.md trigger bounds.** `/servo:spec-oracle` fires on requests
   to generate/specify/evaluate an oracle for a spec, and does not fire
   on "run the oracle" (`quality-gate`) or "iterate on this" (`agent-loop`).
2. **Q&A flow.** The skill asks for target path, spec/slice path,
   baseline commands, and whether to stop after plan generation or
   proceed to install an approved overlay.
3. **Worked examples.** Documentation includes at least two examples
   shaped like jig 046 and 047, showing AC classification and generated
   check families.
4. **Dogfood plan quality.** Running the planner against jig 046/047
   produces plans where the validator/doc/install-contract ACs are
   mostly deterministic and residual judgment is explicit.
5. **No silent approval.** The skill never marks a generated overlay
   `approved` without an explicit user instruction or reviewed approval
   artifact.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Surface tests under `skills/spec-oracle/test_skill_surface.py`.
- [ ] Dogfood plans committed or recorded as fixtures, with any
      non-deterministic ACs named in the deviation log.
- [ ] Reviewed by `reviewer` subagent.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated for any check family deferred.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` status board marks spec 006 DONE.
- [ ] README skill table row marks `/servo:spec-oracle` as shipped.

**Anti-horizontal-phasing check:** After this slice, a user can ask
servo to turn a real spec into an evidence overlay, inspect it, approve
it, and then run the existing agent loop against it.

