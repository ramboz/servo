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
