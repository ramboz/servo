---
status: RECONCILED
kind: feature
dependencies: [adr-0043]
last_verified: 2026-10-12
arch_review: true
claimed_by: claude/adr-0034-specs-028-jig-fe54d4
---

## Slice 034-01 - installed-oracle

**Goal:** A Copilot consumer resolves the installed runtime, scaffolds an oracle
and scores it from a clean directory without Claude or Jig.

**DoR:**
- ADR-0043 accepted after frame critique; existing spec 032 package reused.
- Native CLI discovers the package; package/runtime/project roots are distinct.

**Acceptance Criteria:**

1. **Installed root.** Documented locator works with a custom COPILOT_HOME,
   paths containing spaces, different marketplace names, multiple installs,
   project-owned runtime and absent runtime. Missing runtime is an explicit error.
2. **Executing runtime authority.** Copilot's packaged scaffold resolves its
   own templates even if an unrelated CLAUDE_PLUGIN_ROOT or SERVO_ROOT is set.
   Availability metadata names Servo and the actual native package version,
   without a Claude compatibility tree or correction flags. Source/Claude/Codex
   template and marker behavior remains compatible.
3. **Same oracle authority.** A clean installed scaffold emits oracle.sh,
   .servo/install.json and refinement notes. Packaged quality-gate returns
   versioned pass/below_threshold/env_error and timeout with unchanged 0/1/2 exits.
4. **Actual install.** Isolated-home native marketplace add/install/list and
   exact documented helper execution are observed separately from static tests.
   All public skills/agents/shared helpers/templates and release zips remain
   generated, manifest-valid and drift-guarded.
5. **No coupling.** No mandatory Jig dependency, automatic meta-judge install,
   broad host-name prose substitution or pre-rendered consumer instruction tree.
   The standalone locator remains the fallback; no unproved SessionStart
   publisher is represented as delivered.

**DoD:**
- [x] Focused root/scaffold/gate regression tests show witnessed red-to-green.
- [x] Required compliance, craft and architecture passes clear.
- [x] Installed/zip checks, all-host drift and established full CI gates pass.
- [x] Deviation log, documentation sweep and final reconciliation review clear.

## Assumptions

None. Installed discovery and helper behavior are verified by executed probes,
not inferred from a static manifest.

**Anti-horizontal-phasing check:** The consumer compiles and evaluates its
project without Claude, not merely installs new files.

### Implementation notes (bounded 2026-10-12)

- Executing native scaffold helpers use their own `.github` runtime; unrelated
  `CLAUDE_PLUGIN_ROOT` and `SERVO_ROOT` do not redirect templates or metadata.
  Availability `source_path` is the runtime; identity/version come from the
  parent package's `.plugin/plugin.json`. Source/Claude/Codex behavior is retained.
- `scripts/test_copilot_installed_runtime.py` uses `build_all`-generated fixtures,
  isolated homes and tool stubs: 16 tests, witnessed red (10 failing assertions
  including subtests) to green (16 passed). Packaged gate 0/1/2 and timeout were
  already correct and required no implementation change.
- Locator coverage includes custom homes with spaces, marketplace-independent
  identity, numeric versions/mtime ties, project-owned bootstrap, missing-runtime
  diagnostics and direct native script-path fallback. Installed-store ordering
  precedes that fallback; no live-install configuration discovery was added.
- After coordinator regeneration, combined scaffold, builder, gate and new
  regressions passed all 204 tests and 59 subtests. The earlier committed-host
  byte-identity failure was expected drift pending regeneration, not weakened.
- These fixtures are not native marketplace install evidence. Actual CLI/helper
  commands, release zip/full CI gates, generated hosts and independent reviews
  remain coordinator-owned; no install-store-copy claim or completion flag added.

### Deviation log (after reconciliation)

1. Reused closed spec032's generated package and standalone locator. No unproved
   SessionStart publisher was added; known-package direct invocation is the live
   local-marketplace fallback. This delivers supported deterministic behavior,
   not native autonomy or native frozen-score completion.
2. Fixed native executing-runtime authority and parent manifest metadata; no gate
   production changes were needed. All-host generation preserves source and
   sibling host behavior.
3. Craft's nonblocking PATH-isolation nit was corrected with only explicitly
   seeded tool symlinks. Architecture's stale two-package wording was corrected.
   Actual local native install/clean-consumer evidence is separated from
   copied-layout fixtures and static zip checks in delivery-evidence.md.
4. Final reconciliation found README's live-status link still pointed to the
   older roadmap. It now points to the regenerated status board; the historical
   roadmap is not rewritten to fabricate completion.

### Reconciliation sweep

| Surface | Disposition | Rationale |
|---------|-------------|-----------|
| Runtime roots / marker / templates / builder | updated | Executing native authority, parent metadata and tested locator/bootstrap. |
| Generated Claude/Codex/Copilot packages | updated | Canonical regeneration; no Jig machinery or pre-rendered consumer tree. |
| README / architecture / vision | updated | Supported deterministic delivery versus unavailable autonomy; portable README links. |
| Roadmap | no-op | Historical horizon framing retained; live capability status links to derived board instead. |
| Marketplace / manifests / release workflow | no-op | Reused spec032 mechanism; native CLI discovery and four-manifest/static zip checks pass. |
| ADR index / status board | updated | Derived helper regeneration; old accepted records untouched. |
| Primer / conventions / inbox | no-op | None exist at project root; no new convention or unrelated work. |
| Memory | updated | Runtime/package separation and merge-fixture gotchas recorded by memory.py. |
| Team advisory | deferred | people.md bootstrap is unrelated to this port; no user-owned people data invented. |
| Full CI / final reconciliation | updated | Independent verdicts clear; synchronized exact CI passes2255 tests plus all150 install tests/manifests/Ruff/drift gates. |

### Close-out (post-DONE)

- [ ] Regenerate board and retain package/runtime-root and supported-scope notes.
