---
status: DRAFT
kind: feature
dependencies: [036-01, 035-02, adr-0044]
last_verified:
frame_review: true
arch_review: true
---

## Slice 036-02 - regional-image-evidence

**Goal:** A developer evaluates approved card image regions through the same
installed gate and receives named local blockers with actionable visual
correction artifacts, not only a favorable whole-image average.

**DoR:**
- 036-01 and 035-02 DONE; approved current source captures/region bindings.
- Owner selects a pinned comparison engine only after canonical source/license
  review, bounded platform probes and independently checked metric behavior.
  Impeccable is a candidate, not an adopted dependency.
- Owner approves a bounded positive/negative calibration set, region metrics,
  normalization/scale handling and thresholds after inspecting false-pass/
  false-block results; golden parity alone is insufficient.
- Any selected dependency/contract-changing decision gets its own Proposed ADR
  and acceptance ceremony if needed; ADR-0044 does not settle that choice.

**Acceptance Criteria:**

1. **Same installed gate.** The approved source and bound candidate captures
   feed pinned local regional metrics through the existing ordinary evidence
   component; its raw metrics, comparisons and identity-bound results reach
   the real quality gate and supported reporting consumers. Matching regions
   yield component pass, with all exact/tolerant/state assertions from 036-01
   still enforced. Overall pass additionally requires quality policy; the
   preserved gate run binds component/region-record digests and current delivery.
2. **Local veto.** A named required title/band region contradicted while the
   whole-image diagnostic score is at least 0.99 yields exit 1 and a blocker
   naming the region/constraint and failing metric/threshold. Missing region,
   wrong capture/build/state, unsupported dimensions/scale, or unavailable
   engine yields exit 2, not skipped pixels or silently resized success.
3. **Correction artifacts.** Every evaluated regional failure exposes hashed
   reference/actual crops plus difference or overlay output and bounds linking
   it to the source target and implementation observation. Available artifacts
   are retained on refusal, with a named acquisition/identity cause. The
   report distinguishes raw raster metrics from interpreted thresholds.
4. **Calibration honesty.** Report actual outcomes for every member of the
   approved bounded calibration set, including high-overall-score local
   failures and approved harmless variations. False passes/blocks are visible;
   any required contradiction that passes blocks adoption. Parity probes
   against a pinned candidate implementation are labeled parity only and
   never described as Vellum accuracy or production readiness.
5. **Policy integrity and portability.** Metric engine/version, region set,
   source/capture hashes, normalization, thresholds and exclusions are frozen.
   Changes require reviewed reapproval. The chosen supported-platform install
   and invocation are exercised without global plugin changes, uncontrolled
   downloads or importing a candidate engine's phase workflow/aesthetic
   defaults. Unsupported platforms explicitly refuse.

**DoD:**
- [ ] Installed-gate and report controls demonstrate metric + local-veto +
      correction behavior end to end; no required contradiction false-passes.
- [ ] Bounded calibration/portability report records inputs, limits and failures.
- [ ] Required independent implementation/craft/architecture and reconciliation
      reviews pass with engine/license decision and live documentation aligned.

## Assumptions

- A candidate raster engine is portable within the declared support boundary;
  validate rather than infer it from source structure or successful compilation.
- Selected metrics/thresholds discriminate the approved bounded design
  variations. No calibration or generality is established by this draft.

**Anti-horizontal-phasing check:** The user receives a gate result and concrete
local correction images for an actual app, not an unused image-diff primitive.

### Close-out (post-DONE)

- [ ] Regenerate board; retain bounded calibration/support claims and engine pin.
- [ ] Reconcile live metric/correction/install documentation and decision links.
