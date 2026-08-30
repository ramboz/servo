---
status: DRAFT
dependencies: [adr-0036]
last_verified:
frame_review: true
---

## Slice 030-01 — eval-component-signal

**Goal:** `has_signal` in `/servo:edd-suitability` is additionally satisfied by
at least one **approved, frozen** eval component **installed** in the target's
oracle — established from the two manifests servo already writes
(`install.json`'s `components` registration + the eval's own
`approval_status`/`approved_content_hash`/`hashes` freeze facts) — with a
standing non-blocking advisory when the judged eval is the *only* signal, and
today's tests/ci behavior byte-identical.

**DoR:**
- ☐ [ADR-0036](../../decisions/adr-0036-frozen-evals-satisfy-suitability-signal.md)
  **Accepted** (currently Proposed — this slice does not start before that).
- ☐ Alias map re-confirmed against the tree at implementation time
  (`design-eval` → `design_fidelity`, `content-fidelity` → `content_fidelity`,
  eval-authoring dir == component name) — the closed set ADR-0036 assumes.

**Acceptance Criteria:**

1. **A frozen + approved + registered eval component alone flips the verdict to
   `suitable`, with the advisory.** Fixture: a target whose `install.json` has
   `signals: {tests: false, ci: false, lint: false}` and
   `components: ["design_fidelity"]`, plus `.servo/design-eval/config.json`
   carrying `approval_status: "approved"`, `approved_content_hash`, and a
   non-empty `hashes` map (no live judge, no capture — manifest facts only);
   a spec with ≥1 evaluable AC. `analyze` emits `verdict: "suitable"`, a
   `reasons` entry whose rule code names the eval-signal source (distinct from
   `evaluable_acs_with_signal`, so `--explain` and `reasons` make the
   judged-only case auditable), and **non-blocking** `missing_evidence`
   item(s) on the existing `tests`/`ci` kinds recommending at least one
   deterministic component (the ADR-0033 counterweight). No blocking item
   appears. Tested via the CLI (artifact JSON asserted).
2. **Unfrozen / unapproved / unregistered never counts.** Three negative
   fixtures, same spec, each yielding today's `needs_evidence` with the
   blocking `oracle_signal` item: (a) config present but
   `approval_status: "draft"` (or absent); (b) `approval_status: "approved"`
   but `hashes` missing/empty (never frozen); (c) config fully approved +
   frozen but the component absent from `install.json`'s `components`
   (uninstalled). An unreadable/malformed per-eval config likewise counts as
   no eval signal (fail-closed) — never an env-error exit and never a torn
   artifact. Tested.
3. **tests/ci behavior is unchanged — byte-identical artifacts.** For targets
   where `tests` or `ci` is truthy (with and without an eval component
   present), the emitted artifact is byte-identical to the pre-slice output:
   rule 1 (`evaluable_acs_with_signal`) still fires, `missing_evidence` stays
   as today, `schema_version` stays 1. A regression test pins this by
   comparing against the current `decide()` outputs for the 015-01/02 fixture
   matrix.
4. **The gap's remedy list is truthful.** When no signal of any kind exists,
   the blocking `oracle_signal` item's `detail` now names all three remedies
   (test command, CI workflow, or an approved + frozen eval component); the
   `missing_oracle_signal` reason mirror (015-02 AC3 coherence) still holds.
   Tested.
5. **Docs retire the "empty on suitable" absolute.** SKILL.md's verdict table
   and `decide()`'s docstring say `suitable` may carry **non-blocking advisory
   items only** (blocking items still never appear on `suitable`;
   `unsuitable` still carries an empty list), and SKILL.md documents the
   eval-signal leg + its two manifest sources. `render_human` surfaces the
   advisory on a `suitable` verdict (today it prints advisory info only for
   `needs_evidence`). Surface-tested (`test_skill_surface.py`).

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Fail-closed branches of AC2 mutation-checked (neutering any of the three
      predicates goes red).
- [ ] Host packages rebuilt + drift clean (`build_host_packages.py --check`) —
      `suitability.py` + SKILL.md ship in both host packages.
- [ ] Independent review passed; deviation log + reconciliation sweep produced
      (ADR-0015 amendment note appended at ADR-0036 acceptance per its Status).

**Assumptions:**
- Manifest-only detection is sufficient — no `oracle.sh` parsing, no live
  scoring, no re-hashing of frozen artifacts (staleness stays score-time
  authority via `validate_freeze` → rc 2, which fail-closes the loop
  downstream). Grounded by ADR-0036's code probe; re-confirm on
  implementation.
- The 015-01/02 fixture matrix (stubbed `SERVO_SUITABILITY_ORACLE_PLAN`
  classifier, tempdir targets) extends to the new fixtures without new test
  infrastructure — the eval leg needs only extra JSON files in the tempdir.

**Anti-horizontal-phasing check:** After this slice, a design-led target with
no test suite but an approved, frozen `score_design_fidelity` component gets
`suitable` (plus the counterweight advisory) from
`suitability.py analyze` end to end — and the Compile gate (015-03 /
016-01) admits it — instead of `needs_evidence` demanding tests it does not
need.
