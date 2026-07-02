# servo

> A Claude Code plugin that **compiles engineering intent into executable evaluation** — an Evaluation-Driven Development engine.

**servo** (noun): a closed-loop control system — measures a signal, compares it to a target, and adjusts until they match. That control loop is exactly what servo automates over *engineering evaluation*: compile the target (the oracle), measure the implementation against it, and iterate until they converge.

## Why servo exists

[jig](https://github.com/ramboz/jig) handles **supervised** spec-driven development: a human reviews each slice before the next one starts. Jig owns **engineering intent** — understanding problems, designing solutions, writing specs. Servo owns the next thing: **engineering evaluation**. Given a spec, it decides whether the work suits Evaluation-Driven Development, **compiles the spec into an executable oracle + evidence + execution plan**, and runs an implementation against that compiled evaluation until it converges.

The autonomous loop people associate with this — agent loops scored against an oracle, hooks that grade every `Stop`, worktree races — is **one consumer** of the compiled evaluation, not the headline. Evaluation is the source of truth; execution is an optimization process against it. Those execution surfaces carry a different risk profile, maturity, and audience from jig's: they spawn N parallel agents, install hooks, race worktrees that cost real money. Bundling them into jig would silently expand its scope. Servo is the **evaluation-owning sibling** that keeps the contract explicit. See [ADR-0014](docs/decisions/adr-0014-evaluation-compiler.md).

## What it does

Servo has two phases ([architecture](docs/architecture.md#two-phases-servo-compile-and-servo-run)):

- **Servo Compile** — turn a spec into executable evaluation. Its primary entry point is a **scaffolder**, not a runtime: it probes the target project's signals (tests, lint, CI, language, project size) and drops a tailored `oracle.sh` (plus optional execution artifacts) that reflects what the project actually has, instead of a generic stub the dev rewrites. `/servo:spec-oracle` goes further, compiling a spec's acceptance criteria into a reviewable evidence overlay.
- **Servo Run** — execute an implementation against the compiled evaluation until convergence: the portable agent loop, per-`Stop` oracle hooks, worktree races, and scheduled dispatch. The execution loop is an *interchangeable runtime*, one stage of Run.

| Skill | Phase | Role | Status |
|---|---|---|---|
| `/servo:scaffold-init` | Compile | Probe target signals; drop tailored oracle (+ optional tier-1/2 artifacts) | Spec 001 — **DONE** |
| `/servo:spec-oracle` | Compile | Compile a spec/slice into a reviewable evidence overlay: AC mapping, deterministic checks, negative controls, and an installable oracle component | Spec 006 — **DONE** |
| `/servo:quality-gate` | Run | Run the scaffolded oracle; normalized exit codes | Spec 002 — **DONE** |
| `/servo:agent-loop` | Run | Headless iteration driver (the portable execution loop) with iteration cap, cost ceiling, checkpoint/resume, plateau detection, subagent dispatch; ADR-0008 rebase adds a `/goal`-driven driver, host-scope routing, detached (`--background`) + Routine-ready (`--emit-routine-prompt`) unattended runs | Spec 003 — **DONE** |
| `/servo:oracle-hook` | Run | Claude Code hook installer (idempotent install / uninstall / status); meta-judge `Stop` hook scores each turn via the oracle and blocks below threshold | Spec 004 — **DONE** |
| `/servo:variant-race` | Run | N-worktree parallel race with oracle scoring and winner selection | Future spec |
| `/servo:heartbeat` | Compile + Run | Routine-triggered, read-only discovery over project signals → triage inbox → oracle-gated dispatch of each actionable finding into an isolated worktree loop, under one whole-heartbeat cost ceiling (the scheduled front-end) | Spec 011 — **DONE** |
| `/servo:design-eval` | Compile | Author a frozen UI design-fidelity eval component: capture app-vs-mockup screenshots, judge with a pinned vision model (n-sampled, lower-bound), freeze the definition, install a `score_design_fidelity` component into `oracle.sh` | Spec 012 — **DRAFT** |

## Relationship to jig

Servo is a **sibling plugin**, not a dependency. They coexist in `${CLAUDE_PLUGIN_ROOT}` and reference each other only via filesystem hints — no cross-plugin registration mechanism, no hard dependency.

- Install servo without jig (oracle/headless only) or jig without servo (current default, supervised only).
- Servo reuses jig's `tdd.py detect` (via subprocess) when jig is installed; falls back to its own minimal test-runner detection otherwise.
- Jig's `slice-land prepare` emits soft pull-hints for servo artifacts when servo-style infrastructure is missing — that's the entirety of the coupling.

## Installing servo

Servo has **two different things called "install"** — keep them separate:

- **Servo runtime install** — getting servo's own skills, agents, templates,
  and descriptors onto your machine so the `/servo:*` commands exist. This
  section.
- **Project oracle install** — running `/servo:scaffold-init` *inside a target
  project* to drop a tailored `oracle.sh` + `.servo/install.json` into that
  repo. That is the [scaffolded `oracle.sh`](#the-scaffolded-oraclesh) below,
  not a way to install servo itself.

The runtime install has **three surfaces**, all validated by one data-driven
contract (`.claude-plugin/install-contract.json`) and one verifier
(`scripts/verify_install.py`). Pick by how much you want servo coupled to a
shared checkout. Runtime install/scaffold paths refresh a best-effort
availability marker at `${XDG_STATE_HOME:-$HOME/.local/state}/servo/available.json`
so sibling tools can cheaply detect that servo has been observed on the
machine.

| Surface | Use when | Coupled to source checkout? |
|---|---|---|
| **Plugin install** | You develop/dogfood servo, or installed it as a plugin | Yes (`${CLAUDE_PLUGIN_ROOT}`) |
| **Release zip** | You want a single installable archive for Claude Desktop / `--plugin-dir` | No (self-contained archive) |
| **Project-local scaffold** | A project should carry the exact servo surface it was built with | No (vendored into the project) |

### Plugin install

A checked-out servo repo (or an installed plugin directory) is already a
plugin root: it has `.claude-plugin/` metadata, and its skill/agent commands
reference helpers via `${CLAUDE_PLUGIN_ROOT}`. Verify a plugin root is
structurally installable before trusting it:

```bash
python3 scripts/verify_install.py plugin .
```

Successful plugin verification refreshes the servo availability marker at
`${XDG_STATE_HOME:-$HOME/.local/state}/servo/available.json`.

### Release zip install

Build a deterministic, runtime-only archive (no tests, docs, caches, or
`.git/`) and install it via `claude --plugin-dir <extracted-dir>` or Claude
Desktop's plugin import:

```bash
# Build → dist/servo-v<version>.zip (version read from .claude-plugin/plugin.json)
python3 scripts/build_release_zip.py

# Verify an already-built archive (substitute the real version)
python3 scripts/verify_install.py zip dist/servo-v<version>.zip
```

The builder smoke-tests the archive by default: it extracts the zip into a
temp dir and runs the plugin verifier against the extracted root, so a built
zip is a verified zip.

### Project-local scaffold install

Vendor servo's runtime machinery into a target repo's `.claude/` tree. The
copied skills and agents are `servo-` prefixed (so they never collide with
project-local or `jig-*` assets) and are **self-contained** — their commands
do not reference `${CLAUDE_PLUGIN_ROOT}` and do not reach back into the source
checkout:

```bash
# Vendors servo-prefixed skills/agents + templates into <target>/.claude/
python3 scripts/scaffold_runtime.py <target>

# Verify the scaffolded copy
python3 scripts/verify_install.py scaffold <target>
```

This is distinct from `/servo:scaffold-init` (the [project oracle
install](#the-scaffolded-oraclesh)): scaffold *runtime* copies servo itself
into `<target>/.claude/`; scaffold *init* writes a project's own `oracle.sh`
and `.servo/install.json`.

### Release recipe

Releases are **automated** via [release-please](.github/workflows/release.yml)
(see [CONTRIBUTING.md](CONTRIBUTING.md) for the flow). The primary install
artifact is the **`servo-v<version>.zip` asset attached to the
[latest GitHub release](https://github.com/ramboz/servo/releases/latest)** —
download it and install it as in [Release zip install](#release-zip-install).
CI builds and smoke-tests each release's zip before uploading it, so a
published asset is a verified asset.

To build the same archive **locally** (for development, or as a fallback — this
is *not* how releases are published):

```bash
# Build → dist/servo-v<version>.zip (version read from .claude-plugin/plugin.json)
python3 scripts/build_release_zip.py

# Verify the produced archive (substitute the real version)
python3 scripts/verify_install.py zip dist/servo-v<version>.zip
```

`dist/` is git-ignored; the archive is a build artifact, not a tracked file.
The version in `.claude-plugin/plugin.json` is **release-managed** by
release-please — do not hand-edit it.

### Verifying all surfaces at once

One command runs the plugin verifier against the live checkout and the full
install-surface test suite (plugin verifier, zip builder, scaffold
verifier/runtime, and the docs stale-path guard). This is what CI runs on
every push and pull request:

```bash
bash scripts/verify_install_surfaces.sh
```

## The scaffolded `oracle.sh`

`oracle.sh` is a thin bash driver around a list of **components**. Each component is a function that scores its slice of project quality in `[0.0, 1.0]`; the driver compares that score directly against `THRESHOLD` for the common single-component case, or computes a weighted average across components when two or more are registered.

### Adding a component

Add a `# SEED:start <name>` / `# SEED:end <name>` block containing a `score_<name>` function, and register it in `COMPONENTS`:

```bash
COMPONENTS=(
  "placeholder:1.0"
  "pytest:2.0"        # new — weighted 2× as heavy
)

# SEED:start pytest
score_pytest() {
  if ! command -v pytest >/dev/null 2>&1; then
    echo "missing: pytest" >&2
    return 2          # exit 2 = environment error
  fi
  if pytest -q >/dev/null 2>&1; then
    echo "1.0"
  else
    echo "0.0"
  fi
}
# SEED:end pytest
```

The `# SEED:` markers are how servo locates blocks on re-scaffold — keep them on their own lines, exact spelling, even after edits.

### Exit codes (servo contract)

| Code | Meaning |
|---|---|
| 0 | composite ≥ `THRESHOLD` |
| 1 | composite < `THRESHOLD` |
| 2 | environment error (missing tool, no components, function returned other non-zero) |

These codes are stable across servo's runtime skills — `/servo:quality-gate`, `/servo:agent-loop`, and `/servo:variant-race` all depend on this contract.

## Design philosophy

> Compile evaluation first, run against it later. Per-project, signal-aware artifacts — never generic stubs. Evaluation is the source of truth; the loop optimizes toward it.

- Composite oracle score that reflects available signals (tests, lint, coverage, CI, seeded-issues)
- Hard guardrails on loops: iteration cap, cost ceiling, refuse on dirty tree, refuse without an oracle
- Hooks installed explicitly (never auto-installed); reversible install/uninstall
- Worktree races bounded (default 3 variants, hard cap 5)

See [docs/product-vision.md](docs/product-vision.md) for the vision and [docs/architecture.md](docs/architecture.md) for the mechanics. See [docs/specs/](docs/specs/) for spec state.

## License

[MIT](LICENSE)
