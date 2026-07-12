---
status: DONE
dependencies: [008-01, 008-02, 008-03, adr-0005, adr-0024]
last_verified: 2026-07-12
---

## Slice 008-04 — frozen-params-and-emit

**Goal:** Set the frozen `n` / `δ` / threshold / judge model+params with sane
defaults and plain-language trade-off guidance
([ADR-0005](../../decisions/adr-0005-eval-oracle-component.md): too-wide `δ` never
passes, too-narrow flaps), then emit the eval definition in the exact shape
`/servo:spec-oracle`'s eval-family extension compiles into a frozen `score_<name>`.
Closes the authoring path: this skill authors, spec-006 compiles+freezes, `gate.py`
runs.

### Acceptance criteria

- **AC1** A guided step sets `n`, `δ`, threshold, and judge model+params, each with
  a sane provisional default — inherited from the shipped fidelity presets
  (design-eval / content-fidelity `config.json`) as the starting point, tuned per
  eval — and a one-line plain-language trade-off note (the ADR-0005 knobs).
- **AC2** Emits the eval definition in the exact shape spec-006's eval-family compile
  step consumes → a frozen `score_<name>` per ADR-0005.
- **AC3** The emitted component is built on `skills/_common/fidelity_eval.py`
  (ADR-0024) for freeze/hash/n-sample/lower-bound/ledger/install-splice — **no
  parallel harness**; only the authoring-specific wrapper is new.
- **AC4** Authoring stops at an **approved, compilable definition**. This slice does
  not freeze or run — spec-006 compiles + freezes (ADR-0022 against parsed ACs,
  ADR-0023 co-located artifacts); `gate.py` runs.
- **AC5** A change to the rubric / dataset / model / `n` / `δ` / threshold refuses as
  stale via the shared `validate_freeze` (inherited, not re-implemented).
- **AC6** Tests cover: defaults applied when the author accepts them; the emitted
  definition compiling through spec-006 into a `score_<name>` that `gate.py` runs
  under the ADR-0002 exit contract; a param change triggering `spec_oracle_stale`.

> This is the seam to the existing machinery: everything downstream of the emitted
> definition is the ADR-0005 contract on the ADR-0024 harness, unchanged.

### Deviation log (after reconciliation)

Original ACs preserved above.

- **Architectural correction — no spec-006 "eval-family compile step" (load-bearing).**
  AC2/AC4/AC6 and the spec's Goal 5 + Core-model diagram described the emitted
  definition being compiled+frozen into `score_<name>` by *spec-006's eval-family
  compile step*. **That step does not exist** — `skills/spec-oracle/oracle_overlay.py`
  freezes only *deterministic* overlays (`score_spec_oracle_<id>`). The correct,
  already-shipped mechanism is the one both presets (`design-eval`,
  `content-fidelity`) use: the authoring skill **self-freezes + self-installs** the
  `score_<name>` component via the shared `fidelity_eval.py` splice machinery
  (`splice_component` / `splice_components_entry` / `register_manifest`). `emit`
  mirrors `content_fidelity.py`'s `freeze`+`install` nearly line-for-line. spec-006
  still *classifies* ACs (the `residual_judgment` bucket 008-01 triages) but never
  compiled judged evals. **No new ADR:** the mechanism is
  [ADR-0024](../../decisions/adr-0024-extract-frozen-eval-harness.md)'s (the shared
  harness the presets already self-install through) — this slice applies it and
  *corrects the spec prose* rather than deciding anything new. Spec prose fixed
  inline: Goal 5 + the Core-model diagram (live-prose fix per ADR-0010; git is the
  audit trail). Both review passes flagged this as a founded, well-documented
  deviation. (This slice's own **Goal header** above is preserved as-originally-authored
  per the deviation-log convention — it still names the refuted `/servo:spec-oracle`
  eval-family mechanism; read it together with this correction.)
- **Consequences of the correction for the AC text (preserved above):**
  - AC2 "spec-006's eval-family compile step consumes" → read as "the ADR-0024
    harness freezes + splices."
  - AC4 "does not freeze or run" → the *run* half holds (gate.py runs it); the
    *freeze* half is superseded — `emit` DOES freeze (flips `approval_status` to
    `approved`, pins `hashes` + `approved_content_hash`), which IS the ADR-0005
    clause-2 human-approval gate. Authoring stops there; it does not execute.
  - AC6 "compiling through spec-006 … a param change triggering `spec_oracle_stale`"
    → staleness surfaces as `StaleError` → exit 2 (the same fail-closed effect),
    not a literal `spec_oracle_stale` status string.
- **CLI shape.** `content_fidelity.py`'s separate `freeze`/`install` verbs are
  collapsed into one guided `emit` verb (`emit` freezes; `emit --target <dir>` also
  installs), matching the spec's own `emit` subcommand name. `install_component` /
  `uninstall_component` remain as independently-testable functions. An `uninstall`
  verb was added (not in the spec's `from-goal/triage/rubric/dataset/emit/audit`
  list) as the symmetric complement the AC6 install/uninstall round-trip needs.
- **008-03 carry-forwards, all resolved here.**
  - `validate_freeze` is now wired into `score()` (AC5) — a change to
    rubric/dataset/model/n/δ/threshold refuses as `StaleError` → exit 2 (the
    content-fidelity stale battery, adapted to the generic case shape).
  - `weight` is guarded (`_case_weight` → clean `EnvError` on a non-numeric weight);
    the `total_w <= 0` path retains its `EnvError`.
  - The DSL cross-module import is removed: `parse_constraint`/`evaluate_constraint`
    are **vendored (duplicated) into `score.py`** (so a standalone `.servo/<component>/`
    copy needs no `eval_authoring.py`), with a `VendoredConstraintDSLDriftGuardTests`
    behavioral drift-guard pinning the two copies equal.
  - The `_slug` collision is resolved: `component_name(spec_id, ac_id)` namespaces by
    spec id, so two specs' identically-named ACs never collide; shell-safe under the
    `score_` prefix.
- **`score()` now enforces freeze — inverts an 008-03 placeholder test.** 008-03's
  `test_score_does_not_enforce_freeze_on_a_draft_config` was a placeholder awaiting
  this slice; it is replaced by `test_score_enforces_freeze_stale_on_unapproved_config`
  (docstring names the inverted predecessor). Not a coverage regression — 008-03's
  ACs never required `score()` to skip freeze.
- **`config.json.threshold` vs the gate's `$THRESHOLD` (documented in the test).**
  The eval's `threshold` is pinned into the freeze hash, but the pass/fail gate is
  `oracle.sh`'s own global `$THRESHOLD` env var (the same split content-fidelity has).
  Captured in `GateContractTests`.

**Nits logged (non-blocking, from both review passes):**

- `_PARAM_TRADEOFFS` gives trade-off notes for n/δ/threshold/model but not
  `max_tokens`/`transport` (which `params` also accepts) — minor AC1-completeness gap.
- `freeze` permits an all-`EDIT ME`-placeholder dataset without warning (deliberate:
  min-size is advisory + the human owns approval; but a placeholder-content warning
  would be a cheap honesty improvement).
- The vendored-DSL drift-guard pins a narrow input space; the two `EnvError` classes
  differ (1-arg in `score.py` vs 2-arg in `eval_authoring.py`) — behavior is pinned,
  breadth could widen.
- `_case_weight` is invoked twice per case (once for `total_w`, once for the weighted
  sum) — harmless redundancy.
- `uninstall_target` validates `spec_id` explicitly while `emit_target` validates it
  indirectly via `eval_dir_for_spec` — cosmetic inconsistency, no security impact
  (`_slug` neutralizes any path-unsafe id).

**Carry-forward to close-out / later:** the comparative-archetype baseline judge
signature stays a documented unbuilt seam (no real candidate-gather exists yet); real
candidate-gather + per-candidate `actual_values` extraction remain unbuilt (`this skill
authors, gate.py runs`).

### Reconciliation sweep

- **`docs/specs/008-eval-authoring/spec.md`** — `updated`. Corrected the nonexistent
  spec-006 eval-family step to self-freeze/self-install via the ADR-0024 harness
  **at every occurrence** (reconciliation review caught the first pass as
  under-scoped): Goal 5, the Core-model diagram, the "from freeze/install onward"
  summary line, the Non-goals "Not running evals" bullet, the intro blurb, the SPIDR
  008-04 row, and the Spec-006 reference. The spec is now internally consistent.
- **`skills/eval-authoring/test_eval_authoring.py`** — `updated`. Module docstring now
  names 008-04.
- **`docs/architecture.md`** — `no-op` for the mechanism (no module-boundary/contract
  change — the emit reuses the ADR-0024 harness the presets use; no `arch_review`). The
  stale `/servo:eval-authoring (008, parked)` label refresh stays deferred to spec
  close-out (008-06 / final).
- **Load-bearing decision / ADR trigger** — `no-op` (new ADR). The self-install
  mechanism is ADR-0024's, already recorded; this slice applies it and corrects the
  spec prose. Reasoning recorded in the deviation log; both review passes concurred a
  spec-rationale note (not a new ADR) suffices.
- **`.claude-plugin/install-contract.json`** — `deferred`. Still no SKILL.md; suite +
  install-surface checks green; registration lands at close-out (008-06 / final).
- **`docs/refinement-todo.md`** — `no-op`. The logged nits are cheap in-skill
  follow-ups captured here with the slice they belong to, not open-ended debt.
- **Status board** — `deferred`. Regenerated after `DONE`.
