---
status: DRAFT
dependencies: [006, 015]
last_verified:
frame_review: true
---

## Slice 019-03 — behavioral-ac-recall

**Goal:** Improve the shared AC classifier's recall for behavioral /
negative-behavior phrasing ("the lint *fails* when…", "is *excluded*…",
"does *NOT* compile…") so those ACs land as `command`-checkable instead of
falling through to `residual_judgment`, and make the already-shared
AC-analysis pipeline's single-source-of-truth property an explicit,
regression-guarded contract rather than an accidental byproduct of a
subprocess call.

**DoR:**
- ✅ **Corrects the spec's original framing (grounded by direct code
  read).** The spec's Goal #3 ("one AC-analysis pass feeds both… today they
  parse separately") is **already false** as written: `suitability.py::
  _classify` (`skills/edd-suitability/suitability.py:311-348`) does **not**
  run its own parser — it subprocess-delegates to `oracle_plan.py classify`
  (the same `extract_acs` + `_classify_family` pipeline `oracle_plan.py`
  itself uses to build a spec-oracle plan) and consumes the returned
  `checks` / `residual_judgment` arrays directly
  (`suitability.py::analyze`, lines 355-367). There is **one** AC-parsing
  implementation today, not two. This slice's real scope is therefore (a)
  recall, not re-plumbing, and (b) making that already-shared pipeline an
  explicit, tested contract so a future change can't silently fork it again.
- ✅ **Bug 003 DONE** (commit `f272502`) — the preamble-tolerance /
  non-silent-empty-section half of this spec's goal is already shipped in
  `oracle_plan.py::extract_acs` (bold-label-before-first-item tolerance +
  `_warn_if_empty_ac_section`). This slice is additive on top, not a
  re-fix.
- ✅ **Classifier heuristic grounded** —
  `oracle_plan.py::_classify_family` (lines 274-354) is an ordered
  keyword/regex cascade (`generated_artifact_command` →
  `runtime_reference_scan` → `markdown_links` → `json_contract` →
  `archive_inventory` → `file_presence` → `command` → `text_invariant` →
  `residual_judgment` catch-all). Negative phrasing is *partially*
  recognized today: `file_presence` matches `"does not exist"` (line
  ~329) and `text_invariant` matches `"does not contain"`/`"doesn't
  contain"` (line ~348) — but no family recognizes a negative *behavioral*
  verb ("fails when", "is excluded", "does NOT run/compile/pass", "never
  …").
- ✅ **No existing test coverage for behavioral/negative-behavior ACs** in
  either `test_oracle_plan.py` or `test_suitability.py` — confirmed by
  direct read; this is a genuine recall gap, not a regression.

## Assumptions

- **A1 — the added keyword families won't meaningfully increase false
  positives.** Widening `_classify_family`'s recall for negative-behavior
  phrasing risks misclassifying a `residual_judgment`-appropriate AC (one
  that genuinely needs human judgment) as falsely `command`-checkable. This
  assumes the new keyword families are narrow enough (anchored on
  "fails when" / "is excluded" / "does NOT <verb>" / "never" rather than
  bare "not") to avoid that. *To verify:* run the widened classifier over
  every existing dogfood/fixture spec in this repo's own `docs/specs/` tree
  and diff the before/after classification — any AC that flips families
  gets manually eyeballed before the slice is called done.

**Acceptance Criteria:**

1. **Negative-behavior family recognized.** `_classify_family` gains
   recall for phrasing like "X **fails** when Y", "X **is excluded**
   from…", "X **does NOT** run/compile/pass/build", "X is **never**…" —
   classified as `command`-checkable (the check still needs a concrete
   command/assertion to be written later; this AC is about *classification*
   recall, not authoring new check primitives). Existing families keep
   their current precedence order (no reclassification of already-matching
   ACs). *Test:* `BehavioralNegativeACRecallTests` — one fixture per
   phrasing above, asserting `checks` (not `residual_judgment`).
2. **`suitability.py`'s evaluable count moves with the same fix.** Because
   `suitability.py` delegates to `oracle_plan.py classify`, the same
   behavioral ACs that reclassify from `residual_judgment` to `checks` in
   AC1 automatically increase `n_evaluable` in the suitability verdict —
   proved with an integration test that runs the *real* classifier (not a
   stub) over a fixture spec and asserts the verdict's evidence counts, not
   just the plan's. *Test:* `SharedPipelineSuitabilityIntegrationTests`
   (extends the existing `RealClassifierIntegrationTests` pattern in
   `test_suitability.py`).
3. **Single-pipeline contract is regression-guarded.** A new test asserts
   `suitability.py::_classify` invokes `oracle_plan.py`'s `classify`
   entrypoint (not a private/duplicate parser) — so a future edit that
   accidentally forks the two back apart fails CI immediately, rather than
   silently reintroducing the dogfood's original complaint. *Test:*
   `NoDuplicateACParserTests`.
4. **Dogfood's reported behavioral ACs classify without hand promotion.**
   The cwv-workbench dogfood's own behavioral/negative-phrasing ACs (as
   characterized in this spec's "Why this spec" section and Bug 003's
   record) parse as `checks`, not `residual_judgment`, with no manual
   override needed. *Test:* a fixture reconstructing the dogfood's reported
   phrasing shape (not a copy of proprietary content — a servo-authored
   fixture matching the *pattern*).
5. **Shared AC grammar is documented.** Bug 003's `## Learning` explicitly
   flags "a shared, documented AC grammar" as the follow-up this slice
   closes. Add a short grammar reference (header shape, tolerated
   preamble, negative-behavior keyword families, residual-judgment
   fallback) to `skills/spec-oracle/SKILL.md` (or a sibling doc it links),
   cross-referenced from `skills/edd-suitability/SKILL.md` since both
   consume it. *Test:* `test_skill_surface.py` assertion that the grammar
   section exists and both skills reference the same source.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one fixture.
- [ ] Compliance review pass.
- [ ] Craft review pass.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review pass.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred.
- [ ] Bug 003's record cross-linked to this slice as the "deeper
      unification" follow-through it named.

### Close-out (post-DONE)
- [ ] `docs/specs/README.md` regenerated by `workflow.py status-board`.

**Anti-horizontal-phasing check:** a spec author writing a behavioral AC
("the lint fails when X") gets it correctly counted as evaluable evidence in
both the suitability verdict and the spec-oracle plan on the very first
`edd-suitability`/`spec-oracle` run — no more silent `residual_judgment`
misclassification requiring a manual promotion round-trip.

### Deviation log (after reconciliation)

_Filled in during reconciliation._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | _TBD at reconciliation._ |
| `docs/specs/README.md` | `updated` | _TBD._ |
| `docs/product-vision.md` | `no-op` | _TBD._ |
| `docs/architecture.md` | `no-op` | _TBD._ |
| Primer surfaces | `no-op` | _TBD._ |
| `docs/inbox.md` | `no-op` | _TBD._ |
| `docs/refinement-todo.md` | `no-op` | _TBD._ |
| `docs/memory/**` | `no-op` | _TBD — Bug 003 learning cross-link._ |
| `docs/decisions/README.md` / ADR index | `no-op` | _TBD._ |
