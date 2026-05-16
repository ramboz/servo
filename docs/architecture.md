---
status: DRAFT
last_verified:
---

# Architecture: servo

> Status: Draft — evolves as specs land.

## Shape

Servo is a Claude Code plugin in the same shape as [jig](https://github.com/ramboz/jig):

```
servo/
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       └── <helper>.py
├── agents/                 (deferred — runtime skills will populate)
├── hooks/                  (deferred — Spec 003 will populate)
├── templates/              (per-project artifacts copied into target)
├── scripts/                (verification, install helpers)
├── docs/
│   ├── product-vision.md
│   ├── architecture.md
│   ├── decisions/          (ADRs — deferred until first hard-to-reverse choice)
│   └── specs/
│       └── <NNN>-<name>/spec.md
├── README.md
└── LICENSE
```

## Skill split

Servo is **scaffolder-first, runtime second**. The four runtime skills all presuppose artifacts the scaffolder dropped into the target.

| Skill | Role | Spec |
|---|---|---|
| `/servo:scaffold-init` | Probe → Q&A → tailored install of `oracle.sh` (+ optional agent-loop/hook/race stubs) | 001 |
| `/servo:quality-gate` | Runtime invocation of scaffolded `oracle.sh`; normalized exit codes | future |
| `/servo:agent-loop` | Headless iteration driver | future |
| `/servo:oracle-hook` | Claude Code hook installer | future |
| `/servo:variant-race` | N-worktree parallel race | future |

## Project vs servo-core split

This is the load-bearing distinction. Servo ships **templates and orchestration**; the project owns **content and policy**.

| Project owns | Servo owns |
|---|---|
| `oracle.sh` content, weights, threshold | Template + signal-detection logic |
| Custom signal functions | `# SEED:` annotation convention |
| Domain-specific lint configs | Normalized exit codes |
| Prompt templates for loops | Loop driver, guardrail defaults |
| Cap + ceiling overrides | Defaults (max-iterations=5, cost-ceiling=$2) |
| Hook event choice, retry phrasing | Hook script template, settings.json mutation + backup |
| Variation strategy, variant count | Worktree management, subagent spawning, scoring |

## Tier model

Mirrors jig's tier-based scaffolding:

- **Tier 0** — `oracle.sh` only. Always installs. Composite score of whatever signals are detected.
- **Tier 1** — Tier 0 + agent-loop driver stub. Offered when the project has signals dense enough to make iteration meaningful (tests + lint + types, or similar).
- **Tier 2** — Tier 1 + hook installer + race driver. **Offered explicitly only.** These are higher-risk surfaces (mutates `settings.json`, races real worktrees) and should never auto-install.

## Signal detection

Probe the target for:

- Test framework (pytest / vitest / jest / cargo test / go test / unknown) — reuse jig's `tdd.py detect` via subprocess if jig is present, otherwise fall back to a built-in detector
- Lint configs (`.eslintrc*`, `pyproject.toml` ruff/flake8/mypy sections, etc.)
- CI (`.github/workflows/`, `.gitlab-ci.yml`, …)
- Language (file-extension census)
- Coverage tool presence
- `oracle.sh` already at target root → refuse install without `--force`
- `.servo/install.json` (servo's own manifest, like jig's `scaffold.json`)

Detection results drive **which components are included in the composite** in the generated `oracle.sh`. If lint isn't configured, the generated script doesn't reference lint.

## Install manifest

After install, the target gets `.servo/install.json` with:

```json
{
  "servo_version": "0.1.0",
  "timestamp": "<ISO8601>",
  "installed_tier": "tier-0" | "tier-1" | "tier-2",
  "offered_tiers": [...],
  "signals": { "tests": true, "lint": false, "ci": false, "language": "python" },
  "components": ["pytest", "coverage"]
}
```

This is the analog of jig's `scaffold.json` and is what later runtime skills consult to know what was installed.

## Subagents

Servo ships its own `agents/` roster (`runner.md`, `judge.md`, `architect.md`) rather than reusing jig's `implementer.md` / `reviewer.md` / `architect.md`. Reason: jig's subagent prompts assume **supervised** TDD — they narrate, ask clarifying questions, defer ambiguous calls back to the user. Servo's loops are **unattended** — every iteration costs money, no human is watching, and the loop driver needs machine-parseable signals to decide whether to iterate again. The prompts diverge enough that copy-and-rewrite is cleaner than parameterize-and-share. Documented as a future ADR ("Why a fresh subagent roster").

| Servo agent | Jig analog | Why different |
|---|---|---|
| `runner` | `implementer` | Terse, no soliloquy, exit-non-zero on blocker |
| `judge` | `reviewer` | Machine-parseable verdict (PASS/FAIL/INCONCLUSIVE + score) |
| `architect` | `architect` | Same shape, reworded for unattended-context tradeoffs |

Current state: all three are **placeholders**. Full prompts are authored alongside the specs that need them (spec 003 needs `runner` + `judge`; spec 005 reuses `judge`).

## Runtime artifacts (when later specs land)

Future runtime skills (specs 003–005) will produce these at the *target* project (not in servo's plugin repo):

- `<target>/.servo/runs/<run-id>/` — per-iteration logs from `/servo:agent-loop` (stdout, stderr, oracle score, checkpoint). One subdirectory per loop run.
- `<target>/.servo/hooks/meta-judge.sh` — copied by `/servo:oracle-hook` install; user may customize, uninstall leaves on disk.
- `<target>/.servo/races/<race-id>/` — per-variant scores and metadata from `/servo:variant-race`.

These paths are reserved now (in `.gitignore`) so later specs don't have to renegotiate them.

## Decisions pending (ADR candidates)

Three decisions are likely to crystallize into ADRs during spec 001:

1. **ADR-0001 — Why filesystem-only coupling with jig.** Servo reads jig's filesystem artifacts and invokes jig helpers via subprocess; neither plugin imports the other. Driving factors: independent install/uninstall, version skew tolerance, no shared Python dependency surface.
2. **ADR-0002 — Why a fresh subagent roster, not reused from jig.** See "Subagents" section above. The risk is duplicated prompt maintenance; the win is prompts that match the operating context.
3. **ADR-0003 — Why `oracle.sh` stays project-owned plain bash.** Servo scaffolds it; the project owns it forever after. Driving factors: zero servo runtime dependency for the most-invoked artifact, dev can grep + edit without learning a DSL, version-control friendly.

These are deferred until the spec slice that forces them.

## Open questions (not yet ADR-worthy)

- **Composite weighting heuristic** when multiple signals are present (equal weights? signal-strength-weighted? user-tuned via Q&A?)
- **`.servo/install.json` checked in vs ignored** — currently `.gitignore`d; revisit when team-shared servo installs become a use case.
- **Scaffold-init interaction with jig-scaffolded projects** — likely fine (no path collisions) but worth an explicit slice-level test in 001-03 or 001-05.
- **Agent-loop driver: shell vs Python.** Leaning shell for Tier 1 (zero deps), Python only if Tier 2 needs the richer state (checkpoint/resume).

## Why no crew skill

Multi-agent crews (hand-off / voting / leader-follower coordination) don't yet generalize enough to scaffold. Servo ships a one-page [post-mortem template](../templates/crew-postmortem.md) for capturing ad-hoc crew experiments, but no `/servo:crew` skill. If post-mortems start showing a consistent pattern, that's a future spec; today it would be premature.

## Internal scoping reference

> Internal-only — kept here to anchor scope decisions during spec
> authoring. Not a public framing of servo; should not leak into
> user-facing docs (README, product-vision, templates).

Each runtime skill traces back to a specific pattern in private learning notes:

| Spec | Skill | Source pattern |
|---|---|---|
| 001 | `/servo:scaffold-init` | (spans the four runtime patterns' setup) |
| 002 | `/servo:quality-gate` | oracle scoring |
| 003 | `/servo:agent-loop` | headless iteration ("Ralph") |
| 004 | `/servo:oracle-hook` | meta-judge hook |
| 005 | `/servo:variant-race` | worktree race |
| n/a | (teams pattern covered) | by jig's `agents/` |
| n/a | (crews pattern skipped) | post-mortem template only |

Decisions land in [docs/decisions/](decisions/) as ADRs once they're hard to reverse.
