---
slice: 027-02 — capture-provider seam + web default
pass: reconciliation
verdict: pass
reviewer: jig:reviewer (in-session independent subagent)
reviewed_at: 2026-08-21
prompt_source: reconciliation review of the deviation log / sweep / DoD vs disk
---

VERDICT: pass — reconciliation artifacts honest and complete.

Deviation-log honesty: every claim matches `score.py` — the module-level
`_CAPTURE_PROVIDERS` registry, `_resolve_capture_transport` precedence,
`capture_app` thin dispatcher with defaulted `provider="web"`, double validation
(score() up front + capture_app guard), preflight gated to web, `_ledger`'s
required keyword-only `provider`, and `capture` absent from `_EXTRA_HASH_FIELDS`.

SKILL.md accurately documents the `capture.transport` selector, the
`SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT` override, and the `capture_provider` ledger
field (disambiguating the three transport-ish names: judge `transport` /
`capture_provider` / per-screen `capture_transport`).

DoD accuracy: the "red when removed" box is honestly scoped — the two AC6 tests
are regression-guards (a `capture` key was already excluded from the hash, so they
stay green without the selector); the five feature-bearing tests go red without it.
The full-suite box honestly names the one pre-existing unrelated red test.

Sweep completeness: non-no-op rows (`SKILL.md` updated, `docs/specs/README.md`
deferred) correct; `docs/refinement-todo.md` correctly `no-op` (nothing deferred).

Note: the reviewer had read-only tools and could not run git; the orchestrator
confirmed the uncommitted set was exactly the slice `.md` + `SKILL.md`.
