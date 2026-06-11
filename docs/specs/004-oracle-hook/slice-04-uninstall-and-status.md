---
status: DONE
dependencies: [004-01, 004-03]
last_verified: 2026-06-10
---

## Slice 004-04 — uninstall-and-status

**Goal:** Complete the ROADMAP's `install` / `uninstall` / `status` contract.
`hook.py uninstall <target>` removes **only** servo's `Stop` entry from
`settings.json` (leaving other hooks and the `meta-judge.sh` script on disk), and
`hook.py status <target>` reports whether the hook is installed and consistent.
End-to-end value: a user can cleanly back the hook out (the reversibility that
makes a Tier-2 settings-mutating tool safe to try) and can inspect the install
state at any time.

**DoR:**
- ✅ 004-01 DONE — `install` exists; 004-03 DONE — servo's entry has a stable
  marker and merge/backup machinery exists (uninstall reverses that surgery).
- ✅ Decision pinned (architecture.md "Runtime artifacts"): uninstall **leaves**
  `<target>/.servo/hooks/meta-judge.sh` on disk (the user may have customized it).

**Acceptance Criteria:**

1. **Uninstall removes only servo's entry.** `uninstall` removes servo's `Stop`
   entry (matched by the 004-03 marker) and preserves every other `Stop` entry,
   every other hook event, and all unrelated top-level keys. If removing servo's
   entry empties the `Stop` array, the empty array / key is cleaned up so no dead
   structure is left behind.
2. **Uninstall leaves the script.** `uninstall` does **not** delete
   `<target>/.servo/hooks/meta-judge.sh` (per architecture.md). A re-install
   reuses or re-copies it.
3. **Uninstall is idempotent.** Running `uninstall` when no servo entry is
   present is a no-op success (not an error), and never rewrites unrelated
   content.
4. **Uninstall backs up before mutating.** Like `install`, `uninstall` writes
   `settings.json.servo-bak` before its mutation, and refuses safely (no change)
   on a malformed `settings.json`.
5. **Status reports install state.** `hook.py status <target>` reports, in human
   and `--json` form: whether servo's `Stop` entry is present in `settings.json`,
   whether `meta-judge.sh` exists, and whether the two are consistent (entry
   points at an existing script). Distinct, machine-readable states for
   `installed`, `not_installed`, and `inconsistent` (e.g. entry present but
   script missing, or script present but no entry).
6. **Closed exit contract for the CLI.** `install` / `uninstall` / `status`
   share a small closed exit-code contract consistent with the servo house style
   (0 success, nonzero env-error with a reason), documented for the SKILL.md in
   004-05.

**DoD:**
- [x] All ACs pass; full test suite green (675 passed, 1 skipped — the skip is
      the docker-less shellcheck case).
- [x] Test coverage per AC under `UninstallStatusTests` (15 tests), including the
      round-trip (install → installed → uninstall → **inconsistent** orphaned
      script → rm script → not_installed; see deviation log) and both
      inconsistent-state fixtures.
- [x] Reviewed by `reviewer` subagent (compliance + craft).
- [x] Implementation review passed (`jig:reviewer`: **PASS** first time).
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed (inline).
- [x] `docs/refinement-todo.md` — no *new* deferral this slice (the reviewer
      notes are disclosed reconciliations, recorded in the deviation log).

### Close-out (post-DONE)
- [x] [docs/specs/README.md](../README.md) status board updated.

**Anti-horizontal-phasing check:** After this slice the full lifecycle
(install → inspect → uninstall) is usable end-to-end — reversibility is the
concrete value, not an internal refactor.

### Deviation log (after reconciliation)

Implemented 2026-06-10; 15 new tests (`UninstallStatusTests`) in
`skills/oracle-hook/test_hook.py`; full suite 675 passed, 1 skipped. Changed:
`skills/oracle-hook/hook.py` only — new `cmd_uninstall` + `cmd_status`, a shared
`_load_settings` helper (`cmd_install` refactored onto it), `main()` gained
`uninstall` / `status` subparsers + a shared `target.is_dir()` precondition, and
the module docstring now documents the exit-code contract. No
`meta-judge.sh.template` change.

- **`_load_settings` extracted and `cmd_install` refactored onto it.** install
  (004-03) was finalized, but the parse + dict-check + structural-validation it
  did inline is exactly what uninstall needs, so it became one helper
  (`validate_structure` toggles the odd-shape refusal). install's observable
  004-03 behavior is unchanged — refuse-before-write on malformed/odd-shape,
  message names the file, empty→`{}`, `had_content`/backup semantics — and the
  `IdempotentInstallBackupTests` guard suite (12 tests) still passes, so the
  refactor is safe. DRY across the three commands beat leaving install's copy
  untouched.
- **Post-uninstall status is `inconsistent`, not `not_installed` — DoD wording
  reconciled to the binding ACs.** AC2 leaves `meta-judge.sh` on disk and AC5
  classifies "script present but no entry" as `inconsistent`; so immediately
  after `uninstall` the precise state is `inconsistent` (orphaned script), and
  `not_installed` requires also removing the script. The DoD's convenience
  phrasing ("uninstall → status=not_installed") is imprecise against AC2+AC5;
  the ACs are the contract, so the round-trip test asserts
  `installed → inconsistent → (rm script) → not_installed` with an explicit
  docstring. This is the genuinely useful behavior too — status flags the
  orphaned script rather than hiding it.
- **Strict-mutation vs lenient-inspection asymmetry (disclosed).** install and
  uninstall refuse (env-error) on a valid-JSON-but-odd-shaped `hooks`/`Stop`
  (`_load_settings(validate_structure=True)`) because a blind merge/removal would
  clobber or crash; `status` (`validate_structure=False`) reports such a file
  leniently as "no servo entry" — inspection need not understand a structure it
  will not mutate. `status` still env-errors on truly *unparseable* JSON. This
  extends, but is not literally enumerated by, AC5's state list.
- **Uninstall cleans the emptied `hooks` object, one level beyond AC1's literal
  "Stop array/key."** install creates the `hooks`/`Stop` scaffolding on a fresh
  target, so the inverse op removing an emptied `hooks` is symmetric and leaves
  "no dead structure behind" (AC1's stated intent). Other events / Stop entries
  / top-level keys are preserved; only an *empty* `hooks` is dropped.
- **Shared closed exit contract (AC6).** `0` = success (install / uninstall incl.
  idempotent no-op / status reporting any of the three valid states); `2` =
  env-error with a `reason` (target missing-or-not-a-dir, unparseable settings,
  odd-shape on a mutator, unscaffolded install). No exit 1. `status` returns `0`
  for `not_installed` / `inconsistent` — those are valid *reports*, not failures.
  Documented in the module docstring for 004-05's SKILL.md.
- **Reviewer nits dispositioned (all fixed):** (a) `cmd_uninstall` no longer
  reads `settings.get("hooks")` twice (mirrors `cmd_status`); (b) the docstring
  now notes that wrong-shape refusal applies to the *mutating* commands only;
  (c) `test_status_refuses_malformed` now also asserts the message names the file
  (matching its install/uninstall siblings).

**Review:** `jig:reviewer` independent pass — **PASS** first time. All six ACs
PASS with non-tautological tests; the five scrutinized judgment calls
(DoD-vs-AC5 reconciliation, strict/lenient asymmetry, `_load_settings` refactor,
status exit-0-for-all-states, emptied-`hooks` cleanup) were each dispositioned
in-scope and correct; slice-boundary discipline verified (no 004-05 SKILL.md /
install-contract / dogfood, no template change). Three cosmetic nits, all fixed
above.

**Reconciliation review (inline):** deviation log checked against the diff
(faithful). The DoD-vs-AC5 reconciliation, the strict/lenient asymmetry, and the
emptied-`hooks` cleanup are all disclosed scope decisions grounded in the binding
ACs — not silent changes. The `cmd_install` refactor preserves 004-03 behavior
(guard suite green). `hook.py` is `install`/`uninstall`/`status` only — no 004-05
surface leaked in.
