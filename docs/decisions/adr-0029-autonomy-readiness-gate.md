---
status: Accepted
date: 2026-08-04
deciders: ramboz
supersedes:
superseded-by:
frame_review: true
last_verified: 2026-08-06
---

# ADR-0029: Autonomy-readiness pre-flight gate

## Status

Accepted (2026-08-06)

> **Recorded, not yet built.** This ADR captures the servo-side decision for the
> long-horizon-autonomy bridge (the `oh-my-cli` follow-on). It is paired with the
> DRAFT [spec 023](../specs/023-autonomy-readiness-gate/spec.md) and mirrors jig
> ADR-0051 (identity separation). No skill or `loop.py` code ships with this
> record.

## Context

Servo's Compile phase already asks *"can this spec be evaluated?"* — the
`edd-suitability` gate ([ADR-0015](adr-0015-edd-suitability-gate.md),
[ADR-0018](adr-0018-suitability-gates-compile-not-heartbeat.md)) emits a
three-state verdict and gates Compile. But nothing asks the prior question:
*"is the SCOPE and the INITIAL PROMPT itself precise and bounded enough to hand
to an unattended loop for a long horizon?"*

This is the most common way a long-horizon run wastes a day: not a weak oracle,
but a faithfully-converging loop pointed at a badly-scoped goal. `oh-my-cli`'s
16-day run worked partly because a human tightened the brief up front. Servo has
a hardened, human-approved definition of *done* (the oracle) and a hardened
definition of *evaluable* (`edd-suitability`), but no hardened definition of
*ready to run unattended*. A long-horizon `loop.py` run will happily start on a
one-line "make it better" brief with no cost ceiling and no scope perimeter.
(The heartbeat's short, machine-generated per-finding loops are a different
animal — spec-less by design and already governed by `gate.py` per ADR-0018;
this gate is about the human-authored long-horizon premise, and scopes to
`loop.py` accordingly.)

A second, host-level hazard compounds this: **identity collapse** (jig ADR-0051).
If the loop runs under the same principal that can merge its output, every
"owner-approval" safety gate downstream is fictional — there is no second party
to approve. A readiness gate that ignores this would bless an unsafe setup.

## Decision

Add a new Compile-phase skill, **`autonomy-readiness`**, positioned **upstream of
`edd-suitability`**, that reviews the scope + initial prompt and refuses to let an
unattended loop start on a bad premise. It mirrors the shapes servo already uses,
so it composes rather than reinvents.

**Contract.** A closed three-state verdict `ready | needs_tightening |
unsafe_for_autonomy`, exit `{0,2}` (fail-closed like `edd-suitability`), written
atomically to `<target>/.servo/readiness/<goal-id>.json`. Human-owned: the
artifact starts `approval_status: proposed`; a human reviews the scorecard and
flips it to `approved` (reusing the `eval-authoring` proposed→approved +
`criteria-check` mechanics). It **never** auto-approves.

**Two check tiers**, matching servo's existing deterministic-vs-model split:

- *Deterministic / offline:* an oracle exists, is executable, and has ≥1
  approved (non-draft) component (surface `checks.py --enforce-freeze` at
  readiness time); budget / iteration / `max-candidates` caps are **finite** (a
  24h run with no cost ceiling is unsafe); clean tree + base branch + worktree
  isolation are available (reuse `loop.py`'s dirty-tree preflight); and an
  explicit **mutation perimeter** exists (allowlisted paths + protected denylist
  — ties to jig ADR-0051's `protected_paths`). These are all local, offline
  facts, so this tier stays honestly offline and fail-closed.
- *Model-judged* (reuse `eval-authoring`'s expand-then-independent-review
  two-call pattern — nothing scores the *prompt itself* today): **Precision**
  (specific + bounded vs "make it better"); **Scope-boundedness** (does the brief
  name what is OUT of scope? a long run needs a hard perimeter); **Stop /
  escalation conditions** (does the brief say when to stop rather than thrash?);
  **Safety surface** (secrets / deploys / data migrations / external side-effects
  → require human checkpoints, downgrade to `needs_tightening`); **Internal
  contradiction**.

**Identity posture (conditional, best-effort — not offline-deterministic).**
jig ADR-0051's identity-collapse hazard is real, but it does not map onto
servo's execution model unconditionally, and "who can merge to the base branch"
is networked host policy (branch protection + org / repo permissions), not a
local offline fact — so it does **not** belong in the deterministic tier. Two
grounding facts drive the honest treatment: (a) servo's loop / heartbeat never
merge — `heartbeat dispatch` retains the worktree "so a human can inspect / land
the result", and `loop.py` produces a branch a human lands; there is no
autonomous merge step in servo's default model for a run identity to *collapse*
against; (b) merge authority is only resolvable via a host probe (e.g. `gh` repo
permissions / branch-protection), which may be unavailable offline. Therefore
identity-collapse is a **latent** hazard the readiness gate treats as follows:

- If the run **declares an autonomous land / merge capability** (a future run
  mode where the loop's own principal can merge its output), and a host probe
  confirms run-identity can merge the base branch, return
  `unsafe_for_autonomy` naming identity collapse — the hazard is then real.
- Otherwise (servo's default human-lands-the-worktree model, or no probe
  available), record the identity posture as a **best-effort advisory note** in
  the scorecard — never a silent pass that *blesses* collapse, never a false
  refusal of the ordinary model. When the probe cannot resolve merge authority,
  say so in the note rather than guessing.

This keeps the fail-closed guarantee where it is honest (the offline tier) and
refuses to mislabel a networked, conditional signal as an offline-deterministic
one — while still catching a genuinely identity-collapsed auto-merge setup.

**Refuse-without-readiness preflight — gated on the unattended long-horizon
launch surfaces, NOT on `loop.py` unconditionally.** The heartbeat has no independent
execution path: `heartbeat run` dispatches every finding *through*
`loop.py <worktree> --prompt` (synchronously, `subprocess.run`,
`skills/heartbeat/heartbeat.py`). So a preflight that fired on **every** fresh
`loop.py` run — the way the sibling refuse-without-oracle preflight does — would
sit upstream of every heartbeat dispatch and refuse ~100% of machine-discovered
findings (which carry no human goal-id and never get a `proposed → approved`
flip): the "off switch, not a gate" degeneration Accepted
[ADR-0018](adr-0018-suitability-gates-compile-not-heartbeat.md) rejected. The
scoping therefore needs a concrete **discriminator**, and one already exists in
the code rather than being invented here:

- **Discriminator = the *unattended long-horizon launch surfaces* of slice
  003-08 / [ADR-0008](adr-0008-loop-on-autonomy-primitives.md), which is exactly
  two and they are mutually exclusive at the CLI:** `loop.py --background` (the
  detached run that survives terminal close) **and** `loop.py
  --emit-routine-prompt` (which turns a seed brief into a *scheduled, recurring*
  cloud-Routine prompt — arguably the sharper hazard: no terminal, repeating).
  The readiness preflight gates **both**: `--background` refuses to *start*, and
  `--emit-routine-prompt` refuses to *emit*, unless an `approved` readiness
  artifact exists for the goal. Gating emission is the right hook for the Routine
  path — it is the last servo-owned moment before the brief escapes into a
  scheduler servo no longer controls.
- The heartbeat's per-finding dispatch is a **synchronous, foreground**
  `loop.py --prompt` run that sets **neither** flag (verified: heartbeat passes
  only `--prompt` / `--cost-ceiling` / `--max-iterations`), so it is exempt **by
  construction** — no heartbeat code change, no "skip-readiness" signal, no
  interaction with the readiness artifact. The heartbeat's premise-safety stays
  governed by `gate.py` and its untrusted-data guardrails, exactly as ADR-0018
  decided.
- An **attended** foreground `loop.py --driver goal` run (neither flag set) is
  not the threat model — a human is watching and can stop it; the readiness
  scorecard is still *available* for supervised runs but is advisory there, not a
  hard refusal.

**Regression guard asserts at the `loop.py` layer, not in `heartbeat.py`.**
Because the gate lives in `loop.py` (which the heartbeat calls), a guard that
merely checked "`heartbeat.py` contains no readiness preflight" would pass green
even if an unconditional `loop.py` preflight refused every dispatched finding —
a false-green at the wrong layer. The guard instead proves the **behavior**: a
`loop.py --prompt` run *without* `--background` and without a readiness artifact
is **not** refused for missing readiness. (A single per-configuration heartbeat
readiness approval — distinct from the per-finding prompt — is a possible future
extension, deliberately out of scope here.)

**Reuse seams (do not duplicate):** when jig is co-installed, probe for and shell
to jig's `clarify` skill (a six-category precision scanner) — filesystem probe in
the style of the existing jig-skill detection — and fold in a jig `frame_review`
critique of the brief's assumptions; otherwise ship a built-in rubric.

## Consequences

### Positive

- A long-horizon *unattended* run can no longer *start* — nor be *scheduled* as a
  recurring Routine — on an unscoped premise or an identity-collapsed setup; both
  slice-003-08 unattended surfaces (`--background`, `--emit-routine-prompt`) are
  gated. The cheapest possible insurance against the most expensive failure mode.
- Useful even without the loop: "is this brief precise enough to hand to anyone?"
  is valuable for supervised runs too.
- Puts servo ahead of `oh-my-cli` on the thing that matters most — the premise —
  by making readiness an executable, human-approved artifact rather than a
  habit.

### Negative

- Another human-approval gate before autonomy unlocks (intended friction).
- The model-judged tier costs tokens at Compile time; must stay a one-shot
  scorecard, not a loop.

### Neutral

- Reuses `edd-suitability` / `eval-authoring` artifact and approval shapes; no new
  approval mechanism invented.
- The identity posture reads host signals (best-effort, networked) but decides
  nothing about *how* identities are provisioned (that is the operator's / jig
  ADR-0051's concern). It escalates to a refusal only when an autonomous-merge
  capability makes collapse a live hazard; in servo's default human-lands model
  it is advisory, so it neither blesses nor falsely refuses that model.

## Alternatives considered

- **Fold prompt-readiness into `edd-suitability`.** Rejected: suitability answers
  "is this evaluable?", a different question with a different verdict vocabulary;
  overloading it would blur both. Readiness sits *upstream* and hands off to it.
- **Make it advisory (print warnings, never refuse).** Rejected: an advisory gate
  is exactly today's state (nothing stops a bad-premise run). Fail-closed with a
  human approval flip is the point.
- **Auto-tighten the brief with the model instead of refusing.** Rejected:
  silently rewriting the human's goal is the wrong authority; surface the
  scorecard and let a human tighten and approve.

## Verification

- Golden-case fixtures: a good brief → `ready`; an open-ended brief →
  `needs_tightening`; a secrets- / deploy-touching brief → at least
  `needs_tightening` with the safety surface named; a single-identity setup that
  **also declares autonomous merge** → `unsafe_for_autonomy` naming identity
  collapse, while the same single identity under servo's default
  human-lands-the-worktree model → advisory note, not a refusal.
- Both unattended surfaces proven red→green: `loop.py --background` refuses to
  *start* and `loop.py --emit-routine-prompt` refuses to *emit* without an
  `approved` readiness artifact. A regression guard proves the exemption at the
  `loop.py` layer: a `loop.py --prompt` run setting **neither** flag, without a
  readiness artifact, is **not** refused for missing readiness (so heartbeat
  dispatch, which sets neither, is unaffected — the behavioral analogue of
  ADR-0018's heartbeat-has-no-suitability guard).
- Artifact schema round-trips; the human-approval gate blocks while
  `approval_status: proposed`.
- Boundary integrity: no servo→jig Python import; jig `clarify` / `frame_review`
  reached by subprocess + filesystem only.

## References

- [Spec 023 — autonomy-readiness-gate](../specs/023-autonomy-readiness-gate/spec.md)
- [ADR-0015 — EDD suitability is a fail-closed gate](adr-0015-edd-suitability-gate.md)
- [ADR-0018 — suitability gates Compile, not the heartbeat](adr-0018-suitability-gates-compile-not-heartbeat.md)
- [ADR-0026 — generic eval-authoring surface](adr-0026-generic-eval-authoring-surface.md)
- jig ADR-0051 — autonomy governance plane and identity separation (sibling, `ramboz/jig`)
