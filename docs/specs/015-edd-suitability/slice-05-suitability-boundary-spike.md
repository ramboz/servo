---
status: DONE
kind: spike
dependencies: [015-01, 015-02, 011-01, adr-0015]
last_verified: 2026-06-29
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

**Findings:** _(2026-06-28; scratch artifacts under
`…/scratchpad/spike-015-05/`, nothing shipped to `skills/`)_

- **Survey (real findings).** `heartbeat.py discover` on `ramboz/servo` →
  **36 findings**: 16 CI, 20 commit, **0 issue** (no open issues). Only **3 are
  actionable** (`actionable AND open` — all CI-default-branch failures); the 20
  commits are `commit_context_only` (non-actionable), 13 CI are non-default. The
  **gate only ever sees the 3 actionable candidates.**
- **Recoverable-spec fraction = 0/3 among the candidates that matter.** Every
  actionable finding is a CI failure whose evidence is
  `{run_url, workflow, branch, event}` and whose title is "CI failure: CI on
  main" — **no spec, no `docs/specs/` path, no spec-id token.** (A loose token
  scan matched 17/36 overall, but *entirely* in non-actionable **commit messages**
  — servo's own spec-referencing commits, a spec-driven-repo artifact that does
  not generalize and gives no analyzable `spec.md`.) **Bridge (c) finding→spec
  linkage is unavailable in practice.**
- **Bridge (a) ephemeral-spec synthesis → degenerate.** Synthesizing a `spec.md`
  from each finding's title/detail/evidence and running the *real*
  `suitability.py analyze` against a target with full **tests+ci+lint** signals
  yielded **`needs_evidence` for 36/36** findings (3/3 actionable). Cause: a
  finding carries no ACs → `n_evaluable == 0` → `signal_without_evaluable_acs`.
  The gate would skip **100%** of findings regardless of signals. **An off
  switch, not a gate. Rejected.**
- **Bridge (b) finding-shaped variant** would require a **new analyzer over
  finding features** (source type, evidence presence, target signals) — *not* the
  spec-centric 015-01/02 verdict this spec ships. So it is not "consume the
  verdict at the heartbeat"; it is a different artifact, and its value must be
  weighed against the next point.
- **Marginal value over the existing oracle preflight ≈ nil (step 3).** The
  heartbeat **already** refuses dispatch without a passing-capable oracle:
  `run_dispatch` runs a `gate.py <target>` preflight (refuse-without-oracle,
  [`heartbeat.py:1842`](../../../skills/heartbeat/heartbeat.py)) **and**
  re-verifies the provisioned worktree with `gate.py <worktree>`
  ([`heartbeat.py:1758`](../../../skills/heartbeat/heartbeat.py)); a loop that
  can't satisfy the oracle is recorded `tried`, never falsely `passed`. The
  "vacuous green oracle / false pass" risk ADR-0015 cites is a **spec-level** risk
  (all-residual ACs + a vacuous oracle) that manifests at **Compile**, where a
  real spec with ACs exists — not at the spec-less heartbeat boundary, which is
  already oracle-anchored.

**Conclusion.** EDD suitability is a **Compile-phase gate, not a heartbeat gate.**
Bridges (a) and (c) fail on data; (b) is a different (unbuilt) analyzer whose
marginal value over `gate.py` is unshown. The heartbeat keeps `gate.py` as its
evaluability gate. 015-03 is re-scoped to the **Compile precondition only**
(re-attached to spec 016, which will own the Compile entry); the heartbeat
per-finding gate (original AC1–4, AC6) is **retired**. A finding-shaped
evaluability check, if ever wanted, is future work for **018** and must first
demonstrate value over `gate.py`.

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

**Outcome:** `ADR-0018 created (Accepted 2026-06-28); spec 015-03 re-scoped to the
Compile precondition only (heartbeat gate retired), deferred pending spec 016`.

**DoD:**
- [x] **Findings:** recorded with data; **Outcome:** set.
- [x] ADR authored + Accepted ([ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md)).
      No arch-review needed — the decision *removes* a planned inbox-contract
      change rather than introducing one (011-02's `skipped` invariant is
      preserved); no module boundary changes.
- [x] 015-03 disposition applied (re-scoped to Compile-only, heartbeat ACs
      retired); spec.md SPIDR index updated + `docs/specs/README.md` regenerated.
- [x] No throwaway prototype code shipped into `skills/` — survey + synthesis
      prototypes lived under the session scratchpad (`…/scratchpad/spike-015-05/`)
      and are not in the repo.

### Deviation log (after reconciliation)

A spike ships no production code; the "deviations" are from the investigation
plan above:

- **One repo surveyed, not "≥2".** The plan called for ≥2 real repos. Only
  `ramboz/servo` (36 findings) was surveyed because the result was **decisive** —
  ephemeral-spec synthesis degenerated to `needs_evidence` for 36/36, a structural
  consequence of "a finding has no ACs," not a sampling artifact. A second repo
  could not flip a 100%→0% result, so the extra survey was not spent. (servo had
  0 open issues, so the issue source went unsampled; an issue finding is *more*
  spec-shaped than a CI finding, but still carries no ACs, so the conclusion
  holds.)
- **Bridge (b) adjudicated by design-analysis, not a full prototype.** Building a
  finding-shaped analyzer would have meant writing the very artifact the spike was
  trying to decide *whether* to build. It was instead reasoned to a clear
  disposition (a different analyzer; value over `gate.py` unproven → defer to
  018), which is sufficient for the decision and avoids speculative code.
- **No second consumer found for the precondition (AC5) either** — surfaced that
  015-03's *Compile* half is also unbuilt-consumer-blocked (016), so the re-scoped
  slice stays DEFERRED rather than re-opened to DRAFT.

### Reconciliation sweep

Drift-prone surfaces touched by the spike's disposition (`created` / `updated` /
`no-op`):

- **ADR-0018** — `created` (Accepted): the Compile-only decision + its evidence.
- **ADR-0015** — `updated`: `## Amendments` gains a "resolved by ADR-0018" entry;
  the verdict contract body is unchanged (`no-op` there).
- **docs/decisions/README.md** — `updated`: ADR-0018 index row + next-free-number
  bumped to 0019.
- **015-03 slice** — `updated`: re-scoped to the Compile precondition (heartbeat
  ACs retired), frontmatter deps repointed (016 / adr-0018), `arch_review` /
  `frame_review` flags dropped (the contentious assumptions are resolved); stays
  DEFERRED pending 016.
- **015-02 board Note** — `updated`: corrected the stale "maps to the heartbeat
  `skipped`" forward-reference to "Consumed at the Compile gate (ADR-0018)."
- **spec.md SPIDR section** — `updated`: correction note + 015-03/05 rows.
- **011-02 `skipped` contract** — `no-op`: **preserved** (the planned automated
  setter is dropped), so no amendment is owed.
- **Project memory** — `updated`: the deferral memory + index reflect the
  Compile-only resolution.
