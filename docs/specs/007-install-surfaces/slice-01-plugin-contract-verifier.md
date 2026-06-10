---
status: DONE
dependencies: []
last_verified:
---

## Slice 007-01 — plugin-contract-verifier

**Goal:** A data-driven install contract plus verifier for a servo plugin
root. End-to-end value: a user or CI job can prove a checked-out servo
plugin has coherent manifests and the expected runtime artifacts before
trying to install or package it.

**DoR:**

- Specs 001, 002, and 003 are DONE.
- Current plugin manifests exist.
- Required v1 runtime artifacts are known: three skills, two agents,
  oracle templates, and no hooks.
- Jig's install specs and scripts have been reviewed as reference
  material.

**Acceptance Criteria:**

1. **Contract file exists.** `.claude-plugin/install-contract.json`
   parses as JSON, has `schema_version: 1`, and names the plugin
   `servo`.
2. **Manifest alignment.** `scripts/verify_install.py plugin <root>`
   verifies `.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json` exist, parse, name `servo`, and
   agree with the contract.
3. **Artifact presence.** The plugin verifier checks every required
   skill has `SKILL.md`, every required skill helper named by the
   contract exists, every required agent exists, and every required
   template exists.
4. **Empty hooks are explicit.** The contract records `hooks: []`;
   the verifier accepts that state and does not require
   `.claude/settings.json` or hook scripts in v1.
5. **Actionable failures.** Removing or corrupting any required
   manifest, skill, agent, or template in a temp copy makes the verifier
   exit non-zero with a reason code and the offending path.
6. **JSON output.** `--json` emits one JSON object with
   `schema_version`, `mode`, `status`, `plugin_name`, `version`, and
   `failures`.

**DoD:**

- [x] All ACs pass; verifier tests cover success and one failure fixture
  per reason introduced in this slice. _14 tests in
  `scripts/test_verify_install.py`._
- [x] Verifier is stdlib-only and runs under Python 3.10+.
- [x] `docs/specs/README.md` is updated with slice status.
- [x] Deviation log produced under this slice.
- [x] Independent review pass completed before DONE. _Subagent review
  (`Kuhn`), 2026-05-28: PASS, no blocker or should-fix findings._

**Anti-horizontal-phasing check:** After this slice, servo still cannot
build a zip or scaffold into a target, but it can answer the first
install question: "is this plugin root structurally installable?"

### Deviation log

**Slice 007-01 - implementation started 2026-05-28.** Added
`.claude-plugin/install-contract.json`, `scripts/verify_install.py`, and
`scripts/test_verify_install.py`. Verification:

- `python3 scripts/test_verify_install.py` -> 14/14 tests passing.
- `python3 scripts/verify_install.py plugin . --json` -> pass with
  `plugin_name=servo`, `version=0.1.0`.
- Existing skill-surface smoke:
  `python3 -m unittest skills.scaffold-init.test_skill_surface skills.quality-gate.test_skill_surface skills.agent-loop.test_skill_surface`
  -> 57/57 tests passing.

Deviations from draft spec text:

- **Skill contract entries became objects, not strings.** The draft
  sketch used `"skills": ["scaffold-init", ...]`, but AC #3 requires
  helper files to be named by the contract. Implemented entries as
  `{ "name": "...", "files": ["SKILL.md", "<helper>.py"] }`.
- **Added `manifest_malformed` reason.** The suggested taxonomy had
  `manifest_missing` and `manifest_mismatch`, but corrupt JSON is
  neither. The verifier now reports `manifest_malformed` for plugin and
  marketplace descriptor parse failures.
- **Only plugin mode exists in this slice.** The top-level verifier
  command section already names `zip` and `scaffold`; those subcommands
  remain future work for slices 007-02 and 007-03.

Independent review:

- `Kuhn` subagent, 2026-05-28: **PASS**. Reviewed the tracked diff plus
  untracked full files
  `.claude-plugin/install-contract.json`,
  `scripts/verify_install.py`, and `scripts/test_verify_install.py`.
  No blocker or should-fix issues found.

Slice 007-01 is DONE. Slices 007-02 through 007-05 remain DRAFT.

---

