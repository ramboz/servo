---
status: IN_PROGRESS
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
- [x] `SKILL.md` (6.6 KB) + `templates/config.example.json` shipped.
- [x] Registered in the plugin install contract and present on both hosts
      (`hosts/claude`, `hosts/codex`).
- [ ] Surface tests (the `test_skill_surface.py` pattern the later skills use)
      — **absent for design-eval**.
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

### Retro-reconciliation note (2026-08-18)

Retro-recorded with [012-01](slice-01-freeze-and-aggregation-core.md). Unlike
`scaffold-init`, `quality-gate`, `oracle-hook`, `spec-oracle`, and
`autonomy-readiness`, **design-eval ships no SKILL.md surface tests** — the
anti-greediness / trigger-placement assertions those skills carry have no
equivalent here. Recorded as an open DoD box rather than quietly ticked.
