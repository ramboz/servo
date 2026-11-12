---
slice: 041-02 — credit brake and supported loop launch
pass: arch
verdict: pass
reviewer: build-session arch review (cites ADR-0048 + jig:reviewer)
reviewed_at: 2026-11-12T01:25:45Z
prompt_source: Agent(jig:reviewer) adversarial budget-safety review, delegated by build session
substrate: non-interactive
---

VERDICT: pass

The credit-brake architecture implements ADR-0048 (Accepted) Option A: a brake
denominated in AI credits, never USD-converted, hard between invocations and soft
within (bounded by the stated overrun), fail-closed on missing / partial
telemetry. It fits servo's host-mode architecture **additively** — the Claude USD
path is byte-identical; the Copilot path branches on host and keeps units apart
(USD fields null under Copilot, credit fields separate). The design follows the
041-01 findings: the invocation-scoped cap + session-cumulative report drive a
session-DELTA per iteration; `aiCreditsStatus` is the primary partial gate; and
the per-model overrun bound is applied REACTIVELY because the admin-pinned worker
model (and its context window) are unknown pre-launch. The independent compliance
review confirmed no fail-open / under-count path. Deferred items (plan-sourced
ceiling, known-priced oracle refusal, cross-process resume) are each fail-closed
and recorded in the deviation log + refinement-todo.
