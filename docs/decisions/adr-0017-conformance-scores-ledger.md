---
status: Proposed
date: 2026-06-27
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0017: Conformance scores + trend ledger — servo decorates the jig conformance graph

## Status

Proposed

> **This is the servo half of a paired decision.** The jig half — the
> conformance **graph topology** (which code unit implements which canonical
> element, scope, debt, staleness, sanctioned-divergence, the deterministic
> rungs, and the convergence query) — is **jig ADR-0032** (Proposed, same
> date). Each ADR is the single source for its half; neither restates the
> other. Both are recorded ahead of a committed consumer (the ADR-0005
> "integrate on signal" pattern) and stay **Proposed** until the demand trigger
> fires.

## Context

When an LLM builds a UI incrementally from a canonical design, the work must be
**locally scoped but globally convergent**: each slice implements a portion, yet
the app must converge toward the final design rather than drift into a pile of
individually-correct, collectively-inconsistent screens. jig ADR-0032 introduces
a durable **conformance graph** (canonical element ↔ code unit ↔ verdict) as the
home for this, and splits the work: **jig writes the graph's topology
(deterministic structure); servo writes its scores (non-deterministic
fidelity).** This ADR records servo's half.

servo already ships the per-slice (local) fidelity loop:

- **`/servo:design-eval`** ([ADR-0009](adr-0009-design-fidelity-eval-recipe.md))
  — render the Claude Design reference, screenshot the app at a seeded state,
  vision-judge fidelity n×, confidence-lower-bound, freeze a
  `score_design_fidelity` component.
- The frozen-eval contract + **ledger** ([ADR-0005](adr-0005-eval-oracle-component.md),
  with multimodal eval inputs added 2026-06-11).

What is missing on servo's side is the **global** signal: per-node fidelity
scores that *decorate the jig graph*, and a **convergence trend** (the
gap-to-canonical over successive design versions) read from the ledger.

## Decision (direction — Proposed, not a commitment to build)

servo owns the **score** decorations and the **convergence trend ledger** on the
jig conformance graph:

- **Per-node fidelity verdict** — the frozen `/servo:design-eval` verdict
  (ADR-0005/0009 contract) attached to a graph node as its score slot. jig
  *attests* this verdict onto its review-evidence rails; jig never re-derives it
  (attest-only, jig ADR-0022 boundary — unchanged).
- **Convergence trend ledger** — servo's ledger, read as the *fidelity* signal
  for convergence: did the gap-to-canonical shrink across design versions /
  slices? This is distinct from, and complementary to, jig's *structural*
  coverage (which elements exist / are scoped / drifted). The two together are
  "is it converging?".
- **The VLM (rung-2) fidelity rung** — servo's domain, scoped to the
  composition/hierarchy drift the deterministic rungs (jig's rung-0/1) cannot
  see. Per jig ADR-0032 A6, this is the heaviest and **least load-bearing** rung
  — sequence it last (roadmap P5).

**Boundary:** the conformance graph **topology is single-sourced in jig
ADR-0032**; this ADR does not restate it. servo writes only scores + trend;
reading/writing the graph stays filesystem-only and host-neutral, consistent
with the writer-owned breadcrumb precedent (ADR-0004, ADR-0013).

## Consequences

**Positive.** Reuses the shipped design-eval mechanism + ledger as the per-node
score source — no new eval machinery, just a new *consumer* of the existing
frozen verdicts. Gives "is the app converging?" a fidelity signal that lives
where the scores already are (servo's ledger), rather than forcing jig to
recompute or store scores it does not own.

**Negative / cost.** Two *Proposed* paired ADRs can drift while unbuilt
(mitigated by single-sourcing each half). The trend signal is only meaningful
once enough nodes have frozen verdicts across ≥2 design versions — it is a
late-roadmap capability, not an early win.

**Neutral.** This does not change the attest-only jig↔servo boundary; jig still
never invokes servo or re-derives a score.

## Kill criteria / demand trigger

**Promote Proposed → build only when a real consumer commits to an automated
design gate** (food-log is the existing design-eval consumer; SymPill's Today
screen is candidate #1) **and** the deterministic rungs + per-slice
design_review prove *insufficient* — i.e. a real "individually-fine,
collectively-drifting" incident shows the per-slice score alone misses the
trend. Kill it if structural coverage (jig ADR-0032) + per-slice fidelity
already answer convergence without a trend ledger.

## Alternatives considered

- **servo owns the whole convergence evaluator (topology + scores).** Rejected:
  the graph topology is deterministic structure — jig's domain (ADR-0032);
  putting it in servo over-weights the non-deterministic eval and orphans the
  structural half.
- **jig stores the scores too (no servo half).** Rejected: jig would re-derive
  or duplicate scores it does not own, breaking the attest-only boundary
  (ADR-0005 honesty: a frozen eval's verdict has one owner).

## References

- **jig ADR-0032** — the paired topology half (single source for the graph
  structure, staleness, blast-radius, sanctioned-divergence, deterministic
  rungs, convergence query).
- [ADR-0005](adr-0005-eval-oracle-component.md) — frozen-eval contract + ledger
  (the score source).
- [ADR-0009](adr-0009-design-fidelity-eval-recipe.md) — `/servo:design-eval`,
  the per-slice loop.
- [ADR-0004](adr-0004-session-state-file-format.md), [ADR-0013](adr-0013-servo-available-breadcrumb.md)
  — writer-owned filesystem-contract precedent.
- jig ADR-0022 (pluggable-oracle boundary) — the attest-only seam this rides.
