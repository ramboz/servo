---
slice: 016-02 — run-consume
pass: craft
verdict: pass
reviewer: pr-review (installed skill)
reviewed_at: 2026-07-02T22:31:22Z
prompt_source: review.py pr-review docs/specs/016-execution-planner/spec.md 016-02
---

Craft pass (`pr-review`, using the installed `~/.claude/skills/pr-review/` rubric)
on 016-02 — run-consume. Reviewer: general-purpose (fresh, read-only).

**Verdict: PASS** (no blockers).

Scope matches the slice precisely: consumer-only (producer untouched), `prompt_ref`
not consumed (correctly deferred to 016-05, `--prompt` stays required), generic
`--plan <path>` with no spec-id derivation. The two-seam resolution (driver above
the routing probes, budget above the dispatch call) is correct, and the
load-bearing AC3-key subtlety — never writing plan values into `args.*` so the
goal-driver brake-drop keys only on explicit flags — is implemented cleanly and
directly tested. Fail-closed plan reads faithfully mirror the existing `_load_state`
idiom.

**Nits (→ reconciliation log, none blocking):**
1. `loop.py:3237-3244` (now hoisted) — plan-sourced budget values skip the argparse
   range/type validation (only `args.*` is guarded). Unreachable via the current
   `compiled` producer; belongs to 016-03 (clamp/validate hand-authored plans).
2. `loop.py` driver resolution — a plan-sourced `driver` bypasses the argparse
   `choices` guard (`_decide_route` treats an unrecognized value as `auto`).
   Unreachable via the current producer (`DEFAULT_DRIVER="auto"`); 016-03 territory.
3. `_load_plan` / `_resolve_from_plan` lacked return-type annotations while sibling
   helpers have them — **FIXED this cycle** (annotations added).

**Strengths called out:** `_resolve_from_plan`'s docstring documents *why* plan
values stay in fresh locals (the exact collision the frame-critique flagged, made
legible for future maintainers); `_load_plan` mirrors the `_load_state` fail-closed
idiom with clear reason codes; test hygiene strong (`_run_raw` exercises real
defaults; a stray-`plan.json`-in-target test guards the no-spec-id-derivation
invariant; AC-to-test-class mapping is 1:1).
