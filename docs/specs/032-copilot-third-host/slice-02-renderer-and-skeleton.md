---
status: DONE
dependencies: [032-01, adr-0038]
last_verified: 2026-09-18
# arch_review: true  # adds the Copilot host renderer + dispatch wiring
---

## Slice 032-02 — renderer-and-skeleton

**Goal:** A Copilot user can install servo and invoke its skills — the walking
skeleton: a Copilot arm in servo's builder that emits a committed, drift-guarded
`hosts/copilot/` whose skills load under Copilot CLI, following jig's shipped
`build_copilot_plugin.py` + `CopilotScaffoldRenderer` (ported as functions into
servo's function-based `scripts/build_host_packages.py`).

**DoR:**
- ✅ 032-01 done: contract confirmed vs jig's shipped package + live CLI (manifest
  shape, `.github/` layout, loader rules, `$SERVO_ROOT`/bug 036, marketplace/bug 035).

**Acceptance Criteria:**

1. **Copilot arm + dispatch.** `HOSTS` gains `"copilot"`; `build_all` renders
   `hosts/copilot/` alongside `hosts/claude`/`hosts/codex` in one run; **Claude and
   Codex output stay byte-for-byte unchanged** (a test asserts this).
2. **`.github/` layout + legacy manifest.** The package is
   `hosts/copilot/.plugin/plugin.json` (`name`/`version` [= canonical Claude
   version] /`description` + component-path fields `skills:".github/skills"`,
   `agents:".github/agents"` — **no `hooks`**) with skills under
   `.github/skills/<name>/SKILL.md`, `servo_root.py` at `.github/scripts/`, and
   `templates/` copied to `.github/templates/` **unrendered** (canonical
   `${CLAUDE_PLUGIN_ROOT}` intact). `.github/agents/` is populated by 032-03.
3. **Loader-safe skill render (`_render_copilot_skill`, distinct from Codex).**
   (a) strip the `servo:` namespace from the loaded `name:`, then assert the result
   is `:`-free (raise on residual `:`); (b) jig's `loader_safe_description` — keep
   the `description:` byte-for-byte if ≤1024, else word-boundary-truncate the
   frontmatter value + suffix **and append the full original description to the
   body** as a note. A test proves an over-limit source skill (e.g. `agent-loop`,
   ~2138 chars) renders ≤1024 in Copilot frontmatter with full text in the body,
   while Claude/Codex stay byte-unchanged.
4. **`$SERVO_ROOT` plugin-mode path rewrite (jig bug 036).** Every
   `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/<helper>.py` in a rendered SKILL.md body
   becomes `$SERVO_ROOT/skills/<skill>/<helper>.py`; a `servo_root.py` fresh-shell
   locator ships at `.github/scripts/`; a root-resolution note (self-contained
   locator one-liner, no SessionStart carrier) is injected into each skill that
   references the var. Templates are exempt (ship unrendered). A test asserts no
   `${CLAUDE_PLUGIN_ROOT}` survives in a rendered SKILL.md and the locator + note
   are present.
5. **Marketplace descriptor (jig bug 035).** A repo-root
   `.github/plugin/marketplace.json` with `{"name":"servo","owner":{…},"plugins":
   [{"name":"servo","source":"./hosts/copilot",…}]}` (relative-string source, not a
   git-subdir object). `scripts/validate_manifests.py` routes it through a
   Copilot-specific source-shape check.
6. **Scaffold host-inference (jig bug 034).** The packaged `scaffold-init` helper,
   when run from the Copilot package, infers the Copilot host from the
   `.plugin`/`.github` layout and does not default to Claude (emits `AGENTS.md` /
   `host_renderer: "copilot"`, no `.claude` tree). A test covers the inference.
7. **Skeleton installs + a skill loads.** The rendered package passes a static
   `validate_copilot_package`-style check (manifest valid + component paths; skill
   set == source; SKILL.md frontmatter loader-safe) as the deterministic install
   substitute; a live `copilot plugin install <dir>` + `copilot skill list` is run
   and recorded honestly (residual noted if headless firing is unobservable).

**DoD:**
- [x] All ACs pass; full suite green (1798 passed); new tests fail when the feature is removed (mutation-verified).
- [x] Claude/Codex host output unchanged (drift guard clean for those hosts).
- [x] `build_host_packages.py --check` clean after regenerating `hosts/copilot/`.
- [x] Reviewed by `reviewer` subagent (compliance + craft + arch) — PASS; evidence in `reviews/slice-02-{compliance,craft,arch}.md`.
- [x] Deviation log + reconciliation sweep produced (in this slice; reviewer reconciliation notes recorded).

**Anti-horizontal-phasing check:** After this slice a Copilot user installs servo
and its skills load — observable end-to-end value.

## Deviation log

Implemented ACs 1–5 and 7 as written; AC6 was interpreted (see below). Suite
green + all four new guards mutation-verified. Not committed (working tree left
dirty for owner review). `All ACs pass` DoD box left unticked pending the AC6
adjudication below; the suite-green + mutation-verified halves of that box are
satisfied.

### What was built
- `scripts/build_host_packages.py` (+~300 lines): `"copilot"` added to `HOSTS`;
  a Copilot arm in `build_all` rendering `hosts/copilot/` (`.plugin/plugin.json`
  legacy manifest + `.github/{skills,scripts,templates}`). jig's class-based
  renderer ported as pure functions: `_render_copilot_skill`,
  `_copilot_safe_skill_name`, `_loader_safe_description`,
  `_read_skill_description`, `_replace_description_field`, `_replace_name_line`,
  `_split_frontmatter`, `_frontmatter_value`, `_ensure_servo_root_note`; plus
  `_copy_copilot_tree`, `_write_copilot_manifest`, and a static
  `validate_copilot_package`.
- `scripts/servo_root.py` (new): `$SERVO_ROOT` fresh-shell locator, ported from
  jig's `jig_root.py` (JIG→SERVO; manifest identity `.plugin/plugin.json`
  `name=="servo"`; sentinel `skills/agent-loop/loop.py`). Copied into the
  package at `.github/scripts/servo_root.py`.
- `.github/plugin/marketplace.json` (new, committed source): Copilot marketplace
  descriptor with relative-string `source: "./hosts/copilot"` (bug 035).
- `scripts/validate_manifests.py`: `_copilot_marketplace_errors` + wiring to
  validate the descriptor's Copilot source-shape (string, not git-subdir object).
- `hosts/copilot/**` (56 files, regenerated committed package). `--check` clean.

### AC → gating test names
- **AC1** (arm + dispatch; Claude/Codex byte-identical):
  `HostPackageTests::test_copilot_arm_renders_committed_layout`,
  `::test_copilot_arm_leaves_claude_and_codex_byte_identical`.
- **AC2** (`.github/` layout + legacy manifest w/ no `hooks`; templates
  unrendered): `::test_copilot_arm_renders_committed_layout`,
  `::test_copilot_skill_set_matches_source`,
  `::test_copilot_templates_ship_unrendered`.
- **AC3** (name strip+assert; keep-or-truncate-and-preserve description):
  `::test_copilot_skill_names_are_namespace_safe`,
  `::test_copilot_over_limit_description_truncated_and_body_preserves_full_text`,
  `::test_copilot_short_description_skill_renders_byte_for_byte`;
  `CopilotRenderUnitTests::test_safe_skill_name_strips_servo_namespace`,
  `::test_safe_skill_name_raises_on_residual_colon`,
  `::test_loader_safe_description_truncates_at_word_boundary`,
  `::test_loader_safe_description_keeps_short_text`,
  `::test_render_copilot_skill_rejects_colon_name`.
- **AC4** (`$SERVO_ROOT` rewrite + locator + note, no SessionStart carrier):
  `::test_copilot_rewrites_plugin_root_and_injects_root_note`,
  `::test_copilot_no_braced_plugin_root_survives_any_skill`,
  `::test_copilot_servo_root_locator_shipped`;
  `ServoRootLocatorTests::test_resolves_installed_plugin`,
  `::test_returns_none_when_no_runtime`.
- **AC5** (marketplace descriptor):
  `ManifestValidationTests::test_copilot_marketplace_descriptor_uses_relative_string_source`,
  `::test_copilot_marketplace_rejects_object_source`.
- **AC6** (scaffold host-inference):
  `::test_scaffold_init_runs_under_copilot_layout_without_claude_tree`
  (interpretation below).
- **AC7** (static validate + skill set == source):
  `::test_validate_copilot_package_accepts_built_tree`,
  `::test_validate_copilot_package_flags_unsafe_skill`,
  `::test_copilot_skill_set_matches_source`.
- **Drift** (covers copilot for free): existing `DriftTests`.

### Deviations / interpretations
1. **AC6 — INTERPRETED; hook piece DEFERRED to 032-04.** jig bug 034 was its
   packaged `scaffold.py` defaulting to the *Claude renderer* (emitting
   `CLAUDE.md` / `host_renderer: "claude"` / a `.claude` tree). servo's
   `skills/scaffold-init/scaffold.py` has **no host-renderer concept**: it probes
   a target and emits host-agnostic `oracle.sh` + `.servo/{install.json,
   refinement-todo.md}`, never a host config tree. So AC6's literal wording
   ("emits `AGENTS.md` / `host_renderer: "copilot"`, no `.claude` tree") does not
   map — there is no Claude-default renderer to fix. Verified positively: the
   packaged helper runs under the Copilot `.github/` layout with
   `CLAUDE_PLUGIN_ROOT` unset (its `_templates_root()` falls back to the
   package's `.github/templates/`) and emits only `oracle.sh` + `.servo/`, no
   `.claude`/`CLAUDE.md`. servo's one genuinely host-specific scaffold behavior —
   the oracle gate installed as a Claude `Stop` hook that must become Copilot
   `agentStop` — is **hook work deferred to slice 032-04** per the task scope. No
   hook logic implemented here.
2. **Path rewrite scoped to the canonical `${CLAUDE_PLUGIN_ROOT}/` brace token.**
   All 10 SKILL.md plugin-root refs use the `${CLAUDE_PLUGIN_ROOT}/skills/...`
   brace form → rewritten to `$SERVO_ROOT/`; no brace token survives in any
   rendered SKILL.md. Two non-brace mentions in `heartbeat`'s SKILL.md (a
   Claude-mode GitHub Actions CI example that sets `CLAUDE_PLUGIN_ROOT:` env and
   calls `$CLAUDE_PLUGIN_ROOT/...`) are left truthful — a self-contained Claude
   recipe, matching servo's Codex renderer, which also only rewrites the brace
   token and preserves genuine host discussion. Not a silent break (the example
   defines the var it uses).
3. **Truncated description written as a `>-` folded block scalar, not inline
   JSON.** jig's `_replace_description_field` emits inline `json.dumps`. servo's
   over-limit skills are quote-heavy, so inline JSON escapes every inner quote
   (`\"`); the loader-compat reader strips outer quotes but does not decode
   escapes, so a truncated summary re-measures *over* 1024 even though its decoded
   value fits (jig's truncate path is dormant, so jig never hits this; servo's
   fires on 9 skills). A block scalar needs no escaping (raw == decoded), so the
   validator and Copilot's loader agree at ≤1024. Faithful adaptation of jig's
   rule; the name-strip, ≤1024 budget, word-boundary truncation, and
   full-original-in-body note are ported exactly. Also added one blank line
   between the root note and the full-description note (readability; the 9
   over-limit skills carry both).
4. **Root note omits jig's SessionStart carrier** (ADR-0038: servo's Copilot
   package is hook-free) — the note carries only the self-contained fresh-shell
   locator; it is the sole resolution path.
5. **`.github/agents/` not created (032-03).** Manifest declares
   `agents: ".github/agents"` (forward-compatible); `validate_copilot_package`
   requires the `agents` field but not agent files. Empty dirs aren't committed
   and the drift guard compares files only, so nothing dangles.
6. **`servo_root.py` is committed source** (`scripts/servo_root.py`), copied into
   the package by the builder (mirrors jig's `scripts/jig_root.py`). Ships only
   in the Copilot package (claude/codex builders don't read `scripts/`).
7. **Marketplace descriptor is hand-committed source, not build output** —
   matching how servo commits + validates its Claude/Codex root descriptors
   rather than generating them. It lives outside `hosts/` (not drift-checked);
   `validate_manifests.py` validates it. `validate_manifests` still reports
   "four plugin manifests agree" (the copilot `.plugin/plugin.json` is drift-
   guarded build output, not added to that version-agreement set this slice).

### AC7 live-CLI residual (honest)
`validate_copilot_package` is the deterministic install substitute (headless
`copilot -p` does not reliably fire repo hooks — spike 032-01 finding). A live
`copilot plugin install <dir>` + `copilot skill list` was **not** run: no live
`copilot` CLI in the implementer sandbox. Recorded as a residual for the owner's
review pass, consistent with the spike's recorded live-firing residual.

### Not in scope (later slices)
Agents rendering (032-03), oracle `Stop`→`agentStop` hook + adapter (032-04),
release zip / release-please / per-host smoke (032-05/06). `release-please-
config.json` and `build_release_zip.py` were left untouched, so
`hosts/copilot/.plugin/plugin.json` is **not yet** version-tracked by
release-please nor in the release archive — flagged for 032-06 (nothing parked
to `docs/inbox.md`; these are already planned slices).

### Verification
- Full venv suite: **1798 passed, 2 skipped** (pre-existing), 97 subtests, exit 0.
- Targeted (`test_build_host_packages` + `test_validate_manifests`): 38 passed,
  48 subtests. Mutation-verified: neutering the name strip/assert, the
  description truncation, the `$SERVO_ROOT` path rewrite, and the marketplace
  source-shape check each turns the relevant new test(s) red; all restored.
- `ruff==0.15.17 ruff check .`: all checks passed.
- `build_host_packages.py --check`: clean. `git status` shows `hosts/claude` and
  `hosts/codex` byte-unchanged.

### Orchestrator verification (post-implementer)
- **AC7 upgraded from static residual to LIVE pass.** Loaded the rendered package
  into the real `copilot` 1.0.86 loader:
  `copilot --plugin-dir "$(pwd)/hosts/copilot" skill list` → exit 0, **all 12
  servo skills discovered** under "Plugin skills". No loader rejection despite the
  9 formerly-`servo:`-namespaced skills (all rendered `:`-free; verified every
  `hosts/copilot/.github/skills/*/SKILL.md` `name:` is bare). `scaffold-init`
  displays as `servo:scaffold-init` **in the loader only** — Copilot's own
  collision-disambiguation vs jig's globally-installed `scaffold-init` skill (the
  rendered `name:` field is `scaffold-init`, `:`-free); servo's non-colliding
  skills display bare. Residual now narrowed to: live *hook firing* under headless
  `copilot -p` (unobservable per jig 113-08), which is 032-04's concern, not this
  slice's.
- **AC6 adjudicated (accepted).** servo's `scaffold-init` is genuinely
  host-agnostic (scaffolds `.servo/` oracle infra, emits no `.claude`/`AGENTS.md`/
  `host_renderer` tree), so jig bug-034's Claude-default *renderer* has no servo
  analogue; the implementer verified the packaged helper runs under the Copilot
  `.github/` layout without emitting a Claude tree. servo's only host-specific
  scaffold behavior is the oracle `Stop`→`agentStop` hook, correctly deferred to
  032-04. AC6 satisfied in spirit; no host-inference renderer needed.
- Re-ran targeted tests (38 passed/48 subtests), drift `--check` (clean), ruff
  (clean); no mutation/residue in the tree.
