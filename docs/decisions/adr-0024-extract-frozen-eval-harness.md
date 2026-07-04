---
status: Accepted
date: 2026-07-03
deciders: ramboz
supersedes:
superseded-by:
last_verified: 2026-07-03
---

# ADR-0024: Extract the frozen-eval harness into a shared module for the second eval kind

## Status

Accepted (2026-07-03)

Frame-critique pass recorded (pass, round 3 — see
[docs/decisions/reviews/adr-0024-frame-critique.md](reviews/adr-0024-frame-critique.md)).
Implemented by [spec 020](../specs/020-content-fidelity-eval/spec.md).

## Context

[ADR-0005](adr-0005-eval-oracle-component.md) fixed the *contract* a
non-deterministic eval must satisfy to enter servo's oracle — frozen + hashed
definition, n-sample lower-bound scoring, a plateau noise floor, `env_error`
never a silent zero, ledgered evidence — written generically, with no
modality assumption baked in beyond "the dataset is a hashed artifact."

[ADR-0009](adr-0009-design-fidelity-eval-recipe.md) shipped
[spec 012 (design-eval)](../specs/012-design-eval/spec.md) as that contract's
*first* concrete consumer: a UI-vs-mockup fidelity eval, judged by a vision
model. Its Alternatives-considered section explicitly weighed and rejected
building a general eval-authoring framework up front, deferring on
[ADR-0003](adr-0003-fresh-subagent-roster.md)'s rule-of-three grounds:

> extract the shared `validate_freeze` / `aggregate_lower_bound` /
> `definition_hash` primitives (currently in `design-eval/score.py`) only
> when a second eval kind demands them.

[GitHub issue #16](https://github.com/ramboz/servo/issues/16) is that second
eval kind: **content-fidelity** — does generated *text* match an intended
target (tone, register, reading level, style-guide adherence) beyond what a
linter can check? Same shape as design fidelity — non-deterministic, needs
n-sampling, wants to gate a loop — but the reference is a rubric/spec instead
of a screenshot and the judge is a text model instead of a vision model.

**Grounding (direct read of `skills/design-eval/`, 2026-07-03).** Of
`score.py`'s ~380 lines and `design_eval.py`'s ~220 lines, the following are
already modality-agnostic — no image-specific logic anywhere in them:

- `score.py`: `EnvError`/`StaleError` (lines 43-48), `sha256_text`/
  `sha256_file` (55-60), `definition_hash` (63-86), `artifact_hashes`
  (89-98), `validate_freeze` (101-121), `aggregate_lower_bound` (128-139),
  `_ledger` (344-360), `_extract_json` (290-294), and `_post_with_retry`
  (216-236, a generic HTTP-retry wrapper with no image awareness).
- `design_eval.py`: `init`/`freeze`/`install`/`uninstall`/
  `_register_manifest`/`_deregister_manifest` (66-184) — the oracle.sh
  SEED-splice + `COMPONENTS` entry + `.servo/install.json` registration is
  already parameterized by a `COMPONENT` name constant, not hardcoded to
  vision.

Only these are genuinely vision-specific: `capture_app` (146-160, Playwright
screenshot via `capture.mjs`), the `judge`/`_judge_api`/`_judge_cli` body
construction (the base64 image content blocks + "compare these two images"
prompt wording), and `design_eval.py`'s `capture_refs` (82-86, renders a
mockup to PNG via Playwright) and `_FRAGMENT` (the `score_design_fidelity`
function name + string).

## Decision

Extract the modality-agnostic surface above into a shared module —
`skills/_common/fidelity_eval.py` — mirroring the `skills/_common/` package
jig itself already uses for cross-skill helpers (`workflow.py` imports
`_common.atomic_io`, `_common.parsing`, etc.). `design-eval` becomes the
first *consumer* of that module instead of owning the primitives; a new
sibling skill, `content-fidelity`, becomes the second.

- **What moves (mechanism, unchanged behavior):** freeze validation, the
  definition/artifact hash functions (generalized to take the field list and
  case-array key as parameters rather than hardcoding design-eval's
  `screens`/`viewport` shape), the n-sample lower-bound aggregator, the
  ledger writer, JSON-from-model-reply extraction, the HTTP-retry wrapper,
  and the oracle.sh install/uninstall/manifest-registration splice
  (parameterized by component name + fragment body, not hardcoded to
  `score_design_fidelity`).
- **What stays forked (policy + genuinely different mechanism):** capturing
  the artifact under judgment (Playwright screenshot vs. reading/generating
  text output — content-fidelity's spec picks its own mechanism), and
  building the judge's model-specific payload (image content blocks + vision
  prompt vs. text-only prompt). Each skill's `SKILL.md` also keeps its own
  prerequisites section (Playwright + a vision-capable model vs. a rubric +
  any text-capable model) — folding both into one skill's instructions would
  make each harder to follow for a mechanical extraction that saves no
  meaningful code.
- **Two sibling skills, not one skill with a mode flag.** Mirrors the
  existing `spec-oracle`/`scaffold-init` pattern and ADR-0009's own framing of
  design-eval as "a dedicated, first-class skill … a sibling … not a sub-mode."
  `content-fidelity` gets its own `SKILL.md`, authoring CLI, and runtime,
  built on the shared module exactly as `design-eval`'s will be after this
  extraction.
- **design-eval's public contract does not change.** Its `config.json` shape,
  `score_design_fidelity` component name, and CLI subcommands are unchanged;
  this is a pure internal refactor for that skill. [Spec 020](../specs/020-content-fidelity-eval/spec.md)
  implements this ADR.

**Named risk: the extraction must survive design-eval's copy-based deployment,
not just reorganize source.** Unlike spec-oracle's `checks.py`, which is
*referenced* by an absolute plugin-install path and never copied
([ADR-0023](adr-0023-colocate-durable-spec-oracle-artifacts.md) AC3),
design-eval's `score.py`/`capture.mjs` are `shutil.copyfile`d into an
arbitrary target's `.servo/design-eval/` at install time, and the installed
`oracle.sh` fragment invokes them by a target-relative path with no servo
plugin install reachable at score time. Extracting shared code into
`skills/_common/fidelity_eval.py` does not remove that copy step — it adds a
second file (`fidelity_eval.py`) that must *also* reach the target, by
whatever mechanism the implementing slice picks (a same-directory sibling
copy + an existence-probe import, per 020-01's Assumption A1, is the current
plan; it is explicitly flagged there as untested until implemented). If that
mechanism does not resolve cleanly in practice, the fallback is a checked-in
vendored duplicate of `fidelity_eval.py` inside each skill's source
directory. **Correction (caught by a second frame-critique round,
2026-07-03): this fallback is weaker than first described, and weaker than
its cited precedent.** ADR-0023's `--vendor-engine` does not "keep a vendored
`checks.py` in sync" on an ongoing basis — verified by direct read of
`oracle_overlay.py`: a vendored copy is hashed into `approved_artifacts`
**once, at freeze time**, and `--enforce-freeze` only checks that the
vendored file still matches *that frozen hash* (tamper/drift detection
against the snapshot). It never re-compares against the live, possibly-fixed
canonical source. A vendored `fidelity_eval.py` would inherit the identical
property: it does not close the staleness gap named in Open Questions below,
it **relocates** it, from "an installed target's copy drifts from the
current skill source" to "a checked-in vendored copy drifts from the current
shared module." Both are real, open risks this ADR does not resolve — it
records that a fallback exists, not that the fallback is risk-free. This
ADR's core value proposition (one edited canonical file instead of N
hand-duplicated ones, regardless of which reach-the-target mechanism wins)
still holds; only the *mechanism* that makes the boundary real
at runtime is still open, and 020-01 is where it gets settled.

## Consequences

### Positive
- Fulfills ADR-0009's own anticipated trigger instead of leaving the
  duplication to compound past a second consumer.
- `content-fidelity` inherits the freeze/hash/lower-bound/ledger/install
  machinery — and its ADR-0005 honesty guarantees — for free; it only
  authors the parts that are genuinely new (text-artifact gathering, a
  text-judge prompt).
- A future third eval kind (e.g. an audio or structured-data fidelity eval)
  has a real module to build on rather than a second copy-paste.

### Negative
- The extraction does not eliminate design-eval's copy-based deployment; it
  adds a second copied file whose runtime resolution is a new, unprecedented
  pattern for this codebase (named above), not a proven one — the risk 020-01
  must retire before this ADR's savings are real, not just theoretical.
- Once installed, a target's copy of `fidelity_eval.py` (like today's
  `score.py`/`capture.mjs`) has no re-sync or staleness signal: a later fix
  to the shared module in `skills/_common/` does not reach an
  already-initialized target until it re-runs `init`/`install`. This is a
  **pre-existing property of design-eval's copy model**, not newly introduced
  by this extraction — but the extraction does widen its blast radius from
  one skill to every consumer of the shared module, which is worth naming
  even though fixing it is out of this ADR's scope (see Open questions).
- One more indirection: design-eval's `score.py` now imports from
  `skills/_common/fidelity_eval.py` instead of being fully self-contained;
  a reader has to look in two files.
- The generalized `definition_hash`/`artifact_hashes` signatures take
  explicit field lists instead of a single hardcoded shape — marginally more
  ceremony at each call site in exchange for reuse.

### Neutral
- `skills/_common/` is new to servo (jig's own convention, not previously
  vendored here); this ADR is also the first servo consumer of that layout.
- The exact shared-module function signatures are the implementing spec's
  call, not fixed here.

## Open questions

- **Staleness of a copied shared module (surfaced by frame-critique,
  2026-07-03).** Neither this ADR nor spec 020 adds a re-sync or
  version-staleness check for a target's copied `fidelity_eval.py` (or
  `score.py`/`capture.mjs`, which already have this property today). Out of
  scope here — it pre-dates this extraction and fixing it is a separable
  concern (e.g. a hash-comment + `--reinstall` prompt, mirroring the
  freeze/stale machinery this ADR's own contract already has for the
  *definition*, applied instead to the *engine*). Logged to
  `docs/refinement-todo.md`; revisit if a real drift incident occurs.

## Alternatives considered

- **Keep duplicating (hand-roll `content-fidelity`'s own freeze/aggregate/
  ledger).** Rejected: this is precisely the "re-solder the wire every time"
  scar ADR-0009 named for hand-rolled evals, now hitting the harness itself,
  not just the per-project config.
- **A general eval-authoring framework, `content-fidelity` as a plugin of
  it.** Rejected for the same reason ADR-0009 rejected it the first time:
  over-built relative to two concrete consumers; extract only what both
  actually share (the grounding above enumerates it precisely).
- **One skill (`design-eval`) with a `--kind visual|text` flag.** Rejected:
  the authoring workflow (capture vs. generate; vision vs. text judge
  prerequisites) differs enough that one `SKILL.md` would have to fork
  almost every instruction, for no code savings the shared module doesn't
  already capture.
- **Fold this into an amendment on ADR-0009 instead of a new ADR.** Rejected
  per the amendment-vs-new-ADR convention this project follows from jig's
  spec-workflow (records get a short dated pointer forward, decision-content
  changes get a new ADR): ADR-0009 is a closed, Accepted record, and this is
  new decision-content (a module boundary + a second skill), not a status
  update. ADR-0009 gets a short dated pointer forward to this ADR; its own
  text is not rewritten.

## Verification

No slice implements this yet; obligations for [spec 020](../specs/020-content-fidelity-eval/spec.md):

- design-eval's existing test suite (`skills/design-eval/test_design_eval.py`)
  passes unmodified in intent after the extraction — same assertions, now
  exercising the shared module through design-eval's thin wrapper.
- `content-fidelity`'s freeze/stale/env_error/lower-bound behavior is
  covered by its own tests exercising the *shared* module, not a re-copy of
  design-eval's tests.
- A change to design-eval's rubric/model/n/δ/threshold/screens still refuses
  as stale; a change to content-fidelity's rubric/model/n/δ/threshold/cases
  does too — both via the one shared `validate_freeze`.

## References

- [ADR-0005](adr-0005-eval-oracle-component.md) — the frozen-eval contract
  this extraction still implements, unchanged.
- [ADR-0009](adr-0009-design-fidelity-eval-recipe.md) — design-eval as the
  first consumer; its Alternatives section named this ADR's trigger.
- [ADR-0003](adr-0003-fresh-subagent-roster.md) — the rule-of-three
  reasoning ADR-0009 deferred extraction under.
- [Spec 020 — content-fidelity-eval](../specs/020-content-fidelity-eval/spec.md)
  — implements this ADR.
- [GitHub issue #16](https://github.com/ramboz/servo/issues/16) — the
  originating ask.
