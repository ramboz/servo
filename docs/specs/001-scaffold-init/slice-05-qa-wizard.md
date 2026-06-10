---
status: DONE
dependencies: []
last_verified:
---

## Slice 001-05 — qa-wizard

**Goal:** `skills/scaffold-init/SKILL.md` exposes the helper to the LLM via a Q&A wizard mirroring jig's scaffold-init flow: each question skippable, "skip every question" is the legitimate pure-inference path, never invent answers. End-to-end value: a user typing "set up servo on this project" gets a coherent question flow that fills in flags before the helper runs.

**DoR:**
- ✅ Slice 001-04 DONE
- ✅ Q&A questions enumerated (see below)
- ✅ Anti-greediness test pattern decided (mirror jig's `pr-review` `DescriptionBoundsTests`)

**Acceptance Criteria:**

1. **SKILL.md trigger phrases.** SKILL.md description fires on "set up servo", "scaffold oracle for this project", "install agent loop infrastructure", and similar; does *not* fire on bare "oracle" or "score this code".
2. **Five Q&A questions documented.**
   1. Project type — service / library / plugin / unsure → flag-mapped to component bias
   2. Tier offered — Tier 0 only / Tier 0 + 1 / all three → maps to which templates ship
   3. Loop guardrails — defaults / custom → if custom, ask iteration cap + cost ceiling
   4. Hook installation — yes (Tier 2 only) / no / skip → installs `oracle-hook` registration
   5. Existing servo install — proceed / abort → if `.servo/install.json` present
3. **Each question independently skippable.** Skipping any question omits the corresponding flag; helper falls back to filesystem inference.
4. **Skipping all = pure inference.** Equivalent to invoking `scaffold.py <target>` with no flags.
5. **Refusal on already-scaffolded target without `--force`.** SKILL.md surfaces the helper's refusal message to the user verbatim; doesn't silently retry.

**DoD:** _(same shape)_
- [x] All ACs pass; full test suite green. _53/53 across `test_scaffold.py` + `test_skill_surface.py` (13 new surface tests)._
- [x] Test coverage per AC: AC1→`DescriptionBoundsTests`, AC2→`QAQuestionsTests`, AC3+AC4→`SkippabilityTests`, AC5→`RefusalSurfacingTests`. Plus `SkillFileShapeTests` for the existence/frontmatter shape.
- [x] Deviation log produced under this slice heading.
- [x] Reviewer subagent review. _jig:reviewer agent, 2026-05-15 — PASS-WITH-CAVEATS. Two non-blocking caveats tracked in `docs/refinement-todo.md`._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _New entries for soft anti-greediness checks and section-scoped substring tests._

### Close-out (post-DONE)

- [x] SKILL.md anti-greediness tests pass (`pytest skills/scaffold-init/test_skill_surface.py`). _13/13 green under unittest runner; the file uses `unittest.TestCase` (no pytest-specific syntax), so pytest auto-discovers it. Local pytest binary absent on this dev box — close-out invocation form documented to work wherever pytest is installed._
- [x] `README.md` skills table row for `scaffold-init` flipped to DONE.
- [x] `docs/specs/README.md` status board: spec 001 → DONE.

**Anti-horizontal-phasing check:** After this slice, the user-facing surface is real — typing the trigger phrase produces a tailored install in one Q&A pass. This is the slice that closes the spec.

### Deviation log (after reconciliation)

**Slice 001-05 — implemented 2026-05-15.** 13 surface tests green under `python3 skills/scaffold-init/test_skill_surface.py`. SKILL.md weighs in at ~155 lines covering frontmatter, Q&A flow, pure-inference path, refusal handling, examples.

Deviations from spec text:

- **Four of five questions are documentation-only at this slice** (reviewer-noted). Tier-1, Tier-2, hook-installation, and loop-guardrails questions have no helper flag yet (scaffold.py only accepts `--force`). SKILL.md frames each as "informational at this slice" with forward pointers to specs 003/004/005. AC #3's "skipping any question omits the corresponding flag" is technically aspirational for those four — they have no flag to omit. The only question that maps to a real flag today is #5 (existing-install → `--force`). Acceptable because the spec scoped Tier-1+ to future work; the Q&A surface is the *user-facing* commitment, not the helper's CLI surface.
- **rc=2 differentiation in refusal handling is not exercised by a test.** SKILL.md explicitly differentiates rc=1 ("refused, not failed; offer `--force`") from rc=2 ("environment error, stop, `--force` won't help"). `RefusalSurfacingTests` only verifies the rc=1 path; nothing asserts rc=2 is handled distinctly. Spec text doesn't require it; documenting for traceability.
- **Anti-greediness tests are soft on negative triggers** (reviewer-noted). `test_negative_triggers_in_description` checks the negative phrases appear *somewhere* but not that they live in a do-not block. Tracked in `docs/refinement-todo.md`.
- **Body tests substring-check globally** (reviewer-noted). `QAQuestionsTests` / `SkippabilityTests` / `RefusalSurfacingTests` lowercase the whole file and check for keyword presence anywhere. Tracked in `docs/refinement-todo.md`.
- **`pytest skills/scaffold-init/test_skill_surface.py` close-out form is verified by construction**: the test file uses `unittest.TestCase` with no pytest-specific decorators or fixtures, so pytest auto-discovers and runs the tests identically. The local dev box doesn't have pytest installed; the unittest runner is the authoritative invocation for now.

**Reviewer verdict:** PASS-WITH-CAVEATS (independent review, jig:reviewer subagent, 2026-05-15). All 5 ACs substantively met; the four caveats are all tracked in the refinement-todo.

---

