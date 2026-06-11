---
status: DONE
dependencies: []
last_verified: 2026-06-11
---

## Slice 009-02 — ruff-lint-floor

**Goal:** Add a ruff lint floor to CI (mirroring jig) so Python
style/quality regressions are caught automatically, and bring the existing
tree to green. End-to-end value: contributors get the same lint gate jig
has, enforced in CI rather than by code review alone.

**DoR:**

- 009-01 landed (CI has a real job a lint step can attach to) — or land the
  two together. → **Landing the two together** (same branch/PR); the ruff
  step attaches to 009-01's `test` job.
- Agreement on the ruleset. _(Recommended: jig's — `line-length = 100`,
  `select = ["F", "E", "W", "I", "B"]`, `ignore = ["E402"]`.)_
  → **AGREED: jig's exact ruleset.** Recorded in `ruff.toml`.

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

- [x] All ACs pass; `ruff check .` green; CI lint step active. _AC1–AC3 met
      (`ruff check .` → "All checks passed!"; lint step wired into `ci.yml`'s
      `test` job). **AC4 proven on the runner:** a throwaway deliberate F401
      (`7a23d84`) failed run 27376383980 at the **`Lint (ruff)`** step on both
      `test (3.11)` and `test (3.12)`, while pytest and `install-surfaces`
      stayed green — the lint step blocks independently. Reverted in `4694989`.
      (github.com/ramboz/servo/actions/runs/27376383980)_
- [x] Any pre-existing findings fixed — pure-style changes only, no behavior
      change — and enumerated in the deviation log. _85 findings → 0; full
      suite unchanged at 705/1/13 on both Pythons. Enumerated below._
- [x] Deviation log produced under this slice. _Below._
- [x] Independent review pass completed before DONE. _Same independent
      reviewer pass as 009-01, 2026-06-11 — **PASS, no blockers.** Confirmed
      `ruff.toml` carries the exact ruleset, the tree is clean under both
      `ruff@latest` and the pinned `ruff==0.15.17`, and ran a dedicated
      behavior-preservation audit on every style edit (the `zip(strict=False)`
      raggedness, `raise ... from exc`, the `import shutil`/`import os` F401
      removals, the `l`→`line` renames, and every f-string split boundary) —
      all confirmed behavior-neutral. AC4 (lint-block) correctly noted as
      deferred-to-CI._

**Anti-horizontal-phasing check:** After this slice, the Python lint floor
is enforced in CI, not an oral style guide.

**Deviation log:**

- **Ruleset = jig's exactly.** `ruff.toml` (config-only — servo isn't a pip
  package): `line-length = 100`, `[lint] select = ["F","E","W","I","B"]`,
  `ignore = ["E402"]`.
- **E402 ignore is forward-looking, not a live suppression.** AC1 prescribes
  `ignore = ["E402"]` and cites `build_release_zip.py`'s deferred
  `import verify_install`. In servo today that import is **function-local**
  (inside `smoke_test`, after `sys.path.insert`) and already carries a
  defensive `# noqa: E402`, so E402 never actually fires anywhere
  (`ruff check --select E402 .` → clean even without the ignore). The ignore
  is kept for jig parity + the day a module-level deferred import appears. The
  pre-existing `# noqa: E402` was left in place (harmless; documents intent).
- **85 findings → 0, all pure-style.** Breakdown by rule (pre-fix):
  - `I001` unsorted-imports ×27 — **ruff --fix** (auto).
  - `F401` unused-import ×4 — **ruff --fix** (auto). Notable: `import shutil`
    in `scaffold-init/scaffold.py` was genuinely unused (no `shutil.` anywhere
    in the file) and removed.
  - `E501` line-too-long ×26 — **manual** wraps: long `def` signatures split
    across lines; over-long f-strings split via implicit string concatenation
    (message text byte-preserved across the split); a one-line docstring made
    multi-line; a couple of expressions hoisted to a local var
    (`setup_cfg`, `scaffold_py`); two trailing inline comments moved above
    their statement. Three lines containing escape sequences (`test_loop.py`'s
    `"\\n"` literal, two `test_scaffold.py` f-strings with `\n`) were wrapped
    by an index-based reuse of the original bytes so the string contents are
    byte-identical.
  - `E741` ambiguous-variable-name ×24 — **manual** rename `l` → `line` (all
    were log-line comprehension/loop vars in `agent-loop`; `line` is the
    accurate name). No shadowing introduced (comprehension scopes are local).
  - `B905` zip-without-strict ×2 — **manual** `strict=False` added. `False`
    (not `True`) is deliberate and behavior-preserving:
    `zip(budgets, budgets[1:])` zips operands of *different* lengths by design;
    `strict=True` would change behavior (raise). Per the spec non-goal, the
    fix must not alter what the test asserts.
  - `B007` unused-loop-var ×1 — **manual** `for helper, reason in …items()` →
    `for reason in …values()` (the key was unused).
  - `B904` raise-without-from ×1 — **manual** `except json.JSONDecodeError as
    exc: … raise … from exc` (chains the JSON error as the cause; behaviour of
    the refusal is unchanged).
- **CI lint step: pinned, via `pipx` (deliberate divergence from jig).** The
  step runs `pipx run --spec ruff==0.15.17 ruff check .`. `pipx` is
  preinstalled on `ubuntu-latest` and runs ruff ephemerally (installs nothing
  global), matching servo's local `uvx`/`pipx` convention and AC2. **Pinning**
  the ruff version diverges from jig (which floats): for a spec whose whole
  thesis is *CI correctness*, a floating linter is a self-inflicted flakiness
  vector — a future ruff release can add a rule under a selected prefix
  (`E`/`F`/`W`/`B`) and redden an unrelated PR. `0.15.17` is the exact version
  the tree was brought green against. The step sits in the `test` matrix job
  (jig parity — Goal 5); it therefore runs once per Python, which is redundant
  but trivial (ruff is sub-second) and harmless.
- **AC4 (lint-block proof) DEFERRED to the push.** "A deliberately introduced
  violation fails the CI lint step" needs a remote Actions run; it will be
  demonstrated alongside the 009-01 canary and the evidence captured here.

Verification (local):

- `uvx ruff@latest check .` (ruff 0.15.17) → **All checks passed!** (exit 0).
- Full suite after all style edits: **705 passed, 1 skipped, 13 subtests** on
  both 3.11 and 3.12 — identical to the pre-change baseline (no behavior drift).
- `bash scripts/verify_install_surfaces.sh` → exit 0.
- All 26 touched `.py` files `py_compile` clean.

CI evidence (after push, branch `claude/infallible-tu-344ea6`, PR #1):

- **Lint step active + green** on the clean tree — run 27376015624 (the
  `Lint (ruff)` step inside `test (3.11)`/`test (3.12)` passed).
- **AC4 — lint failures block** — a throwaway deliberate F401
  (`_canary_lint_009.py`, commit `7a23d84`) failed run **27376383980** at the
  **`Lint (ruff)`** step on both `test (3.11)` and `test (3.12)`; crucially the
  `Run full test suite` step PASSED and `install-surfaces` succeeded, so the
  lint gate is what blocked (isolated by using a non-`test_` file pytest
  ignores). Reverted in `4694989`, restoring green.
  github.com/ramboz/servo/actions/runs/27376383980
