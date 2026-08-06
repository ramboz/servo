---
slice: 023-01 — readiness verdict, artifact, and human approval
pass: arch
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-08-06T16:02:22Z
prompt_source: review.py arch-review (spec 023-01)
---

Arch pass verdict: **pass**. The slice is architecturally coherent: it mirrors servo's accepted eval-authoring reuse pattern (filesystem read of jig's SKILL.md spliced as framing into servo's OWN claude -p call — no servo→jig import, verified), keeps the ADR-0011 jig boundary clean, writes an atomic fail-closed artifact, correctly declares itself a host/Compile-phase tool absent from required.skills, and places readiness upstream of edd-suitability. The three tiers (deterministic/model/identity) have honest documented boundaries; identity posture is kept out of the offline-deterministic tier and gated on --declares-autonomous-merge per amended ADR-0029; the model tier fails to a concern, never a silent ready.

Findings dispositioned:
- goal-id cross-module contract: docstring updated to direct 023-02 to consume the `check` subprocess contract (single source of truth) rather than inline-mirror the hash; if 023-02 reads the artifact directly it must add a hash-agreement test.
- schema_version forward-compat: added a guard in load_artifact (approve path). check still reads directly (its missing→exit-1 vs env→exit-2 semantics differ from load_artifact's raise-on-missing) — divergence recorded as a 023-02 reconciliation item.
- re-analyze silently reverts approval: documented in SKILL.md as an intended fail-closed behavior.
- architecture.md phase-boundary table still names edd-suitability as the first Compile step — must gain a readiness row; carried to the reconciliation sweep.
