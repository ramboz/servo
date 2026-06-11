---
status: DRAFT
dependencies: []
last_verified:
---

## Slice 009-02 — ruff-lint-floor

**Goal:** Add a ruff lint floor to CI (mirroring jig) so Python
style/quality regressions are caught automatically, and bring the existing
tree to green. End-to-end value: contributors get the same lint gate jig
has, enforced in CI rather than by code review alone.

**DoR:**

- 009-01 landed (CI has a real job a lint step can attach to) — or land the
  two together.
- Agreement on the ruleset. _(Recommended: jig's — `line-length = 100`,
  `select = ["F", "E", "W", "I", "B"]`, `ignore = ["E402"]`.)_

**Acceptance Criteria:**

1. **Ruff config present.** `ruff.toml` (or `[tool.ruff]` in
   `pyproject.toml`) exists with the agreed ruleset: `line-length = 100`,
   `select = ["F", "E", "W", "I", "B"]`, `ignore = ["E402"]`. _(E402 is
   ignored for the same reason jig does: servo deliberately
   `sys.path.insert(...)` before importing sibling modules — e.g.
   `build_release_zip.py`'s deferred `import verify_install`.)_
2. **CI lint step.** CI runs `ruff check` (resolved on PATH or run
   ephemerally via `uvx` / `pipx` — installs nothing globally) and fails on
   findings.
3. **Tree is clean.** `ruff check .` exits 0 on the repo at slice close.
4. **Lint failures block.** A deliberately introduced violation fails the
   CI lint step.

**DoD:**

- [ ] All ACs pass; `ruff check .` green; CI lint step active.
- [ ] Any pre-existing findings fixed — pure-style changes only, no behavior
      change — and enumerated in the deviation log.
- [ ] Deviation log produced under this slice.
- [ ] Independent review pass completed before DONE.

**Anti-horizontal-phasing check:** After this slice, the Python lint floor
is enforced in CI, not an oral style guide.
