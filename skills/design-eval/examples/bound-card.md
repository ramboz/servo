# Bound card evidence pilot (036-01)

This opt-in pilot measures one self-contained candidate against the independently
approved Vellum `vellum-design-input/0.1-pilot` normal/open card packages.
It is not general design extraction, a production acceptance oracle, an image
metric engine, or evidence of Jig DONE.

**Sealed 6cc759e checkpoint:** the
[immutable proof receipt](../../../docs/specs/036-deterministic-design-evidence/implementation-receipt.md)
preserves baseline quality0.97/all28requiredpass/overall0, preselected
misalignment quality0.5278427304671842/all28requiredpass/overall1, and declared
title20.01px quality0.9675/26pass2fail/overall1, all against unchanged0.8.
Each case has eight real native `claude-opus-5` replies. Earlier failed OAuth,
live and diagnostic epochs are retained, not relabeled as final-source proof.
This proves the bounded fixture, not production/general accuracy or Jig DONE.
The subsequent
[visibility correction](../../../docs/specs/036-deterministic-design-evidence/visibility-correction-receipt.md)
is a distinct source epoch; earlier live proof is not automatically approval
of changed evaluator bytes. Whole-slice acceptance remains blocked pending its
affected proof and full reviews.

## Inputs and supported boundary

Use the exact approved C1 `release-r3` from Vellum revision
`55dd18007cd5664be17c1e7c4666fd1f00dd93d6`. `card_evidence.py` pins exact
package/helper bytes and uses Vellum's verifier and normalizers, rather than
reimplementing its input contract. Historical releases and preview packages
are not substitutes. The independent candidate remains mutable; preparation
witness HTML/PNGs are not implementation goals.

The candidate has exactly `index.html` and `candidate.json`. The latter declares
schema1, entry `index.html`, empty `dependencies` and `assets`. HTML/CSS/JS are
self-contained and inline. Additional local inputs, resource attributes, CSS
resource URLs, symlinks and escapes refuse. During acquisition, the controlled
read-only loopback server serves sealed bytes; requests to any other resource,
WebSockets, service workers, redirects, additional pages and byte mismatches
cannot establish a passing observation. This is not arbitrary HTTP provenance.

Use the explicitly selected Python/Playwright/browser/Claude runtime. The
reviewed manifest pins the virtualenv prefix/configuration, Python distribution
including stdlib/framework, selected package origins, complete browser tree,
selected Claude/Node/bash files and non-OS linkage of the Python native
extensions and selected command entrypoints; the OS is
version-bound. A move or runtime update requires fresh preparation and approval,
not a silent fallback. This macOS pilot refuses unsupported relative native
linkage and executable virtualenv/user startup customization. Homebrew's
base-framework `sitecustomize.py` is allowed only inside that pinned framework.
The actual pilot used Python3.14.0, Playwright1.64.0 and
Chromium156.0.8078.4 at800x600/deviceScale1.

## Prepare, independently review, freeze, install

`SERVO_ROOT` is the selected package root (Copilot: its `.github` directory).
`PYTHON`, `BROWSERS`, `CLAUDE`, `VELLUM_HELPERS`, `C1` and `CANDIDATE` name the
actual local reviewed runtime and read-only input paths, not example metadata.
Create `TARGET` and scaffold it first:

```sh
python3 "$SERVO_ROOT/skills/scaffold-init/scaffold.py" "$TARGET"
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" "$PYTHON" -B \
  "$SERVO_ROOT/skills/design-eval/card_install.py" prepare \
  --target "$TARGET" --producer-root "$VELLUM_HELPERS" --references "$C1" \
  --candidate "$CANDIDATE" --python "$PYTHON" --browser-root "$BROWSERS" \
  --claude "$CLAUDE" --model opus
```

Model choice is explicit and user-controlled. For this known non-Claude parent,
the owner selected current Opus via Claude CLI. A compatible, discoverable Claude
parent can suggest its model, not silently inherit across providers. Unknown
identity does not justify inventing a default or model availability.
The requested `opus` alias is not an immutable provider pin. Native stdout,
returned `modelUsage` and exact CLI/runtime identity are retained; exposed
incompatible model identity refuses. Absent resolution metadata is labeled
unavailable. CLI decoding is explicitly `native-default`, not pretend
temperature/max-token enforcement. Changing an approved judge requires review
and refreeze.

An independent reviewer must actually inspect both source PNGs, re-enumerate
the visual catalogue, and review the exact card policy/hash from
`spec/oracle/card/preparation.json`. Record the genuine card-policy verdict as
JSON with `verdict: pass`, distinct `author`/`reviewer`, and `policy_hash`.
Do not manufacture a reviewer identity or use a synthetic test verdict.

```sh
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" "$PYTHON" -B \
  "$SERVO_ROOT/skills/design-eval/card_install.py" approve-policy \
  --target "$TARGET" --review-record "$ACTUAL_REVIEW_JSON"
python3 "$SERVO_ROOT/skills/design-eval/design_eval.py" record-reenumeration \
  "$TARGET" --author "$AUTHOR" --reviewer "$REVIEWER" --verdict pass
python3 "$SERVO_ROOT/skills/design-eval/design_eval.py" freeze \
  "$TARGET" --author "$AUTHOR" --reviewer "$REVIEWER"
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" "$PYTHON" -B \
  "$SERVO_ROOT/skills/design-eval/card_install.py" generate --target "$TARGET"
# Review checks.json, oracle.sh.fragment, helpers, source/runtime manifests.
python3 "$SERVO_ROOT/skills/spec-oracle/oracle_overlay.py" approve \
  "$TARGET" "$TARGET/spec" card
# Stage the exact final installed oracle.sh, including the real quality wrapper.
# This consumes the first approval, then marks the driver-bound plan draft.
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" "$PYTHON" -B \
  "$SERVO_ROOT/skills/design-eval/card_install.py" seal-driver --target "$TARGET"
# Independently inspect final oracle.sh + its evaluator_artifacts pin in checks.json.
python3 "$SERVO_ROOT/skills/spec-oracle/oracle_overlay.py" approve \
  "$TARGET" "$TARGET/spec" card
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" "$PYTHON" -B \
  "$SERVO_ROOT/skills/design-eval/card_install.py" install --target "$TARGET"
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" \
  python3 "$SERVO_ROOT/skills/quality-gate/gate.py" "$TARGET" --json --timeout 2700
```

Use `--vendor-engine` on generate/seal-driver/install for the ordinary clone-portable
engine path. Installation consumes approved bytes without generating or granting
approval. Draft/unsealed/changed driver bytes refuse; re-generation invalidates
the driver seal and requires the review sequence again. The runtime checks the
actually read shell snapshot against the declared exact input hash, not just the
file found at the end. The installed wrapper selects an absent, run-owned Python
cache prefix and disables bytecode writes, so pre-existing caches do not replace
reviewed helper source. Required removal/uninstall follows
[required-policy.md](../../spec-oracle/examples/required-policy.md); plain
uninstall cannot silently waive required membership.

The card policy and reviewed design-eval definition are separate freezes.
Live quality uses exactly the verified current run's normal/open PNGs, four
samples each, lower bounds with k1 and threshold0.8. Browser-returned PNG hashes
are checked before sealing per-state actual/reference judge inputs. Their byte
and file identities are rechecked around every invocation, across states and
before quality publication. Claude runs in safe/restricted Read-only mode with
normal subscription authentication, not `--bare`; unrelated credential tokens
are removed from its environment and unselected provider/auth modes refuse.
These are trusted-local drift checks, not malicious-writer prevention or full
host/provider attestation. Every attempted judge call,
including an authentication failure, reserves a persistent allowance slot
before invocation. Keep the owner-level consumed count across new checkpoints;
creating a new directory does not grant another eight calls. The owner has
explicitly authorized necessary further pilot invocations, without repeated
per-run prompts, not unbounded/adaptive candidate search or policy tuning.
Each prepared batch documents `--purpose`, copies the complete prior claim
history with `--prior-attempts`, and sets `--calibration-limit` to the inherited
count plus exactly8. Four judgments per state remain fixed. Record every
outcome/model usage; a new epoch is never relabelled as an old passing run.

## Candidate and output identities

Build new mutable candidates using the installed `tools/card/card_bundle.py`
into a fresh directory. Independently select the current delivery through
`candidate-selection.json`, containing target-relative `build` and `delivery`
paths. The delivery is enumerated and hashed independently; matching HEAD,
URL or a self-echoed ID is insufficient. Source/config/build/output changes
require fresh acquisition; target/comparison/evaluator changes require
reviewed reapproval.

The result namespaces remain distinct:

| Record | Authority |
|---|---|
| `design_evidence` schema1 | Raw DOM/style/state facts, 28 approved constraint rows, capture/source/policy/evaluator/build/current-delivery references; component only |
| `command_result_artifacts` schema1 | Generic same-run complete output-manifest/capture byte closure in ordinary raw evidence |
| `required_component_result` schema1 | Once-invoked ordinary component's raw evidence and interpreted required results |
| `gate_result` schema2 | Preserved `.servo/gate-runs/<UUID>/gate.json`; overall completion authority, including quality |

The observer waits for fonts and four identical scoped animation-frame snapshots.
Band geometry uses inclusive1CSSpx tolerance without pre-rounding; declared
size/weight use0; strings, colours and typed ordered family tokens are exact.
Quoted `"sans-serif"` remains named, not generic. A missing/hidden required title
fails dependent assertions without inventing values or turning known UI absence
into unrelated browser failure. Missing/ambiguous/unsupported acquisition refuses.
Rectangular ancestor overflow clips reject fully clipped text. Partial clipping
with surviving positive-area text rectangles is not full invisibility; this is
not glyph/OCR, arbitrary mask/transform or general occlusion certification.
Quality unavailability does not erase conclusive required facts; it still
prevents overall completion.
Current-invocation reuse also checks a gate-owned exclusive acquisition claim
and independently preserved exact-envelope receipt. Raw observations carry
their gate run, capture ID and acquisition nonce. A relabelled or preseeded
result tree cannot substitute for that owned acquisition.

`validate_output_references(check, evidence, run_id, base)` in the installed
required runtime is pure run/path/contract/complete-inventory/byte validation,
including failure/refusal records. It executes no evaluator or grade.
The combined 035-02 integration calls this same helper during readback.
Repeated report reads validate immutable output without claiming live
acceptance, executing commands or re-scoring.

For independent current-delivery readback without recapture/re-scoring:

```sh
PLAYWRIGHT_BROWSERS_PATH="$BROWSERS" "$PYTHON" -B "$TARGET/tools/card/card_evidence.py" \
  verify-current --policy "$TARGET/spec/oracle/card/card-policy.json" \
  --envelope "$PRESERVED_DESIGN_ENVELOPE"
```

The explicit `diagnostic-negative-control` preparation mode is only for
high-quality/zero-threshold veto controls. Its0.99 is synthetic diagnostic
quality, never live fidelity; it is unavailable for an all-matching candidate,
so it cannot establish a positive completion run. Actual baseline observations
and evaluated failures remain distinguishable from this quality control.
036-02 raster metrics and completed Jig119 attestation remain outside this pilot.
