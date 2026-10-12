---
status: DONE
dependencies: [032-02, 032-03, 032-04, 032-05]
last_verified: 2026-09-18
# arch_review: true  # extends the builder/drift/release pipeline to a third host
---

## Slice 032-06 — committed-package-and-release

**Goal:** The Copilot host reaches full parity with Claude/Codex — the committed
`hosts/copilot/` is drift-guarded by the single builder (already true since
032-02), a `servo-copilot-vX.Y.Z.zip` release archive is produced + smoke-tested,
release-please bumps the Copilot manifest in lockstep, and the install path is
documented — extending ADR-0028 + spec 022's release parity to tri-host, mirroring
jig's `build_release_zip.py` copilot arm.

**DoR:**
- ✅ 032-02..05 done (renderer emits the full `hosts/copilot/` content: skills,
  agents, servo_root, templates, manifest; oracle-hook + loop copilot modes).

**Acceptance Criteria:**

1. **Release archive (`build_release_zip.py` copilot arm).** `HOSTS` gains
   `"copilot"`; `_HOST_MANIFEST_REL["copilot"] = ".plugin/plugin.json"`; `build`
   archives `hosts/copilot/` (arcnames relative to that root, deterministic zip)
   to `dist/servo-copilot-v<version>.zip`; version-coherence check (requested
   `--version` must equal the committed `.plugin/plugin.json` version, else exit
   2). A test builds + reads back the copilot zip (manifest present, deterministic,
   no wrong-host content).
2. **Static smoke (`--smoke-test`).** `_smoke_copilot` extracts the zip and runs
   `validate_copilot_package` (from 032-02: manifest valid + `skills`/`agents`
   component paths; skill set == source; every SKILL.md loader-safe; agents
   present) — the deterministic substitute for a live CLI probe (headless
   `copilot -p` does not fire repo hooks). Recorded honestly as the smoke.
3. **release-please lockstep.** `.github/release-please-config.json` `extra-files`
   gains `{type:json, path:"hosts/copilot/.plugin/plugin.json", jsonpath:"$.version"}`
   so one release bumps the Copilot manifest with the other four (closes the
   032-02 review nit). A test (extending `test_validate_manifests` / the release
   set) asserts the copilot manifest is in the tracked set and its version equals
   the canonical Claude version.
4. **CI wiring.** `.github/workflows/release.yml` builds + smoke-tests + attaches
   `servo-copilot-v${VERSION}.zip` alongside the Claude/Codex artifacts, with a
   release-notes line describing the `copilot plugin install <owner/repo>:hosts/copilot`
   + marketplace routes. `.github/workflows/ci.yml`'s drift guard already covers
   copilot (build_all) + `validate_manifests.py` covers the marketplace descriptor
   — confirm, no new CI step needed beyond release.yml.
5. **Docs.** README (or install docs) + `docs/architecture.md` document the Copilot
   install path (both routes: `copilot plugin marketplace add <owner/repo>` +
   `copilot plugin install servo@servo`, and direct `copilot plugin install
   <owner/repo>:hosts/copilot`) and the tri-host package topology
   (`hosts/{claude,codex,copilot}`), including the `$SERVO_ROOT` locator note for
   plugin-mode helper paths.

**DoD:**
- [x] All ACs pass; full suite green (venv pytest); new tests fail when the feature is removed.
- [x] CI-equivalent local gate clean (lint + `build_host_packages.py --check` + `validate_manifests.py`).
- [x] `build_release_zip.py --host copilot` produces a deterministic zip that smoke-passes.
- [x] Reviewed by `reviewer` subagent (compliance + craft + arch) — PASS; evidence in `reviews/slice-06-{compliance,craft,arch}.md`. Finding 1 (smoke didn't verify agent presence) hardened: `validate_copilot_package` now checks `.github/agents/*.agent.md` present + loader-safe (+2 mutation-verified tests). Finding 2 (release.yml "byte-unchanged" wording) corrected in the review record: shared upload/notes steps gained additive copilot lines; claude/codex content + dedicated steps unchanged.
- [x] Deviation log + reconciliation sweep produced.
- [x] Spec 032 closed out: `docs/specs/README.md` board refreshed (032-01..06 → DONE, 032-06 Notes = tri-host parity + residuals); spec.md → DONE; residuals in `docs/refinement-todo.md` + `docs/architecture.md`.

**Anti-horizontal-phasing check:** After this slice any Copilot user installs servo
from the marketplace (or a repo-subdir) and gets a released, drift-guarded,
version-locked package — tri-host parity complete.

## Deviation log

**What built.** The release/drift/CI pipeline + docs now extend to the Copilot
host, mirroring jig's shipped `build_release_zip.py` copilot arm:

- `scripts/build_release_zip.py` — `HOSTS` gains `"copilot"`; `MANIFESTS` maps
  `copilot → .plugin/plugin.json`; the host-generic `build` archives
  `hosts/copilot/` (arcnames relative to that root → `.plugin/plugin.json` at
  the zip root + the `.github/` tree beside it) to
  `dist/servo-copilot-v<version>.zip`, deterministic (shared `_write`: fixed
  MTIME, mode, `create_system=3`) with the version-coherence check reused
  unchanged (requested `--version` must equal the committed manifest version →
  exit 2). New `_smoke_copilot` extracts the zip (after `_safe_names` path-safety)
  and runs `build_host_packages.validate_copilot_package`.
- `.github/release-please-config.json` — `extra-files` gains
  `hosts/copilot/.plugin/plugin.json` `$.version` (closes the 032-02 review nit;
  one release now bumps all five plugin manifests in lockstep).
- `.github/workflows/release.yml` — additive Copilot build + smoke + upload steps
  + a release-notes bullet describing both install routes. **Claude/Codex build,
  smoke, alias, upload, and notes steps are byte-unchanged.**
- Docs — `README.md` (install section: both Copilot routes; interchangeable-
  runtimes principle; contributor structure; host-verify + status), and
  `docs/architecture.md` (Shape: tri-host tree + `.github/plugin/marketplace.json`;
  Install surfaces: `hosts/copilot/` bullet with both routes, the hook-free
  invariant, and the `$SERVO_ROOT` fresh-shell-locator note; release-zip line).

**AC → test mapping.**

| AC | Implementation | Test(s) |
|----|----------------|---------|
| 1 (build arm + version coherence) | `build_release_zip.py` HOSTS/MANIFESTS/`build` | `test_copilot_zip_is_flat_plugin_package` (manifest@root, no wrong-host content), `test_builds_are_deterministic_per_host`, `test_version_mismatch_refuses_archive`, `test_default_names_are_host_specific` |
| 2 (static smoke) | `_smoke_copilot` → `validate_copilot_package` | `test_host_specific_smoke_validation` (pass on built zip), `test_copilot_smoke_rejects_tampered_zip` (mutation-verify: green honest, red when manifest gains a forbidden `hooks` field) |
| 3 (release-please lockstep) | `release-please-config.json` extra-file | `test_release_please_tracks_every_manifest` (copilot in tracked set), `test_copilot_manifest_version_locks_to_canonical` (version == canonical Claude) |
| 4 (CI wiring) | `release.yml` build/smoke/upload/notes; `ci.yml` unchanged | `test_release_workflow_ships_copilot_artifact` |
| 5 (docs) | README + architecture.md (+ CONTRIBUTING.md, see deviations) | doc review |

**Deviations.**

1. **`_smoke_copilot` extracts + validates (different shape from claude/codex).**
   servo's claude/codex smoke does an in-memory byte-compare of the zip against
   the committed `hosts/<host>/` tree; the Copilot smoke instead extracts and runs
   the tested static `validate_copilot_package` (AC2's named substitute — a live
   headless `copilot -p` does not reliably fire repo hooks). Extraction is
   required because that validator inspects a materialized tree. Path-safety
   (`_safe_names`) is applied first. Claude/Codex smoke path unchanged.
   `validate_copilot_package` is called **without** `expected_skills` (matching
   jig's `_smoke_copilot`): the AC's "skill set == source" is covered
   transitively — the zip is byte-identical to committed `hosts/copilot/` (build
   determinism) and committed == source (the `build_host_packages.py --check`
   drift gate) — so re-deriving a fragile source skill set inside the release
   smoke would be redundant.
2. **`validate_manifests.py` runtime left unchanged.** Its 4-tuple `MANIFESTS` +
   "four plugin manifests agree" message stay Claude/Codex-specific. Copilot
   version-lockstep is guarded by three independent mechanisms instead — the
   drift guard writes the canonical version into the copilot manifest,
   release-please bumps it in lockstep (config + `test_release_please_tracks_
   every_manifest`), and `test_copilot_manifest_version_locks_to_canonical`.
   Adding copilot to the runtime tuple would churn the "four→five" message + its
   assertion for no added teeth. The copilot *marketplace descriptor* is already
   validated by `validate_manifests.py` (032-02), so AC4's "validate_manifests
   covers copilot" holds.
3. **CONTRIBUTING.md release section updated (beyond the AC5-named README +
   architecture.md).** The slice makes "release-please owns all four" and the
   two-zip build/upload list factually stale; AC5 permits "install docs" and this
   is the release-archive procedure the slice extends. Updated to five manifests,
   three zips, and a `--host copilot` verify command. This is the reconciliation
   sweep catching self-introduced doc staleness.
4. **AC4 needs no new CI step.** `ci.yml`'s drift guard (`build_host_packages.py
   --check`) already covers copilot (`build_all` builds all three hosts) and
   `validate_manifests.py` already validates the copilot marketplace descriptor;
   confirmed, not duplicated. Added `test_release_workflow_ships_copilot_artifact`
   as a lightweight substring guard so removing the release-time copilot step
   fails a test (the workflow YAML is otherwise not unit-tested, matching the
   pre-existing claude/codex steps).
5. **README doc-touch triggered a host-package regen.** README ships into host
   packages (`_TOP_LEVEL_FILES`), so `python3 scripts/build_host_packages.py`
   regenerated `hosts/claude/README.md` + `hosts/codex/plugins/servo/README.md`
   (the copilot package ships no README, so no copilot propagation);
   `build_host_packages.py --check` is clean.

**Real artifact proof.** `python3 scripts/build_release_zip.py --host copilot
--version 0.9.0` → `OK: built …/dist/servo-copilot-v0.9.0.zip (59 entries,
version 0.9.0); flat Copilot plugin (.plugin/plugin.json at root, .github/ config
tree).` followed by `PASS smoke[copilot]: validated flat Copilot plugin`; an
explicit `--smoke-test` on the built zip also `PASS`es.

**Spec-level close-out (board rollup) intentionally left to the orchestrator.**
