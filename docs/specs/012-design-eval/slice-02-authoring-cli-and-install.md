---
status: IN_PROGRESS
dependencies: [adr-0005]
last_verified: 2026-08-18
---

## Slice 012-02 — authoring-cli-and-install

**Goal:** Ship `skills/design-eval/design_eval.py` — the authoring CLI that
scaffolds an eval directory, captures references, freezes the definition, and
splices a `score_design_fidelity` component into the target's `oracle.sh`,
mirroring `oracle_overlay`'s install/uninstall shape so the component is an
ordinary citizen of the existing contract.

**DoR:**
- ✅ **012-01 supplies the freeze/aggregate core** this CLI drives.
- ✅ **The splice shape is already settled** by spec 006-03's
  `oracle_overlay.py` (`# SEED:start/end` block, `COMPONENTS` registration,
  `.servo/install.json` manifest) — this slice mirrors it rather than
  inventing a second convention.

**Acceptance criteria** (spec ACs 1, 2):
1. `init(target)` scaffolds the eval directory and a `config.json` seeded from
   `templates/config.example.json`.
2. `capture_refs(target)` drives `capture.mjs` to produce the reference PNGs.
3. `freeze(target)` records `definition_hash` + `artifact_hashes` into the
   frozen config.
4. `install(target, weight)` splices a `score_design_fidelity` component into
   `oracle.sh` (idempotent, `bash -n` clean, baseline untouched) and registers
   it in the manifest; `uninstall(target)` reverses it cleanly.
5. The installed component is an **ordinary** `score_<name>` echoing `[0,1]` /
   rc 2 — `oracle.sh`, `gate.py`, and the 0/1/2 contract are unchanged.

**DoD:**
- [x] `init` / `capture_refs` / `freeze` / `install` / `uninstall` +
      `_register_manifest` / `_deregister_manifest` implemented.
- [x] 3 unit tests green — `InstallTests`.
- [x] Scored by stock `gate.py` with no special-casing.
- [x] Shipped in a tagged release (through 0.8.0).
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

### Retro-reconciliation note (2026-08-18)

Retro-recorded with [012-01](slice-01-freeze-and-aggregation-core.md); see that
slice's note for why spec 012 has no review evidence. Test depth here (3 tests)
is materially thinner than 012-01's (15) — install/uninstall round-trip is
covered, but the manifest-registration and splice-idempotence paths lean on the
shared `oracle_overlay` conventions rather than on their own assertions. That
gap is real and is one of the things a review pass would be expected to raise.

**Post-hoc scope change:** the install/splice primitives were later extracted
to `skills/_common/fidelity_eval.py` by
[020-01](../020-content-fidelity-eval/slice-01-extract-shared-harness.md)
([ADR-0024](../../decisions/adr-0024-extract-frozen-eval-harness.md)).
