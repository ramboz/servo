---
status: Proposed
dependencies: []
last_verified: 2026-08-30
---

# ADR-0036: Approved frozen eval components satisfy the suitability signal

## Status

Proposed (2026-08-30)

Extends [ADR-0015](adr-0015-edd-suitability-gate.md) (still Accepted; the closed
three-state verdict, fail-closed default, and `missing_evidence` contract are
untouched — only the *input set* of the `has_signal` predicate widens) within
the [ADR-0018](adr-0018-suitability-gates-compile-not-heartbeat.md) scope
(the verdict gates Compile only). On acceptance, append an amendment note to
ADR-0015 the way ADR-0018 did.

## Context

`suitability.py decide()` calls a spec `suitable` only when **both** legs hold:
at least one evaluable AC, **and** a compilable signal —
`has_signal = any(bool(signals.get(k)) for k in _SIGNAL_KEYS)` with
`_SIGNAL_KEYS = ("tests", "ci")` (`suitability.py:71`), read from
`<target>/.servo/install.json`'s `signals` object. Tests and CI are the only
signal sources the gate can see.

Servo, meanwhile, has grown a second family of compilable evidence that this
predicate is blind to: **frozen eval components** under the
[ADR-0005](adr-0005-eval-oracle-component.md)/[ADR-0024](adr-0024-extract-frozen-eval-harness.md)
contract. An authored `score_design_fidelity` (spec 012), `score_content_fidelity`
(spec 020), or eval-authoring `score_<name>` (spec 008) component is pinned,
hashed, human-approved, installed into `oracle.sh`, and registered in the very
manifest suitability already reads — `fidelity_eval.register_manifest`
(`fidelity_eval.py:369`) appends the component to `install.json`'s `components`
list, and `uninstall` deregisters it symmetrically, so the manifest never lists
a component absent from `oracle.sh`. Yet none of that flips either suitability
condition: a **design-led target with no test suite is refused entry to the
unattended path even when it is fully instrumented** — the exact false-refusal
ADR-0015 warned its own gate could produce ("a new refusal surface can block
work a human judges fine").

The refusal is also self-inconsistent with the evidence checklist. The
`missing_evidence` taxonomy already names the gap **`oracle_signal`** — "no test
or CI signal detected … so the oracle has a deterministic gate to evaluate
against" — but an installed, approved, frozen eval component *is* an oracle
signal (`gate.py` scores it with no special-casing), and closing the gap that
way does not close the checklist item. The actionable half of ADR-0015 points at
a remedy the gate refuses to credit.

The gap is imminent, not hypothetical: **vellum** (the sibling design-domain
plugin — measured-facts redline, drift audit, build-to-redline — which composes
`servo:design-eval` for scoring per its own docs) is adding **Figma** as a
second design source (vellum's design-source-adapter ADR and figma design-source
spec, both filed 2026-08-30). Its targets are the canonical case: design-led,
oracle-instrumented through a frozen fidelity eval, and often without a test
suite at the moment the loop should start.

## Decision

**`has_signal` is additionally satisfied by at least one approved, frozen eval
component installed in `oracle.sh`.** The predicate becomes
`tests OR ci OR frozen_eval`, where the eval leg is established from the two
manifests servo already writes — never from parsing `oracle.sh` itself:

1. **Installed** — the component is registered in
   `<target>/.servo/install.json`'s `components` list (written by
   `fidelity_eval.register_manifest` at install; removed symmetrically at
   uninstall). The dir↔component mapping is closed: the two blessed presets are
   fixed constants (`.servo/design-eval/` → `design_fidelity`,
   `design_eval.py:47`; `.servo/content-fidelity/` → `content_fidelity`,
   `content_fidelity.py:34`), and eval-authoring components live at
   `.servo/<component>/` under their own name (`eval_authoring.py:1231`).
2. **Approved + frozen** — the component's own frozen definition
   (`<target>/.servo/<eval>/config.json`) carries
   `approval_status: "approved"` with `approved_content_hash` and a non-empty
   `hashes` map — the exact fields the authoring CLI's `freeze` stamps
   (`design_eval.py:263-268`) and `fidelity_eval.validate_freeze`
   (`fidelity_eval.py:222`) enforces at score time.
3. **Evidence of the gap stays kind `oracle_signal`.** When no signal of any
   kind exists, the blocking `missing_evidence` item remains
   `{kind: "oracle_signal", blocking: true}`; its detail now names the third
   remedy (install an approved, frozen eval component) alongside tests and CI.
   No taxonomy extension, no schema bump.

Two guardrails are part of the decision, not implementation detail:

4. **Freeze + approval is load-bearing — unfrozen or unapproved evals never
   count.** A config with `approval_status` absent, `draft`, or `stale`, or with
   missing freeze hashes, or a frozen config whose component is not registered
   in `components`, contributes nothing to `has_signal`. Indeterminate eval
   evidence (an unreadable or malformed per-eval config) resolves to "no eval
   signal" — fail-closed per ADR-0015, never an optimistic `suitable` and never
   a new env-error path (absence of eval evidence is an ordinary analysis fact,
   not an environment failure). Suitability reads the *recorded approval facts*;
   it does not re-hash the frozen artifacts — staleness enforcement stays at
   score time, where `validate_freeze` refuses rc=2 (`env_error`), so an
   approved-then-edited eval can never yield a false pass downstream: the loop
   halts on the env error instead of scoring a vacuous green.
5. **A judged-only signal earns a standing, non-blocking advisory.** When the
   *only* satisfied signal source is a frozen eval (no tests, no CI — the judged
   eval is the sole gate), the verdict is still `suitable`, but the artifact
   carries a **non-blocking** `missing_evidence` advisory recommending at least
   one deterministic component. A judged eval under freeze is honest evidence,
   but it is the gameable kind — the ADR-0033 field report is the cautionary
   case (a structurally-lopsided policy scored a nine-divergence UI at
   "essentially passing") — and servo's posture has always been to pair
   non-deterministic evaluation with deterministic checks rather than let a
   single judge carry the oracle (ADR-0005: the deterministic families remain
   the source-of-truth shape; the eval is one component in a composite). The
   advisory is the reward-hacking counterweight, kept advisory (a nudge, not a
   gate) so the decision does not reintroduce the false refusal it exists to
   remove. The advisory reuses the existing non-blocking `tests`/`ci` kinds
   (whose details already frame the "deterministic gate" remedy); a dedicated
   `deterministic_component` kind would require a deliberate schema bump and is
   not warranted for a non-blocking nudge.

This relaxes one 015-02 documentation clause: `missing_evidence` was "load-bearing
only for `needs_evidence` (empty for suitable/unsuitable)". Under this decision a
`suitable` verdict **may carry non-blocking advisory items**; blocking items
still never appear on `suitable`, and `unsuitable` still carries an empty list.
The artifact shape (`{kind, detail, blocking}`), the `kind` taxonomy, the closed
verdict enum, and `schema_version: 1` are all unchanged.

The decision is **domain-agnostic by construction**: any component under the
ADR-0005/ADR-0024 freeze contract counts identically — design fidelity, content
fidelity, and every future frozen eval kind. No skill is named in the predicate.

## Consequences

**Positive.**

- A fully instrumented design-led target (vellum's build-to-redline consumers
  being the imminent class) enters Compile honestly instead of being refused for
  lacking evidence it does not need.
- The `oracle_signal` checklist item becomes truthful: every remedy it names
  actually closes it.
- The freeze/approval ceremony (ADR-0005, ADR-0033's reviewer machinery) gains a
  consumer beyond score time — an *unapproved* eval now visibly buys nothing at
  the gate, which is one more reason to finish the ceremony rather than skip it.

**Negative.**

- A judged-only signal is weaker evidence than tests: the loop optimizes against
  a judge that a lopsided policy can game (the ADR-0033 failure class). Freeze +
  approval + the standing advisory raise the cost and mark the risk; they do not
  eliminate it. Named residual, and the kill criteria below harden it if it
  bites.
- Suitability's input surface widens from one manifest object (`signals`) to the
  `components` list plus per-eval configs — more files whose shape the
  deterministic, byte-stable rule table depends on.

**Neutral.**

- No change to `oracle.sh`, `gate.py`, the loop, or any score-time contract —
  the decision only widens what the upstream gate can see.
- ADR-0015's verdict contract and ADR-0018's Compile-only application are
  unchanged; the rule table stays ordered, first-match, and pure (the eval facts
  are loaded with the other inputs, not mid-decision).

## Alternatives considered

- **Status quo — require tests/CI always.** Rejected: falsely gates design-led
  work that is instrumented under servo's own strictest evidence contract, and
  leaves the `oracle_signal` checklist naming a remedy the gate refuses to
  credit.
- **Count any installed oracle component, including unfrozen ones.** Rejected as
  gameable: an unfrozen judge is exactly what ADR-0005 forbids to gate — a
  runner could author a vacuous eval mid-loop and mint its own signal. The
  freeze + human-approval ceremony is the point.
- **A design-eval-specific carve-out.** Rejected: servo is domain-agnostic —
  content-fidelity and future frozen eval kinds must benefit identically, and a
  skill-named predicate would be a second thing to update per eval kind.
- **Parse `oracle.sh` for `# SEED:` eval blocks instead of reading manifests.**
  Rejected: the manifests are the recorded install contract, kept truthful by
  the register/deregister symmetry; teaching suitability to parse bash would add
  a second parser for facts `install.json` already states.
- **Also count approved spec-oracle overlay components** (deterministic,
  approved, `--enforce-freeze`d). Out of scope: they are not registered in
  `install.json` (`oracle_overlay.py` splices `oracle.sh` only), and an overlay
  is typically compiled *from the spec under analysis* — crediting it as the
  project-level signal for that same spec is circular. Revisit if a real target
  carries an overlay from a *different* spec as its only signal.

## Assumptions

- The register/deregister symmetry holds — `install.json`'s `components` never
  names an eval component absent from `oracle.sh`. Verified in
  `design_eval.py`/`content_fidelity.py` (symmetric `uninstall`) and their
  tests; re-confirm at implementation.
- The dir↔component alias set is closed today (two blessed presets + the
  dir-equals-name eval-authoring convention). A future preset must extend the
  alias map — a named maintenance point, mitigated by the kill criterion below.
- Consumers of the eval leg have run `/servo:scaffold-init` (so both
  `install.json` and its `signals` object exist) — already a suitability
  precondition (`manifest_missing` env-error), not a new requirement.

## Kill criteria

- If a real target games the judged-only path into a meaningless green — a false
  pass the standing advisory failed to prevent — the advisory hardens into a
  gate: a judged-only signal then yields `needs_evidence` with a blocking
  deterministic-counterweight item, and this ADR is amended to record the flip.
- If the alias map proves error-prone (a third preset ships without extending
  it, silently invisible to the gate), move the component name *into* the frozen
  config as a deliberate `fidelity_eval` schema addition and key on that
  instead.

## Open questions

1. **Should approval provenance grade the signal?** ADR-0033 distinguishes
   `reviewed` from `self_approved` freezes. v1 counts both (`approval_status:
   "approved"` is the contract; a self-approved eval is already loudly marked at
   score time) — but a stricter posture could credit only `reviewed` evals, or
   attach the advisory to `self_approved` ones regardless of tests/CI.
2. **Verdict freshness across uninstalls** — spec 015's existing open question
   (does a verdict expire when signals drift?) gets a new instance: an eval
   uninstalled after a `suitable` verdict. Same answer as today: re-analysis is
   the contract; nothing here changes it.

## Verification

To be established by spec 030. At minimum: a frozen + approved + registered eval
component alone yields `suitable` with the non-blocking advisory; an unfrozen,
unapproved, or unregistered eval leaves today's verdict unchanged; targets with
tests/CI signals produce byte-identical artifacts to today; the artifact stays
`schema_version: 1`; and `--explain` surfaces which signal source decided.

## References

- **[ADR-0015](adr-0015-edd-suitability-gate.md)** — the verdict contract this
  extends (amend on acceptance, per its ADR-0018 precedent).
- **[ADR-0018](adr-0018-suitability-gates-compile-not-heartbeat.md)** — the
  Compile-only application; unchanged here.
- **[ADR-0005](adr-0005-eval-oracle-component.md)** — the frozen-eval contract
  that makes an eval component creditable evidence at all.
- **[ADR-0024](adr-0024-extract-frozen-eval-harness.md)** — the shared harness
  whose install/manifest-registration splice this keys on.
- **[ADR-0033](adr-0033-design-eval-structured-scoring-policy.md)** — the field
  report behind the judged-only advisory (a gameable judge is a real, observed
  failure class).
- [Spec 015 — edd-suitability](../specs/015-edd-suitability/spec.md) — the
  analyzer; [Spec 030 — suitability-eval-signal](../specs/030-suitability-eval-signal/spec.md)
  — the implementing spec.
- Specs [012](../specs/012-design-eval/spec.md) /
  [020](../specs/020-content-fidelity-eval/spec.md) /
  [008](../specs/008-eval-authoring/spec.md) — the frozen-eval producers whose
  components become creditable signals.
- **Cross-repo companions (2026-08-30):** vellum's design-source-adapter ADR and
  figma design-source spec (the imminent design-led consumer class); jig's
  composed-pilot inbox entry (the jig × vellum × servo autonomous-build pilot
  that would exercise this seam end to end).
