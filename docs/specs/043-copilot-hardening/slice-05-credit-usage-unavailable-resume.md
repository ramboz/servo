---
status: DRAFT
kind: feature
dependencies: [043-04]
last_verified: 2026-11-16
arch_review: false
frame_review: true
---

## Slice 043-05 — recover the Copilot kill-resume baseline from a persisted sound floor

**Goal:** Let `loop.py --resume` resume a Copilot run that halted on
**`credit_usage_unavailable`** — a worker hard-killed mid-iteration (SIGKILL /
OOM) or a partial usage report — the one interrupt/kill case 043-04 left
fail-closed. 043-04 recovers `interrupted` / `""` halts by reconciling the
resumed read `R` against the persisted `cumulative_credits_nano` as a
fork-fresh floor `B`, but `credit_usage_unavailable` **nulls** that baseline at
both of its halt sites (the `_apply_copilot_credit_iteration` partial-report
path and the invoke-failure path), leaving no sound `B`. This slice persists the
**last CLEAN cumulative** as `last_sound_cumulative_nano` immediately before each
null — written **only from a sound value**, never clobbered by a subsequent null
— and sources 043-04's recovery floor from it when `cumulative_credits_nano` is
null. The recovery arithmetic, the fork-fresh guard `R − N > 0 and R − N ≥ floor`,
and every fail-closed fallback are **043-04's, reused unchanged**; only the floor
*source* changes. This is option (a) of refinement-todo item
"`credit_usage_unavailable` kill-resume recovery is deferred (spec 043-04)";
option (b) (an independent session-continuity signal) remains deferred.

**DoR:**
- Spec 043-04 is DONE — the recovery machinery this slice extends (the
  `_copilot_iteration_nano` `recover` mode, the fork-fresh guard
  `R − N > 0 and R − N ≥ floor`, the `_COPILOT_BASELINE_RECOVERABLE_HALTS`
  preflight branch, the `copilot_baseline_recovered` absolute-set in
  `_apply_copilot_credit_iteration`, and the `credit_baseline_recovery_pending`
  one-shot flag) all ship on `main`. ✓
- The resume-after-kill billed probe is on `main`
  ([`evidence/resume-after-kill/`](evidence/resume-after-kill/README.md)): the
  resumed Copilot session's `totalNanoAiu` (`R`) carries the orphaned pre-kill
  spend exactly (`R − N = P`, zero residual, `aiCreditsStatus == complete`,
  kill-timing-robust) — the same empirical basis 043-04 relies on. The
  `credit_usage_unavailable` halt this slice lifts has **two sub-cases**: the
  **invoke-failure / SIGKILL** path (`claude_data is None` — the probe's
  **direct** killed-worker scenario) and the **partial-report** path (the
  invocation returned but its usage read was incomplete). The probe grounds the
  first directly; the second's soundness rests on ADR-0048 **A2** additivity
  (`L ≤ P` — a partial report means the read was incomplete, not that the server
  un-billed; see `## Decisions needed` proof leg 2), not on the probe. Both
  resolve to the same persisted sound floor + fork-fresh guard. ✓
- ADR-0048 is Accepted (credit unit, session-delta A2, A3 "a killed invocation
  writes no usage file"); refinement-todo item 043-03 follow-up #2 records this
  case as deferred with option (a) named. ✓

**Acceptance Criteria:**

1. **Admit the recoverable `credit_usage_unavailable` halt.** A Copilot
   `--resume` of a run whose persisted `last_terminal_reason` is
   `credit_usage_unavailable`, whose persisted `current_session_id` names a
   resumable session, AND whose persisted `last_sound_cumulative_nano` is a
   **sound non-negative integer**, is no longer unconditionally refused
   `credit_baseline_unavailable` at preflight. It proceeds, deferring the credit
   baseline to the first resumed iteration (the same
   `credit_baseline_recovery_pending` defer 043-04 uses). The reachable case is a
   worker killed on iteration ≥ 2 (a prior `current_session_id` and a last-clean
   cumulative both exist); a **first-iteration** kill persists no
   `current_session_id` and stays preflight-refused (AC4(a)), unchanged from
   043-04.

2. **Recover to `R` on the first resumed iteration — 043-04's path, floor from
   the last-sound.** When the resumed read is complete
   (`aiCreditsStatus == "complete"`, an integer `totalNanoAiu` `R`, a parseable
   OTel Σ `N`) the iteration's recorded spend is the invocation OTel Σ `N` and
   the cumulative is set to the authoritative session-cumulative `R` absolutely
   (the probe's `R − N = P`) — byte-identical to 043-04's recovery. The only
   difference from 043-04 is that the fork-fresh guard's floor is sourced from
   the sound `last_sound_cumulative_nano` `L` (because `cumulative_credits_nano`
   is null here), so the guard is `R − N > 0 and R − N ≥ L`.

3. **Persist `last_sound_cumulative_nano` only from a sound value, at both null
   sites; never clobber it with a null.** Immediately before each site that sets
   `state["cumulative_credits_nano"] = None` on a Copilot halt (the
   `_apply_copilot_credit_iteration` partial-report path and the invoke-failure
   path), if the current `cumulative_credits_nano` is a sound non-negative
   integer, copy it to `state["last_sound_cumulative_nano"]`; otherwise leave the
   existing `last_sound_cumulative_nano` untouched. A second null with no clean
   iteration between (e.g. a failed recovery invocation re-nulling an
   already-null cumulative) must **not** overwrite the genuine floor. The field
   is added to the Copilot state scaffold next to `cumulative_credits_nano`;
   absent ⇒ treated as unsound. On recovery success the floor is retired (popped)
   alongside the one-shot `credit_baseline_recovery_pending` flag (state
   hygiene).

4. **Fail-closed fallbacks preserved.** The run refuses
   `credit_baseline_unavailable` when, for a `credit_usage_unavailable` halt:
   (a) the persisted `current_session_id` is empty/absent (preflight — the
   orphaned session is unreachable, distinct from the no-floor refusal);
   (b) `last_sound_cumulative_nano` is not a sound non-negative integer
   (preflight — no floor to anchor the fork-fresh guard); or (c) on the first
   resumed iteration the resumed read is missing/partial, the `--resume`
   invocation errors / the session is unresumable, or the recovered prior
   `R − N` fails the guard — `R − N ≤ 0` (the fork-fresh signature `R == N`,
   rejected directly so it is caught even at `L == 0`) or `R − N < L` (a
   positive-but-below-floor wrong read). These are 043-04's exact runtime
   branches; only the floor source differs.

5. **Every ADR-0048 guarantee holds on the recovered baseline, and the
   pre-iteration cap no longer crashes on the null baseline.** The first resumed
   iteration's pre-iteration `--max-ai-credits` cap and ≥ 30-credit floor are
   computed from the sound `last_sound_cumulative_nano` (the best persisted lower
   bound before `R` is knowable — a deliberately generous one-shot cap bounded by
   the per-invocation `--max-ai-credits` safety net), because
   `cumulative_credits_nano` is null and arithmetic against it would otherwise
   raise. From the recovery point onward the cumulative is `R` exactly, so the
   post-iteration ceiling halt (`credit_ceiling_reached` when `R` exceeds the
   ceiling) and every subsequent pre-iteration check are exact, identical to a
   fresh run (043-04 A2, re-used).

6. **Scope discipline.** The 043-04 `interrupted` / `""` recovery path,
   `_COPILOT_RESUMABLE_HALTS`, `_COPILOT_BASELINE_RECOVERABLE_HALTS`, and the
   043-03 clean-halt resume path are untouched — this slice only ADDS a parallel
   `credit_usage_unavailable` preflight branch and the last-sound plumbing. The
   structural / config refusals (`None` — an uncommitted run with no guaranteed
   session; `credit_bound_unavailable`; `credit_ceiling_insufficient`; a prior
   `credit_baseline_unavailable`; `backend_mismatch`; `goal_resume_unsupported`)
   stay fail-closed. Option (b) (a session-continuity signal) remains a deferred
   future simplification (refinement-todo).

**DoD:** ACs pass with tests (TDD, witnessed red→green); compliance + craft
reviews; frame-critique (`frame_review: true`) — the load-bearing premise is
that `last_sound_cumulative_nano`, whenever used as the floor, is a sound
non-negative integer ≤ the true pre-halt session-cumulative `P`, so the
fork-fresh guard is as sound on the last-sound floor as 043-04's is on `B`;
**no arch review** — a capability extension within ADR-0048 that changes no
module boundary or public contract (`arch_review: false`, like 043-03 / 043-04);
host-sync gate green (loop.py vendored byte-identical to the three host trees);
reconciliation sweep + deviation log;
[`docs/refinement-todo.md`](../../refinement-todo.md) 043-03-follow-up item #2
marked **RESOLVED by 043-05** (option (a) shipped; option (b) carried forward).

**Anti-horizontal-phasing check:** a user's Copilot worker is SIGKILL'd (OOM, or
`kill -9`) on iteration 3 of a run; the invocation leaves no usage file
(ADR-0048 A3), so servo halts `credit_usage_unavailable` and **nulls** the
persisted `cumulative_credits_nano` — but the billing session is intact and
carries the two clean iterations' spend plus the orphaned third. Before this
slice, `loop.py --resume` refuses it `credit_baseline_unavailable` (043-04 left
it deferred — the nulled baseline gave the fork-fresh guard no floor), and the
user must restart fresh, re-spending the budget. After this slice,
`loop.py --resume --credit-ceiling C --max-iterations N` picks it up: the last
clean cumulative was persisted as `last_sound_cumulative_nano` before the null,
so preflight admits the resume, the first resumed iteration reads the resumed
session's own cumulative `R` (which carries the orphaned spend — probe-grounded),
reconciles `R − N` against the last-sound floor, recovers the baseline to `R`,
records the honest iteration spend, and continues under the credit ceiling
exactly as 043-04 does for an `interrupted` / `""` halt — the resume path now
works end to end for a killed-worker run too. When the resumed read is
missing/partial, the session is unresumable, or the read is a fork-fresh
(`R == N`) / below-floor (`R − N < L`), the run still fails closed, so the budget
contract holds in both branches.

## Decisions needed

- **Is `last_sound_cumulative_nano`, whenever used as the recovery floor, a sound
  non-negative integer ≤ the true pre-halt session-cumulative `P`?** This is the
  slice's load-bearing premise and the frame-critique's focus — it is the exact
  property 043-04 required of `B`, now carried by a persisted watermark instead
  of the live baseline. Proof:
  1. **`L` is sound by construction.** `last_sound_cumulative_nano` is written
     only from a `cumulative_credits_nano` that is a sound non-negative int (the
     `_persist_last_sound_cumulative` guard), so every value it holds is a sound
     non-negative int. Absent ⇒ unsound ⇒ preflight-refused (AC4(b)).
  2. **`L` is a lower bound on `P` (`L ≤ P`).** `L` is the last CLEAN accumulated
     cumulative — the telescoping session-total through the last completed
     iteration before the null. The halt's orphaned/partial spend is only ever
     **additive**: a killed worker billed more on the session after `L` was
     stamped (ADR-0048 A3), and a partial report means the read was incomplete,
     not that the server un-billed. The server-side session-cumulative `R`
     (hence `P = R − N`, the pre-resume total) therefore only grows past `L`. So
     `L ≤ P`, exactly as `B ≤ P` in 043-04.
  3. **`L` is the TIGHTEST available lower bound (monotonicity).** Among sound
     values, `cumulative_credits_nano` is monotone non-decreasing within a run
     (`+= iter_nano` with `iter_nano ≥ 0`; recovery sets it to `R ≥ prior`). Each
     write of `last_sound_cumulative_nano` copies the current sound cumulative, so
     the watermark is monotone non-decreasing across writes. The "only write from
     a sound value" rule means a null (an "unknown", not a decrease) never lowers
     it — so `L` is always the highest clean watermark seen, never a stale-low
     value that would make the `R − N ≥ L` floor wrongly permissive.
  So the guard `R − N > 0 and R − N ≥ L` behaves identically to 043-04's
  `R − N > 0 and R − N ≥ B`. The attack cases:
  - **Fork-fresh resume** (`--resume` of an expired id silently starts a fresh
    session → `R = N`): recovered prior `R − N = 0`, rejected by the `> 0` clause
    directly — caught even when `L == 0`.
  - **Positive-but-too-low wrong read** (`0 < R − N < L`): rejected by `≥ L`
    (`L > 0` after ≥ 1 non-zero clean iteration).
  - **Repeated kill on a failed recovery invocation** (the recovery `--resume`
    is itself killed/unresumable, re-nulling an already-null cumulative): the
    "only write from sound" rule leaves `L` intact — the second null finds
    `cumulative_credits_nano` already null (unsound) and writes nothing. (That
    halt becomes `credit_baseline_unavailable` — non-recoverable — so `L` is not
    re-consumed; preserving it is correct hygiene, not load-bearing for
    soundness, which the guard owns.)
  - **`L == 0` degenerate.** Reachable *with* a session (a 0-nano clean iteration
    then a kill on a later iteration), so this slice does **not** rely on
    "`L == 0` ⇒ no session". Instead the `> 0` clause — reused verbatim from
    043-04 — rejects the fork-fresh signature `R == N` regardless of `L`, so the
    corner is closed structurally. The only genuine resume refused at `L == 0` is
    the zero-orphan case (nothing was spent since the 0-nano iteration — nothing
    to recover), a harmless fail-closed, exactly as 043-04's `B == 0` corner.
  - **Staler floor.** A lower `L` (e.g. from an earlier clean iteration) stays
    `≤ P`, so the floor is still valid; the `> 0` clause carries fork-fresh
    rejection independent of `L`'s magnitude.

- **Which halt reasons does this slice newly recover, and which stay refused?**
  Exactly `credit_usage_unavailable` — the halt that nulls its baseline yet (on
  iteration ≥ 2) leaves a resumable session and a persisted last-clean cumulative.
  Everything 043-04 left refused stays refused: `None` (uncommitted run — no
  guaranteed session, no clean cumulative), the structural/config refusals
  (`credit_bound_unavailable`, `credit_ceiling_insufficient`, a prior
  `credit_baseline_unavailable`, `goal_resume_unsupported`, `backend_mismatch`),
  and — unchanged — the clean halts (resume via the persisted baseline, 043-03
  AC5) and the `interrupted` / `""` halts (043-04's recovery via the live
  baseline floor).

## Assumptions

- **A1 (the last-sound watermark is a sound floor, honest-worker model).** Per
  the proof above, `L` is a sound non-negative int ≤ `P`. Like 043-04, this is
  **not** a cryptographic or adversarial guarantee: `L`, `R`, and `N` are all
  read from the worker-controlled worktree over public reads, so the
  honest-worker model (ADR-0049 A5) applies, identical to 041-02 / 043-03 /
  043-04's per-iteration credit accounting. An adversarial worker forging a
  self-consistent `state.json` (e.g. a fabricated `last_sound` + matching
  telemetry) is explicitly out of model — the servo-driven mode (spec 042-02) is
  where the adversarial anchor lives; this honest-worker resume path does not
  widen trust beyond what 043-04 already assumes.

- **A2 (the first resumed iteration's pre-iteration cap is computed before `R` is
  knowable — bounded one-shot looseness).** `R` is discovered only after the
  first resumed invocation returns, so that invocation's `--max-ai-credits` cap
  and ≥ 30-credit floor are computed from `L` (a sound lower bound). The cap is
  loose by at most the orphaned spend (bounded by the per-invocation
  `--max-ai-credits` safety net), and the moment `R` is recovered the cumulative
  is exact. This is 043-04 A2 with `L` in place of `B`; it also fixes a concrete
  crash — arithmetic on a null `cumulative_credits_nano` (the
  `credit_usage_unavailable` halt's state) would raise, so the cap MUST source
  the floor too, not only the recovery guard.

- **A3 (strictly additive to the set of runs that proceed soundly).** The new
  `credit_usage_unavailable` preflight branch and the last-sound plumbing add a
  recovery path and change no existing one: every not-recovered branch halts with
  the same `credit_baseline_unavailable` reason, no run 043-04 accepted is now
  refused, and — within A1's honest-worker model — no reachable run that would
  silently under-count is now accepted (the `R − N > 0 and R − N ≥ L` guard
  rejects fork-fresh and below-floor reads, as 043-04's does on `B`). The
  last-sound persistence is itself additive: it writes a new field only from an
  already-sound value, immediately before a null the halt already performs.
