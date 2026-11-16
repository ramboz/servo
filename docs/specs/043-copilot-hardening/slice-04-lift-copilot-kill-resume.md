---
status: DONE
kind: feature
dependencies: [adr-0048, 041-02, 043-03]
last_verified: 2026-11-15
arch_review: false
frame_review: true
---

## Slice 043-04 — lift the Copilot kill-resume fail-closed

**Goal:** Let `loop.py --resume` resume a Copilot run that halted on an
**interrupt or kill** — the case 043-03 fail-closed — by recovering the sound
credit baseline from the **resumed session's own first usage read** instead of
the stale persisted `cumulative_credits_nano`. 043-03 refuses an interrupt/kill
resume because the interrupt checkpoint finalizes *before* the credit
accumulation and a killed invocation writes no usage file (ADR-0048 A3), so the
persisted baseline is a stale lower bound (the in-flight iteration's spend is
orphaned). The **resume-after-kill billed probe**
([`evidence/resume-after-kill/`](evidence/resume-after-kill/README.md), merged
2026-11-14) removed the empirical blocker: a SIGKILL'd Copilot session, when
`copilot --resume`d, reports a session-cumulative `totalNanoAiu` (**R**) that
carries the orphaned pre-kill spend **exactly** (`R − N = P`, zero residual;
same `conversation.id`; `aiCreditsStatus == complete`). So on an interrupt/kill
resume the resumed read **R** is exactly the sound session-cumulative servo
needs, and the invocation's OpenTelemetry Σ (**N**) is the honest iteration
spend — the ADR-0048 A2 / 041-01 model. This slice **narrows** 043-03's
`_COPILOT_RESUMABLE_HALTS` fail-closed guard to admit the recoverable
interrupt/kill case (`interrupted` / `""`, each of which carries a sound stale
baseline `B`), recovering baseline `= R` on the first resumed iteration and
**keeping fail-closed as the fallback** when the resumed read is missing/partial
(`aiCreditsStatus != "complete"` / absent `totalNanoAiu` / absent OTel Σ), the
`--resume` invocation errors / the session is unresumable, **or the resumed
session cannot be confirmed to be the orphaned one** — the fork-fresh guard
`R − N ≥ B` (see `## Decisions needed`). The guard is narrowed, not removed.

**DoR:**
- ADR-0048 is Accepted; part 1 persists `cumulative_credits` / `credit_ceiling`,
  A2 establishes the session-delta accounting (`totalNanoAiu` is
  session-cumulative; `--max-ai-credits` is invocation-scoped), and A3 records
  that a killed invocation writes no usage file. ✓
- Spec 041-02 is DONE — the credit brake, the persisted credit state, and the
  session-delta reconciliation all ship. ✓
- Spec 043-03 is DONE — the same-backend Copilot resume, the
  `_COPILOT_RESUMABLE_HALTS` allow-list, and the `credit_baseline_unavailable`
  fail-closed guard this slice narrows all ship. ✓
- The resume-after-kill grounding is on `main` (evidence + GROUNDED
  refinement-todo item); the probe's verdict (R carries the orphan exactly) is
  the empirical basis for AC1/AC2. ✓

**Acceptance Criteria:**

1. A Copilot `--resume` of a run that halted on a **recoverable interrupt/kill
   reason** — `interrupted` (trapped SIGINT/SIGTERM) or `""` (the kill signature
   a SIGKILL of `loop.py` leaves mid-run) — **whose persisted `current_session_id`
   names a resumable session AND whose persisted baseline is a sound non-negative
   integer** is no longer unconditionally refused `credit_baseline_unavailable`.
   It proceeds, deferring the credit baseline to the first resumed iteration,
   which recovers it from the resumed session's usage read `R`.
   `credit_usage_unavailable` (a killed worker / ADR-0048 A3 empty-usage case)
   stays fail-closed: it always nulls its baseline, so it carries no sound lower
   bound to anchor the fork-fresh guard (AC3) — lifting it is deferred
   (refinement-todo).
2. On the first resumed iteration of such a run, when the resumed read is
   complete (`aiCreditsStatus == "complete"`, a valid integer `totalNanoAiu`
   `R`, and a parseable OTel Σ `N`): the iteration's recorded spend is the
   **invocation OTel Σ (`N`)**, and the cumulative credit total is set to the
   **authoritative session-cumulative `R`** — not `R − stale_persisted` (which
   would break the per-call reconciliation) and not `stale + N` (which would
   under-count). This mirrors the probe's `R − N = P` arithmetic: no
   double-count, no reset.
3. Fail-closed fallback preserved. The run halts `credit_baseline_unavailable`
   (fail closed, never a silent unsound resume) when, on the first resumed
   iteration, (a) the resumed read is missing/partial —
   `aiCreditsStatus != "complete"`, an absent/non-integer `totalNanoAiu`, or an
   absent/empty OTel Σ; (b) the `--resume` invocation itself errors / the session
   is unresumable; or (c) **the recovered prior `R − N` is not positive, or falls
   below the persisted stale baseline `B`** — the **fork-fresh guard**
   (`R − N > 0 and R − N ≥ B`): a `copilot --resume` that silently starts a
   *fresh* session (e.g. the id expired during a long sleep) returns a complete,
   truthful read of the *wrong* session with `R = N` (`R − N = 0`), which servo
   cannot otherwise detect (the session id is not in Copilot's event stream); the
   `> 0` clause rejects that signature even when `B == 0`. A recoverable halt whose persisted
   `current_session_id` is empty (unreachable session) **or whose persisted
   baseline is not a sound non-negative integer** (no floor to anchor the
   fork-fresh guard) is refused at **preflight** with the same reason.
4. Every ADR-0048 guarantee holds on the **recovered** baseline exactly as on a
   fresh run, from the point of recovery onward: the post-iteration ceiling halt
   (`credit_ceiling_reached` when the recovered cumulative `R` exceeds the
   ceiling) and the next iteration's ≥ 30-credit pre-iteration floor both read
   the recovered `R`. (The *first resumed* iteration's pre-iteration cap is
   computed from the best available persisted lower bound before `R` is knowable
   — a deliberately generous one-shot cap that the per-invocation
   `--max-ai-credits` safety net still bounds; `R` is unknowable until that
   invocation returns. See `## Assumptions` A2.)
5. The clean-halt resume path (043-03) is unchanged: a resume from a
   `_COPILOT_RESUMABLE_HALTS` reason (iteration cap, credit ceiling, plateau,
   context) still resumes via the persisted `cumulative_credits_nano`, still
   requires it to be a sound non-negative integer (AC5 value check), and never
   enters the recovery path.
6. The `backend_mismatch` narrowing (043-03) is untouched: resuming across a
   genuine backend change (a copilot run as claude, or a claude run as copilot),
   and the September `state_schema_version == 2` prototype, stay refused
   `backend_mismatch` before the credit guard runs.

**DoD:** ACs pass with tests (TDD, witnessed red→green); compliance + craft
reviews; frame-critique (`frame_review: true`) — the load-bearing premise is
that the resumed read is reliably authoritative on the *first* resumed iteration
**and** the fail-closed fallback catches every case where it is not (the probe
grounded the happy path at n=1 and explicitly flagged unresumable-kill sessions,
so fallback coverage is what the frame-critique must scrutinize); **no arch
review** — a capability extension within ADR-0048 that changes no module
boundary or public contract (frontmatter declares `arch_review: false`, like
043-03); host-sync gate green (loop.py vendored byte-identical to the three host
trees); reconciliation sweep + deviation log;
[`docs/refinement-todo.md`](../../refinement-todo.md) resume-after-kill item
(currently GROUNDED) marked **RESOLVED by 043-04**.

**Anti-horizontal-phasing check:** a user's Copilot run is interrupted (Ctrl-C /
slept machine) or killed mid-iteration; its in-flight spend is orphaned on the
billing session, so servo's persisted baseline is a stale lower bound. Before
this slice, `loop.py --resume` refuses it `credit_baseline_unavailable` and the
user must restart fresh, re-spending the budget. After this slice,
`loop.py --resume --credit-ceiling C --max-iterations N` picks it up: the first
resumed iteration reads the resumed session's own cumulative `R` (which carries
the orphaned spend — probe-grounded), recovers the baseline to `R`, records the
iteration's honest OTel spend, and continues under the credit ceiling exactly as
a fresh run — the resume path now works end to end for an interrupt/kill-halted
run, as it already does for a cleanly-halted one (043-03). When the resumed read
is missing/partial or the session is unresumable, the run still fails closed
(not silently mis-accounted), so the budget contract holds in both branches.

## Decisions needed

- **Is the resumed read `R` reliably authoritative on the *first* resumed
  iteration, and does the fail-closed fallback catch every case where it is
  not?** This is the slice's load-bearing premise and the frame-critique's
  focus. The probe grounds the *positive* half at n=1: a SIGKILL'd session,
  resumed, reports `R` carrying the orphaned pre-kill spend exactly (`R − N = P`,
  `aiCreditsStatus == complete`), and it is robust to kill *timing* — a kill
  mid-call makes the OTel lower bound `P` an under-estimate, but `R` (the
  server-side cumulative) still carries that spend, so recovery via `R` stays
  sound regardless of when the kill landed. The probe explicitly flags the
  *negative* half: **a kill can leave an unresumable or corrupt session** (n=1
  clean resume here). The design answers the negative half structurally rather
  than by assuming it away:
  1. **Unreachable session → preflight refusal.** Recovery requires a persisted
     `current_session_id`. A kill before the first worker invocation created a
     session leaves it empty; resuming would spawn a *fresh* session and silently
     abandon the orphan, so it is refused `credit_baseline_unavailable` at
     preflight. `None` (a run that committed no iteration) is likewise **not** a
     recoverable reason.
  2. **Unresumable session (`--resume` errors) → runtime refusal.** If the
     `--resume` invocation itself errors or emits no parseable event, the first
     resumed iteration halts `credit_baseline_unavailable` — the orphan is never
     silently dropped.
  3. **Resumable but partial read → runtime refusal.** If the resumed session
     *does* resume but its first usage read is partial
     (`aiCreditsStatus != "complete"`, absent `totalNanoAiu`, or absent OTel Σ),
     recovery fails closed `credit_baseline_unavailable` — `R` is trusted only
     when the CLI's own completeness marker says it is complete.
  4. **Resumes a *fresh* session (the fork-fresh hole) → runtime refusal via the
     `R − N ≥ B` floor.** This is the load-bearing case the **frame-critique
     (R1 → R2)** surfaced: a `copilot --resume=<expired id>` may *not* error but
     instead **silently start a new conversation** (a common CLI UX, and the
     slept-machine resolution-trigger scenario is exactly when a server-side
     session expires), returning a *complete, truthful* read of the **wrong**
     session. servo cannot verify session continuity directly — the session id is
     not reliably in Copilot's event stream (`_extract_copilot_session_id`), and
     the probe's grounding used a stronger harness (pinned `--session-id` +
     verified `conversation.id`) than production's `--resume=<id>`-only path. A
     fresh session reports `R = N` for its own first invocation, so the **recovered
     prior `R − N = 0`** — the fork-fresh *signature*. The guard: recovery commits
     to `R` only when the recovered prior is **positive AND clears the persisted
     stale lower bound** `B` (`R − N > 0 and R − N ≥ B`). A genuine resume has
     `R − N = true_prior ≥ B` (B is a lower bound; the orphan only adds to it),
     always `> 0` when there was real prior spend; a fork-fresh has `R − N = 0`,
     rejected by the `> 0` clause **directly** — so it is caught even in the
     `B == 0` corner (a prior iteration that accounted to a 0 cumulative, which the
     code admits via a 0-nano `chat` span), where the floor `≥ B` alone would
     degenerate to `≥ 0` and admit it. This is the clean path's
     `expected = R − prior` reconciliation re-used as a *floor* (`≥`, accommodating
     the orphan) plus a positivity guard on the fork-fresh signature. The floor
     half requires a **sound `B`**, which is why `credit_usage_unavailable` (always
     a null baseline) is **not** recoverable (next bullet). `B` is persisted
     *before* the orphaned iteration, so it cannot itself be forged by the
     fork-fresh read. The only genuine resume the `> 0` clause refuses is the
     degenerate `B == 0` + zero-orphan case, where the true prior is 0 and there is
     nothing to recover — a harmless fail-closed.
  So the recovery path commits to `R` **only** when the session resumed, a
  complete read was obtained, a per-invocation OTel Σ was parsed, **and the
  recovered prior is positive and clears the stale baseline floor**; every other
  branch is the same fail-closed refusal 043-03 already shipped.

  **Resolved (frame-critique R1 → R2):** R1 found that committing to `R` on any
  complete read silently under-counts when `--resume` forks fresh (the `R − N ≥ 0`
  guard a fresh session trivially satisfies), directly violating A3 — a class of
  runs 043-03 kept fail-closed-safe. R2 confirmed the `R − N ≥ B` floor closes
  that for every reachable `B > 0` state, but showed the `B == 0` corner (a
  completed iteration that accounted to a 0 cumulative — code-reachable, not
  structurally forbidden) still admitted the fork-fresh signature. **Closed
  structurally** by adding the `R − N > 0` clause, which rejects the fork-fresh
  signature `R == N` itself regardless of `B` (plus restricting the recoverable
  set to halts carrying a sound `B`, deferring `credit_usage_unavailable`). So no
  reachable state silently under-counts — A3's absolute now holds. No billed probe
  of the expired-session CLI behaviour is needed: the guard is sound whether
  `--resume` errors (caught by #2) or forks fresh (caught by #4).

- **Which halt reasons are recoverable, and which stay refused?** The recoverable
  set is exactly the interrupt/kill signatures that (a) orphan in-flight spend,
  (b) leave a resumable session, and (c) carry a **sound non-negative-int stale
  baseline `B`** to anchor the fork-fresh floor: `interrupted` (trapped
  SIGINT/SIGTERM — the resolution-trigger case; the checkpoint finalizes the last
  clean cumulative) and `""` (the per-iteration copilot `terminal_reason`
  persisted by a SIGKILL of `loop.py` between an iteration's atomic state write —
  which stamps the accumulated cumulative — and the clean finalize that would
  overwrite it; 043-03's representative kill signature; ≥ 1 committed iteration ⇒
  a session exists AND `B` was persisted). Everything else stays refused exactly
  as in 043-03: the clean halts resume via the persisted baseline (AC5); `None`
  (uncommitted run — no guaranteed session) stays refused; **`credit_usage_unavailable`
  (a killed worker, ADR-0048 A3, or a partial report) stays refused because it
  ALWAYS nulls its baseline** (both the invoke-failure and the partial-report
  paths set `cumulative_credits_nano = None`), leaving no sound `B` for the
  fork-fresh floor — lifting it needs an independent session-continuity signal
  (deferred, refinement-todo); and the structural / config refusals
  (`credit_bound_unavailable`, `credit_ceiling_insufficient`, a prior
  `credit_baseline_unavailable`, `goal_resume_unsupported`, `backend_mismatch`)
  are not interrupt/kill and are untouched.

## Assumptions

- **A1 (the resumed read `R` is the sound session-cumulative of the *orphaned*
  session — when the CLI marks it complete AND the recovered prior clears the
  stale baseline).** `copilot --resume` of the orphaned session reports a
  `totalNanoAiu` that is the server-side session-cumulative total, carrying the
  pre-kill orphaned spend; grounded by the resume-after-kill billed probe
  (`R − N = P` exactly, zero residual, `aiCreditsStatus == complete`,
  kill-timing-robust). Two things could make `R` *not* the orphaned session's
  sound total, and each is guarded: (i) a non-`complete` / partial read → fail
  closed (the CLI's own completeness marker); (ii) `--resume` silently forking a
  **fresh** session → the fork-fresh guard `R − N > 0 and R − N ≥ B`
  (Decisions-needed #4) — the `> 0` clause rejects the fork-fresh signature
  `R == N` directly (sound even at `B == 0`), the floor rejects a recovered prior
  below the stale lower bound — since servo cannot verify session-id continuity
  directly. This is **not** a cryptographic or
  adversarial guarantee — every input is read from the worker-controlled worktree
  over a public read, so the honest-worker model (ADR-0049 A5) applies, identical
  to the existing per-iteration credit accounting; the slice does not widen trust
  beyond what 041-02 / 043-03 already assume. The floor is the *indirect*
  continuity check servo can perform in lieu of a session-id comparison the CLI
  does not expose.

- **A2 (the first resumed iteration's pre-iteration cap is computed before `R` is
  knowable — a bounded, one-shot looseness).** `R` is discovered only *after* the
  first resumed invocation returns, so that invocation's pre-iteration
  `--max-ai-credits` cap and ≥ 30-credit floor are computed from the persisted
  stale baseline `B` (a sound lower bound — a null baseline is now refused at
  preflight, not normalised to 0, so the full-ceiling-cap case the frame-critique
  flagged for `credit_usage_unavailable` no longer arises). For `interrupted` /
  `""` the orphan is the single in-flight iteration's spend, so the cap is loose
  by at most **one iteration's credits** (itself bounded by the per-invocation
  `--max-ai-credits` safety net), and the moment `R` is recovered the cumulative
  is exact — so the post-iteration ceiling halt and every subsequent pre-iteration
  check are exact (AC4). This is inherent to resume-after-kill: the first resumed
  invocation *is* how `R` is discovered, so "identical to a fresh run" holds from
  the recovery point onward, not for the discovery invocation that precedes it.
  The alternative — refusing until `R` is known in advance — is the 043-03 status
  quo this slice lifts.

- **A3 (recovery never widens the fail-closed surface).** The recovery path is
  reached only from a recoverable halt (`interrupted` / `""`) with a resumable
  session id AND a sound stale baseline; every not-recovered branch (unreachable
  session, unsound baseline, `--resume` error, partial read, **fork-fresh — a
  non-positive OR below-floor recovered prior**) halts with the *same*
  `credit_baseline_unavailable` reason 043-03 ships. So the change is strictly
  additive to the set of runs that *proceed* soundly; no run that 043-03 accepted
  is now refused, and — with the two-part fork-fresh guard `R − N > 0 and
  R − N ≥ B` (frame-critique R1 → R2, the `> 0` clause closing the `B == 0`
  corner) — **no reachable run that would silently under-count is now accepted**
  (within A1's honest-worker model, ADR-0049 A5: an honest fork-fresh resets its
  billing accumulator and so reports `R == N`, always caught; an *adversarial*
  worker forging telemetry is explicitly out of model, as for all of
  041-02 / 043-03's credit accounting).

### Deviation log (after reconciliation)

The six ACs are preserved. The frame-critique (R1 → R2 → R3) drove two
**material, convergent narrowings** of the recovery contract, both recorded below;
the Goal / ACs / `## Decisions needed` / `## Assumptions` were updated to match.

Review rounds (a fresh `general-purpose` reviewer per pass):
- **Compliance: R1 PASS, R2 PASS** (no `[blocker]`). R2 re-verified all six ACs on
  the narrowed code; both floor tests non-vacuous; host-sync byte-identical; ruff
  py39 clean; 643-passed baseline.
- **Craft: R1 PASS, R2 PASS** (no `[blocker]`). R1 folded nit #1 (the renamed
  non-recoverable test restored its `state unchanged on refusal` assertion); R2's
  two nits (pop the one-shot flag on the runtime fail-closed paths; comment the
  defensive `or 0`) were folded in the final code.
- **Frame-critique: R1 needs-changes → R2 needs-changes → R3 PASS** — two
  load-bearing blockers, each fixed:
  - **R1 (fork-fresh under-count):** the recovery path committed to the resumed
    read `R` on any `aiCreditsStatus == "complete"` read, guarded only by
    `R − N ≥ 0`. A `copilot --resume=<expired id>` that *silently forks a fresh
    session* (plausible CLI UX; the slept-machine resolution-trigger case is
    exactly when a server-side session expires) returns a complete, truthful read
    of the WRONG session with `R = N`, so `R − N = 0 ≥ 0` passed and the orphaned
    pre-kill spend was silently dropped → budget under-count. servo cannot verify
    session continuity (the id is not in Copilot's event stream;
    `_extract_copilot_session_id`), and the probe (n=1, resumable session, pinned
    `--session-id`) did not ground the expired-session case. Fixed by the
    **`R − N ≥ B` floor** (re-using the clean path's `expected = R − prior`
    reconciliation as a floor, accommodating the orphan), narrowing the recoverable
    set to `{interrupted, ""}` (both carry a sound stale baseline `B`), and
    requiring a sound `B` at preflight. `credit_usage_unavailable` left the
    recoverable set (it always nulls its baseline — no `B`) and is deferred
    (refinement-todo).
  - **R2 (the `B == 0` corner):** the `R − N ≥ B` floor closes R1 for every
    reachable `B > 0`, but degenerates to `R − N ≥ 0` when `B == 0` — a completed
    iteration that accounted to a 0 cumulative is code-reachable (a 0-nano `chat`
    span makes OTel Σ = 0, `expected = 0` is accepted, `baseline_sound` admits 0),
    so a fork-fresh (`R − N = 0`) slipped through at `B == 0` (bounded to one
    iteration, near-unreachable, but the spec certified total closure). Fixed
    **structurally** by adding the `R − N > 0` clause: the guard is now
    `R − N > 0 and R − N ≥ B`, which rejects the fork-fresh signature `R == N`
    itself regardless of `B`. The only genuine resume it refuses is the degenerate
    `B == 0` + zero-orphan case (nothing to recover — harmless).
  - **R3 PASS:** confirmed the `> 0` clause closes the `B == 0` corner at every
    baseline (direct probe: run-a's `R == N` → `credit_baseline_unavailable` at
    `B ∈ {0, 1, 50cr}`), introduces no spurious refusal of a genuine resume, and
    that A3's "no reachable run silently under-counts" now holds.
- **No arch review** — a capability extension within ADR-0048, no module boundary
  or public-contract change (`arch_review: false`, like 043-03).
- Reconciliation is a separate independent gate over this deviation log; by ADR-0014
  its verdict is its own review-evidence file (sweep row below), not restated here.

Load-bearing choices made during implementation:

1. **Recover from the resumed read `R`, not the stale persisted baseline.** On the
   first resumed iteration of an `interrupt`/`""` halt, `_copilot_iteration_nano`
   `recover` mode trusts the two independently-authoritative readings the probe
   grounded — the session-cumulative `totalNanoAiu` (`R`) and the per-invocation
   OTel Σ (`N`) — recording `N` as the iteration spend and setting
   `cumulative_credits_nano = R` absolutely (the probe's `R − N = P`). This is the
   lift the resume-after-kill probe recommended.

2. **The fork-fresh guard `R − N > 0 and R − N ≥ B` is the session-continuity check
   servo CAN perform.** servo cannot compare session ids (not in the event stream),
   so it reconciles the recovered prior against the persisted stale lower bound. A
   genuine resume has `R − N = true_prior ≥ B > 0`; a fork-fresh has `R − N = 0`,
   caught by the `> 0` clause at any `B`. This re-uses the clean path's
   reconciliation as a floor plus a positivity guard — no new trust surface beyond
   the honest-worker model (ADR-0049 A5) 041-02 / 043-03 already assume.

3. **Narrowed recoverable set `{interrupted, ""}`; `credit_usage_unavailable`
   deferred.** The floor needs a sound `B`; `credit_usage_unavailable` always nulls
   its baseline (both the invoke-failure and the `_apply` partial-report paths), so
   it carries no floor and stays fail-closed (deferred — refinement-todo). `None`
   (no committed iteration) stays refused.

4. **Recovery requires a persisted `current_session_id` (preflight).** Without one
   the orphaned billing session is unreachable and a fresh invocation would silently
   abandon it, so it fails closed at preflight — distinct from the unsound-baseline
   refusal.

5. **The distinct `credit_baseline_unavailable` reason threads through every
   recovery fail-closed branch** (preflight no-session / unsound-baseline; runtime
   partial-read / missing-OTel / fork-fresh / unresumable-invoke), kept separate
   from the normal-path `credit_usage_unavailable` via the
   `halt_reason = credit_error or REASON_CREDIT_USAGE_UNAVAILABLE` seam.

6. **The clean-halt resume path (043-03) is untouched (AC5).** Clean halts
   (`_COPILOT_RESUMABLE_HALTS`) still resume via the persisted baseline with the
   `expected = R − prior` *equality* reconciliation; `test_clean_halt_resume_unchanged_by_recovery_path`
   proves an orphan on a clean halt is NOT absorbed by recovery (it halts
   `credit_usage_unavailable`, as 043-03).

Noted, not changed (deviation-log record):
- **Recover mode drops the per-call `otel == R − prior` equality check for the one
  discovery iteration** (a stale prior gives no sound `expected`), trusting `N`
  under the floor only. Inherent to resume-after-kill, bounded to one iteration,
  documented in A1/A2; equality reconciliation resumes from iteration 2. (craft)
- **First-resumed-iteration pre-iteration cap looseness (A2).** `R` is unknowable
  until the invocation returns, so that one invocation's `--max-ai-credits` cap is
  computed from the stale `B`, loose by at most one iteration's orphan (bounded by
  the per-invocation cap). After recovery the cumulative is exact. (compliance)
- **`import glob` is function-local in `_simulate_kill`** — stylistic, consistent
  with the sibling `_state()` helper. (craft nit #3)
- **Split-judge × deferred-recovery is unreachable under Copilot (frame-critique
  R3 note).** A models block would make the first resumed iteration a split judge
  (`session_id_arg = None`), deferring recovery and risking an interim judge spend
  being discarded by the absolute `cumulative = R` set. But `--models` is refused
  under `--host copilot` (`test_models_refused_under_copilot`), so
  `_models_in_effect` / `split_judge` are always False and the first resumed
  iteration always resumes the session — confirmed by the compliance and craft
  passes. No change needed.
- **A3 cross-references A1's honest-worker scope (frame-critique R3 nit, folded).**
  The adversarial-worker case (forging `R = N + B + ε` to pass the guard) is
  explicitly out of model, consistent with 041-02 / 043-03's credit accounting.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `skills/agent-loop/loop.py` + 3 host copies | `updated` | Narrowed 043-03's `_COPILOT_RESUMABLE_HALTS` fail-closed guard into a three-way preflight (clean / recoverable / other); added `_COPILOT_BASELINE_RECOVERABLE_HALTS = {interrupted, ""}`; `_copilot_iteration_nano` gained a `recover` mode (trusts R + OTel Σ, enforces the `R − N > 0 and R − N >= B` fork-fresh guard); `_normalize_copilot_result` / `_invoke_copilot` / `_invoke_claude` thread `recover_baseline` + surface `copilot_baseline_recovered` / `copilot_session_cumulative_nano`; `_apply_copilot_credit_iteration` sets the cumulative to R absolutely on recovery and preserves the distinct `credit_baseline_unavailable` halt reason; recovery-pending flag cleared on every exit. Byte-identical across the three host trees (`build_host_packages.py --check` green). |
| `skills/agent-loop/test_loop.py` | `updated` | TDD (witnessed red→green): recover-mode unit tests (returns OTel Σ; floor accept-at-baseline; reject-fork-fresh; reject-fork-fresh-at-zero-baseline; reject N>R; partial / missing-OTel / missing-usage); `_apply` recovery (absolute cumulative; non-recovery unchanged); and the `CopilotCrossProcessResumeTests` e2e set (recovers to R=105cr exactly; `""` kill signature; post-iteration ceiling on recovered R; fail-closed on partial read / unresumable session / fork-fresh; clean-halt unchanged). `_simulate_kill(fork_fresh=…)` + `fail_on=` model the orphan and the fork-fresh / unresumable manifestations. Source-only. |
| `skills/agent-loop/test_copilot_capability.py` | `updated` | In-process guard tests: the 043-03 `test_interrupted_or_killed_…` was renamed to `test_non_recoverable_non_clean_halt_refuses_resume` (now refusing `None` / `credit_usage_unavailable` / structural halts, with the `state unchanged on refusal` assertion restored); new admit test (`interrupted` / `""` + session + sound baseline reach the version probe), unsound-baseline refusal, and no-session refusal. Source-only. |
| `docs/specs/043-…/slice-04-lift-copilot-kill-resume.md` | `new` | The slice: Goal / 6 ACs / DoR / DoD / anti-horizontal-phasing / `## Decisions needed` (the fork-fresh resolution R1→R2→R3) / `## Assumptions` (A1–A3) / this deviation log + sweep. Frontmatter `arch_review: false`, `frame_review: true`; walked DRAFT → … → REVIEWED → RECONCILED → DONE. |
| `docs/specs/043-…/spec.md` | `updated` | Reopened the DONE rollup for 043-04: status note, Overview, Slices list, dependencies (`+ 043-03`). |
| `docs/refinement-todo.md` | `updated` | Resume-after-kill item marked **RESOLVED by 043-04** (grounded + lifted; fork-fresh guard noted); resolution-trigger (3) extended; new **043-04 follow-up** item added for the deferred `credit_usage_unavailable` kill-resume recovery (no sound floor baseline). |
| `docs/specs/README.md` (board) | pending close-out | Regenerated by `workflow.py status-board` immediately before the DONE transition. |
| `docs/specs/043-…/reviews/slice-04-{compliance,craft,frame-critique}.md` | `new` | The three implementation-review verdicts (final round), persisted by `review.py record-review`. No arch review (`arch_review: false`). |
| `docs/specs/043-…/reviews/slice-04-reconciliation.md` | `new` (pending close-out) | The reconciliation gate's verdict, persisted once it passes. |
| `skills/quality-gate/gate.py` | `no-op` | gate.py is host-blind; the resume guard + credit recovery live only in loop.py's resume path. |
| `docs/decisions/adr-0048-*.md` | `no-op` | A capability extension within ADR-0048 (credit unit, session-delta A2, fail-closed A3) — no ADR change. |
