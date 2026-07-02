---
status: DONE
dependencies: [006-05, adr-0022]
last_verified: 2026-07-02
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
- [x] All ACs pass; full test suite green (no regressions).
- [x] Implementer test coverage exercises each AC with at least one fixture.
- [x] Compliance review pass (`jig:independent-review` implementation).
- [x] Craft review pass (`pr-review` rubric).
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Reconciliation review pass.
- [x] `docs/refinement-todo.md` updated if any decisions were deferred.

### Close-out (post-DONE)
- [x] `docs/specs/README.md` regenerated by `workflow.py status-board`.
- [ ] Primer hygiene checked (spec 019 not yet fully closed — leave the
      Draft-specs entry until all five slices are DONE).

**Anti-horizontal-phasing check:** a user (or an unattended loop) driving a
jig-authored spec through its lifecycle can now leave the frozen oracle
installed across every transition instead of uninstalling/reinstalling
around each status bump — directly observable via `gate.py`/`checks.py
--enforce-freeze` no longer refusing after a `status:` edit.

### Deviation log (after reconciliation)

Original ACs preserved above; the implementation deviated/extended as follows:

- **Sort key is the AC `id` string, not a literal `(scope, n)` tuple.** AC3's
  text gives `(scope, n)` as an illustrative example; the planner's actual
  `checks.json` items only carry a combined `id` field (`AC-<scope>-<n>`,
  `oracle_plan.py:157`), not separate `scope`/`n` fields, so `_ac_sort_key`
  sorts by `id` directly. Deterministic and order-independent — all AC3
  requires; it does not require numeric ordering.
- **One existing test inverted, not left untouched.** AC5 says the existing
  `FreezeEnforcementTests` class should stay green, but that class contained
  `test_source_changed_is_stale`, which directly asserted the AC2 behavior
  AC1 requires removing. Renamed/inverted to
  `test_source_changed_no_longer_stale` (asserting the new ADR-0022
  contract: a source-file mutation alone no longer refuses); the other five
  tests in that class are untouched, honoring AC5's intent that
  `approval_status`/`approved_artifacts` checks are unaffected.
- **Whitespace normalization scoped to `statement` only, not `reason`/
  `suggested_review`.** AC3 as written only names `statement`; `residual_
  judgment` items' other free-text fields are not normalized. Documented
  here as a deliberate reading of the AC's literal scope, not an oversight.
- **Fixed during reconciliation, not deferred:** both re-review passes
  independently flagged `_ac_sort_key`'s `item.get("id", "")` as capable of
  raising an unhandled `TypeError` from `sorted()` if a hand-edited
  `checks.json` mixed a non-string `id` with string ones — inconsistent
  with the module's defensive-handling posture elsewhere. Fixed with a
  one-line `str(...)` coercion plus a new regression test
  (`test_non_string_id_does_not_raise`), rather than filed to
  `docs/refinement-todo.md` — it was a one-line fix, not a real design
  question.
- **Doc drift found and fixed during the first review round (not a
  second-round deviation, but worth recording):** `skills/spec-oracle/
  SKILL.md`'s `spec_oracle_stale` reason-code row and `docs/architecture.md`'s
  freeze-and-approval prose both still described the removed raw-source-hash
  trigger; both corrected to describe the current parsed-AC-only freeze.
  The historical, closed `docs/specs/006-spec-oracle/slice-04-freeze-and-
  controls.md` record was **not** rewritten in place (Nygard-style
  immutability for closed records, per ADR-0010) — it gained a dated
  `## Amendments` section pointing to this slice/ADR-0022 as the current
  authority instead.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Project front door unaffected — internal freeze-gate behavior change only. |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board` after this slice transitions. |
| `docs/product-vision.md` | `no-op` | Checked — no scope/behavior drift; this slice implements an already-Accepted ADR. |
| `docs/architecture.md` | `updated` | The freeze-and-approval section (`spec_oracle_stale` description) was stale and is now corrected to match ADR-0022's behavior. |
| Primer surfaces | `no-op` | Checked — none reference the freeze-gate reason-code semantics directly. |
| `docs/inbox.md` | `no-op` | Checked — nothing in it is resolved by this slice. |
| `docs/refinement-todo.md` | `no-op` | Checked — the one edge case reviewers surfaced (non-string `id`) was fixed directly rather than deferred; nothing queued. |
| `docs/memory/**` | `no-op` | No new domain terms; the freeze/ADR-0022 learning is captured in this slice's own record and `docs/decisions/adr-0022-*.md`. |
| `docs/decisions/README.md` / ADR index | `no-op` | ADR-0022 already indexed as Accepted; this slice only implements it. |
| `docs/specs/006-spec-oracle/slice-04-freeze-and-controls.md` | `updated` | Closed-record amendment (ADR-0010 policy) — appended a dated `## Amendments` note; original AC/prose text preserved as historical record. |
| `skills/spec-oracle/SKILL.md` | `updated` | The `spec_oracle_stale` reason-code row was stale; corrected. |
