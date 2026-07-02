---
bug: 002
pass: bug-review
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T16:45:05Z
prompt_source: orchestrator bug-review prompt (jig:bug-fix review pass, independent read-only subagent)
---

Independent bug-review (read-only subagent). Fix addresses the confirmed root
cause (`_invoke_claude` argv missing `--settings`), not the symptom. New helper
`_settings_args(target)` forwards ONLY the target's own committed
`.claude/settings.json` via `--settings`, synthesizes no bypass permission-mode,
and returns `[]` when absent (existing targets unaffected). Positive regression
test fails without the fix; negative test guards against over-forwarding.
Goal-driver exclusion is a documented, defensible scope boundary (symmetric
latent issue logged, tied to ADR-0021 / spec 019). `fix_class: local_patch` and
`security_surface: false` are honest. No blockers.
