# 033-01 retrospective implementation verification

Witnessed on 2026-10-12 by the bounded implementation-verification worker.
Scope: [spec 033](spec.md), [slice 033-01](slice-01-diagnostic-handoff.md),
and accepted [ADR-0039](../../decisions/adr-0039-heartbeat-handoff-contract.md).
**Result: 70 existing targeted tests and 5 temporary fixture-based checks pass;
all four behavior-removal mutations fail, then pass after restoration.**

## Chronology and limits

1. The implementation already existed at
   `ac06cec89e544e04ae22fa4c27d4516c7442db6a`, authored/committed at
   `2026-10-12T08:47:05-07:00`, before this recovery's workflow artifacts.
   Its original TDD account is historical, not witnessed by this worker.
2. The assigned spec and slice were already `IN_PROGRESS`; ADR-0039 was
   `Accepted`. This was verification of existing implementation, not a new
   spec-first implementation or a replay/backdating of readiness transitions.
   No implementation, test, status, review artifact, ADR, board, or history
   was changed by this worker.
3. An initial source-identity preflight stopped at
   `AssertionError: docs/architecture.md`, before any tests or sandbox mutation.
   An external, uncommitted update had added ADR/spec links to the handoff
   paragraph since the initial read. Its behavior description was unchanged.
   The verifier was corrected to record that document's current bytes while
   still requiring runtime, tests, skill surfaces, and helpers to equal
   `ac06cec`. This was a verifier assumption failure, not a product regression.
4. Baseline tests passed in a temporary copy; five supplemental checks passed.
   Each mutation was applied separately in that copy, witnessed red, restored
   byte-for-byte, and witnessed green. The complete targeted selection and
   supplemental checks were then rerun green. Verification finished before
   `2026-10-12T16:36:44Z`.
5. The sandbox and disposable verifier were removed. The only durable file
   authored by this worker is this record. No DoD box or lifecycle status was
   changed; independent reviews and reconciliation remain separate gates.

**Discovery limitation — UNINDEXED:** Neither Scout tools nor their deferred
schema loader were exposed in this worker's tool set; an availability retry
could not be issued. Supplied literal paths and bounded, read-only native
keyword/range reads were used and disclosed. The evidence below is direct
source inspection and executable verification, not Scout-indexed affected-test,
impact, or PR-review evidence. No indexed review claim is made.

## Source identity and isolation proof

For publication, host-local roots below are represented by `$SERVO_CHECKOUT`
(the isolated repository) and `$SESSION_FILES` (its temporary session storage).
These placeholders stand for the original absolute path arguments. Only path
spelling is redacted; observed results, hashes, and experiment chronology are
unchanged.

Canonical repository:
`$SERVO_CHECKOUT`.
Checkout HEAD during the completed run:
`4bfa63d7f0e67ef3d23ab862297dacb95b119ee9`.
This checkout was **not globally clean**: workflow recovery documents/reviews
and the architecture link update were already dirty.

| File | SHA-256, identical before and after the completed verification |
|---|---|
| `skills/heartbeat/heartbeat.py` | `4a8e5fab7203a42b4fd70cf86f1573f85699743524ca21bf4b784536e506f542` |
| `skills/heartbeat/test_heartbeat.py` | `bbbbb74b7c7aa4d9dc01f16faffb82ad0c6dc93392900c9a4ce8f0548264da63` |
| `skills/heartbeat/SKILL.md` | `4b45d12df0d5a81eb242c3ceb82f3e44a982f12c091ffaf4b3c11ace689f7781` |
| `docs/architecture.md` | `7f2a4bbbeaac1c769865a1524213c0d663d853be25217f65afb8bb473361843f` |
| `hosts/claude/skills/heartbeat/heartbeat.py` | `4a8e5fab7203a42b4fd70cf86f1573f85699743524ca21bf4b784536e506f542` |
| `hosts/claude/skills/heartbeat/SKILL.md` | `4b45d12df0d5a81eb242c3ceb82f3e44a982f12c091ffaf4b3c11ace689f7781` |
| `hosts/codex/plugins/servo/skills/heartbeat/heartbeat.py` | `4a8e5fab7203a42b4fd70cf86f1573f85699743524ca21bf4b784536e506f542` |
| `hosts/codex/plugins/servo/skills/heartbeat/SKILL.md` | `02aa68dd6fa3395d4c1a4ea3c2a2143255d28af7ac6d10379d4e64e7c42ee63a` |
| `skills/agent-loop/loop.py` | `ef87f18a21c49c9311b94018b0847eb9b67024a755777a0efc1695ce50761097` |
| `skills/quality-gate/gate.py` | `a78037077f567b3fc534c496a61dd9d1500e4aad59301b3ef94a2e99455a4f96` |

Pre-run dirty-state fingerprint:
`4bffa8a4344c338ec98d2996d4609cf824ce076c28ab4047e82a17332d6c9cdc`.
This is SHA-256 of sorted-key JSON containing the complete
`git status --porcelain=v1 --untracked-files=all` text, the tracked binary-diff
hash, and byte hashes of existing dirty/untracked files named by that status.
The tracked `git diff --binary` hash was
`65ff9b360612469bf3bd51d72f3a876f453502fdd7d7202a4e2fee32ec6a399d`.
These fingerprints identify the pre-run snapshot, not subsequent parent edits.

The verifier used `tempfile.TemporaryDirectory` under the session's `files/`
directory and `shutil.copytree` to copy only `skills/`, excluding bytecode/test
caches. Actual sandbox:
`$SESSION_FILES/verify-033-01-e75oz22e`.
Test `TMPDIR` pointed inside that sandbox; `PYTHONDONTWRITEBYTECODE=1` and `-B`
disabled bytecode writes. Existing fixtures used controlled mock runners/`gh`
and real temporary Git repos/worktrees; no live Claude or GitHub session ran.
Nothing was installed.

The final isolation assertions passed:
- Ten canonical file byte comparisons equaled their pre-run snapshots.
- HEAD was unchanged.
- `git diff ac06cec --` over the nine runtime/test/skill/helper paths was empty.
- The sandbox's original heartbeat bytes were restored; after cleanup the
  sandbox no longer existed. Canonical source was never a mutation target.

## Witnessed commands and results

The disposable driver was invoked twice with this real command: the first
invocation stopped at the documented identity guard; the second completed.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B "$SESSION_FILES/verify-033-01.py"
```

Its interpreter resolved to `/opt/homebrew/opt/python@3.14/bin/python3.14`.
Repository-native commands below ran from the sandbox's `skills/heartbeat/`.
The same 16-class command ran before mutations and after all restorations:

```bash
/opt/homebrew/opt/python@3.14/bin/python3.14 -B -m unittest \
  test_heartbeat.OutcomeSummaryHandoffTests \
  test_heartbeat.LoopDispatchOutcomeTests \
  test_heartbeat.OutcomeRecordingTests \
  test_heartbeat.StatusSubcommandTests \
  test_heartbeat.MergeDedupeTests \
  test_heartbeat.ResumeTests \
  test_heartbeat.CandidateSelectionTests \
  test_heartbeat.SerialDispatchTests \
  test_heartbeat.HeartbeatRunCostCeilingTests \
  test_heartbeat.QuarantineWriteTests \
  test_heartbeat.QuarantineSkipTests \
  test_heartbeat.QuarantineReadmitTests \
  test_heartbeat.QuarantineContractTests \
  test_heartbeat.QuarantineSchemaTests \
  test_heartbeat.JigClaimSkipTests \
  test_heartbeat.RankingBoundednessTests
```

Results: baseline **70 passed, 0 failures/errors** (46.397 s); final
**70 passed, 0 failures/errors** (45.481 s). These are repeated executions
of the same 70 tests, not 140 unique tests.

The five temporary checks were executed through the same driver's
`--supplemental` mode, importing the sandbox's existing `test_heartbeat`
fixtures and using `unittest.TextTestRunner`:

```bash
/opt/homebrew/opt/python@3.14/bin/python3.14 -B "$SESSION_FILES/verify-033-01.py" --supplemental "$SESSION_FILES/verify-033-01-e75oz22e"
```

Results: **5 passed, 0 failures/errors** before mutations (1.559 s) and again
after restorations (1.562 s). Temporary test names and load-bearing assertions:

| Temporary check | Witnessed assertion |
|---|---|
| `test_optional_diagnostics_and_base_metadata` | With `_now_iso` fixed, absent/empty/null/nonstrings do not append diagnostic keys; reason-only, hint-only, and both nonempty strings preserve every base value and its five-key prefix. |
| `test_last_history_entry_and_missing_goal_score` | Two history entries override a conflicting direct score with the final `0.0`, `0.3`, or null; empty/absent history preserves direct zero/null; a missing direct goal score remains null. |
| `test_status_guards_json_and_legacy_absence` | `subprocess.run`, discovery, dispatch, and loop invocation are patched to raise if called. Human and JSON `run_status` both return zero, leave target bytes unchanged, display legacy/new outcomes and zero correctly, and match the full current JSON version/counts/candidate payload. Records with missing or null outcome remain readable. |
| `test_actual_rediscovery_preserves_diagnostic_outcome` | Discover, seed diagnostics on a genuinely discovered actionable CI ID, then rediscover that same ID. Its stale title refreshes while outcome, tried status, attempts, and discovered timestamp remain equal; markdown contains reason, hint, and zero. |
| `test_dispatch_persists_without_refreshing_markdown` | Mock goal dispatch persists zero, cap reason, tried status, and one attempt; a seeded `inbox.md` sentinel remains unchanged while immediate human status shows the new reason. |

### Mutation red/green evidence

All edits below affected **only sandbox `heartbeat.py`**. Exact replacement
anchors were required to occur once. Each red command returned **1**, contained
an assertion failure and no test error; byte restoration preceded its green
command, which returned **0**. Each command used the interpreter above with
`-B -m unittest` and the listed fully qualified selectors.

| Mutation | Selector(s), prefixed `test_heartbeat.` | Witnessed red assertion in `skills/heartbeat/test_heartbeat.py` | Red / restored green |
|---|---|---|---|
| Remove the entire optional-diagnostic append loop at `heartbeat.py:2032-2035` | `OutcomeSummaryHandoffTests.test_preserves_stop_reason_and_fix_hint` | `:3686`: `None != 'edit_permission_unavailable'` | 1 test, 1 failure / 1 passed |
| Replace `composite = summary.get("oracle_composite")` with `composite = None` | `OutcomeSummaryHandoffTests.test_preserves_goal_driver_score`; `LoopDispatchOutcomeTests.test_goal_summary_retains_score_without_creating_a_plateau` | `:3654`: `None != 0.0`, `None != 0.8`; `:3022`: `None != 0.0`, `None != 0.4`, `None != 0.9` | 2 tests, 5 failing subtests / 2 passed |
| Remove `records=records` from the human renderer call in `run_status` | `LoopDispatchOutcomeTests.test_permission_wall_handoff_reaches_both_human_views` | `:2980`: `'edit_permission_unavailable' not found` in human status | 1 test, 1 failure / 1 passed |
| Remove markdown's `lines.extend(f"  - {item}" for item in _outcome_details(f.get("outcome")))` | `LoopDispatchOutcomeTests.test_permission_wall_handoff_reaches_both_human_views` | `:3000`: `'edit_permission_unavailable' not found` in refreshed markdown; preceding persistence/status assertions succeeded | 1 test, 1 failure / 1 passed |

Thus four mutants were rejected through **eight assertion/subtest failures**,
not syntax/import errors. The restored selectors contributed five passing test
executions; the final 70+5 run was independently green afterward.

## Acceptance-criterion closure

All source evidence in this table is **UNINDEXED**; confidence concerns the
bounded assertions and inspected code, not external compatibility or review.
`T` denotes `skills/heartbeat/test_heartbeat.py`; `H` denotes
`skills/heartbeat/heartbeat.py`. AC links refer to the numbered
[acceptance criteria](slice-01-diagnostic-handoff.md#acceptance-criteria).

| Criterion | Status | Strongest exact evidence | Confidence | Gap |
|---|---|---|---|---|
| [AC1](slice-01-diagnostic-handoff.md#acceptance-criteria): durable diagnostics/base metadata | Verified locally | `T:2960-3002` actual mock dispatch/persistence; `T:2906-2918`, `3059-3079` identity/cost/attempts/order; diagnostic mutant red; temporary fixed-timestamp/base-field check; `H:2528-2553` durable write | High | No implementation gap found; malformed diagnostics/base-value comparison is temporary coverage. |
| [AC2](slice-01-diagnostic-handoff.md#acceptance-criteria): both drivers/zero/null/no false plateau | Verified locally | `T:3643-3662`, `3004-3026`; five goal-score mutation failures; temporary two-entry history/missing-score assertions. Actual producer shapes inspected at `skills/agent-loop/loop.py:1924-1955`, `2784-2815` | High | Multi-entry final-zero/null and missing direct score checks are temporary. |
| [AC3](slice-01-diagnostic-handoff.md#acceptance-criteria): immediate read-only status/current JSON | Verified locally | `T:2977-2990`, `2016-2106`; human-display mutant red; temporary hard no-shell/discovery/dispatch/loop guards and exact nested JSON payload/target-byte equality; `H:1407-1411` JSON/human branch | High | Explicit raising guards strengthen the permanent PATH-based test but are temporary. |
| [AC4](slice-01-diagnostic-handoff.md#acceptance-criteria): next-discovery markdown/sticky state | Verified locally | `T:2992-3002`; markdown mutant red; temporary matching-ID rediscovery preserves diagnostic outcome/status and temporary dispatch sentinel proves refresh timing; `H:928-971` merge/normalization | High | Existing handoff test retains an unseen invented ID; matching-ID diagnostic rediscovery and dispatch timing were separately checked temporarily. |
| [AC5](slice-01-diagnostic-handoff.md#acceptance-criteria): legacy/absent shape and no migration | Verified locally | `T:3664-3675` exact five-key order; temporary empty/null/nonstrings and old/missing/null-outcome status checks; `H:137` schema remains 3. Historical heartbeat diff contains no schema/normalization/required-field migration | High within repository | Unknown exact-key external consumers remain the explicitly accepted ADR-0039 risk; no universal compatibility claim. |
| [AC6](slice-01-diagnostic-handoff.md#acceptance-criteria): unchanged controls | Verified locally | `T:3004-3026` goal turn/budget/pass classification and absent quarantine; `QuarantineWriteTests`, `QuarantineSkipTests`, `QuarantineReadmitTests`, candidate/serial/budget/claim/ranking classes all green; executable `H:2513-2518` quarantines only `REASON_ORACLE_PLATEAU` | High | No implementation gap found. Historical diff leaves control selectors, iteration forwarding, budgets, claims, and re-admission unchanged. |
| [AC7](slice-01-diagnostic-handoff.md#acceptance-criteria): prose and generated parity | Verified locally | `skills/heartbeat/SKILL.md:73-98`, `docs/architecture.md:241`; both generated heartbeat runtime files byte-equal canonical; both skill bodies equal canonical after only Codex `${PLUGIN_ROOT}` normalization | High | Independent architecture/reconciliation review is not performed by this record. |

Historical boundary command:
`git --no-pager diff ac06cec^ ac06cec -- skills/heartbeat/heartbeat.py`.
Inspected changes are limited to diagnostic/score projection, human display,
and their docstrings; the JSON summary builder and control-policy machinery
were not changed by that implementation.

## Existing full-suite evidence (parent-executed, not rerun here)

The parent reported and recorded `python3 scripts/ci_check.py` in
[ci-evidence.md](ci-evidence.md): **1,866 tests passed**, manifest validation,
pinned Ruff, install surfaces (**107 tests**, overlapping the full suite),
and generated-host drift checks passed. This worker did **not** execute or
duplicate that full command and does not count it as self-witnessed evidence.

## Coverage gaps, deviations, and handoff

- No real implementation gap was found; no runtime rewrite is proposed.
- **PROPOSED** for the parent to consider: preserve the five supplemental
  checks as durable regression tests in a separately authorized edit. They
  were deliberately temporary under this documentation-only assignment.
  The existing suite plus those witnessed checks verifies every AC locally;
  it does not mean every strengthened boundary already has a permanent test.
- Recovery must retain the honest retrospective order: existing source,
  present-time specification/decision gates, present-time verification and
  independent review, then reconciliation. Mutation evidence is not a claim
  that the original implementation was authored spec-first.
- Reconciliation should retain the accepted external-reader limitation,
  distinction between immediate `status` and next-discovery markdown, and
  disclosed UNINDEXED routing limitation. The initial document-identity
  preflight adjustment is accounted for above, not concealed.
- Nothing additional was identified for `docs/inbox.md`; no inbox/task entry
  was created. Review verdicts, transitions, and PR updates remain parent-owned.

## Later promotion — durable boundary regressions

Witnessed on 2026-10-12, completed before `2026-10-12T16:47:07Z`.
The owner extended this worker's writable scope to the existing test module
and this record. The preceding 214 lines describe the **first verification
assignment** and remain unchanged, including its historical source hashes,
temporary-coverage statements, commands, and mutation results. Their original
16,663-byte prefix has SHA-256
`0744f2800c629834d968dc253bef6985ed407474808fa3d96bc1ffc9856189cf`.
The following promotion resolves the previously proposed durable-coverage gap;
it does not rewrite the original chronology or claim a new runtime implementation.

### Promoted tests and final identity

Exactly five test methods were added to existing unittest classes, reusing
their setups and fixtures. No new repository runner, helper, configuration,
runtime behavior, or dependency was added.

| Durable selector, prefixed `test_heartbeat.` | Final test-module lines | AC closure |
|---|---|---|
| `OutcomeSummaryHandoffTests.test_optional_diagnostics_and_base_metadata` | 3750–3785 | AC1/AC5: malformed/absent diagnostics, fixed timestamp, explicit base values and key order, valid reason-only/hint-only/both strings |
| `OutcomeSummaryHandoffTests.test_last_history_entry_and_missing_goal_score` | 3787–3804 | AC2: final multi-entry history zero/null overrides the direct score; absent/empty history and missing goal score |
| `StatusSubcommandTests.test_status_guards_json_and_legacy_absence` | 2133–2189 | AC3/AC5: raising no-shell/discovery/dispatch/loop guards; target-byte equality; exact nested current JSON; legacy five-field, missing, and null outcomes |
| `MergeDedupeTests.test_actual_rediscovery_preserves_diagnostic_outcome` | 1533–1556 | AC4: genuinely matching-ID rediscovery refreshes the title while preserving diagnostic-bearing outcome, status, attempts, and discovery timestamp; markdown shows zero/reason/hint |
| `LoopDispatchOutcomeTests.test_dispatch_persists_without_refreshing_markdown` | 3114–3133 | AC4: dispatch persists score/status immediately without refreshing discovery-owned markdown |

Final `skills/heartbeat/test_heartbeat.py`:
**4,580 lines**, **163 added / 0 removed**.
SHA-256:
`565b1703f742e1912fcbe4d93ba4b0cff1e0d6b940a11bfc93f2fe7767b54b7a`.
SHA-256 of `git diff -- skills/heartbeat/test_heartbeat.py`:
`9d644d862c3173061e8c3fc46b0e1eb6bb0c12012898edb43d0dd1379974385a`.
HEAD remained `4bfa63d7f0e67ef3d23ab862297dacb95b119ee9`.
All nine other byte hashes in the historical identity table still matched.
The historical test-file hash remains evidence of the first mutation run,
not the current promoted test file.

### Fresh red/green and targeted validation

Tests were written first. Before the canonical green run, each new test was
executed against an independently corrupted **temporary copy** of heartbeat.
The copy was under session `files/promote-033-mutations-c8mklt3u`, not the
canonical checkout. Each command used
`/opt/homebrew/opt/python@3.14/bin/python3.14 -B -m unittest` with the corresponding
fully qualified selector above, from that copy's `skills/heartbeat/`.

| Temporary corruption | Witnessed failing assertion in the promoted test module | Result |
|---|---|---|
| Remove diagnostic append loop | `:3784`: reason-only, hint-only, and combined diagnostic dictionaries contain null instead of supplied strings | 1 test, 3 failing subtests |
| Read first history entry instead of last | `:3795`: `0.9 != 0.0`, `0.9 != 0.3`, `0.9 != None` | 1 test, 3 failing subtests |
| Inject a subprocess call before status summarization | `:2164`: `AssertionError: shell`; patched guard prevents actual shell execution | 1 test, 1 failure |
| Drop outcome during matching-ID merge | `:1553`: `None !=` the diagnostic-bearing outcome | 1 test, 1 failure |
| Rewrite markdown during dispatch | `:3126`: `'dispatch rewrite\n' != 'discovery-owned sentinel\n'` | 1 test, 1 failure |

All five mutant commands returned **1** through nine behavioral assertion/subtest
failures, with no test errors. Original sandbox bytes were restored after each
mutation. Running the five selectors together after restoration returned **0**:
**5 passed** (1.638 s). Canonical heartbeat bytes still had SHA-256
`4a8e5fab7203a42b4fd70cf86f1573f85699743524ca21bf4b784536e506f542`;
the mutation sandbox was removed.

The canonical checkout then ran the same 16-class command recorded earlier,
with `PYTHONDONTWRITEBYTECODE=1`, `python3 -B -m unittest`, from canonical
`skills/heartbeat/`. It now includes the five promoted methods:
**75 passed, 0 failures/errors** (53.576 s). The two expected best-effort
schema-version warnings come from seeded legacy v2 records; the asserted machine
summary still reports current schema 3. `git diff --check -- skills/heartbeat/test_heartbeat.py`
also passed.

### Ruff and remaining limits

`python3 -m ruff --version` first reported **No module named ruff**.
Only after that dependency-missing result, `ruff==0.15.17` was installed in a
disposable session-local virtual environment. Its actual lint invocation was:

```bash
"$SESSION_FILES/ruff-033-promotion-fn0sarex/venv/bin/python" -m ruff check skills/heartbeat/test_heartbeat.py
```

Result: **All checks passed**, exit **0**, using the repository's Ruff config.
The environment was removed; no dependency/configuration file was changed.

No remaining gap was found in the five promoted boundaries, and no genuine
source gap was found. The earlier external-reader compatibility and UNINDEXED
limitations still apply. The parent's 1,866-test full CI run predates this
promotion; it is not relabeled as a post-promotion run. This worker executed
only the requested targeted selection and Ruff, not another full CI run.
Statuses, ADRs, review evidence, board, and Git history were not modified.
Nothing additional was identified for `docs/inbox.md`.
