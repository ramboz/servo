---
status: DRAFT
dependencies: [004-01]
last_verified:
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
- [ ] All ACs pass; full test suite green.
- [ ] Test coverage per AC, including fixtures: empty file, file with unrelated
      keys, file with a pre-existing non-servo `Stop` hook, file with a
      pre-existing servo entry (re-install), malformed file.
- [ ] Reviewed by `reviewer` subagent (compliance + craft).
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred.

### Close-out (post-DONE)
- [ ] [docs/specs/README.md](../README.md) status board updated.

**Anti-horizontal-phasing check:** After this slice `install` is trustworthy on
a populated `settings.json` — re-runnable and non-destructive — which is the
observable, end-to-end safety a user needs before adopting a settings-mutating
Tier-2 tool.
