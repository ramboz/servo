# 036-01 corrected-source closeout evidence

The corrected evaluator has four preserved real-quality outcomes and fourteen
separately approved installed diagnostic controls. This is fixed-card,
trusted-local evidence, not production/general design accuracy, convergence,
provider-internal attestation or completion of another project's lifecycle.
Full-slice review and reconciliation records, rather than this summary, govern
the helper transitions.

## Source, inputs and authority

Frozen executable source:
`44a96d9549cd73f8a8ea3e1307157cb994b138ac`, closeout branch
`servo-card-slice-closeout`, stacked on selected integration parent
`6d5e5b66c7f3ed796c7cbbbafdb84012e2e29cb5`
([#44](https://github.com/ramboz/servo/pull/44)).
This includes the sealed producer and completed 035-02 consumer; no upstream
PR merge is required or performed. Subsequent closeout edits are documentation,
review and lifecycle records; executable bytes remain frozen.

| Corrected helper | Exact raw SHA-256 |
|---|---|
| `skills/design-eval/card_capture.py` | `55fbc0cb87dff08c7c7a396c2dc33c39fd2995287c62e751ab49ca336e9fcecd` |
| `skills/design-eval/card_quality.py` | `c43480df5dfab358fd52764a6d65db5aeef0a2085383dba6b718c870c6b5210c` |

Other producer/carrier/consumer executable bytes match the selected integration
source. The closeout audit compares all eight producer files to 44a96d9 and
the official host builder checks derived bytes. C0, approved C1 `release-r3`,
Vellum revision `55dd18007cd5664be17c1e7c4666fd1f00dd93d6`, producer-verifier
hashes and 14 IDs per state are unchanged from the accepted checkpoint in
[plan.md](plan.md#036-01-accepted-readiness-checkpoint-2026-10-15).
Accepted ADR-0044 and DONE 035 records are untouched. 036-02 stays DRAFT.

Overall `gate_result` schema2 is completion authority, including quality;
`required_component_result` schema1 and `design_evidence` schema1 are subordinate
same-run, content-bound records. Pure consumer readback checks immutable
artifact closure without executing the evaluator or re-grading.

## Immutable evidence indexes

All paths below share the read-only producer artifact prefix:

```text
/Users/ramboz/.copilot/session-state/e33c1f8d-6be8-4fb4-8801-6cfe7838aa5c/files/
```

| Index or manifest | Exact raw SHA-256 | Scope |
|---|---|---|
| `final-44a-proof-manifest.json` | `0f74f234b331c82b7696b8a1b94bb7e32cde4178e1123a2cdad136761ff35daa` | Final source/authority link across both current bundles and preserved history. |
| `final-proof-44a96d95/proof-index.json` | `9afd90f6ea456f177ab9019fcac3abff63b038f79c736a0507e53ff52064d83e` | 667 indexed read-only artifacts; four actual runs, 32 raw native answers, 12 independent definition/driver/context record pairs. |
| `property-controls-44a96d95/proof-index.json` | `b17b5effa6a4f3082d2d1b1d6170d9bacbef1d6de00e73c3f6fd5455b9c545d1` | 465 indexed read-only artifacts; fourteen actual installed no-judge controls. |
| `final-proof-6cc759e/proof-index.json` | `45a2df047e05d1dab67982a4b4a0280607537cf78094ad71fcd70b217bb2b2fc` | Unchanged 678-artifact historical source epoch, not relabeled as corrected-source proof. |

Each current live case binds a pre-run selected context, independent policy/
full-driver review, raw approved checks, quality definition, source references,
complete input/output/runtime closure and independently selected current
delivery. Its full audit has 4,177 matching bindings, including all 3,887 nested
runtime pins, and zero mismatches. Counts describe separate audits, not an
aggregate coverage metric. Full oracle bytes, including the quality SEED, are
pinned through existing evaluator artifacts and checked against the snapshot
actually read by `required_runtime.py:740-745`.

## Four genuine live outcomes

All use unchanged quality threshold0.8, approved references, dimensions,
exclusions, four judgments per state and `native-default` CLI decoding.
Exposed usage identifies `claude-opus-5`; it is CLI-reported metadata, not
attestation of provider weights. Exactly32 new judgments50-81 inherit49
consumed attempts for81 total. Closeout performs zero new native calls.

| Case / run | Required pass/fail/unknown | Actual quality | Overall gate |
|---|---|---|---|
| A / `6e4e0161-4f6b-468a-8aed-b640d1c1d4fd` | 28/0/0 | 0.9660566243270259 | pass, exit0 |
| Comment-only changed-build B / `73e576b5-7c3e-4d91-94f7-63fbc65d95b3` | 28/0/0 | 0.9675 | pass, exit0 |
| Fixed misalignment / `87c11ed1-1616-475f-9de1-98399db6bcf2` | 28/0/0 | 0.515 | fail, exit1, `quality_below_threshold` |
| Title20.01px / `e79fc2e0-de8d-4bf0-9da5-12e1045ba495` | 26/2/0 | 0.97 | fail, exit1, `required_constraints_failed` |

A and B use byte-identical grading config, policy, approved checks and full
oracle. Their source/build/current delivery differ only by the preselected
comment; actual captures are byte-identical. An actual `verify-current` check
refuses old A against selected current B without rewriting A's passing record
or running a judge. B is the current selected delivery; A is historical.
The stale-A receipt is `baseline/old-a-current-b-refusal.json`, raw hash
`781970400be9dc5b7afb5b81f3a40be12acfcc12806f3ff400eecbb48129d713`.
This proves one bounded renewed evaluation, not generalized convergence.

| Case | Overall gate raw SHA-256 | Design envelope raw SHA-256 |
|---|---|---|
| A | `5bdad5bed8e5a9ceecfb21eefa50c24487fed0887c609a898afec5fbd4ff78aa` | `907ca02221d7b215743577c86b6c69e160dc764b0ad6a3c547620f614a3c202b` |
| B | `6c07f525e488f2a89d192623000e72d115a170458733e38da289d54e5e9aa0f1` | `cd21290dfd45f351e8eec583c1e0848fb84b831b9a40c9574ebfff1f13ec0dbc` |
| Misalignment | `6c71a313aa5d4f6ad602c318cec789192de5b17bd3a34d36195cf1b0c2f1d22c` | `580055d7552584270110535bef78a71b70d385582a52971e797f49376d1d29e4` |
| Title20.01px | `fc628261c746383819d2326eb6027bdc86de6ed6e9850aa3a5e7f9a53d399158` | `8f8734cb91e5238576ee09af9291fc41e2ab4975fc4ccb3d054cb7e771a9947a` |

## Fourteen current no-judge controls

The separate target uses explicitly reviewed diagnostic mode. Every0.99 here
is **synthetic diagnostic quality**, not live fidelity. All contradiction
controls run at `THRESHOLD=0`; no new claims/judgments are consumed, the existing
81-claim history/private counter remains unchanged, and cap89's spare slots
remain entirely unspent.

| Actual installed control | Required counts | Overall result |
|---|---|---|
| Matching baseline; restored matching baseline | Each28pass/0fail/0unknown | Each exit2: required facts pass, quality unavailable; never fabricated success. |
| Band colour; title monospace; title weight700; title size24; band242/card240 | Each26pass/2fail/0unknown | Each exit1, named required veto despite synthetic0.99. Band raw geometry is242 while card stays240. |
| Missing title; fully clipped title | Each16pass/12fail/0unknown | Each exit1; observed missing/hidden title is conclusive failure, not unavailable acquisition. |
| Ambiguous title binding | 6pass/10fail/12unknown | Exit2; known failures remain visible beside unavailable evidence. |
| Missing root binding | 0pass/0fail/28unknown | Exit2 with unavailable binding. |
| Duplicate, missing or extra unapproved check ID | Each0pass/0fail/28unknown | Each exit2 from frozen approval/inventory guards; not claimed as reapproved target semantics or kernel coverage. |

The index binds all fourteen actual overall gate records. Eleven acquired runs
also publish component/envelope/raw-observation/capture closures; the three
unapproved-ID guards refuse before those records exist, so their component
references are intentionally unavailable. The index preserves selected
candidate/output/delivery bytes and restored frozen inputs.
Both baseline and restored `verify-current` controls pass. The raw closure audit
hashes all3,887 runtime entries, nine copied helpers,43 frozen evaluator-artifact
pins, all fourteen overall records and the eleven available output closures;
zero mismatches. Unavailable component output is not invented for early refusal.
The eleven exported freshness controls remain explicitly 6cc history; current
source has its focused drift/replay regressions and actual A/B freshness proof.

## Acceptance map and review scope

| AC | Final evidence |
|---|---|
| 1 | Real installed A/B pass, source/policy/full-driver approval records and ordinary install/reinstall/draft-refusal regressions. |
| 2 | All28 approved IDs in both states, bound band-specific geometry, exact typography/text/colour/typed-family declarations and separate raw facts/comparisons. No old140px/Inter or rendered-face inference. |
| 3 | Actual normal/open acquisition, observed `opened` subtitle, measured card crop and outside-crop driver provenance, plus real browser action/crop regressions. |
| 4 | Current actual colour/family/weight/size/band/absence/fully-clipped installed vetoes, genuine high-quality20.01px veto, exact comparison controls and real browser geometry/action/text visibility regressions. Earlier separate-build wrong-text/broken-action controls remain historical; current focused kernels/browser tests preserve these comparisons. Exact +/-1.01 arithmetic and measured +/-1.02 browser controls account for Chromium quantization without changing approved tolerance. |
| 5 | Actual ambiguous/missing binding and unapproved-ID refusals; focused unsupported version/type/source-approval/tolerance/non-finite/partial/ownership regressions. Missing required facts are unknown; observed absent title is fail. |
| 6 | Independent pre-run roots/full closures, loaded response bytes and current-delivery inventories, actual staleA/currentB refusal and freshly evaluated B, driver snapshot seal plus focused source/resource/capture/replay controls. |
| 7 | Raw immutable same-run state/capture/component/envelope digests, complete inventory, repeated pure merged-consumer readback, explicit comparison policies, no scalar override. |
| 8 | Existing shared/vendor install semantics, guarded uninstall regressions, official generated-host parity and documented fixed-card local support. No new registry/DSL/controller. |
| 9 | Real component-pass/quality-fail, overall pass, high-quality required-fail and installed refusal records with component digests. Jig119 consumes preserved overall authority separately; its DONE is not a prerequisite or claimed here. |

## Validation and independent readback

Closeout artifacts remain outside the package:

```text
/Users/ramboz/.copilot/session-state/5d2cb165-c016-4993-aded-7f2669f2fe6f/files/
```

`multi-batch-card-tests.txt` proves60 current card tests, including all12 real
browser controls on pinned Python3.14/Playwright1.64/Chromium156, without skips.
`multi-batch-carrier-host-tests.txt` proves402 focused carrier/readback/install/
host tests plus123 subtests. `multi-batch-counter-green.txt` proves23 quality
tests/38 subtests; native replies there are mocked and not live evidence.
Exact hashes and red-to-green history are in the
[allowance receipt](multi-run-allowance-receipt.md).
Counts overlap and are not aggregated. Scoped Ruff, official host generation/
drift and manifests pass. No type/build tool was added to this Python plugin.

CI on44a96d9 exposed ambient `LD_LIBRARY_PATH` from `actions/setup-python` in
two startup-guard unit tests, masking their intended Node/`.pth` assertions.
The test-only correction isolates their environments and adds explicit
LD_LIBRARY_PATH/LD_PRELOAD/DYLD refusal assertions without changing production
behavior or frozen helpers. A CI-like local red reproduces four failures;
the corrected full evidence-test file passes20 tests/14 subtests under that
same ambient variable. `ci-loader-isolation-red.txt` and
`ci-loader-isolation-green.txt` raw hashes are respectively
`585aa1323f29a2b7f8aa1e0f60fe6df756213725eb5f5d886b9567a5236b4ca8`
and `5f2a1f08db8b23ab94d305bfee3fdf6bfd857695e1c765dba24bd6431bc510a4`.

| Independent closeout audit | Exact raw SHA-256 | Executed scope |
|---|---|---|
| `settled-live-audit.json` | `1a099cf3da39a59ad126e4ae78f0f230b269cc110896d30ac32c42e98f171820` | Rehashed all667 indexed read-only files,32 raw answers and12 independent record pairs; verified eight current producer files and all four4177-binding audits; pure consumer read each actual gate twice with subprocess execution forbidden. |
| `settled-property-audit.json` | `433a2dcab3703420cb4e9cf83c16174c065ae34f139b04ec9885d1bb40a6767b` | Rehashed all465 indexed read-only files, full closure/restoration and manifest; pure consumer read all14 actual gates twice and checked clipped-title/band242 raw observations. |

Audit programs `audit_settled_live.py` and `audit_settled_properties.py` have raw
hashes respectively
`1983363baca0efb2fd257c68d300e1f36069bda71352fc209508a7952b0c549e` and
`62e327ef56fd7403351d3a522cf9053c424b88f68217d76f0489da7c4ad204f6`.
They execute no evaluator, reserve no attempt and recompute no score.

Historical nonpassing full reviews and narrower source/driver passes remain
in Git history and separate supporting records. Fresh standard full compliance,
craft, architecture and reconciliation verdicts now pass at the normal
`reviews/slice-01-*.md` paths. They were generated through installed Jig,
reviewed independently in sequence and durably recorded; normal lifecycle gates remain separate, not implied by the review verdicts.
The declined alternative richer craft skill is advisory telemetry, not a waiver.
No closed record, Accepted ADR or convention is
amended; no judge permission is inferred from an unused cap. Figma, user
real-design validation,036-02 and downstream Jig/Vellum completion retain
their existing owners.

The test-only CI correction is commit
`19b9cca`; remote CI run
[`38917312236`](https://github.com/ramboz/servo/actions/runs/38917312236)
passes both Python3.9 and3.12. The runtime/evaluator remains exact44a.
The coordinator's independent raw integration report is
`/Users/ramboz/.copilot/session-state/61f2e313-f28a-403a-9433-724268681e33/files/final-44a-parent-verification.json`,
raw SHA-256
`e553e8df69c3481874a5e5536b541b55cdce1080f82c582a06725c4ce59b87b5`.
It independently checks all current/historical sealed files, current runtime,
32 raw native answers and36 repeated pure reads across18 overall records.
It is supporting integration evidence, not a substitute for any required
independent review or another project's DONE gate.
