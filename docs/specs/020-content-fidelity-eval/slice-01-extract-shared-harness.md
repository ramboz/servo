---
status: DONE
dependencies: [adr-0024]
arch_review: true
frame_review: true
last_verified: 2026-07-03
---

## Slice 020-01 — extract-shared-harness

**Goal:** Move the already-modality-agnostic freeze/hash/aggregate/ledger and
oracle.sh-install-splice primitives out of `skills/design-eval/score.py` and
`design_eval.py` into a new `skills/_common/fidelity_eval.py`, with **no
change to design-eval's public contract or runtime behavior** — its existing
test suite is the regression backstop.

**DoR:**
- ✅ **ADR-0024 records the boundary** (what moves vs. what stays forked) —
  see its Decision section.
- ✅ **Not a formal `dependencies:` entry, but real: this slice extracts code
  from [spec 012](../012-design-eval/spec.md)'s already-built `design-eval`
  runtime**, which exists in-tree today regardless of spec 012's own
  frontmatter lifecycle state (`DRAFT`, per its own "honest status note" —
  012 predates this project's per-slice DONE-gate machinery and uses the
  older embedded-`## Slice` format). This slice's dependency is on the
  *code being present and correct*, not on spec 012 reaching `DONE` through
  a lifecycle it was never run through — so `012` is intentionally omitted
  from the frontmatter `dependencies:` list (which would otherwise permanently
  block this slice's own `DONE` transition on an unrelated, unresolvable gate).
- ✅ **Grounded by direct code read** (`skills/design-eval/score.py`,
  `design_eval.py`, 2026-07-03): `EnvError`/`StaleError` (score.py:43-48),
  `sha256_text`/`sha256_file` (55-60), `definition_hash` (63-86),
  `artifact_hashes` (89-98), `validate_freeze` (101-121),
  `aggregate_lower_bound` (128-139), `_extract_json` (290-294),
  `_post_with_retry` (216-236), `_ledger` (344-360) carry zero image-specific
  logic. `design_eval.py`'s `init`/`freeze`/`install`/`uninstall`/
  `_register_manifest`/`_deregister_manifest` (66-184) are already
  parameterized by the `COMPONENT` module constant, not hardcoded to vision.
- ✅ **Deployment-topology fact, verified by direct read (load-bearing for
  this slice's design — see Assumption A1 below):** `design-eval`'s runtime
  is **copied**, not referenced. `design_eval.py::init()` (66-79)
  `shutil.copyfile`s `score.py` and `capture.mjs` from the skill source into
  `<target>/.servo/design-eval/`, and the installed `oracle.sh` fragment
  (`_FRAGMENT`, design_eval.py:35-44) invokes
  `python3 .servo/design-eval/score.py "$PWD"`. **Correction (caught by
  frame-critique, 2026-07-03): the `"$PWD"` argument is a red herring for
  import resolution** — `score.py::main()` (363-368) resolves
  `base_dir = Path(__file__).resolve().parent` and explicitly documents that
  the argument "is accepted for the oracle.sh contract and intentionally
  ignored." The load-bearing fact is narrower and purely structural: `score.py`
  is copied to an arbitrary target directory and must resolve its sibling
  module relative to `__file__`, independent of CWD or how it was invoked.
  This is a different topology from spec-oracle's `checks.py`
  ([ADR-0023](../../decisions/adr-0023-colocate-durable-spec-oracle-artifacts.md)
  AC3, `oracle_overlay.py:97,132-136`), which is **referenced by absolute
  plugin-install path** and never copied by default. Whatever import
  mechanism this slice picks for the extracted module must survive `score.py`
  running from either its source location (`skills/design-eval/`) or an
  arbitrary target's `.servo/design-eval/` after being copied there alone.
- ✅ **Known, accepted, pre-existing limitation carried forward (not
  introduced by this slice): no re-sync for a copied runtime.** `score.py`/
  `capture.mjs` already have zero staleness detection once copied into a
  target — a later fix in the skill source never reaches an
  already-initialized target until it re-runs `install`. `fidelity_eval.py`
  inherits this same property; this slice does not add a version/hash check
  (out of scope — see ADR-0024's Open questions and
  `docs/refinement-todo.md`). Explicitly not a regression: it is the same
  risk profile design-eval already carries today, now shared by a second
  consumer.

**Acceptance Criteria:**

1. **Shared module exists and carries the modality-agnostic contract.**
   `skills/_common/fidelity_eval.py` (a flat module — no package `__init__`,
   so it copies as a single file exactly like `capture.mjs` does today)
   exports `EnvError`, `StaleError`, `sha256_text`, `sha256_file`,
   `definition_hash`, `artifact_hashes`, `validate_freeze`,
   `aggregate_lower_bound`, `_extract_json`, `_post_with_retry`, and a ledger
   writer — with the same behavior as today's `score.py` versions.
   `definition_hash`/`artifact_hashes` take the case-array key (e.g.
   `"screens"`) and the per-case file-bearing field names as parameters
   instead of hardcoding design-eval's shape, so a second caller with a
   differently-named case array (e.g. content-fidelity's `"cases"`) can reuse
   them unmodified. *Test:*
   `test_fidelity_eval.py` (new, under `skills/_common/`), covering each
   exported function directly (freeze happy-path, stale on each frozen field,
   env_error on missing artifact, lower-bound aggregation on 1/2/n samples).
2. **`score.py` resolves the shared module from either deployment location.**
   A two-candidate probe — `../_common/fidelity_eval.py` relative to
   `score.py`'s own directory (the source layout, `skills/design-eval/` next
   to `skills/_common/`), falling back to a same-directory
   `fidelity_eval.py` (the copied-target layout, both files copied flat into
   `.servo/design-eval/`) — resolves in both cases with no
   `ModuleNotFoundError`. *Test:* `ImportResolutionTests` — one test runs
   `score.py` **as a direct subprocess** (`python3 score.py ...`, mirroring
   the actual `oracle.sh` fragment's invocation contract, not an
   `importlib.spec_from_file_location`/`exec_module` load) from a temp dir
   standing in for the source layout (a `_common/fidelity_eval.py` sibling
   one level up), a second from a temp dir standing in for the copied layout
   (`fidelity_eval.py` flat alongside `score.py`), both asserting the module
   imports and `main()` still executes against the existing fake-scores
   fixture.
3. **`design_eval.py::init()` copies the shared module alongside the
   existing runtime files.** The existing copy loop (today: `("score.py",
   "capture.mjs")`, sourced from `SKILL_DIR`) copies `fidelity_eval.py` too,
   sourced from `skills/_common/` — extending, not restructuring, the
   existing loop. *Test:* `InitCopiesSharedModuleTests` — after `init()`,
   `<target>/.servo/design-eval/fidelity_eval.py` exists and is
   byte-identical to `skills/_common/fidelity_eval.py`.
4. **design-eval's public contract is unchanged.** `config.json` schema,
   the `score_design_fidelity` component name, the `oracle.sh` SEED-splice
   shape, the CLI subcommands (`init`/`capture-refs`/`freeze`/`install`/
   `uninstall`), and every existing assertion in
   `skills/design-eval/test_design_eval.py` still pass, unmodified in intent
   (test bodies may be touched only to point at the relocated functions'
   import path, never to change what they assert). *Test:* full existing
   `test_design_eval.py` suite green.
5. **Oracle-splice helpers are reusable by name, not hardcoded.** The
   SEED-block install/uninstall/`COMPONENTS`-entry/`install.json`-registration
   logic (`design_eval.py:111-167`) moves to the shared module as functions
   parameterized by component name and fragment body, so a second caller
   (content-fidelity, slice 020-02) can install its own differently-named
   component without copy-pasting the splice regex logic. *Test:*
   `SpliceHelperReuseTests` — invoke the shared install helper with a second,
   distinct component name against a throwaway `oracle.sh` fixture and assert
   both components coexist correctly (mirrors the existing multi-component
   `COMPONENTS=(...)` append case already exercised in
   `test_design_eval.py`).

**DoD:**
- [x] All ACs pass; full test suite green (no regressions) — both
      `skills/design-eval/test_design_eval.py` and the new
      `skills/_common/test_fidelity_eval.py` (52 tests; full repo suite 1289
      passed, 0 failed).
- [x] Implementer test coverage exercises each AC with at least one fixture.
- [x] Compliance review pass (`jig:independent-review` implementation) — pass.
- [x] Craft review pass (`pr-review` rubric) — pass (round 2, after a fix).
- [x] Arch review pass (`arch_review: true` — this slice changes a module
      boundary: a new cross-skill shared module) — pass (round 2, after a
      blocker fix).
- [x] Frame-critique pass recorded (`frame_review: true` — see Assumption A1;
      this slice also spawns an ADR) — pass (round 2).
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Reconciliation review pass — pass.
- [x] `docs/refinement-todo.md` updated if any decisions were deferred.

## Assumptions

- **A1 — the two-candidate import probe is the right mechanism (untested
  until implemented).** Neither of servo's two existing precedents transfers
  cleanly: `checks.py` is referenced by absolute plugin-install path and
  never copied (ADR-0023 AC3) — inapplicable, since design-eval's `score.py`
  IS copied and must keep working standalone in an arbitrary target with no
  servo plugin install reachable at score time. jig's own `_common` idiom
  (`sys.path.insert(parent.parent); from _common import x`) assumes the
  importing file never moves from its install location — also inapplicable,
  since `score.py`'s whole point is to be copied elsewhere. The two-candidate
  probe (try the source-layout sibling path, else the copied-flat sibling
  path) is a new pattern for this codebase; the implementer should validate
  it against both real deployment shapes (AC2's two fixtures) before treating
  it as settled, and flag in the deviation log if a simpler mechanism (e.g. a
  single `try/except ImportError` instead of an existence probe) is
  preferable in practice.

**Anti-horizontal-phasing check:** this is the one slice in this spec where
the "vertical value" is a regression guarantee, not a new user-facing
capability — design-eval keeps working exactly as before, for its existing
users, while now sharing its harness with a second skill built in 020-02.
It is justified as a standalone slice (rather than folded into 020-02)
because AC4's full-existing-suite-green gate is the safety net the second
skill is built on top of, and mixing "prove nothing broke" with "build
something new" in one slice would hide a regression in the noise of new
code. 020-02 is the slice where an end user gets new observable value
(`/servo:content-fidelity`).

### Deviation log (after reconciliation)

Original ACs preserved above; the implementation deviated/extended as follows:

1. **`definition_hash`/`validate_freeze` gained an `extra_fields: tuple = ()`
   parameter not explicitly named in AC1's text.** AC1 called for
   generalizing the case-array shape (`cases_key`/`case_file_fields`) but the
   first implementation pass missed that `definition_hash` also pinned a
   top-level `"viewport"` field hardcoded in the shared module — a
   design-eval-specific leak both the arch-review and craft-review passes
   independently caught (round 1, both `needs-changes`/`[blocker]`). Fixed by
   adding a generic `extra_fields` parameter (default `()`, purely additive);
   `skills/design-eval/score.py` now passes `_EXTRA_HASH_FIELDS =
   ("viewport",)` explicitly. A golden-hash regression test
   (`test_definition_hash_unchanged_for_pre_existing_frozen_config`, a literal
   pinned sha256) proves this preserves byte-identical hashes for
   pre-existing frozen `config.json` files — no re-freeze required for
   existing design-eval installs.
2. **`design_eval.py` reuses `_score._fe` instead of independently loading
   `fidelity_eval.py` a second time.** Not required by any AC, but flagged as
   a nit by both round-1 reviews (the module was being `exec_module`-loaded
   twice per process, producing two independent module objects for a
   stateless module). Fixed as a one-line, well-commented reuse of the
   module `score.py`'s own two-candidate probe already loaded — confirmed
   safe by arch-review round 2 (`exec_module` is synchronous, so `_score` is
   fully initialized before `design_eval.py` reads its `_fe` attribute).
3. **AC2's `ImportResolutionTests` invoke `score.py` as a direct subprocess**
   (matching the real `oracle.sh` invocation contract), not via
   `importlib.spec_from_file_location` — this was tightened during
   pre-implementation frame-critique (round 2) as a test-fidelity
   improvement, not a scope change.
4. **The two-candidate import probe (Assumption A1) needed no fallback.** It
   worked as designed on the first attempt, validated end-to-end by real
   subprocess tests against both deployment layouts; no simpler
   `try/except ImportError` mechanism was substituted.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Project front door unaffected — internal shared-module refactor only, no user-facing change to any skill's install/usage instructions. |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board`. |
| `docs/product-vision.md` | `no-op` | Checked — no scope/behavior drift; this slice is an internal refactor fulfilling an already-Accepted ADR. |
| `docs/architecture.md` | `updated` | Added a "Shared frozen-eval harness (`skills/_common/`)" subsection documenting the new module, its parameterization, and the copy-based deployment note — the gap three independent review passes (compliance, craft, arch) flagged as claimed-but-not-yet-done. |
| Primer surfaces | `no-op` | Checked — no `CLAUDE.md`/`AGENTS.md` exist in this repo (servo follows jig's spec-tracking conventions without a full jig scaffold-init; see memory). |
| `docs/inbox.md` | `no-op` | Checked — no entries reference design-eval, content-fidelity, or the shared-module extraction. |
| `docs/refinement-todo.md` | `updated` | Two entries added during framing (before implementation began): the copied-shared-module staleness gap (ADR-0024 Open Questions) and content-fidelity's cross-run generator-determinism gap (surfaced during slice 020-02's frame-critique, filed here since both are spec-020-scoped). Both remain accurate after this slice's implementation — neither fix round touched either concern. |
| `docs/memory/**` | `deferred` | Reserved for the end-of-ceremony `/jig:memory-sync` pass after spec 020 fully closes (both slices DONE), not per-slice — consistent with how this session is running the full spec through its lifecycle in one pass. |
| `docs/decisions/README.md` / ADR index | `no-op` | ADR-0024 already indexed and flipped to Accepted as part of this session's framing step, before implementation began. |
