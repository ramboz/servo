---
status: DRAFT
kind: spike
dependencies: [015-01, 015-02, 011, adr-0015]
last_verified:
---

## Slice 015-05 — suitability-at-the-boundary (spike)

**Question:** Does the EDD suitability verdict have a coherent, *useful* per-finding
form at the heartbeat boundary — and if so, what bridges a spec-less finding to a
verdict — or is suitability a Compile-phase-only gate?

**Time-box:** 1 day.

**Goal:** Resolve the frame-critique unknown that deferred 015-03 with **evidence,
not a guess**. Survey real heartbeat findings, prototype the candidate
finding→verdict bridges and measure their verdict distributions, characterize what
suitability adds *beyond the existing `gate.py` oracle preflight*, and land an ADR
deciding whether/how the verdict gates the heartbeat. The output unblocks 015-03
(re-scope / re-open / retire) and clarifies 015-04's dependency. This is a pure
research slice — its deliverable is a **decision + ADR**, not shipped code (if it
concluded "now ship it," the implementation would be the slice).

**DoR:**
- ✅ **015-03 DEFERRED** with the frame-critique recorded — the unknown is named
  ([[servo-015-03-frame-critique-deferred]] / `reviews/slice-03-frame-critique.md`).
- ✅ **015-01/02 shipped** — a real `suitability.py analyze` to prototype against.
- ✅ **011 `discover` shipped** — can generate real `inbox.jsonl` findings to survey.

**Investigation plan (what produces the data):**

1. **Survey real findings.** Run `heartbeat.py discover` against ≥2 real repos
   (servo itself + one external target) and inspect `inbox.jsonl`. Record the
   field shape per source (CI / issue / commit) and, for each finding, whether
   ANY spec reference is recoverable (issue body/labels, branch name, a commit
   touching `docs/specs/`). **Quantify**: what fraction of findings could
   plausibly name a spec?

2. **Prototype + measure the bridges** (throwaway, scratch-only — nothing lands in
   `skills/`):
   - **(a) ephemeral-spec synthesis** — derive a `spec.md` from a finding's
     title/detail/evidence, run the real analyzer, record the verdict
     distribution. *Hypothesis to test:* findings carry no ACs → near-always
     `needs_evidence` → degenerate (the gate becomes an off switch).
   - **(b) finding-shaped variant** — sketch a rule table over finding *features*
     (source type, evidence presence, target signals) instead of spec ACs; does
     it yield a non-degenerate, defensible verdict distribution on the surveyed
     findings?
   - **(c) target-level gate** — measure overlap with the existing `gate.py`
     oracle preflight + worktree verification; quantify the residual signal
     suitability would add over them.

3. **Characterize the marginal value.** The heartbeat already refuses dispatch
   without an oracle and re-verifies the provisioned worktree with `gate.py`.
   Determine empirically whether the "meaningless green oracle / false pass" risk
   ADR-0015 cites is *already mitigated for findings* by that oracle requirement —
   i.e., does suitability add anything at the heartbeat, or only at Compile (where
   a real spec with ACs exists)?

4. **Decide the home.** If a heartbeat gate is warranted, does it belong in 015,
   in 018 (continuous-evaluation, which extends 011), or a new triage-enrichment
   spec? Is 015-03 re-scoped to Compile-precondition-only and re-attached to 016?

**Findings:** _(filled during IN_PROGRESS — bullet evidence with concrete numbers)_

**Acceptance Criteria (spike exit):**

1. **Data, not assertions.** The survey + prototype results are recorded under
   **Findings:** with concrete numbers (finding counts per source, recoverable-
   spec fraction, per-bridge verdict distributions, preflight overlap).
2. **Each option adjudicated.** Bridges (a)/(b)/(c) and the Compile-only option
   are each accepted or rejected *with their evidence*.
3. **Decision recorded as an ADR.** A new ADR (or a superseding/amendment of
   ADR-0015) records the decision and its consequences for 015-03/04 and the
   heartbeat oracle preflight.
4. **015-03 disposition applied.** 015-03 is re-scoped + re-opened (→ DRAFT)
   against the decided contract, OR retired/superseded — with the spec.md SPIDR
   index and the board updated to match.

**Outcome:** _(set at DONE — e.g. `ADR-NNNN created; spec 015-03 re-scoped/unblocked`,
or `abandoned (reason)`)_

**DoD:**
- [ ] **Findings:** recorded with data; **Outcome:** set.
- [ ] ADR authored + Accepted (or amendment recorded); arch-review if the decision
      changes a module boundary or the inbox contract.
- [ ] 015-03 disposition applied (re-scope/re-open/retire); spec.md SPIDR index +
      `docs/specs/README.md` regenerated.
- [ ] No throwaway prototype code shipped into `skills/` (spike artifacts stay
      scratch; record where they lived).
