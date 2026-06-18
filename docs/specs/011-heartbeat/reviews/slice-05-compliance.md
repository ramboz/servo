---
slice: 011-05 — skill-and-dogfood
pass: compliance
verdict: pass
reviewer: codex-main-local
reviewed_at: 2026-06-18T16:03:59Z
prompt_source: review.py implementation docs/specs/011-heartbeat/spec.md 011-05 skills/heartbeat/SKILL.md skills/heartbeat/heartbeat.py skills/heartbeat/test_heartbeat.py skills/heartbeat/test_skill_surface.py .claude-plugin/install-contract.json scripts/test_scaffold_runtime.py README.md docs/product-vision.md docs/architecture.md docs/specs/011-heartbeat/slice-05-skill-and-dogfood.md
---

VERDICT: pass

REASONING:
Slice 011-05 is implemented against the fleshed acceptance criteria. The new
`skills/heartbeat/SKILL.md` defines `/servo:heartbeat`, documents the Tier-2
explicit opt-in posture, all four heartbeat guardrails, Q&A flow, closed `{0,2}`
refusal handling, and concrete cron / GitHub Actions `schedule:` / Routine
recipes. `.claude-plugin/install-contract.json` now includes `heartbeat`
(`SKILL.md` + `heartbeat.py`), and the project-local scaffold classifier treats
heartbeat examples as illustrative scheduler commands. The capstone dogfood tests
exercise the real `heartbeat.py run` chain with mock `gh`, real `gate.py`, real git
worktrees, and a deterministic `loop.py` leaf; they cover both a passed outcome
and a whole-heartbeat budget halt leaving remaining findings open.

SPECIFIC ISSUES:
- [strength] skills/heartbeat/SKILL.md:1 — the frontmatter trigger bounds are
  narrow and route sibling territory to the existing servo skills.
- [strength] skills/heartbeat/test_skill_surface.py:35 — the surface tests assert
  install-contract inclusion, trigger placement, guardrails, Q&A, refusal reasons,
  and scheduler recipes without relying on a YAML parser dependency.
- [strength] skills/heartbeat/test_heartbeat.py:3299 — `HeartbeatDogfoodTests`
  verifies the end-to-end path with real git worktree/provisioning behavior and
  the existing untrusted-data prompt framing.
- [strength] scripts/test_scaffold_runtime.py:422 — classifying `heartbeat.py` as
  illustrative keeps scaffold command coverage strict without trying to run
  scheduler-shaped examples in a bare scaffold smoke test.

RECONCILIATION NOTES:
Record that implementation required no changes to `heartbeat.py`; the shipped
011-01..04 runtime already satisfied the capstone behavior. The slice adds the
user-facing skill surface, install-contract registration, tests, and close-out
docs.
