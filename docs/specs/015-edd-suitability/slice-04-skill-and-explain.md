---
status: DRAFT
dependencies: [015-01, 015-02, 015-03]
last_verified:
---

## Slice 015-04 — skill-and-explain

**Goal:** Ship the `/servo:edd-suitability` skill surface that makes the analyzer
usable and self-explaining: a human-readable verdict + `--json`, an `--explain`
mode that shows *which rules fired and why*, the documented re-run-after-evidence
flow, and the documented extension point for an optional model-assisted pass.
Closes spec 015 — servo can now refuse un-evaluable work with an auditable,
actionable verdict.

> **Boundary with 015-01..03.** The engine, the evidence list, and the gating
> already work headlessly; this slice is the **Interface** axis — the SKILL.md
> trigger bounds, the `--explain` rationale view, and the docs for the model-assist
> extension point and the waiver posture. It builds no new verdict logic.

**DoR:**
- ✅ **015-01..03 DONE** — verdict + missing-evidence + the two gate call sites
  exist; this slice wraps them in the skill surface and adds `--explain`.
- ✅ Servo SKILL.md house style is established (cf. `/servo:spec-oracle`,
  `/servo:heartbeat`): fire / Do-NOT-fire triggers, sibling pointers, refusal
  table, Q&A.

**Acceptance Criteria:**

1. **Skill surface.** `/servo:edd-suitability` SKILL.md ships with house-style
   fire triggers (generate/specify/"is this work suitable for EDD?"/"why was this
   skipped?") and explicit **Do-NOT-fire** bounds delegating to siblings:
   oracle *synthesis* → `/servo:scaffold-init` (001); AC *classification* →
   `/servo:spec-oracle` (006); *running* the loop → `/servo:agent-loop`. *Test:*
   `SkillSurfaceTriggerTests` (surface tests, the servo convention).

2. **Human + `--json` output.** `suitability.py analyze` renders a concise human
   summary (verdict + one line per blocking `missing_evidence` item) by default
   and the full ADR-0015 JSON under `--json`. *Test:* `OutputModeTests`.

3. **`--explain` rationale.** `--explain` shows the **ordered rule trace** — which
   rules were evaluated, which fired, and the input each keyed on — so a verdict
   is debuggable without reading the rule-table source. *Test:* `ExplainTraceTests`.

4. **Re-run flow documented + demonstrated.** SKILL.md documents the
   acquire-evidence → re-`analyze` → verdict-flips loop, and a dogfood fixture
   demonstrates a `needs_evidence` spec flipping to `suitable` after the named gap
   is closed. *Test:* `RerunDogfoodTests`.

5. **Extension-point + waiver docs.** SKILL.md documents (a) the optional
   model-assist pass as a **flagged, bounded** extension to the deterministic rule
   table (cf. ADR-0005's frozen-eval discipline for any non-determinism), and
   (b) the human-waiver posture for overriding a `needs_evidence` / `unsuitable`
   gate (borrowing spec-006's waiver shape), each marked as the documented seam,
   not built here. *Test:* `ExtensionPointDocTests`.

**DoD:**
- [ ] All ACs pass; surface + dogfood tests green; `ruff check .` clean.
- [ ] `/servo:edd-suitability` added to the install-contract + verified across
      plugin / zip / scaffold surfaces (`verify_install_surfaces.sh`).
- [ ] Reviewed by jig compliance + craft passes (record review evidence).
- [ ] Deviation log produced under this slice heading.
- [ ] `docs/specs/README.md` regenerated.

### Close-out (post-DONE)
- [ ] **Spec-closing slice:** apply the compress-on-close-out rule — migrate
      load-bearing 015 invariants (verdict shape, closed `kind` taxonomy,
      suitability `actionable_reason` codes) to board Notes / memory; trim any
      in-flight 015 prose from primer surfaces.
- [ ] Run `/jig:memory-sync` to persist the suitability vocabulary.
