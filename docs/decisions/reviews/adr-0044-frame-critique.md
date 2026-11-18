---
adr: 0044
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-18T03:04:02Z
prompt_source: review.py frame-critique docs/decisions/adr-0044-required-constraints-cannot-be-averaged-away.md
---

Frame-critique ran two rounds against fresh, independent general-purpose
reviewers, each verifying the ADR's grounding against the shipped code (not the
author's claims).

**Round 1 — needs-changes.** The decision (Option B) was sound — the reviewer
confirmed the required/quality separation in code — but the ADR's *justification*
over-claimed its reach: it framed itself as the keystone for the eval-scoring
cluster (specs 035/039) when (1) spec 039's eval is a graded **quality**
component, and its "re-judge failure is `env_error`, never the cheap score" is
the quality path's own unavailability handling, not an instance of the required
axis; (2) the required runtime restricts required evidence to `command` /
`generated_artifact_command` families, forcing any model-judged required family
to `unknown`, so a graded eval requirement is not expressible at all; (3) spec
035 is an unwritten stub. The ADR also called the required axis "orthogonal",
overstating a per-check flag that, at weight > 0, still feeds the composite.

**Revision.** Re-scoped the ADR to deterministic `command` requirements with an
explicit Scope / Out-of-scope split; corrected the 039 and 035 characterizations;
replaced "orthogonal axis" with "separate verdict"; and moved the
graded/model-judged-requirement question to Kill criteria / Open questions as a
deliberate deferral.

**Round 2 — pass.** All five code-grounding checks held with citations:
(a) the required verdict is computed separately from the weighted composite
(`required_runtime.py` `outcome()` 704-722); (b) a failed required check gates
regardless of score (`test_ac2...` at composite ≥0.99); (c) unknown required
evidence → `required_evidence_unavailable` (rc 2), outranking any score;
(d) weight-0 decouples the quality contribution (with the per-component nuance);
(e) non-command required families are forced to `unknown` (`interpret()`
534-537), grounding the out-of-scope boundary. The deferral premises (035 stub,
039 quality component) were verified true from the specs. The frame survived.

**Two non-blocking precision notes from R2, both applied before recording this
pass:** (1) `weight` is a per-**component** property, not per-check — so the
"weight-0" phrasing now specifies carrying the required check in its own weight-0
component; (2) a lone weight-0 component degenerately sets the composite
(single-component special case), so the phrasing now pairs the weight-0 component
with the scaffold's baseline.

Verdict: **pass.** The decision is sound and grounded in shipped code for its
scoped claim; acceptance (`adr.py accept`) remains the owner's call.
