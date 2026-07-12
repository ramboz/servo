---
status: DRAFT
dependencies: [006, adr-0005, adr-0019, adr-0026]
last_verified:
---

## Slice 008-01 — residual-triage

**Goal:** Given a spec-006 evidence plan's `residual_judgment` list (or the
curated AC set from 008-05), classify each AC as **eval-able** (a rubric +
dataset could score it) vs **human-residual** (taste / policy / ADR-shaped —
stays waived), with a recorded rationale per AC. Never silently promote a taste
call into an eval. The self-contained core of the single servo-owned guided skill
`/servo:eval-authoring` (ADR-0019 / ADR-0026); no jig-side authoring step.

### Acceptance criteria

- **AC1** `eval_authoring.py triage <plan>` reads a spec-006 plan's
  `residual_judgment` entries (and accepts a curated AC set from 008-05 in the same
  shape) and produces, per AC, a proposed classification `eval-able | human-residual`
  plus a one-line rationale.
- **AC2** The classification is a *proposal a human confirms*. The tool never
  auto-promotes an AC it reads as taste/policy/ADR-shaped into `eval-able`; when
  uncertain it defaults to `human-residual` (fail-closed, mirroring ADR-0015).
- **AC3** `human-residual` ACs stay waived exactly as spec-006 already handles them
  (no change to the waiver path); `eval-able` ACs are queued as input to 008-02.
- **AC4** The triage decision + rationale are written to a project-owned,
  inspectable artifact (co-located with the spec per ADR-0023), not plugin state.
- **AC5** The tool's scaffolding output is structurally deterministic (stable
  ordering/format) even though the human's classification is judgment — so a
  re-run over the same plan diffs cleanly.
- **AC6** Tests cover: a mixed plan (some eval-able, some taste) triaged correctly;
  an all-taste plan yielding zero eval-able ACs without error; the artifact
  round-tripping into 008-02.

> Ships as part of `/servo:eval-authoring`. ADR-0019 settled *where* this runs;
> ADR-0026 settled that it is one kind-agnostic surface, not a per-kind sibling.
