---
slice: 015-04 — skill-and-explain
pass: craft
verdict: pass
reviewer: maintainer-self-review
reviewed_at: 2026-06-29T19:34:00Z
prompt_source: review.py pr-review docs/specs/015-edd-suitability/spec.md 015-04 skills/edd-suitability/{suitability.py,SKILL.md,test_skill_surface.py} (independent compliance subagent ran; craft is maintainer self-review)
---

VERDICT: pass

PROVENANCE NOTE:
The compliance pass ran as a fresh independent subagent; this craft pass is a
maintainer self-review against sibling conventions. Independence is weaker than
the compliance pass — flagged for transparency (mirrors 015-01/02's craft
posture).

REASONING:
Scope matches the Interface axis exactly — a skill surface + CLI output modes over
the existing 015-01/02 engine, no new verdict logic, no gate wired. The CLI
follows the house pattern (argparse subcommand, `--json` like `gate.py`); the rule
table was extracted to `_rule_table()` so `decide()` and `build_trace()` cannot
drift; the persisted artifact stays the clean ADR-0015 shape with the trace as an
explicit stdout-only view.

CRAFT NOTES:
- SKILL.md follows the spec-oracle house style (frontmatter fire / Do-NOT-fire
  with per-sibling delegation, helper table, Q&A, refusal/exit semantics, worked
  re-run example). It correctly reflects ADR-0018 (Compile-gate, spec-less
  heartbeat) rather than the retired heartbeat-skip framing.
- The dogfood is a *real* dogfood: it runs the actual `oracle_plan.py` classifier
  (not a stub) and proves the verdict flip, so the documented re-run loop is
  executable, not aspirational.
- Output rendering is readable and bounded (blocking items listed; advisory items
  summarized as a count with a `--json` pointer; re-run hint on `needs_evidence`).
- Both compliance findings were addressed in-pass without scope creep (doc
  sharpening + a SKILL.md note); the genuine cross-skill vendoring gap is tracked
  as a follow-up rather than force-fixed inside an Interface slice.

No blocking craft issues. No new tech debt introduced in this slice's code.
