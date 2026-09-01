---
status: Accepted
dependencies: []
last_verified: 2026-09-01
---

# ADR-0036: Approved frozen eval components satisfy the suitability signal

## Status

Accepted (2026-09-01)

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
hashed, approved, installed into `oracle.sh`, and registered in the very
manifest suitability already reads — `fidelity_eval.register_manifest`
(`fidelity_eval.py:369`) appends the component to `install.json`'s `components`
list, and `uninstall` deregisters it symmetrically, so the manifest never lists
a component absent from `oracle.sh`. Yet none of that flips either suitability
condition: a **design-led target with no test suite is refused entry to the
unattended path even when it is fully instrumented** — the exact false-refusal
ADR-0015 warned its own gate could produce ("a new refusal surface can block
work a human judges fine").

The `oracle_signal` checklist item names the gap but not this remedy. Its
detail asks for a test command or CI workflow "so the oracle has a
**deterministic** gate to evaluate against" (`suitability.py:112-114`) — wording
that is internally consistent with ADR-0015's gameability posture: a judged eval
is *not* deterministic, and the original gate deliberately declined to credit
non-deterministic evidence. This ADR widens that remedy set **on purpose**, with
the reviewed-freeze requirement and the judged-only advisory below as the
counterweights; the case for widening rests on the false refusal of instrumented
design-led targets, not on any inconsistency in the current checklist.
*(Frame-critique revision 2026-08-31: an earlier draft called the refusal
"self-inconsistent with the evidence checklist"; two independent reviewers
flagged that as a misreading of the detail text, and the claim is withdrawn.)*

The gap is imminent, not hypothetical: **vellum** (the sibling design-domain
plugin — measured-facts redline, drift audit, build-to-redline — which composes
`servo:design-eval` for scoring per its own docs) is adding **Figma** as a
second design source (vellum's design-source-adapter ADR and figma design-source
spec, both filed 2026-08-30). Its targets are the canonical case: design-led,
oracle-instrumented through a frozen fidelity eval, and often without a test
suite at the moment the loop should start.

## Decision

**`has_signal` is additionally satisfied by at least one *reviewed*, frozen eval
component installed in `oracle.sh`.** The predicate becomes
`tests OR ci OR reviewed_frozen_eval`, where the eval leg is established from
the two manifests servo already writes — never from parsing `oracle.sh` itself:

1. **Installed** — the component is registered in
   `<target>/.servo/install.json`'s `components` list (written by
   `fidelity_eval.register_manifest` at install; removed symmetrically at
   uninstall). The dir↔component mapping is closed: the two blessed presets are
   fixed constants (`.servo/design-eval/` → `design_fidelity`,
   `design_eval.py:47`; `.servo/content-fidelity/` → `content_fidelity`,
   `content_fidelity.py:34`), and eval-authoring components live at
   `.servo/<component>/` under their own name (`eval_authoring.py:1231`).
2. **Approved + frozen, with reviewed provenance** — the component's own frozen
   definition (`<target>/.servo/<eval>/config.json`) carries
   `approval_status: "approved"` with `approved_content_hash`, a non-empty
   `hashes` map (the fields `fidelity_eval.validate_freeze`,
   `fidelity_eval.py:222`, enforces at score time), **and
   `approval_provenance: "reviewed"`** — the ADR-0033 §4 *prevention* path,
   which design-eval enforces rather than asserts: `freeze --reviewer` refuses
   without a recorded independent re-enumeration verdict by a reviewer distinct
   from the author (`design_eval.py:243-249`, 028-03). A `self_approved`
   freeze, or a frozen config that records **no provenance at all** — which is
   what `content_fidelity.py freeze` (`content_fidelity.py:94-115`) and
   eval-authoring's freeze (`eval_authoring.py:1266`) stamp today — is
   auditability-only evidence (ADR-0033: it "does not carry the prevention
   property") and contributes nothing to `has_signal`. Those two producers
   become creditable only once their freeze paths adopt the same
   distinct-approver seam; until then the gate stays fail-closed on them.
3. **Evidence of the gap stays kind `oracle_signal`.** When no signal of any
   kind exists, the blocking `missing_evidence` item remains
   `{kind: "oracle_signal", blocking: true}`; its detail now names the third
   remedy (install a *reviewed*, frozen eval component) alongside tests and CI.
   No taxonomy extension, no schema bump.

Two guardrails are part of the decision, not implementation detail:

4. **Freeze + reviewed approval is load-bearing — unfrozen, unapproved, or
   self-approved evals never count.** A config with `approval_status` absent,
   `draft`, or `stale`, with missing freeze hashes, with `approval_provenance`
   absent or `self_approved`, or a frozen config whose component is not
   registered in `components`, contributes nothing to `has_signal`.
   Indeterminate eval evidence (an unreadable or malformed per-eval config)
   resolves to "no eval signal" — fail-closed per ADR-0015, never an optimistic
   `suitable` and never a new env-error path (absence of eval evidence is an
   ordinary analysis fact, not an environment failure). Suitability reads the
   *recorded approval facts*; it does not re-hash the frozen artifacts —
   staleness enforcement stays at score time, where `validate_freeze` refuses
   rc=2 (`env_error`), so an approved-then-edited eval can never yield a false
   pass downstream: the loop halts on the env error instead of scoring a
   vacuous green. Provenance is likewise a recorded fact, not a cryptographic
   proof — and the barrier it adds is **normative, not structural**. The
   re-enumeration record backing `reviewed` names its reviewer and author as
   self-reported strings with no identity binding
   (`design_eval.py:141-166` — "distinctness is proven by the record
   itself", i.e. by two strings differing), so a motivated unattended agent
   can still mint `reviewed` on CLI rails by fabricating a verdict record, or
   by leadingly prompting a nominal "reviewer" — the reviewer-trust question
   ADR-0033 OQ6 explicitly leaves open, and this ADR does not resolve it.
   What the requirement removes is the **deception-free** mint that killed
   the first draft: there, `approved` was stamped by the sanctioned happy
   path with nothing misrepresented; here, minting requires affirmatively
   fabricating a review that never happened — a falsified record left on
   disk, the same auditability-not-prevention grade ADR-0033 assigns its own
   detached-loop case ("a rigged score still passes"). The claim, stated
   honestly: no *honest* path mints a signal; every *dishonest* one leaves a
   falsifiable artifact; and the kill criterion below flips the advisory to a
   gate if a real target crosses that line.
5. **A judged-only signal earns a standing, non-blocking advisory.** When the
   *only* satisfied signal source is a reviewed frozen eval (no tests, no CI —
   the judged eval is the sole gate), the verdict is still `suitable`, but the artifact
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
- Reviewed-only crediting narrows the immediate beneficiary set to design-eval
  components — the one producer with the enforced distinct-approver seam, and
  the producer behind the motivating vellum class, so the imminent case loses
  nothing. Content-fidelity and eval-authoring targets stay refused until their
  freeze paths record provenance — a deliberate cost: the gate widens only as
  fast as the approval ceremony actually hardens.

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
  freeze + distinct-approver ceremony is the point.
- **Count any `approval_status: "approved"` freeze, deferring provenance (this
  ADR's own first draft).** Rejected on frame critique (2026-08-31, two
  independent reviewers converging on the same hole): for two of the three
  producers, `freeze` stamps `approved` with **no distinct-approver seam and no
  provenance recorded at all** (`content_fidelity.py:94-115`,
  `eval_authoring.py:1266`), and design-eval's `self_approved` path is a
  self-ack flag (`SERVO_DESIGN_EVAL_ACK_EXCLUSIONS=1`) — so an unattended agent
  on a testless target could author → freeze → install → register an eval and
  mint its own `suitable` end-to-end: the exact move the unfrozen-eval
  rejection above claims the ceremony prevents, and the "meaningless green"
  ADR-0015 exists to refuse. Accepted ADR-0033 already rules a self-approved
  freeze auditability-only ("in a detached loop with [no reviewer], a rigged
  score still passes") — and the rigged eval in its own field report *was*
  frozen and hashed. The advisory is no counterweight there: it is
  non-blocking, so its gate-time effect on an unattended loop is zero.
  (Reviewed-only crediting does not make minting *impossible* — guardrail 4
  names the fabrication residual, which requires falsifying a re-enumeration
  record — but it removes this sanctioned, deception-free path, which is the
  property the first draft lacked.)
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
  tests; re-confirm at implementation. **Known limit (frame critique,
  direction corrected in round 2):** the symmetry is verified against the
  install/uninstall pair only. `scaffold-init --force` re-renders `oracle.sh`
  *and* rewrites `install.json` wholesale (`scaffold.py:543-551`), resetting
  `components` to the freshly detected set — a prior eval registration is
  **erased together with** its splice, not orphaned. The post-`--force`
  failure mode is therefore fail-closed: a still-frozen eval silently loses
  its signal and the target drops back to `needs_evidence` (a false refusal,
  recoverable by re-installing the component) — never a phantom credit, since
  the surviving per-eval config alone does not satisfy the installed
  condition. Spec 030's verification pins that direction; re-analysis after a
  re-scaffold is OQ2's existing contract.
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

1. **Should approval provenance grade the signal?** — **Decided in this
   revision (2026-08-31, forced by frame critique): yes. Only
   `approval_provenance: "reviewed"` credits.** The first draft counted both
   `reviewed` and `self_approved` and deferred the distinction here; two
   independent reviewers showed that made the eval leg self-mintable (see the
   rejected alternative above). What remains is scope, not grading: extending
   the enforced distinct-approver seam to `content_fidelity` and
   eval-authoring freezes so their components can become creditable (a
   `fidelity_eval`-shared provenance stamp; whether spec 030 carries it or a
   sibling slice does is a planning call, not a blocker — the gate is correct
   either way, fail-closed on provenance-less configs).
2. **Verdict freshness across uninstalls** — spec 015's existing open question
   (does a verdict expire when signals drift?) gets a new instance: an eval
   uninstalled after a `suitable` verdict. Same answer as today: re-analysis is
   the contract; nothing here changes it.

## Verification

To be established by spec 030. At minimum: a reviewed + frozen + registered eval
component alone yields `suitable` with the non-blocking advisory; a
`self_approved` freeze and a frozen config with no recorded provenance (today's
`content_fidelity` / eval-authoring stamps) each leave today's verdict
unchanged, as do unfrozen, unapproved, or unregistered evals; targets with
tests/CI signals produce byte-identical artifacts to today; the artifact stays
`schema_version: 1`; `--explain` surfaces which signal source decided; and the
`scaffold-init --force` case is fenced in the fail-closed direction (the
wholesale `install.json` rewrite erases the registration with the splice, so
the eval leg goes dark and the verdict drops to `needs_evidence` — no phantom
credit from the surviving per-eval config alone).

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
