---
status: Proposed
dependencies: []
last_verified: 2026-08-27
frame_review: true
---

# ADR-0037: Agent-loop preflights headless edit permission before the first paid iteration

## Status

Proposed (2026-08-27)

> Filed from a dogfood run against the **airlock** project (spec 008, GA4
> purchase-conversion). Evidence is external to this repo; the owner should
> run the frame-critique + accept flow before adopting.

## Context

`/servo:agent-loop` (`loop.py`) subprocesses `claude -p --agent runner` with
**no** `--dangerously-skip-permissions` and no `acceptEdits` / allow-list. In a
default-permission context the headless child's `Edit` / `Write` tool calls are
**silently denied** — headless mode cannot prompt for approval — so the `runner`
*runs, emits verdicts, and costs real money*, but makes **zero source edits**.
The oracle never moves, and the only way to detect it is inspecting the diff
after the run.

Observed (airlock spec 008, 2026-08-27): two runs — the goal driver
(`iteration_cap_reached`, 15 turns, **$1.27**) and the loop driver
(`oracle_plateau`, 4 iters, **$0.94**) — both made **zero edits** (`map.js`
byte-unchanged) and left the oracle at its red baseline (composite 0.5). Both
failed **safely** (guardrails fired, fail-closed: no false pass, tests not
gamed), but ~**$2.2** was spent proving a permission wall a preflight would have
caught for free. After the user added `.claude/settings.local.json`
`{"permissions":{"defaultMode":"bypassPermissions"}}`, the loop converged in
**one iteration ($0.18)**.

servo already fails **closed, before spending**, on comparable preconditions —
`dirty_tree` (003-07), `manifest_missing` / `oracle_missing`. Headless
edit-capability is the missing member of that set: it is the precondition that
makes the runner able to do its job at all.

## Decision Options Considered

### Option A: Preflight an edit-capability probe → refuse `rc=2` before iteration 1 (chosen)
- **Pros:** turns a silent multi-dollar non-result into an instant, free,
  actionable refusal; mirrors the existing `dirty_tree` / `manifest_missing`
  fail-closed preflights; costs nothing when permission is already granted.
- **Cons:** one more preflight to maintain; the probe must resolve permission
  **exactly** as the runner's `claude -p` will (same settings layers), or it
  false-negatives (blocks a capable run) or false-positives (passes an
  incapable one).

### Option B: Warn-and-continue
- **Pros:** never blocks a run.
- **Cons:** still spends the full budget making zero edits — the warning does
  not prevent the waste it warns about. Rejected.

### Option C: Auto-inject `--dangerously-skip-permissions` into the child
- **Pros:** the loop "just works" unattended.
- **Cons:** servo would **silently disable the host's permission system** on the
  user's behalf — an unacceptable trust escalation for an unattended tool, and
  exactly the kind of self-granted bypass a host safety layer should (and here
  did) refuse. Rejected.

### Option D: Do nothing (status quo)
- **Cons:** the documented failure above — silent budget waste, diagnosable only
  post-hoc. Rejected.

## Recommended Decision

Adopt **Option A**. Before the first paid iteration (both drivers), `loop.py`
runs a cheap **edit-capability probe** through the same permission resolution
the runner's `claude -p` will use (e.g. attempt a scratch write / a no-op
`Edit`), and on denial **refuses fail-closed** — `rc=2`,
`terminal_reason=edit_permission_unavailable` — with a breadcrumb naming the fix
(a worktree `.claude/settings.local.json` grant, or a Routine with Bash +
Edit/Write granted, per 003-08). servo never self-grants the bypass; it names
what the **user** must grant, consistent with the host safety boundary.

## Consequences

**Becomes easier:**
- An un-actionable, multi-dollar silent failure becomes a zero-cost, first-turn,
  actionable refusal — the same posture as every other servo precondition.

**Becomes harder:**
- One more preflight to keep faithful to the child's real permission resolution;
  a drifting probe is worse than none (false verdicts).

## Assumptions

- The probe can faithfully predict the runner's edit permission (it resolves the
  same settings layers the subprocessed `claude -p` reads). If it cannot, the
  refusal is unreliable and the feature is net-negative.

## Kill criteria

- If headless `claude -p` gains reliable default edit capability (or `loop.py`
  moves to an explicitly-granted permission model per invocation), the preflight
  is redundant and should be retired rather than maintained.

## Open questions

- Should the probe be edit-only, or also verify `Bash` (the runner + `gate.py`
  need it)? The 008 evidence showed `Bash`/gate ran while `Edit` was denied, so
  edit-capability is the load-bearing probe — but a combined check may be
  cheaper to reason about.
