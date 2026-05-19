# servo

> A Claude Code plugin that scaffolds closed-loop, unattended agent operations into existing projects.

**servo** (noun): a closed-loop control system — measures a signal, compares it to a target, and adjusts until they match.

## Why servo exists

[jig](https://github.com/ramboz/jig) handles **supervised** spec-driven development: a human reviews each slice before the next one starts. Past that boundary lies a different practice — **unattended agent loops** scored against an oracle, hooks that grade every `Stop`, and worktree races that pick the best of N parallel attempts.

Those patterns share a different risk profile, maturity, and audience from jig's surface — they spawn N parallel agents, install hooks that fire every `Stop`, race worktrees that cost real money. Bundling them into jig would silently expand jig's scope. Servo is the **autonomous sibling** that keeps the contract explicit: installing servo means crossing the line into unattended operation.

## What it does

Servo's primary entry point is a **scaffolder**, not a runtime. It probes the target project's signals (tests, lint, CI, language, project size) and drops a tailored set of artifacts — `oracle.sh`, agent-loop driver, hook installer, race driver — that reflect what the project actually has, instead of a generic stub the dev has to rewrite.

| Skill | Role | Status |
|---|---|---|
| `/servo:scaffold-init` | Probe target signals; drop tailored oracle (+ optional tier-1/2 artifacts) | Spec 001 — **DONE** |
| `/servo:quality-gate` | Run the scaffolded oracle; normalized exit codes | Spec 002 — **DONE** |
| `/servo:agent-loop` | Headless iteration driver with iteration cap, cost ceiling, checkpoint/resume | Spec 003 — **IN PROGRESS** (slice 003-01 DONE) |
| `/servo:oracle-hook` | Claude Code hook installer (idempotent install / uninstall / status) | Future spec |
| `/servo:variant-race` | N-worktree parallel race with oracle scoring and winner selection | Future spec |

## Relationship to jig

Servo is a **sibling plugin**, not a dependency. They coexist in `${CLAUDE_PLUGIN_ROOT}` and reference each other only via filesystem hints — no cross-plugin registration mechanism, no hard dependency.

- Install servo without jig (oracle/headless only) or jig without servo (current default, supervised only).
- Servo reuses jig's `tdd.py detect` (via subprocess) when jig is installed; falls back to its own minimal test-runner detection otherwise.
- Jig's `slice-land prepare` emits soft pull-hints for servo artifacts when servo-style infrastructure is missing — that's the entirety of the coupling.

## The scaffolded `oracle.sh`

`oracle.sh` is a thin bash driver around a list of **components**. Each component is a function that scores its slice of project quality in `[0.0, 1.0]`; the driver computes a weighted average and gates it against `THRESHOLD`.

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

> Scaffold first, runtime later. Per-project, signal-aware artifacts — never generic stubs.

- Composite oracle score that reflects available signals (tests, lint, coverage, CI, seeded-issues)
- Hard guardrails on loops: iteration cap, cost ceiling, refuse on dirty tree, refuse without an oracle
- Hooks installed explicitly (never auto-installed); reversible install/uninstall
- Worktree races bounded (default 3 variants, hard cap 5)

See [docs/product-vision.md](docs/product-vision.md) for the vision and [docs/architecture.md](docs/architecture.md) for the mechanics. See [docs/specs/](docs/specs/) for spec state.

## License

[MIT](LICENSE)
