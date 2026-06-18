---
status: DONE
dependencies: [adr-0013]
last_verified: 2026-06-18
arch_review: true
---

## Slice 014-01 - breadcrumb marker writers

**Goal:** Implement the ADR-0013 servo availability marker across the source,
verification, and runtime-scaffold writer paths, with docs and refinement
records updated so downstream tooling can consume the breadcrumb as an
advisory hint.

**DoR:**

- [x] ADR-0013 Accepted.
- [x] Existing install-surface behavior has regression coverage.

**Acceptance Criteria:**

1. **Contract recorded.** An accepted ADR defines the marker path, schema
   version, required fields, advisory semantics, and initial writer paths.
2. **Source scaffold writer.** `skills/scaffold-init/scaffold.py` writes
   `${XDG_STATE_HOME:-$HOME/.local/state}/servo/available.json` after a
   successful source/release plugin-root scaffold install, with
   `source_kind: "scaffold-init"`.
3. **Runtime scaffold writer.** `scripts/scaffold_runtime.py` writes the same
   marker after successful project-local runtime scaffolding, with
   `source_kind: "scaffold-runtime"`.
4. **Verification writer.** `scripts/verify_install.py plugin <root>` writes
   the same marker after successful plugin-root verification, with
   `source_kind: "verify-plugin"`.
5. **Best-effort safety.** All marker writers warn but keep their primary
   success path green when the marker path cannot be written.
6. **Docs reconciled.** The README, architecture overview, ADR index, and
   refinement-todo entry all point to the accepted ADR or implemented
   breadcrumb behavior.

**DoD:**

- [x] Tests cover all three writer paths, `XDG_STATE_HOME`, marker payload
  shape, and best-effort write failure behavior.
- [x] Compliance, craft, and architecture reviews recorded under this slice.
- [x] Reconciliation review recorded under this slice.
- [x] `docs/specs/README.md` regenerated.

**Anti-horizontal-phasing check:** After this slice, a sibling tool can read
one documented filesystem marker to decide whether to offer a servo scaffold
nudge, without invoking servo or knowing which install surface produced it.

### Deviation log (after reconciliation)

- **Retroactive spec container.** This work began as a refinement-todo and ADR
  follow-up. The implementation existed before this spec file so the formal
  compliance/craft/reconciliation evidence would have a durable, standard
  project location.
- **Verification writer added during reconciliation prep.** The ADR initially
  covered source scaffold and runtime scaffold paths. `verify_install.py plugin
  <root>` was added as the explicit local-clone confirmation path so users who
  verify a plugin root before using `/servo:scaffold-init` still refresh the
  breadcrumb.
- **Manual ADR index update.** `adr.py index docs/decisions` degraded legacy
  servo ADR rows because older records do not all match the current jig ADR
  parser shape. The ADR-0013 row was added manually and the previous index
  content was preserved.
- **Local lint substitution.** `ruff` and `pytest` are not installed in this
  worktree environment, so verification used `unittest`, `py_compile`, and
  `git diff --check` locally.
- **Craft nit fixed.** The craft pass found that module-level test
  `XDG_STATE_HOME` overrides could leak across combined `unittest` imports.
  The tests now set and restore the default state-home in `setUpModule()` /
  `tearDownModule()` for each touched module, while individual breadcrumb
  tests still override the environment locally.
- **Duplicated marker helper accepted.** The architecture pass noted that the
  marker path, payload, and atomic-write helpers are duplicated across the
  three self-contained install surfaces. This is intentional for now so
  release/plugin verification, runtime scaffold, and source scaffold remain
  independently runnable; future schema/path changes must update all three.
