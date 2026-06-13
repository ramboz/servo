---
slice: 003-07 — portable-guardrails
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-06-13T01:12:14Z
prompt_source: independent read-only review of the working tree (slice intentionally uncommitted pre-landing); skills/agent-loop/{loop,test_loop}.py + SKILL.md + docs/architecture.md against docs/specs/003-agent-loop/slice-07-portable-guardrails.md
---

VERDICT: pass

REASONING:
All six ACs are implemented on disk and pinned by meaningful tests that would
fail on regression. AC1 (idempotent vendoring at the `hook.py`-matching relative
path, used by both the in-transcript and authoritative gate runs), AC2/AC3
(dirty-tree refusal, `--allow-dirty`, non-git skip, tracked-only, resume-skip),
AC4 (uniform `_decide_route` eligibility predicate gating both auto-routing and
explicit-goal refusal), AC5 (`_audit_hook_settings` productionizing
`v3_audit_env.py` + `--explain-routing`), and AC6 (auto default + dirty refusal
on by default) are all present and wired through `main()`. The ADR-0008 hard
constraint is preserved: routing only selects *which driver* runs; it never
touches `gate.py`'s verdict, and the goal driver's authoritative final `gate.py`
run plus the fail-closed `oracle_disagreement` branch keep the oracle as sole
authority. The host-probe seam is read-only (it reads the settings hierarchy and
reuses — does not modify — `hook.py`'s path convention), so it does not
constitute a module-boundary shift requiring `arch_review`.

SPECIFIC ISSUES:
1. [Low] test_loop.py 003-07 section-header comment named non-existent class
   names (`DirtyTreeRefusalTests` / `HostScopeRoutingTests`). — FIXED: comment
   updated to the real class names.
2. [Low] `run_goal_loop` re-invokes `_get_claude_version()` for state capture
   after `_decide_route` already probed it. Deliberate (cheaper than threading
   the value across the main()→run boundary). — Documented inline; not blocking.
3. [Low] `_write_settings` test helper defined but unused (dead helper). — FIXED:
   removed.
4. [Low] DoD wording nuance: the routing matrix lives in a "Host-scope routing"
   subsection rather than literally under "Runtime artifacts"; substantively
   satisfies the DoD. — FIXED: added a cross-reference from "Runtime artifacts"
   to the routing matrix.

RECONCILIATION NOTES:
- `--driver` default flipped `loop`→`auto` (loop.py `main()`): a behavior change
  from 003-06's `loop` default, mandated by AC6 + ADR-0008 ("external driver
  demoted from default"). Fail-safe (auto→loop when ineligible) means no host
  loses functionality; 003-06 loop-driver tests were pinned to `--driver loop`.
- Uniform eligibility predicate `eligible = hooks_permitted and goal_available`
  gates both auto-routing AND explicit-goal refusal — faithful to AC4 (explicit
  `goal` on an unsupported host refuses rc=2 per 003-06 AC6).
- Dirty = tracked-file changes only (excludes `??` untracked) and loop-resume
  skips the check; both intentional (prevents servo's own `.servo/` + the
  freshly-vendored `.claude/skills/.../gate.py` from self-tripping; a resumed
  loop's tree is legitimately mid-flight). In `run_goal_loop` the dirty-tree
  refusal correctly precedes vendoring, so vendoring can never dirty the tree
  ahead of its own check.
- `SERVO_MANAGED_SETTINGS_PATH` is a new (test-motivated) env seam on the loop's
  surface; defaults to the real OS managed paths in production.

PROVENANCE: jig:reviewer (independent, read-only, context-free). Re-review after
a first pass mis-judged the slice from git history (HEAD still at 003-06 because
the work is intentionally uncommitted pre-landing); this pass read the working
tree directly per instruction and confirms the implementation.
