---
slice: 008-05 — goal-to-criteria
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-12T17:32:21Z
prompt_source: review.py pr-review ... 008-05 (re-review)
---

VERDICT: pass

Craft re-review after fixes. Prior [blocker] genuinely closed: from_goal_target(...,
*, force=False) raises EnvError("criteria_exists") for an existing criteria.md/json
BEFORE any claude -p call; --force regenerates; the regression test re-runs with
DIFFERENT mock output and asserts byte-for-byte preservation (a silent clobber would
fail it). All three nits resolved with tests: require_all_approved wired via
`criteria-check`; `_resolve_claude` honors SERVO_EVAL_AUTHORING_CLAUDE_BIN (env beats
PATH); criteria_split raises on missing classifier keys. No new blockers.

Strengths: check-before-side-effect no-clobber guard; structural reviewer
independence (goal + AC list only, separate subprocess).

Nits → reconciliation: `_iso_now` duplicates fidelity_eval.iso_now (cosmetic);
frontmatter `goal: {!r}` is not guaranteed YAML-safe (harmless — nothing YAML-parses
it); criteria_split subprocess has no timeout (local deterministic classifier);
the two-file curation surface (approval in criteria.json, editable ACs in criteria.md)
is intentional per ADR-0027 Decision #5 but a coupling to understand.
