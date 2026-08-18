---
status: DONE
dependencies: [adr-0009]
last_verified: 2026-08-18
---

## Slice 012-04 — guided-skill-surface

**Goal:** Ship the `/servo:design-eval` surface — `SKILL.md`'s guided flow plus
`templates/config.example.json` — so a project can be walked from "we have a
mockup" to an installed, frozen `score_design_fidelity` component without
reading the source.

**DoR:**
- ✅ **012-01..03 supply the mechanism** the skill narrates.
- ✅ **House trigger style is settled** by the sibling skills
  (`/servo:spec-oracle`, `/servo:oracle-hook`): explicit fire / do-NOT-fire
  bounds plus a Q&A section.

**Acceptance criteria:**
1. `SKILL.md` documents the full flow (init → author config → capture refs →
   freeze → install → run) with fire / do-NOT-fire trigger bounds.
2. `templates/config.example.json` is a runnable starting point covering the
   screen set, rubric, pinned model, and `n`/`k`/`δ`/threshold.
3. The skill states the ownership split — servo owns the mechanism, the
   project owns the policy — and that servo **scores, it does not prove**.

**DoD:**
- [x] `SKILL.md` + `templates/config.example.json` shipped.
- [x] Registered in the plugin install contract and present on both hosts
      (`hosts/claude`, `hosts/codex`).
- [x] Surface tests — `test_skill_surface.py` ships **25 tests** in the
      sibling-skill pattern, plus two drift tripwires the siblings lack.
- [x] `SKILL.md` documents the full vendored runtime and the `cli` judge
      transport (both corrected during this reconciliation).
- [x] Compliance + craft review verdicts recorded under `reviews/`.
- [x] Reconciliation verdict + deviation log + reconciliation sweep recorded.

### Retro-reconciliation note (2026-08-18)

Retro-recorded with [012-01](slice-01-freeze-and-aggregation-core.md).

**The "no surface tests" gap this note originally described is closed.** At
retro-record time design-eval was the only skill without a
`test_skill_surface.py`; it now ships 25 tests carrying the sibling skills'
anti-greediness pattern plus two things the siblings do not have — assertions
scoped by document section rather than matched globally, and **drift
tripwires** that check the prose against the code (the documented CLI verbs
against `design_eval.py`'s argparse tuple, the documented policy keys against
the shipped template, and the Files table against `init()`'s vendoring list).

Craft review found one blocking defect here, now fixed: after 012-03's
`capture_lib.mjs` extraction, `SKILL.md`'s Flow step 1 and Files table still
listed only `score.py` + `capture.mjs`, so a reader following the doc would
provision a target whose `capture.mjs` could not import at run time. Both now
list the full vendored set, and
`DocumentedFilesMatchInitVendoringTests` fails if they ever diverge again
(verified by mutation).

### Deviation log

- **Retro-lifecycle, not a build deviation** (see 012-01's log).
- **Blocking craft fix:** `SKILL.md` Flow step 1 + Files table now list the
  full vendored runtime (`capture_lib.mjs`, `fidelity_eval.py`), which the
  extraction had left them under-listing — a doc a reader could follow into a
  broken target. `DocumentedFilesMatchInitVendoringTests` guards it.
- **Surface tests added** (`test_skill_surface.py`, 25 tests) — the gap the
  original retro-note described. Two departures from the sibling pattern:
  section-scoped assertions and prose-vs-code drift tripwires.
- **Left as-is (recorded):** the skill's `name: design-eval` uses the bare form
  (shared with `content-fidelity`/`eval-authoring`) rather than the `servo:`
  prefix 9 of 12 skills use; changing a shipped skill's registered name is out
  of scope for this reconciliation.

### Reconciliation sweep

| Artifact | Disposition |
|---|---|
| `skills/design-eval/SKILL.md` | Verified against AC1–3; vendored-runtime + `cli`-transport documentation corrected. |
| `skills/design-eval/templates/config.example.json` | Verified runnable; carries `n`/`k`/`δ`/threshold and ships `approval_status: draft`. |
| `test_skill_surface.py` (25 tests) | Green; Files-table tripwire mutation-verified. |
| Reviews (`reviews/slice-04-{compliance,craft}.md`) | compliance re-pass after DoD correction; craft re-pass after SKILL.md fix. |
