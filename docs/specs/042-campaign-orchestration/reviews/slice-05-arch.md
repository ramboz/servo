---
slice: 042-05 — bounded parallel dispatch
pass: arch
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-13T17:06:58Z
prompt_source: review.py arch-review docs/specs/042-campaign-orchestration/spec.md 042-05 skills/heartbeat/campaign.py skills/heartbeat/test_campaign.py
---

VERDICT: pass

Bounded parallel dispatch is a coherent, minimal extension of the 042-02 serial
coordinator. The "episodic coordinator, no daemon" contract holds (the wave still
Popens-all/joins-all inside one `campaign next` that exits; the non-blocking
`.next.lock` serializes wakes); the dependency-free invariant holds (both paths
lazy-load loop.py/heartbeat.py via the dynamic loader, no static cross-skill import);
the serial path is routed and tested byte-for-byte identical to 042-02; and the
USD-only aggregate-ceiling design is fail-closed at both `init` and `next`.
architecture.md updated with a full 042-05 paragraph; all four host-mirror campaign.py
copies byte-identical. No public contract broke (plan.json gains optional
`max_parallel`/`aggregate_budget`; the function splits are private). No blockers.

Strengths (preserve):
- The AC2 ceiling formula (enforced recorded spend + Σ reserved full ceilings of live
  workers + this item's ceiling ≤ aggregate, per-item accumulation, plan-order
  stop-not-skip on refusal) with conservative full-ceiling reservation released to
  actual spend on finish — the right concurrency-safe model.
- Defense-in-depth: a hand-edited incoherent parallel plan is re-validated at `next`,
  the refusal is recorded, and the command exits non-zero; `_plan_max_parallel`
  coerces bad values to serial — the system fails closed to serial, never unbounded.
- Per-file reconciliation: a killed worker among several releases only its own budget;
  the recorded-but-reserved window is closed by `cleaned_recorded` before any dispatch.
- Shared `_budget_shape_error` single-shape contract; barrier-based concurrency proof.

Nits (all logged in the deviation log, non-blocking):
- The `coordinator_decision` entry is polymorphic across three shapes (serial singular
  / parallel plural + `aggregate` / incoherent-refusal `aggregate:{error}`); a consumer
  branches on shape. Deliberate AC5 trade-off (serial must stay byte-for-byte 042-02),
  low-risk (decision entries are forensic data). architecture.md now notes the richer
  parallel shape.
- The wave joins workers in plan/ready order (not completion order), so a slow
  first-selected worker keeps the coordinator and the held lock alive for the slowest
  worker's duration, and freed slots/budget are reused on the next wake, not mid-wave.
  Correctness-neutral and inherent to Popen-all/join-all; documented in the Scope
  section + refinement-todo.
- `enforced_spend` counts a re-queued item's re-run cost cumulatively — safely
  conservative (stops dispatch sooner), documented.
