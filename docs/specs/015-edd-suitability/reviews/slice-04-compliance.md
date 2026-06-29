---
slice: 015-04 — skill-and-explain
pass: compliance
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-06-29T19:30:00Z
prompt_source: review.py implementation docs/specs/015-edd-suitability/spec.md 015-04 skills/edd-suitability/{suitability.py,SKILL.md,test_skill_surface.py} (independent subagent; reads worktree, uncommitted)
---

VERDICT: pass

REASONING:
All five ACs are met by the deliverables and exercised by the five named test
classes non-superficially — the dogfood test drives the REAL `oracle_plan.py`
classifier through an actual `needs_evidence → suitable` verdict flip, and the
`--explain` tests assert ordered trace, a single `decided` rule, and
non-persistence of `rule_trace` on disk. The CLI output modes (human default,
`--json`, `--explain` as a stdout-only superset) are correct across
suitable / needs_evidence / unsuitable; the rule table is defined once and shared
by `decide()` / `build_trace()`. The deviation log is honest; the latent
scaffold-mode gap is appropriately deferred and contained (ILLUSTRATIVE
classification keeps the suite green).

SPECIFIC ISSUES:
- suitability.py:62-64 (Medium) — `DEFAULT_ORACLE_PLAN` resolves to a
  `spec-oracle` sibling, but spec-oracle is NOT in `install-contract.json`
  `required.skills`, so scaffold-mode never vendors `oracle_plan.py`; a scaffolded
  `suitability.py` is non-functional there without manual wiring. The deviation
  log framed it as a prefix/override nuance; the root cause is missing vendoring.
  **Addressed in-pass:** deviation-log entry sharpened to name the
  missing-vendoring cause + the (a)/(b) decision; follow-up task filed. Plugin
  mode (today's actual use) is sound. Not a blocker for an Interface-axis slice.
- examples/needs-evidence-then-suitable.md (Low) — the fixture carries no
  `spec_id` frontmatter, so `analyze()` derives the artifact name from the parent
  dir → `examples.json`, which could confuse a user following the SKILL.md
  example. **Addressed in-pass:** SKILL.md now documents the
  `<spec-id>.json` = parent-dir-name derivation explicitly (incl. the
  `examples.json` example).

CROSS-CUTTING:
- Principles check clean (deterministic-rules-first with a documented, bounded
  model-assist seam; sibling delegation keeps the skill surface narrow; no new
  verdict logic). Engineering-practices: scope matches the Interface axis; no gate
  wired (ADR-0018); install surfaces green; no new TODO/FIXME; the one latent gap
  is tracked (follow-up task).

RECONCILIATION NOTES:
- Both review findings were resolved in-pass (deviation-log sharpening + SKILL.md
  artifact-name note); recorded in the deviation log.
- DoD items open at review time (jig review evidence + board regen) are closed at
  REVIEWED / DONE close-out, not deviations.
