---
status: DRAFT
dependencies: [adr-0034]
last_verified:
frame_review: true
---

## Slice 029-02 — subagent-advisory

**Goal:** Add a `subagent` judge transport that runs the real vision judge via the
orchestrating session over the real captured shot, shipped as a **loud, non-frozen
advisory** reached only through an explicit non-oracle command — with the oracle
entrypoint returning `env_error` for subagent transport so it can never be consumed
as a gating score, a loud stderr advisory, and a self-reported (not attested) model
in the ledger.

**DoR:**
- ✅ [ADR-0034](../../decisions/adr-0034-design-eval-subagent-judge-transport.md)
  Accepted.
- ✅ Probe done: the judge-request/response channel shape chosen (ADR-0034 OQ1 —
  request/response file pair under the eval dir vs an MCP/stdout protocol), and the
  "no orchestrator present → fail closed without hanging" detection demonstrated
  (Assumptions).
- ✅ Motive demand noted (ADR-0034 Assumptions): record whether desktop-app
  design-eval demand is read-shaped or gate-shaped before building; if
  overwhelmingly gate-shaped, escalate that api/cli reachability is the real need.

**Acceptance Criteria:**

1. **An explicit non-oracle advisory command runs a real subagent judge over the
   real shot.** A `design_eval.py advisory <target>` (or equivalent) path, under
   `judge.transport: subagent`, emits the judge request (two PNG paths + scoring
   instruction) and consumes the session-supplied score. A test drives it through a
   stubbed channel and asserts a real per-shot read is produced.
2. **The oracle entrypoint refuses subagent transport with `env_error`,
   regardless of attendance.** `score.py` invoked as the oracle component under
   `judge.transport: subagent` prints **no stdout composite** and returns
   `env_error` (rc 2) whether or not a session is present — so `oracle.sh` (and the
   attended `/servo:agent-loop` gate) treats it as a missing component and can never
   consume a subagent number. The discriminator is the **entrypoint**, not
   attendance. Tested for both attended and unattended.
3. **A loud stderr advisory + self-reported (not attested) model on every subagent
   run.** The advisory read prints "SUBAGENT JUDGE — self-reported model, an
   advisory read, NOT a verified frozen score" to stderr; the ledger records
   `judge.transport: subagent` and the model labelled **self-reported**, never as
   attestation. Tested.
4. **Fails closed unattended without hanging.** In an unattended context (no
   session channel), the advisory path itself fails closed to `env_error` within a
   bounded wait — never a hang, never a silent 0.0. Tested with the channel absent.
5. **`SERVO_DESIGN_EVAL_FAKE_SCORES` stays a separate test/offline hook.** The
   subagent transport does not reuse or resemble the fake hook; a subagent run is
   distinguishable (real judge + advisory marking) from a fake-scores run. Tested.

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Tests mutation-checked — especially AC2 (entrypoint refusal) and AC4
      (fail-closed), the two guards whose failure would revive the incentive
      migration or hang a run. Host packages rebuilt + drift clean.
- [ ] Implementation + craft review passed. Set `arch_review: true` — this slice
      adds a judge transport and a new non-oracle entrypoint (a boundary change).
- [ ] Deviation log + reconciliation sweep produced.

**Assumptions:**
- The session can run a vision-capable subagent returning a numeric score
  (grounded by the field report; the concrete channel is probed in DoR).
- "No orchestrator present" is detectable without a hang or silent degrade
  (retired by the DoR probe; if not, ADR-0034 Kill criteria shelves the transport).
- The self-reported model is **not** relied on as verification — the advisory
  framing assumes it is unverifiable, so honesty rests on the loud marking, not on
  attestation trust (ADR-0034 §1).

**Anti-horizontal-phasing check:** After this slice, a developer in the Claude
Desktop app (no api/cli judge) can get an honest, real-judge fidelity read to steer
by — loudly marked non-frozen and structurally unable to be consumed as a gate —
removing the incentive that drove the field-report injection, for the authoring use.

### Deviation log (after reconciliation)

_TODO at reconciliation._

### Reconciliation sweep

_TODO at reconciliation._
