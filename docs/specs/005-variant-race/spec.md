---
status: DRAFT
dependencies: [001, 002, 003]
last_verified:
---

# Spec 005 — variant-race

> Run the same work N times in parallel git worktrees, score each result with
> the project's oracle (`gate.py`, spec 002), and promote the highest-scoring
> variant back to the target — cleaning up the losers by default. The race
> driver **wraps** the loop driver (spec 003): each worktree runs its own
> `loop.py`, and the loop's cost-ceiling + checkpoint primitives become
> race-shared state. The unattended cousin of jig's parallel-spec-number
> reservation, applied to ephemeral worktrees. `/servo:variant-race` is a
> **Tier-2** surface — offered explicitly only, never auto-installed, because
> it races real worktrees and multiplies spend.

> **Status: DRAFT — scope capture, parked.** This is best-of-N sampling
> against the oracle, and it is an **optimization, not a prerequisite** for
> EDD (see *Is this core to EDD?* below). Captured now while the loop/gate/
> oracle context is fresh; the slice sketch is pre-SPIDR (goals only, no ACs).
> **Activation trigger:** a real servo target shows single-shot convergence is
> the bottleneck — loops that plateau-halt (003-05) or exhaust the iteration
> cap without passing the oracle, often enough that N× compute for a best
> result is worth paying. Until a real project produces that signal, this is
> captured intent, not queued work. Re-open by SPIDR-splitting the sketch and
> transitioning to `READY_FOR_REVIEW`.

## Is this core to EDD?

No. EDD's closed loop is *define an eval → let the agent iterate against it →
gate acceptance on it*. Specs **001–007 already deliver that entire loop**,
runnable unattended:

- 001 scaffolds `oracle.sh`; 002 makes it uniformly callable with normalized
  exit codes; 003 iterates `claude -p` against it under hard guardrails; 004
  grades each `Stop` turn; 006 compiles spec ACs into deterministic evidence;
  007 installs all of it across three surfaces.

variant-race does not *enable* any of that. It **scales** it: instead of one
sequential loop, run N independent loops and keep the highest-scoring result.
That is a well-established, high-ROI inference-time technique — but it is
strictly **additive**. Every guardrail, scoring path, and install surface EDD
needs already ships without it.

The honest framing: **a force-multiplier, not a foundation.** It pays off only
when single-shot success rate is the limiting factor, and it costs up to N×
concurrent spend against a project whose default ceiling is $2 (003-02). The
one thread that connects it to the core loop: 003-05 ships stuck-loop
*detection* (oracle-score plateau) but can only *halt*; a fan-out race is a
natural *escape* from that plateau. Even that is an enhancement to plateau
handling, not a prerequisite — and it is one of the two possible shapes this
spec could take (see Open questions).

This section is why the spec is parked rather than queued. Nothing downstream
depends on it; it waits for demand.

## Why this spec (when it pays off)

When a project's oracle is a *good discriminator* (which 006 spec-oracle now
makes achievable) but the single-shot loop converges unreliably, best-of-N
against that oracle is the highest-leverage move available — far more reliable
than tuning prompts by hand. The verifier is already trustworthy; the cheapest
way to raise output quality is to sample more and let the verifier pick.

Servo is uniquely positioned to ship this safely because it already owns the
two hard parts:

- a **trustworthy score** to race against (`gate.py --json`, with an optional
  spec-006 overlay), so winner selection isn't vibes; and
- a **bounded loop** to run per variant (`loop.py`, with cost ceiling and
  checkpoint/resume), so a runaway variant can't burn the whole race budget.

Without servo, a dev wiring this by hand re-implements worktree coordination,
per-variant scoring, winner promotion, and cleanup on every project — the same
scars `docs/product-vision.md` names. This spec encodes the orchestration so
the project supplies only **variation strategy and variant count** (the
project-vs-core split: servo owns worktree management, subagent spawning, and
scoring; the project owns *what makes the variants differ* and *how many*).

## Core model

```
race.py <target> --variants N
  → spawn N git worktrees of <target>                 (servo: worktree mgmt)
  → in each worktree: loop.py <wt>                     (spec 003, wrapped)
       └ each loop scored by gate.py --json            (spec 002)
  → collect per-variant final scores                  → .servo/races/<race-id>/
  → select winner by composite score (deterministic tie-break)
  → promote winner back to <target>                   (merge/apply)
  → clean up loser worktrees by default               (reversibility)
```

- **Reserved state path** (already in `.gitignore` per architecture.md):
  `<target>/.servo/races/<race-id>/` holds per-variant scores and metadata.
- **Race wraps loop, loop doesn't know about race** (the boundary 003 set in
  its out-of-scope list): the loop driver is variant-agnostic; the race driver
  composes N of them. Cost-ceiling + checkpoint/resume become race-shared
  concerns the race driver coordinates, not loop-internal ones.
- **Stateless gate, stateful caller** (architecture.md): `gate.py` writes
  nothing; per-variant persistence is 005's responsibility, exactly as
  per-iteration persistence is 003's.

## Non-goals (provisional)

- **Not a new scorer.** Variants are scored by the *existing* `gate.py`
  composite (optionally with a spec-006 overlay). The race introduces no
  special-case scoring — same no-special-casing discipline 006-03 held.
- **Not a variation-strategy engine.** Servo supplies the racing *mechanism*;
  the project owns *what makes variants differ* (prompt/temperature/agent/seed)
  and *how many*. Servo ships a sane default, not a strategy DSL.
- **No cross-machine / distributed races.** Per ADR-0001 filesystem-only
  coupling: worktrees are local; no remote runners, no cloud fan-out.
- **No auto-install.** Tier-2, explicit opt-in only (architecture.md tier
  model). The race driver never lands without the user asking for it.
- **No merge-conflict resolution AI.** Winner promotion is a defined,
  inspectable git operation; if the winner can't apply cleanly, the race
  surfaces it and stops rather than letting an agent "fix" the merge.

## Provisional slice sketch (pre-SPIDR — not ready for implementation)

> Goals only, no ACs. Mirrors the servo 001/002/003 cadence (spike-shaped first
> slice → primitives one at a time → skill + dogfood last). A real consumer is
> needed to ground acceptance criteria; until then this just bounds scope.

| Slice | Title | Goal |
|---|---|---|
| 005-01 | spawn-and-race | Spike-shaped: `race.py <target> --variants N` creates N git worktrees and runs `loop.py` (003) in each, capturing each variant's final oracle score. Validates the race-wraps-loop assumption end-to-end. |
| 005-02 | variant-lease | Coordination so concurrent variants don't collide: per-race-id directory isolation, per-variant subdirs under `.servo/races/<race-id>/`, lease records. The ephemeral-worktree cousin of jig's spec-number reservation. |
| 005-03 | winner-selection | Pick the winner by composite score via `gate.py --json`; deterministic tie-break; recorded selection rationale; loser scores retained for inspection (not silently discarded). |
| 005-04 | promotion-and-cleanup | Promote the winning worktree back to the target (defined git operation); clean up loser worktrees by default (reversibility, per product-vision); `--keep-worktrees` escape hatch; refuse-and-surface on dirty promotion rather than force. |
| 005-05 | skill-and-dogfood | `/servo:variant-race` SKILL.md — Tier-2 explicit-opt-in framing, refusal table, the N× cost-multiplier warning up front — plus an end-to-end dogfood driving the real spawn → loop → score → promote → clean chain. |

## Open questions

- **Two shapes — race-from-start vs plateau-escape.** Is this best-of-N from
  the first iteration (the "A/B testing" framing), or a fan-out triggered only
  when a sequential `loop.py` hits a 003-05 plateau (a surgical escape hatch)?
  These have different cost profiles and different UX. Possibly both as modes,
  but the default matters and should be decided against a real case.
- **Parallel vs sequential execution.** True parallel = N concurrent `claude -p`
  subprocesses (fast, but N× *peak* spend and harder coordination) vs sequential
  best-of-N (slower, smoother spend). The architecture says "parallel"; the cost
  model may argue for a bounded concurrency knob.
- **Cost-ceiling semantics across variants.** Is the $2 default *per variant*
  or *per race*? `--variants 5` silently becoming a $10 ceiling is a footgun;
  the race driver likely needs its own race-level ceiling distinct from the
  loop's per-run one.
- **Variation strategy default.** With no project-supplied strategy, what makes
  variant 2 differ from variant 1 — sampling/temperature variance on an
  identical prompt, distinct seeds, or distinct agents? "Project owns strategy"
  still needs a defensible default for the bare case.
- **Winner promotion mechanism.** Merge the winner's branch, cherry-pick, or
  apply-as-patch? Behaviour when the winner conflicts with the target's current
  state (refuse-and-surface is the leaning, per non-goals).
- **Interaction with the oracle-hook (004).** If a variant's loop has the
  meta-judge Stop hook installed, scoring happens at two layers. Is that
  redundant, complementary, or a conflict to forbid during a race?

## References

- [docs/architecture.md](../../architecture.md) — Tier-2 classification, the
  reserved `.servo/races/<race-id>/` path, the project-vs-core split row
  (project owns variation strategy + count; servo owns worktree mgmt, spawning,
  scoring), and the stateless-gate / stateful-caller contract.
- [docs/product-vision.md](../../product-vision.md) — "Racing worktree variants
  in parallel and picking the winner by score" as one of the four
  unattended-agent patterns; "Race worktrees clean up by default" (reversibility).
- [Spec 003 — agent-loop](../003-agent-loop/spec.md) — the loop driver this
  wraps; its out-of-scope note ("Per-variant scoring across worktrees → 005")
  set this boundary.
- [Spec 002 — quality-gate](../002-quality-gate/spec.md) — the scorer every
  variant is judged by; no special-casing for the race.
- [ROADMAP.md](../ROADMAP.md) — sequencing rationale (003 before 005 because the
  race reuses loop primitives).
