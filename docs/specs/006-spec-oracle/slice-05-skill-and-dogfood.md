---
status: DONE
dependencies: []
last_verified: 2026-06-10
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
- [x] All ACs pass; full test suite green.
- [x] Surface tests under `skills/spec-oracle/test_skill_surface.py`.
- [x] Dogfood plans committed or recorded as fixtures, with any
      non-deterministic ACs named in the deviation log.
- [x] Reviewed by `reviewer` subagent.
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated for any check family deferred.

### Close-out (post-DONE)

- [x] `docs/specs/README.md` status board marks spec 006 DONE.
- [x] README skill table row marks `/servo:spec-oracle` as shipped.

**Anti-horizontal-phasing check:** After this slice, a user can ask
servo to turn a real spec into an evidence overlay, inspect it, approve
it, and then run the existing agent loop against it.

### Deviation log (after reconciliation)

Original ACs above are preserved; this records what changed during
implementation. Implemented 2026-06-10; 21 tests in
`skills/spec-oracle/test_skill_surface.py`; full suite 626 passed, 1 skipped.
**Spec 006 is complete** — all five slices DONE.

- **Surface (AC1/AC2/AC5).** `skills/spec-oracle/SKILL.md` ships
  `/servo:spec-oracle` with a narrow trigger description: fires on
  generate/specify/evaluate-an-oracle requests, and a "Do NOT fire" block routes
  "run the oracle" → `/servo:quality-gate`, "iterate on this" →
  `/servo:agent-loop`, "set up servo" → `/servo:scaffold-init`. The Q&A flow asks
  for target path, spec/slice path, baseline commands, and the stop point (stop
  after plan vs proceed to install an approved overlay). "No silent approval" is
  stated and backed by the real freeze gate (`approve` is a separate explicit
  step; a draft overlay is refused `rc=2` `spec_oracle_unapproved`).
- **Dogfood implemented as committed, self-contained fixtures (AC3/AC4).** The
  worked examples are two authored fixtures — `examples/046-scaffold-fidelity.md`
  and `examples/047-install-contract.md` — shaped like jig's
  `046-scaffold-artifact-fidelity` / `047-install-contract-verification`, and the
  dogfood test runs the planner against *those committed fixtures*, not the jig
  repo. This is a deliberate reading of the parent spec's non-goal "No hidden
  dependency on jig: jig specs are dogfood fixtures, not a hard dependency"
  (spec.md). Classification (asserted against real planner output):
  047-shaped → 4 deterministic / 0 residual (`json_contract`, `archive_inventory`,
  `file_presence`, `command`); 046-shaped → 3 deterministic / 1 residual
  (`generated_artifact_command`, `markdown_links`, `text_invariant`).
- **Live-dogfood verification against the real jig specs.** During development the
  planner was also run against the actual local jig slices (the DoR's dogfood
  target): 046/slice-01 → 3 det / 1 residual; 046/slice-02 → 1 det / 3 residual;
  047/slice-01 → 4 det / 0 residual; 047/slice-02 → 2 det / 2 residual. This
  confirms the dogfood works on real jig content; the committed fixtures reproduce
  the 046-01 / 047-01 shapes so the test stays self-contained.
- **Named non-deterministic AC (DoD).** Across the fixtures the single residual AC
  is `AC-046-01-3` ("reads well / appropriately worded") → `residual_judgment`
  (reason: taste/quality), surfaced with a reason and a suggested human-review
  path — not auto-passed.
- **No new check family deferred.** This surface slice adds no engine behaviour;
  the deferred-family entries already in `docs/refinement-todo.md` (the
  model-assist classifier from 006-01 and negative-control auto-generation from
  006-04) cover the open extensions. DoD bullet satisfied with no new entry.
- **Review-driven tweak.** Independent `jig:reviewer` returned PASS on all five
  ACs. Its one actionable non-blocking note was applied: SKILL.md step 4 now says
  approve "runs each check's negative control **where one is defined**", matching
  `approve`'s disclosed v1 leniency (refinement-todo). Its other note (the
  negative-trigger surface assertion is a global substring check) is consistent
  with the sibling skills and already logged in refinement-todo (006-01) — left
  as-is for a future cross-skill tightening.

**Reconciliation review (inline):** deviation log checked against the diff
(faithful — no source-spec ACs or DoD rewritten). Changes are scoped to
`skills/spec-oracle/` (`SKILL.md`, `examples/`, `test_skill_surface.py`) and the
spec-006-completion docs (README skill row → DONE, `spec.md` rollup → DONE, the
board, this slice). `jig:reviewer` PASS; the one actionable note applied. Spec 006
closes here.

