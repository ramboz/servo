---
slice: 030-01 — eval-component-signal
pass: craft
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-18T16:51:53Z
prompt_source: review.py pr-review --richer-skill none
substrate: non-interactive
---

**VERDICT: PASS** (craft / pr-review, round 1 — fresh `general-purpose` reviewer, no `[blocker]`; verified 94/94 + host-drift-clean + ruff-clean locally).

A tight, well-scoped realization of ADR-0036, confined to `suitability.py` (eval-detection helpers + a threaded `eval_signal` through decide/build_trace/_rule_table + a judged-only advisory branch + `render_human`), its two test files, and SKILL.md, with drift-clean host mirrors. No `oracle.sh`/`gate.py`/loop change, no schema bump (`schema_version` stays 1), and `eval_signal` is returned from `analyze()` for `--explain` but deliberately never persisted — so the "widen `has_signal` only" promise holds.

Strengths (worth repeating): `_is_reviewed_frozen_eval` gives each freeze fact its own early-return and `_write_eval_config`'s independently-suppressible kwargs let the AC2 negatives isolate one predicate apiece (non-vacuous mutation coverage); AC6/AC7 run against the non-stubbed `oracle_plan.py` with without-eval controls, grounding the scope boundary in the real lexical classifier; the `_GOLDEN_DECIDE` fence pins exact pre-slice `decide()` outputs byte-for-byte across `eval_signal ∈ {False, True}` and asserts `eval_signal` never leaks into the persisted artifact; `test_alias_map_matches_producer_source` guards the closed alias set against drift without importing the heavy producers.

Three non-blocking `[nit]`s (reconciliation-log items, applied in reconciliation): (1) rule-3 message prose not source-aware (same finding as compliance); (2) `render_human` infers the judged-only case from advisory-presence rather than the decided reason code — a safe-today implicit coupling; (3) optional path-separator hardening in `_eval_config_dir` (install.json is servo-authored, so negligible). No `[spec]`-tagged issues.
