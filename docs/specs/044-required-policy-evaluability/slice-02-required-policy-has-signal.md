---
status: DONE
dependencies: [044-01, adr-0050, 030-01]
last_verified: 2026-11-19
frame_review: true
---

## Slice 044-02 — required-policy-has-signal

**Goal:** `has_signal` in `/servo:edd-suitability` is additionally satisfied by a
**live, enforceable required-policy check** — the *same* deterministic,
spec-attributed static-source-contract floor 044-01 already made satisfy
`n_evaluable` (the `fidelity_contract` binding + the two-layer L1/L2 liveness
check). A live required-policy check is an **executable deterministic gate the
score-time oracle runs**, so by ADR-0015's own definition of `has_signal` it is a
signal source — and a *strictly safer* one than the stochastic reviewed-frozen
eval 030-01 already credits. With this, a **static-contract-only** design target
(a live `fidelity_contract` floor, but **no** tests/CI and **no** reviewed eval)
reaches `suitable`, instead of being wrongly refused (`needs_evidence` /
`evaluable_acs_no_signal`) for lack of a signal it structurally has. The existing
`has_signal` sources (tests/CI, reviewed frozen eval — 030-01) are unchanged, and
the stochastic `design_fidelity` judge still **never** credits `has_signal` via
this leg (it stays a `has_signal` source via its own 030-01 path, and a fidelity
component only).

### The decision — a low-tension corollary of ADR-0050 (no new ADR)

ADR-0050 decided the **`n_evaluable`** leg: a deterministic, spec-attributed
required-policy check satisfies evaluability; the stochastic judge never does. It
is **silent** on whether that same check satisfies **`has_signal`** — 044-01
named this as the explicit follow-up ("whether a required-policy check should
*also* satisfy `has_signal` is a separate decision"). This slice settles it, and
records the decision here rather than in a new ADR because it is a **direct
corollary** of ADR-0050's logic, not a new load-bearing choice:

1. **It fits `has_signal`'s existing definition.** ADR-0015 defines `has_signal`
   as "an executable gate the oracle can run at all." A `fidelity_contract` floor
   that passes 044-01's L1/L2 liveness **is** exactly that: L2 forces the check
   into `<target>/.servo/required-policy.json`'s `components`, so
   `required_runtime.outcome` runs it at score time (and env-errors if it cannot)
   — grounded in 044-01's own R3 frame-critique (`required_runtime.outcome` ~707;
   `installed_policy` 504–521). Crediting it toward `has_signal` **applies the
   existing definition**, it does not widen it.

2. **It is a strict safe-direction widening.** 030-01 already credits a
   **stochastic** eval toward `has_signal`. Crediting a **deterministic** gate is
   *a fortiori* safe — deterministic-over-stochastic is the entire thrust of
   ADR-0050. The new case that passes (static-contract-only) is the
   **best-instrumented** design target, not a vacuous one.

3. **It opens no new false pass (the load-bearing safety claim).** The judge is
   still excluded from both legs; and the *same single* `policy_evaluable` check
   supplies both `has_signal` and `n_evaluable`, so there is **no** state where it
   satisfies the signal leg while leaving the evaluability leg unmet. A `suitable`
   verdict reached this way always rests on a real deterministic gate that is
   **simultaneously** the evaluability basis — the strongest basis the gate can
   ask for, never the all-residual-plus-vacuous-oracle shape ADR-0018/ADR-0050
   guard against.

4. **It reuses 044-01's liveness mechanism unchanged** — the `fidelity_contract`
   binding and the two-layer L1/L2 predicate (`_required_policy_evaluable`) are
   not touched; no new read, no new liveness logic. The decision-layer change is,
   however, **more than one `OR` term** — see "What the change actually is" below.
   It is a small, coordinated set of edits to the pure rule layer, all **gated on
   `policy_evaluable`** so non-`fidelity_contract` specs stay byte-identical.

5. **It is cleanly reversible** — revert the coordinated pure-layer edits (a
   handful of lines, all gated on `policy_evaluable`) — and changes no module
   boundary or public contract.

The only alternative — leave static-contract-only targets refused — is the gap
ADR-0050's own logic says to close (a real deterministic fidelity floor is the
trustworthy basis). There is no *rejected* load-bearing alternative to record, no
boundary change, and no new tension; that is why this is a slice-captured
corollary and not an ADR. The one genuinely-new element the honest scope surfaces
— the guardrail-5 advisory standing down on the vellum pairing — is a
*recomputation of g5's own "sole-signal" trigger over the now-widened
deterministic-signal set* (edit 3), not a change to g5's decision, and is
**operationally inert** (a non-blocking line on an already-`suitable` verdict,
which the Compile refusal path never reads). So it has no rejected load-bearing
alternative and needs no ADR-0036 amendment. **The `frame_review: true` adversarial
pass adjudicated exactly this** — R1 confirmed the safety frame and the no-ADR
classification and required the honest re-scoping (the original draft
under-described the change as "one `OR` term + dead-code removal"); R2 **passed**,
re-confirming the safety claim against the live code, and its two non-blocking
notes (the accurate g5-trigger basis above; naming the two reason-code constants)
were applied before recording the pass. Evidence at
[`reviews/slice-02-frame-critique.md`](reviews/slice-02-frame-critique.md).

### What the change actually is (honest scope — the frame-critique R1 correction)

The decision layer today has `has_signal = det_signal OR eval_signal`,
`eval_only = has_signal AND NOT det_signal`, and `det_signal` is **tests/CI
only** (`_SIGNAL_KEYS = ("tests","ci")`). So adding `policy_evaluable` to
`has_signal` *alone* would **not** reclassify the policy check as a deterministic
signal: on the vellum pairing (eval + live policy, no tests/CI) `eval_only` would
stay `True` and the decision would still take the (now self-contradictory)
`evaluable_required_policy_with_eval_signal` path. Closing the gap correctly is a
small **coordinated** set of edits to the *pure* rule layer (`decide` /
`_rule_table` / `build_trace` / `_facts` / `render_human`), **every one gated on
`policy_evaluable`** so a non-`fidelity_contract` spec is byte-identical by
construction:

1. **The `has_signal` disjunct.** `has_signal = det_signal OR eval_signal OR
   policy_evaluable`.
2. **Reclassify a live policy check into the deterministic-signal class.**
   Redefine `eval_only = eval_signal AND NOT det_signal AND NOT policy_evaluable`
   (the eval is "the sole signal" only when *neither* a test/CI signal *nor* a
   live policy check is present), and mirror that in `_facts`'s `signal_phrase`
   (a live policy check, when it is the deterministic anchor, gets its own phrase)
   and `render_human`'s judged-only / policy lines — including the two module
   constants that drive those lines and reference the to-be-removed code,
   `_POLICY_EVALUABLE_REASON_CODES` and `_EVAL_SIGNAL_REASON_CODES` (the latter
   collapses to just `("evaluable_acs_with_eval_signal",)` so `judged_only`
   detection stays correct).
3. **The guardrail-5 advisory stands down (ADR-0036 g5 trigger, recomputed over a
   widened signal set — *not* a claim of mechanism-equivalence).** Guardrail 5's
   advisory fires when "the judged eval is the *sole* signal" — its purpose is to
   stop a single stochastic judge from carrying the oracle alone. Once a live
   required-policy check is recognized as a deterministic signal (edit 2), the
   judge is no longer the sole gate on the vellum pairing, so **g5's own trigger is
   simply no longer met** — the advisory is suppressed by recomputing g5's
   condition over the widened deterministic-signal set, **not** by asserting the
   policy check is the same *mechanism* as g5's test/CI counterweight. (It is not:
   per [ADR-0044](../../decisions/adr-0044-required-constraints-cannot-be-averaged-away.md)
   a required-policy check is a separate pass/fail **veto**, not a component folded
   into the composite quality score; per `design-eval` it is CSS-only and does not
   establish whole-view fidelity.) This is operationally inert either way: the
   advisory is a non-blocking line on an already-`suitable` verdict, and
   `execution_planner`'s refusal formatting reads `missing_evidence` only on the
   `verdict != "suitable"` path, so whether it fires changes nothing about Compile
   proceeding. So there is no rejected load-bearing alternative and no ADR-0036
   amendment is needed — frame-critique R2 verified this.
4. **Name the signal provenance accurately in the policy reason-code messages.**
   044-01's `evaluable_required_policy_with_signal` message hardcodes "a
   compilable test/CI signal is present" — true in 044-01 (that code only ever
   fired with test/CI present), but **false** for the new static-contract-only
   provenance where the policy check is itself the signal. The
   `policy_only_evaluable` branch (and the `evaluable_acs_with_signal` branch)
   now name their deterministic signal accurately across provenances: **(a)**
   policy + test/CI → "…a compilable test/CI signal is present"; **(b/c)** the
   policy check is the deterministic signal (no test/CI; an eval may also be
   present as a non-decisive additional `has_signal` source) → "…supplies both
   the evaluability and the oracle signal".

**Only after edits 1+2** is `evaluable_required_policy_with_eval_signal`
unreachable — `policy_only_evaluable` ⟹ `policy_evaluable` ⟹ (new) `NOT
eval_only`, so "policy supplies evaluability **and** the eval is the sole signal"
is a contradiction — so it is then **removed as dead code**, with a test (or the
`--explain` trace) proving the coincidence rather than asserting it.

**The vellum-pairing consequence (a named, correct behavior change to 044-01
AC1).** On the vellum pairing (reviewed eval + live policy, no tests/CI,
all-residual) the verdict stays `suitable`, but: the deciding reason code moves
from `evaluable_required_policy_with_eval_signal` to
`evaluable_required_policy_with_signal` (provenance b — the policy check is the
deterministic signal; the eval is a non-decisive additional signal); the
counterweight advisory **stands down** (the policy check is the counterweight it
asked for); `missing_evidence` is empty. 044-01's AC1 test is updated to this
strictly-more-correct output (documented in the deviation log).

**DoR:**
- ☑ [ADR-0050](../../decisions/adr-0050-eval-is-signal-not-evaluability.md)
  **Accepted** (2026-11-19) — the governing decision; this slice is its named
  `has_signal` corollary.
- ☑ Spec **044-01** DONE on `origin/main` (PR #74, `f5ceeb3`) — the `n_evaluable`
  leg + the `fidelity_contract` binding + the two-layer L1/L2 liveness predicate
  (`_required_policy_evaluable`) this slice reuses **unchanged** as the single
  source of truth for *both* legs.
- ☑ Spec **030-01** DONE on `origin/main` (PR #72, `6cc670b`) — the
  reviewed-frozen-eval `has_signal` source this slice leaves unchanged; the vellum
  pairing (eval → `has_signal`, static contract → `n_evaluable` + now `has_signal`)
  is exercisable end to end.
- ☑ Re-confirmed against the tree: `has_signal = det_signal OR eval_signal` and
  `policy_evaluable` feeds **only** `n_evaluable` today (`suitability.py` `decide`
  / `_rule_table` / `build_trace` / `analyze`), so the gap is real.

**Acceptance Criteria:**

1. **A static-contract-only target reaches `suitable` (the motivating gap
   closed).** Fixture: a target with `signals: {tests:false, ci:false,
   lint:false}`, **no** reviewed eval (`components: []`, no design-eval config so
   030-01's `has_signal` does **not** hold), and a **live** static-source-contract
   (L1 + L2 as in 044-01: a sealed `spec/oracle/static/checks.json` whose
   `approved_required_binding` pins the current `oracle.sh`, plus a
   `.servo/required-policy.json` registering it as an installed required component
   and an `install.json` `required_policy` pin), analyzed against an **all-residual**
   spec that declares `fidelity_contract: spec/oracle/static`. `analyze` emits
   `verdict: "suitable"`, a `reasons` entry whose code is
   `evaluable_required_policy_with_signal` and whose message names the
   required-policy check as **both** the evaluability basis **and** the oracle
   signal (the new provenance-(c) message — it must **not** be 044-01's "a
   compilable test/CI signal is present" string, since there is no test/CI here),
   `has_signal == True` and `policy_evaluable == True` in the `--explain`
   trace, and **no blocking `missing_evidence`** (no `oracle_signal`, no
   `reference_set`). Before this slice the identical declaring fixture was
   `needs_evidence` (`evaluable_acs_no_signal`): `policy_evaluable` credited
   `n_evaluable` but **not** `has_signal`. That pre-slice state is now
   **unreachable by construction** (the one `policy_evaluable` boolean couples both
   legs — the safety property), so the delta is pinned by the positive test's
   explicit `has_signal == True` / `policy_evaluable == True` assertions plus a
   companion that shows the **declaration is the discriminator** (the same
   target+spec with no `fidelity_contract` → not `suitable`). Asserted via the CLI
   (artifact JSON + `--explain`).

2. **Existing `has_signal` sources are unchanged (regression fence).** (a) A
   target with tests/CI and no `fidelity_contract` → `suitable`, byte-identical to
   pre-slice. (b) A reviewed-frozen-eval-only target with all-residual ACs and no
   `fidelity_contract` → stays `needs_evidence` (`signal_without_evaluable_acs`):
   the eval still credits `has_signal` (030-01), the judge still contributes
   **nothing** to `n_evaluable` (044-01), and this slice adds nothing. (c) The new
   `has_signal`-from-policy credit reads **only** the live deterministic
   `family: command` check plan + its install manifests (via the unchanged
   `policy_evaluable`), **never** `install.json`'s `design_fidelity` quality
   component — judge-excluded on the signal leg exactly as on the evaluability
   leg. Asserted via the CLI.

3. **A `fidelity_contract` that is not *live* yields no `has_signal` from it
   (fail-closed — the signal leg inherits 044-01's two-layer gate).** Fixture: a
   **static-contract-only** target (no tests/CI, **no** eval — so nothing else can
   supply `has_signal`) whose declared floor fails an L1/L2 predicate (a
   representative set from 044-01's AC4 matrix: the stale / regenerated-`oracle.sh`
   pin, not-installed, draft `approval_status`, malformed `checks.json`; the
   declared-path-traversal case is already covered by 044-01's reused
   `_safe_target_relpath` / `_required_policy_evaluable` tests, since this slice
   reuses that predicate unchanged). Each yields `policy_evaluable == False` →
   `has_signal == False` →
   `verdict != "suitable"` — the terminal `unsuitable` (`all_acs_residual_no_signal`)
   for an all-residual spec with no other signal. None raises an env-error. This is
   what 044-01's AC4 (which used an eval-bearing target, so `has_signal` was masked
   by the eval) could not show: the policy **signal** leg itself fail-closes when
   the floor is not live, so a loop whose score-time oracle would env-error or
   green-on-judge is never admitted via the signal leg either. Asserted via the CLI
   and the pure helper.

4. **Non-`fidelity_contract` behavior is byte-identical (the regression fence,
   mirrors 044-01 AC5).** For every spec that declares no `fidelity_contract` —
   all non-design specs and a design spec without the binding — the emitted
   artifact is **byte-identical** to the pre-slice (044-01) output across the
   015 / 030 / 044 fixture matrix (tests/ci `suitable`, judged-only `suitable`,
   `needs_evidence`, `unsuitable`): same `verdict`, `reasons`, `missing_evidence`,
   `schema_version: 1`, and `inputs.ac_counts.evaluable` still the **AC** count.
   `policy_evaluable` is threaded through `decide` / `build_trace` as a kwarg
   (default `False`), never persisted, so all new `has_signal` logic is gated on it
   and a non-`fidelity_contract` spec is unchanged **by construction**. A
   regression test pins this.

5. **The vellum pairing is no longer "judged-only"; the dead reason code is
   removed (the named behavior change to 044-01 AC1).** Fixture: the vellum
   pairing (reviewed frozen eval **and** a live static contract, all-residual,
   declares `fidelity_contract`). After this slice: `verdict` stays `suitable`,
   but (a) the deciding reason code is `evaluable_required_policy_with_signal`
   (**not** `evaluable_required_policy_with_eval_signal`), because the live policy
   check is a deterministic signal, so the eval is not the sole signal; (b) the
   counterweight advisory (`tests`/`ci` non-blocking items) is **absent** (the
   policy check IS the deterministic counterweight); (c) `missing_evidence` is
   empty. The reason code `evaluable_required_policy_with_eval_signal` is **removed
   from the module** as unreachable (`policy_only_evaluable` ⟹ a deterministic
   policy signal ⟹ not "eval is the sole signal"). 044-01's AC1 test is updated to
   this behavior. Asserted via the CLI.

6. **Docs state the new `has_signal` source + the corollary rationale.** SKILL.md
   documents that `has_signal` is satisfied by a test/CI signal **or** a reviewed
   frozen eval (030-01) **or** a **live, enforceable required-policy check** (the
   same `fidelity_contract` + L1/L2 floor that satisfies `n_evaluable`), that this
   is a deterministic executable gate (strictly safer than the stochastic eval
   signal), and that a static-contract-only target is therefore `suitable`. The
   module docstring and `decide()` / `_rule_table` docstrings name the live policy
   check as a `has_signal` source. The now-removed `evaluable_required_policy_with_eval_signal`
   reference is cleaned up. Surface-tested (`test_skill_surface.py`).

**DoD:**
- [x] All ACs pass; full test suite green (no regressions). 142 edd-suitability;
      full repo suite 3161 passed / 10 Playwright skips / 415 subtests.
- [x] 044-01 AC1 test updated to the new vellum-pairing behavior (reason code +
      no counterweight advisory); the behavior change recorded in the deviation
      log. The removed `evaluable_required_policy_with_eval_signal` confirmed
      unreachable (`DeadReasonCodeUnreachableTests` proves `policy_only_evaluable`
      always coincides with a deterministic signal — the vellum pairing resolves
      to `evaluable_required_policy_with_signal`).
- [x] Each new fail-closed case of AC3 mutation-checked against the
      static-contract-only baseline (intact ⇒ `suitable`; any single break ⇒
      `unsuitable`, `has_signal == False`).
- [x] Host packages rebuilt + drift clean (`build_host_packages.py --check`) —
      `suitability.py` + SKILL.md ship in all three host packages.
- [x] Python 3.9 floor respected (`from __future__ import annotations`; no bare
      PEP 604 `X | None` in runtime code); ruff clean (line-length 100, B904/E501).
- [x] Independent review (compliance + craft) + frame-critique passed; deviation
      log + reconciliation sweep produced; reconciliation review passed.

**Assumptions:**
- **A live required-policy check is a `has_signal` source because it is an
  executable deterministic gate the score-time oracle runs (the grounding).** L2
  forces the check into `required-policy.json`'s `components`, so
  `required_runtime.outcome` runs it at score time (env-error if it cannot) —
  exactly ADR-0015's "an executable gate the oracle can run at all." Verified
  against 044-01's L1/L2 predicate + the `required_runtime.outcome` ~707 citation
  its R3 frame-critique grounded. So this applies the existing `has_signal`
  definition rather than widening it.
- **`has_signal`-via-policy never stands alone to produce a false `suitable` (the
  load-bearing safety claim).** The *same* single `policy_evaluable` boolean
  supplies both legs, so whenever it credits `has_signal` it also credits
  `n_evaluable` (both `>= 1`). There is no state where the policy check satisfies
  the signal leg while the evaluability leg is unmet, so `suitable` via this path
  always rests on a real deterministic gate that is simultaneously evaluable — the
  strongest basis, never the vacuous all-residual-plus-judge shape ADR-0050 /
  ADR-0018 guard against. **This is the claim the frame-critique must test.**
- **The judge stays excluded from `has_signal`-via-policy.** The credit keys on
  the unchanged `policy_evaluable`, which reads only the deterministic
  `family: command` check plan + install manifests, never `install.json`'s
  `design_fidelity` quality component. The eval's own `has_signal` credit (030-01)
  is a separate, unchanged path.
- **This is a corollary of ADR-0050, not a new decision — adjudicated by the
  frame-critique (R1 pass on the frame, needs-changes on the description).** The
  honest scope is a small coordinated set of pure-layer edits gated on
  `policy_evaluable` (see "What the change actually is"), not "one `OR` term"; it
  is cleanly reversible, changes no boundary/contract, and has no rejected
  load-bearing alternative — including the one genuinely-new element, extending
  guardrail-5's counterweight set, which applies ADR-0036 g5's intent (a
  deterministic check is the counterweight the advisory asks for). ADR-0050 is
  silent on `has_signal` (not contradicted). R1 confirmed the safety frame and the
  no-ADR classification; a future finding of a widened `has_signal` meaning or a
  reopened false pass would escalate to an ADR.
- **The vellum pairing ceasing to be "judged-only" is correct, not a regression.**
  The live policy check is the deterministic counterweight ADR-0033 / guardrail-5
  recommends, so the advisory correctly stops; the verdict stays `suitable`.

**Anti-horizontal-phasing check:** After this slice, a vellum-style
static-contract-only design target — no test suite, no reviewed eval, all-residual
fidelity ACs, a sealed+installed static-source-contract floor, and a spec
declaring `fidelity_contract: spec/oracle/static` — gets `suitable` from
`suitability.py analyze` end to end through the CLI (artifact JSON + human summary
+ `--explain`), so the Compile gate admits the best-instrumented all-deterministic
design case instead of refusing it for lack of a signal it structurally has. The
slice touches the user-facing verdict surface (verdict + reason code + human
summary + trace), not internal plumbing only — vertical, end-to-end value.

### Deviation log (after reconciliation)

The six ACs (AC1–AC6) are preserved. The implementation matched the slice's
**re-scoped** stated approach (the "What the change actually is" section): the
coordinated pure-layer edits — the `has_signal` disjunct, the deterministic-signal
reclassification (`eval_only` / `_facts` / `render_human`), the guardrail-5
counterweight stand-down, and the signal-provenance-accurate reason-code messages —
all gated on `policy_evaluable`, with the now-unreachable
`evaluable_required_policy_with_eval_signal` code removed. As in 030-01 / 044-01,
the major movement was at the **frame**, not the code: the frame-critique re-scoped
the change before any implementation landed.

Review rounds (a fresh independent reviewer per pass):

- **Frame-critique: R1 needs-changes → R2 pass** (`frame_review: true`,
  load-bearing). **R1** conceded the load-bearing *safety* claim (the single
  `policy_evaluable` boolean supplies both legs, so the signal leg can never stand
  alone to produce a false pass; a-fortiori-from-030-01 is sound; the env-error
  residual is 044-01's settled benign "no false green") and the no-ADR call, but
  caught that the slice's **self-description** was wrong against the live code:
  "one `OR` term + dead-code removal" — the `evaluable_required_policy_with_eval_signal`
  code is dead only *after* `eval_only` is redefined (since `det_signal` is
  tests/CI only), and the real change reclassifies the policy check into the
  deterministic-signal class, discharges the g5 counterweight advisory, and
  restructures the policy reason-code messages for the new static-contract-only
  signal provenance. → Rewrote the slice with the honest "What the change actually
  is" scope; corrected the dead-code sequencing; fixed AC1's expected message.
  **R2 (pass)** re-confirmed the safety claim against the live code (`:856` +
  `:858-861`), verified the dead-code claim is now correct, and the honest scope
  matches the module. R2's two non-blocking notes were applied before recording:
  (1) the g5 justification overclaimed *mechanism-equivalence* ("the policy check
  IS the deterministic counterweight") — reworded to the accurate basis: g5's
  "sole-signal / carry-the-oracle" trigger is simply no longer met once the policy
  check is a recognized deterministic signal (a required-policy check is a
  *narrower* mechanism — ADR-0044 veto, not a composite-score component; CSS-only),
  and it is operationally inert (a non-blocking line on an already-`suitable`
  verdict the Compile refusal path never reads); (2) named the two reason-code
  constants in the honest-scope edit list. Full journey in
  `reviews/slice-02-frame-critique.md`.
- **Compliance: pass** (fresh `general-purpose`, read-only against committed HEAD
  + worktree). Verified all six ACs met with non-vacuous tests, byte-identity by
  construction **and** the pre-existing `_GOLDEN_DECIDE` fence, and the dead code
  genuinely unreachable/fully removed. Two minor **non-blocking** imprecisions,
  both resolved: (1) AC1's prose claimed a companion pins the literal pre-slice
  `needs_evidence` delta, but that state is now unreachable (the coupling is the
  point) → reworded AC1 to describe what is actually pinned (the positive test's
  `has_signal`/`policy_evaluable` assertions + the declaration-discriminator
  companion); (2) AC3's break set covers 4 of 5 enumerated breaks → reworded to
  note the declared-path-traversal case is covered by 044-01's reused
  `_safe_target_relpath` / `_required_policy_evaluable` tests (predicate reused
  unchanged).
- **Craft: pass** (fresh `general-purpose`, pr-review baseline; no `[blocker]`).
  Four `[strength]`s (the single `policy_evaluable` boolean couples both legs so a
  `suitable` can never credit the signal leg while evaluability is unmet — safety
  invariant by construction; `_policy_credit` centralization; the real fail-closed
  mutation matrix + non-vacuous byte-identity test; accurate message provenance).
  Three `[nit]`s: nit 1 (`render_human` re-derived the det test inline instead of
  `_SIGNAL_KEYS`, a latent drift risk) — **applied**; nit 2 (ASCII hyphen vs the
  file's em-dash comment convention) — **applied**; nit 3 (the
  `det or eval or policy` triplication across `_rule_table`/`build_trace`/`decide`)
  — **no-op**: pre-existing from 030-01 (which deliberately did not extract), and a
  helper for a three-term boolean is unwarranted (ADR-0002's third-caller trigger
  was 030-01, not this slice; the leanness sweep cautions against it).
- **No arch / code-health review** — the slice sets neither `arch_review` nor
  `code_health_review` (`workflow.py arch-review-needed` / `code-health-review-needed`
  both return `false`): a rule-input widening within ADR-0015/0050, no module
  boundary or public-contract change.
- Reconciliation is a separate independent gate over this deviation log (ADR-0014);
  its verdict is its own review-evidence file (sweep row below).

Load-bearing choices made during implementation:

1. **All new `has_signal` behavior is gated on `policy_evaluable`** — so a spec
   with no `fidelity_contract` (policy_evaluable == False) is byte-identical to
   pre-slice by construction (AC4). Verified: when `policy_evaluable` is False,
   `has_signal` / `eval_only` / `_facts` / the reason-code branches all reduce to
   the exact pre-044-02 expressions.
2. **A live required-policy check joins the deterministic-signal class**, so
   `eval_only` is redefined `eval_signal AND NOT det_signal AND NOT policy_evaluable`
   (the eval is "the sole signal" only when neither a test/CI signal nor a live
   policy check is present). This discharges the ADR-0033 / g5 counterweight
   advisory on the vellum pairing — by **recomputing g5's own "sole-signal"
   trigger over the widened signal set**, not by asserting mechanism-equivalence
   with g5's test/CI counterweight — and it is operationally inert either way.
3. **The `evaluable_required_policy_with_eval_signal` reason code is removed as
   dead** — after edit 2, `policy_only_evaluable` (⟹ `policy_evaluable`) always
   coincides with `NOT eval_only`, so "policy supplies evaluability AND the eval
   is the sole signal" is a contradiction. Pinned by
   `DeadReasonCodeUnreachableTests` (the constants + a `_rule_table` matrix proving
   the code is never emitted and the vellum-pairing shape decides
   `evaluable_required_policy_with_signal`).
4. **The policy reason-code messages name the signal provenance accurately** —
   the `policy_only_evaluable` and `evaluable_acs_with_signal` branches now
   distinguish policy+test/CI ("a compilable test/CI signal is present") from
   policy-is-the-signal ("supplies both the evaluability and the oracle signal" /
   "a deterministic required-policy fidelity check (the oracle signal)"), so no
   reason ever falsely claims a test/CI signal that is not present.
5. **The 044-01 L1/L2 liveness mechanism is reused UNCHANGED** —
   `_required_policy_evaluable`, the `fidelity_contract` binding, and the two-layer
   seal/install check are not touched; the same `policy_evaluable` now simply feeds
   `has_signal` too.

The named behavior change to 044-01 AC1: the vellum pairing (reviewed eval + live
static contract) is no longer "judged-only" — its deciding reason code moves from
`evaluable_required_policy_with_eval_signal` to `evaluable_required_policy_with_signal`,
the counterweight advisory stands down, and `missing_evidence` is empty. The three
affected 044-01 tests (`test_declared_live_contract_all_residual_is_suitable`,
`test_explain_trace_shows_policy_evaluable`,
`test_mixed_evaluable_ac_and_live_contract_keeps_ac_code`) and the `_POLICY_CODES`
tuple are updated to this strictly-more-correct output.

Noted-not-changed:
- `_required_policy_evaluable` / L1 / L2 / `static_contract.py` / `required_runtime.py`
  / `oracle_plan.py` / `gate.py` / `oracle.sh` / the loop — no change (the gate is
  read-only; the liveness predicate is reused as-is).
- **No new ADR, and ADR-0050 / ADR-0036 are not amended** — the slice is a
  corollary of ADR-0050 (silent on `has_signal`, not contradicted), and the g5
  counterweight stand-down applies ADR-0036 g5's intent (its trigger recomputed
  over the widened signal set), so neither record's decision content changes.
  Frame-critique R1 + R2 adjudicated this.
- `docs/architecture.md` — no-op (rule-input widening, no module-boundary or
  public-contract change).
- `docs/inbox.md` / `docs/refinement-todo.md` — no-op (this slice *is* the named
  has_signal follow-up; no new deferred decision).
- `docs/decisions/lightweight-decisions.md` — no-op (the g5 counterweight
  stand-down is recorded in this slice spec + the deviation log, not a non-spec
  UI/visual decision).
- `docs/memory/**` — no-op (no new domain term or dead-end learning beyond what the
  slice + ADR-0050 already record).

### Reconciliation sweep

| Surface | Disposition | Note |
|---|---|---|
| `skills/edd-suitability/suitability.py` | updated | `has_signal` gains the `policy_evaluable` disjunct (`decide` / `_rule_table` / `build_trace`); `eval_only` redefined to exclude a live policy check; `_facts` policy signal_phrase; `render_human` names the signal when the policy check is it; `evaluable_required_policy_with_eval_signal` removed; both reason-code constants updated; docstrings/comments |
| `skills/edd-suitability/test_suitability.py` | updated | 4 044-01 tests re-pinned to the new behavior (vellum pairing no longer judged-only) + `_POLICY_CODES`; 5 new classes (`StaticContractOnlyHasSignalTests`, `ExistingHasSignalSourcesUnchangedTests`, `PolicySignalFailClosedTests`, `PolicySignalByteIdentityTests`, `DeadReasonCodeUnreachableTests`) |
| `skills/edd-suitability/test_skill_surface.py` | updated | `test_skill_md_documents_has_signal_from_required_policy` |
| `skills/edd-suitability/SKILL.md` | updated | new "also satisfies `has_signal`" paragraph; eval-signal-leg intro; reason-code mention de-lists the removed code |
| hosts/{claude,codex,copilot} edd-suitability copies | updated | `build_host_packages.py` regen; `--check` clean (suitability.py + SKILL.md) |
| `docs/specs/044-.../spec.md`, `slice-02-....md` | updated | re-open banner + Scope boundary / Non-goals / Decomposition / Slices; slice authored + frame re-scope; status rollup via `transition` |
| `docs/specs/044-.../reviews/` | updated | frame-critique (R1→R2), compliance, craft, reconciliation evidence. The regenerable `.candidates/` sidecar is excluded as scratch |
| ADR-0050 / ADR-0036 | no-op | not amended; the slice is ADR-0050's named corollary and applies ADR-0036 g5's intent (trigger recomputed, not redecided) |
| `_required_policy_evaluable` / L1 / L2 / `static_contract.py` / `required_runtime.py` / `oracle_plan.py` / `gate.py` / `oracle.sh` / loop | no-op | read-only consumption; the liveness predicate reused unchanged; no schema bump (`schema_version: 1`) |
| `docs/specs/README.md` board | deferred | regenerated at close-out via `workflow.py status-board` |
| `docs/architecture.md` | no-op | rule-input widening within ADR-0015/0050; no boundary / public-contract change |
| `docs/inbox.md` / `docs/refinement-todo.md` | no-op | this slice is the named `has_signal` follow-up; no new deferred decision |
| `docs/decisions/lightweight-decisions.md` | no-op | the g5 counterweight stand-down is a spec-captured decision (slice + deviation log), not a non-spec UI/visual call |
| `docs/memory/**` | no-op | no new domain term or dead-end learning beyond the slice + ADR-0050 |
