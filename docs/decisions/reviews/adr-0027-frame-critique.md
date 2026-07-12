---
adr: 0027
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-07-12T04:33:51Z
prompt_source: review.py frame-critique docs/decisions/adr-0027-goal-to-eval-assisted-authoring.md
---

VERDICT: pass (round 3, after two amendment rounds)

Round 1 (needs-changes): the independent reviewer was over-elevated as the safety
mechanism, but a same-distribution reviewer reading the same vague goal shares the
generating model's blind spots on faithfulness; and AC5 claimed a full suitability verdict
at expansion time, repeating the ADR-0018 off-switch (signal-less synthesized spec →
needs_evidence for everything). Fixed: reviewer demoted to an advisory fresh-eyes pass
reliable only on structural defects; the human named the sole per-AC positive-approval gate
with an automation-complacency guard; AC5 narrowed to the criteria split, the full verdict
deferred.

Round 2 (needs-changes): "coverage gaps" was wrongly listed as a reliably-caught structural
check — an *implicit* gap is the dual of a hallucination (epistemic, shared blind spot);
and the human gate (edit/accept/reject presented ACs) had no way to ADD an omitted AC, so
omission fell through both guards (a false criterion of omission). The ADR-0018 citation was
also imprecise (its measured cause was zero-ACs). Fixed: coverage gaps split into
surface-literal (reviewer) vs implicit (human/epistemic); the human gate now includes adding;
citation corrected to lean on ADR-0015's missing-reference-set path with ADR-0018 as a
companion caution.

Round 3 (pass): frame survives; the ADR is honest that safety is no stronger than the human's
per-AC review. Minor polish applied: Decision #2 now states the reviewer receives {goal,
proposed ACs} (not the expansion chain-of-thought); the structural mis-tag example firmed to
"requires a senior editor's sign-off" tagged `deterministic`. Non-blocking note for 008-05:
ensure both the jig:independent-review reuse and the built-in fallback are handed the goal
text alongside the proposed ACs.
