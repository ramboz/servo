# Learnings

> Durable, cross-session learnings captured at the close of specs and bugs.
> One short entry per learning; link the originating record.

## Tooling

### Test runner needs PYTHONUTF8=1 under a C locale

Running this repo's suite with a Python 3.13 interpreter under a `C` locale
(`LANG`/`LC_ALL` unset) raises a spurious `SyntaxError` importing
`skills/spec-oracle/checks.py`, which carries an em-dash in a docstring.
`ast.parse(..., encoding='utf-8')` succeeds — the failure is the
interpreter's source-decoding under `C`, not a real syntax error. Set
`PYTHONUTF8=1` (or run under any non-`C` locale) before invoking
`python3 -m pytest`. Surfaced during spec 019 slice 019-05.

## Spec workflow

### `dependencies:` frontmatter rejects a bare spec number

`workflow.py transition <slice> DONE` refuses with "unknown dependency token
shape" on a bare spec number like `012` — it needs a slice-shape token
(`012-04`) or an ADR (`adr-0024`). This has now bitten two specs (016 and
020): a slice that depends on an *older* spec's already-built code (not that
spec's own DONE lifecycle, which it may never formally complete if it
predates the per-slice DONE-gate machinery) should describe that dependency
in prose (DoR/Goal text), not in `dependencies:` — a bare-spec entry there
either fails the token-shape check, or, if it did parse, would permanently
block `DONE` on an unrelated spec's unresolved lifecycle. Surfaced by spec
020 slice 020-01.

### A shared module copied (not referenced) into multiple targets needs a two-candidate import probe

`skills/_common/` (the ADR-0024 shared frozen-eval harness) is consumed by
skills whose runtime is `shutil.copyfile`d into an arbitrary target's
`.servo/<skill>/` (unlike spec-oracle's `checks.py`, referenced by absolute
plugin-install path and never copied — ADR-0023). A copied file can't do the
jig-idiom `sys.path.insert(parent.parent); from _common import x`, because
once copied its `__file__` no longer sits near the plugin's `skills/`
directory. The working pattern: try a source-layout sibling path
(`../_common/<module>.py`, for when the importing file still lives in its
skill's source directory) then fall back to a same-directory sibling
(`<module>.py`, for when both files were copied flat into the same target
directory) — an existence probe via `importlib.util.spec_from_file_location`,
not a `sys.path` mutation. See `skills/design-eval/score.py::_load_fidelity_eval`
(the first instance) and ADR-0024 / spec 020's slice 020-01.

## Bugs

### Bug 001 — agent-loop masks auth error as plateau

Servo's headless loop shells out to `claude -p`; the **result envelope is a
first-class failure surface**, distinct from the oracle score. A hard invocation
failure (auth / API / rate-limit) still returns *parseable* JSON with
`is_error: true` / `api_error_status`, so "did we get JSON back?" is the wrong
success test — `_invoke_claude` must inspect `is_error` (excluding the legitimate
`error_max_budget_usd` / `error_max_turns` halts) and map a hard error to
`claude_invocation_failed`, not score it into a plateau. See
[docs/bugs/001-agent-loop-masks-auth-error-as-plateau.md](../bugs/001-agent-loop-masks-auth-error-as-plateau.md).

### Bug 002 — agent-loop no permission mode

A headless `claude -p` inherits the host's default (prompt-on-tool) permission
mode, which **denies Write/Edit/Bash unattended**. The loop must forward the
target repo's own committed `.claude/settings.json` via `--settings` so a target
that pre-authorizes its tools runs unattended — but forward *only* the target's
own settings (never a synthesized bypass mode) so host managed policy still
governs. The broader "refuse-when-nested" behavior belongs to ADR-0021 / spec
019, not this fix. Together with Bug 001, this shows the loop is a top-level /
user-run tool, not something to nest inside another sandboxed agent. See
[docs/bugs/002-agent-loop-no-permission-mode.md](../bugs/002-agent-loop-no-permission-mode.md).

### Bug 003 — spec-oracle parser zero ACs on preamble

The AC-section grammar is an interface between the spec author (jig) and servo's
`extract_acs`. The reported "interstitial prose" hypothesis was too broad — plain
prose, italics, parentheticals, and blanks already parse fine; only a **bold
pseudo-heading label** (`**Note:** …`) zeroed the section, because the same
terminator that (correctly) bounds a sibling `**Definition of Done:**` list also
fired before the first AC item. Lesson: reproduce the *exact* trigger before
fixing — the fix (defer bold-label termination until ≥1 item; warn on a
present-but-empty section) is narrower and safer than "skip all interstitials".
A shared, documented AC grammar (suitability + spec-oracle) is the real
follow-up (spec 019-03). See
[docs/bugs/003-spec-oracle-parser-zero-acs-on-preamble.md](../bugs/003-spec-oracle-parser-zero-acs-on-preamble.md).

### Bug 004 — goal-driver parity with the 001/002 fixes

Fixing a defect in one of two parallel code paths leaves a twin in the other.
The bug 001/002 fixes were scoped (correctly) to the loop driver
`_invoke_claude`; the goal driver `_invoke_claude_goal` / `run_goal_loop` had the
same two gaps (settings not forwarded; auth error masked as
`oracle_below_threshold` instead of `claude_invocation_failed`). Lesson: when a
bug lives in a shared concept (the `claude -p` invocation), sweep every
invocation site. The **independent review step** — not the original fix — is what
surfaced the residual, which is the argument for keeping that step even on
"obvious" small fixes. See
[docs/bugs/004-goal-driver-masks-errors-and-drops-settings.md](../bugs/004-goal-driver-masks-errors-and-drops-settings.md).

### Bug 005 — execution-planner blind to the post-ADR-0023 overlay location

A refactor that moves an artifact's canonical location reaches only the call
sites the moving slice enumerated. ADR-0023 / slice 019-02 moved the spec-oracle
overlay from `.servo/spec-oracles/<id>/` to the colocated
`<spec-dir>/oracle/<id>/`, but `execution_plan.py::_load_evaluation_model`
hardcoded its own copy of the old path and was not in 019-02's grounding list —
so it silently kept reading the (now-empty) legacy location and degraded the
plan's `evaluation_model` to `null` for every overlay in the new, default layout.
Two lessons: (1) a **silent** degradation (exit 0, an optional field → `null`)
ships undetected far more easily than a hard failure — the suite even stayed
green because its fixtures fabricated the *old* path, so a location move needs a
test at the **new** location, not merely a swept call site. (2) The
**dependency-free-skill invariant** (execution-planner duplicates rather than
imports across skill-dir boundaries) is why the fix duplicates
`oracle_dir_for_spec`'s dual-path logic locally — which means the same drift can
recur (a duplicated resolver won't follow a future change to the canonical one);
an accepted, logged trade-off. See
[docs/bugs/005-evaluation-model-stale-overlay-path.md](../bugs/005-evaluation-model-stale-overlay-path.md).

## Jig DONE dependency tokens require slice fragments
When transitioning a slice to DONE with this jig workflow version, dependencies frontmatter is validated by token shape. Whole-spec tokens such as 003 are reported as unknown dependency token shape; use the concrete DONE slice token that owns the dependency, e.g. 003-05 for the runner/judge prompt and verdict-parser contract, plus ADR tokens like adr-0003.

## Copilot installation is not native autonomy
Generated Copilot packaging supports independent scaffold/gate consumers. Native runtime is the executing .github directory; native manifest metadata is one parent higher in .plugin. A local directory marketplace loads LIVE and does not prove copied-store discovery. CLI 1.0.96-2 credits are a minimum-30 soft post-response cap, not hard USD enforcement. Native autonomous launch remains refused under ADR-0043; explicit native-default frozen judges use ADR-0040 and do not claim numeric decoding or stable server defaults.

## Review test-class boundaries after parallel merges
PR37 merge placed new Copilot methods in unrelated main-branch permission-wall fixtures, producing ten CI failures despite both branches passing individually. Restore per-class setup/method boundaries, preserve every assertion and production permission-wall guard, and compare collected test counts. Test-only repair restored all397 historical loop tests before the deliberately new native refusal behavior was added.

## Exercise full native consumers instead of transport-only success
Spec034 actual generic emit/install/score exposed an inherited candidate-gather stub that direct judge() success could not reveal. ADR0042 deliberately adds native-only constraint-free component-relativeUTF8 output files, freezing policy/path not movingbytes and recording a coherent snapshotSHA. NativeFAKE_SCORES/ACTUALS must refuse before selection; score injection can otherwise falselylabel unsupported runtime/image paths as successfulCopilot. Actual installed content/design/generic and packagedauthoring proofs stay distinct from fakeCLI fixtures.

## Unpriced markers must follow activation and actual gate call sites
NativeUSDunknown requires mark-before-activation for install and supportedrefreeze, clear-after-successful nonnative approval/removal. Initial launch checks alone missed goal/Routine rawvendoredgate calls; actualcommands nowcarryUSD-budget context while standalonegrade stayscompatible. Heartbeat mustpersist a realchildoutcome/knownUSD before accountinghalt, unlike a predispatch refusal with no outcome. Manifestmarkers are project-owned and not security/exhaustivefinancial attestation; olderAPIaccounting staysseparate.
## Retrospective ceremony must preserve chronology and check sibling identifiers
Small implementation size does not waive servo's expected jig ceremony; do not substitute a lightweight TDD-only path for its spec, independent-review, and reconciliation workflow. Recover implementation-first work with present-time spec/decision gates, genuine independent verdicts, mutation evidence, and reconciliation; never backdate those artifacts. A clean servo clone can lack the ignored local workflow metadata: use migrate.py adopt-layout to restore only its scaffold sentinel rather than bypassing gates or vendoring unrelated machinery. Check fetched sibling refs before publishing provisional identifiers: this recovery retired colliding 032/0038 reservations and uses spec 033 / ADR-0039 instead. See docs/specs/033-heartbeat-handoff-recovery/spec.md for the honest recovery history.

## Required gate closure follows actual invocation paths
035-01 review showed that executable/script hashes are meaningful only for the paths the invocation actually uses: cwd-relative scripts, PATH resolution, extensionless Python entrypoints and option separators need precise bindings or conservative refusal. Preserve complete reviewed assertion artifacts separately from mutable subjects; overall run/digest-bound gate.json, not component pass, authorizes completion. Default scalar behavior remains v1. See docs/specs/035-required-evidence-alongside-quality-scores/implementation-receipt.md and skills/spec-oracle/examples/required-policy.md.

## Bound facts, quality, and acquisition ownership stay separate
036-01 checkpoint: keep measured required facts distinct from a live judge refusal. A visible text container does not establish visible descendant text; check the actual text nodes without rejecting visible display:contents wrappers. Reuse within one gate invocation requires a gate-owned acquisition claim plus an independently preserved exact-envelope receipt, not a relabelled result tree. Bind the reviewed quality threshold into the ordinary oracle default. Preserve failed OAuth responses and their consumed invocation allowance; a new directory does not replenish an owner budget. See docs/specs/036-deterministic-design-evidence/plan.md; this learning does not claim the IN_PROGRESS slice is accepted.

## Retained gate evidence cannot clear later unavailable execution
035-02 review recovery found that preserving the overall gate is insufficient when a later model/gate call fails or is interrupted: persist final availability independently, retain the earlier immutable oracle only as diagnostics, and validate zero-new-iteration resume plus repeated human/JSON report reads. Missing v2 payloads and legacy checkpoints cannot attest newly enabled required policy. Hook fallback paths need shell-safe quoting and non-object JSON needs visible fail-open warnings. See docs/specs/035-required-evidence-alongside-quality-scores/consumer-implementation-receipt.md and skills/quality-gate/test_gate_consumers.py; fixture proof is not served-build or native-autonomy attestation.

## Required text visibility includes ancestor overflow clips
036-01 full review reproduced a fully hidden title that retained an in-frame text rectangle and checkVisibility=true. Rectangular ancestor overflow clips must intersect the text rectangles before visible required facts can pass; surviving positive area is partial visibility, not full glyph or occlusion certification. Keep the witnessed red, old passing source epoch, narrow correction review and new proof separate. A passing fixture does not waive a later independent review blocker. See docs/specs/036-deterministic-design-evidence/visibility-correction-receipt.md; full-slice acceptance still depends on affected proof and normal gates.

## Frozen judge allowance is separate from consumed attempts
036-01 repeat-proof required explicitly approved whole eight-judgment batches under one frozen definition, not a new freeze after every run. Keep default8 and per-run8, freeze the total cap/purpose, and preserve imported history. Mutable consumed-highwater accounting belongs beside claims, with in-run prefix checks, locked next-number/cap enforcement and atomic synchronized persistence; missing/corrupt initialized state refuses rather than refunding attempts. This remains same-trust local durability, not independent authority against a writer replacing both records. See docs/specs/036-deterministic-design-evidence/multi-run-allowance-receipt.md; source review is not actual-quality or whole-slice acceptance.

## Static APP pilot is not visual or application completion
The genuine 2026-10-19 native pilot is recorded in docs/specs/036-deterministic-design-evidence/static-app-pilot-evidence.md. Dashboard20 produced16pass/4fail/0unknown at threshold0; independent marker15 produced15pass. SOURCE and APP family declarations both name IBM Plex first: failures are exact ordered fallback/quoted-generic declaration differences, not actual-face or visual-defect proof. Header failure is exact DOM text including whitespace/case/copy. The marker PASS covers only fifteen selected facts and nontext geometry, not empty APP text, icon meaning, backend truth or full UI quality. Native query exception retained count:null/all six heading UNKNOWN. Mixed instability retained all60 atomics, known marker absence FAIL and changing caption-size UNKNOWN. Source approval, user ADR acceptance, exact APP policy review and sealed pre-result release are separate authorities. Remaining controls/restorations/postreviews and existing Jig0.2 nonclearance stay explicit; never convert this pilot into full-app/Jig DONE. Exact source/policy/raw carrier and independent parent-verification hashes are in the evidence record.

## Bug 006 pin refusals need the original independent authority
An actual native copied-source integrity negative refused2 yet published41rows for20approvedIDs, with secondary NoneType causes hiding the original artifact-modified cause. Reuse the existing check_pins authority before outer component validation; do not posthoc-deduplicate diagnostics or treat valid pins as valid result evidence. Bug006 native temporary-target regressions cover protected artifact/evaluator/runtime drift, exact approved IDs once, original causes, no assertion execution, exactrestorePASS and genuinely missing/malformed component refusals with current pins. Fresh origin/main dc56bd33 lacks the unmerged owning feature; qualified reproduction refers ONLY to exact integrationbase2cd33a4a/runtimef0, not plain-main reproduction or resolution. Raw41row anomaly, actual base red, normal lifecycle red/green and independent bug/craft reviews remain recorded. Existing APP pilot installs/releases are not rebound to fixedruntime526; fresh installed-definition review/release is required.

## Actual native526 APP-path integrity recovery in 036-03
The 2026-10-20 corrected epoch proves Bug006 on the actual approved20-ID Dashboard07 APP installation, separately from six generic two-ID fixture gates. Native baseline96507236 is1/16pass4fail; original protected copied-SOURCE drift1b8ce7bb is2/exact20approvedUNKNOWN IDs once, each original artifact-modified cause, noNoneType/<gate>/APPobservation/acquisitionclaim; byteexactSOURCE385restore then freshAPPf61c7ea0 returns1/16pass4fail. Independent marker02 baseline5a213752 passes only15selectedfacts. Actual immutable repair audit a6367b93 and parent75-row verification0a424673 are linked in docs/specs/036-deterministic-design-evidence/static-app-pilot-evidence.md. Old41row anomaly24a10dd7 and oldf0epoch are preserved, not rewritten. Fresh sealednative526 c664 checkpoint/newpolicy approvals/separate4fb release are distinct authorities. Declaredfamily-stack/DOMtext failures are not actual-face or pixel proof; markergeometry is not emptyAPPtext/iconmeaning/backendtruth/fullappJigDONE. Remaining finitecontrols/readbacks/postreviews govern only the Servo consumer slice.

## CSS paint guards need applicable boxes and explicit uncertainty (036-03)
Fresh final compliance caught real APP visibility false-blocks after a complete native experiment: ancestors visibility:hidden and HTML hidden attributes can be overridden. Old hidden-marker native raw.visible was true/8x8 while the old guard failed it; preserve that invalid negative premise and emitted outcome, never call it correct paint proof. Visibility/2 source-only TDD/review corrects applicable overflow/content boxes, effective fill, unsupported ink before transparency, hard absence versus unsupported geometry and text-fragment order. A pinned Chromium primitive has display:contents opacity0 painted byte-identical to its visible control while native checkOpacity says false: explicitly UNKNOWN/veto on computed contents nondefault opacity, not inferred hidden or PASS. Inline/block opacity0 remains known hidden even with zero client dimensions. Current source2cfe/test57ec has54realbrowserprimitivecases plus full2570pass15skip316subtests; scoped mechanism/control PASS is not final compliance or APP approval. New policies/definitions/releases and actual profile2 outcomes remain required. See docs/specs/036-deterministic-design-evidence/visibility2-correction-receipt.md; old07/02/f0/source authorities remain immutable.
