---
status: DONE
dependencies: [004-01]
last_verified: 2026-06-10
---

## Slice 004-03 — idempotent-install-and-backup

**Goal:** Make `install` safe to run against a *real* `settings.json` that
already has content: re-running is idempotent (no duplicate Stop entries), other
hooks and unrelated keys are preserved (merge, not clobber), and the prior
`settings.json` is backed up before the first mutation. End-to-end value: a
developer with an existing `.claude/settings.json` (their own hooks, env, perms)
can install the servo hook without losing anything and without accumulating
duplicates on re-install.

**DoR:**
- ✅ 004-01 DONE — `install` writes a `hooks.Stop[]` entry into a created-from-
  scratch `settings.json`.
- ✅ Decision pinned: backup filename is `settings.json.servo-bak` (single
  rolling backup of the last pre-mutation state); the merge is JSON-structural,
  not text-based.

**Acceptance Criteria:**

1. **Idempotent install.** Running `install` twice produces exactly one servo
   `Stop` entry — the second run detects servo's existing entry (identified by a
   stable marker, e.g. the script path / a `servo` tag in the entry) and is a
   no-op on the array.
2. **Merge, not clobber.** `install` preserves all other top-level keys in
   `settings.json` (`env`, `permissions`, model settings, …) and all **other**
   `Stop` entries and non-`Stop` hook events. Only servo's `Stop` entry is
   added.
3. **Backup before mutate.** Before the first mutation, `install` copies the
   existing `settings.json` to `<target>/.claude/settings.json.servo-bak`. A
   re-install (servo entry already present, no change needed) does not rewrite
   the backup. Creating a brand-new `settings.json` (none existed) writes no
   backup.
4. **Malformed settings.json refuses safely.** If `settings.json` exists but is
   not valid JSON, `install` refuses (nonzero exit, message names the file) and
   makes **no** change and **no** backup — it never overwrites unparseable user
   content.
5. **Stable entry identity.** Servo's `Stop` entry carries a marker that both
   the idempotency check (this slice) and `uninstall` (004-04) use to find
   exactly servo's entry without touching others.

**DoD:**
- [x] All ACs pass; full test suite green (660 passed, 1 skipped — the skip is
      the docker-less shellcheck case).
- [x] Test coverage per AC under `IdempotentInstallBackupTests` (12 tests),
      including all named fixtures: empty file, file with unrelated keys, file
      with a pre-existing non-servo `Stop` hook, file with a pre-existing servo
      entry (re-install), malformed file (+ two odd-shaped-`hooks` refusals).
- [x] Reviewed by `reviewer` subagent (compliance + craft).
- [x] Implementation review passed (`jig:reviewer`: **PASS** first time).
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed (inline).
- [x] `docs/refinement-todo.md` updated (a servo `meta-judge.sh` template upgrade
      will not refresh an already-installed script — write-if-absent defers it).

### Close-out (post-DONE)
- [x] [docs/specs/README.md](../README.md) status board updated.

**Anti-horizontal-phasing check:** After this slice `install` is trustworthy on
a populated `settings.json` — re-runnable and non-destructive — which is the
observable, end-to-end safety a user needs before adopting a settings-mutating
Tier-2 tool.

### Deviation log (after reconciliation)

Implemented 2026-06-10; 12 new tests (`IdempotentInstallBackupTests`) in
`skills/oracle-hook/test_hook.py`; full suite 660 passed, 1 skipped. Changed:
`skills/oracle-hook/hook.py` (`cmd_install` reworked) only — no
`meta-judge.sh.template` change and no `settings.json` *contract* change. The
004-01 deviation log's deferred item — "idempotency/backup/merge-preservation
**tests**" — is closed here.

- **AC1 / AC2 / AC5 were already implemented in 004-01 (marker-based dedup +
  `setdefault` merge) but were not test-gated; this slice gates them.** Tests
  cover the idempotent single entry, unrelated-top-level-key preservation,
  other-`Stop`-entry + other-event preservation, and the stable marker (with a
  negative case). No code change was needed for those three — AC3 (backup) plus
  the safety hardening below are the new code.
- **AC3 backup is a single rolling, byte-faithful copy.** `shutil.copyfile`
  copies the *original* `settings.json` bytes to `settings.json.servo-bak`
  before the first mutation (a 4-space-vs-`indent=2` test proves it is the
  original, not a re-serialization). A re-install with servo already present
  returns at a no-op branch *before* the backup line, so the backup is never
  rewritten; a brand-new (or empty) `settings.json` sets no `had_content` and
  gets no backup.
- **Empty / whitespace-only `settings.json` is treated as an empty config, not
  as malformed.** 004-01 would have hit `json.loads("")` → refuse; 004-03 treats
  a content-free file as `{}` and installs cleanly (no backup — nothing to
  preserve). The DoD names "empty file" as a required fixture, and refusing on a
  benign empty stub would be hostile; AC4's refusal stays scoped to *non-empty,
  unparseable* content.
- **The meta-judge script is now written only when absent.** This preserves a
  user-customized `meta-judge.sh` across re-install (spec.md calls the script
  "user-customizable") and self-heals a deleted one; the slice's promise is a
  *non-destructive* re-install. Disclosed trade-off (not silent): a future servo
  `meta-judge.sh.template` change will **not** refresh an already-installed
  script — recorded in [refinement-todo](../../refinement-todo.md) with
  `uninstall` + `install` (004-04) as the interim upgrade path.
- **Structural pre-validation added (a defensive extension of AC4).** A
  valid-JSON `settings.json` whose `hooks` is not an object, or whose
  `hooks.Stop` is not an array, is refused (`reason=settings_malformed`) before
  any write. Without it the `setdefault`/`append` path crashed with
  `AttributeError` mid-install — the exact half-write footgun AC4 exists to
  prevent. `settings_malformed` is the installer's own refusal vocabulary, not a
  `gate.py` / ADR-0002 contract change.
- **Carried to 004-04:** `uninstall` will delete on the same `_entry_is_servo`
  predicate (marker = the `.servo/hooks/meta-judge.sh` substring of the
  command); 004-04 should keep that match path-anchored so a user command that
  merely contains the substring cannot be misclassified as servo's.
- **Reviewer nits dispositioned:** (a) the test-module docstring was updated to
  reflect that the file now hosts the 004-02 / 004-03 suites; (b) the
  pre-existing `MetaJudgeScriptTests` "AC5: gate rc=0" docstring mislabel is a
  004-01 surface and was left untouched (out of this slice's scope).

**Review:** `jig:reviewer` independent pass — **PASS** first time. All five ACs
PASS with non-tautological tests (notably the backup-fidelity and
sentinel-backup tests); the full DoD fixture matrix is covered; the three
deliberate judgment calls (empty-file-as-`{}`, write-script-if-absent,
structural pre-validation) were each dispositioned in-scope and correct;
slice-boundary discipline verified (no 004-04 `uninstall` / `status` leaked in).
Three cosmetic nits, dispositioned above.

**Reconciliation review (inline):** deviation log checked against the diff
(faithful). The empty-file and write-if-absent behaviors are disclosed scope
choices grounded in the slice DoD and spec.md's "user-customizable" wording, not
silent changes; the template-upgrade-refresh trade-off is recorded in
refinement-todo; `cmd_install` remains `install`-only (no 004-04 surface), so
the slice boundary holds.
