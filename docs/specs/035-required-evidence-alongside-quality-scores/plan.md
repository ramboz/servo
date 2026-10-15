# Plan: required evidence alongside quality scores

035-01 implementation pickup, 2026-10-15. ADR-0044 is Accepted and owner
authority is recorded in `owner-acceptance.md`. Only 035-01 is selected;
035-02 and spec036 remain DRAFT and are not implemented here.

## Readiness

The clean pickup HEAD and remote selected parent
`servo-required-design-evidence` both equal
`a383c8761afaab010f133207876d1c6f01ff2b2e`; proposal PR40 is OPEN and targets
main. The implementation PR targets that selected parent, never main. No merge
is authorized. Use installed Jig helpers for the ordinary state transitions,
with a fresh independent frame/readiness review of the encoding below before
READY_FOR_IMPLEMENTATION. A cleared framing-evidence check alone is not that
readiness review.

035-01 starts standalone with existing command/generated-artifact fixtures;
it does not wait for Vellum/Jig DONE or a new observer. The accepted peer input
namespaces are not reused as Servo serializers. Required driver/result race
proof is implementation work, not a circular readiness prerequisite.

## 035-01: installed required gate

### Concrete encoding and approval closure

Extend existing `checks.json` with optional boolean `required: true` on check
or residual entries, and an explicit top-level
`required_policy: {"schema_version": 1, "enabled": true}` opt-in. No policy
means existing behavior, even when old diagnostic checks fail. A required flag
without enabled approved policy is invalid, not a quiet downgrade. Unknown
policy versions/types, non-boolean flags and duplicate/empty IDs refuse.
The enabled empty required set is valid and still runs quality.

Keep the current AC-content canonicalization (sort by stable ID, normalize
statement whitespace). For enabled policy, include the complete new policy
object and required flags in `approved_content_hash`. A disabled overlay uses
`required_policy: {"schema_version": 1, "enabled": false}` and removes or sets
false every `required` flag; true flags with false/absent policy refuse. Both
enabled and explicitly disabled policy objects remain in the extended hash
domain and require explicit reapproval. Hash all executable
check parameters, controls, normalizations/tolerances/exclusions encoded in
those entries; don't invent a new comparison language. Approval also pins the
component ID, source identity, shared or vendored evaluator bytes and generated
fragment/required-driver runtime bytes. `source_identity` is the approved
source provenance pair `{path, hash}` captured by the existing planner and
checked at approval, NOT current living-document bytes or evaluated-build
identity. Runtime keeps ADR-0022's parsed-AC freeze behavior: lifecycle-only
source edits are allowed and don't assert new provenance. Record these as a separate
`approved_required_binding` on the existing plan. Legacy approval/hash behavior
is unchanged when the extension is absent.

Use ordinary `generate -> review -> approve -> install` operations.
`generate`/`install` do not approve. Required installation is explicitly
requested with `install --enable-required`, consumes the already-approved
binding, and assembles the installed project policy from approved component
entries. Keep that assembly in `.servo/required-policy.json`, with its digest
and version pinned in `.servo/install.json.required_policy`. Each entry closes
component ID, target-relative (or existing supported absolute) checks path,
approved content hash, required ID set, evaluator path/hash, evaluator-artifact
closure, fragment hash, required-runtime path/hash and source provenance pair.
The full canonical `approved_required_binding` is included in each installed
entry, so these pins all contribute to project policy identity.
Project policy identity covers the complete set of these entries. Neither a
runtime env var nor a zero component weight clears membership. Removing,
adding or weakening membership requires an explicitly reapproved overlay and
installation; uninstall refuses a still-required component. An explicitly
disabled/reapproved overlay can remove its entry, leaving an enabled empty
project policy rather than silently reverting the project to v1. Installation
of a disabled/reapproved overlay uses the same explicit `--enable-required`
operation, verifies its new approval, replaces its existing scoring fragment
and removes only that overlay's required entry. A plain reinstall without the
explicit operation preserves/refuses the existing opt-in rather than
downgrading it. Still-required uninstall refuses before any writes; uninstall
after the explicit disabled install is ordinary idempotent removal.

Default/forced re-scaffold of an enabled project preserves its approved policy,
driver and required components or refuses before writing; this slice chooses
refusal, with guidance to revise/reapprove policy through the overlay flow.
Missing/invalid `.servo/required-policy.json`, missing/mismatched manifest pin,
or a required-driver marker with no manifest policy is an inconsistent
installation and refuses. Once enabled, even a valid empty project policy
stays v2; neither file deletion nor `--force` scaffolding silently restores v1.

### Bounded executable assertion closure

Each required `command`/`generated_artifact_command` entry declares
`evaluator_artifacts: [<target-relative file>, ...]` (explicit empty list for
an inline argv assertion or reviewed binary-only command). The explicit list
is mandatory for required command entries, not inferred by searching imports.
Approval resolves and pins the command executable's exact bytes, every
declared assertion script/helper artifact and the spec-oracle/runtime engine
bytes. The argv itself (including inline code), declared artifact list and
all comparison parameters are part of the plan content hash. Generated
artifact setup commands require the same executable/artifact closure.

Artifacts implementing the assertion are policy; mutable subject files,
generated outputs and application files are observations and are not frozen
as evaluator artifacts. Review must declare the complete bounded assertion
closure, including local imports/helpers used by an assertion script. Unknown
artifact roles, missing declarations/files, unsupported executable resolution
or shell/dynamic evaluators with undeclared dependencies refuse approval/use,
not inferred pass. This is a reviewed closed-file assertion declaration,
not general transitive environment discovery or a dependency registry.
Approved artifact/executable bytes are checked again before invocation, so
editing `assert.py` while leaving argv unchanged refuses; changing a subject
input still executes and yields a real pass/fail observation. This honest-drift
model does not authenticate malicious co-rewriting of declarations and hashes.

Upgrade only a recognized canonical scaffold driver, preserving the existing
COMPONENTS array and SEED/custom score functions. Compare the driver outside
those editable seams with the supported template before writing. A customized
unsupported driver refuses with no partial oracle/policy writes. The opt-in
driver uses the same scalar functions once each and a bounded stdlib required
runtime, not a second evaluator or generic registry. Default template rendering
and existing scalar `--score-only` exit behavior remain unchanged.

### Result carrier and digest domains

Use UUID-based run IDs and exclusive per-run directories. `gate.py` establishes
the run context and passes it to its one oracle subprocess; direct enabled
`oracle.sh` establishes the same context if there is no gate caller. Runtime
context names are `SERVO_GATE_RUN_ID` and `SERVO_GATE_RESULT_DIR`. Required
components receive their component identity and exact destination, not a
"latest" pointer. Caller-provided run context must be validated; a reused
destination refuses rather than overwriting old results.

The existing component artifact directory holds
`runs/<run_id>/result.json`. Its distinct envelope is
`schema_version: 1, kind: "required_component_result"` and contains `run_id`,
`component`, `policy_hash`, `config_hash`, `evaluator_hash`, `source_identity`,
the invocation's diagnostic `score`, raw `evidence`, and interpreted
`required: {status, ids, passed, failed, unknown, items}`. Each item includes
the required check ID, interpreted status/reason and reference to its raw
evidence record. Required `not_applicable`, unsupported family, malformed or
unavailable observation maps to unknown, never pass. Collected contradictions
remain failures, including an asserted observed absence. Preserve all known
failures alongside unknowns. Ledger evidence gets the same run ID; no command
is rerun to obtain a second channel.

Use UTF-8 JSON with sorted keys, compact separators and `allow_nan=False` for
Servo identity objects, with explicit typed `schema_version`/`kind` domain
fields. File references use `sha256:` plus SHA256 of their exact published
bytes; do not apply Vellum's 0.1-pilot input serializer. A config identity is
the frozen plan content hash; the project policy identity is its canonical
complete binding object. Reject non-finite scores/weights/thresholds and
ambiguous duplicate keys in enabled inputs/results. Paths and display
timestamps are not substitutes for identities.

Write temporary files in the destination directory, flush before atomic
publication, and never overwrite an existing published result. Validation
checks the closed required-ID set and evidence set, counts/status consistency,
expected schema/kind, current run/component/policy/config/evaluator/source
identity and exact referenced content digest. Partial writes, stale records,
missing/extra/duplicate IDs and wrong identities refuse. Validate the current
installed fragment and evaluator bytes too; approved on-disk fragment metadata
does not prove the live oracle still contains that fragment.

The enabled oracle publishes `.servo/gate-runs/<run_id>/oracle-result.json`
with effective quality weights/threshold, threshold env-override provenance,
composite and required aggregation, plus exact component file/digest references.
The gate validates that record and preserves
`.servo/gate-runs/<run_id>/gate.json`, returning that same overall gate payload
on `--json`. It is `schema_version: 2`, `kind: "gate_result"`, with `run_id`,
`status`, `exit_code`, `reason`, quality diagnostics, approved policy identity,
required counts/IDs/items and bound component references. Pre-invocation
enabled-policy refusals also return v2 unknown diagnostics when the enabled
manifest is identifiable; never emit a v1 success after an invalid opt-in.

`gate.json` is completion authority. Components cannot confer completion.
Both channels come from the one invocation; gate validation is not a second
check run or a design re-score. Gate schema2 is separate from this component
schema1, future component-design-envelope schema1, design-eval-policy schema2
and Vellum input0.1-pilot. No runtime producer name is special-cased.

### Scope and verification

Cover template/scaffold and spec-oracle installers, shared/vendored engines,
gate summary/version selection and all generated installed packages. Preserve
existing no-policy oracles byte-for-byte where possible and behavior-for-
behavior where rendering differs; custom drivers require explicit supported
migration. Prove the high-score veto through the installed gate before 036-01
uses it.

Add targeted installed tests before source edits: >=0.99 quality / required
fail, THRESHOLD=0, zero required-component weight, pass/low-quality/both-fail,
failure plus unknown, enabled empty set, unsupported/residual/unbound checks,
malformed and edited approvals, stale/missing/wrong-ID/wrong-digest records,
partial writes, concurrent invocations and single-invocation side effects.
Use current source and regenerated host packages, not global installed Servo.
Existing local pytest is available; `scripts/run_tests.py` is a full-suite-only
wrapper (it does not forward selectors), so invoke targeted pytest directly.
Exercise the actual scaffold/approve/install/gate CLIs and supported vendors.
No shared watchers/services or upstream captures are needed.

## 035-02: consumers

### Pickup and readiness

035-02 pickup is based on clean `servo-installed-required-gate` at
`aefc9306fa6aa38d55cb9543338b413823624f11`, the OPEN implementation PR41,
whose selected parent is `servo-required-design-evidence`. The new slice's PR
targets `servo-installed-required-gate`; there is no merge or main retarget.
035-01 is DONE with real gate/component fixtures. The earlier 035-01 readiness
and scope paragraphs above are its historical pickup, not this slice's scope.
After fresh independent framing/readiness review, use the actual helper
READY_FOR_REVIEW -> READY_FOR_IMPLEMENTATION -> IN_PROGRESS transitions.

### Bounded consumer inventory

The inventory comes from literal gate/oracle/status/sentinel references in
canonical `skills/`, `templates/`, `agents/`, `hooks/`, `scripts/` and the install
contract, plus the concrete subprocess and persistence seams read below.
Generated `hosts/` are projections of that canonical source under the existing
builder. This closes the repository's declared runtime/install surfaces; it
does not establish compatibility with dynamic or external consumers.

| Consumer | Source seam at pickup | Treatment |
|----------|-----------------------|-----------|
| Loop subprocess and completion | `skills/agent-loop/loop.py:2320-2368,2990-3098` | Read the overall gate, reject unavailable/unsupported/stale/replayed v2, halt v2 refusal with exit 2. Keep existing budget/context/iteration/plateau brakes. |
| Loop checkpoint, resume, prompts, final summary | `loop.py:753-768,2370-2439,2570-2660,2750-2762,3010-3050` | Add preserved overall payload and exact gate reference to history/summary; validate v2 checkpoint bindings before reuse. Legacy state version 1 stays readable. |
| Goal, sentinel and Routine guidance | `loop.py:3100-3174,3266-3333,3626-3708,3720-3780` | Only the overall gate can pass. Preserve final evidence and separate oracle cause from existing cap/disagreement terminal reasons. No native Copilot goal driver. |
| Clone-portable gate vendor | `loop.py:2278-2317` | Vendor the consumer reader beside gate/runtime through the existing installer. |
| Hook install and advice | `skills/oracle-hook/hook.py:96-107,180-237,325-452`; `templates/meta-judge.sh.template` | Version-aware required-failure hint and refusal warning; env-error remains turn fail-open, never completion. Existing customized scripts are not replaced; emit migration guidance. Copilot adapter remains advisory. |
| Planner | `skills/execution-planner/execution_plan.py:176-212,229-271,286-334` | Reference approved required policy/config/source identities and overall carrier pattern without evaluating, grading or claiming served-build provenance. |
| Heartbeat gate preflight/provision/verification | `skills/heartbeat/heartbeat.py:1634-1689,1766-1797,2340-2426` | Validate overall v2, copy policy and approved evaluator sidecars, exclude prior gate/component run records; preserve verification refusal evidence. |
| Heartbeat final outcome and triage | `heartbeat.py:1050-1078,1480-1590,2083-2116,2490-2600` | Preserve final overall authority/refusal and evidence in outcomes and human/JSON reports; required fail cannot become passed. Keep quarantine/accounting behavior. |
| Runner/judge instructions | `agents/runner.md`, `agents/judge.md` | Explain required contradiction versus unavailable evidence, inspection and rerun, with policy reapproval only as an explicit owner change. |
| Host/install documentation | `skills/{agent-loop,heartbeat,oracle-hook,execution-planner}/SKILL.md`, `README.md`, `docs/architecture.md`, `.claude-plugin/install-contract.json`, `scripts/build_host_packages.py` | Update live guidance, runtime closure and generated packages via the existing builder. |
| Scalar evaluators and upstream readiness | `skills/_common/fidelity_eval.py`, `skills/{design-eval,content-fidelity,eval-authoring,autonomy-readiness,edd-suitability}/*` | No-op: these emit component scores or inspect compile-time readiness, not installed overall gate completion. Their component/policy versions are not gate versions. No design/common changes. |
| Gate producer/scaffold/overlay | `skills/{quality-gate,scaffold-init,spec-oracle}/*`, `templates/oracle.sh.template` | No new grading or producer edits. Reuse 035-01's approved policy and carrier; raise a producer API gap to the coordinator before touching shared core. |

### Carrier handling

Use a small consumer-only reader next to quality-gate, shared by the named
consumers and included in the existing project vendor closure. It reads and
checks evidence; it never invokes checks or recomputes quality/required grades.
No new DSL, registry, scheduler or competing completion authority is added.
The coordinator is notified of this consumer-only seam before source edits.

For a live v2 invocation, the caller requests a fresh UUID and exact
`.servo/gate-runs/<UUID>` destination via the existing run-context variables.
Accept only that run, matching subprocess exit/status and exact published
`gate.json` bytes. Carry the original overall payload as `oracle` and its
`{path, hash}` reference as `gate_ref` in consumer records. The payload already
closes policy, effective quality policy and exact component references;
validate referenced bytes, run/config/evaluator/source bindings and the current
approved installed policy using existing read-only pins. Do not pick a latest
ledger, fabricate a score on refusal, equate a component pass with gate pass,
or interpret approved source provenance as served/current-build attestation.
Any build/observation identity already present in component raw evidence is
preserved, not fabricated or re-derived.

V2 failure remains `fail` with its typed cause; v2 refusal remains `env_error`
with actionable unavailable-evidence diagnostics, retaining known failures.
Invalid/missing mandatory references and unknown versions refuse with exit 2.
Once-only/replay controls apply to new invocation acceptance; multiple reports
may read the same immutable recorded run. Checkpoint/final handoff readers
revalidate their recorded exact-byte references without running the evaluator.
No pass can be inferred from a remembered scalar score or an unbound summary.
Pre-publication producer refusals without a usable run are unavailable, not
invented immutable records. Scalar v1 behavior and legacy checkpoints stay
compatible; additive fields do not conflate checkpoint and gate schema versions.

### TDD and installed controls

The implementer witnesses failing tests before source edits and stores exact
commands/results in a slice-specific consumer receipt. Exercise pass, high-score
required veto (including zero weight/THRESHOLD=0), component pass plus overall
quality fail, unavailable evidence, unsupported version, wrong/missing/digest-
mutated carrier, stale/replayed run, old v1 state and hook turn fail-open.
Prove goal disagreement/caps, diagnostic plateau and heartbeat triage final
reporting without a real model call or a native Copilot autonomy claim.
Use actual freshly installed command fixtures and preserved 035-01 records;
never rewrite those historical payloads to appear green. The fixture smoke
must surface a real required veto in a supported consumer's final report and
retain matching gate/component paths for handoff. Fixture proof is not general
design convergence or served-build attestation.

Run only targeted consumer/required-gate regressions, existing lint and host
drift/install checks; do not run unrelated full suites or weaken old tests.
Fresh compliance, craft, architecture and reconciliation verdicts precede
helper REVIEWED/RECONCILED/DONE. Reconcile live docs, leanness, memory and this
inventory without editing Accepted ADRs, DONE records, conventions or spec036.

## Verification and reconciliation

Use existing targeted gate/scaffold/overlay and consumer tests, plus installed
positive/negative controls. Record witnessed red-to-green and independent
compliance/craft/architecture evidence during implementation. Sweep live
architecture, README/skills, templates, package/install documentation and
report consumers; do not amend closed specs/Accepted ADRs in this proposal.
