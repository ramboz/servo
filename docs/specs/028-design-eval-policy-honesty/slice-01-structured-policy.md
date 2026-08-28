---
status: DRAFT
dependencies: [adr-0033]
last_verified:
frame_review: true
---

## Slice 028-01 — structured-policy

**Goal:** Replace the free-text `rubric` with a structured `dimensions` +
`ignore:[{id, reason}]` policy (`schema_version` 1→2), hash the structure into the
frozen definition, assemble the judge prompt from it, and disposition the v1→v2
migration — so an author can write, freeze, and score a screen with per-dimension
judging and an explicit, discrete ignore-list end to end.

**DoR:**
- ✅ [ADR-0033](../../decisions/adr-0033-design-eval-structured-scoring-policy.md)
  Accepted.
- ✅ Probe #1 done: score a real screen with (a) a fused prose rubric and (b) an
  equivalent per-dimension policy on the same shots, and confirm per-dimension
  judging is not materially noisier (ADR-0033 Kill criteria). If it regresses,
  adopt the fallback shape (single scored question + structured `ignore`) before
  writing ACs 1–2.
- ✅ Probe #2 done: enumerate every `.servo/design-eval/config.json` reachable
  in-repo to size the migration blast radius (Assumptions).

**Acceptance Criteria:**

1. **A `schema_version: 2` config with `dimensions: [{id, description, weight?}]`
   and `ignore: [{id, reason}]` freezes and scores.** `design_eval.py freeze`
   accepts the structured policy, and `score.py` produces a composite from it — no
   free-text `rubric` key required. Each `dimension` and each `ignore` entry is a
   discrete object (not prose).
2. **The judge prompt is assembled from the structure**, not a hand-written
   string: the per-dimension scoring instruction and the explicit ignore-list are
   composed by `score.py` from `dimensions`/`ignore`. A test asserts the assembled
   prompt names each scored dimension and each ignored id, and that there is no
   second free-text channel where an unreviewed instruction can ride along.
3. **Editing `dimensions` or `ignore` (ids, reasons, or weights) re-freezes.** The
   structured policy is part of the frozen, sha256'd definition; a post-freeze edit
   to any of it makes `score.py` refuse as **stale** (exit 2), consistent with
   ADR-0005. A test mutates each and asserts staleness.
4. **A `schema_version: 1` (free-text `rubric`) config is handled per the chosen
   migration disposition, loudly.** Force-re-author (lean): a v1 config scores with
   an `env_error` (exit 2) naming the v1→v2 migration, never a silent score. (If
   Probe #2 shows auto-migration is warranted, instead: a v1 `rubric` is lifted
   into a v2 skeleton — one `dimension` = the whole rubric, empty `ignore` — and a
   loud stderr advisory says the eval must be re-authored into real dimensions.)
   Either way the behavior is explicit and tested; no v1 config silently scores as
   if it were structured.
5. **Per-dimension scores are legible in the ledger.** Each screen row records the
   per-dimension sub-scores (not only the aggregate), so a low composite says
   *which* dimension failed.

**DoD:**
- [ ] All ACs pass; full test suite green (no regressions).
- [ ] Tests exercise each AC with a fixture; each new test shown to fail when its
      feature is removed (mutation-checked).
- [ ] Host packages rebuilt; `scripts/build_host_packages.py --check` clean.
- [ ] Implementation + craft review passed (`reviewer` subagents).
- [ ] Deviation log + reconciliation sweep produced under this slice heading.
- [ ] `docs/refinement-todo.md` updated for any deferred decision.

**Assumptions:**
- Per-dimension vision judging is not materially noisier than a fused rubric
  (retired by Probe #1 in DoR before ACs 1–2 are built; fallback shape named).
- The migration blast radius is ~one consumer (retired by Probe #2). The disposition
  (force-re-author vs auto-migrate) is chosen from that enumeration, not assumed.

**Anti-horizontal-phasing check:** After this slice, an author can author a
structured design-eval policy, freeze it, and get a real per-dimension composite
with an explicit ignore-list — a complete, user-visible authoring-to-score path,
not scaffolding for a later slice.

### Deviation log (after reconciliation)

_TODO at reconciliation._

### Reconciliation sweep

_TODO at reconciliation._
