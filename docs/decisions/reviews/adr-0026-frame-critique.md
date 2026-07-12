---
adr: 0026
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-12T04:33:51Z
prompt_source: review.py frame-critique docs/decisions/adr-0026-generic-eval-authoring-surface.md
---

VERDICT: pass (round 3, after two amendment rounds)

Round 1 (needs-changes): the ADR conflated the judge *prompt* (authorable text) with
the judge *payload* (runtime wire format). ADR-0024's forked axis is capture + payload;
the ADR addressed only the prompt, so "any residual AC / only new code is UX"
overreached — verified `fidelity_eval.py` carries no capture/payload code (both live in
each preset's `score.py`). Fixed by scoping to text-judged evals, conceding the non-text
judge payload stays forked (preset-only), and citing content-fidelity (spec 020, DONE) as
the shipped text-judge consumer being generalized.

Round 2 (needs-changes): within text, content-fidelity's judge is a fixed two-slot
reference-comparison (`_prompt(generated, reference)`, score.py:195), and per-field freeze
semantics are hand-classified (`_REFERENCE_FILE_FIELDS`/`_CASE_PIN_FIELDS`, score.py:58,66).
The ADR's 1-slot and 3-slot examples require a configurable multi-field dataset schema +
per-field freeze classification — real runtime work, not "unbake the prompt / honesty for
free." Fixed: Decision #1 now names the multi-field schema as real work and adds a Negative
bullet handing the per-field freeze-classification honesty risk to spec 008; the Verification
obligation (single-input/no-reference case) forecloses a hollow content-fidelity-minus-prompt
implementation.

Round 3 (pass): frame survives. The kind-agnostic-vs-ADR-0024 reconciliation holds
(generality delivered as a separate skill, not a mode-fork of a preset). Carry-forward
(non-blocking): the multi-field schema is strategic-bet scope, exercised by the Verification
obligation rather than a shipped consumer — the ADR now states this caveat explicitly and
spec 008 should track it as bet-scope, not consumer-validated.
