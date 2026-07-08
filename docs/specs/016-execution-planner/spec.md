---
status: DONE
dependencies: [001, 003, 006]
last_verified:
---

# Spec 016 — execution-planner

> The last step of Servo Compile: turn the compiled evaluation (oracle +
> spec-oracle overlay + suitability verdict) into a durable, reviewable
> **execution plan** that Servo Run consumes — the Compile→Run handoff artifact
> at `<target>/.servo/plans/<spec-id>/plan.json`, per
> [ADR-0016](../../decisions/adr-0016-execution-plan-artifact.md). Skill:
> `/servo:execution-planner` (016-04).

> **Status: DONE — 016-01/02/03/04 DONE (2026-06-30 / 2026-07-02 / 2026-07-04 /
> 2026-07-08); spec 016's active work is complete. 016-05 stays DEFERRED**
> (prompt-render, pending a real Compile→Run that wants the plan to supply the
> task prompt rather than a hand-passed `--prompt`).
> Activated once [ADR-0016](../../decisions/adr-0016-execution-plan-artifact.md)
> was Accepted (2026-06-30). The plan's **sole consumer is `loop.py`** — Compile →
> Run for a real spec — *not* the heartbeat, whose findings are spec-less
> ([ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md)).
> **[016-01](slice-01-plan-emit.md) (plan-emit)** — `execution_plan.py compile`
> emits `.servo/plans/<spec-id>/plan.json`. Its `suitable`-only precondition
> landed the Compile-gate *mechanism* that
> [015-03](../015-edd-suitability/slice-03-pipeline-gate.md) then built its full
> ACs on. **[016-02](slice-02-run-consume.md) (run-consume)** — `loop.py` gains
> a **`--plan <path>`** flag (a generic path — `loop.py` never derives a
> `spec-id`) that reads `budget` + `driver` as run defaults; no `--plan` ⇒
> today's behavior unchanged. Consuming `prompt_ref` is split to
> [016-05](slice-05-prompt-render.md) (prompt-render, DEFERRED) — a usable seed
> prompt needs a *spec→prompt compiler*, a distinct capability; `--prompt`
> stays required. **[016-03](slice-03-clamp-and-review.md) (clamp-and-review)**
> — a plan-sourced disable sentinel (`0`) on a budget knob is clamped back to a
> live default rather than honored as disabled (narrowed from a numeric
> magnitude ceiling that was never actually decided anywhere — see the
> [ADR-0016 amendment](../../decisions/adr-0016-execution-plan-artifact.md#amendments));
> `provenance: human_edited` plans are now consumable; `execution_plan.py
> compile` refuses to silently clobber an edited plan (content-hash detected,
> `--force` overrides). **[016-04](slice-04-skill-surface.md) (skill-surface)** —
> ships `/servo:execution-planner` (house-style SKILL.md + `compile --json`
> outcome envelope); a **plugin-discovered** skill, deliberately **not** vendored
> into `install-contract.json` `required.skills` (a Compile-phase host tool whose
> only runtime consumer, `loop.py --plan`, is already `agent-loop` — mirrors the
> 015-04 posture). Realizes the provisional `/servo:execution-plan` as
> `/servo:execution-planner` (matches the skill dir). Closes spec 016's active work.

## Why this spec

[ADR-0014](../../decisions/adr-0014-evaluation-compiler.md) names the execution
plan as a Servo Compile output, but it has no home. The loop is invoked ad hoc —
a human or the heartbeat dispatcher passes `--prompt` / `--cost-ceiling` /
`--max-iterations` / `--driver` on the command line — and the per-run
`state.json` ([ADR-0004](../../decisions/adr-0004-session-state-file-format.md))
records what *happened*, not what was *planned*. So the Compile→Run boundary is a
flag bag, "Execution Planning" produces nothing, and downstream consumers
(heartbeat reuse, 017 adaptive planning) have nothing to read or rewrite.

[ADR-0016](../../decisions/adr-0016-execution-plan-artifact.md) settles the
*contract*: a named, versioned, project-owned `plan.json` that references (not
copies) the other Compile artifacts, is reviewable/editable before Run, and
**cannot loosen a hard guardrail past its safe ceiling**. This spec builds the
planner that emits it and teaches Run to consume it.

## Goals (provisional)

1. **Compile an execution plan.** Assemble `plan.json` from the suitability
   verdict (015), the oracle (001), and the spec-oracle overlay (006): oracle
   reference + components + threshold, evaluation-model reference, budget
   (iterations / cost ceiling / context-fill / plateau window), driver, and
   prompt reference. Per the ADR-0016 schema.
2. **Reference, don't copy.** Point at the oracle and spec-oracle by identity
   (path / id), the way `state.json` references the Claude session — one source
   of truth per artifact.
3. **Stay reviewable and editable.** A human can inspect and adjust the plan
   before Run consumes it (`provenance: human_edited`), mirroring the spec-oracle
   freeze/approval posture (006-04).
4. **Teach Run to consume it.** `loop.py` gains a `--plan <path>` flag (a generic
   path — `loop.py` never derives a `spec-id`; the caller points it at the compiled
   `plan.json`) and reads `budget` / `driver` from it as run defaults; with no
   `--plan`, behavior is byte-for-byte today's (CLI flags + defaults) — the plan is
   opt-in glue, not a precondition. Consuming `prompt_ref` as the seed prompt is
   deferred to [016-05](slice-05-prompt-render.md): it needs the producer to
   *compile* an actionable prompt from the spec (the raw `spec.md` is incoherent fed
   verbatim to `claude -p`), a distinct capability. The heartbeat dispatcher is
   **not** a plan consumer: its findings are spec-less, so a `spec-id`-keyed plan has
   nothing to bind (ADR-0018).
5. **Clamp, never disable.** A plan budget requesting the documented "disable
   this brake" sentinel is clamped back to a live default, not honored as
   disabled ([ADR-0016 amendment, 2026-07-04](../../decisions/adr-0016-execution-plan-artifact.md#amendments):
   narrowed from a numeric magnitude ceiling once 016-03 found no such policy
   ceiling exists, and inventing one would silently defeat the review goal
   below). A plan value that *raises* a knob is honored exactly like an
   explicit CLI flag; the plan configures *how* Run optimizes, the brakes
   (ADR-0008/003) and the oracle authority (ADR-0011) are untouched.
6. **Be reproducible.** A run is reconstructable from its plan; the plan records
   `compiled_at` and `provenance`.

## Non-goals

- **Not running the loop.** That stays 003; this spec stops at an emitted plan +
  Run's ability to read it.
- **Not adaptive re-planning.** Rewriting the plan mid-flight from convergence
  signals is 017 (evaluation intelligence); 016 produces the *initial* plan and
  the read/clamp contract it rewrites against.
- **Not a new authority.** The plan can never disable a brake or override the
  oracle.
- **Not replacing `state.json`.** Plan (Compile output, stable) and state (Run
  outcome, rewritten per iteration) stay distinct artifacts (ADR-0016).

## Core model

The Compile→Run handoff the plan makes durable:

```
[015 suitability: suitable]
        │
[001 oracle] ─┐
[006 overlay]─┼─→ [016: compile execution plan] ──→ .servo/plans/<spec-id>/plan.json
[budget/driver/prompt]                                        │  (reviewable, editable)
                                                              ▼
                                          [Servo Run: loop.py --plan <path>]
                                          reads defaults, clamps disabled brakes,
                                          oracle stays authority → state.json (outcome)
```

`plan.json` (Compile, stable) and `state.json` (Run, per-iteration outcome) are
reciprocal — plan vs result.

## SPIDR split

**Path-first** (the artifact and its Compile-boundary gate), then a **Path** slice
(Run consuming budget/driver), then **Rules** (clamping/review), then **Interface**
(the skill surface), plus a later **Path** slice (compiling the seed prompt). No
spike: ADR-0016 settled the contract. Only 016-01 was consumer-independent and
pinnable from the schema up front; the rest waited for a grounding consumer to pin
ACs (the 015 lesson — a parked slice gets a resolution trigger, not guessed ACs).
016-05 was split out of 016-02 by the latter's frame-critique once "consume the
prompt" proved to be a distinct *compile-a-prompt* capability, not a knob-read.

| Slice | Title | Axis | Status | Goal |
|---|---|---|---|---|
| [016-01](slice-01-plan-emit.md) | plan-emit | Path | **DONE** | Compile `plan.json` from suitability verdict + oracle + overlay + budget/driver/prompt; ADR-0016 schema; **references not copies** (`suitability_ref`, not an inlined verdict); `schema_version`; git-ignored `.servo/plans/`; emits **only on a `suitable` verdict** (the 015-03 Compile gate). |
| [016-02](slice-02-run-consume.md) | run-consume | Path | **DONE** | `loop.py --plan <path>` (generic path, no `spec-id` derivation) reads `budget` + `driver` as run defaults; precedence flag > plan > default; driver-aware budget (goal driver drops loop-only brakes); no `--plan` ⇒ today's behavior unchanged; `human_edited` plans refused pending 016-03 (superseded). `--prompt` stays required (`prompt_ref` consumption = 016-05). Consumer is `loop.py` only, not the heartbeat (ADR-0018). |
| [016-03](slice-03-clamp-and-review.md) | clamp-and-review | Rules | **DONE** | Clamp a plan's disable-sentinel budget values back to a live default (not a numeric magnitude ceiling — [ADR-0016 amended](../../decisions/adr-0016-execution-plan-artifact.md#amendments) 2026-07-04, no such policy ceiling was ever decided anywhere in `loop.py`); `human_edited` provenance now consumable (supersedes 016-02's refusal); plan-value validation fails closed before clamping; `execution_plan.py compile` refuses to clobber an edited plan via content hash (`budget_hash`, not a self-reported label), `--force` to override. |
| [016-04](slice-04-skill-surface.md) | skill-surface | Interface | **DONE** | `/servo:execution-planner` SKILL.md (house-style) + `execution_plan.py compile --json` outcome envelope. **Plugin-discovered, NOT vendored** into `required.skills` — the original goal's "install-contract entry" was reframed by the frame-critique: it's a Compile-phase host tool (only runtime consumer `loop.py --plan` is already `agent-loop`), mirroring 015-04. Heartbeat plan-reuse dropped (ADR-0018). |
| [016-05](slice-05-prompt-render.md) | prompt-render | Path | DEFERRED | Producer *compiles* an actionable seed prompt from the spec (not the raw `spec.md` doc) → target-relative artifact; `loop.py --plan` seeds from `prompt_ref` when `--prompt` omitted. Split from 016-02 by its frame-critique (rendering is a distinct capability). Trigger: 016-02 DONE. |

## Open questions

- **One plan per spec, or per run?** `plans/<spec-id>/plan.json` assumes a stable
  per-spec plan; a per-run variant (or a plan→many-runs fan-out for variant-race,
  005) may be needed.
- **Plan/overlay/state naming.** Three "plan"-ish things now (execution **plan**,
  spec-oracle **plan.md**, run **state**); keep the docs disambiguation tight.
- ~~**Where the suitability verdict lives** — inline in `plan.json` or a
  standalone artifact 015 owns.~~ **Resolved (ADR-0016, refined 2026-06-30):** the
  plan **references** 015's standalone `.servo/suitability/<spec-id>.json` via
  `suitability_ref` (reference, not copy), so the verdict can't go stale relative
  to a re-analysis.
- **Variant-race interaction (005).** Does each variant get its own plan, or one
  plan with N executions? Decide when 005 activates.

## References

- [ADR-0016 — the execution plan is the Compile→Run handoff artifact](../../decisions/adr-0016-execution-plan-artifact.md)
  — the contract this spec implements.
- [ADR-0014 — evaluation compiler](../../decisions/adr-0014-evaluation-compiler.md)
  — names the execution plan as a Compile output.
- [ADR-0004 — session-state file format](../../decisions/adr-0004-session-state-file-format.md)
  — the reciprocal Run-outcome artifact.
- [Spec 015 — edd-suitability](../015-edd-suitability/spec.md) (upstream verdict),
  [Spec 003 — agent-loop](../003-agent-loop/spec.md) (the Run consumer),
  [Spec 017 — evaluation-intelligence](../017-evaluation-intelligence/spec.md)
  (the adaptive-planning rewriter).
