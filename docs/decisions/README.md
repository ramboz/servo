# Decisions

> Architectural Decision Records. Nygard convention: immutable after acceptance.
> New decisions supersede old ones — never edit an accepted ADR.
> Filenames follow `adr-NNNN-<kebab-slug>.md`; titles use the form
> `# ADR-NNNN: <Title>`.

## Index

- [ADR-0001: Reuse jig's `tdd.py detect` for test-framework detection when jig is co-installed](adr-0001-reuse-jig-test-detector.md) — Servo prefers jig's detector via subprocess when `${CLAUDE_PLUGIN_ROOT}/jig/skills/tdd-loop/tdd.py` exists, falls back to a built-in matcher otherwise. Establishes the filesystem-only coupling pattern. (2026-05-15, Accepted)
- [ADR-0002: Quality-gate caller contract — closed exit codes and versioned JSON schema](adr-0002-gate-caller-contract.md) — `gate.py` exits only `0/1/2` (unexpected oracle exits remap to `2`); `--json` payloads carry `schema_version: 1` from day one. The contract specs 003 / 004 / 005 consume. (2026-05-18, Accepted)
- [ADR-0003: Why a fresh subagent roster, not reused from jig](adr-0003-fresh-subagent-roster.md) — Servo ships two fresh agents (`runner`, `judge`) because their machine-parseable verdict-block output diverges from jig's narrative `implementer` / `reviewer`. Architect calls delegate to `jig:architect` directly — no servo-side architect prompt. (2026-05-19, Accepted)
- [ADR-0004: Session-state file format on disk](adr-0004-session-state-file-format.md) — Per-run loop scoreboard at `<target>/.servo/runs/<run-id>/state.json`, referencing Claude Code sessions by `session_id` only. Atomic-write contract, `state_schema_version`, run-id collision policy. Filesystem-only coupling with Claude Code. (2026-05-19, Accepted)
- [ADR-0005: Eval as a frozen oracle component](adr-0005-eval-oracle-component.md) — A non-deterministic eval enters the composite only as a *frozen* `score_<name>`: its definition (rubric + dataset + judge model + `n` + `δ`) is hashed and approved, it reports a confidence lower bound rather than a raw judge score, and `loop.py` gains a plateau noise floor. The reciprocal servo-side ADR to jig's ADR-0022. (2026-06-09, Proposed)
- [ADR-0006: Meta-judge Stop-hook output contract & fail-open posture](adr-0006-meta-judge-output-contract.md) — Spec 004's `Stop` hook blocks with a structured composite/threshold hint on below-threshold (`{"decision":"block"}`, not `additionalContext`), fails **open** on any env-error (a `systemMessage` warning, never a block, so it can't trap a session), and nudges at most once per stop sequence (respects/biases-on `stop_hook_active`). The interactive inverse of agent-loop's fail-closed brakes. (2026-06-10, Accepted)

## Pending

ADR candidates (numbers are *hints* of the next likely allocation order,
not reservations — the next accepted ADR claims the next free number
regardless of which candidate fires first). `0005` is reserved (Proposed)
by the eval-oracle-component ADR and `0006` is now Accepted (meta-judge
output contract), so the next free number is `0007`:

- **A future ADR — Why `oracle.sh` stays project-owned plain bash.** Crystallizes if anyone ever proposes a Python or Node oracle alternative. Listed in `docs/architecture.md` under "Pending (ADR candidates)".

## Format

Each ADR carries a frontmatter block (`status`, `date`, `deciders`,
`supersedes`, `superseded-by`) plus body sections: Context, Decision,
Consequences (positive / negative / neutral), Alternatives considered,
Verification, References.

## When to write an ADR

- Hard-to-reverse decisions (file formats, contracts, public-API shapes)
- Decisions that affect multiple modules or downstream callers
- When a contract changes in a breaking way
- When the architect agent (`jig:architect` per ADR-0003) produces a proposal that is accepted
