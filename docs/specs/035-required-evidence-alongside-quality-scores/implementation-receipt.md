# 035-01 implementation receipt

2026-10-15. The implementer-epoch sections below preserve the original
IN_PROGRESS handoff and its historical results. Independent-review recovery
and final checks are recorded separately below; current lifecycle/review
authority lives in the slice and helper-produced review files. Accepted
ADR-0044 is unchanged.

## Epoch and scope

Clean selected parent: `a383c8761afaab010f133207876d1c6f01ff2b2e`.
Pickup/current committed HEAD: `a6fd46b` (readiness); implementation is the
uncommitted worktree delta, not a new committed epoch. No main-checkout source,
global Servo runtime, upstream capture or shared service was used.

Implementer-epoch canonical byte identities (`sha256:` prefix implied):

| File | SHA256 |
|---|---|
| `skills/quality-gate/required_runtime.py` | `6f87a26532817046cecef93bd392dd60fbaff340604d5a451b1107c1d49ebc79` |
| `skills/spec-oracle/checks.py` | `cc6b9d4910776c62c1f13008d9e2c32b0f80dc3a7fcf5973afa17e77304b3136` |
| `skills/spec-oracle/oracle_overlay.py` | `e66d89d963c42a7ad8841b1c360eecaf47a07de1bb25e5d93e3145fd5444ee0b` |
| `skills/quality-gate/gate.py` | `51190c533661c545f66fb96ca53c1a4bd31e7d3a96320b144a43f31f7e5cda45` |
| unchanged `templates/oracle.sh.template` | `730a73e374db5f5004758a3fbb9af2a27caf1e4e3dcba3fb4d9e624622e0d7df` |

The canonical template stays byte-identical for default installs. Explicit
upgrade checks that template outside COMPONENTS/SEED seams, preserves those
seams, and substitutes the bounded required driver. Runtime assertion closure
is reviewed argv/executables/declared files, not a generic registry or
transitive environment discovery. Local binding paths relocate with the
target; shared/external paths remain exact.

## Witnessed TDD evidence

Tests were added before their respective fixes and actually run red. No red
commit was made because the parent owns commits; the test-only checkpoints
and assertions are recorded here instead. Commands ran from this worktree.

Initial exact command:

```sh
uvx pytest -q skills/spec-oracle/test_required_gate.py
```

**1 failed**, `test_ac2_installed_contradiction_veto_at_high_quality_and_zero_threshold`:
`2 != 0`, `oracle_overlay.py: error: unrecognized arguments: --enable-required`.
After minimal install/carrier wiring: **1 passed**. The intervening canonical
normalizer failures were fixed (anchored SEED and array boundaries).

Subsequent exact red commands and selected load-bearing failures:

| Command suffix after `uvx pytest -q skills/spec-oracle/test_required_gate.py` | Witness |
|---|---|
| `--tb=short` (first expanded set) | 1 failed / 12 passed: `test_ac3_policy_and_executable_drift_refuse_before_assertion`, `calls.exists()` unexpectedly true |
| `--tb=short` (next expanded set) | 5 failed / 12 passed: generated absolute assertion script rejected despite declaration; unowned direct context returned 1 instead of 2; quality-authority control returned 1 instead of 2; vendor runtime absent; approval drift above |
| `-k 'runtime_vendor_contract or unsupported_enabled_driver or finite_quality' --tb=short` | 2 failed / 1 passed: install contract omitted runtime; edited enabled driver reinstall returned 0 instead of 2 |
| `-k 'dynamic_component or invalid_oracle_required' --tb=short` | 2 failed: dynamic array silently installed; invalid overall required aggregate returned 1 instead of 2 |
| `-k relocation --tb=short` | 1 failed: vendored invocation used the original target's absolute result destination |
| `-k malformed_raw --tb=short` | 4 failing subtests: boolean evidence version, malformed message, wrong family and inconsistent evidence/score accepted |
| `-k usd_budget --tb=short` | 1 failed: enabled path bypassed existing accounting guard (returned 1 instead of 2) |
| `-k refresh_installed --tb=short` | 1 failed: explicit reapproval copied new runtime but retained old installed runtime pin |
| `-k missing_oracle_record --tb=short` | 1 failed: missing overall carrier discarded the exact-run component's already-observed failure |

All are green in the final runs. No existing guard was skipped or weakened.
The pre-existing dependency allowlist now recognizes `importlib` as stdlib;
the guard still rejects non-stdlib imports. The expanded pre-existing
accounting controls also caught an invalid-UTF8 detection regression, fixed
without changing the guard.

## Implementer-epoch checks (historical results, not final-byte verification)

```sh
uvx pytest -q skills/spec-oracle/test_required_gate.py \
  skills/spec-oracle/test_oracle_overlay.py skills/spec-oracle/test_checks.py \
  skills/quality-gate/test_gate.py skills/quality-gate/test_unpriced_oracle.py --tb=short
```

**336 passed, 10 subtests passed** (28 new installed/identity tests plus
308 existing checks). Covers AC1–6: reviewed shared/vendored installs and
generated setup closure; high-quality/threshold-zero/weight-zero veto and
direct oracle exit; observed absence versus timed-out capture; failure plus
unknown; policy/approval/source/artifact/ID/result drift; malformed versions,
complete evidence sets, score consistency and byte digests; concurrent exact
run binding and single invocation counters for both quality/component checks;
decision table and preserved overall quality failure; enabled-empty removal,
no partial unsupported migration, force refusal, reinstall/uninstall,
relocation, runtime reapproval, accounting and scalar/stdout compatibility.

```sh
uvx pytest -q scripts/test_build_host_packages.py scripts/test_scaffold_runtime.py \
  scripts/test_verify_install.py skills/quality-gate/test_skill_surface.py --tb=short
```

**147 passed, 52 subtests passed**. The new generated-host test independently
builds current source into temporary Claude, Codex and Copilot packages and
executes each package's real scaffold → generate → approve → install → gate,
proving pass/fail/refusal. Fixtures are bounded and cleaned; test CLI
availability breadcrumbs use fixture-local XDG state.

```sh
uvx pytest -q skills/scaffold-init/test_scaffold.py scripts/test_scaffold_runtime.py \
  skills/agent-loop/test_loop.py -k 'Vendor or vendor or scaffold or install' --tb=short
PYENV_VERSION=3.9.19 python3.9 skills/spec-oracle/test_required_gate.py -q
uvx ruff==0.15.17 check skills/quality-gate/{required_runtime.py,gate.py,test_gate.py} \
  skills/spec-oracle/{test_required_gate.py,checks.py,oracle_overlay.py} \
  skills/scaffold-init/scaffold.py skills/agent-loop/loop.py --output-format concise
python3 scripts/build_host_packages.py
python3 scripts/build_host_packages.py --check
git --no-pager diff --check
```

Vendor/scaffold selection: **116 passed, 2 existing skips, 387 deselected**.
The two existing shellcheck controls skip because shellcheck is unavailable
(installed Docker daemon unreachable); no skip was added or guard loosened.
Python floor: **28 tests passed** on actual Python 3.9.19.
Pinned Ruff: **pass**. Host regeneration/drift (version 0.11.0): **pass**.
Whitespace: **pass**. No unrelated full suite or standalone type checker was
run; this repository has no configured type-check gate for these helpers.

## Actual carrier capture and reusable contract

The public [walkthrough/schema/examples](../../../skills/spec-oracle/examples/required-policy.md)
and `skills/spec-oracle/test_required_gate.py` provide reusable command and
generated-artifact fixtures. Schema2 `gate_result` and schema1
`required_component_result` are distinct from future design-envelope schema1,
existing design-eval-policy schema2 and Vellum0.1-pilot.

A final real CLI capture used run
`989ce895-e6a8-48af-8e19-709452d92f2c`: rc **1**,
`required_constraints_failed`, composite **1.0**, threshold **0.0**, required
component weight **0**. These are the exact emitted target-relative paths:

- `spec/oracle/demo/runs/989ce895-e6a8-48af-8e19-709452d92f2c/result.json`
  (`sha256:f1e02801e488a90d5471c0414c69530b4720e47d8ae483b108b0aef4eb02576e`)
- `.servo/gate-runs/989ce895-e6a8-48af-8e19-709452d92f2c/oracle-result.json`
- `.servo/gate-runs/989ce895-e6a8-48af-8e19-709452d92f2c/gate.json`
  (`sha256:d18764e36a3cddac20bbc7a4bdd17d865e6cbc8d66b1eab2c09893b6e4183889`)
- Project policy identity:
  `sha256:86a64f6799ff7fdd9f01f3fb88150288b2dd61c6c2bcf6bf4346f047752f82ec`.

Capture fixture was cleaned, not retained as a durable project attestation.
Its policy hash includes the fixture's approved executable/shared-engine
paths; these values are honest run evidence, not portable golden digests.
Use the committed fixtures to emit new records for downstream integration.

## Deviations and handoff

No material accepted-architecture or policy deviation. Carrier implementation
lives with quality-gate; the existing default template is intentionally not
rewritten. No producer-name runtime coupling, second assertion invocation,
latest-ledger query, auto-approval or default upgrade was introduced.

At the original handoff, remaining work was independent compliance/craft/
architecture review, reconciliation, lifecycle evidence and publication.
The recovery section below records subsequent work without backdating that
handoff. 035-02 consumer propagation and 036 observations/build linkage
are deliberately not implemented. No new separate-spec/inbox item identified;
existing consumer/design follow-ups already have owners. No writes to memory,
conventions, accepted ADRs or closed specs were made.

## Independent-review recovery

Compliance initially returned `needs-changes` on actual executed-script cwd
closure, false-only legacy annotations and missing vendored gate runtime.
Recovery reviews found relative-PATH executable resolution, extensionless
interpreter entrypoints and a Python option-separator ambiguity. Each finding
was fixed with an installed regression; the final compliance reviewer passed
AC1-6. Craft then found migration truncation when a custom SEED scorer contained
the driver marker, plus a nonblocking vacuous composite-control gap. Migration
now locates the driver anchor outside every SEED span, and the control forges
only the composite while preserving the effective threshold.

Exact recovery commands after `uvx pytest -q
skills/spec-oracle/test_required_gate.py`:

| Selector / flags | Witnessed red | Verified green |
|---|---|---|
| `-k working_directory --tb=short` | 1 failed: wrong root assertion approved instead of refused | 3 passed with original script/generated closure controls |
| `-k false_required --tb=short` | 1 failed: scalar installed gate refused 2 instead of 0 (including missing unused vendor carrier) | 3 passed with scalar/invalid-opt-in controls |
| `-k missing_vendored_runtime --tb=short` | 1 failed: enabled gate downgraded to v1 rc1 | 3 passed with preceding recovery controls |
| `-k 'relative_path_executable or extensionless' --tb=short` | 3 failed: all unbound approvals returned 0 instead of 2; relative-PATH probe executed from the actual target cwd | 6 passed with existing script/cwd/generated controls |
| `-k python_option_separator --tb=short` | 2 failing subtests: direct/generated Python `-- -c` script accepted | 5 passed, 2 subtests passed with closure controls |
| `-k 'seed_driver_marker or gate_recomputes_quality' --tb=short` | 1 failed, 1 passed: supported custom scorer migrated to invalid Bash | 3 passed with unsupported custom-driver control |

The first relative-PATH test attempt incidentally refused from the helper's
cwd and was not accepted as proof; the fixture was corrected to launch
approval from the target, then witnessed the exact regression. No existing
assertion was weakened or skipped. The composite control now requires the
specific `quality composite mismatch` diagnostic; threshold mismatch is not
used as a proxy.

Supported-shape restrictions are conservative implementation bounds, not new
policy semantics or Accepted-ADR amendments: absolute PATH for bare
executables; declared Python script entrypoints/simple flags or inline code;
no module/separator/unsupported interpreter inference; generated script
entrypoints absolute/pinned. Missing gate-side runtime refuses v2 with null
run ID before invocation, never a v1 success or fabricated gate attestation.

The historical 28-test runs above must not be read as verification of the final
deliverable.

## Reviewed epoch before the final typed-domain audit (historical)

After the complete review recovery, the orchestrator ran:

```sh
uvx pytest -q skills/spec-oracle/test_required_gate.py \
  skills/spec-oracle/test_oracle_overlay.py skills/spec-oracle/test_checks.py \
  skills/quality-gate/test_gate.py skills/quality-gate/test_unpriced_oracle.py \
  scripts/test_build_host_packages.py scripts/test_scaffold_runtime.py \
  scripts/test_verify_install.py skills/quality-gate/test_skill_surface.py --tb=short
PYENV_VERSION=3.9.19 python3.9 skills/spec-oracle/test_required_gate.py -q
uvx ruff==0.15.17 check skills/quality-gate/{required_runtime.py,gate.py,test_gate.py} \
  skills/spec-oracle/{test_required_gate.py,checks.py,oracle_overlay.py} \
  skills/scaffold-init/scaffold.py skills/agent-loop/loop.py --output-format concise
python3 scripts/build_host_packages.py --check
```

**491 passed, 64 subtests passed**; actual Python 3.9.19 **36 passed**;
pinned Ruff and all three generated-host drift checks **pass at that epoch**.
Compliance, craft and arch cleared the migration fix at that point. The later
typed-domain and legacy-byte audit below supersedes this epoch, not its
historical executed results. Reviewers were read-only and did not claim to
execute tests or recompute hashes: the orchestrator owns execution evidence.

| Source file at that historical epoch | SHA256 |
|---|---|
| `skills/quality-gate/required_runtime.py` | `61ec2e4d8bd5007a6d9d126975a2fd85f4383dab23a8e70a308c0cbedeb29edd` |
| `skills/spec-oracle/checks.py` | `f6435132834b4850a66cdef97f40de72b44df72712865b3dd285e3a7610edf67` |
| `skills/spec-oracle/oracle_overlay.py` | `637cd98026ad80d33b3be2dd86e792db02df7c73539f6d0ffad5d8ae6e5cd606` |
| `skills/quality-gate/gate.py` | `5c469d1cd547c851ff0ec94b544519ac44feea3bb613b54a6986b263f476b0c2` |
| unchanged `templates/oracle.sh.template` | `730a73e374db5f5004758a3fbb9af2a27caf1e4e3dcba3fb4d9e624622e0d7df` |

## Initial durable examples (historical epoch)

At that epoch CLI examples were emitted into session artifacts, not a
production target or a new repository attestation:

`files/035-01-installed-fixture/` (vendored clone-portable fixture) and
`files/035-01-emitted-gates-initial.json` (archived actual outputs/index). These persist in this
implementation session's artifacts directory; exact component references in
the records resolve there. The temporary source fixture was cleaned. No
watcher/service remains running.

| Control | Run ID | Overall outcome |
|---|---|---|
| High quality, zero weight, THRESHOLD=0, required contradiction | `60d9c98e-3f43-4892-98df-92979fee2151` | 1 / required_constraints_failed |
| Required pass and quality pass | `b5746f40-b0d8-46bb-8071-8c36b6f67d71` | 0 / pass |
| Passing component, failed quality threshold | `4babcfd1-621f-4f83-ab5c-854ef715d7bd` | 1 / quality_below_threshold |
| Approved fragment drift | `a3ff025b-a0f4-4558-aa8a-1395266b96e9` | 2 / required_evidence_unavailable |

Each overall schema2 artifact is
`.servo/gate-runs/<run_id>/gate.json`; component schema1 artifacts are
`spec/oracle/demo/runs/<run_id>/result.json` when available. The fixture's
approved fragment was restored after the drift control, not reapproved or
weakened; its earlier refusal record remains honest. These are executable
contract fixtures, not Vellum C1/design observations or served/current-delivery
attestations. Coordinator owns final cross-repository integration.

## Reconciliation recovery and selected-parent manifest

The first reconciliation verdict was `needs-changes`: remaining unconditional
v1-only stateless/exit-1 wording, a stale generated board/current-state
paragraph, and the helper's inherited `main...HEAD` inventory were not yet
reconciled. Live skill/architecture wording now distinguishes default v1 and
enabled v2; the active spec describes pickup rather than claiming all slices
still DRAFT. The installed board helper was rerun and `check-board` passed.
Generated-host and skill-surface documentation checks then passed:
`uvx pytest -q skills/quality-gate/test_skill_surface.py
scripts/test_build_host_packages.py --tb=short`: **73 passed, 52 subtests
passed**. These documentation corrections changed no runtime byte in the preceding
historical source-epoch table. The final audit below subsequently changed
runtime/scaffold bytes.

The slice comparison is the selected parent
`a383c8761afaab010f133207876d1c6f01ff2b2e`, not local `main`. This closes the
inventory by a git diff over every tracked/staged path; new implementation
files were staged before the audit. The helper's stale-local-main comparison
also names inherited CONTRIBUTING/CHANGELOG, plugin/release configuration,
release workflows and older decision/spec records. Their selected-parent
delta is empty; they are deliberately excluded, not silently reconciled or
attributed to 035-01.

Canonical selected-parent manifest (all dispositions **updated**):

| Area | Explicit paths |
|---|---|
| Install contract | `.claude-plugin/install-contract.json` |
| Public/live documentation | `README.md`, `docs/architecture.md`, `docs/memory/learnings.md` |
| Required gate | `skills/quality-gate/gate.py`, `skills/quality-gate/required_runtime.py`, `skills/quality-gate/SKILL.md`, `skills/quality-gate/test_gate.py` |
| Approved checks/overlay | `skills/spec-oracle/checks.py`, `skills/spec-oracle/oracle_overlay.py`, `skills/spec-oracle/SKILL.md`, `skills/spec-oracle/examples/required-policy.md`, `skills/spec-oracle/test_required_gate.py` |
| Existing installation seams | `skills/scaffold-init/scaffold.py`, `skills/agent-loop/loop.py` (sibling vendor only) |
| Selected spec directory | `spec.md`, `plan.md`, `tasks.md`, `slice-01-installed-required-gate.md`, `implementation-receipt.md` under `docs/specs/035-required-evidence-alongside-quality-scores/` |
| Actual review evidence | `reviews/slice-01-{frame-critique,readiness,compliance,craft,arch,reconciliation}.md` under the same selected spec directory |
| Derived board | `docs/specs/README.md` |

Generated paths are the following explicit relative files beneath each of
`hosts/claude/`, `hosts/codex/plugins/servo/`, and `hosts/copilot/.github/`:
`skills/agent-loop/loop.py`,
`skills/scaffold-init/scaffold.py`,
`skills/quality-gate/{SKILL.md,gate.py,required_runtime.py}`,
`skills/spec-oracle/{SKILL.md,checks.py,oracle_overlay.py,examples/required-policy.md}`.
Also updated are `hosts/claude/README.md` and
`hosts/codex/plugins/servo/README.md`. Every generated path was rebuilt, never
hand-edited.

Unchanged/excluded: all Accepted ADRs/closed records, original default
`templates/oracle.sh.template`, 035-02 and all spec036 files. No convention or
unrelated release configuration was changed. The memory team advisory was
skipped for this bounded run without introducing people metadata or a
permanent suppression marker.

## Final typed-domain and legacy-byte recovery

After the first reconciliation pass, the final carrier audit witnessed
Python's `True == 1` / `False == 0` / `2.0 == 2` aliases accepting malformed
result domains. Exact command:
`uvx pytest -q skills/spec-oracle/test_required_gate.py -k
result_domain_types --tb=short`. The initial probe produced **4 failures**:
floating schema version, boolean overall exit/count, and boolean component
required count. Follow-on independent review and bounded probes exposed
component exit aliases, empty-policy string scores/weights, boolean composite,
unbound scalar references and oversized JSON integers. Each was run red
before its fix; oversized threshold/weight/score integers yielded **3
OverflowError subtest failures**, now normalized to explicit refusal rather
than a crash.

The final implementation reuses the existing canonical serializer for typed
pin/required/overall comparisons, validates overall and component numeric/
exit domains before arithmetic, refuses unbound scalar references, and
normalizes conversion overflow with a narrow exception. No schema change,
generic validation framework or approval relaxation was added.

A separate AC6 probe,
`uvx pytest -q skills/spec-oracle/test_required_gate.py -k
legacy_oracle_comment --tb=short`, witnessed legacy gate **1 instead of 0**
from a non-UTF8 Bash comment, then forced re-scaffold **1 instead of 0**.
Only ASCII marker probes now use replacement decoding (oracle and manifest);
required JSON/artifacts still parse strictly. The control proves both a v1
passing invocation and explicit forced restoration of a scalar install;
required-policy force refusal remains covered.

### Final executed validation and byte identity

Same targeted command as the preceding epoch, additionally including
`skills/scaffold-init/test_scaffold.py`, produced **556 passed, 2 existing
shellcheck-unavailable skips, 76 subtests passed**. Actual Python 3.9.19 ran
**39 passing tests**. Pinned Ruff, regenerated Claude/Codex/Copilot drift and
whitespace checks passed. Compliance, craft and arch were independently
refreshed for these final bytes; reconciliation covers the updated chronology.
No runtime change followed this final execution.

| Final canonical runtime | SHA256 |
|---|---|
| `skills/quality-gate/required_runtime.py` | `4388400a23dcd918561b3edc155c9da7606ffa3b9bec02dd8f04c4cdcfde2d42` |
| `skills/scaffold-init/scaffold.py` | `0f71376806bc9b40eecce7223d4d476f145f05eec5c1058f3662001bb0bf5132` |
| `skills/spec-oracle/checks.py` | `f6435132834b4850a66cdef97f40de72b44df72712865b3dd285e3a7610edf67` |
| `skills/spec-oracle/oracle_overlay.py` | `637cd98026ad80d33b3be2dd86e792db02df7c73539f6d0ffad5d8ae6e5cd606` |
| `skills/quality-gate/gate.py` | `5c469d1cd547c851ff0ec94b544519ac44feea3bb613b54a6986b263f476b0c2` |
| unchanged `templates/oracle.sh.template` | `730a73e374db5f5004758a3fbb9af2a27caf1e4e3dcba3fb4d9e624622e0d7df` |

### Final durable invocation examples

The existing fixture was explicitly regenerated, reapproved and installed
with the final reviewed vendored runtime. Its archived initial index stays
historical; `files/035-01-emitted-gates.json` now indexes these actual final
invocations and their exact gate digests:

| Control | Run ID | Exit / reason |
|---|---|---|
| High quality, zero weight, THRESHOLD=0 veto | `266536f3-3824-4bac-bad3-a16f53757026` | 1 / required_constraints_failed |
| Required + quality pass | `0e6b8486-b25f-410a-97d7-6b925b57b16d` | 0 / pass |
| Component pass, quality fail | `4bd18584-2087-4af9-b9ea-1746ff2f53b7` | 1 / quality_below_threshold |
| Approved artifact drift | `3afec893-96a7-4541-b4c8-c0cb8767f751` | 2 / required_evidence_unavailable |

Final fixture policy identity:
`sha256:a058bbb626dd8360bd19ccb7efa79e63b0d89da3b374023ce60b291fc26ac123`.
The passing gate's exact byte digest is
`sha256:432186d0e0abcc90a67c38a01ead6f23157ce5f528fe4f581276ca63be65915d`.
Artifact paths remain the installed fixture's
`.servo/gate-runs/<run_id>/gate.json` and
`spec/oracle/demo/runs/<run_id>/result.json`. The approved fragment was restored
after the refusal control; no policy was weakened to pass. These remain
standalone assertion fixtures, not real design/source/build attestation.
