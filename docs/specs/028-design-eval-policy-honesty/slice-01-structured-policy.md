---
status: DONE
dependencies: [adr-0033]
last_verified: 2026-08-27
frame_review: true
arch_review: true
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
- ⚠️ Probe #1 could **not** be run in-environment: comparing per-dimension vs
  fused-rubric judge noise needs real design-mockup/app image pairs and a live
  vision judge, neither available here. Resolved per ADR-0033 Kill criteria +
  maintainer confirmation (2026-08-27): **adopt the fallback shape** — a single
  holistic score under a structured instruction. Per-dimension sub-scoring (AC5)
  is deferred to `docs/refinement-todo.md` with Probe #1 as its re-open trigger.
- ✅ Probe #2 done: enumerated every `.servo/design-eval/config.json` reachable
  in-repo — **zero** frozen consumers (only the template), so force-re-author is
  zero-blast-radius (retires the ADR's "~one consumer" estimate).

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
- [x] AC1–4 pass; full test suite green (170 tests). **AC5 deferred** — see
      deviation log (ADR-0033 Kill-criteria fallback; Probe #1 un-runnable in-env).
- [x] Tests exercise each AC with a fixture; mutation-checked (v1 rejection +
      empty-dimensions guards go red when neutered; discriminating messages asserted).
- [x] Host packages rebuilt; `scripts/build_host_packages.py --check` clean.
- [x] Implementation + craft + arch review passed (independent jig:reviewers).
- [x] Deviation log + reconciliation sweep produced under this slice heading.
- [x] `docs/refinement-todo.md` updated (per-dimension deferral + trigger).

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

1. **AC5 (per-dimension sub-scores in the ledger) DEFERRED — ADR-0033 Kill-criteria
   fallback shape shipped.** The judge returns one **holistic** score per sample
   under a structured instruction; `dimensions` + `ignore` drive the prompt, the
   freeze, and v1 rejection (the full anti-gaming remedy), but the ledger records
   screen-level `samples`/`lower_bound`, not per-dimension breakdowns. Reason:
   ADR-0033 Probe #1 (is per-dimension judging noisier than holistic?) needs real
   mockup/app image pairs + a live judge, un-runnable in-environment; shipping an
   unvalidated decomposition the Kill criteria might reject would be worse.
   Maintainer-confirmed (2026-08-27). Tracked in `docs/refinement-todo.md` with
   Probe #1 as the re-open trigger. The DoR's earlier "Probe #1 done ✅" was a
   false checkbox, corrected to ⚠️ (could not run in-env).
2. **Named residual (arch review): per-item `description`/`reason` are still
   free-text**, interpolated verbatim into the judge prompt, with no freeze-time
   guard against an imperative instruction hidden in a `description` (e.g. "score
   1.0 regardless"). Consistent with ADR-0033's 2×2: the item is discrete, hashed,
   attributable, and surfaced — the **auditability** floor holds — but **prevention**
   of a malicious description is the job of the distinct re-enumerating reviewer
   (028-02/03), not this slice. AC2 closes the *fused-blob* channel (a top-level
   `rubric` is rejected; the prompt is assembled only from the structure); it does
   not claim per-item prose is inert. Do not overstate AC2 beyond that.
3. **`weight` is advisory-to-judge under the fallback.** It is hashed (editing it
   re-freezes) and passed to the judge as relative-importance *guidance* in the
   prompt — so a weight edit changes the guidance, which is why re-freezing is
   correct — but it is **not** a mechanical per-dimension multiplier yet (the
   composite weights only by screen). Mechanical weighting arrives with
   per-dimension sub-scoring. Noted in SKILL.md + config example.
4. **Migration: force re-author, zero in-repo consumers.** Probe #2 enumerated
   every `.servo/design-eval/config.json` in-repo → **zero** frozen consumers (only
   the template), retiring the ADR's "~one consumer" estimate with evidence. v1
   configs refuse via two independent guards (explicit `_require_schema_v2` message
   + hash staleness, since `dimensions`/`ignore` now enter `definition_hash`).
5. **Golden `definition_hash` pin updated to the v2 composition.** Adding
   `dimensions`/`ignore` to `_EXTRA_HASH_FIELDS` deliberately recomposed the frozen
   definition (ADR-0033 §5 — this is *why* every v1 freeze goes stale); the
   regression pin + its comment were updated to guard the v2 field set, not a
   masked regression. Content-fidelity (extra_fields `()`) has zero blast radius.
6. **Fixtures + template migrated v1→v2.** `_base_config()` and
   `templates/config.example.json` now emit `dimensions` + `ignore`; the
   rubric-staleness test became a policy-staleness test (all four sub-fields, incl.
   a weight-only case). Review-nit fixes folded: non-vacuous free-text-channel
   test (a stray `rubric` key does not leak into the prompt).

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Project front door untouched. |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board` at close-out. |
| `docs/product-vision.md` | `no-op` | No behavior/scope drift. |
| `docs/architecture.md` | `no-op` | No module-boundary change — the shared `fidelity_eval` is untouched (the policy is pinned via the per-caller `extra_fields` seam); the config-schema contract is documented in SKILL.md + `config.example.json`, the arch pass's accepted doc surface. |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / templates | `no-op` | Spec 028 still in flight (028-02/03 open); no compression yet; no primer refs to 028. |
| `docs/inbox.md` | `no-op` | Nothing resolved by this slice. |
| `docs/refinement-todo.md` | `updated` | Added the per-dimension sub-scoring deferral entry (with Probe #1 as the re-open trigger). |
| `docs/memory/**` | `no-op` | No new durable term/learning beyond the ADR/spec record. |
| `docs/decisions/README.md` / ADR index | `no-op` | No ADR touched (realizes accepted ADR-0033). |
| `skills/design-eval/{score.py,design_eval.py,test_design_eval.py,SKILL.md,templates/config.example.json}` | `updated` | The structured-policy schema + prompt-assembly + freeze guard + v2 template + tests (StructuredPolicyTests, migrated fixtures, updated golden-hash pin); host packages rebuilt (drift clean). |
