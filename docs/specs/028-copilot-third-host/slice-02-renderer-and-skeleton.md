---
status: IN_PROGRESS
dependencies: [028-01, adr-0034]
last_verified:
# arch_review: true  # adds the Copilot host renderer + dispatch wiring
---

## Slice 028-02 — renderer-and-skeleton

**Goal:** A Copilot user can install servo and invoke its skills — the walking
skeleton: a Copilot arm in servo's builder that emits a committed, drift-guarded
`hosts/copilot/` whose skills load under Copilot CLI, following jig's shipped
`build_copilot_plugin.py` + `CopilotScaffoldRenderer` (ported as functions into
servo's function-based `scripts/build_host_packages.py`).

**DoR:**
- ✅ 028-01 done: contract confirmed vs jig's shipped package + live CLI (manifest
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
   `${CLAUDE_PLUGIN_ROOT}` intact). `.github/agents/` is populated by 028-03.
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
- [ ] All ACs pass; full suite green (venv pytest); new tests fail when the feature is removed.
- [ ] Claude/Codex host output unchanged (drift guard clean for those hosts).
- [ ] `build_host_packages.py --check` clean after regenerating `hosts/copilot/`.
- [ ] Reviewed by `reviewer` subagent (compliance + craft + arch).
- [ ] Deviation log + reconciliation sweep produced.

**Anti-horizontal-phasing check:** After this slice a Copilot user installs servo
and its skills load — observable end-to-end value.
