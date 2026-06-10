---
status: Accepted
date: 2026-06-10
deciders: ramboz
supersedes:
superseded-by:
---

# ADR-0006 — Meta-judge Stop-hook output contract & fail-open posture

## Context

Spec 004 (`/servo:oracle-hook`) installs a Claude Code `Stop` hook — the
"meta-judge" — that scores every assistant turn against the scaffolded oracle
(via `gate.py`, ADR-0002) and feeds a retry hint back when the work is below
threshold. Like `gate.py`'s caller contract (ADR-0002), the hook's *output*
behaviour is consumed by parties that will be hard to renegotiate later: the
spec's own later slices (004-03..05), every project that installs the hook, and
the humans whose interactive sessions it runs in.

Three contract-shaping questions surfaced while authoring spec 004, and the
[ROADMAP](../specs/ROADMAP.md)'s shorthand ("emits retry hints as
`additionalContext`") turned out to be imprecise enough to be misleading:

- **Q1 — which feedback mechanism?** A `Stop` hook can either **block** the stop
  (`{"decision":"block","reason":…}`, exit 0 — the turn does *not* end, Claude
  keeps working *now*, `reason` is shown to Claude) **or** attach
  `hookSpecificOutput.additionalContext` (exit 0 — the turn *ends*, the hint is a
  system reminder Claude sees on the *next* turn). They are mutually exclusive.
  `additionalContext` cannot make a meta-judge keep working — it only annotates
  the next turn — so the ROADMAP wording would have shipped a no-op meta-judge.
- **Q2 — fail open or fail closed?** `/servo:agent-loop` (spec 003) fails
  **closed**: every guardrail halts the loop, because the danger is burning
  budget unattended. A `Stop` hook is the opposite environment — a human is in
  the session — and its dangerous failure mode is *blocking forever* on a
  misconfigured oracle and trapping the session.
- **Q3 — how aggressive?** Block until the oracle passes (up to Claude Code's
  consecutive-block cap), or nudge once?

The `Stop`-hook surface itself was grounded against the Claude Code hooks
documentation (2026-06 probe; see spec 004 "Pre-spec research" + Assumptions),
and validated end-to-end against synthetic stdin and the real `gate.py` in slice
004-01. A live-session confirmation is carried to the 004-05 dogfood.

## Decision

The meta-judge's output contract has four clauses.

**1. Block is the v1 default.** On `gate.py` exit 1 (below threshold) the hook
emits `{"decision":"block","reason":<hint>}` and exits 0. Blocking is the only
mechanism that makes the agent keep working, which is the meta-judge's entire
purpose. The softer `additionalContext` mode is a **project-owned** knob (the
project owns the installed `meta-judge.sh` and may switch modes), not the
default.

**2. Fail open on anything that is not a clean score.** `gate.py` exit 2
(env_error, any `reason` in ADR-0002's closed taxonomy), an uninvocable or
unparseable gate, or a gate timeout → the hook **never blocks**. It emits a
one-line `systemMessage` to the *user* (e.g. `servo meta-judge: oracle env_error
(reason=manifest_missing); not gating this turn …`) and exits 0, letting the stop
proceed. A meta-judge that can deadlock a human's session is worse than no
meta-judge at all.

**3. At most one nudge per stop sequence.** The hook reads `stop_hook_active`
from stdin and suppresses the nudge (exits 0, never invokes the gate) when it is
set — *or when it cannot be determined* (unparseable stdin, missing `python3`).
An indeterminate guard biases toward never trapping the session; only a
definitively-parsed `stop_hook_active: false` proceeds to score. This stays well
inside Claude Code's consecutive-block cap without depending on its exact value.

**4. Hint content is composite + threshold (+ `missing` when present).** The
below-threshold hint names the composite and the threshold, plus any components
`gate.py --json` reports as `missing`. Per-component *failing-score* evidence is
deliberately out of scope: `gate.py --json` exposes only
`composite`/`threshold`/`missing`, and the stock oracle reports `missing` only on
its env-error path — so surfacing which components scored low needs a spec-002
`gate.py` enhancement (deferred, see `docs/refinement-todo.md`).

The hook bounds its `gate.py` call with a `--timeout` (default 45s, override
`SERVO_META_JUDGE_GATE_TIMEOUT`) chosen to fire before the `settings.json` hook
`timeout` (default 60s), so a hung oracle yields a clean env-error the fail-open
path handles rather than an abrupt hook kill.

## Consequences

**Positive.**
- The interactive session gets the same deterministic, oracle-scored discipline
  as the headless loop, with no human remembering to run the gate.
- The hint is evidence-backed (real composite vs threshold), replacing the
  brittle transcript-regex "looks done" heuristics the meta-judge supersedes.
- The fail-open posture + one-nudge guard make the hook safe to leave installed:
  it cannot trap a live session, whatever state the oracle is in.

**Negative.**
- A genuinely below-threshold turn is blocked exactly once per sequence; a user
  who disagrees with the oracle must let the second stop through (or uninstall).
  Acceptable: the oracle is the project's own quality bar.
- The below-threshold hint is currently terse (composite/threshold) until the
  deferred per-component enhancement lands.

**Neutral.**
- The contract is `Stop`-event-specific. Extending the installer to other hook
  events (PreToolUse, etc.) is explicitly out of scope for spec 004 and would
  revisit this ADR.

## Alternatives considered

- **`additionalContext` default (the ROADMAP's literal wording).** Rejected as
  the default: it is non-blocking, so it cannot make the agent keep working —
  the meta-judge would be a no-op nudge. Retained as an opt-in project knob.
- **Fail closed (block on env_error too).** Rejected: a misconfigured oracle
  would trap the human's session — the exact footgun a `Stop` hook must avoid.
  This is the deliberate inversion of agent-loop's fail-closed brakes.
- **Block until the oracle passes (up to the cap).** Rejected as the default: too
  aggressive for interactive use; a documented project customization instead.
- **An LLM judge in the hook (`type: "prompt"`/`"agent"`).** Rejected for v1:
  paying a model round-trip on every turn-stop is expensive and non-deterministic.
  The deterministic oracle is the judge.

## Verification

- `templates/meta-judge.sh.template` implements clauses 1–4; covered by
  `skills/oracle-hook/test_hook.py` (`MetaJudgeScriptTests` — block/pass/runaway/
  indeterminate; `FailOpenSafetyTests` — every env-error reason warns and never
  blocks, gate-invocation failure fails open, the gate call is `--timeout`-bound
  and override-able).
- The block-vs-pass-vs-env-error decision table is total (one test per row).

## References

- [ADR-0002 — Quality-gate caller contract](adr-0002-gate-caller-contract.md) —
  the `gate.py` exit/JSON contract this hook consumes.
- [ADR-0001 — filesystem-only coupling](adr-0001-reuse-jig-test-detector.md) —
  the trust model the hook inherits.
- [Spec 004 — oracle-hook](../specs/004-oracle-hook/spec.md) — "Core model",
  "Hook output contract", and Assumptions.
- [Spec 003 — agent-loop](../specs/003-agent-loop/spec.md) — the fail-closed
  cousin this ADR inverts.
