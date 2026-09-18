from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import build_host_packages  # noqa: E402


def file_map(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


class HostPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="servo-host-packages-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.hosts = self.tmp / "hosts"
        out = io.StringIO()
        self.assertEqual(
            build_host_packages.build_all(REPO_ROOT, self.hosts, out=out),
            0,
            out.getvalue(),
        )

    def test_builds_flat_claude_and_codex_marketplace(self):
        self.assertTrue((self.hosts / "claude/.claude-plugin/plugin.json").is_file())
        self.assertTrue((self.hosts / "codex/.agents/plugins/marketplace.json").is_file())
        self.assertTrue(
            (self.hosts / "codex/plugins/servo/.codex-plugin/plugin.json").is_file()
        )

    def test_manifests_share_canonical_version(self):
        canonical = json.loads((REPO_ROOT / ".claude-plugin/plugin.json").read_text())
        claude = json.loads(
            (self.hosts / "claude/.claude-plugin/plugin.json").read_text()
        )
        codex = json.loads(
            (self.hosts / "codex/plugins/servo/.codex-plugin/plugin.json").read_text()
        )
        self.assertEqual(claude["version"], canonical["version"])
        self.assertEqual(codex["version"], canonical["version"])

    def test_runtime_inventory_and_exclusions(self):
        for plugin in (
            self.hosts / "claude",
            self.hosts / "codex/plugins/servo",
        ):
            self.assertTrue((plugin / "README.md").is_file())
            self.assertTrue((plugin / "LICENSE").is_file())
            self.assertTrue((plugin / "servo.jpg").is_file())
            self.assertTrue((plugin / "agents/runner.md").is_file())
            self.assertTrue((plugin / "templates/oracle.sh.template").is_file())
            source_skills = {
                p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")
            }
            packaged_skills = {p.parent.name for p in (plugin / "skills").glob("*/SKILL.md")}
            self.assertEqual(packaged_skills, source_skills)
            offenders = [
                p.relative_to(plugin).as_posix()
                for p in plugin.rglob("*")
                if p.is_file()
                and (
                    p.name.startswith("test_")
                    or p.suffix == ".pyc"
                    or "__pycache__" in p.parts
                    or ".pytest_cache" in p.parts
                )
            ]
            self.assertEqual(offenders, [])

    def test_host_specific_content_is_not_leaked(self):
        claude = self.hosts / "claude"
        self.assertFalse((claude / ".codex-plugin").exists())
        self.assertFalse((claude / ".claude-plugin/marketplace.json").exists())
        self.assertFalse((claude / ".agents").exists())
        codex_plugin = self.hosts / "codex/plugins/servo"
        self.assertFalse((codex_plugin / ".claude-plugin").exists())

    def test_codex_rewrites_only_skill_plugin_root_paths(self):
        codex = self.hosts / "codex/plugins/servo"
        skill_text = "\n".join(p.read_text() for p in (codex / "skills").glob("*/SKILL.md"))
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", skill_text)
        self.assertIn("${PLUGIN_ROOT}/skills/", skill_text)
        # Genuine host/runtime discussion remains truthful.
        self.assertIn("Claude Code", (codex / "skills/agent-loop/SKILL.md").read_text())

    def test_codex_skill_names_rely_on_plugin_namespace_once(self):
        codex = self.hosts / "codex/plugins/servo/skills"
        for skill in codex.glob("*/SKILL.md"):
            with self.subTest(skill=skill.parent.name):
                name_line = next(
                    line for line in skill.read_text().splitlines() if line.startswith("name:")
                )
                self.assertEqual(name_line, f"name: {skill.parent.name}")

    def test_codex_skill_descriptions_fit_discovery_metadata(self):
        codex = self.hosts / "codex/plugins/servo/skills"
        for skill in codex.glob("*/SKILL.md"):
            with self.subTest(skill=skill.parent.name):
                frontmatter = skill.read_text().split("---", 2)[1]
                self.assertIn("description: >-", frontmatter)
                description = frontmatter.split("description: >-", 1)[1].strip()
                self.assertLessEqual(len(description), 1024)

    def test_eval_authoring_discovery_description_preserves_routing_boundary(self):
        source = (REPO_ROOT / "skills/eval-authoring/SKILL.md").read_bytes()
        first = build_host_packages._render_codex_skill(source, "eval-authoring")
        second = build_host_packages._render_codex_skill(source, "eval-authoring")
        self.assertEqual(first, second)
        description = first.decode().split("---", 2)[1].split("description: >-", 1)[1].strip()
        self.assertLessEqual(len(description), 1024)
        self.assertIn("free-form goal", description)
        self.assertIn("Do NOT use", description)
        self.assertIn("design/content fidelity", description)
        self.assertIn("generic surface", description)

    def test_overlong_codex_description_refuses_instead_of_truncating_semantics(self):
        source = b"---\nname: servo:example\ndescription: >-\n  " + b"x" * 1025 + b"\n---\nbody\n"
        with self.assertRaisesRegex(ValueError, "shorten its first paragraph"):
            build_host_packages._render_codex_skill(source, "example")

    def test_repeated_builds_are_identical_and_replace_stale_files(self):
        other = self.tmp / "other"
        self.assertEqual(build_host_packages.build_all(REPO_ROOT, other, io.StringIO()), 0)
        self.assertEqual(file_map(self.hosts), file_map(other))
        stale = self.hosts / "claude/STALE"
        stale.write_text("stale")
        self.assertEqual(build_host_packages.build_all(REPO_ROOT, self.hosts, io.StringIO()), 0)
        self.assertFalse(stale.exists())

    # ------------------------------------------------------------------ #
    # Slice 028-02 — Copilot host arm.
    # ------------------------------------------------------------------ #

    def test_copilot_arm_renders_committed_layout(self):
        # AC1/AC2: a Copilot package is emitted alongside claude/codex with the
        # legacy `.plugin/plugin.json` manifest and `.github/` component tree.
        copilot = self.hosts / "copilot"
        manifest_path = copilot / ".plugin/plugin.json"
        self.assertTrue(manifest_path.is_file())
        self.assertTrue((copilot / ".github/skills/agent-loop/SKILL.md").is_file())
        self.assertTrue((copilot / ".github/scripts/servo_root.py").is_file())
        self.assertTrue((copilot / ".github/templates/oracle.sh.template").is_file())
        manifest = json.loads(manifest_path.read_text())
        canonical = json.loads((REPO_ROOT / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "servo")
        self.assertEqual(manifest["version"], canonical["version"])
        self.assertEqual(manifest["skills"], ".github/skills")
        self.assertEqual(manifest["agents"], ".github/agents")
        # No plugin hooks ship — servo's Copilot package is hook-free (ADR-0034).
        self.assertNotIn("hooks", manifest)

    def test_copilot_arm_leaves_claude_and_codex_byte_identical(self):
        # AC1: adding the Copilot arm must not perturb the committed Claude or
        # Codex trees — the freshly built pair matches what is already on disk.
        self.assertEqual(
            file_map(self.hosts / "claude"),
            file_map(REPO_ROOT / "hosts" / "claude"),
        )
        self.assertEqual(
            file_map(self.hosts / "codex"),
            file_map(REPO_ROOT / "hosts" / "codex"),
        )

    def test_copilot_skill_set_matches_source(self):
        # AC2/AC7: the packaged skill set equals the source skill set.
        source_skills = {p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")}
        packaged = {
            p.parent.name
            for p in (self.hosts / "copilot/.github/skills").glob("*/SKILL.md")
        }
        self.assertEqual(packaged, source_skills)

    def test_copilot_templates_ship_unrendered(self):
        # AC2: templates are copied byte-for-byte, canonical ${CLAUDE_PLUGIN_ROOT}
        # left intact (they are rendered per-mode at scaffold time, not here).
        packaged = self.hosts / "copilot/.github/templates/oracle.sh.template"
        source = REPO_ROOT / "templates/oracle.sh.template"
        self.assertEqual(packaged.read_bytes(), source.read_bytes())

    def test_copilot_skill_names_are_namespace_safe(self):
        # AC3(a): every rendered name is ':'-free and the servo: namespace is gone.
        skills = self.hosts / "copilot/.github/skills"
        for skill in skills.glob("*/SKILL.md"):
            with self.subTest(skill=skill.parent.name):
                name_line = next(
                    line for line in skill.read_text().splitlines() if line.startswith("name:")
                )
                self.assertEqual(name_line, f"name: {skill.parent.name}")
                self.assertNotIn(":", name_line[len("name:"):])

    def test_copilot_over_limit_description_truncated_and_body_preserves_full_text(self):
        # AC3(b): agent-loop's ~2133-char description is truncated to <=1024 in
        # the Copilot frontmatter, with the complete original preserved in body.
        rendered = (self.hosts / "copilot/.github/skills/agent-loop/SKILL.md").read_text()
        source = (REPO_ROOT / "skills/agent-loop/SKILL.md").read_text()
        original_desc = build_host_packages._read_skill_description(source)
        self.assertGreater(len(original_desc), 1024)
        rendered_desc = build_host_packages._read_skill_description(rendered)
        self.assertLessEqual(len(rendered_desc), 1024)
        self.assertTrue(rendered_desc.endswith(" (full description in skill body)"))
        # A phrase past the truncation budget is gone from frontmatter but kept
        # in the body note — no routing/trigger guidance is lost.
        self.assertNotIn("in-Routine authority", rendered_desc)
        body = rendered.split("---", 2)[2]
        self.assertIn("in-Routine authority", body)
        self.assertIn(original_desc, body)
        # Claude ships the same skill byte-for-byte (render is Copilot-only).
        self.assertEqual(
            (self.hosts / "claude/skills/agent-loop/SKILL.md").read_bytes(),
            (REPO_ROOT / "skills/agent-loop/SKILL.md").read_bytes(),
        )

    def test_copilot_short_description_skill_renders_byte_for_byte(self):
        # AC3: a compliant skill (short description, bare name, no plugin-root
        # reference) is emitted byte-for-byte identical to its source.
        packaged = (self.hosts / "copilot/.github/skills/design-eval/SKILL.md").read_bytes()
        source = (REPO_ROOT / "skills/design-eval/SKILL.md").read_bytes()
        self.assertEqual(packaged, source)

    def test_copilot_rewrites_plugin_root_and_injects_root_note(self):
        # AC4: no ${CLAUDE_PLUGIN_ROOT} survives; helper paths become $SERVO_ROOT;
        # a self-contained locator note (no SessionStart carrier) is injected.
        rendered = (self.hosts / "copilot/.github/skills/agent-loop/SKILL.md").read_text()
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", rendered)
        self.assertIn("$SERVO_ROOT/skills/agent-loop/loop.py", rendered)
        self.assertIn(".github/scripts/servo_root.py", rendered)
        self.assertIn("servo's runtime root (this plugin's own directory)", rendered)
        self.assertNotIn("SessionStart", rendered)

    def test_copilot_no_braced_plugin_root_survives_any_skill(self):
        # AC4 (package-wide): the canonical ${CLAUDE_PLUGIN_ROOT} brace token —
        # the documented plugin-mode helper path — is rewritten in every skill.
        skills = self.hosts / "copilot/.github/skills"
        for skill in skills.glob("*/SKILL.md"):
            with self.subTest(skill=skill.parent.name):
                self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", skill.read_text())

    def test_copilot_servo_root_locator_shipped(self):
        # AC4: the fresh-shell locator ships and names servo's plugin manifest.
        locator = (self.hosts / "copilot/.github/scripts/servo_root.py").read_text()
        self.assertIn('PLUGIN_NAME = "servo"', locator)
        self.assertIn(".plugin", locator)

    def test_validate_copilot_package_accepts_built_tree(self):
        # AC7: the static package validator accepts a freshly built tree.
        source_skills = {p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")}
        problems = build_host_packages.validate_copilot_package(
            self.hosts / "copilot", expected_skills=source_skills
        )
        self.assertEqual(problems, [])

    def test_validate_copilot_package_flags_unsafe_skill(self):
        # AC7 (teeth): the validator rejects a colon-bearing name and an
        # over-limit description injected into the built tree.
        skill = self.hosts / "copilot/.github/skills/design-eval/SKILL.md"
        skill.write_text(
            "---\nname: servo:design-eval\ndescription: " + "x" * 1100 + "\n---\nbody\n"
        )
        problems = build_host_packages.validate_copilot_package(self.hosts / "copilot")
        self.assertTrue(any("design-eval" in p for p in problems), problems)

    # ------------------------------------------------------------------ #
    # Slice 028-03 — Copilot agents (`.github/agents/<name>.agent.md`).
    # ------------------------------------------------------------------ #

    def test_copilot_agents_rendered_with_mapped_tools(self):
        # AC1/AC2: source agents/<name>.md render to
        # .github/agents/<name>.agent.md with Claude tool names mapped to
        # Copilot's vocabulary, order preserved.
        runner = self.hosts / "copilot/.github/agents/runner.agent.md"
        judge = self.hosts / "copilot/.github/agents/judge.agent.md"
        self.assertTrue(runner.is_file())
        self.assertTrue(judge.is_file())
        runner_fm, _ = build_host_packages._split_frontmatter(runner.read_text())
        judge_fm, _ = build_host_packages._split_frontmatter(judge.read_text())
        self.assertEqual(
            build_host_packages._frontmatter_list(runner_fm, "tools"),
            ["view", "create", "edit", "bash", "glob", "grep"],
        )
        self.assertEqual(
            build_host_packages._frontmatter_list(judge_fm, "tools"),
            ["view", "glob", "grep"],
        )

    def test_copilot_judge_agent_has_no_write_or_exec_tool(self):
        # AC4: judge's read-only tool set (no create/edit/bash) is preserved.
        judge = self.hosts / "copilot/.github/agents/judge.agent.md"
        fm, _ = build_host_packages._split_frontmatter(judge.read_text())
        tools = build_host_packages._frontmatter_list(fm, "tools")
        self.assertNotIn("create", tools)
        self.assertNotIn("edit", tools)
        self.assertNotIn("bash", tools)

    def test_copilot_agent_name_description_and_body_preserved(self):
        # AC1: name/description/body are preserved verbatim; only the
        # `tools:` block changes.
        for name in ("runner", "judge"):
            with self.subTest(agent=name):
                rendered = (
                    self.hosts / f"copilot/.github/agents/{name}.agent.md"
                ).read_text()
                source = (REPO_ROOT / f"agents/{name}.md").read_text()
                rendered_fm, rendered_body = build_host_packages._split_frontmatter(rendered)
                source_fm, source_body = build_host_packages._split_frontmatter(source)
                self.assertEqual(rendered_body, source_body)
                self.assertEqual(
                    build_host_packages._frontmatter_value(rendered_fm, "name"),
                    build_host_packages._frontmatter_value(source_fm, "name"),
                )
                self.assertEqual(
                    build_host_packages._frontmatter_value(rendered_fm, "description"),
                    build_host_packages._frontmatter_value(source_fm, "description"),
                )

    def test_copilot_agents_carry_no_model_field_or_id(self):
        # AC3: no rendered agent carries a model: field or a hard-coded
        # opus/sonnet model id.
        for name in ("runner", "judge"):
            with self.subTest(agent=name):
                text = (self.hosts / f"copilot/.github/agents/{name}.agent.md").read_text()
                self.assertNotIn("model:", text)
                self.assertNotIn("opus", text.lower())
                self.assertNotIn("sonnet", text.lower())

    def test_copilot_manifest_agents_path_resolves_to_real_files(self):
        # AC1: the manifest's `agents: ".github/agents"` path (written in
        # 028-02) now resolves to real rendered agent files matching source.
        manifest = json.loads((self.hosts / "copilot/.plugin/plugin.json").read_text())
        agents_dir = self.hosts / "copilot" / manifest["agents"]
        self.assertEqual(
            {p.name.removesuffix(".agent.md") for p in agents_dir.glob("*.agent.md")},
            {p.stem for p in (REPO_ROOT / "agents").glob("*.md")},
        )

    def test_scaffold_init_runs_under_copilot_layout_without_claude_tree(self):
        # AC6: the packaged scaffold-init helper runs under the Copilot .github/
        # layout (CLAUDE_PLUGIN_ROOT unset) and emits servo's host-agnostic
        # artifacts (oracle.sh + .servo/), never a Claude host tree. servo's
        # scaffold-init has no Claude-default *renderer* (unlike jig bug 034):
        # it scaffolds oracle infra, not a host config tree. The only
        # host-specific behavior (the oracle Stop->agentStop hook) is 028-04.
        pkg_scaffold = self.hosts / "copilot/.github/skills/scaffold-init/scaffold.py"
        self.assertTrue(pkg_scaffold.is_file())
        target = self.tmp / "scaffold-target"
        target.mkdir()
        env = dict(os.environ)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        env["XDG_STATE_HOME"] = str(self.tmp / "xdg-state")
        proc = subprocess.run(
            [sys.executable, str(pkg_scaffold), str(target)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue((target / "oracle.sh").is_file())
        self.assertTrue((target / ".servo/install.json").is_file())
        self.assertFalse((target / ".claude").exists())
        self.assertFalse((target / "CLAUDE.md").exists())


class DriftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="servo-host-drift-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.hosts = self.tmp / "hosts"
        self.assertEqual(build_host_packages.build_all(REPO_ROOT, self.hosts, io.StringIO()), 0)

    def test_check_passes_in_sync_without_mutation(self):
        before = file_map(self.hosts)
        out = io.StringIO()
        self.assertEqual(build_host_packages.check_drift(REPO_ROOT, self.hosts, out), 0)
        self.assertEqual(file_map(self.hosts), before)

    def test_check_names_drift_and_regeneration_command(self):
        stale = self.hosts / "claude/.claude-plugin/plugin.json"
        stale.write_text("stale")
        out = io.StringIO()
        self.assertEqual(build_host_packages.check_drift(REPO_ROOT, self.hosts, out), 1)
        self.assertIn("claude/.claude-plugin/plugin.json", out.getvalue())
        self.assertIn("python3 scripts/build_host_packages.py", out.getvalue())


class CopilotRenderUnitTests(unittest.TestCase):
    """Pure-transform coverage for the Copilot skill renderer (no build)."""

    def test_safe_skill_name_strips_servo_namespace(self):
        self.assertEqual(
            build_host_packages._copilot_safe_skill_name("servo:agent-loop"),
            "agent-loop",
        )
        # A bare (un-namespaced) name is preserved.
        self.assertEqual(
            build_host_packages._copilot_safe_skill_name("design-eval"),
            "design-eval",
        )

    def test_safe_skill_name_raises_on_residual_colon(self):
        with self.assertRaises(ValueError):
            build_host_packages._copilot_safe_skill_name("servo:a:b")

    def test_loader_safe_description_keeps_short_text(self):
        short = "a short routing description"
        self.assertEqual(build_host_packages._loader_safe_description(short), short)

    def test_loader_safe_description_truncates_at_word_boundary(self):
        original = "word " * 400  # 2000 chars, well over the limit
        safe = build_host_packages._loader_safe_description(original)
        self.assertLessEqual(len(safe), 1024)
        self.assertTrue(safe.endswith(" (full description in skill body)"))
        # Word-boundary truncation never splits mid-token.
        body = safe[: -len(" (full description in skill body)")]
        self.assertFalse(body.endswith("wor"))

    def test_render_copilot_skill_is_deterministic(self):
        source = (REPO_ROOT / "skills/agent-loop/SKILL.md").read_bytes()
        first = build_host_packages._render_copilot_skill(source, "agent-loop")
        second = build_host_packages._render_copilot_skill(source, "agent-loop")
        self.assertEqual(first, second)

    def test_render_copilot_skill_rejects_colon_name(self):
        source = b"---\nname: servo:a:b\ndescription: short\n---\nbody\n"
        with self.assertRaises(ValueError):
            build_host_packages._render_copilot_skill(source, "a")

    # -------------------------------------------------------------- #
    # Slice 028-03 — agent tool mapping + `.agent.md` rendering.
    # -------------------------------------------------------------- #

    def test_copilot_tool_names_maps_claude_to_copilot_vocabulary(self):
        self.assertEqual(
            build_host_packages._copilot_tool_names(
                ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
            ),
            ["view", "create", "edit", "bash", "glob", "grep"],
        )

    def test_copilot_tool_names_preserves_order_for_read_only_subset(self):
        self.assertEqual(
            build_host_packages._copilot_tool_names(["Read", "Glob", "Grep"]),
            ["view", "glob", "grep"],
        )

    def test_copilot_tool_names_rejects_unmapped_tool(self):
        with self.assertRaisesRegex(ValueError, "no Copilot tool mapping"):
            build_host_packages._copilot_tool_names(["Read", "Sudo"])

    def test_render_copilot_agent_maps_tools_preserves_name_description_body(self):
        source = (
            b"---\nname: runner\ndescription: does things\ntools:\n  - Read\n"
            b"  - Write\n  - Edit\n  - Bash\n  - Glob\n  - Grep\n---\n\n# Body\n\ntext\n"
        )
        rendered = build_host_packages._render_copilot_agent(source, "runner")
        fm, body = build_host_packages._split_frontmatter(rendered.decode("utf-8"))
        self.assertEqual(
            build_host_packages._frontmatter_list(fm, "tools"),
            ["view", "create", "edit", "bash", "glob", "grep"],
        )
        self.assertEqual(build_host_packages._frontmatter_value(fm, "name"), "runner")
        self.assertEqual(
            build_host_packages._frontmatter_value(fm, "description"), "does things"
        )
        self.assertEqual(body, "\n# Body\n\ntext\n")

    def test_render_copilot_agent_rejects_unmapped_tool(self):
        source = b"---\nname: x\ndescription: d\ntools:\n  - Sudo\n---\nbody\n"
        with self.assertRaises(ValueError):
            build_host_packages._render_copilot_agent(source, "x")

    def test_render_copilot_agent_rejects_model_field(self):
        source = b"---\nname: x\ndescription: d\nmodel: opus\ntools:\n  - Read\n---\nbody\n"
        with self.assertRaisesRegex(ValueError, "model"):
            build_host_packages._render_copilot_agent(source, "x")

    def test_render_copilot_agent_no_frontmatter_raises(self):
        with self.assertRaises(ValueError):
            build_host_packages._render_copilot_agent(b"no frontmatter here\n", "x")

    def test_render_copilot_agent_is_deterministic(self):
        source = (REPO_ROOT / "agents/runner.md").read_bytes()
        first = build_host_packages._render_copilot_agent(source, "runner")
        second = build_host_packages._render_copilot_agent(source, "runner")
        self.assertEqual(first, second)


class ServoRootLocatorTests(unittest.TestCase):
    """The $SERVO_ROOT fresh-shell locator (bug 036)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="servo-root-locator-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        import servo_root

        self.servo_root = servo_root

    def _make_install(self, home: Path, version: str) -> Path:
        root = home / "installed-plugins" / "servo" / "servo"
        github = root / ".github"
        (root / ".plugin").mkdir(parents=True)
        (root / ".plugin" / "plugin.json").write_text(
            json.dumps({"name": "servo", "version": version})
        )
        sentinel = github / "skills" / "agent-loop" / "loop.py"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("# runtime sentinel\n")
        return github

    def test_resolves_installed_plugin(self):
        home = self.tmp / "copilot-home"
        github = self._make_install(home, "0.9.0")
        os.environ["COPILOT_HOME"] = str(home)
        self.addCleanup(os.environ.pop, "COPILOT_HOME", None)
        self.assertEqual(self.servo_root.resolve(start=self.tmp), github)

    def test_returns_none_when_no_runtime(self):
        os.environ["COPILOT_HOME"] = str(self.tmp / "empty-home")
        self.addCleanup(os.environ.pop, "COPILOT_HOME", None)
        self.assertIsNone(self.servo_root.resolve(start=self.tmp))


if __name__ == "__main__":
    unittest.main()
