---
status: DRAFT
dependencies: [004-01, 004-03]
last_verified:
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
- [ ] All ACs pass; full test suite green.
- [ ] Test coverage per AC, including round-trip (install → status=installed →
      uninstall → status=not_installed) and the inconsistent-state fixtures.
- [ ] Reviewed by `reviewer` subagent (compliance + craft).
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred.

### Close-out (post-DONE)
- [ ] [docs/specs/README.md](../README.md) status board updated.

**Anti-horizontal-phasing check:** After this slice the full lifecycle
(install → inspect → uninstall) is usable end-to-end — reversibility is the
concrete value, not an internal refactor.
