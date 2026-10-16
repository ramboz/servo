# 036-01 settled-source implementation and proof receipt

**Current acceptance: blocked.** Full reviews of this 6cc759e proof epoch found
and reproduced the visible-title ancestor-overflow defect. The authorized
[narrow correction](visibility-correction-receipt.md) has fresh red/green and
installed diagnostic proof. A later separately authorized
[repeated-run allowance](multi-run-allowance-receipt.md) now supports explicitly
approved same-definition A/B proof with monotonic local consumption.
Both need affected actual-quality proof and full reviews before lifecycle
completion. The three preserved runs below remain
genuine 6cc759e observations, not proof of the corrected evaluator.

The bounded Trailhead card has three preserved, genuine installed-gate
outcomes: overall pass, component-pass/quality-fail, and required-fail despite
passing quality. This receipt distinguishes that sealed-source evidence from the
earlier unsuccessful reviews and diagnostic epochs. It is not a Jig119
attestation, production acceptance, general accuracy or convergence claim.

## Selected source and ownership

Closeout branch: `servo-card-slice-closeout`, selected integration parent
`servo-capture-readback-integration` at
`6d5e5b66c7f3ed796c7cbbbafdb84012e2e29cb5`
([#44](https://github.com/ramboz/servo/pull/44)).
It combines sealed producer
`6cc759e807cab5411363b44c19c58e7a457b3715`
([#45](https://github.com/ramboz/servo/pull/45)) and the 035-02 consumer cut
`4412a9aef47226f7ed9b339cb12aa2f380a437c6`
([#42](https://github.com/ramboz/servo/pull/42)).
At that selected parent, the eight producer files in the source table of
[the integration receipt](consumer-integration-receipt.md#exact-merge-and-preserved-ownership),
excluding its additional consumer row, match 6cc759e byte-for-byte. Subsequent
review caused the separately authorized capture/test correction linked above;
at 09f0879 seven other producer files remained unchanged. The later allowance
extension additionally changes only `card_quality.py` and focused tests.
No upstream PR merge is a
prerequisite or performed.

C0 and C1 use the accepted checkpoint in [plan.md](plan.md#036-01-accepted-readiness-checkpoint-2026-10-15):
Vellum `55dd18007cd5664be17c1e7c4666fd1f00dd93d6`, independently approved
`release-r3`, 14 required IDs per state and the pinned producer verifier.
Proposal-era pending prose in the overview is historical; it does not revoke
that accepted checkpoint. Accepted ADR-0044 and DONE 035-01 remain unchanged.
036-02 regional image evidence remains DRAFT.

## Immutable final proof

Read-only proof root:

```text
/Users/ramboz/.copilot/session-state/e33c1f8d-6be8-4fb4-8801-6cfe7838aa5c/files/final-proof-6cc759e/
```

`proof-index.json` raw SHA-256:
`45a2df047e05d1dab67982a4b4a0280607537cf78094ad71fcd70b217bb2b2fc`.
Its 678 indexed files include the actual receipts, preserved overall/component/
design records, native replies, source/capture/build/delivery inventories and
nine independently supplied definition/driver/context records. Each case's
`full-closure-audit.json` reports 4,175 matching bindings, including 3,887
nested runtime-file pins, with zero mismatches. These are three separate
audits, not an aggregate coverage claim.

| Fixed case / run | Required pass/fail/unknown | Actual quality / threshold | Overall authority |
|---|---|---|---|
| `baseline` / `cbe6b5b3-a60f-4dc1-abb9-23a8fd6f48a2` | 28/0/0 | 0.97 / 0.8 | pass, exit 0 |
| `misalignment` / `2de07bf5-fc61-482d-bcf8-1dbc11ec2d5e` | 28/0/0 | 0.5278427304671842 / 0.8 | fail, exit 1, `quality_below_threshold` |
| `required-failure` / `78963609-9c1f-4602-aa41-3b7129c60476` | 26/2/0 | 0.9675 / 0.8 | fail, exit 1, `required_constraints_failed` |

Misalignment changes only preselected title/subtitle translation (120px/40px).
Required-failure changes only declared title size 20px to 20.01px: normal/open
title-font-size fail at explicit zero tolerance. No reference, rubric,
exclusion, sample policy or threshold was tuned to produce these outcomes.
Each run has eight actual native Claude CLI replies reporting `claude-opus-5`,
with frozen `native-default` decoding. The 24 new calls inherit 25 consumed
attempts, including the initial failed authentication attempt, for 49 total;
closeout makes zero judge calls.

| Case | Overall gate raw SHA-256 | Design envelope raw SHA-256 |
|---|---|---|
| baseline | `c4f3d3714d6615fac0d7072904338b0b46992735bfd5c15328c0145e46dcd5b9` | `0d07ec41cdd9dc74deae5cc0ac431decf654192147ae9a4a3ba4f25cd336b17f` |
| misalignment | `3020a4b26677899972b7c99e3d61821f27911ce4677b1f74f7f11045a8b85f07` | `f96865c25384e9a73e234e0cf3335b2632eb5fa0155d046213fa41c22dcd8382` |
| required-failure | `d5ad9b220fefe663d23c68aae9e7a06b0910a133f47b85004bc768395c20b804` | `ee6b14fe8cc28e3b23ed127fe7a532e6cd896492450a921254ef97ea9998c8a0` |

The per-case `pre-run-context.json` and independent context were selected
before evaluation, not extracted from a passing envelope. Their exact
policy/approved checks/full oracle/quality config/source/build/current-delivery
pins are in the index. The full oracle, including the quality SEED, is frozen
through existing `evaluator_artifacts`; the actually read driver snapshot is
checked (`required_runtime.py:740-745`), not merely the later current file.
The three full-oracle raw hashes are respectively
`2f832e981826f09452d99464895512ce2273cec779fa1661259e53936ae49937`,
`8a92fb140ddebe7c107f52af9143bb9a8bacde51ed2486539fe867af32b69dd7`,
`ecef3d352637bdf323dc7c1b965ff70356643acf2f814a93b7d3ecea2493dae5`.

Independently enumerated `delivery/index.html` raw hashes are respectively
`655d86c5a41078701413e1f002904c30b99fdeda1cd795dfe24b9bdebbaa58f9`,
`ac497e6621b968f394f0016923ac38902369451b2fde5e9c7f9fe8f113ea9275`,
`5a478683f8c114b33ed5fbd3732b0b27da967240dc734b43518a409bb90dd88b`.
An unchanged HEAD, URL or echoed identity is insufficient. These records
establish selected local delivery only, not arbitrary hosting provenance.

`nojudge-controls/receipt.json`, raw SHA-256
`554e75297966fbf11a0b4ddd6125875b00dae9146d1b65fca3681356b281248e`,
preserves eleven final-source controls: Node startup/browser environment,
real quality wrapper, dirty source, wrong output, current-delivery drift,
ambiguous binding, copied capture/envelope/unlisted-output mutations, and old
tree replay under a new invocation. Copied pure-readback refusals are labeled
separately from actual installed-gate refusals. Known failures survive beside
unknown observations. Original live bytes and selected current delivery were
restored exactly; final `verify-current` records exist for all three cases.
`preapproval-guard/receipt.json` separately preserves draft-driver refusal.

## Acceptance evidence map

This map points reviewers to evidence; independent verdicts, not this map,
clear the lifecycle gates.

| AC | Current deliverable and proof |
|---|---|
| 1 | `card_install.py` prepare/approve/generate/seal/install sequence; immutable baseline installed overall pass and preapproval guard. Reinstall/draft and threshold controls in `test_card_install.py`, `test_required_gate.py`. |
| 2 | All 28 final envelope rows retain approved source IDs, observed values and explicit comparison/normalizer/tolerance. Band-specific bindings, exact text/colour/weight and typed family controls in `test_card_evidence.py`; no card-width substitution or rendered-font-face claim. |
| 3 | Final normal/open raw observations, crop and loaded response bytes; actual state/crop/hidden-text controls in `test_card_capture.py`. Open driver remains outside reference crop. |
| 4 | Final genuine high-quality 20.01px required veto, exact arithmetic/absence/hidden/text/family comparisons, real browser missing-title/no-op/band-width geometry controls, and installed required-veto selectors. Earlier twenty separate-build diagnostic controls remain historical, not relabeled as final-source live runs. Pure exact +/-1.01 comparisons and measured +/-1.02 browser controls account for Chromium geometry quantization without changing policy. |
| 5 | Final actual unavailable/browser/binding/refusal records; required inventory, missing tolerance, finite-value and ownership regressions in `test_card_evidence.py`, carrier output/refusal controls in `test_result_artifacts.py`. |
| 6 | Three independent pre-run roots/full closure audits plus final drift/replay controls. `card_bundle.py`, `card_capture.py`, `card_evidence.py` and exact driver snapshot checks; output closure is revalidated by the merged consumer. |
| 7 | Complete immutable raw/state/capture trees and per-constraint envelopes; same-run component digests beneath gate schema2. Repeated pure merged-consumer reads preserve exact payload and gate reference with no execution/re-scoring. |
| 8 | Existing ordinary shared/vendor installer, guarded uninstall, generated-host/runtime selectors and documented bounded support. No new registry, DSL or controller. |
| 9 | All three genuine overall verdicts above, digested component records and current pure readback. Jig119's actual attestation is downstream-owned, not a prerequisite or claimed by Servo. |

## Initial closeout validation on the combined source

These receipts precede the visibility correction. Its own current-source
receipts are recorded separately; the earlier audit's eight-file comparison
is historical and intentionally not rebound to changed capture bytes.

Local receipts are under
`/Users/ramboz/.copilot/session-state/5d2cb165-c016-4993-aded-7f2669f2fe6f/files/`.
They are not added to the installed runtime.

| Receipt | Executed selector and result | Raw SHA-256 |
|---|---|---|
| `closeout-card-browser-tests.txt` | Pinned Vellum `.venv` Python 3.14.0, declared browser path and `SERVO_CARD_BROWSER_TESTS=1`; `unittest discover -s skills/design-eval -p 'test_card_*.py' -v`: 47 pass, including all 10 real browser tests, no skips. Quality unit controls mock replies, not live judges. | `6336e9dc846155b26b904362899839d1da8ec918f84493a416eaec200d309fbe` |
| `closeout-merged-pytest.txt` | Both gate consumer files, `test_result_artifacts.py`, `test_required_gate.py` and five build/scaffold/verify/Copilot/docs-install files: 402 pass, 123 subtests. | `6098169c4eda45d110fc72c15a3f406269a3dba4545a1dba93c23943089c73ed` |
| `closeout-scoped-lint.txt` | Ruff 0.15.17 over canonical card/carrier/consumer files and affected tests: pass. | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |
| `closeout-proof-audit.json` | Rehashed all 678 indexed read-only files and nine independent record pairs, verified eight producer files against 6cc759e, and read each actual overall run twice through the merged pure consumer with subprocess execution forbidden: pass. | `96601e028a99dcf50801549d497de3f26a3fa8a3cfb476c245b9d4c068780251` |

The audit program is `audit_closeout.py`, raw SHA-256
`b50f25d9a516b693f4306510af79a0000a3a729178c36152949825bdec2d314c`.
Earlier 261/291/148-case receipts overlap these selectors and are not added
into a new coverage total. No separate type/build tool exists for this Python
plugin; generated-host drift and manifest checks use the repository builders.
Missing pytest/Ruff were restored only into a session-local tools environment;
the read-only pinned browser environment and global installations were untouched.

## Review and remaining boundary

The historical compliance `needs-changes` remains in Git history and the slice's
checkpoint narrative. Its threshold, acquisition-ownership and visible-text
findings received witnessed red-to-green fixes before this source freeze.
The recovery adds tested runtime/native-linkage, cache, image and actually-read
driver closure; it does not retroactively turn earlier runs into proof of
later code. Fresh full compliance, craft and architecture records live at
`reviews/slice-01-{compliance,craft,arch}.md`; reconciliation is recorded
separately by the normal helper before lifecycle completion.

The supported claim is a trusted-local, fixed two-state card with explicit
source/policy approval and independent current-delivery selection. No hostile
co-writer/forgery-proof host or provider-weights attestation is implied by the
hashes or CLI-reported model metadata. Figma, user real-design validation,
036-02, Jig119 completion and Vellum013 integration closeout remain with their
respective owners. No closed record, Accepted ADR, convention or global plugin
configuration is amended here.
