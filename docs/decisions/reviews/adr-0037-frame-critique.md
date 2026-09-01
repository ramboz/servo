---
adr: 0037
pass: frame-critique
verdict: needs-changes
reviewer: jig:reviewer subagent x2 independent (claude-fable-5), orchestrator-verified against loop.py
reviewed_at: 2026-09-01T17:07:16Z
prompt_source: review.py frame-critique docs/decisions/adr-0037-agent-loop-permission-preflight.md
---

Frame-critique of ADR-0037 (agent-loop preflights headless edit permission
before the first paid iteration), two independent `jig:reviewer` subagents
(claude-fable-5), prompt built by `review.py frame-critique`. **Both returned
`needs-changes` and independently converged on the same finding**, which the
orchestrator then verified against the cited code.

## What is settled (not in dispute)

The **policy** is grounded and fine: ADR-0021 (Accepted) requires the loop to
detect when it cannot edit and "refuse loudly," and the airlock spec-008
evidence (two runs, ~$2.2, zero edits on a silent permission wall) is real —
corroborated at n=2 (Bug 002 hit the identical "reads/reasons but Write/Edit
denied, oracle never moves" failure on a separate dogfood, cwv-workbench spec
015). The disagreement is only with ADR-0037's *mechanism*.

## Primary finding (both critics) — the exposed assumption is the probe's SHAPE

ADR-0037 bets on an **ex-ante** edit-capability probe run before iteration 1,
"through the same permission resolution the runner's `claude -p` will use"
(adr-0037:51-52, 72-78). Two problems, both verified:

1. **Cheap XOR faithful.** The only faithful resolution is the runner's own
   mechanism — `_invoke_claude` builds `["claude","-p",…] + _settings_args(target)`
   at `cwd=target` (loop.py:1662-1674). A real `claude -p` probe is neither
   "instant/free" (contradicting adr-0037:47,84) nor deterministic (a one-turn
   agent may not emit an `Edit` → false-negative that blocks a capable run). The
   only genuinely cheap probe — a direct Python scratch-write by loop.py — is
   meaningless: loop.py already writes into the target unconditionally
   (`_atomic_write_state`), so it always passes → false-positive, the exact
   silent-waste the feature exists to prevent.

2. **"Same settings layers" is contradicted by the ADR's own cited fix.**
   VERIFIED: `_settings_args` (loop.py:1607-1621) forwards ONLY the committed
   `.claude/settings.json`, never `.claude/settings.local.json` — yet the grant
   the ADR cites as its proof (adr-0037:34-36) was in `settings.local.json`. The
   runner's real resolution is `--settings <committed>` MERGED with claude's own
   cwd-hierarchy (user/project/project-local/managed/`defaultMode`), a
   version-dependent precedence. loop.py knows how to read that full stack for
   its hook audit (`_layered_settings`, loop.py:851-853 reads settings.local.json)
   but does NOT forward it. A probe modeled on `_settings_args` would miss the
   very grant the ADR cites → false-negative.

3. **Edit-capability is not a single global yes/no.** Permissions are path- and
   tool-scoped (`Edit(src/**)`, Write-vs-Edit). The observed failure was `Edit`
   on an existing `map.js`; the ADR proposes "a scratch write / a no-op Edit"
   (adr-0037:76). A scratch *Write* (new path) or a *Bash*-satisfied probe can
   pass while `Edit`-to-source is denied → false-positive; a scratch path under
   an `Edit(src/**)`-scoped target is denied though the real edit is allowed →
   false-negative.

**Net downstream risk:** false-positive → the silent-waste failure recurs
(feature adds cost, delivers nothing); false-negative → blocks runs that would
have succeeded (**strictly worse than status quo** — a new regression neither
the status quo nor a post-hoc detector can produce). The ADR *names* the
fidelity risk (adr-0037:93-95) but does not price it: no grade, no
drift-detection story, and the kill criterion (99-101) covers only "preflight
becomes redundant," never "probe is unfaithful / blocks a capable run."

## The un-ruled-out alternative (both critics proposed it independently)

A **post-hoc** detector: run iteration 1, and if the runner reports zero edits
AND the oracle is unmoved, refuse `rc=2` with the same breadcrumb before
iteration 2. This is grounded in already-shipped machinery:
- the loop scores the oracle every iteration (`oracle_score_history`);
- the runner verdict already carries `files_changed` (agents/runner.md:52,64,
  present only on `verdict: CHANGES_MADE`);
- the ADR's entire lineage (bugs 001/002/004) is post-hoc result-envelope
  inspection, and ADR-0021 is shape-agnostic ("detect… and refuse loudly").

It caps waste at ~one iteration, reads *reality* instead of predicting it, and
carries NO fidelity burden and NO false-negative regression. ADR-0037's
Options B/D are strawmen ("warn-and-continue" / "do nothing"); this real
alternative is never considered, so Option A's "free" pro is measured against a
strawman.

## Scoping asymmetry (critic B) — the likely synthesis

The ADR applies the preflight to "both drivers" uniformly (adr-0037:72), but the
two drivers differ:
- **loop driver** — per-iteration checkpoints exist, so the cheap robust
  **post-hoc** option is available.
- **goal driver** — one long `claude -p`, no cheap mid-run checkpoint, so
  **ex-ante has genuine value** here. But note its existing audit
  (`_audit_hook_settings`, loop.py:836-891) reads only
  `disableAllHooks`/`allowManagedHooksOnly` — a DIFFERENT axis than the
  `permissions`/`defaultMode` edit-permission the airlock hit (VERIFIED), so a
  preflight is net-new resolution logic, not an extension of the existing audit.

A hybrid — post-hoc for the loop driver, a best-effort ex-ante check only for
the goal driver — is the shape both critiques point toward.

## Recommendation to the owner (decision fork)

The mechanism, not the policy, needs a decision. Options:
- **(A) Post-hoc / hybrid (recommended):** rewrite the Decision to detect
  zero-edits-after-iteration-1 for the loop driver; reserve a best-effort
  ex-ante check for the goal driver only, with the fidelity limits named. This
  is what the convergent critique supports.
- **(B) Keep the ex-ante probe but re-price it honestly:** define the probe as a
  real `claude -p` micro-invocation (accept the cost), scope it to `Edit` on an
  existing in-repo file, and add the missing kill criterion for the
  false-negative case. Weaker; still carries the fidelity burden.
- **(C) Accept as-is:** not advised — ships a self-admitted fidelity burden plus
  a new capable-run-blocking regression.

This is the owner's call (the ADR itself says the owner should run
frame-critique before adopting). `accept` stays correctly blocked until a
revised frame earns a pass.
