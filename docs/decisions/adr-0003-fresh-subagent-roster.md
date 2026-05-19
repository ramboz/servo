---
status: Accepted
date: 2026-05-19
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0003 — Why a fresh subagent roster, not reused from jig

## Context

Servo is a Claude Code plugin and a sibling to [jig](https://github.com/ramboz/jig). Jig already ships an `agents/` roster (`implementer.md`, `reviewer.md`, `architect.md`) tuned for supervised, spec-driven TDD with a human in the loop. Servo's loops are different in kind: every iteration costs real money, no human is watching, and the loop driver needs machine-parseable signals to decide whether to iterate again.

The question has been latent since spec 001 — servo's `agents/` directory has carried placeholder files for `runner`, `judge`, and `architect` each opening with a "why this exists, not jig's X" framing. Spec 003 (`/servo:agent-loop`) slice 003-05 is what forces the decision: that slice ships real `runner` and `judge` prompts beyond placeholder so the agent-loop can actually dispatch iterations and parse verdicts.

A third audit during this ADR's drafting (2026-05-19) clarified the roster scope. The `runner` and `judge` agents diverge from their jig analogs at the *output-schema* level — narrative for a human reader vs fenced verdict block for a loop driver — which forces a separate roster. The `architect` agent does not have that divergence: it produces ADRs for human readers in both projects, and any format wrapping is post-hoc. Reusing `jig:architect` therefore costs nothing real, and avoids an agent name collision under Claude Code's plugin-namespacing surface. Servo's `architect.md` placeholder is removed; architectural calls during servo's own development reuse `jig:architect` via the filesystem-only coupling pattern from [ADR-0001](adr-0001-reuse-jig-test-detector.md).

This ADR is the close-out artifact for slice 003-05. Authorship and acceptance happen in the same step: the decision was always going to be this for `runner` / `judge`, and the architect-reuse question was settled by the audit above.

## Decision

Servo ships **two** fresh agents — `agents/runner.md` and `agents/judge.md` — authored for the unattended-agent context. No shared imports with jig, no `--agent` references into jig's `implementer` / `reviewer`, no registration mechanism that exposes jig's agents under servo names. Architectural calls reuse `jig:architect` directly (Claude Code's plugin-prefix namespacing addresses both rosters; servo's loop driver and dev-time decision-makers invoke `claude --agent jig:architect ...` when an ADR-worthy decision lands). Coupling between servo and jig stays filesystem-only per [ADR-0001](adr-0001-reuse-jig-test-detector.md) — the two plugins live next door but never reach into each other's process or module space.

Concrete prompt-shape divergences this commits to:

- **`runner` vs `implementer`.** Jig's `implementer` may narrate intermediate reasoning and ask the user clarifying questions when a slice is ambiguous. Servo's `runner` is terse, never asks clarifying questions, and exits non-zero on any blocker so the loop driver can take over (escalate, retry with a different prompt, or terminate the run). Output ends with a fenced ```` ```verdict ``` ```` block carrying `schema_version: 1` (first line), `verdict: <CHANGES_MADE | NO_CHANGES | BLOCKED>`, optional `files_changed: <comma-separated paths>`, and `reasoning: <one-line summary>`.
- **`judge` vs `reviewer`.** Jig's `reviewer` produces narrative findings for a human reader. Servo's `judge` ends its output with a fenced ```` ```verdict ``` ```` block carrying `schema_version: 1` (first line), `verdict: <PASS | FAIL | INCONCLUSIVE>`, `score: <float in [0.0, 1.0]>`, and `reasoning: <one-line summary>`. The loop driver parses this block with a single regex shared with `runner`'s output shape.
- **`architect` is delegated, not duplicated.** Servo does not ship its own architect prompt. Jig's `architect` (Nygard-convention ADR generator) is invoked directly. Servo's actual ADR shape (frontmatter + Context + Decision + Consequences + Alternatives + Verification + References) is achieved by post-processing jig's output rather than authoring a separate prompt — the wrapping format is cheap; the reasoning work that an architect agent does is identical regardless of which template wraps it.

**Verdict-block schema versioning.** Following [ADR-0002](adr-0002-gate-caller-contract.md)'s `schema_version` mechanism explicitly: every verdict block emitted by `runner` or `judge` carries `schema_version: 1` as its first field. `loop.py` refuses to consume a block whose `schema_version` is missing or not equal to the version it knows — rc=2 with `reason=verdict_schema_mismatch` and a stderr breadcrumb naming both the expected version and the value observed (or "absent"). Any future field rename, type change, or semantic shift bumps the version; pure additive changes MAY keep `schema_version: 1` but the bias is "bump on any doubt" — silent mis-decoding of a verdict is worse than a noisy refusal. The same closed-version mechanism is what made `gate.py --json` safe to fan out across specs 003 / 004 / 005; the verdict block has the same fan-out shape (003 invokes runner+judge; 005 reuses judge for variant scoring) and earns the same posture.

## Consequences

### Positive

- Each plugin's subagents stay tuned to the actual audience. Jig keeps narrating to its supervising user. Servo keeps producing machine-parseable signals that the loop driver can branch on without an LLM round-trip to "interpret" the previous iteration.
- Independent install/uninstall is preserved. A user who has only servo never sees jig's prompts loaded, and vice versa.
- The fenced ```` ```verdict ``` ```` block is a closed, versioned schema. `schema_version: 1` is the first field; consumers refuse loudly on a mismatch rather than silently mis-decoding. Adding fields is additive (consumers ignore unknown keys; version stays at 1 unless semantics shift); renaming or retyping fields bumps the version. The loop driver and spec 005's race driver share one parser and one version gate.
- No registration mechanism to design or maintain. Two `agents/` directories in two plugin roots — nothing more.

### Negative

- Real duplication cost on `runner` and `judge`. Two sets of prompts to maintain. When a new Claude Code agent capability lands (a new tool, a new output format), both rosters need an update — but the scope is now narrowed to two agents instead of three.
- Servo's `runner` and `judge` cannot benefit from improvements made to jig's `implementer` and `reviewer` without a manual port. Acceptable: the prompts diverge enough that wholesale copying would regress servo's machine-parseability.
- Servo's ADR-writing dev-time workflow now depends on jig being installed when an `architect` invocation is needed. Mitigation is small: ADRs can also be written by hand (which is what produced ADR-0001 through ADR-0004 in practice), and the architect agent is an "invoked rarely" surface to begin with.

### Neutral

- The decision binds to a specific filesystem layout (separate `agents/` directories under separate plugin roots, with Claude Code's plugin-prefix namespacing for invocation). If Claude Code ever ships a cross-plugin agent registry with different resolution semantics, this ADR may want a re-check.
- If, in some future spec, servo's loop needs an architect-style call to produce a machine-parseable verdict rather than an ADR (e.g., a runtime architectural decision scored by the loop driver), servo would need to author its own architect prompt at that point. Today no such use case exists; the placeholder removal reflects current scope, not a forever-no posture.

## Alternatives considered

- **Reuse jig's `agents/` verbatim via filesystem reference, for the full roster.** Have `loop.py` invoke `claude --agent jig:reviewer ...` whenever jig is co-installed, and similarly for the implementer + architect roles. Rejected *for the runtime roles*: jig's `reviewer` produces narrative findings, not the fenced ```` ```verdict ``` ```` block the loop driver needs; parsing free-form narrative into `PASS` / `FAIL` / `INCONCLUSIVE` would itself require an LLM round-trip — exactly the unattended-cost problem this roster exists to avoid. The same constraint disqualifies `jig:implementer` for `runner`'s role. Accepted *for architect* (see Decision): an architect call produces an ADR for human readers in both projects, so jig's output is directly usable.
- **Parameterize jig's prompts with conditional `if SERVO_CONTEXT...` blocks.** Rejected: the prompts diverge in tone, in output schema, and in escalation policy (ask the user vs exit non-zero). A conditional version would be longer and harder to read than two clean files, and would force every jig prompt change to consider servo's audience as a side concern.
- **Vendor a one-time copy of jig's prompts into servo, then let them drift.** Rejected: superficially appealing (start from a known-good baseline) but actively misleading. The starting shape is wrong — jig's `reviewer` opens by asking the human for context, jig's `implementer` ends with "let me know if you want me to continue." Authoring from scratch with the unattended-context constraints in mind produces a better artifact than scrubbing jig's prompts of supervision cues.
- **Have jig accept a `--unattended` mode that changes its prompts' tone.** Rejected: forces jig to support two audiences (its own users and servo's loop drivers) and makes jig's roadmap depend on servo's. Better that each plugin stays tuned to its own audience and ships its own prompts.

## Verification

- **Slice 003-05 AC #5** verifies `agents/runner.md` produces a fenced ```` ```verdict ``` ```` block with `schema_version: 1` and `verdict: <CHANGES_MADE | NO_CHANGES | BLOCKED>` and that `loop.py` parses it. Tested via a mock-`claude` that emits the canonical block; the parsed fields surface in the per-iteration JSON line.
- **Slice 003-05 AC #6** verifies `agents/judge.md` produces the same block shape with `schema_version: 1`, `verdict: <PASS | FAIL | INCONCLUSIVE>`, and `score: <float in [0.0, 1.0]>`. The block parser is shared between runner and judge (single regex in `loop.py`); only the allowed `verdict:` values differ by agent.
- **Slice 003-05 AC #7** verifies loop dispatch — each iteration invokes `claude --agent <runner|judge> -p ...` with the alternation `runner → judge → runner → ...` confirmed by inspecting mock-`claude` arg captures.
- **Slice 003-05 AC #10** verifies the `verdict_schema_mismatch` refusal path: mock-`claude` emits a block missing `schema_version`, or with `schema_version: 2`, or with `schema_version: "1"` (string instead of int) — each case maps to rc=2 with the documented `reason` and the stderr breadcrumb naming the expected vs observed version.
- **Spec 005 (`/servo:variant-race`)** will reuse `judge` for per-variant scoring; the closed verdict-block schema is what makes that reuse safe.
- **Architect-via-jig** verifies by use: the next ADR-worthy servo decision invokes `jig:architect`, captures its Nygard-shaped output, and is post-processed into servo's ADR shape. If the post-processing step proves consistently painful (more than ~5 minutes per ADR), this ADR should be re-opened in favor of authoring a servo-shaped architect prompt.
- **Trigger for reconsideration:** if Claude Code ships a cross-plugin agent registry with different resolution semantics, or if servo's `runner` / `judge` prompts converge with jig's over time (e.g., jig adopts machine-parseable verdict blocks for its own reasons), or if a future spec needs an architect-style agent with machine-parseable output, this ADR should be re-opened.

## References

- [`docs/architecture.md`](../architecture.md) — "Subagents" section, including the agent-comparison table this ADR formalizes.
- [Spec 003 — agent-loop](../specs/003-agent-loop/spec.md), slice 003-05 ("Stuck-loop detection + subagent handoff") and Clarifications Q7 (verdict-block output schema).
- [`agents/runner.md`](../../agents/runner.md), [`agents/judge.md`](../../agents/judge.md) — the placeholder files that have telegraphed this decision since spec 001. (A third placeholder, `agents/architect.md`, was removed when this ADR was accepted; architectural calls reuse `jig:architect` per the Decision section.)
- [ADR-0001](adr-0001-reuse-jig-test-detector.md) — the filesystem-only-coupling framing this ADR extends to subagents.
- [jig](https://github.com/ramboz/jig) — the sibling plugin whose `agents/` roster this ADR declines to reuse.
