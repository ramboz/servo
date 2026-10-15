# Installed required assertions (opt-in)

Use the **current package's** helper paths, not another global Servo install.
`SERVO_ROOT` below denotes that package root (Copilot: its `.github` directory).
Start with an ordinary scaffolded project and its scalar components:

```sh
python3 "$SERVO_ROOT/skills/scaffold-init/scaffold.py" "$TARGET"
python3 "$SERVO_ROOT/skills/spec-oracle/oracle_plan.py" \
  "$TARGET" "$TARGET/spec/spec.md" --spec-id demo
```

The planner captures `source_spec_path` / `source_hash`. Review/edit
`$TARGET/spec/oracle/demo/checks.json`, preserving that provenance. For an
existing command check, an example reviewed entry is:

```json
{
  "id": "assertion",
  "family": "command",
  "required": true,
  "command": ["python3", "-c", "from pathlib import Path; raise SystemExit(0 if Path('subject').exists() else 1)"],
  "evaluator_artifacts": []
}
```

Add top-level `"required_policy": {"schema_version": 1, "enabled": true}`.
An absent `subject` is an **observed contradiction**, not a failed capture.
A timeout or unavailable executable is unavailable evidence, never pass.
`required` must be a boolean. IDs must be nonempty and unique across both
checks and residuals. Only existing `command` and `generated_artifact_command`
families supply required executable evidence in this slice; a required residual
or unsupported family stays unknown.

A generated-artifact variant uses the existing primitive, not a new evaluator:

```json
{
  "id": "generated",
  "family": "generated_artifact_command",
  "required": true,
  "build_command": ["python3", "-c", "from pathlib import Path; Path('built').touch()"],
  "command": ["python3", "-c", "from pathlib import Path; raise SystemExit(not Path('built').exists())"],
  "evaluator_artifacts": []
}
```

Both argv lists and their executable bytes are frozen. For assertion scripts
and local helpers, declare the complete reviewed target-relative closed-file
list in `evaluator_artifacts`, including build scripts. Empty means an explicitly
reviewed inline/binary-only assertion, **not** automatic import discovery.
Mutable subjects/generated outputs are observations, not evaluator artifacts.
Shell/dynamic executable wrappers and undeclared script entry points refuse.
Servo does not authenticate the reviewer's closure declaration or discover a
general transitive environment.

Required bare executables need absolute PATH entries; relative executable
paths are resolved against a command check's actual `working_directory`.
Python accepts reviewed inline `-c` code or an explicitly declared script
entrypoint (including extensionless scripts), optionally preceded by the
simple flags `-I`, `-S`, `-B`, `-E`, `-s`, `-u`. Module execution, option
separators and other interpreter shapes refuse rather than guessing their
artifact closure. Other interpreter CLIs are not supported by this bounded
slice. Generated checks run in fresh temporary directories, so their script
entrypoints/executable paths must be absolute and declared/pinned; relative or
dynamically generated assertion scripts refuse. Subject inputs still remain
mutable observations.

## Review, approve, install

```sh
python3 "$SERVO_ROOT/skills/spec-oracle/oracle_overlay.py" \
  generate "$TARGET" "$TARGET/spec" demo
# Review checks.json, generated oracle.sh.fragment, assertion helpers and runtime.
python3 "$SERVO_ROOT/skills/spec-oracle/oracle_overlay.py" \
  approve "$TARGET" "$TARGET/spec" demo
python3 "$SERVO_ROOT/skills/spec-oracle/oracle_overlay.py" \
  install "$TARGET" "$TARGET/spec" demo --enable-required --weight 0
python3 "$SERVO_ROOT/skills/quality-gate/gate.py" "$TARGET" --json
```

For clone-portable engines use `--vendor-engine` on **both** generate and
install. It includes `checks.py` and `required_runtime.py`. Generation and
installation do not approve; install consumes reviewed bytes without
regenerating them. Shared-engine upgrades change identity and require review
and reapproval. Local identity paths are target-relative; external/shared
paths remain absolute. Executable resolution must still match on the adopter.

Only the recognized canonical driver can be upgraded. Existing SEED functions
and static COMPONENTS entries survive. Unsupported driver edits/dynamic arrays
refuse before any writes. Runtime `THRESHOLD=0` and zero weights affect quality,
never required membership. Non-finite quality values refuse.

To remove membership, edit to `enabled: false` and remove/set false **all**
required flags, generate, review, approve, then explicitly install again with
`--enable-required` (same engine mode). Only that component's membership is
removed; its new scalar fragment replaces the old one. A plain reinstall or
uninstall cannot remove still-required membership. Subsequent uninstall is
ordinary/idempotent. The project stays enabled/v2 even with zero required
members. Re-scaffold, including `--force`, refuses rather than erasing opt-in.
Repair inconsistent policy/manifest/runtime installations through reviewed
installation, not by deleting one file to get a v1 pass.

## Carrier and identity contract

Servo identity JSON: UTF-8, sorted keys, compact separators, ASCII escapes,
`allow_nan=False`, explicit typed `schema_version` / `kind`. Duplicate keys
refuse. `sha256:` file references hash **exact published bytes**, not parsed
JSON, timestamps, path labels, or Vellum input serialization.
Schema versions, exit codes and counts are integer domains; booleans are not
numbers. Quality scores/weights/thresholds must be finite JSON numbers, not
numeric strings. Oversized values, aliased types and unbound scalar result
references refuse with exit 2 rather than becoming successful proof.

| Artifact | Domain / fields |
|---|---|
| `spec/oracle/demo/checks.json` | Existing plan plus `required_policy`, boolean flags, `approved_content_hash`, `approved_required_binding` |
| `.servo/required-policy.json` | schema **1**, kind `required_policy`; complete `components` bindings, installed runtime hash and canonical driver-prefix hash |
| `.servo/install.json.required_policy` | `{schema_version: 1, hash: "sha256:…"}` of the complete canonical installed policy |
| `spec/oracle/demo/runs/<UUID>/result.json` | schema **1**, kind `required_component_result`; `run_id`, `component`, `policy_hash`, `config_hash`, `evaluator_hash`, `source_identity`, diagnostic `score`, raw `evidence`, interpreted `required` |
| `spec/oracle/demo/ledger.jsonl` | Existing raw evidence rows, now also stamped with that invocation's `run_id` |
| `.servo/gate-runs/<UUID>/invocation.json` / `oracle-claim.json` | Exclusive invocation ownership; reused caller context refuses |
| `.servo/gate-runs/<UUID>/oracle-result.json` | Overall proposed schema **2** / `gate_result`, from one invocation of each component |
| `.servo/gate-runs/<UUID>/gate.json` | Validated preserved **overall completion authority**; same payload returned by `gate.py --json` |

Approval binds component, checks path, complete required ID set, frozen config,
source provenance `{path, hash}`, evaluator executable/artifact closure, engine,
fragment and required runtime/driver bytes. Config identity sorts ACs by ID and
normalizes statement whitespace; all executable parameters, controls and flags
remain in its domain. Explicit disabled policies also require reapproval.
Source identity is the planner's approved provenance, **not** current living
source bytes or a claim about the evaluated build. Lifecycle-only source edits
do not invalidate runtime freeze (ADR-0022).

Overall gate fields (all emitted, including null diagnostics on refusal):

```json
{
  "schema_version": 2,
  "kind": "gate_result",
  "run_id": "<UUID>",
  "status": "fail",
  "exit_code": 1,
  "reason": "required_constraints_failed",
  "composite": 1.0,
  "threshold": 0.5,
  "threshold_override": {"source": "oracle_default", "value": "0.5"},
  "policy_hash": "sha256:<complete-installed-policy>",
  "missing": [],
  "components": [
    {"component": "baseline", "weight": 1.0, "score": 1.0, "exit_code": 0, "result": null},
    {"component": "spec_oracle_demo", "weight": 0.0, "score": 0.0, "exit_code": 0,
     "result": {"path": "<target>/spec/oracle/demo/runs/<UUID>/result.json",
                "hash": "sha256:<exact-component-bytes>"}}
  ],
  "required": {
    "status": "fail", "ids": ["assertion"], "passed": [], "failed": ["assertion"], "unknown": [],
    "counts": {"pass": 0, "fail": 1, "unknown": 0},
    "items": [{"id": "assertion", "component": "spec_oracle_demo", "status": "fail",
               "reason": "command exited with code 1 (expected 0): …", "evidence_index": 0}]
  }
}
```

Component `required` has the same shape without the item's `component` field;
`evidence_index` indexes its own immutable raw `evidence` array. Component refs
are run-bound/digest-bound, not latest-ledger queries. `threshold_override.source`
is `environment` when THRESHOLD was supplied; `value` preserves its original
string. Effective weights/scores are in `components`. The gate verifies the
quality arithmetic independently; it does not rerun/re-score assertions.

| Required / quality | rc / status / reason |
|---|---|
| pass / pass | 0 / pass / null |
| fail / pass | 1 / fail / required_constraints_failed |
| pass / fail | 1 / fail / quality_below_threshold |
| fail / fail | 1 / fail / required_and_quality_failed |
| unknown / either | 2 / env_error / required_evidence_unavailable |

Unknown takes precedence and retains available failures. A passing component
does **not** authorize completion when the overall quality gate fails.
Gate schema2, required-component schema1, future design-envelope schema1,
design-eval-policy schema2 and Vellum0.1-pilot are separate namespaces.
No policy keeps the v1 payload, stdout, `--score-only` and 0/1/2 behavior.
An identifiable required install with a missing gate-side
`required_runtime.py` refuses with v2 unknown diagnostics **before** invoking
the oracle. That pre-invocation refusal has `run_id: null` and no preserved
invocation; it cannot attest completion. Repair the installed gate package
and rerun to obtain bound evidence. A false-only `required: false` annotation
without policy remains an ordinary scalar overlay.
Consumer/autonomy propagation is a separate slice; do not treat this as
035-02/036 support.

Executable source and generated-host examples, including generated-artifact,
concurrency, relocation and mutation controls:
`uvx pytest -q skills/spec-oracle/test_required_gate.py`.
