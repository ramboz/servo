---
slice: 003-07 — portable-guardrails
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-06-13T01:12:14Z
prompt_source: independent read-only craft review of skills/agent-loop/{loop,test_loop}.py + SKILL.md + docs/architecture.md
---

VERDICT: pass

REASONING:
The 003-07 code is high-craft and idiomatic: it matches loop.py's established
conventions throughout — `(value, breadcrumb)` tuple returns
(`_ensure_vendored_gate`, `_parse_claude_version`), the `REASON_*` taxonomy
(`REASON_DIRTY_TREE`, `REASON_GATE_VENDOR_FAILED`), fail-closed posture,
`subprocess.run`/`Popen` with `FileNotFoundError`/`OSError` guards, and dense
rationale comments tying each decision to ADR-0008 verdicts. The tricky edge
cases are handled correctly and well-commented: version parsing tolerates
`(Claude Code)` suffixes and pre-release tags; the porcelain parse excludes `??`
and slices `line[3:]` (so a rename `orig -> new` is captured intact);
git-not-installed degrades to "skip" not "refuse"; settings parse errors are
surfaced not crashed; `allowManagedHooksOnly` binds only in the managed tier;
vendoring is genuinely idempotent (byte-compare before rewrite); and
`--explain-routing` early-returns before the `--prompt` check. The routing
precedence in `main()` is sound (explicit `loop` short-circuits the probe,
explicit `goal` refuses on an unsupported host, `auto` downgrades + logs). Tests
are hermetic (isolated `$HOME`, neutralised managed layer, monkeypatched
version/audit, PATH-shadowed mock claude); the `_run_loop` `--driver loop` pin
and `MOCK_CLAUDE_VERSION` bump are well-justified accommodations of the new
`auto` default, not masking. SKILL.md and architecture.md are accurate and
complete against the DoD. No blocking issues.

SPECIFIC ISSUES:
1. [Low] `_managed_settings_paths` hardcoded OS paths → subprocess routing tests
   silently depended on the host having no real managed-settings.json. — FIXED:
   added the `SERVO_MANAGED_SETTINGS_PATH` env seam; the subprocess helpers
   (`_run_raw` / `_run_goal`) now neutralise the managed layer for hermeticity,
   and a new end-to-end managed-tier refusal test exercises the seam.
2. [Low] double `claude --version` capture on the goal path (routing probe +
   state init). — Acknowledged with an inline comment; trivial sub-second cost.
3. [nit] two synthetic preflight run-ids per refused fresh run. — Harmless
   (informational-only ids); left as-is.
4. [nit] `gate = gate_path` redundant rebind in `_compose_goal_prompt`. — FIXED:
   removed; the prompt uses `gate_path` directly. No injection risk (the path is
   servo's own vendored path; the seed is the user's own task text passed to
   their own `claude`, never shell-evaluated by loop.py).

RECONCILIATION NOTES:
- The dirty-tree brake excludes untracked files by design so servo's own run
  artifacts (`.servo/`, the vendored `gate.py` at an untracked path) never
  self-trip it; loop-mode `--resume` skips the check (a resumed tree is
  legitimately mid-flight). Documented in SKILL.md + architecture.md.
- `SERVO_MANAGED_SETTINGS_PATH` is a new env seam (mirrors `v3_audit_env.py`'s
  OS-path logic; defaults to the real OS paths in production).

PROVENANCE: jig:reviewer (independent, read-only, context-free). All findings
were [Low]/[nit] (non-blocking); the actionable ones were addressed inline and
re-verified (003-07 subset 44 passed, ruff clean, full test_loop.py 230 passed).
