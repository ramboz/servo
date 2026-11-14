---
status: DRAFT
kind: feature
dependencies: [adr-0048, 041-02]
last_verified:
arch_review: false
frame_review: true
---

## Slice 043-03 — cross-process resume of a Copilot run

**Goal:** Allow `loop.py --resume` to resume a persisted run whose
`backend == copilot`. Today the `backend_mismatch` guard refuses to resume any
run whose `backend != claude`, so an interrupted Copilot run restarts fresh and
re-spends its budget — even though its `cumulative_credits_nano` and
`credit_ceiling` already persist in `state.json`. This slice narrows the guard
to allow a same-backend Copilot resume, relying on the persisted session-delta
credit accounting (ADR-0048 A2 / the bug-007 pattern) that already handles
intra-run accounting.

**DoR:**
- ADR-0048 is Accepted; part 1 persists `cumulative_credits` / `credit_ceiling`,
  and A2 establishes the session-delta accounting (`totalNanoAiu` is
  session-cumulative; `--max-ai-credits` is invocation-scoped). ✓
- Spec 041-02 is DONE — the credit brake, the persisted credit state, and the
  `backend_mismatch` guard all ship.

**Acceptance Criteria:**

1. `loop.py --resume` resumes a persisted run when `state.json` records
   `backend == copilot`, not only `backend == claude`. The `backend_mismatch`
   guard refuses only a genuine backend *change* (resuming a copilot run as
   claude, or a claude run as copilot), not a same-backend copilot resume.
2. On resume, the credit brake re-establishes its session-snapshot baseline from
   the persisted `cumulative_credits_nano`, so the first resumed iteration's
   per-iteration cost is `new session-cumulative totalNanoAiu − persisted
   baseline` (ADR-0048 A2), and the cumulative total continues from where the
   interrupted run halted — no double-counting and no reset to zero.
3. A resumed Copilot run keeps every ADR-0048 guarantee: the ≥ 30-credit
   pre-iteration halt (`credit_ceiling_reached`), the post-iteration ceiling
   halt, and fail-closed on missing or partial telemetry
   (`credit_usage_unavailable`) — identical to a fresh Copilot run.
4. Resuming across a genuine backend change stays refused with the existing
   `backend_mismatch` reason: the guard is narrowed, not removed.
5. If a Copilot `--resume` cannot soundly re-establish the session baseline (see
   `## Decisions needed`), the run fails closed rather than resuming with an
   unsound credit total.

**DoD:** ACs pass with tests (TDD, witnessed red); compliance + craft reviews;
frame-critique (`frame_review: true`); **no arch review** — a capability
extension within ADR-0048 that changes no module boundary or public contract
(frontmatter declares `arch_review: false`); host-sync gate green (loop.py
vendored to the three host trees); reconciliation sweep + deviation log;
`docs/refinement-todo.md` item 3 marked resolved.

**Anti-horizontal-phasing check:** a user's Copilot run is interrupted (terminal
closed, machine slept) and `loop.py --resume` picks it up with its credit total
intact, instead of restarting fresh and re-spending the budget — the resume path
works end to end for Copilot, as it already does for Claude.

## Decisions needed

- **Does the persisted baseline represent the session-cumulative total across a
  process boundary?** ADR-0048 A2 establishes that *within* a run the brake
  diffs from a session snapshot. A cross-process resume spawns a fresh `loop.py`
  **and** a fresh `copilot --resume` of the same session; the resumed session's
  usage file reports session-cumulative credits (including pre-interruption
  spend). For AC2 to hold, the persisted `cumulative_credits_nano` must be
  exactly that session-cumulative value at halt, so
  `delta = new_cumulative − persisted` is correct. If servo instead persisted an
  invocation-local total, a cross-process resume would under- or double-count.
  The refinement-todo asserts "the intra-run session-delta already handles the
  accounting"; this slice must **verify** the persisted field is
  session-cumulative — a read of 041-02's state schema, ideally plus a
  cross-process resume probe — rather than assume it. Within ADR-0048's
  accounting model (not ADR-shaped), but a real correctness premise the
  frame-critique and implementation settle before relying on it; AC5 is the
  fail-closed fallback if it does not hold.

## Assumptions

- **A1 (session identity survives a cross-process resume).** `copilot --resume`
  resumes the *same* billing session, so its usage file's `totalNanoAiu` stays
  session-cumulative across the process boundary and the persisted baseline
  stays valid. Partly grounded by ADR-0048 A2 (verified session-cumulative on
  `--resume` within the 041-01 probe); unverified specifically for a
  servo-persisted, servo-relaunched cross-process resume. If a cross-process
  `copilot --resume` instead starts a new billing session (resetting
  `totalNanoAiu`), the session-delta accounting breaks and this slice's premise
  fails — the load-bearing claim the frame-critique tests.
