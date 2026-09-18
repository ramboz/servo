---
status: IN_PROGRESS
dependencies: [028-02, 028-03, 028-04, 028-05]
last_verified:
# arch_review: true  # extends the builder/drift/release pipeline to a third host
---

## Slice 028-06 — committed-package-and-release

**Goal:** The Copilot host reaches full parity with Claude/Codex — the committed
`hosts/copilot/` is drift-guarded by the single builder (already true since
028-02), a `servo-copilot-vX.Y.Z.zip` release archive is produced + smoke-tested,
release-please bumps the Copilot manifest in lockstep, and the install path is
documented — extending ADR-0028 + spec 022's release parity to tri-host, mirroring
jig's `build_release_zip.py` copilot arm.

**DoR:**
- ✅ 028-02..05 done (renderer emits the full `hosts/copilot/` content: skills,
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
   `validate_copilot_package` (from 028-02: manifest valid + `skills`/`agents`
   component paths; skill set == source; every SKILL.md loader-safe; agents
   present) — the deterministic substitute for a live CLI probe (headless
   `copilot -p` does not fire repo hooks). Recorded honestly as the smoke.
3. **release-please lockstep.** `.github/release-please-config.json` `extra-files`
   gains `{type:json, path:"hosts/copilot/.plugin/plugin.json", jsonpath:"$.version"}`
   so one release bumps the Copilot manifest with the other four (closes the
   028-02 review nit). A test (extending `test_validate_manifests` / the release
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
- [ ] All ACs pass; full suite green (venv pytest); new tests fail when the feature is removed.
- [ ] CI-equivalent local gate clean (lint + `build_host_packages.py --check` + `validate_manifests.py`).
- [ ] `build_release_zip.py --host copilot` produces a deterministic zip that smoke-passes.
- [ ] Reviewed by `reviewer` subagent (compliance + craft + arch).
- [ ] Deviation log + reconciliation sweep produced.
- [ ] Spec 028 closed out: slice board refreshed; load-bearing invariants + residuals migrated to the status-board Notes / refinement-todo.

**Anti-horizontal-phasing check:** After this slice any Copilot user installs servo
from the marketplace (or a repo-subdir) and gets a released, drift-guarded,
version-locked package — tri-host parity complete.
