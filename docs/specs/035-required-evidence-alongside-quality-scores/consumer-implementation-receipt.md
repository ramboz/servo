# 035-02 consumer implementation receipt

Implemented 2026-10-15 in the isolated `servo-required-verdict-consumers`
checkout. Selected base: `aefc9306fa6aa38d55cb9543338b413823624f11`
(035-01 DONE / PR41); readiness/start record:
`0eb26540a7ef40a150c78499979614bf3707ac25`. Read the accepted ADR-0044,
spec/AC/DoD, bounded plan and fresh readiness evidence before edits. Pickup
already completed the ordinary READY_FOR_IMPLEMENTATION → IN_PROGRESS
transitions. This receipt is implementation evidence, **not a review verdict**.
No commit, push, PR, merge, agent delegation or review transition was performed.
This opening and earlier pending/IN_PROGRESS statements describe the original
implementer epoch. Later recovery sections preserve the actual chronology;
current lifecycle/verdict authority is the slice record and its reviews.

## Witnessed TDD

All artifacts below are under:

`/Users/ramboz/.copilot/session-state/134ce109-68f5-4639-a421-d1e773fb724e/files/`

Tests were added and actually run before production edits. Their initial red
state is noted here rather than committed, as requested.

```sh
uvx --with pytest-subtests pytest -q \
  skills/quality-gate/test_gate_consumers.py \
  skills/quality-gate/test_gate.py skills/oracle-hook/test_hook.py \
  skills/execution-planner/test_execution_plan.py
```

`035-02-red.txt`: **14 failed, 183 passed, 9 subtests passed**, exit 1.
Failures witnessed every AC: absent original-payload/reference carriers,
refusal returning normal halt, high-score plateau lacking required IDs,
scalar hook advice, missing planner identities, copied historical runs,
missing version-aware reader, and missing final triage evidence.

Additional inspect → failing-test → implementation loops retained exact
commands, output and exit status:

| Receipt | Witnessed red / correction |
|---------|----------------------------|
| `035-02-red-followup.txt` | 2 failed, 3 passed: enabled scalar summary trust and legacy no-policy minimal gateway regression |
| `035-02-red-parser-and-dispatch.txt` | 2 failed, 19 passed, 3 subtests passed: strict duplicate/nonfinite parser absent; real dispatch and advisory-adapter controls already green |
| `035-02-red-readback.txt` | 4 failed: v1 downgrade readback promotion, driver drift, scalar dispatch trust and historical dispatch-time mutation |
| `035-02-red-preflight.txt` | 1 failed, 4 passed: preflight refusal discarded structured carrier |
| `035-02-red-malformed.txt` | 3 failed, 1 passed: malformed records/advice crashed instead of refusing |
| `035-02-red-resume-scalar.txt` | 1 failed: zero-new-iteration resume trusted a history `status=pass` over bound overall fail |
| `035-02-red-config-drift.txt` | 1 failed: remembered approved config hash did not detect an edited check body; fixed through existing pure identity helper, no reexecution |

First broad regression attempt (`035-02-consumer-regressions-attempt2.txt`)
found four tightly coupled regressions, with 1226 tests and 74 subtests passing.
Two were the old tests' hardcoded stdlib allowlists missing `importlib`; each
allowlist gained only that real stdlib module. The other two exposed no-policy
unversioned minimal gateway compatibility. Original assertions, unpriced-model
refusal controls and all other legacy tests remain intact.

Completion regression command (not `scripts/run_tests.py`, not a full suite):

```sh
uvx --with pytest-subtests pytest -q \
  skills/agent-loop skills/heartbeat skills/oracle-hook \
  skills/execution-planner skills/quality-gate \
  skills/spec-oracle/test_required_gate.py
```

The earlier completion checkpoint (`035-02-completion-green.txt`) passed
1244 tests and 82 subtests. Final config-identity closure command/output:
`035-02-config-closure-green.txt`. This includes the installed required-gate
regressions, not unrelated full-suite work: **1245 passed, 82 subtests passed,
0 failed**, exit 0, at final implementation bytes.
The new fixture file covers 27 test methods, with explicit controls for each
of the six ACs. Prior green checkpoints and final focused refinements are
retained separately, not overwritten.

Runtime/install closure:

```sh
uvx --with pytest-subtests pytest -q \
  scripts/test_build_host_packages.py scripts/test_scaffold_runtime.py \
  scripts/test_verify_install.py scripts/test_copilot_installed_runtime.py \
  scripts/test_docs_install.py scripts/test_build_release_zip.py
python3 scripts/build_host_packages.py
python3 scripts/build_host_packages.py --check
uvx ruff check .
git --no-pager diff --check
```

`035-02-config-closure-runtime-green.txt`: **159 passed, 78 subtests passed**.
Final lint/drift/whitespace: **all pass**, `035-02-config-closure-checks.txt`.
All host edits came from the normal builder; it needed no source
change because its existing runtime traversal already includes the new reader.
No dependencies had to be restored. No unrelated suite, watcher or service ran.

## Bounded inventory and fixture coverage

The literal canonical reference sweep is retained as
`035-02-consumer-inventory.txt` (271 matches, including documentation and
installer references). This is the plan's repository boundary, not a claim
about dynamic/external consumers.

| Consumer | Evidence / treatment |
|----------|----------------------|
| `agent-loop/loop.py` subprocess and completion | Fresh UUID, exact overall gate bytes and subprocess exit; pass/veto/refusal/quality failure, stale/replay/unknown-version controls |
| Loop history, prompts, checkpoint/resume, final summary | Original `oracle`, exact `gate_ref`, separate `oracle_reason`; component mutation refuses before spend; zero-iteration resume copies the bound decision, not scalar history; old v1 resume tests pass |
| Plateau and budget/context/iteration brakes | Flat composite 1 with required fail halts non-converged, retains IDs/reasons; existing cap, budget, context and quarantine regressions remain unchanged |
| Goal/sentinel/Routine guidance | Mocked model with real final installed gate; disagreement and turn/cost caps retain their terminal reasons and separate oracle cause; no component/score pass sentinel |
| `oracle-hook/hook.py`, meta-judge template, Copilot adapter | Actual installed veto block and refusal fail-open warning; custom script unchanged with migration guidance; installed advisory adapter forwards evidence, native Copilot launch still refuses |
| `execution-planner/execution_plan.py` | References manifest-pinned required policy, completion carrier pattern and approved config/evaluator/source binding; no evaluation or build attestation |
| `heartbeat/heartbeat.py` preflight/provision/verification | Real installed preflight and verification; refusal JSON retains contradictions/unavailable IDs; no dispatch or inbox mutation on preflight refusal; approved sidecars/local evaluator pins copied, old component/gate runs excluded |
| Heartbeat outcome and triage | Real worktree dispatch of component-pass/quality-fail remains `tried`; human/JSON report original gate/refs and correction guidance; report rereads preserve cost and dispatch timestamp |
| Clone-portable vendor and all three generated hosts | Reader is included with gate/runtime in install contract and goal vendor; actual generated gate invocation/readback controls on Claude, Codex and Copilot packages; drift/runtime tests |
| Runner/judge and live skill/README/architecture guidance | Correct contradiction vs refusal repair; policy reapproval is explicit, no self-grading; raw evidence retained, source provenance not served-build identity |
| `_common/fidelity_eval.py`, design/content scorers | No-op: component scoring/freeze/ledger utilities, not installed overall gate consumers; reference sweep and their score/ledger entry points confirm no completion-reader seam. No design/common changes |
| `eval-authoring`, `autonomy-readiness`, `edd-suitability` | No-op: compile-time registration/readiness/suitability, not runtime overall verdict readers; their schema versions are unrelated. Existing accounting/preflight tests exercise their consumer-facing registration seams |
| Producer/scaffold/overlay, oracle template | No-op: 035-01 remains authority; producer hashes below unchanged, installed positive/negative controls retained. No producer API/core overlap was necessary |
| Builder/release/runtime verification scripts | Existing generic traversal and manifest contract consume the new runtime file; 159 install/generation tests and final host drift check prove closure without a new installer |

## Contract decisions and deviation log

- The consumer-only `skills/quality-gate/gate_consumer.py` seam reads identities,
  exact byte digests and approved bindings using existing read-only runtime
  helpers. It never invokes checks or recomputes composite/required grades.
  Original overall `oracle` is preserved, including raw component evidence refs.
  Current config bodies are checked through the already-approved deterministic
  evaluator's existing pure `plan_content_hash` helper, after checking evaluator
  byte pins; no run/check/score function or producer API change is involved.
- A live run requests a new UUID/exact destination; `consumer-accepted.json`
  publishes an exclusive acceptance claim. Immutable report rereads do not
  claim again. Unknown versions, missing/mutated refs and stale/replayed runs
  refuse 2. No latest pointer, standalone component pass or trusted summary
  authorizes completion. Historical v1 reads remain v1.
- Published env_error may legitimately lack unavailable refs. Preserve its
  original refusal/known contradictions; add consumer diagnostics when binding
  validation fails. Never manufacture `0.0`, evidence or an immutable gate ref.
- Small compatibility refinement: no-policy unversioned minimal gateway
  adapters retain their existing shape; an explicit unknown version or an
  enabled-policy v1 downgrade still refuses. Refused carriers cannot promote
  themselves on reread.
- Safety-limited provisioning: absolute external component-sidecar paths refuse
  isolation with migration/reapproval guidance rather than redirecting the
  approved evaluator back to the original checkout or rewriting identities.
  Target-relative policy/sidecars and external approved evaluator pins retain
  their existing identities. This bounded limitation is documented.
- Live quality-gate/required-policy guidance was also corrected where it still
  said consumer propagation was future work. No accepted ADR, DONE record,
  convention, memory file, producer/core implementation or spec036 was changed.
- Native Copilot unattended autonomy remains unsupported. Hook output is
  advisory, and turn fail-open is not completion attestation. Mocked model
  processes are fixture proof only. No design or served/current-build claim.
- No separate-spec discovery or `docs/inbox.md` item. External consumer
  compatibility and independent review/reconciliation remain explicit handoff
  obligations, not completed work.

## Real supported final-report smoke and source identity

Run:

```sh
python3 /Users/ramboz/.copilot/session-state/134ce109-68f5-4639-a421-d1e773fb724e/files/035-02-smoke.py --config-closure
```

Final artifact prefix (all paths below relative to this prefix):

`/Users/ramboz/.copilot/session-state/134ce109-68f5-4639-a421-d1e773fb724e/files/035-02-config-closure-smoke/`

- `035-02-smoke-receipt.json`: exact current-source SHA256 identities.
- `035-02-emitted-gates.json`: full installed pass/veto/component-pass-quality-fail/refusal carriers and exact refs.
- `035-02-loop-final.jsonl`, `035-02-goal-finals.json`: real final gates, mocked model only.
- `035-02-installed-hook.json`: actual installed high-score veto advice.
- `035-02-triage-human.txt`, `035-02-triage.json`: actual supported final reporting, required assertion plus correction and gate path/hash.

The final-report fixture is `035-02-installed-fixture/`. Composite **1.0**,
required component weight **0**, `THRESHOLD=0`, overall
`fail / required_constraints_failed`:

- Gate: `.servo/gate-runs/2255e49a-f702-4213-81cf-0c19caad70ae/gate.json`,
  `sha256:8bc4ff3487c57d1c300f0af69d2a38dff9412938519f07548ebb961867cf41d2`.
- Component: `spec/oracle/demo/runs/2255e49a-f702-4213-81cf-0c19caad70ae/result.json`,
  `sha256:3bd2712c7110be9d8434eb5ea0376877d2f2a23d895d030b7f93e0a3b0e147b6`.

The separate Jig119 refusal control is overall
`fail / quality_below_threshold`, despite required/component pass:
`.servo/gate-runs/cb959c26-f59d-4db6-9e9d-ac6ba4e12117/gate.json`
(`sha256:d287a86b7de0a263f5d77b66b6ffd4db909a72202a066395e07c8a87eaff4de2`);
its matching component is
`spec/oracle/demo/runs/cb959c26-f59d-4db6-9e9d-ac6ba4e12117/result.json`
(`sha256:f82fabd696a46bf534210da8092ce25e0af5e66dbc3b875ed04d97d3592aa96a`).
These preserved records require no rerun/rescore for inspection.

The four actual 035-01 historical controls were read-only SHA256-verified
against the handoff and copied byte-for-byte into `035-01-original-carriers/`.
Their original absolute references remain unchanged; these copies are archival,
not rewritten relocated authority. See `035-02-historical-fixture-receipt.json`.
No historical fixture was modified or rewritten green.

Final reader:
`sha256:3aa7c9a8e471ec43f1d674d7fa326daf90f300415b525dbc2d8d52c1f061bf6b`.
Unchanged producer gate:
`sha256:5c469d1cd547c851ff0ec94b544519ac44feea3bb613b54a6986b263f476b0c2`;
unchanged required runtime:
`sha256:4388400a23dcd918561b3edc155c9da7606ffa3b9bec02dd8f04c4cdcfde2d42`.
The smoke receipt pins loop, heartbeat, hook, template, planner, checks and
overlay source bytes as well. Exhaustive changed-file paths/line counts/hashes
are in the session `035-02-deliverables.json` handoff.

Independent compliance/craft/architecture and reconciliation reviews, board
close-out, commits and stacked PR publication remain the orchestrator's work.
Slice remains IN_PROGRESS; no review checkbox is manually ticked.

## Orchestrator compliance recovery (2026-10-15)

Fresh compliance returned `needs-changes`; its actual non-clearing evidence was
recorded with `review.py` and committed in `b3897fd` before replacement.
The orchestrator corrected three coupled bugs with witnessed test-first
regressions, preserving the preceding implementation receipt as its earlier
source epoch rather than rewriting that chronology:

| Control | Red evidence | Green evidence |
|---------|--------------|----------------|
| An evaluated iteration followed by failed/interrupted invocation keeps final unavailability through heartbeat and repeated read-only reports | `035-02-review-heartbeat-red.txt`: 2 failed subtests | `035-02-review-heartbeat-green.txt`: 4 tests and 2 subtests passed |
| Installed hook runtime path contains spaces and an apostrophe | `035-02-review-hook-path-red.txt`: 1 failed | `035-02-review-hook-path-green.txt`: 1 passed; both gate and reader paths safely rendered |
| Non-object gate JSON warns visibly, without blocking or attesting completion | `035-02-review-hook-json-red.txt`: 5 failed subtests | `035-02-review-hook-json-green.txt`: 1 test and 5 subtests passed |

The final unavailable status is now kept separately from the original prior
gate evidence. Human reporting labels that retained gate as diagnostic, not
current completion. No producer grading, convention or accepted/closed record
changed. Only the new consumer tests were extended; old tests were not weakened.
There are now 30 consumer test methods.

`035-02-review-recovery-regressions.txt` records 755 passing affected consumer
tests and 48 passing subtests. `035-02-review-recovery-runtime.txt` records
148 passing runtime/install tests and 73 passing subtests. These are targeted
runs, not an unrelated full suite. A following formatting-only lint correction
does not change behavior; final source-epoch controls are recorded separately
in `035-02-reviewed-source-controls.txt` and
`035-02-reviewed-source-checks.txt`.

The corrected source-epoch installed smoke uses a fresh directory, preserving
every previous carrier unchanged:
`035-02-reviewed-source-smoke/035-02-smoke-receipt.json`. Its index and
loop/goal/hook/triage files follow the same names as the preceding epochs.
The source receipt pins the actual bytes and each overall/component reference;
this is fixture proof, not real design or served/current-build attestation.

### Availability and missing-authority recovery

A second fresh compliance review found two remaining availability paths:
zero-new-iteration resume and a model failure/malformed verdict after edits.
Its genuine `needs-changes` record is preserved by commit `48b4d19`.
`035-02-review-availability-red.txt` witnessed 4 failing subtests;
`035-02-review-availability-green.txt` cleared 4 tests and 4 subtests.
The loop now persists unavailable final status separately from prior evidence,
does not turn an exhausted-cap resume into a current evaluated verdict, and
marks failed post-edit turns unavailable. Existing terminal reasons and
no-policy v1 behavior are preserved; a fresh bound gate can recover.

The associated missing-authority sweep added two further negative controls:
a triage record missing its original overall payload cannot remain `passed`,
and an old scalar checkpoint cannot attest newly enabled policy with no new
evaluation. `035-02-review-missing-authority-red.txt` witnessed 2 failures;
`035-02-review-missing-authority-green.txt` cleared 4 tests and 4 subtests
including the availability controls. There are now 33 consumer test methods.
Only consumer sources/tests changed; producers remain byte-identical.

Final source-epoch control and historical failure/resume regressions are in
`035-02-availability-source-controls.txt`; Python-floor controls in
`035-02-availability-python39.txt`; lint/drift/runtime receipts use the same
availability prefix. Exact freshly installed runtime/control paths are in
`035-02-availability-source-smoke/035-02-smoke-receipt.json` and its emitted
gate index. Earlier smoke directories and source receipts remain historical,
not rewritten to match newer source.

### Craft nit and final source

Fresh craft passed with one non-blocking malformed planner-reference nit.
The correction validates the manifest's closed required-policy pin shape,
typed policy version and digest before projecting a plan reference; malformed
pins use the existing `EnvError(manifest_malformed)` rather than uncaught
`TypeError`. No grading or producer behavior changed.
`035-02-craft-planner-red.txt` witnessed 6 failing subtests;
`035-02-craft-planner-green.txt` cleared 2 tests and 6 subtests. There are now
34 consumer test methods.

The final source epoch is recorded in `035-02-final-source-controls.txt`,
`035-02-final-source-python39.txt`, `035-02-final-source-checks.txt` and
`035-02-final-source-runtime.txt`. Its fresh installed fixtures and exact
source/gate/component hashes are at
`035-02-final-source-smoke/035-02-smoke-receipt.json` and the adjacent emitted
gate index. Earlier source epochs remain unchanged.

## Final independent review and reconciliation

Fresh compliance, craft, architecture and reconciliation each returned pass.
The review records beside the slice are recorded by `review.py`; genuine
earlier non-clearing compliance verdicts remain in git history. The craft nit
and architecture receipt nit have executed, bounded dispositions above.
The slice's deviation log/sweep covers live runtime/docs, generated/vendor
surfaces, source-backed memory, leanness and deferred external work. Lifecycle
state and dependency checks are performed by the ordinary helpers, not inferred
from this receipt.
