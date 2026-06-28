---
status: DONE
dependencies: [015-01]
last_verified: 2026-06-27
---

## Slice 015-02 — missing-evidence

**Goal:** When the verdict is `needs_evidence` (EDD-shaped but not ready),
populate the ADR-0015 `missing_evidence` list with **actionable, blocking-flagged
items** keyed to a **closed `kind` taxonomy** — turning "this isn't ready" into a
concrete checklist (the actionable half of EDD onboarding). Each item names the
gap, why it blocks, and how to close it.

> **Boundary with 015-01 / 015-03.** 015-01 emits the verdict + top-level
> `reasons` and may emit an *empty* `missing_evidence`; this slice makes the list
> *load-bearing* for `needs_evidence` and pins its closed `kind` set. Acting on
> the list at a consumer (heartbeat records `skipped` with the reason; Compile
> halts and surfaces it) is 015-03. A `suitable` verdict carries an empty
> `missing_evidence`; an `unsuitable` verdict carries `reasons` (why it's not
> EDD-shaped) but is not expected to carry a *fixable* evidence list.

**DoR:**
- ✅ **015-01 DONE** — the verdict artifact + rule table + the
  `missing_evidence` field exist (reserved, possibly empty). This slice
  enriches the same artifact through the same atomic write path; no new file.
- ✅ Decision: the `kind` taxonomy is **closed** (mirrors ADR-0002's closed
  `reason` posture). v1 set drawn from ADR-0015's examples:
  `tests` / `lint` / `ci` / `oracle_signal` / `reference_set` — extended only by
  a deliberate schema bump, never an open string.
- ✅ Decision: `missing_evidence` items reuse 015-01's deterministic inputs
  (001 signals, 006 classification) — an item is emitted only when a rule can
  point at a concrete absent input, never a vague "needs more."

**Acceptance Criteria:**

1. **Closed `kind` taxonomy.** Each `missing_evidence[*].kind` is one of the
   closed v1 set (`tests` / `lint` / `ci` / `oracle_signal` / `reference_set`);
   an input that maps to no known kind is **not** emitted as an open-string kind
   (fail-closed on taxonomy, like the verdict enum). *Test:*
   `MissingEvidenceKindTaxonomyTests`.

2. **Actionable, blocking-flagged items.** Every item carries `{kind, detail,
   blocking}`: `detail` is a human-readable, spec-specific next step (e.g. "no
   test signal detected in install.json; add a test command so the oracle has a
   deterministic gate"), and `blocking: true` marks gaps that *cause* the
   `needs_evidence` verdict. *Test:* `MissingEvidenceItemShapeTests`.

3. **Verdict ⇔ list coherence.** A `needs_evidence` verdict has ≥1
   `blocking: true` item (the gap that blocked it); a `suitable` verdict has an
   empty `missing_evidence`; the blocking items' `kind`s are reflected in the
   top-level `reasons`. The list and the verdict can never disagree. *Test:*
   `VerdictEvidenceCoherenceTests`.

4. **Deterministic + re-runnable.** The same inputs yield the same
   `missing_evidence` (stable order: taxonomy order, then `detail`). After the
   gap is closed (e.g. a test command added) and `analyze` re-runs, the
   corresponding item disappears and the verdict can flip to `suitable` — the
   re-analysis loop ADR-0015 names. *Test:* `MissingEvidenceRerunTests`.

**DoD:**
- [x] All ACs pass; `test_suitability.py` extended (40 tests; full suite green —
      1073 before the in-pass coherence-test strengthening); `ruff check .` clean
      (pinned 0.15.17).
- [x] Reviewed by the jig compliance + craft passes (recorded under `reviews/`;
      compliance ran as an independent subagent (pass), craft is a maintainer
      self-review (pass) — provenance noted in the craft file).
- [x] Deviation log produced under this slice heading.
- [x] `docs/specs/README.md` regenerated.

### Close-out (post-DONE)
- [x] Carry the closed `kind` taxonomy forward in the board Notes so 015-03's
      heartbeat reason mapping stays in sync.

### Deviation log (after reconciliation)

Original ACs preserved above; the implementation deviated/extended as follows:

- **`oracle_signal` umbrella + advisory `tests`/`ci` sub-items (AC1/AC2).** For
  the missing-signal case the analyzer emits a single *blocking* `oracle_signal`
  item plus *advisory* (`blocking: false`) `tests` and `ci` how-to items, rather
  than marking each specific signal blocking. Rationale: only **one** compilable
  signal is required, so the abstract `oracle_signal` is the honest blocking gap
  and the specific items are the concrete fix. All five taxonomy kinds are
  exercised in v1 (`lint` advisory; `reference_set` blocking when there are no
  evaluable ACs).
- **Blocking kinds reflected via appended `reasons` entries (AC3).** Coherence
  is made structural: `decide()` appends a `{"code": "missing_<kind>",
  "message": detail}` reason per blocking item alongside the fired-rule reason.
  Additive to 015-01's single-reason shape; consumers branching on the closed
  `verdict` enum are unaffected.
- **`unsuitable` carries an empty list.** Per the slice boundary, the list is
  load-bearing only for `needs_evidence`; both `suitable` and `unsuitable` carry
  an empty `missing_evidence`. An `unsuitable` spec's gap (all-residual ACs) is
  not closable by acquiring evidence, so emitting "add tests" would mislead.
- **`manifest_malformed` explicit test added.** Closes the test gap 015-01's
  deviation log deferred to this slice (a present-but-unparseable
  `install.json` ⇒ exit 2, no artifact).

### Reconciliation sweep

Drift-prone surfaces checked (`updated` / `no-op` / `deferred`):

- **015-01 verdict artifact contract** — `updated`: `missing_evidence` is now
  populated for `needs_evidence` (was reserved-empty); `needs_evidence` reasons
  gain appended `missing_*` entries. Additive; the `suitable`-path reasons and
  the closed `verdict` enum are unchanged (015-01's 24 tests still pass).
- **ADR-0015 `missing_evidence` shape** — `no-op`: `{kind, detail, blocking}`
  implemented faithfully; the `kind` set is drawn from the ADR's examples and
  pinned closed.
- **001 `install.json` `signals` schema** — `no-op`: still a read-only consumer;
  the `lint` key (already echoed in `inputs`) now also drives an advisory item.
- **015-03 boundary** — `no-op`: no caller wired. Acting on the list (heartbeat
  records `skipped`; Compile halts) stays 015-03.
- **`docs/specs/README.md` board** — `deferred`: regenerated at DONE close-out.

**Architecture impact:** none — extends an existing standalone skill helper; no
module boundary or public contract changed (implements ADR-0015's
`missing_evidence`), so no ADR.
