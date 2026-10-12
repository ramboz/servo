---
status: Accepted
dependencies: [adr-0005, adr-0024, adr-0040, adr-0041]
last_verified: 2026-10-12
frame_review: true
---

# ADR-0042: Native generic evals read explicit frozen candidate file paths

## Status

Accepted (2026-10-12)

## Context

Generic native scoring needs real candidate output, not an injected score.

An executed full installed generic proof revealed
`skills/eval-authoring/score.py:405-419` always raises "candidate-gather not yet
implemented" for a real non-fake candidate. Existing operational prose discloses
that seam; native judge dispatch alone cannot fulfill 033-05's installed
generic consumer. Content/design already have concrete acquisition surfaces.

This is a tightly coupled native-only extension, not a general system-under-test
runner or repair of older API acquisition/hashes. The scorer already receives
`base_dir`, the directory containing config.json, and uses it for artifact/
reference paths. Installed base is the emitted component directory; spec-local
base is that eval's output directory.

## Decision Options Considered

### Option A: Inject scores or treat case.input as generated output
- **Pros:** Produces apparent success cheaply.
- **Cons:** Not a real candidate or native proof. Rejected.

### Option B: Add a general command/API system-under-test runner
- **Pros:** Flexible production acquisition.
- **Cons:** Broad execution/permission/budget framework outside this port. Rejected.

### Option C: Native-only explicit component-relative UTF-8 candidate files
- **Pros:** Real, project-owned moving output; read-only, clone-portable and
  consistent with the existing artifact base.
- **Cons:** The system/external driver must deliberately write/copy output into
  the component directory. It is not automatic system execution.
- **Disposition:** Chosen.

## Recommended Decision

1. Each native generic case requires deliberate `candidate_file`, a relative
   path inside the component directory containing config.json. The user/system
   writes real output there. Never substitute input/reference/rubric for output.
2. Freeze the native path and versioned acquisition policy
   `component-file-utf8-v1` with the native definition/dataset. Do not hash the
   moving output bytes into human approval. Existing API/Claude-CLI definition
   hashes and their disclosed acquisition behavior remain unchanged.
3. Resolve against the explicit existing `base_dir`, never accidental cwd or
   inferred project-parent depth. Reject absolute/traversal/symlink escapes,
   missing/non-file sources, invalid UTF-8 and NUL data with `env_error` before
   native judging. Freeze validates the path/policy; output may arrive later.
4. Read one coherent byte snapshot per case, decode once, and use the same text
   for every sample in that batch. Record per-case path/policy/SHA256 in the
   ledger as executed input provenance, not frozen moving-output identity.
5. Preserve model/runtime/default-decoding consent, independent read-only native
   calls, reference/rubric hashes, approval, sample/LCB/threshold policy and
   unpriced installation/re-freeze ordering. Native fake-score injection is
   rejected; test native protocols with fake executables, not passing injected
   production scores.
6. File-v1 supports constraint-free scored cases only. Existing generic
   `expected_output.constraints` depends on an unbuilt actual-value extractor;
   acquiring text does not supply those measurements. Reject nonempty/invalid
   native constraints and native fake-actuals injection before model invocation.
   Do not fabricate metrics from inputs or advertise constrained generic cases
   as supported. Actual-value extraction remains separately scoped future work.

## Consequences

**Becomes easier:**
- A generic component can genuinely grade an externally produced native text
  artifact through the existing emit/freeze/install/score workflow.
- Candidate provenance is deterministic without freezing the changing result.

**Becomes harder:**
- Callers must supply real output files; native initialization alone does not
  gather system output.
- Unpriced native components still cannot run under USD-bounded orchestration.
  No command runner or broader old-API repair is included.
- Native file-v1 does not support constrained cases; it fails explicitly rather
  than funding a judge and failing measurement afterward.

## Assumptions

The producer owns the component output directory and deliberately publishes its
candidate files there. Snapshot hashing attests the bytes read, not correctness
or authenticity of the external producer.

## Kill criteria

If a use case requires active system invocation rather than existing output
artifacts, author a separate acquisition/budget/permission contract. Do not
silently execute commands or reinterpret approved path policy to fit it.

## Open questions

None for this bounded native file policy.

## Verification

033-05 supplements cover path/policy freeze, moving output, snapshot consistency,
negative file cases and actual emitted installed generic native scoring.
