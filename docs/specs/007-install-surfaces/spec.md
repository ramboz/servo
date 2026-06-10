---
status: DONE
dependencies: [001, 002, 003]
last_verified: 2026-06-01
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
| `stale_source_reference` | Managed scaffold markdown references the plugin checkout (`${CLAUDE_PLUGIN_ROOT}`) or an unresolved repo-relative path. _(007-04; distinct from `artifact_missing`.)_ |
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

## Slices

- [007-01 — plugin-contract-verifier](slice-01-plugin-contract-verifier.md)
- [007-02 — release-zip](slice-02-release-zip.md)
- [007-03 — scaffold-runtime](slice-03-scaffold-runtime.md)
- [007-04 — scaffold-fidelity](slice-04-scaffold-fidelity.md)
- [007-05 — docs-and-ci](slice-05-docs-and-ci.md)

