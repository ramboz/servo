# Finite static-contract APP protocol (proposed)

This consumer measures explicit static declarations on an independent APP.
It does not measure visual quality, actual font face, dynamic data correctness
or full application completion. Source approval means source integrity only.

## Effective policy

The canonical JSON policy has `schema_version: 1`,
`kind: static_source_contract_app_policy`, `version: static-source-contract-app/1`
and explicit `target`, `producer`, `source`, `bindings`, `normalizers`,
`constraints`, `environment`, `selection`, `output_root`, `runtime`,
`evaluator_files`, `residuals` and `approval`.

- `source` names the approved package directory, raw input hash, target revision
  and producer request hash. `producer` pins the five current source helpers.
  Identity validation calls `inspect()` only, never source `verify()`.
- `bindings` contains CSS-only `root`, independent `document_witnesses` selectors,
  and exact per-source-role `elements` selectors relative to that root.
  No expected text/style is an acquisition guard. Child absence means only
  approved-bound-element absence; root/state/ambiguous/unconfirmed gaps refuse.
- `constraints` preserves every source policy row and adds its explicit APP
  normalizer. Source inventory, comparisons, units and tolerance cannot change.
- `normalizers` pins the finite property map and APP family grammar below.
  `environment` exactly preserves the approved source environment.
- `selection` names a mutable candidate/delivery selector, not design policy.
  Each selected candidate needs a fresh run and byte closure, not source
  reapproval. `output_root` has one literal `{run_id}` segment.
- `runtime` includes interpreter/prefix/platform/package origins and versions,
  browser root, fresh complete file manifest and non-OS native linkage pins.
  The outer `#!/usr/bin/env bash` driver uses the explicitly selected, hashed
  Bash plus its closed non-OS link dependencies; the APP browser manifest is
  not presented as shell closure. Current browser directory membership,
  including symlinks, is separately frozen and checked without browser launch.
  Evaluator/helper files are separately byte-pinned. No model runtime/calls.
- `approval` starts pending. An independently produced exact-policy review
  names distinct author/reviewer and the current policy hash before approval.
  No preparer-generated approval or engineering-goahead substitution.

Policy identity is SHA-256 of ASCII `servo-static-app-policy-v1`, newline, then
canonical JSON excluding only `approval`. Canonical JSON uses sorted keys,
compact separators, ASCII escaping, finite numbers and unchanged semantic-array
order. Byte hashes use `sha256:` followed by 64 lowercase hex digits.

## APP family grammar

`css-computed-family-list/1` is a finite computed-declaration grammar, not a CSS
parser. A comma separates tokens; comma inside quotes explicitly refuses.
Quoted tokens are ASCII `[A-Za-z][A-Za-z0-9 -]*`, single or double delimited,
without escapes. Their content/case/internal spaces remain literal; delimiter
choice is not semantic. Quoted generic names remain **named**.

Unquoted tokens consist of one or more ASCII identifier words:
`(?:[A-Za-z_]|-[A-Za-z_])[A-Za-z0-9_-]*`, separated by spaces/tabs canonicalized
to one space. Named case/order remain significant. A single unquoted supported
generic is typed generic and lowercased, retaining C0 generic-case behavior.
The exact supported set is `serif`, `sans-serif`, `monospace`, `cursive`,
`fantasy`, `system-ui`, `ui-serif`, `ui-sans-serif`, `ui-monospace`,
`ui-rounded`, `math`, `fangsong`. Generic words cannot be embedded in a
multiword named token. Unquoted `inherit`, `initial`, `unset`, `revert`,
`revert-layer`, reserved `default` and unsupported legacy `emoji` refuse;
quoted versions remain named. Escapes, non-ASCII, control characters other than
separator tabs, comments, functions, empty tokens and unknown grammar refuse.

Basis: MDN [font-family](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/font-family)
and [custom-ident](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/custom-ident).
Compatibility vectors preserve C0 positive typed representations, including
generic case, named-vs-generic, order, named case and quoted internal spacing.
C0's rejected unquoted named families remain rejected by its unchanged v0
source normalizer; APP/1 explicitly extends observation syntax only.
Other APP values use the pinned source primitives: exact DOM text, opaque RGBA,
CSS scalars and explicit inclusive tolerances. No whitespace/text case folding,
face inference, zero-tolerance default or unknown-property fallback.

## Snapshot and observation closure

A `static_snapshot_candidate` manifest explicitly lists entry URL,
sorted unique resource URL/path/content-type rows and metadata paths.
The complete input inventory is exactly that manifest, metadata and resources.
A copy-only `static_snapshot_build` binds source inventory, recipe hash,
output inventory/configuration and separate domain hashes
`servo-static-snapshot-input-v1` / `servo-static-snapshot-output-v1`.
Selected current delivery is independently inventoried; a git label is not
substituted for byte identity.

Read-only loopback serves sealed bodies only. The browser must complete every
declared GET response with exact body/content-type/status, no redirects or
service workers, and no extra resource, websocket, popup or download.
Response bodies are retained as hashed output artifacts. Both real API routes
must complete before Dashboard settlement; first-render-only closure is not
sufficient. Fonts-ready and four equal animation-frame snapshots of the
**approved required raw properties plus correspondence/visibility** give
bounded settlement, not whole-view determinism. Each DOM snapshot reads the
bound roles atomically. Unselected descendants, counters, pulses and root
height (unless required) do not enter the stability key. Changing a required
value still refuses after the bounded sixty-frame window; stable wrong values
remain comparisons, not acquisition prerequisites.

APP visibility uses bounded raw DOM/style/text observations plus ancestor
overflow and paint-containment intersection. Unsupported paint effects refuse.
Each non-whitespace text node's nonzero range rectangles must retain
positive-area intersection after all relevant ancestor/frame clips. Partial
positive-area text is accepted; this is not OCR, full-string legibility,
occlusion, pixel or actual-face proof. Formatting-only whitespace nodes do not
need an ink witness, but original `textContent` (including that whitespace)
is preserved verbatim for exact comparison. Nested text is checked through its
own ancestors; unsupported descendant transforms refuse.
Backend acquisition metadata is provenance, not backend authenticity.
Currentness means the independently selected local snapshot candidate/build/
delivery, not a deployed backend or current upstream branch.

## Gate-owned output and pure readback

Each ordinary command declares `refusal_exit_codes: [2]` and
`result_artifact: {root: "spec/oracle/static/runs/{run_id}/observed",
manifest: "evidence.json", schema_version: 1, kind: "static_source_contract_evidence"}`.
One required command per approved ID returns 0/1/2 for pass/fail/unknown.
Duplicate/partial/extra inventories refuse. Known contradictions survive
acquisition refusal; an unavailable run is not an earlier successful result.

The output has schema1/kind above, run ID/acquisition nonce, source identities,
policy hash/required IDs, evaluator/runtime identity, build/current-delivery
closure, raw observation references, all interpreted constraints, summary,
measurement-only diagnostic and visible residuals. Its `artifacts` is the exact
sorted closed output inventory excluding only the manifest itself.
Exclusive gate-owned acquisition claim/receipt binds UUID, nonce, policy and
manifest bytes. Reuse is restricted to the same invocation and current closure.

The installed overall gate owns the component result and final verdict.
Ordinary spec-oracle's pass fraction is not a model/visual score. Required
failures veto even at `THRESHOLD=0`. The actual generic consumer calls
`required_runtime.validate_output_references(check, evidence, run_id, base)`
through `gate_consumer`; no producer-specific dispatch is added.
`verify-current` only checks source/policy/runtime/helper/output inventories,
nonce/run/driver and current build/delivery identities, returning the preserved
producer verdict. It must not launch browser, call `compare()` or source
`verify()`, or recompute scores.

Existing Jig 0.1 input allowlist does not clear this separate 0.2 component.
No relabel, Jig edit, full-view waiver or downstream-DONE claim is permitted.
