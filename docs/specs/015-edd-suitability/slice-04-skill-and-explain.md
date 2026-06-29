---
status: DONE
dependencies: [015-01, 015-02]
last_verified: 2026-06-29
---

## Slice 015-04 — skill-and-explain

**Goal:** Ship the `/servo:edd-suitability` skill surface that makes the analyzer
usable and self-explaining: a human-readable verdict + `--json`, an `--explain`
mode that shows *which rules fired and why*, the documented re-run-after-evidence
flow, and the documented extension point for an optional model-assisted pass.
Completes spec 015's active work — servo can now produce an auditable, actionable
suitability verdict a human (and, once spec 016 lands the Compile entry, the
Compile gate) can consume.

> **Boundary with 015-01/02 and 015-03.** The engine + the evidence list already
> work headlessly (015-01/02); this slice is the **Interface** axis — the SKILL.md
> trigger bounds, the `--explain` rationale view, and the docs for the model-assist
> extension point and the waiver posture. It builds **no new verdict logic** and
> wires **no gate** — the Compile precondition is the re-scoped 015-03 (DEFERRED
> pending spec 016; [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md)),
> so this slice does not depend on it.

**DoR:**
- ✅ **015-01 + 015-02 DONE** — verdict + populated `missing_evidence` exist;
  this slice wraps `suitability.py analyze` in the skill surface and adds
  `--json` / `--explain`. It does **not** depend on 015-03 (per ADR-0018 the
  skill surface no longer needs a gate consumer).
- ✅ Servo SKILL.md house style is established (cf. `/servo:spec-oracle`,
  `/servo:heartbeat`): fire / Do-NOT-fire triggers, sibling pointers, refusal
  table, Q&A.

**Acceptance Criteria:**

1. **Skill surface.** `/servo:edd-suitability` SKILL.md ships with house-style
   fire triggers ("is this work suitable for EDD?" / "what evidence is this spec
   missing?" / "why won't Compile proceed on this spec?") and explicit
   **Do-NOT-fire** bounds delegating to siblings: oracle *synthesis* →
   `/servo:scaffold-init` (001); AC *classification* → `/servo:spec-oracle` (006);
   *running* the loop → `/servo:agent-loop`. *Test:* `SkillSurfaceTriggerTests`
   (surface tests, the servo convention).

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
- [x] All ACs pass; surface + dogfood tests green (14 in `test_skill_surface.py`;
      full suite 1088 passed); `ruff check .` clean (pinned 0.15.17).
- [x] `/servo:edd-suitability` added to the install-contract + verified across
      plugin / zip / scaffold surfaces (`verify_install_surfaces.sh` → 106 passed).
- [x] Reviewed by jig compliance + craft passes (recorded under `reviews/`;
      compliance ran as an independent subagent (PASS — 2 findings fixed in-pass),
      craft + reconciliation are maintainer self-reviews (PASS)).
- [x] Deviation log produced under this slice heading.
- [x] `docs/specs/README.md` regenerated.

### Close-out (post-DONE)
- [x] **Last active slice (015-03 DEFERRED pending 016 → spec re-activates when it
      re-opens).** Compressed the 015 surface invariants into the 015-04 board Note
      (output modes, `--explain` shape, dogfood, install-contract, follow-up);
      reconciled the stale spec.md status blockquote + flagged Goal 4 / Core model
      heartbeat references as retired by ADR-0018.
- [x] Persist the suitability vocabulary to memory (servo-015 memory updated).

### Deviation log (after reconciliation)

Original ACs preserved above; the implementation deviated/extended as follows:

- **Pre-implementation slice edits (ADR-0018).** Before coding, the slice's
  `015-03` dependency was dropped and AC1's fire triggers were reframed
  ("why was this skipped?" → Compile-gate language) because
  [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md)
  retired the heartbeat-skip mapping. The skill surface speaks of the Compile
  gate, not a heartbeat `skipped`.
- **`--explain` is a stdout-only view.** AC3 asks for an ordered rule trace. The
  persisted artifact stays the clean ADR-0015 shape; `--explain` prints the trace
  in human mode and, with `--json`, adds a `rule_trace` key to the **stdout** JSON
  only — never to the file (a test asserts the on-disk artifact has no
  `rule_trace`). The rule table was extracted into `_rule_table()` so `decide()`
  and `build_trace()` share one definition.
- **Env errors unchanged under `--json`.** AC2 specifies the success-path output.
  Env errors keep 015-01's closed contract (structured stderr reason + exit 2, no
  artifact) in **all** modes; `--json` only shapes the success output. (An
  env-error JSON envelope was considered and deferred — additive, unspecified.)
- **All five AC test classes live in `test_skill_surface.py`** (mirroring
  `spec-oracle`'s surface suite), including the CLI `OutputModeTests` /
  `ExplainTraceTests`; `test_suitability.py` (the 015-01/02 engine suite) is
  unchanged.
- **`suitability.py` classified ILLUSTRATIVE in scaffold mode.** Registering
  `edd-suitability` in `required.skills` made `test_scaffold_runtime.py` scan its
  SKILL.md; `suitability.py` needs the spec-006 `oracle_plan.py` sibling + a spec
  path, so it is marked illustrative (like `gate.py` / `heartbeat.py`), not a
  bare-scaffold smoke command. **Surfaced a latent gap (out of scope, follow-up
  filed):** the *root cause* is that **`spec-oracle` is not in
  `install-contract.json` `required.skills`**, so scaffold-mode never vendors
  `oracle_plan.py` at all — a scaffolded `suitability.py` is therefore
  non-functional there without manual wiring (the
  `SERVO_SUITABILITY_ORACLE_PLAN` override / a non-prefixed sibling path is the
  *symptom*, not the cause). The follow-up must decide whether to (a) add
  `spec-oracle` to the contract so the classifier vendors, or (b) document the
  override as the required scaffold-mode setup. Plugin mode (where suitability is
  actually used today) resolves the sibling correctly, so 015-04's surface is
  sound. *(Sharpened per the compliance review's Medium finding.)*

### Reconciliation sweep

Drift-prone surfaces checked (`updated` / `no-op` / `deferred`):

- **`suitability.py` CLI** — `updated`: added `--json` / `--explain` + the human
  default + `_rule_table`/`build_trace`/`render_*`. The pure `decide()` contract
  (verdict/reasons/missing_evidence) is unchanged — 015-01/02's 40 tests pass.
- **`.claude-plugin/install-contract.json`** — `updated`: `edd-suitability` added
  to `required.skills` (`SKILL.md` + `suitability.py`); all install surfaces green.
- **`scripts/test_scaffold_runtime.py`** — `updated`: `suitability.py` classified
  ILLUSTRATIVE (see deviation log).
- **ADR-0018 boundary** — `no-op`: this slice wires no gate; the SKILL.md states
  the Compile-only consumer and the spec-less-heartbeat rationale.
- **spec.md SPIDR row + board** — `deferred`: regenerated at DONE close-out.

**Architecture impact:** none — adds a skill surface + CLI output modes over the
existing 015-01/02 engine; no module boundary or public contract changed, so no
ADR (implements the existing ADR-0015 / ADR-0018).
