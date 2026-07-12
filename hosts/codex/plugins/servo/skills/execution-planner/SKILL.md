---

name: execution-planner
description: >-
  Assemble the [ADR-0016](../../docs/decisions/adr-0016-execution-plan-artifact.md) **execution plan** — the durable Compile→Run handoff artifact — from the Compile inputs already produced upstream (the suitability verdict, the oracle, the spec-oracle overlay) and write it to `<target>/.servo/plans/<spec-id>/plan.json`. This is the **last step of Servo Compile**: it decides nothing new, classifies nothing, and adds no gate — it only references what Compile already produced.
---

# /servo:execution-planner

The **last step of Servo Compile**: assemble the
[ADR-0016](../../docs/decisions/adr-0016-execution-plan-artifact.md) execution
plan and write it to `<target>/.servo/plans/<spec-id>/plan.json` — the durable
Compile→Run handoff, reciprocal to the per-run `state.json`
([ADR-0004](../../docs/decisions/adr-0004-session-state-file-format.md)): a
*plan*, not an *outcome*. It assembles no new evidence and adds no new gate —
it **references** (never copies) what Compile already produced: the
suitability verdict (015), the oracle (001), and the spec-oracle overlay (006).

The helper lives at
`${PLUGIN_ROOT}/skills/execution-planner/execution_plan.py`:

| Helper | Role | Spec |
|---|---|---|
| `execution_plan.py compile` | assemble the plan from the suitability verdict + oracle + overlay, write `plan.json` (`--json` for a scripted caller) | 016-01, 016-04 |
| `loop.py --plan <path>` | Run consumes the plan: budget/driver defaults, clamped, never loosened past a brake | 016-02 |
| `execution_plan.py compile` (recompile-preserve) | refuse to silently clobber a hand-edited `plan.json`'s `budget`/`driver` (`--force` to override) | 016-03 |

## When to use this skill

Use when a spec has already cleared suitability and is ready to hand off from
Compile to Run. Deciding whether the spec IS suitable is
`/servo:edd-suitability`; classifying its ACs / building the evidence overlay
is `/servo:spec-oracle`; running the loop against the plan this skill produces
is `/servo:agent-loop`; scoring a build is `/servo:quality-gate`. This skill
is the **assembly step in between**: it turns already-decided Compile inputs
into one durable, reviewable artifact.

## Q&A before compiling

Before running, confirm:

1. **Target path** — the repo whose Compile artifacts (`.servo/install.json`,
   `oracle.sh`, the suitability verdict, the optional spec-oracle overlay) are
   read, and where `plan.json` is written.
2. **Spec / slice path** — the Markdown spec whose suitability verdict and
   overlay (if any) the plan will reference.
3. **Output mode** — the existing human confirmation line (default), or a
   structured `--json` outcome envelope for a scripted Compile→Run caller.

## Workflow

```bash
# Compile — human confirmation by default.
python3 "${PLUGIN_ROOT}/skills/execution-planner/execution_plan.py" \
    compile <target> --spec <spec-path>
#   → servo: execution plan for <spec-id> compiled -> <target>/.servo/plans/<spec-id>/plan.json

# Machine-readable outcome envelope (for a scripted Compile→Run caller):
python3 ".../execution_plan.py" compile <target> --spec <spec-path> --json
#   → {"schema_version": 1, "spec_id": "...", "status": "compiled",
#       "plan_path": "...", "provenance": "compiled", "driver": "auto",
#       "budget": {...}}

# Recompiling over a hand-edited plan refuses by default (016-03 AC4);
# pass --force to discard the edit and recompile from scratch:
python3 ".../execution_plan.py" compile <target> --spec <spec-path> --force

# Run — the sibling that actually consumes the plan (not this skill):
python3 "${PLUGIN_ROOT}/skills/agent-loop/loop.py" <target> \
    --plan <target>/.servo/plans/<spec-id>/plan.json
```

## Where the plan sits

`compile` is the **last step of Servo Compile** — every upstream artifact
(suitability, oracle, spec-oracle overlay) must already exist; this skill
produces nothing new, only assembles a reference to what exists. The plan
then feeds `loop.py --plan <path>` at Run time (ADR-0016) and is the
reciprocal Compile-side artifact to the per-run `state.json` (ADR-0004): a
*plan* — durable, reviewable, produced once per compile — versus an
*outcome* — rewritten every iteration of a run.

## Refusal table — closed `{0, 2}` exit contract

`compile` never exits `1`. Exit `0` means the plan was emitted (or, on a
no-op recompile, unconditionally overwritten); exit `2` means an environment
error — a structured `reason` on stderr (`servo: <reason>: <message>`), and
**no plan is ever written on a refusal** (no torn artifact), in every output
mode:

| `reason` | Meaning | Next step |
|---|---|---|
| `spec_missing` | the `--spec` path does not exist | pass a real spec path |
| `suitability_missing` | no verdict at `.servo/suitability/<spec-id>.json` | run `/servo:edd-suitability analyze <target> --spec <spec>` first |
| `suitability_malformed` | the verdict file is not readable JSON | re-run `/servo:edd-suitability analyze` to regenerate it |
| `suitability_not_suitable` | the verdict is `needs_evidence` / `unsuitable` | acquire the missing evidence it lists, then re-analyze and re-compile |
| `manifest_missing` | no `.servo/install.json` at the target | run `/servo:scaffold-init` first |
| `manifest_malformed` | `.servo/install.json` is not valid JSON, or has no `components` list | re-run `/servo:scaffold-init`, or fix the manifest by hand |
| `oracle_missing` | no `oracle.sh` at the target | run `/servo:scaffold-init` first |
| `plan_edit_detected` | an existing `plan.json`'s `budget`/`driver` content no longer matches its recorded `budget_hash` (hand-edited since the last compile) | review the edit; pass `--force` to recompile and discard it, or keep the edit and skip recompiling |

## Human + `--json` output

Env-error refusals are **unchanged in every mode** — the structured stderr
`reason` and exit `2`, no JSON envelope, no torn artifact, whether or not
`--json` was passed (mirrors 015-04's "env errors unchanged under `--json`").
`--json` only shapes the **success** output: instead of the human line,
`compile` prints a single JSON outcome envelope to stdout —

```json
{
  "schema_version": 1,
  "spec_id": "...",
  "status": "compiled",
  "plan_path": ".../.servo/plans/<spec-id>/plan.json",
  "provenance": "compiled",
  "driver": "auto",
  "budget": {"max_iterations": 5, "cost_ceiling_usd": 2.0,
             "context_fill_threshold": 0.75, "plateau_window": 3}
}
```

— enough for a scripted Compile→Run caller to locate and gate on the plan
without re-reading `plan.json` from disk.

## Install posture — host / Compile-phase tool, not vendored

This is a **host / Compile-phase tool**, like `/servo:edd-suitability` and
`/servo:spec-oracle` — it runs from the full servo plugin against a target,
and is **not** vendored into a scaffolded target's unattended runtime. The
only runtime consumer of the plan it produces, `loop.py --plan`, is already
vendored as `agent-loop`; `execution_plan.py` itself never runs unattended.
Accordingly it is **deliberately absent** from
`.claude-plugin/install-contract.json`'s `required.skills` — mirroring the
015-04 follow-up's posture for `edd-suitability` / `spec-oracle` — while it
still ships as an ordinary discoverable skill via the release zip's
`include: skills/`.
