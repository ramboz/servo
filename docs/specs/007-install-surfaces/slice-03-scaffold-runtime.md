---
status: DONE
dependencies: []
last_verified:
---

## Slice 007-03 — scaffold-runtime

**Goal:** Add an explicit project-local scaffold mode that vendors servo
runtime machinery into `<target>/.claude/` with servo-prefixed skill and
agent names. End-to-end value: a project can carry the exact servo
runtime surface it needs without depending on a globally installed
plugin checkout.

**DoR:**

- 007-01 DONE.
- Existing spec 001 scaffold behavior has regression coverage.
- Scaffold destination layout and prefixes are agreed in the contract.

**Acceptance Criteria:**

1. **Explicit scaffold mode.** A documented command, either through
   `skills/scaffold-init/scaffold.py` or a shared install helper, copies
   runtime machinery into `<target>/.claude/` without changing the
   default `scaffold.py <target>` oracle-install behavior.
2. **Skills copied with helpers.** The target receives
   `.claude/skills/servo-scaffold-init/`,
   `.claude/skills/servo-quality-gate/`, and
   `.claude/skills/servo-agent-loop/`, each with `SKILL.md` and required
   helper files.
3. **Agents copied with prefixes.** The target receives
   `.claude/agents/servo-runner.md` and
   `.claude/agents/servo-judge.md`.
4. **Templates copied.** The target receives
   `.claude/servo/templates/` with the same required templates as the
   plugin contract.
5. **Scaffold manifest written.** The target receives
   `.claude/servo/scaffold-install.json` recording source version,
   timestamp, copied skills, copied agents, copied templates, and
   managed marker.
6. **Self-contained smoke.** In a temp target with
   `${CLAUDE_PLUGIN_ROOT}` unset or invalid, at least one scaffolded
   helper command runs using only files under the target.
7. **Scaffold verifier.** `python3 scripts/verify_install.py scaffold
   <target>` passes for a valid scaffolded target and fails
   actionably when any managed required artifact is missing.

**DoD:**

- [x] Tests cover new scaffold mode, preservation of old oracle-install
  behavior, idempotency, self-contained helper smoke, and scaffold
  verifier success/failure.
- [x] No real `.claude/settings.json` hook entries are written while the
  contract hook list is empty.
- [x] Deviation log produced under this slice.
- [x] Independent review pass completed before DONE. _Independent reviewer
  (general-purpose subagent), 2026-06-01 — **PASS**. All 7 ACs met and
  meaningfully tested; `scaffold.py` byte-for-byte unchanged (AC1); AC6 smoke
  verified with `CLAUDE_PLUGIN_ROOT` unset; verifier failures distinct and
  actionable (AC7); no design-principle violations. Findings: one cosmetic
  docstring (fixed in `verify_install.py`); two scaffold-mode fidelity gaps
  deferred to 007-04 (logged below)._

**Anti-horizontal-phasing check:** After this slice, servo can be used
from a project-local `.claude/` copy, not only from a plugin checkout.

**Deviation log (after reconciliation):**

- **Shared helper, not a `scaffold.py` mode.** Per AC1's "either through
  `skills/scaffold-init/scaffold.py` or a shared install helper", the
  runtime-scaffold ships as a new `scripts/scaffold_runtime.py` that reads
  `.claude-plugin/install-contract.json`. `scaffold.py`'s bare-positional
  oracle-install (`scaffold.py <target>`) is untouched; a regression test
  asserts it still writes `oracle.sh` + `.servo/install.json` and does *not*
  create the runtime layout. This keeps the "one data-driven contract + one
  verifier" architecture from 007-01/007-02 intact.
- **CLI shape.** `scaffold_runtime.py` takes a single bare positional
  `<target>` (no subcommand) since it has exactly one job; this mirrors the
  ergonomics of the oracle-install form without colliding with it.
- **Source-of-truth for the verifier.** The scaffold target does not carry
  `.claude-plugin/install-contract.json`, so `verify_install.py scaffold`
  loads the contract from the servo source checkout that ships the verifier
  (`_source_root()`) and checks the servo-prefixed vendored copies under the
  target.
- **Self-contained smoke command.** Chosen helper is the vendored
  `scaffold.py detect <target>`. It only inspects the target directory and
  performs an `.exists()` probe for co-installed jig at
  `plugin_root()/jig/...`; with `CLAUDE_PLUGIN_ROOT` unset it falls back to
  `parents[2]` (the target's `.claude/`), finds no jig, and uses built-in
  detection — no template loading, so it runs purely from files under the
  target. `gate.py`/`loop.py` were not chosen because they need richer
  inputs; `detect` is the minimal plugin-root-independent command.
- **Manifest.** `scaffold-install.json` uses `schema_version: 1` and records
  `source_version` (from `.claude-plugin/plugin.json`), `timestamp`
  (`iso_now`, `YYYY-MM-DDTHH:MM:SSZ`), `managed_marker`
  (`managed-by-servo`), and the prefixed `skills` / `agents` / `templates`
  lists. Written with `sort_keys=True` for deterministic re-runs.
- **Idempotency.** Re-running overwrites managed files in place
  (`shutil.copy2`) and rewrites the manifest; the managed file set is
  unchanged on re-run (covered by tests). Only `timestamp` changes between
  runs.
- **`_write_human` header.** Made mode-aware (`PASS <mode> ...`) instead of
  the hard-coded `PASS plugin ...`; no existing test asserted on the human
  header, and scaffold output would otherwise misreport the mode.
- **Known gaps deferred to 007-04 (surfaced by the independent review).** Two
  scaffold-mode fidelity gaps are out of scope here but recorded for
  traceability: (1) the vendored *oracle-install* command
  (`servo-scaffold-init/scaffold.py <target>`) is not yet self-contained —
  with `CLAUDE_PLUGIN_ROOT` unset its `plugin_root()` fallback resolves to
  `<target>/.claude` but templates are vendored to
  `<target>/.claude/servo/templates`, so it fails to find
  `oracle.sh.template`; (2) the vendored `SKILL.md` copies still contain
  `${CLAUDE_PLUGIN_ROOT}` references. AC6 is still met (the `detect` command
  is self-contained), but both are squarely 007-04's AC1 ("no stale
  plugin-root commands") / AC6 ("no source checkout references").

---

