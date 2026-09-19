---
status: DRAFT
skill:
use_cases: []
---

# Spec 030: suitability eval-signal (approved frozen evals satisfy has_signal)

> Realizes [ADR-0036](../../decisions/adr-0036-frozen-evals-satisfy-suitability-signal.md)
> (**Proposed** — the slice's DoR gates on its acceptance). Motivated by a
> cross-repo seam gap (review of vellum + jig + servo, 2026-08-30): a design-led
> target instrumented with an approved, frozen `score_design_fidelity` component
> — vellum's build-to-redline consumers, about to multiply as vellum adds Figma
> as a second design source (its design-source-adapter ADR + figma spec, filed
> 2026-08-30) — is refused entry to the unattended path because
> `has_signal` reads only `tests`/`ci`, so the fully instrumented spec sits at
> `needs_evidence` with a blocking `oracle_signal` item its own oracle already
> satisfies.

## Overview

Teach `/servo:edd-suitability` to credit servo's own strictest evidence
contract: `has_signal` becomes `tests OR ci OR reviewed_frozen_eval`, where the
eval leg requires an eval component that is **installed** (registered in
`install.json`'s `components` by `fidelity_eval.register_manifest`) **and
approved + frozen with reviewed provenance** (its `.servo/<eval>/config.json`
carries `approval_status: "approved"` + `approval_provenance: "reviewed"` +
`approved_content_hash` + non-empty `hashes` — the freeze fields
`validate_freeze` enforces at score time, plus the enforced distinct-approver
provenance design-eval's `freeze --reviewer` records; ADR-0036 frame-critique
revision 2026-08-31). Unfrozen, unapproved, self-approved, provenance-less
(today's content-fidelity / eval-authoring stamps), or unregistered evals never
count; a judged-only signal (no tests, no CI) still
returns `suitable` but carries a standing **non-blocking** advisory
recommending a deterministic counterweight (the ADR-0033 reward-hacking
lesson). One lean slice: the `suitability.py` rule inputs, the advisory, the
doc updates, and the regression fence that today's tests/ci behavior is
byte-identical.

Current state (probed 2026-08-30):

- `has_signal = any(bool(signals.get(k)) for k in _SIGNAL_KEYS)`,
  `_SIGNAL_KEYS = ("tests", "ci")` (`suitability.py:71`, consumed in
  `decide()`/`build_trace()`); signals come from `_load_signals` →
  `<target>/.servo/install.json`'s `signals` object only — the sibling
  `components` list is never read.
- The blocking gap item is `{kind: "oracle_signal", blocking: true}`
  (`_missing_evidence`, `suitability.py:110-116`); `missing_evidence` is
  documented "load-bearing only for `needs_evidence` (empty for
  suitable/unsuitable)" (`decide()` docstring, SKILL.md, 015-02 board note).
- Install registration: `fidelity_eval.register_manifest`
  (`fidelity_eval.py:369`) appends the component name to `components`;
  `deregister_manifest` is symmetric (design_eval.py `uninstall` docstring:
  the manifest never lists a component no longer in `oracle.sh`).
- Freeze facts: `freeze()` stamps `hashes` / `approved_content_hash` /
  `approval_status: "approved"` (`design_eval.py:263-268`);
  `fidelity_eval.validate_freeze` (`fidelity_eval.py:222`) refuses `StaleError`
  → rc 2 at score time unless approved and hash-intact. Provenance: only
  design-eval records `approval_provenance`/`approved_by` (`reviewed` is
  enforced via the 028-03 distinct-reviewer re-enumeration verdict;
  `self_approved` via self-ack); `content_fidelity.py freeze` (`:94-115`) and
  eval-authoring (`eval_authoring.py:1266`) record **no provenance today**, so
  their components cannot credit the leg until they adopt the shared seam
  (ADR-0036 OQ1 resolution).
- Dir↔component mapping is closed: `.servo/design-eval/` → `design_fidelity`
  (`design_eval.py:47`), `.servo/content-fidelity/` → `content_fidelity`
  (`content_fidelity.py:34`), eval-authoring `.servo/<component>/` under its
  own name (`eval_authoring.py:1231`).

Non-goals: no change to `oracle.sh` / `gate.py` / loop behavior or any
score-time contract; no schema bump (`schema_version: 1`, `{kind, detail,
blocking}` shape, and the five-kind taxonomy all stay); no crediting of
spec-oracle overlay components (not registered in `install.json`; circular for
the spec under analysis — ADR-0036 Alternatives); no waiver / model-assist work.

## Assumptions

- The register/deregister symmetry holds, so `components` membership is a
  truthful "installed in oracle.sh" proxy — verified in the authoring CLIs and
  their tests; the slice re-confirms by fixture.
- The alias map (two blessed presets + dir-equals-name) is the complete closed
  set today; ADR-0036's kill criterion owns the future-preset risk.
- Reading per-eval configs keeps the verdict deterministic and byte-stable:
  the new inputs are ordinary JSON files loaded up front (no clock / network /
  randomness enters `decide()`).

## Decomposition

One vertical slice (Rules axis — the verdict logic is the whole change; the
skill surface only needs its prose updated). No spike: ADR-0036 pinned the
manifest facts by direct code probe, and every mechanic lands on files
suitability already owns or reads.

- **030-01 (Rules)** — the eval-signal leg + judged-only advisory in
  `suitability.py`, with the test fence (reviewed-eval-alone → suitable +
  advisory; self-approved/provenance-less/unfrozen/unapproved/unregistered →
  unchanged; tests/ci → byte-identical) and the SKILL.md / docstring updates
  that retire the "empty on suitable" absolute.

## Slices

- [030-01 — eval-component-signal](slice-01-eval-component-signal.md)
