---
slice: 042-05 — bounded parallel dispatch
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-13T17:06:58Z
prompt_source: review.py frame-critique docs/specs/042-campaign-orchestration/spec.md 042-05 (R1 needs-changes -> R2 pass)
---

VERDICT: pass (round 2)

Round 1 (needs-changes) raised a frame-honesty finding: 042-05's one novel
contribution — the aggregate cost ceiling — lands only on servo-driven, single-unit
USD campaigns, while ADR-0049's sole motivating runaway is a credit-billed,
HOST-DRIVEN Copilot fan-out, a mode that structurally gets no servo-enforced
aggregate ceiling; and the "episodic coordinator" story understated a wave-duration
blocking window. The prescribed fix was "a frame change, not a code fix."

Round 2: the author stated the narrowness plainly in the load-bearing artifacts — the
slice's new `## Scope` section, `architecture.md`, and `SKILL.md` all say outright
that the aggregate ceiling is servo-driven/USD-only, that host-driven mode has NO
campaign-level aggregate cap (inherent — servo doesn't dispatch there, "not a 042-05
omission"), and that the motivating Copilot runaway is NOT addressed by this slice.
Verified against ADR-0049: the "Delivery and host parity" section and resolved
open-question-3 both bound the recorded runaway via the released version's
verified-wrapped Copilot (042-04, per-worker), not via an aggregate cap — the slice
mirrors the ADR's scope rather than inflating it. The deferrals' resolution triggers
name the structural barrier (host-driven aggregate cap needs "a servo-side enforcement
point"), and the secondary wave-blocking finding is plainly admitted. The frame
survives.

Non-blocking tightenings (folded post-R2):
- refinement-todo entry 1 ("Credit-priced aggregate ceiling") reworded to scope the
  credit→USD pricing lever to *servo-driven* credit campaigns, and to note that it
  does NOT by itself give a host-driven Copilot campaign an aggregate ceiling (Copilot
  is always host-driven → servo never runs its dispatch; that is the separate
  structural barrier in entry 2).
- the Scope bullet + SKILL.md now distinguish advisory (no per-worker loop ceiling —
  unbraked in flight) from wrapped (per-worker loop ceiling), rather than lumping both
  as "Σ per-worker ceilings."
