---
status: DRAFT
dependencies: [028-02, 028-03, 028-04, 028-05]
last_verified:
# arch_review: true  # extends the builder/drift/release pipeline to a third host
---

## Slice 028-06 — committed-package-and-release

**Goal:** The Copilot host reaches full parity with Claude and Codex — a
committed, drift-guarded `hosts/copilot/` built by servo's single builder, a
`servo-copilot-vX.Y.Z.zip` release archive, and per-host install verification —
extending ADR-0028 + spec 022's release parity to tri-host.

**DoR:**
- ✅ 028-02..05 done (renderer emits the full `hosts/copilot/` content).

**Acceptance Criteria:**

1. **Single builder + drift guard.** servo's builder regenerates `hosts/copilot/`
   alongside `hosts/claude`/`hosts/codex`; CI regenerates and fails on a dirty
   `git diff` for the copilot package too. A test proves a stale `hosts/copilot/`
   is caught.
2. **Release archive.** The release pipeline produces `servo-copilot-vX.Y.Z.zip`
   from the committed package, and release-please is coordinated to bump the
   Copilot manifest version in lockstep (no hand-edited versions), extending spec
   022.
3. **Per-host verification.** A Copilot install/smoke check runs in a Copilot CLI
   environment (or the closest deterministic substitute, recorded honestly),
   independent of the Claude/Codex checks.
4. **Docs.** README/install docs + `docs/architecture.md` document the Copilot
   install path and the tri-host package topology.

**DoD:**
- [ ] All ACs pass; full suite green; new tests fail when the feature is removed.
- [ ] CI-equivalent local gate clean (lint + host-package drift `--check`).
- [ ] Reviewed by `reviewer` subagent (compliance + craft; arch pass).
- [ ] Deviation log + reconciliation sweep produced.
- [ ] Spec 028 closed out: compress the Active-specs entry; migrate load-bearing
      invariants to the status-board Notes column.

**Anti-horizontal-phasing check:** After this slice any Copilot user installs
servo with one command from the marketplace and gets a released, drift-guarded
package.
