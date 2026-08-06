---
adr: 0029
pass: frame-critique
verdict: pass
reviewer: jig:reviewer (5 independent passes)
reviewed_at: 2026-08-06T15:13:24Z
prompt_source: review.py frame-critique docs/decisions/adr-0029-autonomy-readiness-gate.md
---

Frame-critique verdict: **pass** (5th independent pass, 2026-08-06).

Four load-bearing frame flaws were caught adversarially and fixed while the ADR
was still Proposed/mutable, before any implementation:

1. **Identity-collapse check mis-tiered.** Was classified "Deterministic /
   offline," but merge authority is networked host policy and servo's
   loop/heartbeat never merge code (dispatch retains the worktree for a human to
   land). Reframed as a conditional, best-effort networked signal that escalates
   to `unsafe_for_autonomy` only when a run declares an autonomous land/merge
   capability; advisory otherwise.

2. **Readiness preflight wired into `heartbeat.py`** contradicted Accepted
   ADR-0018 (spec-less/autonomous heartbeat; a per-finding human-approval gate
   there degenerates to an off-switch, refusing ~100% of machine findings).
   Scoped off the heartbeat.

3. **"Scoped to loop.py" was under-specified** — the heartbeat's only execution
   edge IS `loop.py --prompt`, so a loop.py preflight sits upstream of every
   heartbeat dispatch. Named a concrete, code-grounded discriminator and moved
   the regression guard to assert non-refusal at the loop.py layer (not
   absence-in-heartbeat.py, which would be a false-green at the wrong layer).

4. **Discriminator incomplete** — slice 003-08 ships two unattended long-horizon
   surfaces, not one: `--background` (refuse-to-start) AND `--emit-routine-prompt`
   (refuse-to-emit). Both now gate on readiness; heartbeat's synchronous
   neither-flag `--prompt` dispatch stays exempt by construction.

The passing frame confirms: fail-closed human-approved readiness gate upstream of
edd-suitability, three-state verdict, exit {0,2}, atomic `<target>/.servo/
readiness/<goal-id>.json`, conditional identity posture, dual-surface
discriminator, loop.py-layer regression guard. Grounding facts verified in code
(heartbeat never sets either flag; the two flags are mutually exclusive at the
CLI; loop/heartbeat never merge code — heartbeat.py:48-51).

Two NON-load-bearing follow-ups deferred to implementation time (recorded in the
slice's "Frame-critique follow-ups"): a launch-surface coverage assertion, and a
disclosed Routine-recurrence re-verification limit.
