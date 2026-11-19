---
status: RECONCILED
dependencies: [adr-0050]
last_verified: 2026-11-19
frame_review: true
claimed_by: claude/neval-from-required-check-2f5e9f
---

## Slice 044-01 — required-policy-evaluable

**Goal:** `n_evaluable` in `/servo:edd-suitability` is additionally satisfied by
a **deterministic, spec-attributed required-policy check** — the judge-free
static-source-contract observer (`family: command`, ADR-0046). The credit is
bound to the spec under analysis by an **explicit frontmatter binding**
(`fidelity_contract: <target-relative path>`) the spec author declares, and fires
only when the declared path resolves to a **live, enforceable** `family: command`
floor — a committed seal pinned to the current `oracle.sh` **and** installed as a
required component (the two-layer L1/L2 liveness check), not a committed
`approval_status: "approved"` label alone. The stochastic `design_fidelity` judge
**never** credits `n_evaluable`; `has_signal` and non-`fidelity_contract` specs
stay byte-identical.

**DoR:**
- ☑ [ADR-0050](../../decisions/adr-0050-eval-is-signal-not-evaluability.md)
  **Accepted** (2026-11-19, after a 4-round frame-critique that pinned the
  mechanism against live code — read the required-runtime check plan, attribute
  per-spec, exclude the judge; evidence at
  `docs/decisions/reviews/adr-0050-frame-critique.md`).
- ☑ The two-layer liveness predicate re-confirmed against the tree at
  implementation time: **L1** (committed `spec/oracle/static/checks.json`:
  `required_policy {schema_version:1, enabled:true}` + `approval_status:
  "approved"` + ≥1 `family:"command"`/`required:true` check + an
  `approved_required_binding` whose `required_ids` match the checks and whose
  `evaluator_artifacts` carry an `oracle.sh` row hashing the current `oracle.sh` —
  the `driver_seal` pin, static_contract.py ~911–927) and **L2** (runtime
  `.servo/required-policy.json` lists the static contract as an installed required
  component — `required_runtime.installed_policy` ~504–521). A committed
  `approval_status` label alone is insufficient (the R2 frame-critique correction);
  the full cryptographic seal stays score-time authority.
- ☑ Spec 030-01 (the paired `has_signal` eval leg) is DONE on `origin/main`
  (PR #72, `6cc670b`), so the vellum pairing (eval → `has_signal`, static
  contract → `n_evaluable`) is exercisable end to end.

**Acceptance Criteria:**

1. **A design spec that declares its own sealed static-source-contract check
   reaches `suitable` (the canonical vellum pairing).** Fixture: a target whose
   `install.json` has `signals: {tests:false, ci:false, lint:false}` and
   `components: ["design_fidelity"]`, with `.servo/design-eval/config.json`
   carrying the reviewed-frozen facts (`approval_status: "approved"`,
   `approval_provenance: "reviewed"`, `approved_content_hash`, non-empty
   `hashes`) so `has_signal` holds via 030-01; **and** a **live** static contract:
   a sealed `spec/oracle/static/checks.json` (`required_policy {schema_version:1,
   enabled:true}`, `approval_status: "approved"`, ≥1 `family: "command"`,
   `required: true` check, and an `approved_required_binding` whose
   `evaluator_artifacts` pin the current `oracle.sh` — L1), a matching
   `oracle.sh`, and a `.servo/required-policy.json` registering the static contract
   as an installed required component plus an `install.json` `required_policy` pin
   (L2); and a spec whose frontmatter declares
   `fidelity_contract: spec/oracle/static` and whose ACs are **all residual**
   (`oracle_plan classify` → `n_evaluable == 0` from AC text). `analyze` emits
   `verdict: "suitable"`, a `reasons` entry whose rule **code names the
   required-policy fidelity check as the evaluability basis** (distinct from the
   AC-based `evaluable_acs_with_*` codes, so `--explain` / `reasons` make the case
   auditable) **and** the eval as the signal, plus the standing **non-blocking**
   counterweight advisory (the eval is the sole signal). **No blocking
   `missing_evidence` item appears** — in particular no `reference_set` item,
   because the required-policy check supplies evaluability. Asserted via the CLI
   (artifact JSON).

2. **The stochastic `design_fidelity` judge alone never credits `n_evaluable`
   (ADR-0050 reject Option B — the core guard).** Fixture: the **same** reviewed,
   frozen, registered `design_fidelity` eval (so `has_signal` holds), **all
   residual** ACs, but the spec declares **no** `fidelity_contract` (and no static
   contract is installed). `analyze` emits `verdict: "needs_evidence"`, reason
   `signal_without_evaluable_acs`, with the **blocking** `reference_set` item
   ("add at least one deterministically-checkable AC"). The judge credits
   `has_signal` (030-01) but contributes **nothing** to `n_evaluable`: byte-for-byte
   the pre-slice 030-01 judged-only-no-evaluable artifact. Asserted via the CLI.

3. **The automatic / target-global leak is closed — an *undeclared* spec is never
   credited by a co-located static check (the mechanical guard — fact 4).**
   Fixture: a target that **does** carry a sealed static-source-contract check at
   `spec/oracle/static/checks.json`, analyzed against a spec that is all-residual
   and **does not declare `fidelity_contract`** (a spec that merely sits on the
   instrumented target). The static check is **not** credited — `analyze` returns
   `needs_evidence` (`signal_without_evaluable_acs` with the eval signal, or the
   terminal `unsuitable` `all_acs_residual_no_signal` with no signal), **never
   `suitable`**. A companion assertion proves the declaration is the discriminator:
   the **same target** analyzed against a spec that **does** declare
   `fidelity_contract: spec/oracle/static` → `suitable` (AC1); the only difference
   is the analyzed spec's own declaration — so the credit requires an affirmative
   per-spec opt-in, never a target-global credit a spec inherits for free. The
   synthetic `spec_id: "static"` / `source_spec_path: "spec/static.md"` in
   `checks.json` play **no** part in attribution (they are never matched against
   the feature spec). Asserted via the CLI.

3b. **The honest-author residual is explicit and fenced — a *deliberately
   declaring* second spec is credited; the gate does not compute AC↔redline
   correspondence (ADR-0050 reject-B boundary).** Fixture: a target with one real
   **live** static-source-contract check (L1 + L2 satisfied), analyzed against a
   **second, unrelated, all-residual** spec that **does** declare
   `fidelity_contract: spec/oracle/static`
   (deliberately pointing at the target's one redline, which was authored for a
   *different* spec). This spec **is** credited → `suitable` — and the test
   **documents** that this is the designed honest-author residual, not a bug: the
   gate's contract is *credit = the analyzed spec's own declaration **+** a real
   sealed deterministic floor*, and whether that floor's redline genuinely
   corresponds to this spec's fidelity goals is an **author-declared, reviewable
   claim** the gate cannot (and by ADR-0050's judge-exclusion must not) compute.
   The credit is sound **by construction** only within the single-redline-per-target
   vellum closure (one target, one redline, one design spec); a mis-declaration
   degrades to **a real deterministic floor attributed to the wrong spec**
   (Option-A-grade evidence), **never** Option B's vacuous judge-only oracle, and
   is caught by **spec review**. Pinning this as a test makes the attribution
   boundary first-class, so a future change that silently widens or narrows it is
   visible. Asserted via the CLI.

4. **A `fidelity_contract` that does not resolve to a *live, enforceable* check
   never credits (fail-closed validation — two-layer).** Each of these, with an
   all-residual spec declaring `fidelity_contract`, yields **no** `n_evaluable`
   credit (same `needs_evidence` / `unsuitable` as AC3). **L1 (committed seal +
   `oracle.sh` liveness):** (a) the declared path has no `checks.json`; (b)
   `checks.json` is unreadable / malformed JSON; (c) `required_policy` is absent or
   not `{schema_version:1, enabled:true}`; (d) `approval_status` is absent or not
   `"approved"` (draft / pending / unapproved); (e) a `checks` entry is not
   `family: "command"`, or not `required: true`, or the `checks` list is empty; (f)
   the declared path is absolute, escapes the target (`..`), or is otherwise unsafe;
   (g) `approved_required_binding` is absent/malformed or its `required_ids` do not
   match the checks; (h) **the `oracle.sh` pin is absent or stale** — no
   `{path:"oracle.sh"}` row in the binding's `evaluator_artifacts`, or its `hash`
   ≠ the current `oracle.sh` (the regenerated-`oracle.sh` honest-drift case — a
   committed-approved `checks.json` the score-time gate would env-error). **L2
   (installed as a live required component):** (i) `.servo/required-policy.json` is
   absent / malformed, `install.json` carries no `required_policy` pin, or no
   component **entry** (each entry *is* an `approved_required_binding`) both points
   at this static `checks.json` (`checks_path`) **and equals the committed binding**
   (the not-installed /
   different-required-check / re-sealed-but-not-reinstalled cases — where the oracle
   would otherwise env-error or green on the `design_fidelity` judge alone). None raises an env-error (exit 2) and none leaves a torn artifact. The
   judge is **excluded by construction** — the credit reads only the
   `family: command` check plan + its install manifests, never `install.json`'s
   quality `components` / `design_fidelity`. Each fail-closed predicate is isolated
   by a fixture so the DoD mutation-check holds. Asserted via the CLI and/or the
   pure helper.

5. **Non-`fidelity_contract` behavior is byte-identical (the regression fence).**
   For every spec that declares no `fidelity_contract` — all non-design specs, and
   a design spec without the binding — the emitted artifact is **byte-identical**
   to the pre-slice output across the 015 / 030 fixture matrix (tests/ci
   `suitable`, judged-only `suitable`, `needs_evidence`, `unsuitable`): same
   verdict, `reasons`, `missing_evidence`, `schema_version: 1`, and the
   `inputs.ac_counts.evaluable` still reports the **AC** count (the required-policy
   credit is **not** persisted into the artifact's `inputs`, mirroring 030-01's
   `eval_signal`). A regression test pins this against the current `decide()` /
   artifact outputs.

6. **Docs state the new evaluability source + its three constraints.** SKILL.md
   documents that `n_evaluable` is satisfied by a deterministic AC **or** a
   spec-attributed `family: command` required-policy check (the
   `fidelity_contract` binding), that the stochastic `design_fidelity` judge never
   satisfies `n_evaluable` (it stays `has_signal` + fidelity component only), and
   the attribution rule (per-spec declaration, not the synthetic static
   `spec_id`). `decide()`'s docstring names the new source. Surface-tested
   (`test_skill_surface.py`).

**DoD:**
- [x] All ACs pass; full test suite green (no regressions). 130 edd-suitability;
      full repo suite 3144 passed / 10 Playwright skips.
- [x] Each fail-closed predicate of AC4 mutation-checked (neutering the L1
      oracle.sh pin reds `test_h`; dropping the L2 `entry == binding` identity reds
      `test_i`; non-vacuous via the `test_baseline_live_contract_is_credited` anchor).
- [x] Host packages rebuilt + drift clean (`build_host_packages.py --check`) —
      `suitability.py` + SKILL.md ship in all three host packages.
- [x] Python 3.9 floor respected (`from __future__ import annotations`; no bare
      PEP 604 `X | None` in runtime code); ruff clean (line-length 100, B904/E501).
- [x] Independent review (compliance + craft) + frame-critique passed; deviation
      log + reconciliation sweep produced; reconciliation review passed.

**Assumptions:**
- **Attribution is author-declared under an honest-author threat model, sound by
  construction within the single-redline-per-target vellum closure (the
  load-bearing assumption).** The gate mechanically enforces the analyzed spec's
  own declaration (AC3) and that the declared floor is a real sealed deterministic
  check (AC4), but it **cannot** verify that a valid floor's redline corresponds to
  this spec's fidelity goals — that is the stochastic judgment ADR-0050 excludes.
  So a second feature spec that deliberately declares the binding on a shared
  target is credited (AC3b), caught by spec review, not the gate. This rests on
  servo's standing honest-author model (ADR-0036 guardrail 4; ADR-0049) and
  ADR-0050's own "single-redline-per-target identity … correspondence holds by
  construction" — not a mechanical anti-forgery guarantee. If a real target class
  ever shares one instrumented target across several independent feature specs
  (outside the vellum closure, ADR-0050 Kill criterion 2), the residual would need
  a content-level tie or a per-spec redline; this slice does not build that.
- **The credit must track score-time *enforceability*, via a two-layer liveness
  check — not a committed `approval_status` label (the R2 frame-critique's
  load-bearing correction).** The gate credits only when **L1** holds (committed
  `checks.json` sealed **and** its `approved_required_binding` pins the current
  `oracle.sh`) **and L2** holds (the static contract is a registered component in
  the runtime `.servo/required-policy.json`). This closes the honest-drift states a
  label-only predicate would wrongly admit — a regenerated `oracle.sh` (score-time
  env-error) and a not-installed / different-required-check floor (score-time
  green-on-judge, re-laundering Option B). The gate mirrors only these
  honest-drift-relevant liveness facts; the full cryptographic seal (config /
  fragment / canonical hash pins) stays score-time authority in
  `required_runtime` / `driver_seal` — so the gate never re-implements the seal,
  it refuses to *admit* a loop that would then refuse. `.servo/` is gitignored
  (runtime), read like the `.servo/install.json` the gate already consumes.
- **The credit is +1 (presence), not the internal CSS-property count.** A sealed
  static-source-contract check is **one** deterministic fidelity floor for the
  spec, regardless of how many computed-CSS properties it internally compares.
  Crediting `n_evaluable += 1` (not `len(checks)`) keeps the count honest — it
  does not conflate target-level property checks with per-AC evaluability — and
  only `>= 1` matters to the rule table. The evaluability source is surfaced in
  the decided reason code and the `--explain` trace, never folded into
  `inputs.ac_counts.evaluable` (so AC5 byte-identity holds).
- **The evaluability source must be threaded into the pure `decide()`** — like
  030-01's `eval_signal`. `analyze` (IO) computes the attributed required-policy
  presence and passes a `policy_evaluable` kwarg into `decide()` /
  `build_trace()` / the rule table (pure), so the deciding rule can name the
  evaluability *source* without re-reading files. `decide()`'s existing signature
  gains a keyword-only `policy_evaluable: bool = False` (default preserves every
  existing caller / AC5 byte-identity). The total used for the `>= 1` predicates
  is `n_evaluable_acs + (1 if policy_evaluable else 0)`; the AC-vs-policy
  evaluability source is derived inside `decide()` as `n_evaluable - (1 if
  policy_evaluable else 0)`.
- **A frontmatter scalar reader (stdlib) is sufficient.** The binding is a single
  top-level scalar (`fidelity_contract: <path>`) in the spec's leading `---`
  frontmatter block; a minimal reader (first fence block, `key: value`, strip
  quotes) with no PyYAML dependency reads it. Absent block / absent key → `None` →
  no credit (byte-identical).
- **The gate reads the spec file directly for the binding** (it already has the
  `--spec` path and stats it). `oracle_plan classify` is **not** changed to
  surface the binding — keeping its output byte-identical and the new read
  self-contained in `suitability.py`.
- **`has_signal` is untouched** — a static-contract-only target (no eval, no
  tests/CI) stays `needs_evidence` (`evaluable_acs_no_signal`); widening
  `has_signal` to required-policy checks is a separate decision out of scope here.

**Anti-horizontal-phasing check:** After this slice, a vellum-style design target
— no test suite, all-residual fidelity ACs, a reviewed+frozen `design_fidelity`
eval, a sealed static-source-contract check, and a spec that declares
`fidelity_contract: spec/oracle/static` — gets `suitable` (plus the counterweight
advisory) from `suitability.py analyze` end to end, so the Compile gate admits it
on a **real deterministic fidelity floor** instead of refusing it for lack of a
deterministic AC it does not need (AC1). The gate mechanically refuses the two
false-pass shapes it *can* refuse: a spec that declares no floor is never credited
(AC2 / AC3), and a declared floor that is not a real sealed deterministic check
fails closed (AC4) — so the judge-only vacuous oracle ADR-0050 primarily guards
against never returns. The one residual it **cannot** mechanically refuse — a
second feature spec on a shared target that *deliberately* declares the binding —
is stated first-class and fenced by a test (AC3b): it degrades to a real
deterministic floor attributed to the wrong spec (Option-A-grade, never Option B),
sound by construction within the single-redline vellum closure and otherwise
caught by spec review. The boundary is named honestly, not papered over.

### Deviation log (after reconciliation)

The six ACs (AC1, AC2, AC3, AC3b, AC4, AC5, AC6) are preserved. The
implementation matched the spec's stated approach (frontmatter binding read
directly in `suitability.py`; the `+1` presence credit folded into `n_evaluable`
upstream in `analyze`; the two-layer L1/L2 liveness predicate; judge-exclusion;
byte-identity via non-persistence of the threaded kwarg). As in 030-01, the major
movement was at the **frame**, not the code — three frame-critique rounds
materially hardened the mechanism before any implementation landed.

Review rounds (a fresh `general-purpose` reviewer per pass):

- **Frame-critique: R1 needs-changes → R2 needs-changes → R3 pass**
  (`frame_review: true`, load-bearing). R1 caught that the `fidelity_contract`
  binding is **author opt-in, not mechanical attribution** (a target-independent
  constant), and the spec overclaimed that a mis-pointed binding "fails closed."
  → Reframed to the honest-author threat model + the single-redline-per-target
  by-construction closure (ADR-0050's own account), with the residual made
  first-class and fenced by **AC3b**; the overclaim corrected everywhere. R2
  caught that the seal predicate trusted a committed `approval_status` label — a
  strict **subset** of the real seal — so it would admit honest-drift targets the
  score-time oracle refuses (stale `oracle.sh` → env-error) or greens past on the
  judge alone (not the installed required gate → Option-B relaunder). → Replaced
  with the **two-layer L1/L2 liveness check** (committed seal + current
  `oracle.sh` pin; installed as a required component with the committed binding),
  widening **AC4** (a–i). R3 passed, verifying L1/L2 predicts score-time
  enforceability (the catastrophic "no false *green*" axis is structurally closed
  — L2 forces the check into `required-policy.json`'s components, so
  `required_runtime.outcome` degrades any residual seal drift to env-error, never
  a green). R3's two non-blocking notes were applied before recording: the
  "mirror-drift is safe" justification was corrected from "never a false
  `suitable`" to the structural "no false *green*" guarantee (naming the benign
  env-error residual), and the L2 phrasing was fixed (a `components` entry *is* an
  `approved_required_binding`). Full journey in `reviews/slice-01-frame-critique.md`.
- **Compliance: R1 pass** (fresh `general-purpose`, no `[blocker]`; verified
  **empirically** — exercised the real module and tests, and independently
  mutated a scratchpad copy to confirm the AC4 fixtures are non-vacuous: neutering
  the L1 `oracle.sh` pin reds `test_h`, dropping the L2 `entry == binding`
  identity reds `test_i`, neutering the per-spec declaration gate reds both AC3
  attribution tests). One non-blocking `[nit]`: the mixed case (≥1 evaluable AC
  **and** a declared live floor) was verified correct by reading the code but had
  no dedicated test. Applied: `test_mixed_evaluable_ac_and_live_contract_keeps_ac_code`.
- **Craft: R1 pass** (fresh `general-purpose`, pr-review baseline; no `[blocker]`).
  Five `[strength]`s (non-vacuous mutation fixtures; score-time-liveness mirroring
  with the regenerated-`oracle.sh` witness; structural byte-identity; fail-closed
  helpers that never env-error; 030-01-parallel threading). Three non-blocking
  `[nit]`s, all applied: (1) `_read_frontmatter_scalar` matched an indented
  (non-top-level) key — tightened the regex to top-level only (+ indented-key
  test case); (2) the `+1` credit arithmetic was at three sites — extracted the
  `_policy_credit()` helper (ADR-0002 third-caller); (3) added defensive
  sub-branch witnesses `test_j..m` (binding kind, malformed required-policy.json,
  components-not-list, non-string check id).
- **No arch / code-health review** — the slice sets neither `arch_review` nor
  `code_health_review`: a rule-input widening within ADR-0015/0050, no module
  boundary or public-contract change (`workflow.py arch-review-needed` / `code-health-review-needed`
  both return `false`).
- Reconciliation is a separate independent gate over this deviation log; by
  ADR-0014 its verdict is its own review-evidence file (sweep row below).

Load-bearing choices made during implementation:

1. **Evaluability is computed in `analyze` (IO) and threaded into `decide` (pure)
   as a `policy_evaluable` kwarg** — mirroring 030-01's `eval_signal`. `decide` /
   `build_trace` / `_rule_table` / `_facts` all gain the kwarg (default `False`,
   preserving every existing caller + AC5 byte-identity); `analyze` returns a
   4-tuple so the CLI threads it into the `--explain` trace.
2. **The credit is +1 presence, not the internal CSS-property count** (one
   deterministic fidelity floor = one evaluability rung), centralized in
   `_policy_credit()`. It is **not persisted** into the artifact's `inputs`
   (`ac_counts.evaluable` keeps the AC count), which is exactly what keeps
   non-`fidelity_contract` artifacts byte-identical (AC5), surfacing only via the
   decided reason code (`evaluable_required_policy_with_{eval_,}signal`) and the
   `--explain` trace (`policy_evaluable`).
3. **The two-layer L1/L2 predicate mirrors only the honest-drift-relevant parts
   of the score-time seal** (L1 `driver_seal` `oracle.sh` pin; L2
   `installed_policy` registration + the `plan.approved_required_binding == entry`
   identity). The full cryptographic seal (config / fragment / `runtime_hash`
   pins) stays score-time authority — the gate refuses to *admit* a loop that
   would then refuse, rather than re-implementing the seal. Mirror-drift is a
   *conservative subset*: it can only produce a benign false-`suitable`-that-
   env-errors (iteration-1, loud), never a silent false *green*.
4. **Attribution is author-declared under the honest-author model** (ADR-0036 g4
   / ADR-0049), scoped to the single-redline-per-target vellum closure. An
   undeclared spec is never credited (AC3); a deliberately mis-declaring spec is
   the documented residual (AC3b), caught by spec review — the gate cannot (and by
   judge-exclusion must not) compute AC↔redline correspondence.
5. **All new reads are fail-closed** — `_load_json_file` / `_file_sha256` /
   `_read_frontmatter_scalar` / `_safe_target_relpath` swallow their own
   OSError/ValueError and `_required_policy_evaluable` returns only True/False, so
   the new leg never raises an env-error (exit 2) or leaves a torn artifact. Path
   safety (resolve + `is_relative_to`) defends against traversal / symlink escape.

Noted-not-changed:
- `has_signal` is **not** widened — a static-contract-only target (no eval, no
  tests/CI) stays `needs_evidence` (`evaluable_acs_no_signal`); whether a
  required-policy check should also satisfy `has_signal` is a separate decision
  ADR-0050 does not open.
- No change to `oracle.sh` / `gate.py` / `required_runtime.py` /
  `static_contract.py` / `oracle_plan.py` or any score-time contract — the gate is
  read-only over the committed `checks.json`, the runtime `.servo/required-policy.json`
  + `install.json`, and `oracle.sh`.
- ADR-0050 is **not** amended; it already records the decision + the honest-author
  / single-redline framing the frame-critique rounds confirmed.

### Reconciliation sweep

| Surface | Disposition | Note |
|---|---|---|
| `skills/edd-suitability/suitability.py` | updated | new leg: `_policy_credit`, `_load_json_file`, `_file_sha256`, `_read_frontmatter_scalar`, `_safe_target_relpath`, `_oracle_pin_matches`, `_required_policy_evaluable`; `policy_evaluable` threaded through `decide`/`build_trace`/`_rule_table`/`_facts`/`analyze` (now a 4-tuple)/`_run_analyze`/`render_human`; new reason codes `evaluable_required_policy_with_{eval_,}signal` |
| `skills/edd-suitability/test_suitability.py` | updated | AC1 (positive + `--explain` + human summary + mixed-case), AC2 (judge-never-credits), AC3 (undeclared + discriminator), AC3b (honest-author residual), AC4 a–m (two-layer fail-closed, baseline-anchored non-vacuous), AC5 (byte-identity both ways), helper units (frontmatter + path safety + `_required_policy_evaluable`) |
| `skills/edd-suitability/test_skill_surface.py` | updated | AC6 docs assertions (SKILL.md leg + attribution + liveness; `decide` docstring) |
| `skills/edd-suitability/SKILL.md` | updated | new `## The required-policy evaluability leg (ADR-0050 / spec 044)` section; 030-01 Scope boundary now cross-references the 044 exception |
| hosts/{claude,codex,copilot} edd-suitability copies | updated | `build_host_packages.py` regen; `--check` clean (suitability.py + SKILL.md) |
| `docs/specs/044-.../spec.md`, `slice-01-....md` | updated | authored + frame re-scope (honest-author + two-layer liveness); status rollup via `transition` |
| `docs/specs/044-.../reviews/` | updated | frame-critique, compliance, craft, reconciliation evidence. The regenerable `.candidates/` sidecar is excluded as scratch |
| ADR-0050 | no-op | not amended; records the decision + constraints the slice realizes |
| `oracle.sh` / `gate.py` / `required_runtime.py` / `static_contract.py` / `oracle_plan.py` / loop | no-op | read-only consumption; no schema bump (`schema_version: 1`); `has_signal` untouched |
| `install.json` schema / `.servo/required-policy.json` shape | no-op | read existing fields only (the `required_policy` pin + `components`) |
| `docs/specs/README.md` board | deferred | regenerated at close-out via `workflow.py status-board` |
| `docs/architecture.md` | no-op | no module-boundary / public-contract change (rule-input widening within ADR-0015/0050) |
| `docs/inbox.md` / `docs/refinement-todo.md` | no-op | the `has_signal`-for-required-policy question is named in the spec Non-goals; no new deferred decision |
| `docs/memory/**` | no-op | no new domain term or dead-end learning beyond what the spec + ADR-0050 already record |
