---
status: DRAFT
dependencies: [006, adr-0022]
last_verified:
---

## Slice 019-01 — freeze-parsed-acs

**Goal:** `checks.py --enforce-freeze` compares the current parsed AC set
against the approved one (via `approved_content_hash` over `checks.json`) and
no longer trips `spec_oracle_stale` on a raw byte change to the source spec
file — so a living-document consumer (jig rewrites the slice's `status:`
frontmatter on every lifecycle transition) can stay frozen across transitions.
Implements [ADR-0022](../../decisions/adr-0022-freeze-against-parsed-acs.md).

**DoR:**
- ✅ **ADR-0022 Accepted** (2026-07-02) — freeze against the parsed AC set,
  drop the raw-source-file hash check, canonicalize the AC set so trivial
  reformatting does not false-stale.
- ✅ **006-04 DONE** — `checks.py::freeze_violation` and
  `plan_content_hash` already exist; grounded by direct code read
  (`skills/spec-oracle/checks.py:838-885`):
  - The **raw-file check** lives at `freeze_violation` lines 855-866: it
    reads `plan["source_spec_path"]` / `plan["source_hash"]`, re-hashes the
    live source file, and returns `spec_oracle_stale` on any byte diff. This
    is the check ADR-0022 says to drop.
  - The **parsed-AC check** already exists separately at lines 878-883:
    `approved_content_hash` (set by `oracle_overlay.py::approve`, hashing
    only `{"checks": ..., "residual_judgment": ...}` via
    `plan_content_hash`, `checks.py:819-835`) is compared against a
    freshly-recomputed `plan_content_hash(plan)`. This is the check ADR-0022
    says to *keep* as the sole staleness signal.
  - `plan_content_hash` today does `json.dumps(..., sort_keys=True,
    separators=(",", ":"))` over the `checks` / `residual_judgment` **lists
    in file order** — `sort_keys` only orders each object's own keys, not the
    list elements, so a pure item-reorder (e.g. re-numbering ACs after an
    edit elsewhere in the spec) still changes the hash. ADR-0022 asks for
    order-independent + whitespace-normalized canonicalization.
- ✅ **`oracle_overlay.py::approve`'s own source-hash check** (lines
  ~259-269, a *different* call site — the one-time approval gate, not the
  per-score freeze gate) is **out of scope**: it is not the reported pain
  (that was `--enforce-freeze` tripping on *every score*, not on approval),
  and re-approval after a genuine spec edit re-planning is still the correct
  flow.

**Acceptance Criteria:**

1. **Raw-file hash no longer gates freeze.** `checks.py --enforce-freeze`
   removes the `source_spec_path`/`source_hash` re-hash-and-compare block
   from `freeze_violation` (today's lines 855-866). A `status:` frontmatter
   edit or an appended deviation-log section on the source spec — which
   changes its raw bytes but not its ACs — no longer trips
   `spec_oracle_stale`. *Test:* `FreezeSurvivesLivingDocMutationTests`.
2. **An AC edit still trips staleness.** Editing the *text* of an approved
   AC (or adding/removing one) still trips `spec_oracle_plan_modified`
   (unchanged behavior — the existing `approved_content_hash` compare).
   *Test:* `FreezeStillCatchesACEditTests` (regression guard on existing
   006-04 behavior).
3. **Canonical AC-set hash is order-independent and whitespace-normalized.**
   `plan_content_hash` sorts the `checks` + `residual_judgment` lists by a
   stable key (e.g. `(scope, n)`) before hashing, and normalizes each
   statement's whitespace (collapse runs of whitespace, strip leading/
   trailing) before hashing — so re-ordering ACs (without changing their
   content) or a pure whitespace reformat of an AC statement does **not**
   change the hash, while an actual content edit still does. *Test:*
   `PlanContentHashCanonicalizationTests` (reordered-ACs → same hash;
   whitespace-reformatted statement → same hash; content-changed statement →
   different hash).
4. **`approve` still records a hash over the new canonical form.**
   `oracle_overlay.py::approve` computes `approved_content_hash` via the
   now-canonicalized `plan_content_hash`, so a freshly-approved plan is
   internally consistent with the freeze gate (no false-positive
   `spec_oracle_plan_modified` immediately after approval). *Test:*
   `ApproveThenFreezeRoundTripTests`.
5. **No regression on the existing 006-04 freeze suite.** `approval_status`
   (unapproved/stale-marker) and `approved_artifacts` (byte-identical
   `checks.py` / `oracle.sh.fragment`) checks in `freeze_violation` are
   untouched — this slice only removes the raw-source-hash block and
   canonicalizes the AC-content hash. *Test:* full
   `skills/spec-oracle/test_checks.py::FreezeEnforcementTests` green.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Implementer test coverage exercises each AC with at least one fixture.
- [ ] Compliance review pass (`jig:independent-review` implementation).
- [ ] Craft review pass (`pr-review` rubric).
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation sweep produced under this slice heading.
- [ ] Reconciliation review pass.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred.

### Close-out (post-DONE)
- [ ] `docs/specs/README.md` regenerated by `workflow.py status-board`.
- [ ] Primer hygiene checked (spec 019 not yet fully closed — leave the
      Draft-specs entry until all five slices are DONE).

**Anti-horizontal-phasing check:** a user (or an unattended loop) driving a
jig-authored spec through its lifecycle can now leave the frozen oracle
installed across every transition instead of uninstalling/reinstalling
around each status bump — directly observable via `gate.py`/`checks.py
--enforce-freeze` no longer refusing after a `status:` edit.

### Deviation log (after reconciliation)

_Filled in during reconciliation._

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | _TBD at reconciliation._ |
| `docs/specs/README.md` | `updated` | _TBD — regenerated by `workflow.py status-board`._ |
| `docs/product-vision.md` | `no-op` | _TBD._ |
| `docs/architecture.md` | `no-op` | _TBD._ |
| Primer surfaces | `no-op` | _TBD._ |
| `docs/inbox.md` | `no-op` | _TBD._ |
| `docs/refinement-todo.md` | `no-op` | _TBD._ |
| `docs/memory/**` | `no-op` | _TBD._ |
| `docs/decisions/README.md` / ADR index | `no-op` | _TBD._ |
