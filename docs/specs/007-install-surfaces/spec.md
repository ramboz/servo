---
status: IN_PROGRESS
dependencies: [001, 002, 003]
last_verified:
---

# Spec 007 - install-surfaces

> Make servo installable through the same three surfaces that made jig
> usable in practice: plugin marketplace metadata, a deterministic
> release zip, and a project-local scaffold mode that vendors the runtime
> machinery into a target repo. Every surface gets the same contract and
> the same verifier.

## Why this spec

Servo currently has the start of a plugin:

- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- skills and agents in the repo
- `/servo:scaffold-init`, which installs a project-owned `oracle.sh` and
  `.servo/install.json`

That is not the same thing as a complete install story.

Jig has already worked through the operational shape:

- a local plugin can be installed and dogfooded;
- a release zip is deterministic and install-smoked;
- scaffold mode can copy jig's skills, agents, hooks, scripts, and
  settings into a target project's `.claude/`;
- verification scripts can check plugin, zip, and scaffold installs
  without needing the model to reason from scratch each time.

Servo needs the same boring reliability before it asks users to trust
unattended loops. A loop that cannot find its skill helper, runner
agent, template files, or generated oracle is not a product problem; it
is an installation-contract problem.

This spec creates that contract before servo grows more runtime
surfaces. Future specs for hooks, races, and spec-oracles should extend
the contract rather than invent new validators.

## Current gap

Implemented today:

- Plugin and marketplace descriptor stubs.
- Skills: `scaffold-init`, `quality-gate`, `agent-loop`.
- Agents: `runner`, `judge`.
- Templates for project-owned `oracle.sh` and signal components.
- Target install manifest at `<target>/.servo/install.json`.

Missing today:

- No install contract that names required plugin artifacts.
- No plugin-root verifier.
- No release zip builder.
- No release zip smoke test.
- No manifest validator beyond JSON parse by consumers.
- No scaffold mode that vendors servo runtime machinery into
  `<target>/.claude/`.
- No generated-doc/path fidelity checks for scaffolded copies.
- No CI or release recipe proving install artifacts stay coherent.

## Goals

1. **Define one install contract.** Servo should have a versioned,
   data-driven contract that names required skills, agents, templates,
   scripts, hook entries, and scaffold destinations.
2. **Verify plugin installs.** A fast stdlib-only verifier should prove
   a plugin root has coherent manifests and all required artifacts.
3. **Build deterministic release zips.** A release zip should contain
   the plugin runtime users need, exclude tests/dev/historical files,
   carry the manifest version, and pass the same verifier after extract.
4. **Support project-local scaffold mode.** Users should be able to copy
   servo runtime machinery into a target repo's `.claude/` tree, with
   prefixed names that do not collide with project-local or jig assets.
5. **Keep scaffold copies self-contained.** Scaffolded skills should run
   without `${CLAUDE_PLUGIN_ROOT}` and without reaching back into the
   source checkout.
6. **Make future surfaces additive.** When specs 004, 005, and 006 ship
   hooks, race orchestration, or spec-oracle helpers, they should update
   the contract and inherit verifier coverage.
7. **Document the install choices.** README and skill docs should state
   when to use plugin install, release zip install, or project-local
   scaffold mode.

## Non-goals

- **No public marketplace submission.** This spec prepares the
  descriptor and install artifacts; it does not require publishing a
  public listing or cutting a public release.
- **No new runtime behavior.** Hook installation, worktree racing, and
  spec-oracle generation remain owned by specs 004, 005, and 006.
- **No change to the oracle contract.** The project-owned `oracle.sh`
  and `.servo/install.json` semantics from specs 001 and 002 remain
  intact.
- **No hard dependency on jig.** Jig is the reference implementation
  pattern, not a runtime dependency.
- **No package-manager abstraction.** This spec covers Claude Code
  plugin/scaffold surfaces, not Homebrew, npm, pip, or system package
  managers.

## Core model

Servo has two different things called "install" unless we name them
carefully:

| Layer | What is installed | Destination | Owner |
|---|---|---|---|
| **Servo runtime install** | Skills, agents, templates, scripts, hook entries, descriptors | Plugin root, release zip, or `<target>/.claude/` | Servo |
| **Project oracle install** | `oracle.sh`, `.servo/install.json`, refinement notes, future spec overlays | Target project root | Project |

Spec 001 implemented the second layer. This spec implements the first.

The three runtime install surfaces share one contract:

1. **Plugin root** - a checked-out servo repo or installed plugin
   directory with `.claude-plugin/` metadata.
2. **Release zip** - a deterministic archive of the same runtime
   artifacts, installable by Claude Desktop or `claude --plugin-dir`.
3. **Project-local scaffold** - copied runtime machinery under
   `<target>/.claude/`, useful when a project should carry the exact
   servo surface it was built with.

The verifier should treat these as different projections of the same
contract, not three unrelated implementations.

## Install contract

Add a versioned contract file:

```
.claude-plugin/install-contract.json
```

Initial shape:

```json
{
  "schema_version": 1,
  "plugin_name": "servo",
  "version_source": ".claude-plugin/plugin.json",
  "required": {
    "skills": ["scaffold-init", "quality-gate", "agent-loop"],
    "agents": ["runner", "judge"],
    "templates": [
      "oracle.sh.template",
      "components/pytest.sh.fragment",
      "components/vitest.sh.fragment",
      "components/jest.sh.fragment",
      "components/cargo.sh.fragment",
      "components/go.sh.fragment",
      "components/eslint.sh.fragment",
      "components/ruff.sh.fragment"
    ],
    "hooks": [],
    "scripts": []
  },
  "release_zip": {
    "include": [
      ".claude-plugin/",
      "agents/",
      "skills/",
      "templates/",
      "hooks/",
      "README.md",
      "LICENSE"
    ],
    "exclude_globs": [
      "**/__pycache__/**",
      "**/.pytest_cache/**",
      "**/test_*.py",
      "**/*.pyc",
      "**/.DS_Store",
      "**/.gitkeep",
      ".git/**",
      "docs/**",
      "dist/**",
      "mcp-server.log",
      "templates/crew-postmortem.md"
    ]
  },
  "scaffold": {
    "skill_prefix": "servo-",
    "agent_prefix": "servo-",
    "runtime_root": ".claude/servo",
    "managed_marker": "managed-by-servo"
  }
}
```

The exact field names may evolve during implementation, but the
contract must stay data-driven. Future specs should add expected
artifacts by editing this contract plus tests, not by hard-coding new
path lists in every script.

## Release zip contract

The release zip should be a flat plugin archive, not a repo snapshot.

Included:

- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.claude-plugin/install-contract.json`
- `agents/runner.md`
- `agents/judge.md`
- required `skills/*/SKILL.md` files and their runtime helpers
- required `templates/`
- `hooks/` when hooks exist; empty hook directory is allowed in v1
- `README.md`
- `LICENSE`

Excluded:

- tests
- caches
- `.git/`
- docs/spec history
- local logs
- build output
- contributor-only files unless explicitly needed at runtime

The builder should smoke-test the zip by extracting it into a temp dir
and running the plugin verifier against the extracted root.

## Scaffold-mode contract

Project-local scaffold mode copies servo runtime machinery into a target
repo while preserving current spec 001 behavior.

Expected initial layout:

```
<target>/
|-- .claude/
|   |-- agents/
|   |   |-- servo-runner.md
|   |   `-- servo-judge.md
|   |-- skills/
|   |   |-- servo-scaffold-init/
|   |   |   |-- SKILL.md
|   |   |   `-- scaffold.py
|   |   |-- servo-quality-gate/
|   |   |   |-- SKILL.md
|   |   |   `-- gate.py
|   |   `-- servo-agent-loop/
|   |       |-- SKILL.md
|   |       `-- loop.py
|   `-- servo/
|       |-- install-contract.json
|       |-- scaffold-install.json
|       `-- templates/
|           `-- ...
|-- .servo/
|   `-- install.json
`-- oracle.sh
```

Rules:

- Scaffold mode is explicit in this spec. Existing
  `scaffold.py <target>` behavior stays compatible.
- Scaffolded skill names are prefixed with `servo-` to avoid collisions
  with project-local skills and jig's `jig-*` names.
- Scaffolded agents are prefixed with `servo-`.
- Skill docs and helper command examples must be rewritten so they work
  from the target repo and do not mention `${CLAUDE_PLUGIN_ROOT}` unless
  discussing plugin mode.
- Helper scripts must resolve sibling files relative to their own
  location or the scaffold manifest, not the original checkout.
- `.claude/settings.json` is touched only when the install contract has
  hook entries. Because servo has no shipped hooks yet, the first
  implementation should exercise the settings reconciler with fixtures
  but perform no hook mutation in real scaffold mode.
- Re-running scaffold mode is idempotent for managed files and preserves
  unmanaged user files.

## Verifier commands

Add a single verifier entry point:

```bash
python3 scripts/verify_install.py plugin <plugin-root>
python3 scripts/verify_install.py zip <zip-path>
python3 scripts/verify_install.py scaffold <target-root>
```

Required properties:

- stdlib-only;
- fast enough for normal CI;
- human-readable failures by default;
- optional `--json` output with stable `reason` codes;
- failure messages name the missing or invalid path;
- plugin and zip verification read `.claude-plugin/install-contract.json`;
- scaffold verification reads the scaffolded copy of that contract under
  `.claude/servo/install-contract.json`.

Suggested initial reason taxonomy:

| Reason | Meaning |
|---|---|
| `contract_missing` | Required install contract file missing. |
| `contract_malformed` | Contract is not valid JSON or has unsupported schema. |
| `manifest_missing` | Plugin or marketplace descriptor missing. |
| `manifest_mismatch` | Descriptor name/version/source does not match contract. |
| `artifact_missing` | Required skill, agent, template, script, or hook missing. |
| `artifact_forbidden` | Release zip contains excluded files. |
| `zip_invalid` | Zip cannot be opened or has unsafe paths. |
| `scaffold_manifest_missing` | Project-local scaffold manifest missing. |
| `scaffold_not_self_contained` | Scaffolded helper reaches back to plugin checkout. |
| `settings_invalid` | Managed hook settings cannot be parsed or reconciled. |

## Guardrails

- **No silent fixture success.** Zip and scaffold verifiers must be run
  against real temp extractions/copies, not only synthetic path lists.
- **No source-checkout dependency in scaffold mode.** Tests should unset
  `${CLAUDE_PLUGIN_ROOT}` or point it at a nonexistent path before
  running scaffolded helper smoke checks.
- **No stale doc commands.** Scaffolded docs and examples must use paths
  that exist inside the scaffold target.
- **No accidental release bloat.** Release zip tests should assert both
  required inclusions and forbidden exclusions.
- **No hook-settings side effects before hooks ship.** The machinery can
  be implemented and fixture-tested, but real scaffold mode should leave
  `.claude/settings.json` alone while `required.hooks` is empty.
- **No duplicated artifact lists.** The contract file is the source of
  truth. Scripts may normalize it, but should not carry parallel lists.

## SPIDR analysis

| Technique | Question | Decision |
|---|---|---|
| **S - Spike** | Can jig's install pattern transfer to servo without dragging supervised-workflow assumptions with it? | **Yes, with a servo-specific contract.** Reuse the three surfaces, not jig's exact artifact list. |
| **P - Path** | Zip first or scaffold first? | **Contract first.** Plugin, zip, and scaffold all become cheaper once they share expected artifacts. |
| **I - Interface** | What is the stable boundary? | `.claude-plugin/install-contract.json`, `scripts/verify_install.py`, `scripts/build_release_zip.py`, and scaffolded `.claude/servo/scaffold-install.json`. |
| **D - Data** | What data prevents drift? | Required artifacts, release include/exclude rules, scaffold prefixes, managed marker, plugin manifest version. |
| **R - Rules** | What prevents broken installs? | Verifier gates, zip smoke extraction, self-contained scaffold smoke tests, and fixture coverage for missing artifacts. |

## Slice index

| Slice | Title | Goal |
|---|---|---|
| 007-01 | plugin-contract-verifier | Add the data-driven install contract and verify a plugin root against it. |
| 007-02 | release-zip | Build deterministic release zips and smoke-test extracted archives with the plugin verifier. |
| 007-03 | scaffold-runtime | Copy servo runtime machinery into a target `.claude/` tree and verify it as self-contained. |
| 007-04 | scaffold-fidelity | Harden generated docs, path rewrites, version provenance, idempotency, and stale-reference checks. |
| 007-05 | docs-and-ci | Document install choices and wire install-contract checks into repo automation. |

---

## Slice 007-01 - plugin-contract-verifier

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

## Slice 007-02 - release-zip

**Goal:** A deterministic release zip builder that packages only the
runtime artifacts named by the contract and proves the extracted archive
passes plugin verification. End-to-end value: servo can be distributed
as a single installable archive instead of a whole development checkout.

**DoR:**

- 007-01 DONE.
- Release zip include/exclude policy agreed in the contract.
- Plugin verifier can run against arbitrary extracted directories.

**Acceptance Criteria:**

1. **Zip builds.** `python3 scripts/build_release_zip.py --output
   <path>` writes a zip containing the required runtime artifacts and no
   top-level wrapping directory.
2. **Deterministic output.** Running the builder twice against the same
   tree produces byte-identical zip files.
3. **Forbidden files excluded.** Tests, caches, `.git/`, docs, dist
   outputs, logs, and Python bytecode are not present in the archive.
4. **Version source.** The builder reads the version from
   `.claude-plugin/plugin.json`; if a requested version or output name
   conflicts with the manifest version, it fails clearly.
5. **Smoke extraction.** With the default smoke behavior, the builder
   extracts the zip into a temp dir and runs
   `verify_install.py plugin <extract-root>` against it.
6. **Unsafe paths refused.** The verifier rejects zips with absolute
   paths or `..` traversal entries.

**DoD:**

- [x] Builder tests cover inventory, exclusions, determinism, version
  mismatch, smoke extraction, and unsafe path rejection. _23 tests in
  `scripts/test_build_release_zip.py`; 37 total script tests with
  `scripts/test_verify_install.py`._
- [x] `dist/` remains ignored or otherwise untracked. _Added to
  `.gitignore`._
- [x] README documents the zip install command after this slice or in
  007-05 if docs are intentionally deferred. _Deferred to 007-05 so
  the public docs land once plugin, zip, and scaffold surfaces can be
  described together._
- [x] Deviation log produced under this slice.
- [x] Independent review pass completed before DONE. _Final subagent
  review (`Halley`), 2026-05-28: PASS, no blocker or should-fix
  findings._

**Anti-horizontal-phasing check:** After this slice, a user can build a
release archive locally and verify that the extracted plugin is
installable.

### Deviation log

**Slice 007-02 - implementation started 2026-05-28.** Added
`scripts/build_release_zip.py`, `verify_install.py zip` mode, and
`scripts/test_build_release_zip.py`. Verification:

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_build_release_zip.py`
  -> 23/23 tests passing.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts -p 'test_*.py'`
  -> 37/37 tests passing.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_release_zip.py --output /private/tmp/servo-v0.1.0.zip`
  -> built a 21-entry archive and smoke-verified it through
  `verify_install.py zip`.

Deviations from draft spec text:

- **`--version` is optional.** The spec says the builder reads the
  version from `.claude-plugin/plugin.json`; implementation follows
  that as the default and treats `--version` as an optional assertion
  that must match the manifest.
- **Filename version mismatch is pattern-based.** Output filenames of
  the form `servo-v<version>.zip` are checked against the manifest
  version. Arbitrary filenames such as `servo-test.zip` are allowed for
  local smoke builds.
- **Local metadata exclusion added.** The implementation adds
  `**/.DS_Store`, `**/.gitkeep`, and
  `templates/crew-postmortem.md` to `release_zip.exclude_globs`; these
  are deterministic-release hygiene rules in the spirit of "caches /
  local logs / dev files" even though the initial JSON sketch did not
  spell them out.
- **README install docs deferred.** 007-05 owns the public install docs
  for plugin, zip, and scaffold together; this slice records the
  deferral rather than adding zip-only docs early.

### Review reconciliation

Independent review:

- `Nash` subagent, 2026-05-28: **FAIL** with two should-fix findings.
  1. Release zip inventory included non-runtime sentinel/contributor
     files (`hooks/.gitkeep`, `skills/.gitkeep`, and
     `templates/crew-postmortem.md`).
  2. Unsafe-path validation missed Windows-drive absolute paths such as
     `C:/evil.txt`.

Reconciliation:

- Added `**/.gitkeep` and `templates/crew-postmortem.md` to
  `release_zip.exclude_globs`; added
  `test_gitkeep_and_crew_postmortem_excluded`.
- Added Windows drive/absolute detection via `PureWindowsPath`; added
  `test_windows_drive_absolute_entry_rejected`.
- Re-ran focused checks: release zip tests now 21/21; script discovery
  now 35/35; real zip build now contains 21 runtime entries.

Independent follow-up review:

- `Boyle` subagent, 2026-05-28: **FAIL** with one should-fix finding.
  The builder accepted unsafe `release_zip.include` entries such as
  `../outside.txt` when `--no-smoke` was used, allowing it to write an
  unsafe archive before the verifier could reject it.

Reconciliation:

- Added release-include and final-archive path validation in
  `scripts/build_release_zip.py`, including Windows drive detection.
- Added `UnsafeContractTests` for parent traversal and Windows-drive
  include paths.
- Re-ran focused checks: release zip tests now 23/23; script discovery
  now 37/37; real zip build still contains 21 runtime entries.

Independent final review:

- `Halley` subagent, 2026-05-28: **PASS**. No blocker or should-fix
  findings. Verified that all three prior findings are fixed: forbidden
  sentinel/contributor files are absent from the inventory, `C:/evil.txt`
  is rejected by zip verification, and unsafe contract include paths are
  rejected before the builder writes an archive.

Slice 007-02 is DONE. Slices 007-03 through 007-05 remain DRAFT.

---

## Slice 007-03 - scaffold-runtime

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

- [ ] Tests cover new scaffold mode, preservation of old oracle-install
  behavior, idempotency, self-contained helper smoke, and scaffold
  verifier success/failure.
- [ ] No real `.claude/settings.json` hook entries are written while the
  contract hook list is empty.
- [ ] Deviation log produced under this slice.
- [ ] Independent review pass completed before DONE.

**Anti-horizontal-phasing check:** After this slice, servo can be used
from a project-local `.claude/` copy, not only from a plugin checkout.

---

## Slice 007-04 - scaffold-fidelity

**Goal:** Harden the project-local scaffold output so generated docs,
commands, links, helper paths, and version provenance reflect the target
copy rather than stale plugin-checkout assumptions. End-to-end value:
scaffolded servo does not hand users commands that fail immediately.

**DoR:**

- 007-03 DONE.
- At least one scaffolded temp target fixture exists.
- Known jig gaps from specs 046 and 047 have been reviewed.

**Acceptance Criteria:**

1. **No stale plugin-root commands.** Scaffolded `SKILL.md` files and
   generated helper instructions do not contain
   `${CLAUDE_PLUGIN_ROOT}` for commands meant to run in scaffold mode.
2. **Runnable examples.** Every scaffold-mode command example emitted by
   servo docs or generated files is exercised in a temp scaffold target,
   or explicitly marked as illustrative and excluded by a testable
   marker.
3. **Local links resolve.** Relative links in scaffolded Markdown files
   resolve inside the scaffold target or are rewritten/removed.
4. **Version provenance.** Scaffolded manifests record the version from
   `.claude-plugin/plugin.json`, not a hard-coded fallback.
5. **Idempotent upgrade.** Re-running scaffold mode updates managed
   files and the scaffold manifest while preserving unmanaged files
   under `.claude/`.
6. **No source checkout references.** The scaffold verifier detects
   managed files that reference the original servo checkout for runtime
   helper paths.

**DoD:**

- [ ] Tests cover stale path detection, command smoke, link resolution,
  version provenance, and idempotent upgrade.
- [ ] The verifier output distinguishes "missing artifact" from
  "artifact exists but points at the wrong source."
- [ ] Deviation log produced under this slice.
- [ ] Independent review pass completed before DONE.

**Anti-horizontal-phasing check:** After this slice, scaffold mode is not
only present; it is polished enough that a user can follow its generated
instructions without knowing servo's source checkout layout.

---

## Slice 007-05 - docs-and-ci

**Goal:** Document the install surfaces and run install-contract checks
as part of normal repo verification. End-to-end value: contributors can
change servo artifacts without accidentally breaking plugin install,
release zip install, or project-local scaffold install.

**DoR:**

- 007-01 through 007-04 DONE.
- Repo verification command(s) are known.
- Decision made whether this repo should add GitHub Actions now or only
  a local verification script.

**Acceptance Criteria:**

1. **README install section.** README explains plugin install, release
   zip install, and project-local scaffold mode, including when to
   choose each.
2. **Spec/docs status updated.** `docs/product-vision.md`,
   `docs/architecture.md`, and `docs/specs/README.md` describe install
   surfaces using the two-layer distinction: servo runtime install vs
   project oracle install.
3. **One verification command.** A single documented local command runs
   plugin verifier tests, zip builder tests, and scaffold verifier
   tests.
4. **Automation wired.** CI, if present or added in this slice, runs the
   install verification command on PR and push. If CI is deferred, the
   deferral is recorded with a resolution trigger.
5. **Release recipe.** Docs include the manual release recipe for
   building and verifying the zip. If release-please or GitHub release
   asset automation is added, tests/docs cover its expected artifact
   name.

**DoD:**

- [ ] Docs reviewed for stale path examples.
- [ ] Local verification command passes.
- [ ] CI decision recorded if automation is not added.
- [ ] Deviation log produced under this slice.
- [ ] Independent review pass completed before DONE.

**Anti-horizontal-phasing check:** After this slice, install reliability
is part of servo's ordinary development loop, not an oral tradition.
