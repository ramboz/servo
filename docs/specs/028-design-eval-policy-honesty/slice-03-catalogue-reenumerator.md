---
status: DRAFT
dependencies: [028-01, 028-02, adr-0033]
last_verified:
frame_review: true
---

## Slice 028-03 — catalogue-reenumerator

**Goal:** Add the enumerate-first catalogue mode with an **independent
re-enumerating reviewer** — produce an itemised divergence list before any scalar,
require every catalogued item to be scored or explicitly excluded, and gate the
"prevention" property on a reviewer distinct from the author who re-enumerates
against the reference. This is the omission-path seam ADR-0033 identifies as
load-bearing: without it a thin catalogue leaves zero recoverable trace.

**DoR:**
- ✅ 028-01 + 028-02 DONE (structured policy + freeze-surfacing/approval-provenance).
- ✅ Demonstration done: an independent reviewer subagent, given a reference and a
  deliberately *thin* catalogue, re-enumerates and flags ≥1 uncatalogued real
  divergence the author dropped (ADR-0033 §3/OQ5). If it cannot add signal over
  unaided authoring, degrade this slice to "human-owned catalogue, surfaced at
  freeze" (Assumptions) before writing ACs 2–3.

**Acceptance Criteria:**

1. **A `catalogue` step produces an itemised, unfiltered divergence list before
   any scalar.** `design_eval.py catalogue <target> <screen>` (or equivalent)
   emits discrete labelled divergences (vision-assisted); no composite is produced
   in this mode. A test asserts the list is itemised and no score is emitted.
2. **Every catalogued item must be dispositioned — scored or excluded — before
   freeze.** Freeze refuses a structured policy in which a catalogued divergence is
   neither a `dimension` nor an `ignore` entry (no third, unaccounted state). A
   test asserts the refusal names the undispositioned item(s).
3. **The "prevention" marker requires an independent re-enumerating reviewer.** A
   freeze earns approval provenance `reviewed` (028-02) for the *omission* path
   only when a reviewer distinct from the authoring identity has re-enumerated the
   reference and its verdict is recorded (frame-critique / `jig:reviewer` idiom,
   recorded like an ADR frame-critique verdict). A test asserts a self-authored
   catalogue without that verdict is marked `self_approved`, never `reviewed`.
4. **A thin catalogue is caught by the re-enumerator, not by a record read.** A
   test stages a reference with a real divergence the author omitted; the
   independent reviewer flags it; absent the reviewer, the omission is shown to be
   *not* recoverable from the frozen record alone (documenting the ADR-0033 2×2
   honestly in a test, not just prose).

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Tests mutation-checked; host packages rebuilt + drift clean.
- [ ] Implementation + craft review passed. Consider `arch_review: true` — this
      slice adds a review seam to the freeze lifecycle (a workflow boundary).
- [ ] Deviation log + reconciliation sweep produced.

**Assumptions:**
- An independent reviewer subagent re-enumerates a reference well enough to catch a
  motivated author's thin catalogue (retired by the DoR demonstration; fallback to
  human-owned catalogue named). This is the spec's most load-bearing assumption —
  the whole omission-path guarantee rests on it (ADR-0033).
- The re-enumerator can run where design-eval authoring runs. In the desktop-app
  setup it shares the reachability wall of spec 029 / ADR-0034 (no api/cli judge) —
  cross-check whether the re-enumerator needs the 029 subagent transport, and note
  the dependency if so.

**Anti-horizontal-phasing check:** After this slice, an author's catalogue is
re-enumerated by an independent reviewer before a freeze can claim prevention, so
the field-report's silent-omission move is caught at authoring time — the actual
remedy for the reported failure, end to end.

### Deviation log (after reconciliation)

_TODO at reconciliation._

### Reconciliation sweep

_TODO at reconciliation._
