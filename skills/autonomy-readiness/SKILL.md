---
name: servo:autonomy-readiness
description: |
  Decide whether a goal's SCOPE and INITIAL PROMPT are precise and bounded
  enough to hand to an unattended, long-horizon agent loop — *before* any budget
  is burned. Emits the ADR-0029 **readiness verdict**: a closed three-state gate
  (`ready` / `needs_tightening` / `unsafe_for_autonomy`), fail-closed, written to
  `<target>/.servo/readiness/<goal-id>.json`. Human-owned — the artifact starts
  `approval_status: proposed` and is never auto-approved; a human reviews the
  scorecard and flips it to `approved`. Readiness sits **upstream of**
  `/servo:edd-suitability`: suitability asks "can this spec be evaluated?", this
  asks the prior question "is the premise safe to run unattended at all?".

  Fire this skill when the user wants to:

    - "is this goal/brief ready to run unattended?" / "is this safe to hand to a
      long-horizon loop?"
    - "why won't the background run / recurring Routine start?" / "what's blocking
      autonomy on this goal?"
    - "review this prompt before I let it run for a day" / "is this brief precise
      and bounded enough?"
    - "approve this goal for an unattended run" / "check whether <goal> is
      approved for autonomy"
    - "is my run identity separated from my merge identity?" / "will owner-approval
      gates actually hold?"

  Do NOT fire on:

    - "is this spec suitable for EDD?" / "what evidence is this spec missing?" —
      that's `/servo:edd-suitability`. Readiness sits UPSTREAM of it and hands off
      to it; it does not judge EDD-shape or the acceptance criteria.
    - "scaffold the oracle" / "install servo" / "detect signals" — that's
      `/servo:scaffold-init`. Readiness *reads* the oracle/signals it produced; it
      does not synthesize them.
    - "run the loop" / "iterate on this" / "let claude fix it" — that's
      `/servo:agent-loop`. Readiness is the *precondition* an unattended launch
      surface consults, not the run.
    - "score this build" / "what's the oracle score?" — that's
      `/servo:quality-gate`. Readiness judges the *premise*, not a build.

  When in doubt, ask which servo skill the user means rather than invent a
  trigger match.
---

# /servo:autonomy-readiness

The Compile-phase gate **upstream of** `/servo:edd-suitability`. Servo can prove
*done* (the oracle) and *evaluable* (`edd-suitability`), but not *ready to run
unattended*. The most expensive long-horizon failure mode is not a weak oracle —
it is a faithfully-converging loop pointed at a **badly-scoped goal**, or an
**identity-collapsed** setup where every downstream owner-approval gate is
fictional. This skill reviews the scope + initial prompt and refuses a bad
premise at the boundary with an auditable, human-approved verdict
([ADR-0029](../../docs/decisions/adr-0029-autonomy-readiness-gate.md)).

The helper lives at `${CLAUDE_PLUGIN_ROOT}/skills/autonomy-readiness/`:

| Helper | Role |
|---|---|
| `readiness.py analyze <target> --prompt <brief>` | run all tiers → the verdict JSON at `.servo/readiness/<goal-id>.json` (atomic), `approval_status: proposed` |
| `readiness.py approve <target> (--goal-id \| --prompt)` | human flip `proposed → approved` (refuses an `unsafe_for_autonomy` verdict) |
| `readiness.py check <target> --prompt <brief>` | the consumer gate: exit 0 iff the goal's artifact exists AND is `approved` |
| `readiness.py analyze … --explain` | ordered scorecard trace (which checks fired and why), stdout-only |

> **Re-running `analyze` revokes a prior approval** (by design, fail-closed): the
> same brief hashes to the same `<goal-id>`, so a fresh `analyze` overwrites the
> artifact back to `approval_status: proposed`. Re-score means re-approve — a
> premise that changed must be re-reviewed before an unattended run may consult it.

## When to use this skill

Use when the user wants to know **whether a goal is safe to hand to an
unattended run** and, if not, **what to tighten**. Judging EDD-shape is
`/servo:edd-suitability`; scaffolding the oracle is `/servo:scaffold-init`;
running the loop is `/servo:agent-loop`; scoring a build is
`/servo:quality-gate`. This skill is the **gate upstream of all of them** — it
judges the *premise*, and emits a verdict a launcher reads before starting.

This is a **host / Compile-phase tool**, like `/servo:edd-suitability` — it runs
from the full servo plugin against a target, and is **not** vendored into a
scaffolded target's unattended runtime (the heartbeat/loop never invoke it
themselves). It is therefore intentionally absent from
`.claude-plugin/install-contract.json`'s `required.skills`.

## Q&A before analyzing

1. **Target path** — the repo whose oracle / tree / components are inspected (and
   where the verdict artifact is written).
2. **The brief** — the initial prompt (`--prompt`) or a file (`--brief-file`).
3. **Caps** — a finite `--cost-ceiling`, `--max-iterations`, and
   `--max-candidates` (an unbounded long-horizon run is unsafe).
4. **Mutation perimeter** — a `--mutation-perimeter <path.json>` (allowlist +
   protected denylist) bounding what the run may change.
5. **Autonomous merge?** — pass `--declares-autonomous-merge` only if the run's
   own principal will merge its output; otherwise identity is an advisory note.

## Workflow

```bash
# Analyze — human summary by default (verdict + each concern/unsafe check).
python3 "${CLAUDE_PLUGIN_ROOT}/skills/autonomy-readiness/readiness.py" \
    analyze <target> --prompt "<brief>" \
    --cost-ceiling 5.0 --max-iterations 20 --max-candidates 3 \
    --mutation-perimeter <perimeter.json>
#   → writes <target>/.servo/readiness/<goal-id>.json (atomic), exit 0.

# Full artifact JSON (for a consumer / audit):
python3 ".../readiness.py" analyze <target> --prompt "<brief>" --json

# Why did it decide that? Ordered scorecard trace (stdout-only, never persisted):
python3 ".../readiness.py" analyze <target> --prompt "<brief>" --explain

# Human review, then approve (fails closed on an unsafe verdict):
python3 ".../readiness.py" approve <target> --prompt "<brief>"

# The consumer gate a launcher consults (exit 0 = permit, non-zero = refuse):
python3 ".../readiness.py" check <target> --prompt "<brief>"
```

A non-`ready` verdict is **exit 0** — an unsafe premise is a *successful
analysis*, not an error. Exit `2` is reserved for environment errors (missing
target / missing artifact / a fail-closed refusal to approve an unsafe verdict);
`analyze` never exits 1, and a failed analysis never leaves a torn artifact.
`check` exits **1** (a normal reportable negative) while the artifact is missing
or `proposed`, and **0** once `approved`.

## The verdict (closed three-state gate)

| Verdict | Meaning | Next step |
|---|---|---|
| `ready` | every deterministic, model-judged, and identity check passed | review, then `approve` |
| `needs_tightening` | a precondition or premise-quality concern fired | address it, re-`analyze` |
| `unsafe_for_autonomy` | identity collapse (declared autonomous merge + confirmed merge authority) | cannot be approved; fix separation |

Fail-closed: indeterminate input never yields `ready`. The scorecard records a
`checks: [{code, tier, status, message}]` list across three tiers —
**deterministic** (oracle present/executable, ≥1 approved component, finite
budget/iteration/candidate caps, clean isolated tree, mutation perimeter),
**model** (Precision, Scope, Stop/escalation, Safety surface, Contradiction,
scored via the expand-then-independent-review two-call pattern), and
**identity** (conditional, best-effort). The final verdict is the worst tier.

### Identity posture (conditional, best-effort — amended ADR-0029)

Identity collapse escalates to `unsafe_for_autonomy` **only** when the run
**declares** an autonomous land/merge capability (`--declares-autonomous-merge`)
**and** a host probe (`gh`) confirms the run principal can merge to the base
branch. Under servo's default human-lands-the-worktree model (no autonomous
merge declared) it is an **advisory scorecard note**, never a refusal. When the
run declares autonomous merge but the probe cannot resolve merge authority, the
verdict degrades to `needs_tightening` ("cannot confirm identity separation") —
never a silent pass.

## Reuse seams — jig co-install (subprocess + filesystem only, no import)

When jig's `clarify` skill is co-installed at user scope
(`~/.claude/skills/clarify/SKILL.md`), the model-judged tier splices jig's own
framing into the prompt-scoring calls; otherwise it ships the built-in
`readiness-rubric.md`. The probe is a **filesystem hint** and the call is a
**subprocess** — there is **no servo→jig Python import** (ADR-0011 boundary),
so servo never hard-depends on jig.

## Consumer contract — the `loop.py` preflight (documented seam, not built here)

The `check` verb is the deterministic gate an unattended launcher consults.
Wiring it into the two unattended long-horizon launch surfaces of slice 003-08 /
[ADR-0008](../../docs/decisions/adr-0008-loop-on-autonomy-primitives.md) —
`loop.py --background` (refuse-to-start) and `loop.py --emit-routine-prompt`
(refuse-to-emit) — is **slice 023-02**, deliberately **not built here**. The
heartbeat's per-finding `loop.py --prompt` dispatch sets neither flag and is
exempt by construction ([ADR-0018](../../docs/decisions/adr-0018-suitability-gates-compile-not-heartbeat.md));
023-02 carries the loop-layer regression guard that proves that exemption.
