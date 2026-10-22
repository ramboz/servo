# Slice 037-01 tasks

- [x] Witness failing required-gate and neutral-closure controls.
- [x] Retain generic required/output/consumer behavior and negative tests.
- [x] Extract only used neutral I/O/runtime primitives.
- [x] Pin the actual reviewed six-file producer closure and require new epochs.
- [x] Exercise two non-card public workflows with native 0/1/2 and pure native readback.
- [x] Verify host-package and project-vendor closure without pilot modules.
- [x] Update reusable docs and record the owner-accepted prospective ADR-0046.
- [x] Complete independent compliance, craft, architecture and reconciliation.

Delivery follows normal slice closure: regenerate/check the board, commit this
feature branch, push it and create the ready-for-review replacement PR. These
hosting operations are session delivery steps, not product acceptance claims.

## Implementation evidence (not review evidence)

### Witnessed red and substantive controls

- Default-main lacks `required_runtime.py` and neutral/static helpers: initial
  regression collection failed; isolated required-veto/consumer/neutral closure
  controls then recorded **11 failures, 1 pass**. Tests preceded implementation.
- Packaging controls first failed on the missing vendor carrier declaration and
  absent regenerated hosts. The install contract and canonical host generation
  made them green; no old feature packages were transplanted.
- A genuine TESTONLY packet independently approved under different source-tool
  bytes initially passed preparation incorrectly. The minimal new-install guard
  now requires its approved six-tooling inventory to equal current producer
  pins. Different-epoch preparation and re-finalization refuse; producer archive
  semantics and historical approvals are unchanged.
- The early provisional capture helper changed during integration. Its affected
  test epochs were discarded and recreated, never rebound.

### Final source and actual native workflows

Reviewed source implementation cut:
`80f178ea1b25ebb0fff7b3e8c6651fcb4aa3e2b6`; pushed source cut:
`d41c5ef56fa41be618d5cf1e6aac1705622de2fd`. All six working and committed helper
bytes were individually checked against the final pins.

Both actual public workflows passed: seven-fact grid/audio routing with shared
engine, and nine-fact nested document/navigation with vendored engine and
different resources/environment. Each executes actual source preview ->
TESTONLY independent approval -> finalize -> verify -> consumer-check; actual
static preparation/policy approval; ordinary sealed overlay installation;
native gate request/accept/read; PASS/FAIL/UNKNOWN; independent live source and
delivery drift; output tamper; and strictly subprocess-free native readback.
No source, approval, runtime or installation seam is mocked. Only reader
controls forbid work. Test approvals do not attest real application success.

Untouched TESTONLY positives and their complete path/hash/nonce/native-reference
indexes are retained privately in session files, not committed proof exports:
`audio-routing-TESTONLY-facef292-62fe-4c46-8111-a09f7134964f` and
`document-reader-TESTONLY-c4c5327b-0a3e-42b6-b2eb-f4a29d831731`.
The parent independently rehashed all **99/116** indexed artifacts successfully.
Native readback does not infer a newest run or select from discarded controls.

### Reader-premise clarification, not a runtime regression fix

The original extra auxiliary/runtime probes forbade every subprocess. They
failed on uncached `platform.platform()` (`uname -p` and interpreter `file -b`)
and Vellum's existing fixed `git -C <original-root> rev-parse HEAD` query.
Initial independent compliance returned `needs-changes` on that broad reading.
These red results are preserved here, not relabelled as runtime defects.

The coordinator explicitly clarified the existing approved boundary on
2026-10-22: native `gate_consumer.read` remains strictly subprocess-free;
auxiliary `verify-current` is read-only, permits the existing bounded metadata
queries, and never acquires, evaluates, compares or rescores. Accepted ADR-0046,
producer/runtime meanings, hashes, schema/argv and existing epochs are unchanged.
Prospective AC2/AC5 and live docs now name this distinction explicitly.

Replacement probes execute the real uncached metadata queries with exact argv
guards on both `run` and `Popen`, reject arbitrary commands, and forbid
acquisition/evaluation/comparison. The runtime probe and both retained shapes'
current-reader probes passed (**3/3**). The native no-subprocess control remains
strict and unchanged. No production helper bytes were changed for this
clarification; existing clean carriers remain untouched.

### Native cache-I/O defect found and repaired in review

The next independent compliance pass found a real defect: Python's default
source loader could write bytecode caches during native readback and consume
cached code rather than the hashed evaluator source. Four new cold/forged-cache
controls failed before the fix, covering both carrier bootstrap and the
approved identity helper with bytecode enabled.

The first repair compiled exact source bytes but a further review exposed
transitive cold imports; an additional control reproduced that cache write.
The consumer now compiles exact source bytes in memory without cache I/O,
suppresses transitive import cache writes for that load and restores the caller's
bytecode policy even on import failure;
the evaluator identity helper's bytes are checked against the approved hash
before compilation. It still calls only the existing pure content-hash helper,
not checks or scoring. The affected output/consumer/neutral-package suite
passed **92 tests, 41 subtests**, including cold/forged/transitive and policy-restoration
controls. This is a
runtime defect repair, unlike the auxiliary-premise clarification above.
The four static helpers, six source helpers and native required engine are
unchanged; existing acquisitions are not relabelled as reviewed at creation.

### Preparation preservation found and repaired in craft

Craft found that the generated `spec/static.md` could overwrite project content
and that invalid inputs could leave preparation output before validation.
Collision/invalid-producer controls first recorded **4 failures**; after
no-follow destination/parent preflight, producer/source/bindings/runtime
validation before creation, and exclusive specification/helper creation, the
controls passed (**2 tests, 4 subtests**). Real public workflows also exercise
preservation of an existing specification and retry only after removing their
own synthetic sentinel.

Publication is not a multi-directory transaction: an I/O interruption or
concurrent input change can still leave unapproved partial output. The
walkthrough directs a fresh scaffolded target rather than automatic deletion
or overwrite. This bounded residual is explicit, not a success-shaped fallback.
`static_contract.py` bytes changed, requiring fresh TESTONLY native epochs;
old retained acquisitions remain untouched.

### Validation commands/results

- Final parent-run `python3 scripts/ci_check.py`: **2536 passed, 8 explicit-runtime
  opt-ins skipped**; manifests, pinned Ruff, **150** install-surface checks and
  generated-host drift all passed.
- Safety-fixed actual public workflows: **2/2 passed** in 231 seconds; their
  fresh retained final-helper epochs are
  `audio-routing-TESTONLY-7ea6d357-64ee-4572-aa7b-ba95c6378e79` and
  `document-reader-TESTONLY-6d02f8d3-c863-44f7-a4e3-f6c77897215a`.
  All **215** indexed artifact hashes were reverified. Both fresh targets'
  bounded auxiliary-current probes also passed. Jig independently exercised
  both unchanged carriers through read/hash, public record/check/REVIEWED and
  foreign-run/tampered-DONE refusal without producer/evaluator/browser calls.
- Implementer final pre-clarification `python3 scripts/ci_check.py`: **2528
  passed, 8 explicit-runtime opt-ins skipped**; manifests, pinned Ruff, **150**
  install-surface checks and generated-host drift passed.
- Targeted native/extraction suite: **348 passed, 97 subtests**; final
  neutral/static/package regressions **66 passed, 93 subtests**.
- Actual isolated `test_static_workflows.py PublicWorkflowTests`: **2/2**.
- Actual isolated browser controls: **4/4**.
- Parent-run bounded metadata probes: `SERVO_STATIC_RUNTIME_TESTS=1` runtime
  control **1/1** and `SERVO_STATIC_READER_TARGET` current reader **1/1 per
  shape**. The supplied frozen runtime is read-only and receives no installs.
- Exact AST comparison confirms all twelve extracted I/O function bodies match
  the selected effort source. General `design_eval.py` / `score.py` unchanged.

## Named acceptance coverage

| AC | Controls |
|---|---|
| 1 | `InstalledRequiredGateTests.test_ac2_installed_contradiction_veto_at_high_quality_and_zero_threshold`; v1, argv/pin/inventory/refusal/concurrency controls in `test_required_gate.py` / `test_result_artifacts.py` |
| 2 | Loop/checkpoint/resume, hook/planner/heartbeat/triage controls in `test_gate_consumers.py`; `test_complete_frozen_arguments_and_repeated_reads_are_pure` in `test_gate_output_readback.py`; bounded auxiliary/runtime metadata probes |
| 3 | `NeutralClosureTests.test_ac3_exact_primitive_extraction_without_component_implementation`; strict I/O/ownership controls and generic static/browser controls |
| 4 | Both public workflows' live-source/tooling-epoch controls and committed six-file verification |
| 5 | `test_audio_routing_public_workflow` and `test_document_reader_public_workflow`, actual public commands and native authority |
| 6 | Host/project-copy import closure, vendor-carrier declaration, generated-host native controls and the reader's real `--vendor-engine` workflow |
