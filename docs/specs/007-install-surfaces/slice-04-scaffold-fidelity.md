---
status: DONE
dependencies: []
last_verified:
---

## Slice 007-04 — scaffold-fidelity

**Goal:** Harden the project-local scaffold output so generated docs,
commands, links, helper paths, and version provenance reflect the target
copy rather than stale plugin-checkout assumptions. End-to-end value:
scaffolded servo does not hand users commands that fail immediately.

**DoR:**

- 007-03 DONE.
- At least one scaffolded temp target fixture exists.
- Known jig gaps from specs 046 and 047 have been reviewed.
- Concrete scaffold-mode gaps observed during the 007-03 independent review
  (see 007-03 deviation log) must be closed by this slice's AC1/AC6: the
  vendored oracle-install command is not self-contained (templates at
  `.claude/servo/templates` vs `plugin_root()` fallback `.claude/templates`),
  and vendored `SKILL.md` copies still reference `${CLAUDE_PLUGIN_ROOT}`.

**Acceptance Criteria:**

1. **No stale plugin-root commands.** Scaffolded `SKILL.md` files and
   generated helper instructions do not contain
   `${CLAUDE_PLUGIN_ROOT}` for commands meant to run in scaffold mode.
2. **Runnable examples.** Every scaffold-mode command example emitted by
   servo docs or generated files is exercised in a temp scaffold target,
   or explicitly marked as illustrative and excluded by a testable
   marker.
3. **Local links resolve.** Relative links in scaffolded Markdown files
   resolve inside the scaffold target or are rewritten/removed.
4. **Version provenance.** Scaffolded manifests record the version from
   `.claude-plugin/plugin.json`, not a hard-coded fallback.
5. **Idempotent upgrade.** Re-running scaffold mode updates managed
   files and the scaffold manifest while preserving unmanaged files
   under `.claude/`.
6. **No source checkout references.** The scaffold verifier detects
   managed files that reference the original servo checkout for runtime
   helper paths.

**DoD:**

- [x] Tests cover stale path detection, command smoke, link resolution,
  version provenance, and idempotent upgrade. _27 new tests across
  `scripts/test_scaffold_runtime.py` (StalePluginRootRewriteTests,
  VendoredOracleInstallSelfContainedTests, ScaffoldCommandClassificationTests,
  LinkResolutionTests, VersionProvenanceTests,
  IdempotentUpgradePreservesUnmanagedTests),
  `scripts/test_verify_install.py` (ScaffoldStaleSourceReferenceTests), and
  `skills/scaffold-init/test_scaffold.py` (TemplatesRootPluginModeTests)._
- [x] The verifier output distinguishes "missing artifact" from
  "artifact exists but points at the wrong source." _New
  `stale_source_reference` reason, distinct from `artifact_missing` /
  `manifest_missing`; covered by
  `test_stale_reference_is_distinct_from_artifact_missing`._
- [x] Deviation log produced under this slice.
- [x] Independent review pass completed before DONE. _Independent reviewer
  (general-purpose subagent), 2026-06-01 — **PASS**. All 6 ACs met and
  independently verified (zero `${CLAUDE_PLUGIN_ROOT}` / `../` links in
  vendored files; self-contained oracle-install with `CLAUDE_PLUGIN_ROOT`
  unset; plugin/source mode byte-for-byte preserved; AC2 classification proven
  exhaustive via an injected command; `stale_source_reference` distinct from
  `artifact_missing`). No design-principle violations. Findings: test-count
  corrected 33→27 (above); two non-blocking notes added to the deviation log._

**Anti-horizontal-phasing check:** After this slice, scaffold mode is not
only present; it is polished enough that a user can follow its generated
instructions without knowing servo's source checkout layout.

**Deviation log (after reconciliation):**

- **Scaffold-aware `_templates_root` (closes the 007-03 self-contained
  gap).** Added `_templates_root()` to `skills/scaffold-init/scaffold.py`:
  it returns the vendored `parents[2]/servo/templates` when that directory
  exists (scaffold mode — `scaffold.py` is at
  `<target>/.claude/skills/servo-scaffold-init/scaffold.py`, so `parents[2]`
  is `<target>/.claude`), else falls back to `plugin_root()/templates`
  (plugin/source mode). `_load_template`/`_load_fragment` now call it. The
  source checkout has no `<repo>/servo/templates` directory, so the fallback
  guarantees plugin/source-mode behavior is byte-for-byte unchanged; proven
  by `TemplatesRootPluginModeTests` and the full `test_scaffold.py` staying
  green. This makes the vendored oracle-install (`scaffold.py <target>`)
  self-contained with `CLAUDE_PLUGIN_ROOT` unset.
- **SKILL.md rewrite rule (AC1).** During vendoring, `scaffold_runtime.py`
  rewrites — for every contract skill `name` — the literal
  `${CLAUDE_PLUGIN_ROOT}/skills/<name>/` to
  `.claude/skills/<skill_prefix><name>/` in each copied `SKILL.md`. After
  this no `${CLAUDE_PLUGIN_ROOT}` remains in vendored `SKILL.md` files.
- **`.py` helpers are NOT rewritten (scoping).** The vendored `scaffold.py`
  / `gate.py` / `loop.py` are left byte-identical: they are scaffold-aware
  via `_templates_root`, and their docstring mentions of
  `CLAUDE_PLUGIN_ROOT` are accurate dual-mode documentation, not stale
  commands. The AC1 "no stale plugin-root commands" guarantee is scoped to
  `SKILL.md` command examples; the verifier's `stale_source_reference` scan
  is likewise scoped to managed markdown (SKILL.md + agents), not helpers.
- **Link-strip rule (AC3).** For each `[text](dest)` in a vendored `.md`
  file (SKILL.md + agents), the link is reduced to plain `text` (the
  `](dest)` is dropped) when `dest` is relative (not `http(s)://`, not
  `mailto:`, not a bare `#anchor`) and either escapes the scaffold target or
  does not resolve to an existing file under it. This strips the agents'
  `[ADR-0003](../docs/decisions/adr-0003-...)` links while preserving the
  visible `ADR-0003` text. Links that resolve inside the target are kept
  (covered by `test_resolving_link_is_kept`).
- **AC2 classification approach (testable marker = the test itself).** A
  fidelity test parses every vendored `SKILL.md`, extracts each shell
  command invoking a vendored helper
  (`python3 .claude/skills/servo-*/*.py ...`), and classifies it
  exhaustively in the test: RUNNABLE helpers (`scaffold.py` in its
  `<target>`, `<target> --force`, and `detect <target>` forms) are actually
  executed in a temp scaffold target with `CLAUDE_PLUGIN_ROOT` unset and
  asserted to exit 0; ILLUSTRATIVE helpers (`gate.py` — needs a runnable
  oracle; `loop.py` — needs a live `claude` and burns real cost) are listed
  with a reason. `test_every_scaffold_command_is_classified` FAILS if a
  helper appears in the vendored docs that is in neither set, so a new
  unclassified example cannot silently ship unrun. (Chose the in-test marker
  over an in-doc marker.)
- **`stale_source_reference` verifier reason (AC6 / DoD).** `verify_install.py
  scaffold` scans managed markdown for (a) a literal `${CLAUDE_PLUGIN_ROOT}`
  and (b) relative links that escape or fail to resolve under the target,
  emitting a NEW `stale_source_reference` failure distinct from
  `artifact_missing` / `manifest_missing`. Only existing managed files are
  scanned; a missing file remains `artifact_missing`.
- **Version provenance (AC4).** No change to 007-03's behavior was needed —
  `scaffold-install.json.source_version` already comes from `plugin.json`
  via `plugin_version()`, which raises rather than returning a baked-in
  default. Added `VersionProvenanceTests` asserting
  `source_version == plugin.json.version`, that `scaffold_runtime.py` has no
  hardcoded `source_version` literal, and that `plugin_version()` raises when
  the manifest version is absent.
- **Idempotent upgrade preserving unmanaged files (AC5).** No change to
  007-03's overwrite-only-managed-paths / delete-nothing behavior was needed.
  Added `IdempotentUpgradePreservesUnmanagedTests`: an unmanaged
  `<target>/.claude/skills/my-custom/note.txt`, a `<target>/.claude/settings.json`,
  and an unmanaged agent survive a re-run untouched while managed files and
  the manifest are refreshed.
- **AC2 smoke is helper-granular (reviewer note).** The runnable-command
  smoke executes a fixed arg-set per helper, not a literal replay of each
  documented argument form; `test_every_scaffold_command_is_classified`
  enforces exhaustiveness at *helper* granularity. A newly documented
  *argument form* of an already-classified helper would ship without its own
  smoke run. Acceptable today (the three documented `scaffold.py` forms match
  the executed arg-sets); revisit if scaffold-mode docs grow new flags.
- **`verify_install.py scaffold` reports `version=<unknown>` (intentional).**
  `verify_scaffold` sets `version=None` even though `scaffold-install.json`
  carries `source_version`; the spec does not require scaffold mode to report
  a version. Flagged so a future slice doesn't mistake the `<unknown>` human
  output for a regression.

---

