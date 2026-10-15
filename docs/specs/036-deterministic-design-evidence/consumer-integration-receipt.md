# Supporting 036-01 consumer readback integration

This checkpoint closes the declared-output readback seam between 036's producer
and 035-02's completed consumers. It is **not** a whole-slice verdict, new live
design evaluation, delivered-build attestation, or Jig DONE. 036-01 remains
IN_PROGRESS under `servo-live-card-evidence`; primary036 owns final producer
proof and reviews, and the parent owns final integrated source-epoch acceptance.

**Current supporting source:** the final-source sync below imports exact
recovery `6cc759e807cab5411363b44c19c58e7a457b3715`. Earlier sections retain
the original c197421/pre-seal source chronology and hashes; their former
"current-helper" run b6e14da1 is not the current sealed-driver epoch.
No historical run has been rebound to satisfy a later guard.

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

## Final-source v4 sync (2026-10-15)

### Exact merge and preserved ownership

The parent authorized one same-worktree/same-[PR44](https://github.com/ramboz/servo/pull/44)
sync of recovery `servo-execution-seal-recovery` at
`6cc759e807cab5411363b44c19c58e7a457b3715`
([PR45](https://github.com/ramboz/servo/pull/45), based on5440).
The existing integration head `c1974210a707ffdd3cfbd0a829398b5357f600a7`
merged that exact commit without conflicts as
`298a38a962bfafb1bffbfe730ba3290cf971c3c2`.
The official builder and board helper ran afterward; the board was already
current. No upstream checkout or branch was modified, no PR was merged, and
no recovery-owned symbol was manually changed. Whole036 remains IN_PROGRESS.

The recovery's producer code and tests match its exact source commit.
`gate_consumer.py` and its45-case integration test file remain byte-identical
to c197421. The only `required_runtime.py` delta from5440 is the
producer-owned check against the bytes actually read into `oracle_bytes`,
including any full `oracle.sh` evaluator pin, before its decoded snapshot
is interpreted. The existing pure output validator and its caller are not
duplicated or changed.

| Canonical source | Merged raw SHA-256 |
|------------------|-------------------|
| `skills/quality-gate/gate_consumer.py` | `ecb98a8c630463ac69c687590dbcc8b40cbda1eca82f9fe85b0b1b0e46075507` |
| `skills/quality-gate/required_runtime.py` | `f0f9d90cf7c0f25c5f7163966ae9cfd8010261522f9842438da67622aa858bfe` |
| `skills/spec-oracle/checks.py` | `1dc07210e5977bca2f08f2d0620b99aa1d51240035b2c02108238b4c09e3eb27` |
| `skills/spec-oracle/oracle_overlay.py` | `e5ada618c06d7dc3131b33f712bc0161fb41aa7c3089181cd2b1e3e93d2549d0` |
| `skills/design-eval/card_bundle.py` | `8e39ae545c8acc726d4310ece587bebc847bbb247a1eafeaf70e9f412a46a5ff` |
| `skills/design-eval/card_capture.py` | `00176691125c53a584696c4f9da18885ef36dec75136f2eb30fd7610385b1a9d` |
| `skills/design-eval/card_evidence.py` | `210f86ab64ff67b00de5da04fc731ec689d2c5de1c1373948d08b882cadafc82` |
| `skills/design-eval/card_install.py` | `c553b2138a7f813120ae1cd9558c9c387c82cd1a0d98ca54071df0beb3968efe` |
| `skills/design-eval/card_quality.py` | `2ac7fe51addce4c5c9199155aaf7b77d1b86574878747e1e510c69ad3e79787f` |

These source hashes are verified by `v4-source-checks.txt`, including exact
Git comparisons against recovery6cc759e and consumerc197421. Generated
Claude/Codex/Copilot bytes and the goal vendor use the normal mechanisms.

### Independently pinned v4 context

Parent records are under
`/Users/ramboz/.copilot/session-state/61f2e313-f28a-403a-9433-724268681e33/files/`.
They describe diagnostic/no-judge preflight, not final live-quality proof.

| Parent artifact | Exact raw SHA-256 |
|-----------------|-------------------|
| `036-v4-definition-review.json` | `01cb81caad1f440a493287d04e6c811bd6c483b45fc496e2a12b5aea53d0e9ed` |
| `036-v4-final-driver-review.json` | `a623255c50e694f3c73a45a804ce2b3035a0ab77916d3d63708cbf99f868a7ad` |
| `036-v4-nojudge-controls.json` | `a466faa8d1391c10997d19c1f31865275e85a36f7d937c2e5d111aa19650ab6d` |
| `036-v4-frozen-context.json` | `8f9a1b2d29572bc9f8d1cd5bb1e067ef5c08906cd73eebc9ed832ebe91c23a54` |

The original target is
`/Users/ramboz/.copilot/session-state/b4480ab8-e29f-4eae-acf0-c7e65d2c0d31/files/closure-preflight-v4`.
The proof independently checks each supplied root pin, complete approved
binding, copied helper bytes versus merged source, all3887 declared runtime
file hashes, and that all28 checks declare the final `oracle.sh` exactly once.
Its exact raw driver pin is
`7c3e521312730ba615ea7979cbc06d709c887e17f262e887e65c23b9bbe5c741`;
current approved `checks.json` is
`9463b4ed14ff63b25100531e2ca0ccf8062cdb95478a8001937efff29fd4c533`.
The staged-driver review's earlier draft-checks hash is intentionally different:
ordinary approval/install added the approved binding, as pinned separately by
the parent's frozen context. This is not an approval rewrite.

The independently selected current `delivery/index.html` raw hash is
`5a201b048d73b1097e88f3bd29fc5b6e2274b6bf8122e21d64135e4d9af9b4f5`.
Re-enumeration equals the pinned output inventory, not just a self-echoed ID.
The baseline envelope's build equals the independently pinned selected build;
the input identity includes both complete input files and the recipe, and
the output identity binds the complete output list. Input/output domain
hashes are respectively
`4df8efca843324076adb70ec0384060c55aa7184842ba08bbc983a22b3e31f81` and
`741a360ceccb349803716cc1c0800754861487055440396da42effe5c8c34639`.
This is a bounded hash-only context check, not a new browser acquisition,
execution or Jig attestation.

### Actual preserved no-judge readback and copied-only controls

`v4-pure-readback.py` blocks subprocess execution, grading and publication,
disables bytecode writes, and uses `consumer.read` twice per exact record.
It writes only its own session receipt. Every read retains original overall
payload, exact `gate_ref`, reason and component refs, with no `consumer_error`:

| Original control / run | Readback authority preserved | Exact gate raw SHA-256 |
|------------------------|------------------------------|-----------------------|
| Matching required, quality unavailable / `a8201dd8-03c3-4a75-9eaa-b34b32dec695` | 28requiredpass, overall refusal2; diagnostic quality cannot establish a positive run | `f42ad71badd5394382ae866adadc149915243d6111bfecb22389a6802b00da1b` |
| Changed real wrapper / `317ddd80-e6b3-41d4-a455-201386c517fb` | Refusal2, no component refs; unknown remains honest | `1f8bc700eb806c24beaa45b30d33bc13a12cfbfd0b83e4950c2b6a4cb1f8ac6a` |
| Unpinned Node startup / `c83db5a6-11f4-4f01-a80d-bc0f73c5c1ed` | Refusal2, all28unknown | `de3e28bf87f8e5135438dea953822d6c1c08aefce8c724268f3e22d4075e5d0c` |
| Font24 / `2ddb484e-477e-4c68-af0e-ac8810471c1e` | Required veto1 despite synthetic0.99/THRESHOLD0; both title-font-size IDs fail | `3f4778aa711dde0ee8dbe55e284830745a1a394ca3a01eaa36a5ad7e82bf7292` |

The entire107-file original target inventory, claims and all four parent
receipts remain unchanged. No live-acceptance marker is written. A complete
disposable target copy retains the original frozen definitions/references;
the pure validator accepts its untouched output. Separate copied `normal.png`
and `evidence.json` byte edits then refuse. Copied `oracle.sh` mutation refuses
against the entire frozen evaluator-input pin list, not a fabricated subset.
These are copy-based pure-helper/pin controls, not new producer runs or claims
that a modified original was executed. The disposable copy is removed.

The exact script/receipt raw hashes are respectively
`1a1999b12dbb2a241295b7e4fc2c66c9c58cea7242084917a5c63b9da336ca2a`
and `a8222161557a33e5ce0ca8ed9257e189005a89ceb8bd2d29fa1f9833b04a095c`,
stored as `v4-pure-readback.py` / `v4-pure-readback.json` in this integration
session's files directory. `v4-pure-readback.txt` records the successful
command. Scratch proof initially omitted the recipe from its input-identity
assertion; it was corrected to the existing `card_bundle.py` contract
`{"files": inputs, "recipe": recipe}`. No production source or original
record was changed to satisfy that probe.

### Targeted validation and scoped review

| Receipt in integration session files | Merged-source result |
|--------------------------------------|----------------------|
| `v4-targeted-tests.txt` | `uvx --with pytest-subtests pytest -q` over both consumer files, `test_result_artifacts.py`, `test_required_gate.py`, and `test_card_{evidence,install,quality,capture}.py`:291pass/68subtests,10 explicit live-browser opt-in skips. No live judge commands; quality tests use mocked native replies. |
| `v4-runtime-tests.txt` | Same five targeted package/install/runtime files as the original checkpoint:148pass/73subtests. |
| `v4-python39.txt` | Python3.9 over both consumer files plus `test_result_artifacts.py`:215pass/26subtests. |
| `v4-source-checks.txt` | Scoped Ruff0.15.17, official host drift, board, whitespace, exact recovery/consumer source comparisons and raw hashes pass. |

Commands explicitly prepend `/opt/homebrew/bin` to PATH after the resumed
app environment omitted `uvx`; no dependency manifests or installed packages
were changed. Counts overlap and are not summed with previous epochs.
This is a source merge, not new hand-authored runtime behavior, so existing
regressions and the original witnessed red/green remain distinct from the
new v4 readback controls.

Fresh [source-sync scoped review](reviews/integration-v4-source-sync.md)
passes, covering the exact merge, unchanged consumer, preserved snapshot seal
and truthful v4 control/receipt reconciliation. It is recorded separately
from both prior integration verdicts and primary036 whole-slice verdicts.

### Remaining boundary after source/readback closure

The formerly pending exact-source seal sync is now imported and checked.
There is no new consumer/core API gap or schema change at this checkpoint.
All v4 actual outcomes remain refusal/veto, never an invented overall pass;
historical25 judge calls are unchanged. Old545a, b6e14da1 and01ec are not
relabelled as proof of the final sealed-driver guard.

Final live-quality runs are a separate parent-controlled lane. Full036
acceptance criteria, compliance/craft/architecture/reconciliation and lifecycle
closure, plus Jig119 delivered-revision interop, remain primary/parent-owned.
Neither source synchronization nor these no-judge records claim full
compliance, final live proof, production acceptance or DONE.
