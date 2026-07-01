---
slice: 016-01 — plan-emit
pass: craft
verdict: pass-with-nits
reviewer: maintainer-self-review
reviewed_at: 2026-06-30T00:00:00Z
prompt_source: code-quality / idiom / edge-case review of execution_plan.py + test_execution_plan.py; maintainer self-review; read from the working tree
---

VERDICT: pass-with-nits

REASONING:
The helper mirrors the established servo skill shape (`suitability.py` /
`heartbeat.py`): a closed `EnvError(reason, message)` → exit 2, a pure
`compile_plan()` that raises before any write, a separate atomic `write_plan()`
(`tmp` + `os.replace`, insertion-order JSON, no `sort_keys` so the ADR-0016 key
order and AC7 idempotency both hold), and an `add_subparsers` CLI. Inputs are read
by identity and never copied. Dependency-free is respected (budget constants
duplicated, not imported). Preconditions are ordered so the headline `suitable`
gate fires before the manifest/oracle reads.

SPECIFIC ISSUES (all Low; none blocking):
- **`prompt_ref` is an absolute path.** `str(spec_path.resolve())` embeds a
  machine-specific absolute path into a project-owned artifact; the spec typically
  lives outside the target, so a relative ref isn't always available. Acceptable
  for v1 (assumption A2), but flagged for 016-02/03 when the run actually consumes
  `prompt_ref` — a relative-when-under-target rule may be wanted. Logged in the
  deviation log.
- **`_load_evaluation_model` swallows a corrupt overlay to `None`.** A
  present-but-unreadable `checks.json` is treated as "no overlay" rather than an
  env error. Intentional (the overlay is optional enrichment; a baseline-only
  target legitimately has none) and documented in the docstring — but it does hide
  a genuinely corrupt overlay. Kept as-is; noted.
- **Test name slightly over-promises.** `test_editing_referenced_suitability_not_
  reflected_in_plan` asserts the plan carries no copy of the verdict body (no
  `reasons` in the serialized plan) rather than literally editing-then-reading.
  Since the plan stores only a path this is equivalent, but the name reads more
  ambitiously than the assertion. Cosmetic.

CROSS-CUTTING:
- Docstring is accurate and cites ADR-0016 + the 015-03 seam; the module header
  documents the closed exit contract like its siblings.
- Threshold parse is defensive (regex + `DEFAULT_ORACLE_THRESHOLD` fallback,
  tolerant of an unreadable oracle) without over-engineering.
- No security surface: reads local files only, no subprocess, no untrusted-content
  interpolation (unlike heartbeat's dispatch prompt).
