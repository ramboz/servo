---
slice: 020-01 — extract-shared-harness
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-04T03:22:28Z
prompt_source: review.py pr-review docs/specs/020-content-fidelity-eval/spec.md 020-01 ...
---

VERDICT: pass (round 2, after a fix)

Round 1 flagged skills/_common/fidelity_eval.py::definition_hash hardcoding
"viewport" (a design-eval-specific field) into the shared module, plus a nit
about fidelity_eval being loaded twice under independent module objects.
Fixed: definition_hash/validate_freeze now take a generic extra_fields tuple
(default ()); score.py threads _EXTRA_HASH_FIELDS=("viewport",) through thin
wrappers; design_eval.py reuses _score._fe instead of a second independent
load. Verified clean, generic, and well-documented; the new golden-hash
regression test pins a literal sha256 proving byte-identical hashes for
pre-existing frozen configs.
