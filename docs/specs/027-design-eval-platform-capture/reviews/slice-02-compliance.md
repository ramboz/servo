---
slice: 027-02 — capture-provider seam + web default
pass: compliance
verdict: pass
reviewer: jig:reviewer (in-session independent subagent, no build-conversation access)
reviewed_at: 2026-08-21
prompt_source: independent implementation review of commit a6950a2 against slice-02 ACs
---

PASS — all six ACs satisfied.

- AC1/AC2: absent config and explicit `capture.transport: "web"` both drive the
  exact existing `node capture.mjs --screen --out` spawn; a pre-slice frozen eval
  still scores and does not go stale (`_capture_web` is a behavior-preserving
  refactor of the old `capture_app` body).
- AC3: resolution precedence env (`SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT`) >
  `config.capture.transport` > `"web"` (`_resolve_capture_transport`).
- AC4: an unknown provider raises `EnvError` → rc 2 env_error, validated in
  `score()` BEFORE `if provider == "web": preflight_capture` and before any
  capture, with a second guard in `capture_app` — no path spawns a subprocess for
  an unknown provider; never a fall-through to web.
- AC5: the ledger records top-level `capture_provider` = resolved name on live,
  `null` on the fake arm.
- AC6: a `capture` block is excluded from `definition_hash` (only `viewport` is in
  `_EXTRA_HASH_FIELDS`) and does not stale a frozen eval; composite/freeze/
  env_error/0-1-2 contracts intact.

Tests are feature-bearing — removing the ledger field, the selector, or the
registry guard turns them red. The 2-arg `capture_app` callers keep working via
the defaulted `provider="web"`.
