---
status: DONE
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
- [x] 19 unit tests green — `InstallTests` (3), `InstallHardeningTests` (8),
      `FreezeCliTests` (3), `CliDispatchTests` (3), `CaptureRefsTests` (2).
- [x] Scored by stock `gate.py` with no special-casing.
- [x] Shipped in a tagged release — 0.3.0 through 0.8.0.
- [x] Compliance + craft review verdicts recorded under `reviews/`.
- [x] Reconciliation verdict + deviation log + reconciliation sweep recorded.

### Retro-reconciliation note (2026-08-18)

Retro-recorded with [012-01](slice-01-freeze-and-aggregation-core.md); see that
slice's note for the lifecycle history.

**The thin-coverage gap this note originally described is now closed.** At
retro-record time the slice had 3 tests and leaned on the shared
`oracle_overlay` conventions rather than its own assertions. The review pass
confirmed the gap and it was fixed in the same reconciliation: `bash -n`
validity of the spliced `oracle.sh` (both before and after uninstall),
SEED-block balance, manifest de-duplication on re-install, uninstall
idempotence, config preservation across `install()`'s `init()` step, and the
fail-closed `FileNotFoundError` paths are now directly asserted, plus
`de.freeze()` and `main()`'s argparse dispatch.

Compliance also flagged `capture_refs` as the one CLI verb with neither error
handling nor a test: a missing `node` escaped as an uncaught traceback rather
than the clean env-error rc that `score.capture_app` already returned for the
same failure. Fixed (`ENV_ERROR_RC`, mirroring `score.py`'s `EXIT_ENV_ERROR`)
and covered by `CaptureRefsTests`.

**Post-hoc scope change:** the install/splice primitives were later extracted
to `skills/_common/fidelity_eval.py` by
[020-01](../020-content-fidelity-eval/slice-01-extract-shared-harness.md)
([ADR-0024](../../decisions/adr-0024-extract-frozen-eval-harness.md)).

### Deviation log

- **Retro-lifecycle, not a build deviation** (see 012-01's log).
- **Thin-coverage gap closed during reconciliation:** install/uninstall
  hardening, `de.freeze()`, and `main()` dispatch are now asserted directly
  (`InstallHardeningTests`, `FreezeCliTests`, `CliDispatchTests`).
- **`capture_refs` error-handling fix (behavior change):** a missing `node`
  now returns `ENV_ERROR_RC` (2) instead of escaping as an uncaught
  `FileNotFoundError`, mirroring `score.capture_app`. Covered by
  `CaptureRefsTests`.

### Reconciliation sweep

| Artifact | Disposition |
|---|---|
| `skills/design-eval/design_eval.py` (init/capture_refs/freeze/install/uninstall/main) | Verified against AC1–5; `capture_refs` hardened; `init()` now vendors `capture_lib.mjs`. |
| Splice mechanics (`fidelity_eval.py` register/splice) | Verified; `bash -n` clean both ways, manifest de-dup asserted. |
| `test_design_eval.py` install/freeze/dispatch classes | 19 tests green. |
| Reviews (`reviews/slice-02-{compliance,craft}.md`) | compliance re-pass after DoD/count correction; craft pass. |
