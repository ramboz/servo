---
status: DONE
dependencies: [adr-0029, adr-0015, adr-0018, adr-0026]
last_verified: 2026-08-04
---

# Spec 023 — autonomy-readiness-gate

> **Status: 023-01 DONE (2026-08-06); 023-02 DEFERRED.** Implements
> [ADR-0029](../../decisions/adr-0029-autonomy-readiness-gate.md) (**Accepted**,
> frame-critique pass recorded — four frame flaws caught and fixed before code).
> Slice **023-01** — the `autonomy-readiness` skill (verdict, deterministic +
> model-judged tiers, conditional identity posture, human `proposed→approved`
> gate, `check` consumer contract) — is landed. Slice **023-02** (the `loop.py`
> `--background`/`--emit-routine-prompt` preflight that auto-consults `check`) is
> split out and **DEFERRED** until picked up. Part of the long-horizon autonomy
> bridge (the `oh-my-cli` follow-on); mirrors jig ADR-0051 / jig spec 106 on
> identity separation, conditioned on servo's execution model (see Notes).

## Why this spec

Servo can prove *done* (the oracle) and *evaluable* (`edd-suitability`), but not
*ready to run unattended*. The most common way a long-horizon run wastes a day is
a faithfully-converging loop pointed at a badly-scoped goal — or an
identity-collapsed setup where every downstream owner-approval gate is fictional.
[ADR-0029](../../decisions/adr-0029-autonomy-readiness-gate.md) decides the fix: a
Compile-phase `autonomy-readiness` gate upstream of `edd-suitability` that reviews
the scope + initial prompt and refuses to start on a bad premise.

## Goals (provisional)

1. A new `autonomy-readiness` skill emits a closed three-state verdict
   `ready | needs_tightening | unsafe_for_autonomy`, exit `{0,2}`, atomic artifact
   at `<target>/.servo/readiness/<goal-id>.json`, human-owned
   (`approval_status: proposed → approved`, never auto-approved).
2. Deterministic checks (local, offline): oracle present/executable/≥1 approved
   component; finite budget/iteration/`max-candidates` caps; clean-tree + worktree
   isolation; explicit mutation perimeter.
2b. Identity posture (conditional, best-effort — not offline): **run-identity ≠
   merge-identity** escalates to `unsafe_for_autonomy` **only when the run
   declares an autonomous land/merge capability** and a host probe confirms the
   run principal can merge the base branch; in servo's default
   human-lands-the-worktree model it is an advisory scorecard note, never a
   silent bless of collapse nor a false refusal (per amended ADR-0029).
3. Model-judged checks score the *prompt itself*: Precision, Scope-boundedness,
   Stop/escalation conditions, Safety surface, Internal contradiction — reusing
   `eval-authoring`'s expand-then-independent-review two-call pattern.
4. The two unattended long-horizon launch surfaces of slice 003-08/ADR-0008 gate
   on readiness: `loop.py --background` refuses to *start* and `loop.py
   --emit-routine-prompt` refuses to *emit* without an `approved` readiness
   artifact (sibling of the refuse-without-oracle preflight). The heartbeat
   dispatches `loop.py --prompt` **synchronously with neither flag**, so it is
   exempt by construction (ADR-0018: spec-less/autonomous, governed by `gate.py`)
   — a regression guard asserts at the loop.py layer that a `--prompt` run with
   neither flag and no readiness artifact is not refused.
5. Reuse seams: shell to jig `clarify` + `frame_review` when jig is co-installed
   (subprocess + filesystem only, ADR-0011 boundary); built-in rubric otherwise.

## Vertical slices

- **023-01 — readiness verdict + artifact + human approval:** the
  `autonomy-readiness` skill, the three-state verdict, the atomic
  `<target>/.servo/readiness/<goal-id>.json`, the deterministic + model-judged
  tiers (including the conditional identity posture), the proposed→approved human
  gate, and a `check` consumer contract (exit non-zero while `proposed`, zero once
  `approved`) — a human runs readiness on a real goal and gets an actionable,
  approvable verdict that blocks a bad-premise start, end-to-end value before any
  loop is wired. See the slice file for ACs.
- **023-02 — loop.py readiness preflight (the two unattended surfaces):** wire
  `loop.py --background` (refuse-to-start) and `loop.py --emit-routine-prompt`
  (refuse-to-emit) to auto-consult the 023-01 `check` contract, with the
  loop-layer regression guard proving heartbeat dispatch (neither flag) is
  unaffected (ADR-0018). Split out from 023-01 because it edits the `loop.py`
  core + its large existing suite and is independently sizable (as the spec Notes
  anticipated). **DEFERRED** until 023-01 is DONE.

## Notes

- The identity check is the executable form of jig ADR-0051's precondition, but
  conditioned on servo's execution model: servo's loop/heartbeat never merge
  (the dispatch worktree is retained for a human to land), so identity collapse
  is a *latent* hazard. It returns `unsafe_for_autonomy` only when a run declares
  an autonomous land/merge capability and a host probe confirms the run principal
  can merge the base branch; otherwise the posture is an advisory scorecard note
  (amended ADR-0029, per the frame-critique of 2026-08-06).
- Refuse-without-readiness preflight wiring into `loop.py` (the heartbeat is
  excluded per ADR-0018) may split into a second slice (023-02) if it proves
  independently sizable.
