# Visibility/2 conformance correction

This corrects the finite APP guard's CSS classifications without changing
SOURCE facts or adding rendering support. Real browser primitives and a scoped
independent mechanism review were complete at this source-only checkpoint.
Fresh exact policies, definitions and native experiments were then required;
their subsequent separate authorities/results are recorded in the
[current pilot evidence](static-app-pilot-evidence.md). This source-only receipt
itself is neither an APP approval nor a lifecycle PASS.

## Preserved failure and scope

Final compliance found that the old guard incorrectly required every ancestor
to have computed `visibility:visible`. CSS descendants can override inherited
hidden visibility. The related HTML `hidden` shortcut was also incorrect when
CSS supplies display. The old marker hidden-negative case has native raw
visibility true and an 8x8 box but the old guard emits hidden failure.
Its original bytes/outcome, full `c2c9...` index, parent `d38...` byte
verification and genuine compliance NONPASS are preserved.

A fresh source-only mechanism review then identified applicable clipping-box,
effective fill, hard-absence precedence and unsupported-shadow ordering errors.
These were reproduced in real browser primitives before correction, not
silently waived or represented as passing reviews.
Source/C0/family primitives, original approvals, goal inventory, zero tolerances,
generic native526 and output kind/schema are unchanged.

## Corrected finite contract

Visibility profile
`scoped-dom-text-ancestor-overflow-and-paint-intersection-app/2` is explicit in
the effective policy. Computed visibility is read at the bound element and
each text-node parent; HTML `hidden` alone does not prove lack of paint.
Overflow/paint/content-visibility checks require an applicable container, not
`display:contents` or ordinary non-replaced HTML inline client geometry.

Applicable boxed/inline zero opacity, actual display suppression and
content-visibility suppression remain known absence. Independent known absence
survives an unrelated unsupported effect; unsupported transform geometry alone
cannot establish absence. Missing text fragments retain their conclusive
classification regardless of unrelated unsupported-fragment order.
Text uses effective fill, while shadows, strokes and text-clipped backgrounds
remain explicitly unsupported and refuse before zero-fill inference.
No shadow/stroke rendering, OCR, pixel fidelity or accessibility support is
introduced.

Nondefault opacity on computed `display:contents` is a narrowly declared
uncertainty: native `checkVisibility(checkOpacity:true)` reports false while
the primitive PNG is byte-identical to its visible control.
This is UNKNOWN for affected required IDs and vetoes completion, not guessed
PASS or conclusive hidden FAIL. Ordinary inline zero opacity really hides even
when its client dimensions are zero; the rule is not generalized to all
zero-sized ancestors. Independent hard absence still wins.

## Exact source and real TDD

Retained artifact root **A** is
`/Users/ramboz/.copilot/session-state/43b73062-3958-42e3-879f-4f588494ff00/files`.
The supporting snapshot context
`A/visibility2-correction-source-context/context.json`, SHA256
`45583d0a4b515f4ab1ccc1ad1119dae3c4c38975e4282f4f508b3dfb54e17f0f`,
retains exact current source/test/control bytes and raw red/green pointers.

| Reviewed working-tree artifact | SHA256 |
| --- | --- |
| `skills/design-eval/static_contract.py` | `2cfe1022de458a3a00b7a43eea572bc5f53ef3f3e12956b549c787a24d213d0d` |
| `skills/design-eval/test_static_browser.py` | `57ec6525adcc05ffc0f15074d9130a9ea8d515e1e1becbb2c869ea538a6706de` |
| New `A/static-candidate-control-visibility2.py` | `38b7dc0ee9d5875aac0e0af6848dac68bfd0b5f76d4fe063ecf5fbb2bee23a92` |

`A/036-03-visibility-override-red.txt` witnesses the original real-browser
override failures against old helper `58a92958...`.
Further actual reds are retained as `036-03-visibility2-mechanism-red.txt`,
`036-03-visibility2-additional-paint-red.txt`,
`036-03-visibility2-applicability-red.txt` and
`036-03-visibility2-fragment-order-red.txt`. These were working-tree TDD
witnesses, not retroactively pinned APP definitions.

The final opt-in browser module passed all three methods in 13.905 seconds:
37 explicit real-CSS matrix variants, sixteen prior capture/settlement/
selector variants and the geometry-only empty-role control. Native CSS and
actual browser APIs are used, not mocked visibility flags.
Raw result: `A/036-03-visibility2-final-mechanism-green.txt`.
The pure observer suite passed ten tests plus 26 subtests; package/pure-surface
checks passed 83 tests plus 78 subtests. Full current-suite validation is a
separate checkpoint, not inferred from these focused runs:
`A/visibility2-full-pytest.stdout` records 2570 passed, fifteen skipped and
316 subtests passed in 386.96 seconds. The three opt-in browser methods above
were executed separately, not counted as passing because of their skips.

The opacity diagnostic is
`A/visibility2-boxless-opacity-primitive/native.json` plus its six PNGs:
contents opacity0/opacity1 and boxed opacity1 are byte-identical
`f000940c...`; boxed/inline opacity0 are white `d2d044c8...`.
The related existing-property applicability probe is
`A/visibility2-content-visibility-primitive/native.json`: contents/ordinary
inline content-visibility does not hide in this pinned browser; boxed hidden
does. These are repository-only CSS primitives, not APP/SOURCE acceptance,
model judgments or quality scores.

## Scoped independent review and next authority

Fresh reviewer `jig:reviewer`, agent
`433370e6-267a-4dcc-8068-707745c5c08e`, first returned needs-changes, then
returned PASS after the actual correction/TDD batch.
Raw records are `A/036-03-visibility2-mechanism-needs-changes.txt` and
`A/036-03-visibility2-mechanism-pass.txt`. Its pass covers only the mechanism/
control intent. The reviewer read source and retained evidence; it did not
rerun tests or independently recompute supplied hashes. The orchestrator's
matching-byte snapshot binding is disclosed, not attributed to the reviewer.

Old controller `bea834e5...` and all frozen 07/02 files remain unchanged.
The new controller repairs intended hidden negatives with explicit
`display:none` and preselects real inherited-visibility/hidden-attribute
override positives with the same frozen goals. It must receive exact
policy/control-plan review before any new APP result.
New 08/03 policy approval, installation and empirical results are not
established by this source-only receipt.
At this source-only checkpoint the existing Jig pure-consumer negative had
not run. The subsequent actual bounded format refusal is linked in current
pilot evidence; it stops before semantic/tree/delivery validation and does not
establish a positive 0.2 bridge. Jig remains NONCLEARING.
Full-app, face, backend, visual-quality and merge acceptance remain outside
this correction.

### Versioned controller R2 addendum

The first source-only controller `38b7dc0e...` remains unchanged.
`A/static-candidate-control-visibility2-r2.py`, SHA256
`0f6bbbf5b1cd350b194b28ddb0d3f7205ed400a8c89fa2c5dff46aad9145a7bc`,
adds only two proposed native marker controls and provenance:
contents/nondefault-opacity UNKNOWN must veto even if all eleven other facts
pass; adding actual `display:none` must retain the four known marker failures
instead of erasing them with contents uncertainty. The fifteen SOURCE goals
and comparison policy are unchanged.

The same independent reviewer returned a scoped controls-only PASS at
`A/036-03-visibility2-controls-r2-pass.txt`; it did not recompute the supplied
SHA or execute either candidate. Expected vectors are exactly 11 PASS/4 UNKNOWN
with exit 2, then 11 PASS/4 FAIL with exit 1. These are pre-result expectations,
not new empirical outcomes or approval to execute.
