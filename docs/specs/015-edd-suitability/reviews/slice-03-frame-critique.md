---
slice: 015-03 — pipeline-gate
pass: frame-critique
verdict: needs-changes
reviewer: maintainer-frame-critique
reviewed_at: 2026-06-28T03:45:00Z
prompt_source: pre-implementation frame-critique (slice declares frame_review: true); outcome — DEFERRED
---

VERDICT: needs-changes (→ slice DEFERRED)

REASONING:
The slice's load-bearing frame — "the heartbeat consults the suitability verdict
for that finding's spec" (AC1) — does not hold. The 015-01/02 verdict is
spec-centric: `decide()` keys off AC classification from `oracle_plan.py classify`
over a `spec.md`. A heartbeat finding (CI / issue / commit) carries no spec and
no ACs; it is framed directly as a `loop.py --prompt`
([heartbeat.py:1537](../../../skills/heartbeat/heartbeat.py)). There is nothing to
pass to `suitability.py analyze --spec`, so AC4 (fail-closed on an unavailable
verdict) would fire for every finding → every finding `skipped`
(`suitability_unavailable`) → the heartbeat dispatches nothing. The second
consumer, AC5's Compile precondition, has no Servo Compile entry point to gate
(none implemented; 016 is DRAFT/parked). Both grounding consumers are therefore
missing.

SPECIFIC ISSUES:
- AC1–4, AC6 (heartbeat per-finding gate) — no finding→spec linkage exists
  anywhere in the repo (grep-verified); the spec-centric verdict cannot be
  produced for a spec-less finding. Building this as written yields an off
  switch, not a gate.
- AC5 (Compile precondition) — no `/servo:compile` / `run_compile` / handoff
  exists; the `/servo:edd-suitability → Compile` path is the unbuilt 015-04 skill
  feeding the unbuilt 016 planner.
- The 015 spec.md's activation claim ("grounding consumer: the heartbeat (011,
  DONE)") is the mistaken assumption: 011 being *done* does not make it able to
  *consume* a spec-centric verdict for spec-less findings.

DISPOSITION:
- Slice 015-03 → DEFERRED with an explicit resolution trigger (re-open when 016
  lands a Compile entry, OR a finding→spec linkage + finding-shaped suitability
  input is specced for the heartbeat).
- ADR-0015 amended (`## Amendments`, 2026-06-28) so its heartbeat-mapping claim
  is corrected without superseding the still-in-force gate contract.
- The verdict + `missing_evidence` artifact (015-01/02) ships unaffected; only
  the gating *wiring* is parked.
