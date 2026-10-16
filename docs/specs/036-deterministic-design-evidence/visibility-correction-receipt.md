# 036-01 required-title visibility correction

**Historical correction checkpoint.** Its later corrected-source actual proof
is pinned in [the settled closeout receipt](settled-closeout-receipt.md);
normal full review/lifecycle records govern acceptance.
Fresh full compliance, craft and architecture reviews of the combined 6d5e5b6
source all returned `needs-changes` for one reproduced AC2/AC4 defect: a
zero-height `overflow:hidden` ancestor could fully hide the required title while
the observer reported it visible. No additional material blocker was found in
that review batch. The coordinator explicitly assigned this active-slice fix
to the isolated closeout branch; no other source writer was active.

The earlier [678-artifact proof](implementation-receipt.md#immutable-final-proof)
remains genuine evidence of source 6cc759e, not of this correction. All 678
hashes were rechecked unchanged. Standard full-slice verdicts remain nonpassing
until fresh approved fixed-epoch proof and required reviews clear.

## Narrow change and semantics

Only canonical `card_capture.py`, focused `test_card_capture.py` and their
official generated mirrors change executable/test behavior. The observer
intersects text rectangles with ancestor padding-box overflow clips on applicable
`hidden`, `clip`, `scroll` and `auto` axes. A fully clipped required title is a
named conclusive failure, not an acquisition error or invented missing value.
At least one positive-area rectangle per text node must survive; partial
clipping alone does not claim the text is wholly invisible. Existing complete
card-frame, hidden-descendant, transparent-colour, paint-effect and
`display:contents` checks remain.

This adds no glyph/OCR, arbitrary mask/transform/occlusion certification,
generic visibility framework, platform, policy knob, schema or controller.
Targets, tolerances, references, required membership, quality dimensions,
exclusions, threshold and user-selected model policy are unchanged.
No Accepted ADR, DONE 035 record or convention is amended.

Exact corrected `skills/design-eval/card_capture.py` raw SHA-256:
`55fbc0cb87dff08c7c7a396c2dc33c39fd2995287c62e751ab49ca336e9fcecd`.
At the 09f0879 checkpoint, all seven other canonical producer files retain
their integration-parent bytes. A later separately assigned quality-budget
extension permits an explicitly approved same-definition A/B allowance; the
09f diagnostic records below are not relabeled as proof of that later code.

## Witnessed regression and bounded independent reviews

Artifact root:

```text
/Users/ramboz/.copilot/session-state/5d2cb165-c016-4993-aded-7f2669f2fe6f/files/
```

`title-overflow-repository-red.txt` records the installed Jig `tdd.py run`
against `test_card_capture.py`: exactly sixteen new normal/open × zero-width/
zero-height × overflow-mode subcases failed; existing and restoration controls
passed. After the minimal predicate correction,
`title-overflow-repository-green.txt` records 12 browser tests / 34 subtests
passing. Both used the pinned Python 3.14.0 / Playwright 1.64.0 / Chromium 156
runtime, with browser tests explicitly enabled, not skipped.

| Actual receipt | Raw SHA-256 |
|---|---|
| `title-overflow-repository-red.txt` | `9a02809b39fb4a792a00726a33020f1725d05e77d5704f1a39e5e18a02279ca2` |
| `title-overflow-repository-green.txt` | `609487bdce08290f80756031598d6bb930d8efa9cc85b06a9de4c953e34912a7` |
| `overflow-source-review.txt` | `a7163f6f2860f1da9e611e4ea04e633a3119aeeef89a599e5c5fdc260f19e3c9` |
| `overflow-policy-review.json` | `e8f6a57a512ba4c49bb35cd2e36c16a18c624f542c86c4eef6efe781bd296873` |
| `overflow-driver-review.txt` | `7ce84d922b7090b93120e6115f58292bbb394b55d3e6677129be5b31fde4fd59` |

The fresh read-only source reviewer passed only the surgical patch and prepared
diagnostic definition, directly inspected both C1 reference PNGs, re-enumerated
the unchanged catalogue, and checked copied code/targets/build/delivery.
A separate exact staged-driver reviewer inspected all 28 full-oracle input
pins, the real wrapper and 3,883 current runtime pins. Those narrowly scoped
passes do not replace standard whole-slice compliance/craft/arch evidence.
The current runtime manifest is new; its count is not relabeled as the prior
3,887-entry manifest. Both reviewers inherited default models.

## Actual installed diagnostic and restoration

Target: `overflow-installed-control/` under the artifact root. Canonical
prepare, actual independent policy approval, recorded re-enumeration/freeze,
generate, approval, seal-driver, exact-driver review, final approval and install
ran in order. No hand-authored approval shortcut or altered oracle wrapper was
used. Policy review binds
`sha256:c4b47835c69366adfbb00b2f01629eb9e935a2760fd4a96448fa283160372742`.
The full installed oracle hash is
`fee6e6d6adc0de660b986fcfc8122859c7fd9a325df5ab1d4c2620d56f502c97`.

| Control / run | Actual required result | Overall installed gate |
|---|---|---|
| Fully clipped title / `46ab1fb7-45e9-443c-8c51-36eeee0a56e6` | 16 pass, 12 named title failures, 0 unknown | exit 1, `required_constraints_failed`, explicitly synthetic diagnostic quality 0.99 despite `THRESHOLD=0` |
| Restored unchanged baseline / `d67ee1eb-bcf4-4ea3-a450-61c95b3cb7e5` | 28 pass, 0 fail, 0 unknown | exit 2, quality unavailable; no fabricated live success |

Both normal/open raw observations show clipped title `visible:false` versus
restored `visible:true`; acquisition remains available. Raw title text remains
`Trailhead`, not a substituted default. The candidate was rebuilt and selected
delivery independently updated between runs without reapproving design targets.
Clipped delivery passed `verify-current` before restoration; the selected
current delivery is now restored and its own `verify-current` also passes.
The earlier negative is preserved history, not claimed current-delivery success.

`overflow-control-receipt.json` binds exact overall/envelope hashes, raw title
observations, two repeated pure consumer reads for each record, reviews and
test receipts. Raw SHA-256:
`2523a01ea3bcd2ef8cbb8ca373121183fc07361b659b769f2bb63a7132defffa`.
Reproduce its read-only audit from this worktree with:

```sh
python3 -B /Users/ramboz/.copilot/session-state/5d2cb165-c016-4993-aded-7f2669f2fe6f/files/audit_overflow_controls.py
```

Audit program raw SHA-256:
`1b72ce176bb4480479a27c494b8154454c39667de4c55bd7a0f36ba87b3361e4`.
`overflow-restored-current.json` raw SHA-256:
`b2f5fb93d7dc5c393d524c8b837aa2bee8df3ec16bb1f55ba590a5863ed49706`.
All 49 inherited claim files remain byte-exact; **zero new judge calls**.
The prepared diagnostic allowance field is not permission to use its eight
unused slots. Actual diagnostic mode does not invoke a native judge.

## Current-source validation and remaining gates

`overflow-current-card-tests.txt`: 49 tests pass, including all 12 real browser
tests, without startup-path overrides or skips. Raw SHA-256:
`a1faaf63191907f8aae3350cb006d03079492236c001163e0261819d730e6fd3`.

`overflow-current-carrier-readback-host-tests.txt`: 402 pass / 123 subtests
through the same focused carrier/consumer/host selectors as the initial
receipt. Raw SHA-256:
`7ddeb7eff841aeb858ee8e38e419353e47013c4b92cd008e3de1366e3076953b`.
These overlap earlier selectors and are not a new aggregate coverage count.
Scoped Ruff, official host regeneration/drift, manifests and diff checks pass.

An initial combined pytest attempt retained `PYTHONPATH` to import the
session-local pytest into the pinned browser interpreter. Two existing
environment-guard tests correctly rejected that startup override; they were
not weakened. Clean-environment card unittest and separate carrier pytest
commands above pass. The same attempt caught a new README repository-docs
relative link; it was corrected to the existing host-portable GitHub-link
pattern and hosts regenerated. No unrelated source fix was made.

At this checkpoint the standard three full-slice verdicts remained
`needs-changes`; the later44a proof is separate, not rebound to09f.
Only after that proof and required full reviews pass may reconciliation and
normal REVIEWED → RECONCILED → DONE proceed. There is no waiver, merge,
036-02 advancement, Jig119 completion or general accuracy claim.
