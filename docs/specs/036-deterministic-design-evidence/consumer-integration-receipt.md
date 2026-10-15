# Supporting 036-01 consumer readback integration

This checkpoint closes the declared-output readback seam between 036's producer
and 035-02's completed consumers. It is **not** a whole-slice verdict, new live
design evaluation, delivered-build attestation, or Jig DONE. 036-01 remains
IN_PROGRESS under `servo-live-card-evidence`; primary036 owns final producer
proof and reviews, and the parent owns final integrated source-epoch acceptance.

## Bases and ownership

| Item | Exact identity |
|------|----------------|
| Selected 036 parent | `servo-live-card-evidence` at `5440b63458bf862d4fe0b19e274db18c38c170aa`, draft [#43](https://github.com/ramboz/servo/pull/43) |
| Completed consumer merged locally | `servo-required-verdict-consumers` at `4412a9aef47226f7ed9b339cb12aa2f380a437c6`, [#42](https://github.com/ramboz/servo/pull/42) |
| Local merge commit | `f4cd22bae3d1cf3ca2969ed4b7c45676117d0e57` |
| Supporting branch | `servo-capture-readback-integration` |

The parent was checked both locally and through the live PR API at this exact
head. README conflicts preserve both pilot and consumer guidance, learning
conflicts retain both entries, and the board/generated hosts were regenerated
from merged canonical source. No upstream worktree/branch or GitHub PR was
merged or rewritten. No closed035 record, Accepted ADR, convention, primary036
standard review, or producer-owned runtime symbol was manually edited.

## Scoped contract and implementation

The named acceptance surface is 036-01 AC6/7's immutable run/output bindings
through the existing 035-02 interface (AC1/4/5/6). This lane does not claim
all of either slice's ACs anew. The existing full 036 readiness/implementation
records remain authoritative for their own scope.

`gate_consumer._validate` first retains its existing overall gate byte/run,
installed policy/driver, component byte/identity, source/config, evaluator/
runtime/artifact pins, complete config content hash and live fragment checks.
When that frozen plan declares `result_artifact`, it requires the exact evidence
ID inventory and calls:

```python
pins.validate_output_references(check, evidence, run_id, target)
```

`check` is the complete pinned producer check, `evidence` the published component
row, `run_id` the validated overall UUID, and `target` the resolved approved
project base. There is no caller-selected subset, design-kind dispatch,
`validate_component`, comparison/grade recomputation, recapture or execution.
Declared non-required output is still bound; undeclared legacy behavior is
unchanged.

The producer's existing pure helper owns contract/version/run/path, manifest,
complete inventory and exact-byte hashing. Missing/partial/unlisted/duplicate/
foreign-run/symlink/escaping/changed output refuses with `env_error`, exit2,
`required_evidence_unavailable`, no completion composite and a concrete
`consumer_error`. Original `oracle`, exact `gate_ref`, and raw failure/refusal
reasons remain available. An honest acquisition refusal may lack output or
component refs; it stays unknown, never borrows an earlier pass. Live acceptance
alone uses exclusive `consumer-accepted.json`; immutable report rereads do not
claim another execution.

This validates published byte closure, not design meaning or independent current
delivery. The collector owns those meanings; a gate/output closure alone is
not Jig's delivered-build attestation.

## Witnessed TDD and targeted checks

Receipts live in the integration session's
`/Users/ramboz/.copilot/session-state/4c3292b7-48fb-43e0-92be-83e01a6d9ac0/files/`.
Counts below overlap and must not be summed as unique coverage.

| Receipt | Executed scope and result |
|---------|---------------------------|
| `readback-red.txt` | Jig `tdd.py run . --test skills/quality-gate/test_gate_output_readback.py::test_postpublication_output_mutation_refuses_with_original_gate[capture-command]`: one witnessed failure; mutated capture still returned0 before the fix. |
| `readback-green.txt` | Jig targeted TDD helper: 26 postpublication mutation cases pass for both command families. |
| `readback-extended.txt` | Intermediate35pass/1fail: new pure-argument test expected macOS `/var` spelling instead of the API's resolved `/private/var` base. Expectation corrected to `.resolve()`; no existing guard weakened. |
| `readback-targeted-tests.txt` | `uvx --with pytest-subtests pytest -q skills/quality-gate/test_gate_output_readback.py skills/quality-gate/test_gate_consumers.py skills/spec-oracle/test_result_artifacts.py skills/spec-oracle/test_required_gate.py`: 252pass/50subtests. |
| `readback-final-consumer-tests.txt` | Final output-readback file after the additive craft-nit test: 45pass; production implementation bytes unchanged from the252pass cut. |
| `readback-runtime-tests.txt` | `scripts/test_build_host_packages.py`, `test_scaffold_runtime.py`, `test_verify_install.py`, `test_copilot_installed_runtime.py`, `test_docs_install.py`: 148pass/73subtests through targeted pytest. |
| `readback-python39.txt` | Both affected consumer files on Python3.9: 78pass/26subtests. |
| `readback-python39-additive.txt` | Final additive residual-inventory case on Python3.9: 1pass. |
| `readback-source-checks.txt` | Scoped Ruff0.15.17, official host drift, Jig board, whitespace, and original producer hashes pass. |
| `readback-test-quality.yaml` | Canonical integration diff only; all three advisory quality signals false. Helper-generated whole-branch metrics are not this checkpoint's scope. |

The 45 new installed-fixture cases cover capture/envelope mutation, partial/
missing/unlisted/duplicate/foreign/escaping/symlink output, exact full raw
evidence inventory, missing references, live replay versus repeated reporting,
failure/refusal retention, optional declared output, truthful missing
acquisition output, final triage downgrade without rewriting inbox/history,
sticky later unavailability, source config drift before validator use, and
generated Claude/Codex/Copilot plus goal-vendored reader parity. The additive
craft-nit case proves both valid and omitted non-required residual evidence
in a mixed plan, with no residual judge invocation.

Tests freshly generate/approve/install synthetic command fixtures with current
merged producer bytes. Their capture bytes are not design/browser/judge
evidence. Deliberately malformed carrier fixtures and restored throwaway
capture bytes are explicit tests, not rewritten historical producer records.
No model/judge command or actual design scoring was invoked.

## Genuine historical readback, not a new producer epoch

`readback-historical.py` reads the exact handoff at SHA-256
`e1f27950e91c4dbbcb91a766eb7c01eb5987d17e8c931913b26d580124a6c42c`,
disables bytecode writes, forbids subprocess/grading calls, and compares every
file's path/hash across each original target before/after two readbacks.
`readback-historical.json` records full unchanged inventories and exact refs.
It does not call live acceptance, rewrite paths/IDs, or create markers there.

| Identified run | Original authority preserved by readback |
|----------------|------------------------------------------|
| `545a9dd5-805f-4f79-a695-bc9ff6faf63f` | Historical prior-budget-helper positive remains pass0. Gate hash `25d33087cdf680b728a6a7031a3ee85915dca99e656a19fcb4321aeba0bec013`; envelope `91b756eaa45d1d818fdb1121587ad6e6bbf8e9986afb8a224b95edf55d85e012`. **Not** the final current canonical producer positive. |
| `01ec10a8-62fe-448a-81d7-25c06a0e45a7` | Fixed component-pass/quality-fail remains fail1/`quality_below_threshold`. Gate hash `f7da633743bdfcec81442ec676ea359bad157f63b6af42d4898503cf45b3412d`; envelope `957bc02dee7e65a8ca1f6b61aa0cb4a5406bfc99264e34c9b06983fdaabda45d`. |

Both original trees are unchanged; no negative is represented as new live
judge evidence.

## Current-helper genuine positive readback

Primary036 subsequently supplied the current-helper handoff at raw SHA-256
`8a4a03edf38e30556979d9a3e4dc7bc0d0cd0cd195ed13e70e90cd2ac785c8a7`
with source head `5440b63458bf862d4fe0b19e274db18c38c170aa`.
`readback-current-positive.py` read the identified actual run
`b6e14da1-40da-4e76-b37d-580eb3e82844` twice using the consumer's pure read path:
pass0, all28requiredpass, composite0.9675/default0.8. It forbids subprocess/
grading and disables bytecode writes. The whole original target inventory
is unchanged in `readback-current-positive.json`.

| Bound artifact | Exact raw SHA-256 |
|----------------|-------------------|
| Overall gate | `be85185ee007a71c3c6551978c413087fc1ace327ede477d3a8292aac506c369` |
| Component | `adc6fb8b550a98c091a0f95ac062188f67b9fbc106b25c4f6414932caf487637` |
| Design envelope | `524727c7c0b2a7e973f3fbfa19ac67fca95ee7722a51ee0b95b2d188c02b96a0` |

Only its output tree was copied into an explicitly disposable session fixture.
The producer's pure validator accepted the untouched copy with the original
complete check/evidence/run, then independently refused copied `normal.png`
and envelope mutation. Original carrier/reference bytes, paths, run IDs and
frozen evaluator locations were not rewritten. These copied negatives are
pure reference controls, not newly executed or judged producer evidence.
This current-helper read does not close primary036's full controls/reviews,
prove final independent current delivery, or attest Jig completion.

## Source closure and review boundary

All hashes are raw SHA-256. Canonical and generated consumer bytes agree:

| File | Hash at reviewed cut |
|------|----------------------|
| `skills/quality-gate/gate_consumer.py` | `ecb98a8c630463ac69c687590dbcc8b40cbda1eca82f9fe85b0b1b0e46075507` |
| `skills/quality-gate/test_gate_output_readback.py` | `9f015ea22f6ebfd956072344ef51fb1916dc149dde9637cc7b1533b640def41c` (final additive craft-nit test) |
| `skills/quality-gate/required_runtime.py` (unchanged) | `3291ce7c7746eef341dc0c5856a1fbb0f74baeab9c086d79383139769a644072` |
| `skills/spec-oracle/checks.py` (unchanged) | `1dc07210e5977bca2f08f2d0620b99aa1d51240035b2c02108238b4c09e3eb27` |
| `skills/spec-oracle/oracle_overlay.py` (unchanged) | `e5ada618c06d7dc3131b33f712bc0161fb41aa7c3089181cd2b1e3e93d2549d0` |

Fresh scoped [compliance](reviews/integration-readback-compliance.md) and
[craft](reviews/integration-readback-craft.md) independently pass. One nonblocking
craft test-coverage suggestion was addressed additively, with no production-code
change. Fresh scoped [reconciliation](reviews/integration-readback-reconciliation.md)
also passes, including the additive test and current-helper readback receipt.
These verdicts live separately as `reviews/integration-readback-*.md`, never over
primary036's `slice-01-*.md` verdicts. The normal review helper has no supporting-
checkpoint output path; its generated prompt is used, but `record-review` is
not allowed to overwrite the primary owner's whole-slice evidence.

## Scoped reconciliation and remaining parent work

**New upstream finding after scoped review:** primary036 identified that the
`score_design_fidelity` SEED wrapper is not included in `evaluator_artifacts`
at selected source5440, while the generic driver identity strips SEED blocks.
The recorded actual runs used the reviewed real wrapper, but do not establish
the forthcoming exact-wrapper drift guard. Primary036 owns sealing the final
installed `oracle.sh` bytes through existing evaluator-artifact pins and
explicit staged-driver review/reapproval. No pure API/schema or consumer-byte
change is requested here. Neither b6e14da1 nor01ec is rebound or represented
as proof that this new guard already exists.

- Updated: shared consumer reader, focused tests and live quality-gate guidance;
  generated hosts through the official builder only.
- No-op: producer core/driver threshold, final bundle/target/policy identities,
  closed035 records, Accepted ADRs/conventions, independent current delivery,
  primary036 lifecycle and its standard full-slice reviews.
- Deferred to parent/primary036: refresh this integration on the final settled
  036 head including the exact installed-driver seal; freshly approve any
  fixtures affected by frozen producer-byte
  changes; rerun the scoped checks on that exact final source; complete the
  full 036 AC/review/source-epoch proof and Jig119 interop using genuinely
  current positive/refusal records. No full compliance or DONE is claimed here.
- No new module boundary or design decision: this calls the already accepted
  producer-owned pure API and preserves consumer authority. No ADR or
  convention change is needed for this supporting seam.
