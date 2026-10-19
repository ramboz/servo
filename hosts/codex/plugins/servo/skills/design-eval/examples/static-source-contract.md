# Finite static-contract APP observer

**Status:** 036-03 implementation in progress, not an approved installation or
application-success receipt. ADR-0045 remains Proposed pending owner acceptance.
Exact APP policy and an independent positive control require separate genuine
pre-result review. Never fabricate approval files from these instructions.

This observer compares a finite approved source inventory with a separate
application snapshot. It does not measure pixels, actual font face, dynamic
data truth, backend authenticity, whole-view fidelity or application/Jig DONE.
The ordinary deterministic fraction is a **measurement diagnostic**, never
model/visual quality. No judge calls or model configuration are needed.

## Prerequisites and preparation

Use a scaffolded target, the pinned five Vellum producer helpers and an actual
approved `vellum-confirmed-source/0.2` / `static-css-subset/1` package. Source
authority stays with Vellum; do not relabel it as the old card contract or alter
its facts/normalizers. The present runtime preparation uses macOS `otool` and
requires an existing isolated Playwright runtime/browser; it installs nothing.
Other platforms are not established by this experiment.

Create an independent candidate directory containing APP resources, any real
frozen API bodies, provenance metadata and `candidate.json`. Its exact shape is:

```json
{
  "schema_version": 1,
  "kind": "static_snapshot_candidate",
  "entry": "/panel.html",
  "resources": [
    {"url": "/panel.css", "path": "panel.css", "content_type": "text/css"},
    {"url": "/panel.html", "path": "panel.html", "content_type": "text/html"}
  ],
  "metadata": []
}
```

URLs and metadata are sorted, unique and explicitly closed. Every resource
must actually load; extra/unlisted/external requests refuse. This is read-only
loopback snapshot transport, not arbitrary HTTP/backend attestation. Archive
real backend acquisition provenance and name any unclosed identity gaps rather
than substituting a git label or invented data.

Independently review CSS-only APP bindings: `root`, `document_witnesses` (a
nonempty list of structural selectors) and `elements` (exact source-role to
relative selector mapping). Do not require the expected text/style under test
as an acquisition prerequisite. A known bound-element absence is not a claim
that no visually equivalent element exists elsewhere.

With `PLAYWRIGHT_BROWSERS_PATH` set to the frozen browser directory:

```bash
python3 "$SERVO_ROOT/skills/scaffold-init/scaffold.py" "$TARGET"
"$PY" -I -B "$SERVO_ROOT/skills/design-eval/static_contract.py" prepare \
  --target "$TARGET" --package "$APPROVED_SOURCE" --producer-root "$PRODUCER" \
  --bindings "$BINDINGS" --browser-root "$PLAYWRIGHT_BROWSERS_PATH"
```

`$PY` is the selected existing virtualenv's Python. Preparation copies evaluator
helpers and unchanged approved inputs, freshly enumerates runtime bytes,
browser membership and selected outer Bash/non-OS linkage, then writes a
**pending** `spec/oracle/static/app-policy.json` and ordinary `checks.json`.
An exact-policy review must inspect the resulting hash, inventory, bindings,
APP grammar, units/tolerances, environment, runtime and residuals. Direction
approval is not that record. Changed semantic/helper/runtime bytes require
fresh preparation/review; never rebind old approval to new bytes.

## Build the selected snapshot

Build through the **copied target helper**, whose exact recipe path/hash will
be checked during frozen execution:

```bash
"$PY" -I -B "$TARGET/tools/static/static_snapshot.py" build \
  --source "$TARGET/candidate" --out "$TARGET/builds/baseline"
```

Create a separate delivery copy of `builds/baseline/output` and a reviewed
`candidate-selection.json` naming relative `build` and `delivery` directories.
The source must be canonical, absolute and nonsymlinked inside the target.
The verifier independently inventories selected delivery and browser-loaded
response bytes; HEAD/URL/echoed IDs are not substitutes.

```bash
"$PY" -I -B "$TARGET/tools/static/static_snapshot.py" verify \
  --build "$TARGET/builds/baseline" --delivery "$TARGET/delivery"
```

This is pure snapshot identity, not an APP result.

## Approval, ordinary installation and gate

Only after a genuine independent exact-policy/pre-result record exists:

```bash
"$PY" -I -B "$TARGET/tools/static/static_contract.py" approve \
  --policy "$TARGET/spec/oracle/static/app-policy.json" --review "$ACTUAL_REVIEW"
python3 "$SERVO_ROOT/skills/spec-oracle/oracle_overlay.py" generate \
  "$TARGET" "$TARGET/spec" static
```

Use the existing ordinary `approve` then `install --enable-required` overlay
flow, with shared engine or the usual consistent `--vendor-engine` choice.
Before any evaluation, add the final installed `oracle.sh` to every check's
`evaluator_artifacts`, regenerate, independently review and reapprove that
ordinary plan, then reinstall idempotently. The observer refuses an unsealed
driver, incomplete/optionalized source inventory or a pending/stale APP policy.
Do not execute any discarded intermediate installation.

Invoke the real `skills/quality-gate/gate.py "$TARGET" --json` using the selected
runtime and preserve its published gate/component/output references. There is
one ordinary required command per approved ID. The first acquires one
gate-owned UUID/nonce-bound APP observation; subsequent commands only reuse
those same immutable bytes after identity checks. Required failures veto
overall success even at `THRESHOLD=0`; unknown acquisition refuses.

Exact text includes original whitespace and case. The finite APP family
grammar preserves typed named/generic identity, named case and fallback order;
unsupported grammar refuses. Text paint checks require positive-area witnesses
for non-whitespace range rectangles after each ancestor/frame clip, including
paint containment. Formatting-only whitespace is not an ink prerequisite but
remains in raw DOM text. Partial positive-area text can pass this guard: it is
not OCR, whole-string legibility or occlusion/pixel proof. Unsupported
descendant transforms/paint refuse.
Geometry/presence/background-only roles need no contained text or text-paint
observation. If text itself is required and its observed DOM value is empty,
that literal value needs no ghost ink; the binding still requires a unique
visible nonzero box. Missing visibility/text-paint observation flags are
unknown, never defaults to success or observed absence.
Settlement samples approved required properties and correspondence/visibility
atomically. Unselected counters, pulses and unrequired root height are not
readiness conditions; changing a required property still refuses after the
bounded sixty-frame window.

## Pure current readback and limits

```bash
"$PY" -I -B "$TARGET/tools/static/static_contract.py" verify-current \
  --policy "$TARGET/spec/oracle/static/app-policy.json" --envelope "$PRESERVED_ENVELOPE"
```

Readback checks current source/policy/runtime/helper/output and independently
selected candidate/build/delivery identity, including added browser-runtime
members, but does not launch browser, capture, compare or rescore. Its output
preserves the original producer summary. Existing Generic gate consumers
validate the declared output references through the ordinary pure seam.
Currentness means that selected local snapshot, not a deployed backend or
current upstream branch.

Source approval, static-contract success and full application completion are
different claims. Existing Jig `design_bindings` only admits the old 0.1-pilot
input: this separate 0.2 experiment cannot clear it. Do not modify Jig, relabel
inputs, waive full-app residuals or turn a small controlled PASS into vision/
whole-UI quality. Normal independent postreviews and reconciliation remain
necessary before this slice can close.
