---
status: DONE
dependencies: []
last_verified:
---

## Slice 002-05 — qa-wizard

**Goal:** `skills/quality-gate/SKILL.md` exposes the helper to the LLM. Mirrors the `scaffold-init` SKILL.md shape: trigger phrases the skill fires on, explicit negative triggers, refusal-handling guidance, examples. No Q&A flow needed — the gate has few user-facing knobs — but a short "options" section covers `--json`, `--timeout`, and the `audit` subcommand. End-to-end value: typing "score this project" or "run the oracle" surfaces the gate naturally.

**DoR:**
- ✅ Slice 002-04 DONE
- ✅ Anti-greediness tests pattern reused from `skills/scaffold-init/test_skill_surface.py` (`DescriptionBoundsTests`)
- ✅ Trigger phrase set agreed (positive: "score", "run the oracle", "run quality gate", "check the oracle"; negative: "set up", "install", "scaffold", "fix the test")

**Acceptance Criteria:**

1. **SKILL.md trigger phrases.** SKILL.md description fires on "score this code", "run the oracle", "run quality gate", "what's the oracle score?", and similar; does *not* fire on "set up servo" / "scaffold oracle" (those are spec 001's territory) nor on "fix the failing test" / "make tests pass" (out of scope).
2. **Options section documented.** The body lists `--json`, `--verbose`, `--timeout <seconds>`, and the `audit` subcommand with one-line descriptions and an example invocation each.
3. **Refusal handling.** SKILL.md tells the LLM how to react to rc=2 — distinguish missing-oracle (suggest `/servo:scaffold-init`) from missing-manifest (same) from timeout (offer to re-run with a longer `--timeout`) from unparseable output (surface raw stderr). Do NOT silently retry.
4. **Audit example.** At least one example shows a user asking "what does this servo install include" → the LLM runs `gate.py audit <target>` and surfaces the output.
5. **No SKILL.md regressions for scaffold-init.** `skills/scaffold-init/test_skill_surface.py` still passes; the new `skills/quality-gate/test_skill_surface.py` passes too.

**DoD:** _(same shape)_
- [x] All ACs pass; both surface test files green. _18/18 in `quality-gate/test_skill_surface.py`; 13/13 in `scaffold-init/test_skill_surface.py` regression; 75/75 in `test_gate.py`; 40/40 in `test_scaffold.py`. Total 146 tests across four files._
- [x] Test coverage per AC: AC1→`DescriptionBoundsTests` (4 tests, including positive + negative + audit trigger + sibling-pointer assertions). AC2→`OptionsSectionTests` (5 tests, `--json` + `--verbose` + `--timeout` + audit + examples). AC3→`RefusalHandlingTests` (4 tests, refusal section + reason taxonomy + no-silent-retry + recovery pointers). AC4→`AuditExampleTests` (3 tests, presence + install contents + no-oracle assertion). AC5→cross-skill regression by running both surface test files (passes confirmed).
- [x] Reviewer subagent review. _2026-05-18, PASS verdict (clean). Four non-blocking caveats around surface-test substring looseness — same family as the pre-existing 001-05 entries in `docs/refinement-todo.md`._
- [x] Implementation review passed.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated. _One new entry: surface tests for quality-gate inherit the loose-substring pattern from scaffold-init (sibling refinement-todo entries share a fix path). Reasons not enumerated in surface tests (`manifest_malformed`, `manifest_invalid_key`, `target_*`, `invocation_failed`) covered by `test_reason_field_documented`'s common-six subset; broader coverage deferred._

### Close-out (post-DONE)

- [x] SKILL.md anti-greediness tests pass (`python3 skills/quality-gate/test_skill_surface.py`). _18/18 green; pytest auto-discovery works because the file uses `unittest.TestCase` with no pytest-specific syntax (matches the 001-05 pattern)._
- [x] `README.md` skills table row for `quality-gate` flipped to DONE.
- [x] `docs/specs/README.md` status board: spec 002 → DONE.

**Anti-horizontal-phasing check:** After this slice, the user-facing surface is complete — typing a trigger phrase produces a real gate invocation with structured output and timeout safety. This is the slice that closes the spec.

### Deviation log (after reconciliation)

**Slice 002-05 — implemented 2026-05-18.** 18 surface tests green in `skills/quality-gate/test_skill_surface.py`; 13 surface tests in `scaffold-init/test_skill_surface.py` still green (no sibling regression). End-to-end check: SKILL.md frontmatter declares the skill, lists positive + negative triggers, points at the sibling `/servo:scaffold-init` for scaffolding requests; body documents the three options (`--json`, `--verbose`, `--timeout`) + audit subcommand + the 11-reason refusal taxonomy + recovery pointers + concrete examples.

Deviations from spec text:

- **Refusal table enumerates 11 `reason` codes**, not just the 4-5 named in AC #3 (missing-oracle, missing-manifest, timeout, unparseable output). The taxonomy locked in slices 002-01..04 is: `target_missing`, `target_not_directory`, `manifest_missing`, `manifest_malformed`, `manifest_invalid_key`, `oracle_missing`, `oracle_not_executable`, `invocation_failed`, `timeout`, `unexpected_exit`, `unparseable_oracle_output`. SKILL.md documents all 11 with recovery hints; surface tests only assert the 6 most common (`test_reason_field_documented`). Broader enumeration in tests deferred.
- **Trigger-phrase substring assertions remain loose**, inheriting the pattern from `scaffold-init/test_skill_surface.py`. Same caveat as the pre-existing 001-05 refinement-todo entries. Not regressed by this slice.
- **`SERVO_GATE_TIMEOUT` env var documented inline with `--timeout`** in the Options table. Spec didn't require it be discoverable from SKILL.md (env vars are usually invisible to the LLM), but surfacing it here makes the timeout knob fully visible in one place.
- **Audit example walks through the user-facing UX**, not just the helper invocation. Spec AC #4 said "at least one example shows a user asking...". SKILL.md has the audit example formatted as a user/assistant exchange + the expected stdout structure, so the LLM has a template to follow.

**Reviewer caveats not addressed in-flight** (logged here for traceability):

- Surface tests' loose-substring pattern (e.g., `"longer"` in `test_recovery_pointers_present`) inherits the 001-05 entries already in `docs/refinement-todo.md`. New refinement-todo entry added for quality-gate's variant.
- Pre-existing 002-01..04 entries in `docs/refinement-todo.md` still apply.

**Reviewer verdict:** PASS (independent review, `jig:reviewer` subagent, 2026-05-18). All 5 ACs met by observable surface tests; refusal table enumerates the closed `reason` taxonomy with recovery hints; sibling skill (`/servo:scaffold-init`) explicitly pointed-at for out-of-scope triggers; cross-spec regression on `scaffold-init/test_skill_surface.py` confirmed green. **Spec-level verdict from the reviewer:** spec 002 is ready to mark DONE after dogfood + close-out actions land.

---

