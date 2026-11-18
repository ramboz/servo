---
status: DONE
dependencies: [adr-0036]
last_verified: 2026-11-18
frame_review: true
---

## Slice 030-01 — eval-component-signal

**Goal:** `has_signal` in `/servo:edd-suitability` is additionally satisfied by
at least one **reviewed, frozen** eval component **installed** in the target's
oracle — established from the two manifests servo already writes
(`install.json`'s `components` registration + the eval's own
`approval_status`/`approval_provenance`/`approved_content_hash`/`hashes`
freeze facts; only `approval_provenance: "reviewed"` credits, per ADR-0036's
frame-critique revision 2026-08-31) — with a standing non-blocking advisory
when the judged eval is the *only* signal, and today's tests/ci behavior
byte-identical.

**DoR:**
- ☑ [ADR-0036](../../decisions/adr-0036-frozen-evals-satisfy-suitability-signal.md)
  **Accepted** (2026-09-01, after a 3-round frame-critique → reviewed-provenance-only
  eval leg; evidence at `docs/decisions/reviews/adr-0036-frame-critique.md`).
- ☑ Alias map re-confirmed against the tree at implementation time
  (`design-eval` → `design_fidelity`, `content-fidelity` → `content_fidelity`,
  eval-authoring dir == component name) — the closed set ADR-0036 assumes.
  Pinned in-code by `EvalAliasMapDriftTests.test_alias_map_matches_producer_source`.

**Acceptance Criteria:**

1. **A frozen + reviewed-approved + registered eval component alone flips the
   verdict to `suitable`, with the advisory.** Fixture: a target whose
   `install.json` has `signals: {tests: false, ci: false, lint: false}` and
   `components: ["design_fidelity"]`, plus `.servo/design-eval/config.json`
   carrying `approval_status: "approved"`,
   `approval_provenance: "reviewed"`, `approved_content_hash`, and a
   non-empty `hashes` map (no live judge, no capture — manifest facts only);
   a spec with ≥1 evaluable AC. `analyze` emits `verdict: "suitable"`, a
   `reasons` entry whose rule code names the eval-signal source (distinct from
   `evaluable_acs_with_signal`, so `--explain` and `reasons` make the
   judged-only case auditable), and **non-blocking** `missing_evidence`
   item(s) on the existing `tests`/`ci` kinds recommending at least one
   deterministic component (the ADR-0033 counterweight). No blocking item
   appears. Tested via the CLI (artifact JSON asserted).
2. **Unfrozen / unapproved / self-approved / provenance-less / unregistered
   never counts.** Five negative fixtures, same spec, each yielding today's
   `needs_evidence` with the blocking `oracle_signal` item: (a) config present
   but `approval_status: "draft"` (or absent); (b) `approval_status:
   "approved"` but `hashes` missing/empty (never frozen); (c) config fully
   approved + frozen but the component absent from `install.json`'s
   `components` (uninstalled); (d) approved + frozen but
   `approval_provenance: "self_approved"` (design-eval's self-ack path —
   auditability-only per ADR-0033, never creditable); (e) approved + frozen
   with **no** `approval_provenance` field at all (today's content-fidelity /
   eval-authoring freeze stamps). An unreadable/malformed per-eval config
   likewise counts as no eval signal (fail-closed) — never an env-error exit
   and never a torn artifact. Tested.
3. **tests/ci behavior is unchanged — byte-identical artifacts.** For targets
   where `tests` or `ci` is truthy (with and without an eval component
   present), the emitted artifact is byte-identical to the pre-slice output:
   rule 1 (`evaluable_acs_with_signal`) still fires, `missing_evidence` stays
   as today, `schema_version` stays 1. A regression test pins this by
   comparing against the current `decide()` outputs for the 015-01/02 fixture
   matrix.
4. **The gap's remedy list is truthful.** When no signal of any kind exists,
   the blocking `oracle_signal` item's `detail` now names all three remedies
   (test command, CI workflow, or a reviewed + frozen eval component); the
   `missing_oracle_signal` reason mirror (015-02 AC3 coherence) still holds.
   Tested.
5. **Docs retire the "empty on suitable" absolute.** SKILL.md's verdict table
   and `decide()`'s docstring say `suitable` may carry **non-blocking advisory
   items only** (blocking items still never appear on `suitable`;
   `unsuitable` still carries an empty list), and SKILL.md documents the
   eval-signal leg + its two manifest sources. `render_human` surfaces the
   advisory on a `suitable` verdict (today it prints advisory info only for
   `needs_evidence`). Surface-tested (`test_skill_surface.py`).
6. **Scope-boundary fence: the eval widens the signal leg, not the
   evaluable-AC leg (frame-critique 2026-11-17).** `suitable` requires
   `n_evaluable >= 1` **AND** `has_signal`; this slice widens only
   `has_signal`. A *purely*-residual design spec — all ACs visual-fidelity
   prose ("matches the mockup / redline / Figma"), which the **real**
   `oracle_plan classify` resolves to `n_evaluable == 0` (no deterministic
   check family matches) — against a target with `signals {tests:false,
   ci:false, lint:false}` is **refused — never `suitable`**, whether or not a
   reviewed, frozen, registered `design_fidelity` eval is installed. The test
   asserts **both ends of the delta** (so a regression can restore neither):
   (i) **with** the eval → `verdict: "needs_evidence"`, reason
   `signal_without_evaluable_acs`, blocking `reference_set` ("add at least one
   deterministically-checkable AC"); (ii) **without** the eval → the terminal
   `verdict: "unsuitable"`, reason `all_acs_residual_no_signal` ("route to a
   human"). The eval does **not** substitute for an evaluable AC — it only
   **upgrades the terminal `unsuitable` to a recoverable `needs_evidence`** (a
   bonus: it lifts a *false terminal* refusal) — so an all-judge oracle with
   zero deterministic anchors stays refused by design (ADR-0015 fail-closed +
   ADR-0036 guardrail 5 reward-hacking caution). That `unsuitable →
   needs_evidence` delta rides on a testless target class AC3's byte-identity
   fence does not cover, so **AC6 owns it**. Tested via the **non-stubbed**
   `oracle_plan.py` so the test pins the real residual classification of
   visual-fidelity ACs, not a stub's `n_evaluable`.
7. **Positive realistic case through the real classifier — the value claim is
   proven, not assumed (frame-critique round 2).** A design-led spec with **no**
   test/CI signal that carries ≥1 AC the **real** `oracle_plan` classifier
   recognises as deterministic — verified phrasings: "the built
   `dist/index.html` file is present" (`file_presence`), "running `npm run
   build` exits 0" (`command`), "the rendered HTML contains 'Sign in'"
   (`text_invariant`) — *alongside* a visual-fidelity AC ("matches the mockup"),
   against a target with `signals {tests:false, ci:false, lint:false}` **and** a
   reviewed, frozen, registered `design_fidelity` eval, yields `verdict:
   "suitable"` with the `evaluable_acs_with_eval_signal` reason and the
   non-blocking counterweight advisory. Tested via the **non-stubbed**
   `oracle_plan.py` so the positive claim is grounded in the real classifier,
   not a stub's injected `n_evaluable`. Together **AC6** (all-residual →
   refused) and **AC7** (mixed → admitted) bound the value claim empirically:
   the eval unblocks exactly the design-led targets that carry ≥1
   classifier-recognised AC — and only those.

**DoD:**
- [x] All ACs pass; full test suite green.
- [x] Fail-closed branches of AC2 mutation-checked (neutering any of the
      fail-closed predicates goes red).
- [x] Host packages rebuilt + drift clean (`build_host_packages.py --check`) —
      `suitability.py` + SKILL.md ship in all three host packages (claude /
      codex / copilot).
- [x] Independent review passed; deviation log + reconciliation sweep produced
      (ADR-0015 amendment note appended at ADR-0036 acceptance per its Status).

**Assumptions:**
- **The eval widens `has_signal` only; the `n_evaluable` leg is untouched
  (frame-critique 2026-11-17, two rounds → resolved by this re-scope).**
  `suitable` needs `n_evaluable >= 1` **AND** `has_signal`. `n_evaluable` comes
  from `oracle_plan classify`, which matches AC *text* against **token/keyword**
  families (a pre-existing spec-006 property this slice does not change), so
  whether a design-led target has an evaluable AC depends on how its ACs are
  *phrased*: "the built `dist/index.html` file **is present**" classifies
  (`file_presence`), the semantically-identical "the page exposes a built index
  file" does not. A spec whose ACs are **all** residual — visual-fidelity prose,
  and behavioural prose that misses the families (verified: "the component
  mounts" / "no console errors" / "the build produces output" are residual
  today) — stays `needs_evidence` even with the eval (AC6); a spec with ≥1
  classifier-recognised AC flips to `suitable` (AC7). ADR-0036's Verification
  bullet ("a reviewed + frozen + registered eval component **alone** yields
  suitable") therefore presumes the spec already carries ≥1 classifier-evaluable
  AC — the ADR widens the signal source and does not reconcile the `n_evaluable`
  leg, which this slice leaves unchanged **by design** (the eval is a gate, not
  an anchor). **Open, unresolved here:** whether vellum's real build-to-redline
  specs carry such an AC is not verifiable from this repo; if they are mostly
  all-residual, crediting the eval toward *evaluability* (the `n_evaluable` leg)
  is load-bearing for the motivating population and must follow soon — a
  separate, larger decision (a stronger judge-reliance claim than ADR-0036
  makes), named here, out of scope for this slice.
- **The distinct judged-only reason code needs the signal *source* in the rule
  table.** AC1's `evaluable_acs_with_eval_signal` (distinct from
  `evaluable_acs_with_signal`) cannot come from a `decide()` that only sees a
  collapsed `has_signal`; `decide()` / `build_trace()` / the rule table take an
  explicit `eval_signal` input (threaded from `analyze`'s manifest read) so the
  deciding rule names its source. A small, contained refactor — noted so it is
  an acknowledged change, not a surprise.
- Manifest-only detection is sufficient — no `oracle.sh` parsing, no live
  scoring, no re-hashing of frozen artifacts (staleness stays score-time
  authority via `validate_freeze` → rc 2, which fail-closes the loop
  downstream). Grounded by ADR-0036's code probe; re-confirm on
  implementation.
- The 015-01/02 fixture matrix (stubbed `SERVO_SUITABILITY_ORACLE_PLAN`
  classifier, tempdir targets) extends to the new fixtures without new test
  infrastructure — the eval leg needs only extra JSON files in the tempdir.
- Advisory emission needs a **new branch**, not literal reuse: today the
  non-blocking `tests`/`ci` items are emitted only inside
  `if not has_signal:` (`suitability.py:109-129`), and a judged-only target
  has `has_signal=True` — so AC1's advisory comes from a judged-only branch
  that emits those kinds while suppressing the blocking `oracle_signal` item
  (ADR-0036 round-3 frame-critique note).

**Anti-horizontal-phasing check:** After this slice, a design-led target with
no test suite — carrying ≥1 AC the **real** `oracle_plan` classifier recognises
as deterministic (e.g. "the built `dist/index.html` file **is present**" →
`file_presence`) *alongside* its visual-fidelity ACs — plus a reviewed, frozen
`score_design_fidelity` component gets `suitable` (plus the counterweight
advisory) from `suitability.py analyze` end to end — and the Compile gate
(015-03 / 016-01) admits it — instead of `needs_evidence` demanding tests it
does not need (**AC7**, pinned through the real classifier). A spec whose ACs
are **all** residual — visual-fidelity prose *or* behavioural prose that misses
the keyword families (verified: "the component mounts", "no console errors",
"the build produces output" all classify residual today) — is **refused, never
`suitable`** (**AC6**: with the eval it is `needs_evidence`, an *upgrade* from
the terminal `unsuitable` it would be with no signal at all), because this slice
widens the signal leg, not the token-based `n_evaluable` leg; that boundary is
fenced, not papered over.

### Deviation log (after reconciliation)

The seven ACs are preserved. The implementation matched the spec's stated
approach (manifest-only detection, byte-identical tests/ci, no schema bump); the
major movement during this slice was at the **frame**, not the code — three
frame-critique rounds materially reshaped the spec's scope statement before any
implementation landed.

Review rounds (a fresh `general-purpose` reviewer per pass):
- **Frame-critique: R1 needs-changes → R2 needs-changes → R3 pass** (`frame_review:
  true`, load-bearing). R1 caught that `suitable` needs `n_evaluable >= 1` **AND**
  `has_signal` and the slice widens only `has_signal`, so a purely-residual design
  spec stays refused even with the eval — the stubbed fixtures hid it. → Added the
  **Scope boundary** (spec overview) + **AC6** (real-classifier fence). R2 caught
  that the re-scoped "realistic design target carries ≥1 deterministic AC" claim
  used examples ("the component mounts" / "no console errors" / "the build
  produces output") that the token-based classifier itself classifies residual
  (verified by running `oracle_plan classify`). → Replaced them with
  real-classifier-verified phrasings ("the built `dist/index.html` file is present"
  → `file_presence`, etc.), narrowed the value claim to classifier-recognised ACs,
  added **AC7** (positive case through the real classifier), and named the
  vellum-population sufficiency as an explicit **Open question** (unverifiable from
  this repo). R3 passed, re-running the classifier on all seven phrasings and
  verifying every manifest/provenance fact against live code; it left one
  non-blocking note (applied): the all-residual case does not "stay"
  `needs_evidence` — it is terminal `unsuitable` with no signal and the eval
  **upgrades** it to recoverable `needs_evidence` (never `suitable`), so AC6 now
  asserts both ends of that `unsuitable → needs_evidence` delta (a testless target
  class AC3's byte-identity fence does not cover). Full journey in
  `reviews/slice-01-frame-critique.md`.
- **Compliance: R1 pass** (fresh `general-purpose`, no `[blocker]`; verified
  **empirically** — exercised the real module, confirmed AC2 mutation-isolation,
  AC3 byte-identity vs git-HEAD `decide()`, AC6/AC7 through the real classifier;
  blast radius 94 + 501 green, ruff clean, host-sync OK; no principle
  violations). Two non-blocking `[nit]`s: the rule-3 prose (same as craft,
  applied below) and a minor coverage gap — `_eval_signal`'s non-list guard and
  the judged-only `--explain` render path were not directly asserted (both
  empirically fail-closed / inert). The DoR alias-map re-confirmation is
  satisfied in-code by `test_alias_map_matches_producer_source`.
- **Reconciliation changes applied (from the two passes above):** the three
  craft/compliance `[nit]`s and the compliance coverage gap were fixed in this
  phase (details in load-bearing choice 6 below); the suite grew 94 → 100
  (`EvalSignalReconCoverageTests`), host packages were rebuilt, and
  `build_host_packages.py --check` stays clean.
- **Craft: R1 pass** (fresh `general-purpose`, no `[blocker]`; verified 94/94 +
  host-drift-clean + ruff-clean locally). Three non-blocking `[nit]`s, all
  applied during reconciliation: (1) rule 3's `signal_without_evaluable_acs`
  message hardcoded "a test/CI signal exists…", which contradicts the `_facts`
  suffix in the eval-only case — made source-aware (det keeps the exact
  pre-slice string so AC3 byte-identity holds; eval-only reads "a reviewed,
  frozen eval signal exists…"); (2) `render_human` inferred the judged-only case
  from advisory-presence — re-keyed on the decided reason code
  `evaluable_acs_with_eval_signal` so a future det-signal advisory can't print a
  false "sole signal" line; (3) defense-in-depth path guard in
  `_is_reviewed_frozen_eval` rejecting a component name with a path separator /
  `..` before it reaches the filesystem (install.json is servo-authored, so the
  risk is negligible, but the guard is cheap). Three `[strength]`s recorded:
  per-predicate fail-closed isolation with non-vacuous mutation fixtures,
  real-classifier grounding of AC6/AC7, and the alias-map drift guard.
- **No arch / code-health review** — the slice sets neither `arch_review` nor
  `code_health_review`; it is a rule-input widening within ADR-0015/ADR-0036, no
  module boundary or public-contract change.
- Reconciliation is a separate independent gate over this deviation log; by
  ADR-0014 its verdict is its own review-evidence file (sweep row below), not
  restated here.

Load-bearing choices made during implementation:

1. **The eval signal is computed in `analyze` (IO) and threaded into `decide`
   (pure) as an `eval_signal` kwarg**, not read inside `decide`. This keeps the
   decision pure/byte-stable and lets the rule table name the signal *source*:
   rule 1 emits `evaluable_acs_with_eval_signal` for a judged-only case
   (distinct from the deterministic `evaluable_acs_with_signal`), so `reasons` /
   `--explain` make the case auditable (AC1). `decide`/`build_trace`/`_rule_table`/
   `_facts` all take `eval_signal`; `analyze` now returns a 3-tuple
   `(spec_id, artifact, eval_signal)` so the CLI threads it into the trace.
2. **The eval signal is NOT persisted into the artifact's `inputs`.** This is
   what keeps tests/ci artifacts byte-identical with AND without an eval present
   (AC3) — the eval surfaces only via the decided reason code (judged-only case)
   and the stdout-only `--explain` trace, never the persisted JSON.
3. **`_is_reviewed_frozen_eval` checks four freeze facts independently and
   fail-closes on each** (`approval_status == "approved"`, `approval_provenance
   == "reviewed"`, non-empty `hashes`, present `approved_content_hash`), plus a
   `try/except` that treats an unreadable/malformed config as "no eval signal"
   (never an env-error). `approved_content_hash` is checked separately from
   `hashes` because ADR-0036 names both as required freeze facts; AC2 fixture (f)
   isolates that predicate so the mutation-check DoD holds for it.
4. **The judged-only counterweight advisory fires only for the `suitable`
   judged-only case** (`_missing_evidence(judged_only=...)`), not for an
   eval-signal `needs_evidence` (eval present but no evaluable ACs) — that case
   mirrors today's deterministic `signal_without_evaluable_acs` (reference_set
   blocking, no tests/ci nudge), keeping the two consistent.
5. **The closed dir↔component alias map (`_EVAL_COMPONENT_DIRS`) reverses the
   producers' forward mapping**, with `_eval_config_dir` falling back to
   dir-equals-name for eval-authoring components. A drift-guard test asserts the
   map matches the producers' `COMPONENT`/dir source (ADR-0036 kill criterion).
6. **Reconciliation nit fixes (both review passes, non-blocking → applied).**
   (a) Rule 3's `signal_without_evaluable_acs` message is now signal-source-aware
   like rule 1: the eval-only case reads "a reviewed, frozen eval signal exists
   but no evaluable ACs to gate on" (the det case keeps the exact pre-slice
   string, so the AC3 byte-identity golden is untouched — re-verified against
   git HEAD). This removes the self-contradiction the reviewers flagged (the old
   message claimed "a test/CI signal" while `_facts` appended "a reviewed frozen
   eval signal") and extends AC4's truthfulness to rule 3. (b) `render_human`
   keys the judged-only advisory block on the decided reason code
   (`evaluable_acs_with_eval_signal`), not on advisory-presence, so a future
   deterministic-signal `suitable` carrying an advisory could never print a
   false "sole signal" line. (c) A defense-in-depth guard in
   `_is_reviewed_frozen_eval` rejects a component name containing a path
   separator / `..` before it reaches the filesystem (install.json is
   servo-authored, so this is belt-and-suspenders). The compliance coverage gap
   (`_eval_signal` non-list guard + the judged-only `--explain` render path) is
   closed by `EvalSignalReconCoverageTests` (6 tests). All test-guarded:
   100 edd-suitability pass, ruff clean, host packages re-synced.

Noted-not-changed:
- The `n_evaluable`-leg decision (crediting the eval toward *evaluability* to
  lift the all-residual case) is **out of scope** and named as an Open question /
  possible follow-up in the spec Scope boundary + slice Assumptions — a separate,
  larger decision (stronger judge-reliance than ADR-0036 makes).
- ADR-0036 is **not** amended; its Verification bullet's presumption of ≥1
  evaluable AC is documented in the spec's Assumptions instead (an accepted-ADR
  amendment would need owner approval; the spec is the right home for the
  implementation-level scope boundary).

### Reconciliation sweep

| Surface | Disposition | Note |
|---|---|---|
| `skills/edd-suitability/suitability.py` | updated | eval-signal leg: `_load_manifest`, `_EVAL_COMPONENT_DIRS`, `_eval_config_dir`, `_is_reviewed_frozen_eval`, `_eval_signal`; `eval_signal` threaded through `decide`/`build_trace`/`_rule_table`/`_facts`; judged-only advisory; `analyze` 3-tuple; `render_human` advisory on `suitable`. **Rename:** `_load_signals` → `_load_manifest` (returns the full `install.json` so `components` is read alongside `signals`; all call sites updated — the spec's "Current state" probe names the pre-rename `_load_signals`) |
| `skills/edd-suitability/test_suitability.py` | updated | AC1/AC2 (8 negatives inc. malformed + mutation-isolation), AC3 (golden + invariance + CLI byte-identity), AC4, AC6 (both delta ends), AC7 (positive via real classifier), alias-map drift guard |
| `skills/edd-suitability/test_skill_surface.py` | updated | AC5 docs assertions + `render_human` judged-only advisory surfacing |
| `skills/edd-suitability/SKILL.md` | updated | verdict table row; retired the "empty on suitable" absolute; new `## The eval-signal leg` section (two manifest sources + scope boundary) |
| hosts/{claude,codex,copilot} edd-suitability copies | updated | `build_host_packages.py` regen; `--check` clean |
| `docs/specs/030-.../spec.md`, `slice-01-....md` | updated | frame re-scope (Scope boundary, AC6/AC7, Assumptions, Open question); status rollup |
| `docs/specs/030-.../reviews/` | updated | recorded review evidence (frame-critique, compliance, craft; reconciliation added at close-out). The regenerable `.candidates/` sidecar (the shown richer-skill set; richer-skill was `none`) is excluded as scratch |
| ADR-0036 | no-op | not amended; boundary + follow-up documented in the spec (owner-approval rule for accepted records) |
| `install.json` schema / `oracle.sh` / `gate.py` / loop | no-op | ADR-0036 non-goals; reads existing `components`, no schema bump (`schema_version: 1`) |
| eval producers (`design_eval`/`content_fidelity`/`eval_authoring`) | no-op | read-only; alias map mirrors them, drift-guarded by test |
| other `suitability.py` consumers | no-op | none — grep confirmed no external callers of `analyze`/`_load_manifest`/`build_trace`/`decide` outside the skill, so the `_load_signals`→`_load_manifest` rename is internal |
| `docs/specs/README.md` board | deferred | regenerated at close-out via `workflow.py status-board` |
| `docs/inbox.md` / `docs/refinement-todo.md` | deferred | the n_evaluable-leg follow-up is named in the spec; a tracking entry can be added at close-out if the orchestrator wants it tracked outside the spec |
