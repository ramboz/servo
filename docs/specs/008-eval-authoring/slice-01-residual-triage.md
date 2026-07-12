---
status: DONE
dependencies: [006-05, adr-0005, adr-0019, adr-0026]
last_verified: 2026-07-12
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

### Deviation log (after reconciliation)

Original ACs preserved above; the following record what changed during
implementation and why.

- **New artifact-dir convention.** Introduced `eval_dir_for_spec` →
  `<spec_dir>/eval/<spec_id>/`, the sibling of spec-oracle's `oracle/<spec_id>/`
  (ADR-0023 colocation). The `triage` artifact is `triage.json` (machine) +
  `triage.md` (human gate). This directory is reused by slices 008-02..04, so it
  is established here deliberately.
- **Timestamp-free artifact (AC5).** Unlike spec-006's `checks.json` (which
  carries `generated_at`), the triage artifact omits any churning timestamp so a
  re-run over the same plan is byte-identical. Intentional divergence from the
  sibling's shape, driven by AC5's clean-diff requirement.
- **Cross-skill reason constants mirrored, not imported.** `RESIDUAL_REASON_TASTE`
  / `RESIDUAL_REASON_UNMATCHED` are duplicated as literals (servo's "cross-skill
  data flows as JSON/subprocess, never a Python import" convention). A drift-guard
  test loads spec-006's live constants and asserts they still match, so a spec-006
  wording change fails loudly instead of silently degrading eval-able detection to
  zero (fail-closed but silent, otherwise).
- **Deterministic, fail-closed classification.** Classification is keyword/
  substring matching (no LLM), biased toward `human-residual` (over-match is safe;
  AC2). Short/ambiguous tokens (`adr`, `tone`) are word-anchored via `_has_word`
  (mirroring `oracle_plan.py`); longer phrases stay substring. This trades
  eval-able recall for fail-closed safety — a future maintainer expecting
  LLM-assisted triage should know this is intentional (a model-assist step remains
  a future, out-of-scope enhancement).
- **Craft-review blocker fix.** The artifact directory is derived from the plan
  file's own on-disk location (`plan_path.resolve().parents[2]`, since a spec-006
  plan always lives at `<spec_dir>/oracle/<spec_id>/checks.json`), NOT from the
  plan's recorded `source_spec_path` (a display string resolved against CWD) —
  making AC4 colocation CWD-independent. Guarded by a basename cross-check raising
  `EnvError`.
- **Deferred nit.** The `plan_path_layout_mismatch` guard branches lack a direct
  test (defensive code beyond AC6's coverage requirement). Low-risk follow-up,
  tracked in `docs/refinement-todo.md` (trigger: the next slice touching
  `eval_authoring.py`'s path-resolution, e.g. 008-05).
- **SKILL.md is out of scope here.** Spec 008 has no dedicated skill-surface
  slice, so `/servo:eval-authoring`'s `SKILL.md` and install-contract registration
  are correctly not authored by 008-01 (its six ACs ship the helper only). This
  cross-slice gap is tracked for spec close-out.

### Reconciliation sweep

- **`docs/architecture.md`** — `no-op`. A new, self-contained skill on the
  existing ADR-0024 harness; no module-boundary or public-contract change (the
  slice declares no `arch_review`). It reads spec-006's `checks.json` as a data
  contract and does not touch spec-006's waiver path (AC3).
- **Load-bearing decision / ADR trigger** — `no-op`. The design choices (artifact
  dir, timestamp-free determinism, deterministic classification) are derivations
  of existing decisions (ADR-0023 colocation, AC5, spec-006's deterministic-v1
  stance), not new load-bearing choices with rejected alternatives warranting a
  new ADR.
- **`.claude-plugin/install-contract.json`** — `deferred`. The new skill is not
  yet registered (no SKILL.md until close-out); the full suite + install-surface
  checks are green without it. Registration lands with the skill surface at spec
  close-out.
- **Status board** — `deferred`. Regenerated via `workflow.py status-board` after
  the `DONE` transition.
- **Memory / `docs/inbox.md`** — `no-op`. No cross-session learning beyond the
  SKILL.md close-out gap, which is captured in this deviation log and carried by
  the orchestrator.
