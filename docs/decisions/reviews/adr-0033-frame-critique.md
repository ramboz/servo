---
adr: 0033
pass: frame-critique
verdict: pass
reviewer: jig:architect (frame-critique subagent)
reviewed_at: 2026-08-28T00:52:44Z
prompt_source: review.py frame-critique adr-0033
---

Frame-critique verdict: **pass** (round 4 of 4).

Reviewer: jig:architect subagent (adversarial frame-critique, ADR-0020 OQ2/OQ3),
grounded against ADR-0005, ADR-0034, skills/_common/fidelity_eval.py, and
skills/design-eval/score.py (freeze machinery verified: rubric hashed as opaque
sha256_text and checked verbatim in validate_freeze, excluded from definition_hash).

Convergence (the anti-gaming remedy — the stubborn one, and the field report's own
lesson enacted on our own ADR):
- Round 1 (needs-changes): "prevention" rested on a non-motivated reviewer never
  established as distinct from the authoring agent, and §4 let the agent self-ack
  via a deliberateness bypass → relocated gaming rather than preventing it. Also a
  definition_hash vs artifact_hash citation slip.
- Round 2 (needs-changes): the §4 fix was not mirrored to §3 — the enumerate-first
  catalogue's anti-OMISSION claim had the same author≠curator dependency (a thin
  catalogue is the isomorphic gaming move); "detectable after the fact" imported a
  detector a detached loop lacks.
- Round 3 (needs-changes): asymmetry on the AUDITABILITY axis — an exclusion is
  self-evidencing (ignore {id,reason} names the drop → auditability unconditional)
  but a thin catalogue evidences nothing (omitted items absent → detecting it needs
  re-enumeration). True structure is a 2×2, and the ADR contradicted itself.
- Round 4 (pass): explicit, internally consistent 2×2 — exactly one cell
  (exclusion→auditability) unconditional, the other three conditional on a distinct
  party; omission degrades to "nothing", not a floor; the contradiction is gone;
  OQ5–6 promote an independent RE-ENUMERATING reviewer as the load-bearing seam.
  One non-blocking observation folded in post-pass: the exclusion floor is
  strategically dominated (a motivated author prefers the invisible omission path),
  so the adversarial case rests entirely on the re-enumerator — now stated outright.

Net: the ADR honestly separates an unconditional record-level auditability floor
(exclusion only) from conditional prevention, names the omission path as the
dangerous one with no reviewer-free floor, and does not claim any property where it
does not hold. Central spec-time open question (OQ1): v1→v2 migration / force
re-author. Load-bearing seam (OQ5–6): whether the autonomous freeze path requires a
distinct re-enumerating reviewer.
