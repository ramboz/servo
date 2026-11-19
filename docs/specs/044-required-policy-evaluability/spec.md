---
status: DONE
skill:
use_cases: []
---

# Spec 044: required-policy evaluability (a deterministic, spec-attributed required-policy check satisfies `n_evaluable`)

> Realizes [ADR-0050](../../decisions/adr-0050-eval-is-signal-not-evaluability.md)
> (**Accepted** 2026-11-19, 4-round frame-critique;
> `docs/decisions/reviews/adr-0050-frame-critique.md`). The named follow-up to
> spec [030-01](../030-suitability-eval-signal/spec.md): 030-01 widened the
> **`has_signal`** leg (a reviewed, frozen eval credits the signal), deliberately
> leaving **`n_evaluable`** untouched. The gap it named: a pure build-to-redline
> design target (vellum's workflow) is **all-residual** — every AC a fidelity
> match the model-judge scores, so `oracle_plan classify` returns
> `n_evaluable == 0` — and therefore sits at `needs_evidence`, never `suitable`,
> even after 030-01. ADR-0050 decided how a design-led target earns
> evaluability: **not** by crediting the stochastic judge (reject Option B), but
> by crediting a **deterministic, spec-attributed required-policy check** — the
> judge-free static-source-contract observer (`family: command`, ADR-0046), which
> renders the built app and compares computed CSS against the redline within
> tolerance.

## Overview

Teach `/servo:edd-suitability` to credit `n_evaluable` from a **deterministic
required-policy check attributed to the spec under analysis**, in addition to a
deterministic AC. Today `n_evaluable = len(oracle_plan classify's checks)` —
deterministic AC *text* only (`suitability.py` `analyze`). This slice adds a
second, bounded evaluability source governed by ADR-0050's **three load-bearing
constraints**:

1. **Deterministic only.** The credit reads a `family: command` required-policy
   check (the static-source-contract observer at `<target>/spec/oracle/static/checks.json`,
   ADR-0046). The **stochastic vision eval (`design_fidelity`) never** satisfies
   `n_evaluable` (rejects Option B) — it stays a `has_signal` source and fidelity
   component only (030-01, unchanged).
2. **Spec-attributed.** A required-policy check credits `n_evaluable` **only for
   the spec whose redline it corresponds to**, never target-globally. The static
   `checks.json` is a per-*target* artifact (`spec_id: "static"`), while
   `n_evaluable` is per-*spec*; an **unqualified** credit would pass an unrelated
   all-residual spec co-located on the same instrumented target — the exact false
   pass ADR-0050 exists to prevent (fact 4 / Kill criterion 1).
3. **Judge-excluded.** The credit reads the deterministic check plan directly; it
   **never** reads `install.json`'s `components` / `design_fidelity` into
   `n_evaluable` (fact 3).

**The attribution handle (the load-bearing part — ADR-0050 Assumptions + Kill
criterion 1).** Neither artifact names the other: the static `checks.json`
carries synthetic redline literals (`spec_id: "static"`,
`source_spec_path: "spec/static.md"` — `static_contract.py::prepare`), which
**collide in name** with the feature-spec `source_spec_path` in
`oracle_plan`/`required_runtime` and so must **not** be used to attribute; and
`oracle_plan classify` returns only the feature spec's own `spec_id` / `checks` /
`residual_judgment`, naming no redline. So this slice adds **an explicit binding**
(ADR-0050's sanctioned handle): the design spec **declares its own deterministic
fidelity floor** in its frontmatter —

```yaml
fidelity_contract: spec/oracle/static   # target-relative path to the sealed
                                        # static-source-contract checks.json dir
```

The gate credits `n_evaluable` **iff** the spec under analysis declares
`fidelity_contract` **and** the declared path resolves to a **live, enforceable**
static-source-contract floor — a committed seal pinned to the current `oracle.sh`
**and** installed as a required component in the runtime policy (the two-layer
`L1`/`L2` liveness check in Assumptions, which mirrors the honest-drift-relevant
parts of `driver_seal` / `required_runtime`; the full cryptographic seal stays
score-time authority). A committed `approval_status: "approved"` label alone does
**not** suffice — that is the R2 frame-critique's load-bearing correction.

**What this handle does and does not guarantee — the honest-author threat
model.** Two mechanical guarantees hold; one residual is explicitly **not**
closed by the gate, and this slice states that plainly rather than claiming a
mechanical guarantee a deterministic gate cannot provide:

- **Mechanical (gate-enforced).** (i) The credit requires the analyzed spec's
  **own affirmative declaration** — a spec that declares no `fidelity_contract`
  is **never** credited, even on a fully instrumented target. This closes the
  *automatic / target-global* leak — the common case, and the one fact 4 frames:
  a spec gets nothing merely by sitting on an instrumented target (AC3). (ii) The
  declared target must be a **live, enforceable deterministic check** — a missing,
  malformed, draft, unapproved, disabled, non-`command`, non-`required`, traversal,
  **stale-`oracle.sh`-pin, or not-installed-as-a-required-component** binding fails
  closed (AC4, the two-layer L1/L2 check). So the gate rejects the unqualified
  target-global credit, a fabricated / vacuous / unsealed floor, **and** an
  honest-drift floor the score-time oracle would refuse (env-error) or green past
  on the judge alone.
- **Residual (not gate-closed — the honest-author model).** The gate **cannot**
  verify that a *valid, sealed* contract's redline actually **corresponds** to
  the declaring spec's fidelity goals — computing AC↔redline correspondence is
  precisely the stochastic judgment ADR-0050 **excludes** from `n_evaluable`. So
  a second, unrelated, all-residual spec that **deliberately** declares
  `fidelity_contract` pointing at the target's one real sealed contract **is**
  credited (AC3b). This is sound **only within the single-redline-per-target
  vellum closure** ADR-0050 scopes to — *one target, one redline, one design
  spec*, where the correspondence holds **by construction** — which is the ADR's
  **own** account of the handle: *"the single-redline-per-target identity
  (vellum's case: one target carries one redline for one design spec, so the
  correspondence holds by construction), or an explicit binding the slice adds."*
  Outside that closure (several feature specs sharing one instrumented target),
  the declaration is an **affirmative, reviewable attribution caught by spec
  review**, not by the gate — servo's standing honest-author trust model
  (ADR-0036 guardrail 4's self-reported `reviewed` string; ADR-0049's
  honest-worker scoping). Even a mis-declared credit degrades to **a real
  deterministic fidelity floor attributed to the wrong spec** — Option-A-grade
  evidence, **not** Option B's vacuous judge-only oracle — so the worst case is
  materially weaker than the false pass ADR-0050 primarily guards against.
  Multi-redline / multi-spec disambiguation is out of scope (Kill criterion 2).

On a vellum target `static_contract.py::prepare` writes exactly one static
contract at the hardcoded `spec/oracle/static` (and refuses a second), so within
the closure the declared floor is unambiguous — the by-construction identity the
credit rests on.

With this, a design-led target reaches `suitable` by **pairing** the vision eval
(the `has_signal` fidelity signal, 030-01) with its **own** static-source-contract
check (the deterministic `n_evaluable` fidelity floor, this slice), while an
all-residual spec that declares no deterministic floor — and has no deterministic
AC — correctly stays `needs_evidence`.

**Scope boundary — this widens the `n_evaluable` leg only; `has_signal` is
untouched.** `suitable` needs `n_evaluable >= 1` **AND** `has_signal`
(`suitability.py` rule 1). 030-01 widened `has_signal`; this slice widens only
`n_evaluable`. A target carrying **only** a static contract (no eval, no
tests/CI) has `n_evaluable >= 1` but `has_signal == False`, so it is
`needs_evidence` (`evaluable_acs_no_signal`) — correct, and out of scope to
change here (whether a required-policy check should *also* satisfy `has_signal` is
a separate decision ADR-0050 does not open). The motivating vellum case pairs the
static contract **with** the design eval, whose 030-01 `has_signal` closes that
leg.

Current state (probed 2026-11-19, against `origin/main` at ADR-0050 / 030-01):

- `n_evaluable = len(plan.get("checks", []))` — the count of deterministic ACs
  from `oracle_plan classify`, consumed in `analyze` and threaded into
  `decide()` / `build_trace()` / the rule table (`suitability.py`). No other
  evaluability source is read today.
- The static-source-contract observer writes a per-target plan to the hardcoded
  `<target>/spec/oracle/static/checks.json` (`static_contract.py::prepare`): top-level
  `required_policy: {schema_version: 1, enabled: true}`, `spec_id: "static"`,
  `source_spec_path: "spec/static.md"`, and `checks: [{id, family: "command",
  required: true, …}]`. `prepare` writes **no** `approval_status`; the required-policy
  **install** step stamps `approval_status: "approved"` + `approved_required_binding`
  (which carries the `oracle.sh` hash-pin `driver_seal` checks, static_contract.py
  ~911–927) into the committed `checks.json`, **and** writes the runtime
  `<target>/.servo/required-policy.json` (the installed-component manifest
  `required_runtime.installed_policy` reads, ~504–521) + an `install.json`
  `required_policy` pin. `.servo/` is gitignored — runtime state, like
  `.servo/install.json`, which the gate already reads.
- `design_fidelity` (the stochastic judge) is the one fidelity entry in
  `install.json`'s `components`; 030-01's `_eval_signal` resolves it to credit
  `has_signal` only. Nothing reads it toward `n_evaluable`.

Non-goals: no change to `has_signal` (030-01's leg stays as-is); no change to
`oracle.sh` / `gate.py` / `required_runtime.py` / `static_contract.py` /
`oracle_plan.py` / the loop or any score-time contract (the gate is **read-only**
over the committed `checks.json`, the runtime `.servo/required-policy.json` +
`install.json`, and `oracle.sh`); **no re-implementation of the full cryptographic
seal** — the gate mirrors only the honest-drift-relevant liveness facts
(`oracle.sh` pin + install registration); the config/fragment/canonical hash pins
stay score-time authority in `required_runtime`/`driver_seal`; no schema bump
(`schema_version: 1`, the `missing_evidence` taxonomy, the five-rule table all
stay); no crediting a required-policy check toward `has_signal`; no
multi-redline-per-target disambiguation (ADR-0050 Kill criterion 2 scopes the
handle to the single-redline vellum case).

## Assumptions

- **The credit must track score-time *enforceability*, not a committed label — a
  two-layer liveness check (the R2 frame-critique's load-bearing correction).**
  `approval_status: "approved"` in the committed `checks.json` is **necessary but
  not sufficient**: `static_contract.py::prepare` writes `checks.json` *without*
  that label, and the required-policy **install** step stamps it together with
  `approved_required_binding` and a **live `oracle.sh` hash-pin**, and writes the
  runtime `.servo/required-policy.json`. A predicate that trusts the label alone
  would credit honest-drift states the score-time oracle **refuses** — the
  airtight code-only case is an `oracle.sh` legitimately regenerated after sealing
  (a new quality component, a threshold change, a re-scaffold): `driver_seal`'s
  `oracle.sh` pin no longer matches, so the static check env-errors at score time
  while the stale `checks.json` still reads `approved`. Worse, a committed-sealed
  contract that is **not the installed required gate** (a different required check
  installed, or none) lets the oracle green on the `design_fidelity` *judge*
  alone — re-laundering Option B's false pass through the evaluability leg. So the
  gate credits **iff** two liveness layers hold, mirroring the honest-drift-relevant
  parts of the real seal (the full cryptographic seal — config/fragment/canonical
  hash pins — stays score-time authority in `required_runtime`/`driver_seal`, which
  refuse when the oracle runs; the gate's job is to not *admit* a loop that would
  then refuse or green-on-judge, per ADR-0015):
  - **L1 — committed seal + `oracle.sh` liveness** (`<target>/spec/oracle/static/checks.json`):
    `required_policy == {schema_version:1, enabled:true}`, `approval_status ==
    "approved"`, ≥1 `checks` entry all `family=="command"` + `required is true`,
    and an `approved_required_binding` whose `required_ids` match the checks **and**
    whose `evaluator_artifacts` carry exactly one `{path:"oracle.sh", hash:H}` with
    `H == sha256(<target>/oracle.sh)` — the same `oracle.sh` pin `driver_seal`
    checks (static_contract.py ~911–927). Closes the regenerated-`oracle.sh` case.
  - **L2 — installed as a live required component** (`<target>/.servo/required-policy.json`,
    the runtime manifest `required_runtime.installed_policy` reads): it exists, is
    `kind: "required_policy"`, `install.json` carries a `required_policy` pin, and a
    component **entry** in `components` (each entry *is* an `approved_required_binding`)
    points at this static `checks.json` (its `checks_path`) **and equals the
    committed `checks.json`'s `approved_required_binding`** — installed == committed,
    exactly the `plan.approved_required_binding == entry` identity score-time
    enforces (`required_runtime.oracle` ~779–785). Closes the not-installed /
    different-required-check / re-sealed-but-not-reinstalled cases — the ones that
    would otherwise env-error or green on the judge alone.

  **The guarantee is "no false *green*", not "no false `suitable`" (structural, not
  subset-cardinality).** The gate mirrors only a **subset** of score-time's seal —
  the honest-drift-relevant liveness facts (install registration, binding equality,
  `oracle.sh` pin), not every residual (`runtime_hash`, config / fragment hash
  pins). So states exist where `L1∧L2` hold (gate: `suitable`) but score-time
  **env-errors** on an unmirrored residual — e.g. a servo upgrade re-vendors
  `.servo/required_runtime.py` without re-installing (score-time `installed_policy`
  checks `runtime_hash`, ~516–517; the gate does not), or config / fragment drift
  between the committed `checks.json` and the installed entry. These are **benign**:
  the *catastrophic* axis is **structurally closed** — L2 forces the static check
  into `required-policy.json`'s `components`, and once there `required_runtime.outcome`
  (~707: `required == "unknown" or composite is None → exit 2`) turns **any**
  required-seal failure or omission into a score-time **env-error, never a green**.
  So a residual false-`suitable` costs one loud iteration-1 env-error (visible,
  fail-closed), exactly like the regenerated-`oracle.sh` case L1 closes — it never
  produces the silent judge-only false *green* ADR-0050 / ADR-0015 guard against.

  Any missing / malformed / draft / stale-pin / unlisted state is fail-closed (no
  credit, never an env-error). `.servo/` is gitignored (runtime), so the gate reads
  it the same way it already reads `.servo/install.json`.
- **The attribution handle is author-declared + the single-redline-per-target
  by-construction closure, under an honest-author threat model** (ADR-0050
  Assumptions / Kill criterion 1 — the load-bearing risk). The spec-declared
  `fidelity_contract` frontmatter is a per-spec, reviewable, explicit binding; the
  gate mechanically (i) requires the analyzed spec's own declaration (closing the
  automatic / target-global leak — AC3) and (ii) proves the declared path resolves
  to a real sealed deterministic fidelity check (closing the fabricated / vacuous
  / unsealed path — AC4). It is **not** the static contract's synthetic
  `source_spec_path` / `spec_id` (which collide in name with the feature-spec
  handle). The gate **cannot** mechanically verify AC↔redline correspondence —
  that is the stochastic judgment ADR-0050 excludes — so a second feature spec
  that **deliberately** declares the binding on a shared target is credited (the
  honest-author residual, AC3b), caught by spec review and sound by construction
  only within the single-redline vellum closure. This is **not** Kill criterion 1
  firing: the ADR itself names "the single-redline-per-target identity … or an
  explicit binding the slice adds" as a sealable handle, and this slice
  implements exactly that — honestly, without claiming a mechanical guarantee the
  gate does not provide.
- **Reading the frontmatter + the `checks.json` keeps the verdict deterministic
  and byte-stable** — both are ordinary files loaded up front; no clock / network
  / randomness enters `decide()`, and a spec with no `fidelity_contract` reads
  byte-identically to pre-slice (AC5).
- **A design target's ACs can be all-residual** — verified against the real
  `oracle_plan classify` in 030-01 (fidelity prose → `residual_judgment`); this
  slice does not change the classifier.

## Decomposition

One vertical slice (Rules axis — the whole change is the verdict logic in
`suitability.py`: a new, bounded evaluability source + its attribution guard,
threaded through the existing rule table, with the skill-surface prose). No
spike: ADR-0050's 4-round frame-critique pinned the mechanism (read the
required-runtime check plan, not `install.json` components; attribute per-spec,
not target-globally; exclude the judge) against the live code, and every mechanic
lands on files suitability already owns or reads.

- **044-01 (Rules)** — the required-policy evaluability credit + its spec-attribution
  guard in `suitability.py`, with the test fence (declared + sealed static
  contract → `suitable`; judge alone, unattributed static check, and no
  deterministic check → refused; non-design specs byte-identical) and the
  SKILL.md / docstring updates.

## Slices

- [044-01 — required-policy-evaluable](slice-01-required-policy-evaluable.md)
