# Reusable finite static-source evidence

This is a product workflow, not a source approval, policy approval or
application-success receipt. The boundary is specified by
[spec 037](../../../docs/specs/037-reusable-design-evidence/spec.md) and the
[ADR-0046](../../../docs/decisions/adr-0046-component-agnostic-static-evidence.md).
The accepted boundary decision does not approve any installation or result.

The actual six clean producer helpers are pinned against the reviewed source
cut. Preparation refuses changed helper bytes, not by aliasing old approvals.
The commands below are not an application approval or success claim. Never
guess hashes or reuse an old approval for changed helper bytes.

## Authority and runtime prerequisites

Supply a genuinely approved `vellum-confirmed-source/0.2` package with profile
`static-css-subset/1`, produced by the exact clean successor helper closure:
`confirmed_source.py`, `capture_confirmed.py`, `design_input.py`,
`redline_intake.py`, `resolve_redline.py`, `validate_redline.py`.
Original-source freshness remains live: changed source bytes or tool bytes
require a new source approval epoch, not a renamed approval or archive waiver.
The package's approved tooling inventory must exactly equal the six current
pins. A source inspector being able to read another tooling epoch does not
authorize that packet for this product path; preparation and current validation
refuse it without changing its original approval.

The evaluator copies precisely four neutral helpers: `static_contract.py`,
`static_snapshot.py`, `evidence_io.py`, `evidence_runtime.py`. Its approved
`evaluator_files` inventory includes those four, the six producer helpers and
runtime manifest JSON files. There is no component implementation, provider
registry, model judge or app dependency policy in this closure.

Use an existing isolated virtualenv with Playwright and its frozen Chromium
browser directory. Preparation enumerates the selected Python, module origins,
Bash, browser membership and non-OS native links; it installs nothing.
Native-link closure currently requires macOS `otool` and rejects unsupported
relative native linkage. No broader platform/build-framework support is claimed.
Use source-only `-I -B` Python; helpers direct caches to temporary locations.
Do not install into, mutate or repoint an existing approved runtime.

## Prepare the policy

Here `$SERVO_ROOT` is the installed package root, `$PY` is the selected
virtualenv Python and `PLAYWRIGHT_BROWSERS_PATH` names its browser directory.
Set PATH to the selected Bash before preparation and keep it identical when
running the gate.

Independently review a bindings JSON containing `root`, a nonempty list of
structural `document_witnesses`, and `elements` mapping exactly the approved
source roles to relative CSS selectors. Bindings must not test the expected
text/style as a condition of acquiring the observation.

```bash
python3 "$SERVO_ROOT/skills/scaffold-init/scaffold.py" "$TARGET"
"$PY" -I -B "$SERVO_ROOT/skills/design-eval/static_contract.py" prepare \
  --target "$TARGET" --package "$APPROVED_SOURCE" --producer-root "$PRODUCER" \
  --bindings "$BINDINGS" --browser-root "$PLAYWRIGHT_BROWSERS_PATH"
```

Preparation copies unchanged approved input and pinned helpers into the target,
then writes **pending** `spec/oracle/static/app-policy.json` and `checks.json`.
Generation is not approval. The independent pre-result policy review must cover
the exact policy hash, role/ID inventory, binding independence, explicit units,
normalizers/comparisons/tolerances, environment, runtime and residuals.

Preparation refuses occupied or symlinked `spec/static.md`,
`spec/oracle/static`, `tools/static` and `design-input` destinations before
writing. Producer/source, bindings and runtime preflight also precede output
creation; generated specification files use exclusive creation, never overwrite.
An I/O interruption or concurrent source change during publication can still
leave unapproved partial output. Use a fresh scaffolded target in that case;
do not delete or overwrite project-owned content to force a retry.

## Build an independent static delivery

Create a candidate directory inside the target, with an exact `candidate.json`:

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

Resource URLs and metadata are sorted and unique. All files must be declared;
every resource must actually load. Extra, external or unlisted requests refuse.
This is loopback snapshot transport, not arbitrary HTTP/backend attestation.
Real frozen API bodies may be declared resources, but their authenticity is a
separate residual. Do not replace source authority with copied candidate facts.

Build through the **copied** helper, whose exact recipe path/hash is checked:

```bash
mkdir -p "$TARGET/builds"
"$PY" -I -B "$TARGET/tools/static/static_snapshot.py" build \
  --source "$TARGET/candidate" --out "$TARGET/builds/baseline"
```

Make a separate delivery copy of `builds/baseline/output`. Write
`candidate-selection.json` as:

```json
{"build":"builds/baseline","delivery":"delivery"}
```

```bash
"$PY" -I -B "$TARGET/tools/static/static_snapshot.py" verify \
  --build "$TARGET/builds/baseline" --delivery "$TARGET/delivery"
```

The source must be canonical, absolute and nonsymlinked inside the target.
Snapshot verification independently inventories source, build and current
delivery. It is byte identity, not an observation or visual score.

## Independently approve and ordinarily install

Only after a genuine independent exact-policy review record exists:

```bash
"$PY" -I -B "$TARGET/tools/static/static_contract.py" approve \
  --policy "$TARGET/spec/oracle/static/app-policy.json" --review "$ACTUAL_REVIEW"
python3 "$SERVO_ROOT/skills/spec-oracle/oracle_overlay.py" generate \
  "$TARGET" "$TARGET/spec" static
python3 "$SERVO_ROOT/skills/spec-oracle/oracle_overlay.py" approve \
  "$TARGET" "$TARGET/spec" static
python3 "$SERVO_ROOT/skills/spec-oracle/oracle_overlay.py" install \
  "$TARGET" "$TARGET/spec" static --enable-required
```

Use shared engine or the ordinary consistent `--vendor-engine` choice. Before
evaluation, add the final installed `oracle.sh` to every check's
`evaluator_artifacts`, regenerate, independently review and reapprove the plan,
then reinstall idempotently. Do not execute discarded intermediate installs.
The observer refuses pending/stale policy, optionalized/incomplete source IDs,
or an unsealed final driver.

Invoke `gate.py "$TARGET" --json` in the same selected runtime/environment.
Native consumers use `gate_consumer.request -> gate.py -> accept/read`; never
precreate invocation directories or copy previous native claims. One command
per approved ID shares one immutable UUID/nonce-bound acquisition.
Required FAIL yields exit 1 even with perfect quality or `THRESHOLD=0`;
UNKNOWN yields exit 2 and retains known failures. Only the **overall gate**
verdict can pass, never a component alone.

## Preserved readback and limits

The public versions stay `static-source-contract-app/1`,
`static_snapshot_candidate` schema 1 and
`static_source_contract_evidence` schema 1. Evidence is published under
`spec/oracle/static/runs/{run_id}/observed/evidence.json`, with raw observations,
capture and a complete file/hash inventory. Preserve native gate/component
references as well as this envelope.

```bash
"$PY" -I -B "$TARGET/tools/static/static_contract.py" verify-current \
  --policy "$TARGET/spec/oracle/static/app-policy.json" --envelope "$PRESERVED_ENVELOPE"
```

Current-identity readback checks live source, policy, evaluator, runtime/browser
membership, selected candidate/build/current-delivery and output identity. It
does not acquire, evaluate, compare or rescore and preserves the original summary.
It retains bounded local OS/interpreter metadata queries and fixed
`git -C <original-root> rev-parse HEAD` source freshness checks; it is read-only,
not subprocess-free. Generic native `gate_consumer.read` is strictly
subprocess-free/hash-read-only and verifies declared output references but does not
independently claim the snapshot is still selected; use `verify-current` for
that additional currentness claim.

Text is literal, including whitespace/case. Family-list comparison preserves
typed generic/named identity, named case and fallback order. The bounded
visibility profile checks effective visibility, applicable clipping boxes and
positive-area witnesses for non-whitespace text fragments. Empty required text
needs no ghost ink but still requires a unique visible nonzero binding.
Unsupported paint/geometry stays UNKNOWN. Settlement uses four equal atomic
required-fact/correspondence frames within a bounded sixty-frame window; stable
failures remain beside unstable IDs. These are not OCR, occlusion, legibility,
whole-string visibility or universal CSS-rendering guarantees.

No whole-view pixels, actual font face, interaction, backend authenticity,
deployed build or lifecycle completion claim follows. New source-helper bytes
need new test-only source and policy approvals in tests, and genuine approvals
for real applications. Synthetic test approvals never attest an application.
