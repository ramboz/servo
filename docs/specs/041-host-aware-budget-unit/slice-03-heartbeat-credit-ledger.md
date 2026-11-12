---
status: DRAFT
kind: feature
dependencies: [041-02]
last_verified: 2026-11-11
---

## Slice 041-03 — heartbeat credit ledger

**Goal:** A heartbeat pass on a Copilot-hosted target is bounded by a
whole-pass AI-credit ceiling, kept strictly apart from USD.

**DoR:** 041-02 DONE.

**Acceptance Criteria (sketch):**

1. `heartbeat.py run --host copilot --credit-ceiling N` forwards the host and
   the remaining whole-pass credits to each dispatched loop.
2. `outcome` records `credits` (number or `null`). A `null` is never summed as
   0: it stops the pass with rc=2 and the remaining candidates stay `open`.
3. A whole-pass ceiling sums only outcomes in its own unit. An inbox pass that
   would mix USD and credit outcomes under one ceiling refuses with rc=2.
4. With no `--host copilot`, heartbeat behaviour is byte-identical.

**DoD:** ACs pass; docs updated; reviews.

**Anti-horizontal-phasing check:** an unattended Copilot heartbeat stops at a
credit budget the user set, across all the findings it dispatches.

### Deviation log

- **Unit discriminator = presence of the `credits` key.** `_outcome_is_credit_unit`
  keys on the key's presence (a Copilot loop summary and the host-aware
  `_env_error_outcome` always carry it; a USD outcome never does). `_outcome_credits`
  returns `None` for null/missing/non-numeric and **never clamps to 0** (contrast the
  USD `_outcome_cost_usd`), so an unknown credit spend halts the pass.
- **Under copilot each loop gets an explicit `--max-iterations`** (default 5 when the
  user gave none), because `loop.py` requires it under `--host copilot` (041-02).
- **`--cost-ceiling`-refusal heuristic under copilot** uses `!= DEFAULT` (argparse
  cannot distinguish an omitted default from an explicit `--cost-ceiling 2.0`). Inert:
  `run_heartbeat` passes `whole_cost_ceiling=None` under copilot, so a USD ceiling can
  never be enforced on a Copilot pass — the missed error string is cosmetic, not a
  budget hole (independent review).
- **Asymmetric baselines (latent note).** `_spent_credits` is unit-filtered;
  `_spent_cost_usd` is not (preserving AC4 byte-identical parity). Safe because credit
  outcomes carry `cost_usd: 0.0` and the per-pass `since` filter excludes prior-pass
  outcomes — both directions verified no cross-unit contamination (independent review).
- **Tests** drive the ledger via an in-process `_dispatch_credits_inproc` helper (the
  REAL `run_dispatch` + real `gate.py` + a faithful mock `loop.py`, over a real git
  target) because `run`'s discover mints nondeterministic finding-ids; the `run` CLI +
  unit guards are still exercised end-to-end through the real subprocess.

### Reconciliation sweep

- **Code:** `skills/heartbeat/heartbeat.py` — the credit path is gated behind
  `host == HOST_COPILOT` / `whole_credit_ceiling is not None`; the Claude/USD path is
  byte-identical (the 243-test baseline is preserved; full repo suite 2744 passed).
- **Tests:** `skills/heartbeat/test_heartbeat.py` (+16, 259 total) cover all four ACs
  (forwarding, record+null→halt+open, mixed-unit→refuse, below-floor halt, claude
  byte-identical) + the five CLI guards.
- **Reviews:** independent `jig:reviewer` compliance **pass** + craft **pass** — "no
  fail-open, under-count, or unit-mix path." The one actionable nit (module `Usage:`
  docstring + slice list) is fixed.
- **Docs:** heartbeat `SKILL.md` (Copilot `--host`/`--credit-ceiling` surface +
  example + Q&A); host packages regenerated (`--check` in sync).
- **Contract surface:** the `outcome.credits` field is additive (ADR-0010 reserved
  shape); the Claude outcome is unchanged (no `credits` key).
