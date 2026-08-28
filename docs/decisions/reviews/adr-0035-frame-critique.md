---
adr: 0035
pass: frame-critique
verdict: pass
reviewer: jig:architect (frame-critique subagent)
reviewed_at: 2026-08-28T00:52:45Z
prompt_source: review.py frame-critique adr-0035
---

Frame-critique verdict: **pass** (round 3 of 3; passed round 2, re-confirmed after edits).

Reviewer: jig:architect subagent (adversarial frame-critique), grounded against
ADR-0032 (which defers the manual/human path #29 as the next provider family),
ADR-0005, and skills/design-eval/score.py.

Convergence:
- Round 1 (needs-changes): "strictly better than fake-scores / trust the image,
  audit the shot" inverted on detectability — a doctored image got real-judge
  authority with only a ledger token (the channel humans don't read) and no stderr
  advisory, quieter than the loud fake-scores marking; and it borrowed ADR-0032's
  "eyeball the shots" across a deliberate-adversary threat boundary.
- Round 2 (pass, two notes): mandated a loud stderr advisory on every manual run
  (symmetric to fake-scores); dropped "strictly better"; separated selection-bias
  from fabrication; conceded the doctored-image residual is inherent and NOT closed.
- Round 3 (pass): re-confirmed after folding in the two notes — §3 scoped to a
  masquerade-prevention/class tell (NOT a doctoring tell), base-rate asymmetry
  named (fires on ~100% of honest manual runs → habituation), habituation added as
  a kill-criterion. Load-bearing seam (staged-file provider reusing the ADR-0032
  contract, one new provenance token) verified against score.py:493-534/784-801.
  One non-blocking forward-note: the habituation fallback assumes a downstream gate
  consumes design-eval composites — to specify if/when that criterion fires.

Verdict recorded at current ADR text.
