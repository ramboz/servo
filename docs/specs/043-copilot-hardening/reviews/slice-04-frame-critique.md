---
slice: 043-04 — lift the Copilot kill-resume fail-closed
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-16T02:24:21Z
prompt_source: review.py frame-critique (R1 nc → R2 nc → R3 pass)
---

**VERDICT: PASS** (frame-critique, R1 needs-changes → R2 needs-changes → R3 PASS — a fresh general-purpose reviewer each round).

The load-bearing premise — the resumed read `R` is authoritative on the first
resumed iteration AND the fail-closed fallback catches every case where it is not —
is now faithfully realized. Two progressively narrower blockers were found and
fixed; R3 confirmed closure.

**R1 blocker (fixed) — fork-fresh silent under-count.** The recovery path committed
to `R` on any `aiCreditsStatus == "complete"` read, guarded only by `R − N ≥ 0`. A
`copilot --resume=<expired id>` that silently FORKS A FRESH session (a plausible CLI
UX; the slept-machine resolution-trigger case is exactly when a server-side session
expires) returns a complete, truthful read of the WRONG session with `R = N`, so
`R − N = 0 ≥ 0` passed and the orphaned pre-kill spend was silently dropped →
budget under-count (~2× ceiling in the demonstrated scenario, run reports success).
servo cannot verify session continuity (the session id is not in Copilot's event
stream); the probe (n=1, resumable session, pinned `--session-id`) did not ground
the expired-session case. **Fixed** by the `R − N ≥ B` floor (B = persisted stale
baseline) — the clean path's `expected = R − prior` reconciliation re-used as a
floor accommodating the orphan — plus narrowing the recoverable set to
`{interrupted, ""}` (both carry a sound `B`), requiring a sound baseline at
preflight, and deferring `credit_usage_unavailable` (always a null baseline).

**R2 blocker (fixed) — the `B == 0` corner.** The `R − N ≥ B` floor closes R1 for
every reachable `B > 0`, but degenerates to `R − N ≥ 0` when `B == 0` (a completed
iteration that accounted to a 0 cumulative is code-reachable via a 0-nano `chat`
span), re-admitting the fork-fresh signature at `B == 0` (bounded to one iteration,
near-unreachable, but the spec certified total closure). **Fixed structurally** by
the `R − N > 0` clause: the guard is `R − N > 0 and R − N ≥ B`, rejecting the
fork-fresh signature `R == N` directly regardless of `B`.

**R3 (PASS) — confirmation.** The `recovered_prior <= 0` clause fires before the
`< B` check, so a fork-fresh (`R − N = 0`) is caught at every `B` including 0;
direct probe (run-a `R == N`, prior 0) → `(None, 'credit_baseline_unavailable')`;
the only genuine resume refused by `> 0` is the degenerate `B == 0` + zero-orphan
case (nothing to recover — harmless), and run-b (`R − N > 0`) still recovers at
`B == 0`. No new spurious refusal; A3's "no reachable run silently under-counts"
holds within A1's honest-worker model; the two state-hygiene pops are correct
(no double-fire / stale-fire). All four `loop.py` copies byte-identical and carry
the guard; targeted tests + the full suite green; ruff clean.

**Non-blocking (R3 notes, folded / documented):** A3 now cross-references A1's
honest-worker scope. The split-judge × deferred-recovery interaction R3 flagged as
untraced is **unreachable under Copilot** (`--models` is refused under
`--host copilot`, so `_models_in_effect` / `split_judge` are always False and the
first resumed iteration always resumes the session) — confirmed independently by the
compliance and craft passes; recorded in the deviation log.
