---
slice: 043-05 — recover the Copilot kill-resume baseline from a persisted sound floor
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-16T17:21:27Z
prompt_source: review.py frame-critique
---

**VERDICT: PASS** (frame-critique, round 1 — fresh general-purpose reviewer; `frame_review: true`, load-bearing).

The single load-bearing premise — `last_sound_cumulative_nano` (L), whenever used as the recovery floor, is a sound non-negative int ≤ the true pre-halt session-cumulative P, so the guard `R − N > 0 and R − N ≥ L` is as sound on L as 043-04's is on the live baseline B — is GROUNDED, not merely asserted, and 043-05 does not widen the trust surface beyond 043-04 (ADR-0049 A5 honest-worker; ADR-0048 A2 session continuity).

Verified against the committed code:
- **L is sound by construction** — `_persist_last_sound_cumulative` writes L only when `_is_sound_nano(current)`; absent ⇒ unsound ⇒ preflight-refused.
- **L ≤ P** — the full write census of `cumulative_credits_nano` ({`=0`, `=None`, `=R`, `+=iter_nano`}) telescopes servo's total to the server-side session-cumulative after every sound write; the server cumulative is monotone over a continuous session (A2), so L (last clean total) ≤ P (total just before the first resumed invocation); orphaned/partial spend is only additive.
- **L is the tightest watermark** — the three sound writes are monotone non-decreasing; write-only-from-sound means a null never lowers L.
- **Session consistency** (the genuinely new exposure vs 043-04, and it is closed) — L is stamped inside `_apply_copilot_credit_iteration`, which returns/halts BEFORE the `current_session_id` update, so a failing iteration advances neither L nor the session id; `--models` is refused under Copilot, so no split-judge path resets the session id. L names the same session `current_session_id` does, exactly as 043-04's live B.

Attacks run and repelled: L > P (impossible — same monotone timeline); fork-fresh / wrong-session read (`R−N=0` caught by `>0` independent of L; below-floor caught by `≥L`); null-baseline crash in the pre-iteration cap (avoided — both the cap and the guard floor source via `_copilot_recovery_floor`); repeated kill clobbering L (write-only-from-sound preserves it; the failed recovery halts `credit_baseline_unavailable`, non-recoverable); L==0 degenerate (closed structurally by `>0`). Risky scenarios are exercised, not just asserted; scope discipline holds (043-04 branch and `_COPILOT_RESUMABLE_HALTS` untouched).

One non-blocking note (applied): the DoR over-attributed the partial-report sub-case's grounding to the resume-after-kill probe; it actually rests on ADR-0048 A2 additivity (the probe grounds the invoke-failure sub-case directly). The DoR wording was tightened accordingly; no Goal/AC/guard change.
