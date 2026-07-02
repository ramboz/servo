---
status: Proposed
date: 2026-07-01
deciders:
supersedes:
superseded-by:
last_verified: 2026-07-01
---

# ADR-0021: Servo is oracle-first; the agent-loop is one optional consumer

## Status

Proposed (2026-07-01) — surfaced by an external dogfood (cwv-workbench spec 015);
awaiting acceptance.

## Context

The agent-loop ([spec 003](../specs/003-agent-loop/spec.md),
[ADR-0008](adr-0008-agent-loop-claude-code-autonomy.md)) drives edits by shelling
out to `claude -p`. In an external dogfood, all six slices of cwv-workbench's
spec 015 were driven to DONE using servo's **Compile + gate** — but the **native
loop could not run at all** because it was invoked from inside another (auto-mode
Claude Code) agent:

- the spawned `claude -p` could not authenticate (401 — the host's gateway token
  is not inherited by the subprocess; [Bug 001](../bugs/001-agent-loop-masks-auth-error-as-plateau.md));
- once auth was fixed, the runner could not obtain **edit permissions**
  ([Bug 002](../bugs/002-agent-loop-no-permission-mode.md)); and
- the outer agent's host safety classifier (correctly) **refused to spawn an
  unrestricted unattended sub-agent** — not something servo can or should override.

The working pattern was **servo-as-oracle + an external implementer**: servo
Compiled a frozen oracle, an in-harness implementer (jig:implementer) did the
edits, and `quality-gate` (`gate.py`/`oracle.sh`) was the pass/fail authority.
This showed servo's durable value is **Compile** (suitability + spec-oracle +
freeze) and **the gate**; the loop is one optional consumer — and it is a
top-level / user-run tool, not something another agent can nest.

## Decision

Treat servo as **oracle-first**, and bless a first-class **external-driver /
bring-your-own-implementer** mode:

- **Compile** produces a frozen, reviewable oracle; **`quality-gate`** is the
  authority. Any driver — a human, CI, or another agent — may perform the edits.
- The **agent-loop is one optional driver** among these, not the center.
- `agent-loop` must **detect when it cannot function** (auth failure per Bug 001,
  denied edit permissions per Bug 002, or a restricted/nested host) and **refuse
  loudly** with a terminal reason, rather than silently plateauing.
- Document the oracle-as-a-service path on the skill surface so "servo Compiles;
  you (or your CI/agent) drive; `quality-gate` judges" is a named, supported flow.

## Consequences

### Positive
- Servo is usable in the common environments where the headless loop cannot run
  (another agent, CI, or a permission-restricted host drives the edits).
- A clearer product spine: the Compile + gate core is the value; the loop is a
  convenience layer over it.

### Negative
- The BYO-implementer contract must be documented and supported.
- `agent-loop` grows refuse-when-nonfunctional paths (auth / permission / nesting).

### Neutral
- Does not remove or deprecate the loop; it reframes it as one consumer.

## Alternatives considered

- **Keep loop-centric; treat non-loop use as unsupported.** Rejected — the
  dogfood shows loop-nesting is a real, common case and it is blocked by design.
- **Make the loop work nested by having servo request/inject permissions.**
  Rejected — a host safety classifier correctly blocks an agent from spawning an
  unrestricted sub-agent; servo should not try to defeat it (see Bug 002's caveat).

## Verification

cwv-workbench spec 015 ran end-to-end (6/6 slices DONE) via Compile + gate + an
external implementer, with the native loop provably unusable. Bugs 001/002
capture the loop's failure modes. Acceptance criterion for the follow-on work:
`agent-loop` emits a distinct terminal reason (not `oracle_plateau`) on auth /
permission / nesting failure, and the skill docs describe the oracle-as-a-service
flow.

## References

- [ADR-0008](adr-0008-agent-loop-claude-code-autonomy.md) — agent-loop autonomy
- [Spec 003](../specs/003-agent-loop/spec.md) — agent-loop
- [Bug 001](../bugs/001-agent-loop-masks-auth-error-as-plateau.md),
  [Bug 002](../bugs/002-agent-loop-no-permission-mode.md)
- cwv-workbench ADR-0015 (the dogfood target)
