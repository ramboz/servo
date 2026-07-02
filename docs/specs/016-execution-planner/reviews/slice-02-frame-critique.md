---
slice: 016-02 — run-consume
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-07-02T21:39:40Z
prompt_source: review.py frame-critique docs/specs/016-execution-planner/spec.md 016-02 (4th pass)
---

Adversarial pre-implementation frame-critique (`frame_review: true`). Reached PASS
on the 4th pass; the first three each surfaced a real wrong-frame issue that was
fixed before advancing — the pass earned its keep.

**Iteration history (evidence trail):**
1. **needs-changes** — spec.md's provisional goal still enlisted the heartbeat as a
   plan consumer (contradicts ADR-0018) and never stated how `loop.py` (no spec-id)
   locates the plan. Fixed: named the `--plan <path>` addressing mechanism and
   scoped the consumer to `loop.py` in the banner, Goal 4, SPIDR row, and core-model
   diagram.
2. **needs-changes** — the load-bearing "read `prompt_ref` as the seed prompt"
   (AC3) was a category mismatch: `prompt_ref` points at the whole multi-slice
   `spec.md`, but `loop.py` feeds the seed verbatim to `claude -p` as the task
   instruction (`loop.py:1300`, `:464`). Also: A1's "single seam" was wrong for
   `--driver` (consumed by routing probes before `run_loop`); and a citation error.
   Fixed the seam + citation; moved to fix the producer.
3. **needs-changes** — "fix the producer" exposed that `execution_plan.py` never
   reads `spec.md` (derives `spec_id` from the dir name), so rendering an actionable
   prompt is a distinct *spec→prompt compiler* capability, not a knob-read. Also
   caught the goal driver structurally dropping two of four budget knobs
   (`loop.py:3049`). Resolution: **split prompt rendering to new slice 016-05**;
   narrowed 016-02 to `budget` + `driver` consumption; added the goal-driver
   carve-out as AC3.
4. **PASS** — A1 and A2 verified directly against `loop.py`; the 016-05 split judged
   coherent (not a scope dodge) and 016-02 non-hollow. Only remaining exposure is
   the disclosed, bounded `--driver` `None`-migration risk the frame already names —
   not a wrong assumption.

**Reviewer:** general-purpose (fresh subagent, no implementation context), read-only.

**Verdict: PASS.**

**Implementation note carried forward:** AC1 (fill un-passed knobs) and AC3 (silent
drop of plan-sourced loop-only brakes under the goal driver) collide if plan values
are written into `args.<brake>` in place — the drop warns iff `args.<brake> is not
None` (`loop.py:3058`). The resolution layer must track source-of-value
(user-passed vs plan-sourced vs default) separately from the `None`-sentinel.
Recorded in the slice's Assumptions section.
