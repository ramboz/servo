---
adr: 0034
pass: frame-critique
verdict: pass
reviewer: jig:architect (frame-critique subagent)
reviewed_at: 2026-08-28T00:52:45Z
prompt_source: review.py frame-critique adr-0034
---

Frame-critique verdict: **pass** (round 3 of 3).

Reviewer: jig:architect subagent (adversarial frame-critique, ADR-0020 OQ2/OQ3),
grounded against ADR-0031/0032 §7, ADR-0005, and skills/design-eval/score.py.

Convergence:
- Round 1 (needs-changes): the draft's "model pinned and verified, or it refuses"
  was a self-report by the judged agent, not a verification — a "frozen subagent
  score" was fake-scores with a protocol wrapper. Recommendation: invert to a
  loud, non-frozen advisory; defer frozen scoring pending a real
  attestation-to-computation binding.
- Round 2 (needs-changes): inversion resolved round 1, but the benefit was
  overclaimed — the field-report user's motive was a GATING number, which an
  advisory does not meet, so the incentive could migrate to "freeze subagent and
  treat the advisory number as the score."
- Round 3 (pass): non-gating is now STRUCTURAL — a subagent-transport eval on the
  oracle entrypoint returns env_error (EXIT_ENV_ERROR=2, score.py:35) and emits no
  stdout composite; the advisory read is reached only via an explicit non-oracle
  command. Benefit reframed as serving attended authoring/iteration, with an
  explicit motive assumption conceding the gating-motivated user is NOT served
  (they need api/cli). Two non-blocking notes: (1) the authoring-read population is
  a load-bearing assumption to weigh against real demand at spec time; (2) the
  gating block must be discriminated by ENTRYPOINT, not attendance, or the attended
  /servo:agent-loop gate leaks — closed post-pass by an ADR clarification stating
  the discriminator is the entrypoint (aligned with the reviewer's own resolution).

Verdict recorded at current ADR text (post-clarification).
