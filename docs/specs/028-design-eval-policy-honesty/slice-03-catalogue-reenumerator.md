---
status: DONE
dependencies: [028-01, 028-02, adr-0033]
last_verified: 2026-08-28
frame_review: true
arch_review: true
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
- [x] AC1–3 pass; AC4 partially (its out-of-band prong — see deviation log); full
      suite green (192 tests).
- [x] Tests mutation-checked (undispositioned-refusal, distinctness-from-record,
      non-empty-catalogue, fingerprint-staleness all go red when neutered); hosts
      rebuilt + drift clean.
- [x] Implementation + craft + **arch** review passed (independent jig:reviewers;
      round 2 after the round-1 distinctness-fail-open blocker was fixed).
- [x] Deviation log + reconciliation sweep produced.

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

1. **Round-1 BLOCKER fixed (all three reviews): distinctness was fail-open.** The
   first cut gated the distinct-from-author check on the *optional* freeze `--author`
   flag, so `freeze --reviewer X` with no `--author` earned `reviewed` on a
   self-review — defeating the exact motivated-author threat ADR-0033 targets. Fix
   (defense-in-depth): `record-reenumeration` now **requires `--author`** and
   **rejects `reviewer == author` at write time** (a self-review can never be
   recorded); `_check_reenumeration` re-proves distinctness **from the record**,
   unconditionally (both ids present + different), so the freeze `--author` flag is a
   mere optional cross-check, not the guarantee source. New tests:
   `test_record_reenumeration_rejects_self_review_at_source`, `_requires_author`,
   `test_reviewed_distinctness_holds_even_without_freeze_author_flag`.
2. **Verdict fingerprint widened to the whole attestation surface (craft/arch
   blocker/nit).** `_reenumeration_fingerprint = sha256(definition_hash |
   artifact_hashes)` binds the verdict to the full policy (dimensions/ignore/
   catalogue/viewport/judge/samples/threshold/screens) **and** the reference image
   *content* — so a reference swap, a disposition re-file (scored→ignored), or a
   catalogue edit all stale it. Tested three ways.
3. **`reviewed` requires a non-empty `catalogue` (craft/arch nit).** The extreme
   thin catalogue (none) can no longer earn `reviewed` — an empty catalogue can be
   `self_approved`, never `reviewed`. (Catalogue is optional for a `self_approved`
   freeze — that is ADR-0033's 2×2 degradation *by design*: no catalogue → the
   omission path is "nothing recoverable", honestly, not a missing guard.)
4. **AC5 (per-dimension) note:** unaffected here (deferred in 028-01). **AC4's
   second prong** — "absent the reviewer, the omission is not recoverable from the
   record alone" — is only *partially* test-representable: the real re-enumeration
   is out-of-band vision work (a distinct subagent/human reading the reference), not
   unit-testable in-environment (same limit as 028-01 Probe #1). Represented via a
   recorded `verdict=fail` path + the honest SKILL.md trust-boundary note.
5. **Accepted trust boundary (arch OQ, logged as the chosen stance):** the
   `reenumeration.json` record and the `approval_provenance` marker are **trusted
   metadata, not tamper-evident** — neither is in `definition_hash`/`artifact_hashes`
   (consistent with ADR-0005, where `approval_status` is likewise unhashed), so a
   post-freeze hand-edit flipping `self_approved`→`reviewed`, or deleting the record,
   would not stale `approved_content_hash`. This is deliberate: identity distinctness
   rests on truthful `--reviewer`/`--author` inputs and the out-of-band reviewer
   actually doing the work — a *structured, catalogue-bound* discipline, **not
   forgery-proof**. Named honestly in SKILL.md ("Residual").
6. **UX nit (craft, non-blocking):** `record-reenumeration` does not pre-warn when
   the catalogue is empty/undispositioned; the freeze gate is authoritative, so no
   false `reviewed` escapes — recording a verdict that cannot yet earn `reviewed` is
   merely a mildly confusing loop, left as-is.
7. **Golden `definition_hash` pin updated again** (v2 composition now includes
   `catalogue`): `sha256:514e2758…`. Deliberate ADR-0033 §3 recomposition; content-
   fidelity (`extra_fields=()`) has zero blast radius.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Front door untouched. |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board` at close-out (spec 028 now DONE). |
| `docs/product-vision.md` | `no-op` | No behavior/scope drift. |
| `docs/architecture.md` | `no-op` | No module-boundary change to the shared `fidelity_eval`; the catalogue/re-enumeration seam is design-eval-local (score.py policy/hash, design_eval.py workflow/CLI/record). Documented in SKILL.md. |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / templates | `no-op` | Spec 028 closes, but nothing to compress: no `CLAUDE.md` Active-specs entry for 028 (verified), no `AGENTS.md`; the board tracks DONE. |
| `docs/inbox.md` | `no-op` | Nothing resolved by this slice. |
| `docs/refinement-todo.md` | `no-op` | No new deferred decision (the accepted trust boundary is recorded here in the deviation log as the chosen stance, not a deferral). |
| `docs/memory/**` | `no-op` | No new durable term/learning beyond the ADR/spec record. |
| `docs/decisions/README.md` / ADR index | `no-op` | No ADR touched (completes accepted ADR-0033 §3). |
| `skills/design-eval/{score.py,design_eval.py,test_design_eval.py,SKILL.md}` | `updated` | Catalogue + disposition rule + enforced re-enumeration verdict + CLI (`catalogue`, `record-reenumeration`) + tests; host packages rebuilt (drift clean). |
