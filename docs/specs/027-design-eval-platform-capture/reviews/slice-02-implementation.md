---
slice: 027-02 — capture-provider seam + web default
pass: implementation (compliance + craft)
verdict: pass
reviewer: jig:reviewer (in-session independent subagent, no build-conversation access)
reviewed_at: 2026-08-21
prompt_source: implementation review of commit a6950a2 against slice-02 ACs
---

VERDICT: pass — all six ACs satisfied, no blocking issues.

Compliance (AC1–AC6):
- Provider selection follows env > config > "web" (`_resolve_capture_transport`);
  the web path is a behavior-preserving refactor into `_capture_web`.
- AC4: an unknown provider fails closed to `EnvError`, validated in `score()`
  BEFORE the `if provider == "web": preflight_capture` gate and before any capture,
  with a second guard in `capture_app` — no path spawns a subprocess for an unknown
  provider.
- AC5: the ledger records `capture_provider` = resolved name on live, `null` on the
  fake arm.
- AC6: a `capture` block is excluded from `definition_hash` and does not stale a
  frozen eval.
Tests are feature-bearing (removing the ledger field / selector / registry guard
turns them red). The 2-arg `capture_app` callers keep working via the defaulted
`provider="web"`; `_ledger`/`capture_app` have no cross-skill callers.

Non-defect observations (dispositioned, no change required):
- The judge-transport key check runs before provider validation, so a run missing
  both a key and a valid provider surfaces the key error first. Both are env_error
  rc 2; ordering is not spec-constrained.
- The fake-scores arm leaves `provider=None` and skips transport validation — by
  design (fake-scores is the offline/test hook; no capture runs).
- The AC4 test is double-guarded (score() + capture_app), so it proves fail-closed
  but does not isolate the "before preflight" ordering. Honest classification:
  feature-bearing but weaker than the other five.
