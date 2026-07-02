---
slice: 019-02 — colocate-artifacts
pass: arch
verdict: pass
reviewer: jig:reviewer (independent read-only subagent)
reviewed_at: 2026-07-02T19:48:00Z
prompt_source: review.py arch-review
---

VERDICT: pass

REASONING:
The slice cleanly implements ADR-0023: oracle_dir_for_spec is the single shared
path helper, imported by oracle_plan.py rather than recomputed, eliminating the
three independent path constructions the frame-review flagged. checks.py is
referenced by absolute plugin-install path by default with --vendor-engine as an
explicit, well-documented opt-in for the clone-portability case, and the legacy
.servo/spec-oracles/ location is a narrowly-scoped read-only fallback that
self-obsoletes once a target re-plans. docs/architecture.md is updated
faithfully and consistently with the code.

SPECIFIC ISSUES:
- [strength] oracle_dir_for_spec is a single, well-documented path helper with a
  clear, narrow migration fallback, giving a clean, self-terminating
  deprecation path rather than a permanent dual-path burden.
- [strength] the shared-engine path resolves relative to __file__ (the plugin
  install), the same idiom already used elsewhere, so reference-not-copy costs
  no new resolution mechanism.
- [nit] generate()'s rel_oracle_dir computation silently falls back to an
  absolute path when the spec dir is outside the target root -- plausible in
  multi-repo setups; worth a docstring note (not fixed, low-severity edge case).
- [nit] docs/architecture.md's runtime-artifacts entry doesn't call out the
  version-skew risk of the referenced (unhashed) engine explicitly -- addressed
  during reconciliation via a docs/refinement-todo.md entry.

RECONCILIATION NOTES:
ADR-0023's version-skew risk (an installed oracle.sh.fragment referencing a
plugin-sibling checks.py whose contents can change independently of the frozen
approved_artifacts hash) is real but consistent with ADR-0023's stated
trade-off -- logged to docs/refinement-todo.md during reconciliation rather than
fixed inline (a freeze-mechanism redesign is out of this slice's scope).
