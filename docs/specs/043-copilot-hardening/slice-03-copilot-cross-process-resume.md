---
status: DONE
kind: feature
dependencies: [adr-0048, 041-02]
last_verified: 2026-11-14
arch_review: false
frame_review: true
---

## Slice 043-03 — cross-process resume of a Copilot run

**Goal:** Allow `loop.py --resume` to resume a persisted run whose
`backend == copilot` **that halted cleanly** (iteration cap, credit ceiling,
plateau, or context). Today the `backend_mismatch` guard refuses to resume any
run whose `backend != claude`, so even a cleanly-halted Copilot run restarts
fresh and re-spends its budget — even though its `cumulative_credits_nano` and
`credit_ceiling` already persist in `state.json`. This slice narrows the guard
to allow a same-backend Copilot resume, relying on the persisted session-delta
credit accounting (ADR-0048 A2 / the bug-007 pattern) that already handles
intra-run accounting. A run that was **interrupted or killed** is instead
fail-closed-refused: its in-flight invocation's spend is orphaned on the billing
session (ADR-0048 A3 — a killed invocation writes no usage file), so the
persisted baseline is a stale lower bound that cannot be soundly reconciled
without a resume-after-kill probe (deferred). The frame-critique settled this
scope boundary — see `## Decisions needed`.

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
5. If a Copilot `--resume` cannot soundly re-establish the session baseline, the
   run fails closed (`credit_baseline_unavailable`) rather than resuming with an
   unsound credit total. This covers two conditions: (a) the persisted
   `cumulative_credits_nano` is null / absent / non-integer / negative; and (b)
   the run did not halt on a clean, credit-accounted terminal reason — an
   interrupted or killed run orphans its in-flight spend (ADR-0048 A3), leaving a
   stale baseline (see `## Decisions needed`).

**DoD:** ACs pass with tests (TDD, witnessed red); compliance + craft reviews;
frame-critique (`frame_review: true`); **no arch review** — a capability
extension within ADR-0048 that changes no module boundary or public contract
(frontmatter declares `arch_review: false`); host-sync gate green (loop.py
vendored to the three host trees); reconciliation sweep + deviation log;
`docs/refinement-todo.md` item 3 marked resolved.

**Anti-horizontal-phasing check:** a user's Copilot run halts at its iteration
cap (or credit ceiling / plateau / context); `loop.py --resume --credit-ceiling C
--max-iterations N` picks it up with its credit total intact and continues from
the persisted session-cumulative baseline, instead of restarting fresh and
re-spending the budget — the resume path works end to end for a cleanly-halted
Copilot run, as it already does for Claude. An interrupted or killed run is
fail-closed-refused (not silently mis-accounted), so the budget contract holds in
both branches.

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

  **Resolved (frame-critique, this slice):** the premise **holds for a CLEAN
  halt** — servo's per-iteration delta accumulation telescopes exactly to the
  session-cumulative `totalNanoAiu` at every clean iteration boundary
  (`_copilot_iteration_nano` returns `total − prior`; the run loop does
  `cumulative += delta`, so the running sum equals the last reported session
  total), and ADR-0048 A2's billed probe grounds the copilot-CLI cross-process
  session-cumulative behaviour for a cleanly-ended run. It does **not** hold at an
  **interruption**: the interrupt checkpoint finalizes and bumps `iteration_count`
  **before** `_apply_copilot_credit_iteration`, and a killed invocation writes no
  usage file (A3), so the persisted baseline **excludes the orphaned in-flight
  spend** — a stale lower bound. A resume from such a halt would make the first
  resumed iteration's `delta = new_cumulative − stale_baseline` either break the
  per-call OTel reconciliation (if the orphan reappears in `totalNanoAiu`) or
  silently under-count (if it does not), and which occurs is unverified by A2
  (resume-after-clean-end) or A3 (kill→no-usage-file, never resumed). Resume is
  therefore **scoped to clean, credit-accounted halts** (`_COPILOT_RESUMABLE_HALTS`
  = iteration cap / credit ceiling / plateau / context), and an interrupted or
  killed run **fails closed** (AC5). Two layers enforce this: an *original*
  interrupted/killed run is refused at **preflight** — it persisted a
  non-resumable `last_terminal_reason` atomically with its accounted baseline, so
  a kill cannot forge a resumable-reason + stale-baseline state. The one residual
  edge — a clean-halt run that is resumed and then itself killed *during its first
  resumed iteration*, before that iteration's atomic write — keeps the pre-resume
  resumable reason on disk and so passes preflight, but is caught at **runtime** by
  `_copilot_iteration_nano`'s session-delta reconciliation (`expected = new −
  prior < 0`, or the per-call OTel Σ ≠ the delta when the orphan reappears →
  fail-closed `credit_usage_unavailable`). So no path silently under-counts.
  Grounding resume-after-kill (to lift the preflight refusal) is deferred to a
  billed probe (refinement-todo).

## Assumptions

- **A1 (the persisted baseline is a sound session-cumulative total — true only
  for a cleanly-halted run).** `copilot --resume` resumes the *same* billing
  session, so its usage file's `totalNanoAiu` stays session-cumulative across the
  process boundary; grounded by ADR-0048 A2 (verified session-cumulative on
  `--resume` within the 041-01 probe, a resume-after-clean-end). The frame-critique
  established that the exposed failure mode is **not** session reset (A2 disproves
  that) but **baseline staleness after an interruption or kill**: credit
  accumulation runs *after* the interrupt checkpoint, and a killed invocation
  writes no usage file (A3), so the in-flight spend is **orphaned** and the
  persisted baseline is a stale lower bound. For such a run `delta = new −
  stale_baseline` either breaks the OTel reconciliation (orphan reappears) or
  under-counts the budget (it does not) — unverified by A2 (clean-end) or A3
  (kill→no-usage-file, never resumed). This slice **fails closed** on a non-clean
  halt (AC5 / `_COPILOT_RESUMABLE_HALTS`); the resume-after-kill probe that would
  ground the interrupted case is deferred (refinement-todo).

### Deviation log (after reconciliation)

The five ACs are preserved; AC5's wording was sharpened (its two fail-closed
conditions made explicit). The frame-critique drove a **material scope narrowing**
of the Goal and anti-horizontal-phasing check (from "resume an interrupted run" to
"resume a cleanly-halted run; fail-closed on interruption"), recorded below.

Review rounds (a fresh `general-purpose` reviewer per pass):
- **Frame-critique: R1 needs-changes (1 load-bearing blocker) → R2 PASS.** R1 found
  that the premise fails at the slice's own motivating halt — interruption — because
  credit accumulation runs AFTER the interrupt checkpoint (which finalizes
  `REASON_INTERRUPTED` + bumps `iteration_count` before `_apply_copilot_credit_iteration`),
  so the persisted baseline excludes the in-flight iteration's spend, which a killed
  invocation orphans on the billing session (ADR-0048 A3: no usage file). The original
  AC5 (null/absent/negative only) passed that stale-but-valid int. Fixed by the
  staleness guard + honest spec narrowing (below); R2 re-tested the narrowed clean-halt
  frame and passed.
- **Compliance + craft: PASS, no `[blocker]`** (recorded under `reviews/slice-03-*`).
  No arch review — a capability extension within ADR-0048, no module boundary or
  public-contract change (`arch_review: false`).
- Reconciliation is a separate independent gate over this deviation log; by ADR-0014
  its verdict is its own review-evidence file (sweep row below), not restated here.

Non-blocking nits folded (from compliance / craft / frame-critique):

1. **Spec framing — two-layer fail-closed (frame-critique R2).** `## Decisions needed`
   now documents that an *original* interrupted/killed run is refused at preflight
   (AC5), while the one residual edge — a clean-halt run resumed and then killed during
   its first resumed iteration — passes preflight but is caught at runtime by
   `_copilot_iteration_nano`'s session-delta reconciliation; no path silently
   under-counts.
2. **Representative kill signature (frame-critique R2).** `test_interrupted_or_killed_
   copilot_run_refuses_resume` now includes the literal `""` that a killed Copilot
   iteration leaves on disk (`_normalize_copilot_result` hardcodes `terminal_reason=""`),
   alongside `None` / `"interrupted"` / other non-progress reasons.
3. **Override comment corrected (craft).** The `credit_ceiling` resume-override comment
   dropped the misleading "direct programmatic entry … persisted ceiling stands"
   dead-path phrasing; it now states the `is not None` guard simply scopes the override
   to Copilot (the flag is mandatory + non-None there, always None under claude).
4. **Staleness refusal message widened (implementer, in response to compliance's
   pre-invocation-halt note).** Compliance observed that pre-invocation fail-closed halts
   (`credit_ceiling_insufficient` / `credit_bound_unavailable`) are also non-resumable
   despite making no spend; the staleness refusal message therefore no longer asserts
   "orphaned in-flight spend" for *every* non-resumable halt — it states the general rule
   (resume only from a clean progress halt) and notes the interrupted/killed case orphans
   spend "in particular".

Noted, not changed (deviation-log record):
- **Inherited `host`-key discriminator handling (craft).** The guard resolves the
  persisted backend from both `backend` and `host`; only `backend` is written today,
  but the `host` arm backs the documented 6-case `backend_mismatch` regression
  (hand-edited / forward-compat states), so it is kept.
- **Ceiling-less copilot resume message (craft).** A copilot `--resume` that omits
  `--credit-ceiling` is refused by the generic `_refuse_copilot_capability()` ("copilot
  needs a ceiling") rather than a resume-specific message — by design, since the ceiling
  is a required opt-in on every copilot invocation.
- **Pre-invocation fail-closed halts (compliance).** `credit_ceiling_insufficient` /
  `credit_bound_unavailable` runs are also non-resumable (not in `_COPILOT_RESUMABLE_HALTS`),
  so they are refused even though they made no resumable progress. Spec-conformant and
  fail-closed-safe; the allow-list is deliberately the four clean *progress* halts.
- **Claude-version gate on a copilot resume (surfaced during the review rounds;
  implementer-confirmed).** Enabling copilot resume newly exposes it to the resume-path
  `claude_version_mismatch` guard (claude-specific, fail-safe, `--resume-anyway`-bypassable).
  Deferred follow-up filed (refinement-todo, 043-03 follow-ups #2 — host-gate the version
  check under copilot).

Load-bearing choices made during implementation:

1. **The session-cumulative premise HOLDS for a CLEAN halt; it FAILS at an interruption
   — so resume is scoped to clean halts and fails closed otherwise (AC5).** For a clean
   halt the last iteration's spend is credit-accounted before finalization, and servo's
   per-iteration delta accumulation telescopes exactly to the session-cumulative
   `totalNanoAiu` (`_copilot_iteration_nano` returns `total − prior`; the loop does
   `cumulative += delta`), grounded by ADR-0048 A2's billed probe. At an interruption the
   accumulation is SKIPPED (interrupt checkpoint precedes it) and a killed invocation
   writes no usage file (A3), so the baseline is a **stale lower bound**. The new
   `_COPILOT_RESUMABLE_HALTS` allow-list gates resume; a non-clean halt fails closed
   (`credit_baseline_unavailable`). The premise is NOT verified unconditionally — it is
   verified for clean halts and fail-closed elsewhere.

2. **AC5 is a two-part fail-closed guard.** (a) VALUE: the persisted
   `cumulative_credits_nano` must be a non-negative int — not null (a prior fail-closed
   halt wrote null, never 0), absent, boolean, or negative. (b) STALENESS:
   `last_terminal_reason` must be in `_COPILOT_RESUMABLE_HALTS`. Both refuse
   `credit_baseline_unavailable` before any worker call or version probe, and neither is
   waivable by `--resume-anyway` (the guard is inside the `host == HOST_COPILOT` block,
   which the narrowed backend check has already proven is a true copilot→copilot resume).

3. **Defense-in-depth: the premise failing AT RUNTIME is also fail-closed.** Even if a
   stale baseline reached the loop (the resumed-then-killed edge), the existing
   `_copilot_iteration_nano` guard `if expected < 0 … REASON_CREDIT_USAGE_UNAVAILABLE`
   halts when the session-delta goes negative or the per-call OTel Σ disagrees with the
   delta (orphan reappeared). Preflight (staleness/value) and runtime (`expected < 0` /
   OTel mismatch) both fail closed — the brake never under-counts.

4. **The narrowed backend guard refuses a genuine backend CHANGE and preserves the
   September-prototype handling.** Resolves the persisted backend from the consistent
   `(backend, host)` discriminators (unmarked v1 → claude); refuses on the September
   `state_schema_version == 2` prototype, inconsistent discriminators, or
   `persisted_backend != host`. All six existing `backend_mismatch` regression cases stay
   refused; the new direction (claude run resumed as copilot) is now refused too
   (previously it slipped past the guard and would have crashed on the missing credit
   fields). The guard stays ahead of `_get_claude_version` (proven by patched-probe
   tests).

5. **A Copilot resume requires `--credit-ceiling` AND `--max-iterations`, and the credit
   flag is honored as a resume override (not silently ignored).** `main()`'s Copilot
   opt-in gate re-applies on resume (both flags mandatory — an asymmetry with a Claude
   resume, which may omit the persisted equivalents), so the required `--credit-ceiling`
   is applied as an override, symmetric with `--cost-ceiling`. The CLI validates it
   `>= 30` before `run_loop`; absent (direct programmatic entry under claude, where it is
   None) the override no-ops. This keeps 043-02's launch-gate ordering untouched and
   leaves the `test_all_launch_surfaces` no-bypass invariant green.

6. **New preflight refusal reason `credit_baseline_unavailable` (AC5)** — in the open set
   with `backend_mismatch` / `state_missing`, within ADR-0048's fail-closed accounting
   family; maps to `error` via the total A2 outcome map. No module boundary or
   public-contract change (consistent with 041-02/043-02 adding reasons within their
   slices), so no arch review.

Test-fixture note: the cross-process resume e2e uses a NON-git target (like the 003-04
resume and copilot-brake tests), so the orthogonal 031-01 edit-permission-wall relabel
does not fire and a below-threshold run halts cleanly at the iteration cap (rc=0,
`last_terminal_reason=max_iterations_reached` — a `_COPILOT_RESUMABLE_HALTS` member, so
the resume is allowed). "Real git repo" is satisfied by a REAL two-phase run→resume
producing a REAL persisted `state.json`; git is orthogonal to credit-resume behaviour.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `skills/agent-loop/loop.py` + 3 host copies | `updated` | Narrowed the `backend_mismatch` resume guard (refuse genuine change + September v2 prototype, allow same-backend copilot→copilot); added the two-part AC5 fail-closed guard (value check + `_COPILOT_RESUMABLE_HALTS` staleness check → `credit_baseline_unavailable`); added the `_COPILOT_RESUMABLE_HALTS` allow-list and `REASON_CREDIT_BASELINE_UNAVAILABLE` constants; added a `credit_ceiling` resume override (symmetric with `cost_ceiling`). Byte-identical across the three host trees (`build_host_packages.py --check` green). |
| `skills/agent-loop/test_loop.py` | `updated` | TDD (witnessed red→green): session-cumulative cross-process mock (`_mock_copilot_cumulative`) + `CopilotCrossProcessResumeTests` proving AC1/AC2 (clean-halt resume continues to 90cr exactly — not reset-to-40, not double-count-to-140), the `--resume=<session_id>` worker call (A1), AC3 (post-iteration ceiling / pre-iteration ≥30 floor / fail-closed-on-partial, all on a resumed run), and the credit-ceiling resume override. Source-only (test files never ship to host packages). |
| `skills/agent-loop/test_copilot_capability.py` | `updated` | In-process guard tests: AC4 (claude→copilot → `backend_mismatch`), AC5 value check (null/absent/bool/float/negative, isolated by a clean `last_terminal_reason`), AC5 staleness check (`test_interrupted_or_killed_copilot_run_refuses_resume` — interrupted / `""` / completed / None / other, the frame-critique's case), and AC1-allow (a sound copilot state over each clean halt reason reaches the version probe). The existing 6-case `backend_mismatch` regression stays green. Source-only. |
| `docs/specs/043-…/slice-03-copilot-cross-process-resume.md` | `updated` | Goal + anti-horizontal-phasing narrowed to clean halts (interrupted/killed fail-closed); AC5 wording made two-condition; `## Decisions needed` + `## Assumptions A1` record the frame-critique resolution (premise holds for clean halts, stale after interruption; two-layer fail-closed). Frontmatter walked DRAFT → … → REVIEWED (RECONCILED + DONE + board regen pending this gate's close-out); this deviation log + sweep appended. |
| `docs/refinement-todo.md` | `updated` | Item 3 marked **RESOLVED by 043-03, scoped to clean halts** (verified-for-clean, fail-closed-for-interrupted); resolution-trigger line marks (3) resolved; new **043-03 follow-ups** block added (resume-after-kill billed probe; claude-version host-gating). |
| `docs/specs/README.md` (board) | pending close-out | Regenerated by `workflow.py status-board` immediately before the DONE transition — not yet applied when this sweep was written. |
| `docs/specs/043-…/reviews/slice-03-{compliance,craft,frame-critique}.md` | `new` | The three implementation-review verdicts (final round, all `pass`), persisted by `review.py record-review`. No arch review (`arch_review: false`). |
| `docs/specs/043-…/reviews/slice-03-reconciliation.md` | `new` (pending close-out) | The reconciliation gate's verdict, persisted by `review.py record-review` once the gate passes — not yet written when this sweep was composed. |
| `skills/quality-gate/gate.py` | `no-op` | gate.py is host-blind; the resume guard + credit-baseline handling live only in loop.py's resume path. |
| `docs/decisions/adr-0048-*.md` | `no-op` | This slice extends the resume capability within ADR-0048 (credit unit, session-delta A2, fail-closed A3) — no ADR change. |
