---
status: DONE
dependencies: [adr-0034]
last_verified: 2026-08-27
frame_review: true
arch_review: true
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
- [x] All ACs pass; full test suite green (164 tests).
- [x] Tests mutation-checked — the entrypoint gate (AC2) and self-reported-model
      go red when neutered; AC4 fail-closed is non-vacuous by construction (a
      broken deadline hangs the `timeout=0` test). Host packages rebuilt + drift clean.
- [x] Implementation + craft review passed; `arch_review: true` arch pass passed.
- [x] Deviation log + reconciliation sweep produced.

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

1. **New non-oracle `advisory` subcommand + `advisory_read()`.** The subagent judge
   is reached ONLY via `design_eval.py advisory` (which prints a labelled
   `ADVISORY (subagent, non-frozen): …`, never a bare pipeable float). The oracle
   `score.py` path refuses subagent transport at the entrypoint. `arch_review: true`
   arch pass passed (non-gating is structural, advisory path cleanly outside the
   oracle seam per ADR-0031/0032 §7).
2. **Craft nits folded:** malformed response *values* (non-numeric score, non-list,
   non-object) now fail closed to `EnvError` (uniform env_error surface) + tested;
   a mid-write response is tolerated (poll-until-deadline, distinct "present but
   unparseable" message) with an atomic-write (temp+rename) instruction in the
   request; a non-numeric `SERVO_DESIGN_EVAL_SUBAGENT_TIMEOUT` fails closed.
3. **Arch nit folded:** on the manual+subagent intersection the honesty tells now
   **stack** — `advisory_read` calls `_emit_honesty_advisories`, so the per-screen
   `MANUAL CAPTURE` advisory (ADR-0035 §3) fires alongside the `SUBAGENT JUDGE`
   advisory. Tested (`test_advisory_stacks_manual_capture_advisory`).
4. **fake-scores + subagent (compliance + craft note):** the subagent entrypoint
   gate lives inside `if fake is None:`, so a config with both `transport: subagent`
   AND `SERVO_DESIGN_EVAL_FAKE_SCORES` takes the loud fake path (FAKE SCORES /
   `not_captured`), not the subagent `env_error`. **Intentional/acceptable:**
   fake-scores is a separate, loudly-marked offline/test hook that supersedes
   transport resolution; no self-reported subagent number ever gates (the judge
   never runs), so AC2's honesty invariant holds. Recorded, not "fixed".
5. **Deferred (logged, not blocking — arch/craft):** (a) `score()` and
   `advisory_read()` share a capture/aggregate/ledger shape — a future refactor to a
   common helper would remove the drift surface (the paths genuinely differ today:
   `judge()` calls vs the request/response channel). (b) The channel filenames are
   fixed (`subagent/request.json` / `response.json`) with no correlation id, so two
   concurrent advisory runs in one eval dir would collide — out of scope until
   batch/parallel advisory is wanted.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Project front door untouched. |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board` at close-out (029 spec now DONE). |
| `docs/product-vision.md` | `no-op` | No behavior/scope drift. |
| `docs/architecture.md` | `deferred` | A new non-oracle `advisory` entrypoint is a second consumer of the design-eval mechanism; the arch pass judged SKILL.md (§ judge transports) the adequate doc surface at this granularity. Front-door architecture prose unchanged; revisit if design-eval's runtime section is next edited. |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / templates | `no-op` | 029 closes, but there is nothing to compress: `CLAUDE.md` carries no Active-specs entry for 028/029 (verified — no refs), and there is no `AGENTS.md`. The status board tracks the DONE state. |
| `docs/inbox.md` | `no-op` | Nothing resolved by this slice. |
| `docs/refinement-todo.md` | `updated` | Added a "design-eval subagent advisory (029-02) — two deferred robustness items" entry (shared score()/advisory_read helper; channel correlation id) so the two deferrals live in the canonical tracker, per the reconciliation review. |
| `docs/memory/**` | `no-op` | No new durable term/learning beyond the ADR/spec record. |
| `docs/decisions/README.md` / ADR index | `no-op` | No ADR touched (realizes accepted ADR-0034). |
| `skills/design-eval/SKILL.md` + `design_eval.py` | `updated` | Added the `subagent` transport + `advisory` subcommand; host packages rebuilt (drift clean). |
