"""
Tests for slice 007-03 (`scripts/scaffold_runtime.py`).

Run from the repo root:
    python3 scripts/test_scaffold_runtime.py
or with pytest:
    uvx pytest -q scripts/test_scaffold_runtime.py

These tests intentionally exercise the project-local scaffold mode without
touching `scaffold.py`'s default oracle-install behavior (regression below).
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCAFFOLD_INIT_DIR = REPO_ROOT / "skills" / "scaffold-init"
OLD_XDG_STATE_HOME = None
TEST_STATE_HOME = None
sys.path.insert(0, str(SCRIPTS_DIR))

import scaffold_runtime  # noqa: E402

CONTRACT = json.loads(
    (REPO_ROOT / ".claude-plugin" / "install-contract.json").read_text()
)
PLUGIN_VERSION = json.loads(
    (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text()
)["version"]
SCAFFOLD_CFG = CONTRACT["scaffold"]
SKILL_PREFIX = SCAFFOLD_CFG["skill_prefix"]
AGENT_PREFIX = SCAFFOLD_CFG["agent_prefix"]
RUNTIME_ROOT = SCAFFOLD_CFG["runtime_root"]
MANAGED_MARKER = SCAFFOLD_CFG["managed_marker"]


def setUpModule():
    global OLD_XDG_STATE_HOME, TEST_STATE_HOME
    OLD_XDG_STATE_HOME = os.environ.get("XDG_STATE_HOME")
    TEST_STATE_HOME = Path(tempfile.mkdtemp(prefix="servo-state-home-"))
    os.environ["XDG_STATE_HOME"] = str(TEST_STATE_HOME)


def tearDownModule():
    if OLD_XDG_STATE_HOME is None:
        os.environ.pop("XDG_STATE_HOME", None)
    else:
        os.environ["XDG_STATE_HOME"] = OLD_XDG_STATE_HOME
    if TEST_STATE_HOME is not None:
        shutil.rmtree(TEST_STATE_HOME, ignore_errors=True)


def _new_target() -> Path:
    return Path(tempfile.mkdtemp(prefix="servo-scaffold-runtime-"))


class ScaffoldSkillsTests(unittest.TestCase):
    """AC2: skills are copied with the servo- prefix and their helper files."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)

    def test_each_required_skill_dir_is_prefixed(self):
        skills_root = self.target / ".claude" / "skills"
        for skill in CONTRACT["required"]["skills"]:
            skill_dir = skills_root / f"{SKILL_PREFIX}{skill['name']}"
            self.assertTrue(
                skill_dir.is_dir(),
                f"missing prefixed skill dir {skill_dir}",
            )

    def test_required_skill_files_present(self):
        skills_root = self.target / ".claude" / "skills"
        for skill in CONTRACT["required"]["skills"]:
            for file_name in skill["files"]:
                path = skills_root / f"{SKILL_PREFIX}{skill['name']}" / file_name
                self.assertTrue(path.is_file(), f"missing skill file {path}")

    def test_unprefixed_skill_dirs_not_created(self):
        skills_root = self.target / ".claude" / "skills"
        for skill in CONTRACT["required"]["skills"]:
            bare = skills_root / skill["name"]
            self.assertFalse(bare.exists(), f"unexpected bare skill dir {bare}")


class ScaffoldAgentsTests(unittest.TestCase):
    """AC3: agents are copied with the servo- prefix."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)

    def test_prefixed_agents_present(self):
        agents_root = self.target / ".claude" / "agents"
        for agent in CONTRACT["required"]["agents"]:
            path = agents_root / f"{AGENT_PREFIX}{agent}.md"
            self.assertTrue(path.is_file(), f"missing prefixed agent {path}")

    def test_unprefixed_agents_not_created(self):
        agents_root = self.target / ".claude" / "agents"
        for agent in CONTRACT["required"]["agents"]:
            bare = agents_root / f"{agent}.md"
            self.assertFalse(bare.exists(), f"unexpected bare agent {bare}")


class ScaffoldTemplatesTests(unittest.TestCase):
    """AC4: templates are copied under the runtime_root."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)

    def test_all_required_templates_present(self):
        templates_root = self.target / RUNTIME_ROOT / "templates"
        for template in CONTRACT["required"]["templates"]:
            path = templates_root / template
            self.assertTrue(path.is_file(), f"missing template {path}")

    def test_component_fragments_present(self):
        templates_root = self.target / RUNTIME_ROOT / "templates"
        self.assertTrue(
            (templates_root / "components" / "pytest.sh.fragment").is_file()
        )


class ScaffoldManifestTests(unittest.TestCase):
    """AC5: a scaffold manifest records version, marker, and copied artifacts."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)
        self.manifest_path = self.target / RUNTIME_ROOT / "scaffold-install.json"
        self.manifest = json.loads(self.manifest_path.read_text())

    def test_manifest_written(self):
        self.assertTrue(self.manifest_path.is_file())

    def test_manifest_has_schema_version(self):
        self.assertIn("schema_version", self.manifest)
        self.assertIsInstance(self.manifest["schema_version"], int)

    def test_manifest_records_source_version(self):
        self.assertEqual(self.manifest["source_version"], PLUGIN_VERSION)

    def test_manifest_records_timestamp(self):
        self.assertRegex(
            self.manifest["timestamp"],
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        )

    def test_manifest_records_managed_marker(self):
        self.assertEqual(self.manifest["managed_marker"], MANAGED_MARKER)

    def test_manifest_lists_copied_skills(self):
        expected = sorted(
            f"{SKILL_PREFIX}{skill['name']}"
            for skill in CONTRACT["required"]["skills"]
        )
        self.assertEqual(sorted(self.manifest["skills"]), expected)

    def test_manifest_lists_copied_agents(self):
        expected = sorted(
            f"{AGENT_PREFIX}{agent}" for agent in CONTRACT["required"]["agents"]
        )
        self.assertEqual(sorted(self.manifest["agents"]), expected)

    def test_manifest_lists_copied_templates(self):
        self.assertEqual(
            sorted(self.manifest["templates"]),
            sorted(CONTRACT["required"]["templates"]),
        )


class AvailabilityBreadcrumbTests(unittest.TestCase):
    """ADR-0013: runtime scaffold writes the servo availability marker."""

    def test_scaffold_runtime_writes_availability_marker(self):
        target = _new_target()
        state_home = target / "state"
        self.addCleanup(shutil.rmtree, target, True)
        old_state_home = os.environ.get("XDG_STATE_HOME")
        os.environ["XDG_STATE_HOME"] = str(state_home)
        self.addCleanup(
            lambda: (
                os.environ.__setitem__("XDG_STATE_HOME", old_state_home)
                if old_state_home is not None
                else os.environ.pop("XDG_STATE_HOME", None)
            )
        )

        scaffold_runtime.scaffold_runtime(target)

        marker = state_home / "servo" / "available.json"
        self.assertTrue(marker.is_file(), "availability marker was not written")
        payload = json.loads(marker.read_text())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["plugin_name"], "servo")
        self.assertEqual(payload["source_kind"], "scaffold-runtime")
        self.assertEqual(Path(payload["source_path"]), REPO_ROOT)
        self.assertEqual(payload["source_version"], PLUGIN_VERSION)
        self.assertRegex(
            payload["updated_at"],
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        )

    def test_marker_write_failure_warns_without_failing_scaffold(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        blocked_state_home = target / "state-file"
        blocked_state_home.write_text("not a directory")
        old_state_home = os.environ.get("XDG_STATE_HOME")
        os.environ["XDG_STATE_HOME"] = str(blocked_state_home)
        self.addCleanup(
            lambda: (
                os.environ.__setitem__("XDG_STATE_HOME", old_state_home)
                if old_state_home is not None
                else os.environ.pop("XDG_STATE_HOME", None)
            )
        )

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            manifest = scaffold_runtime.scaffold_runtime(target)

        self.assertEqual(manifest["source_version"], PLUGIN_VERSION)
        self.assertIn("could not write availability marker", stderr.getvalue())
        self.assertTrue((target / RUNTIME_ROOT / "scaffold-install.json").is_file())


class IdempotencyTests(unittest.TestCase):
    """AC1/idempotency: re-running updates managed files without duplication."""

    def test_rerun_does_not_error_or_duplicate(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        scaffold_runtime.scaffold_runtime(target)
        first = sorted(p.relative_to(target).as_posix()
                       for p in (target / ".claude").rglob("*") if p.is_file())
        # second run must not raise and must not change the managed file set
        scaffold_runtime.scaffold_runtime(target)
        second = sorted(p.relative_to(target).as_posix()
                        for p in (target / ".claude").rglob("*") if p.is_file())
        self.assertEqual(first, second)

    def test_rerun_refreshes_managed_file_content(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        scaffold_runtime.scaffold_runtime(target)
        helper = (
            target / ".claude" / "skills"
            / f"{SKILL_PREFIX}scaffold-init" / "scaffold.py"
        )
        helper.write_text("# tampered\n")
        scaffold_runtime.scaffold_runtime(target)
        self.assertNotEqual(helper.read_text(), "# tampered\n")
        self.assertEqual(
            helper.read_text(),
            (SCAFFOLD_INIT_DIR / "scaffold.py").read_text(),
        )


class NoHookEntriesTests(unittest.TestCase):
    """DoD: no real .claude/settings.json hook entries while hooks list is empty."""

    def test_no_settings_json_written(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        scaffold_runtime.scaffold_runtime(target)
        settings = target / ".claude" / "settings.json"
        self.assertFalse(
            settings.exists(),
            "scaffold must not write .claude/settings.json while hooks are empty",
        )


class SelfContainedSmokeTests(unittest.TestCase):
    """AC6: a vendored helper runs using only files under the target."""

    def _run_vendored_detect(
        self, target: Path, env: dict[str, str]
    ) -> subprocess.CompletedProcess:
        vendored = (
            target / ".claude" / "skills"
            / f"{SKILL_PREFIX}scaffold-init" / "scaffold.py"
        )
        return subprocess.run(
            [sys.executable, str(vendored), "detect", str(target)],
            capture_output=True,
            text=True,
            env=env,
        )

    def test_detect_runs_with_plugin_root_unset(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        scaffold_runtime.scaffold_runtime(target)
        env = dict(os.environ)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        result = self._run_vendored_detect(target, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("components", payload)

    def test_detect_runs_with_plugin_root_invalid(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        scaffold_runtime.scaffold_runtime(target)
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(target / "does-not-exist-xyz")
        result = self._run_vendored_detect(target, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("components", payload)


class OracleInstallRegressionTests(unittest.TestCase):
    """Regression: scaffold.py <target> oracle-install is unchanged."""

    def test_oracle_install_still_writes_expected_shape(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
        result = subprocess.run(
            [sys.executable, str(SCAFFOLD_INIT_DIR / "scaffold.py"), str(target)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((target / "oracle.sh").is_file())
        self.assertTrue((target / ".servo" / "install.json").is_file())
        manifest = json.loads((target / ".servo" / "install.json").read_text())
        self.assertEqual(manifest["installed_tier"], "tier-0")
        # oracle-install must not create the runtime scaffold layout
        self.assertFalse((target / ".claude" / "skills").exists())
        self.assertFalse((target / RUNTIME_ROOT / "scaffold-install.json").exists())


class CliTests(unittest.TestCase):
    """AC1: documented command copies runtime machinery into <target>/.claude/."""

    def test_main_scaffolds_target(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        with redirect_stdout(io.StringIO()):
            rc = scaffold_runtime.main([str(target)])
        self.assertEqual(rc, 0)
        self.assertTrue((target / RUNTIME_ROOT / "scaffold-install.json").is_file())

    def test_cli_subprocess_scaffolds_target(self):
        target = _new_target()
        self.addCleanup(shutil.rmtree, target, True)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "scaffold_runtime.py"), str(target)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            (target / ".claude" / "agents" / f"{AGENT_PREFIX}runner.md").is_file()
        )


# ---------------------------------------------------------------------------
# 007-04 scaffold-fidelity
# ---------------------------------------------------------------------------

def _vendored_skill_md_paths(target: Path) -> list[Path]:
    skills_root = target / ".claude" / "skills"
    return [
        skills_root / f"{SKILL_PREFIX}{skill['name']}" / "SKILL.md"
        for skill in CONTRACT["required"]["skills"]
    ]


def _vendored_managed_markdown(target: Path) -> list[Path]:
    paths = _vendored_skill_md_paths(target)
    agents_root = target / ".claude" / "agents"
    paths.extend(
        agents_root / f"{AGENT_PREFIX}{agent}.md"
        for agent in CONTRACT["required"]["agents"]
    )
    return paths


class StalePluginRootRewriteTests(unittest.TestCase):
    """AC1: vendored SKILL.md files carry no `${CLAUDE_PLUGIN_ROOT}` commands."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)

    def test_no_plugin_root_in_vendored_skill_md(self):
        for skill_md in _vendored_skill_md_paths(self.target):
            text = skill_md.read_text()
            self.assertNotIn(
                "${CLAUDE_PLUGIN_ROOT}", text,
                f"stale ${{CLAUDE_PLUGIN_ROOT}} survived in {skill_md}",
            )

    def test_skill_md_points_at_vendored_skill_paths(self):
        # Every rewritten command should reference the prefixed, vendored
        # `.claude/skills/servo-<name>/` location instead of the plugin root.
        scaffold_md = (
            self.target / ".claude" / "skills"
            / f"{SKILL_PREFIX}scaffold-init" / "SKILL.md"
        ).read_text()
        self.assertIn(
            f".claude/skills/{SKILL_PREFIX}scaffold-init/scaffold.py", scaffold_md
        )

    def test_source_skill_md_unchanged(self):
        # The source checkout's SKILL.md must keep its plugin-mode docs;
        # only the vendored copy is rewritten.
        src = (SCAFFOLD_INIT_DIR / "SKILL.md").read_text()
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", src)


class VendoredOracleInstallSelfContainedTests(unittest.TestCase):
    """AC6: the vendored oracle-install runs with CLAUDE_PLUGIN_ROOT unset.

    Closes the concrete 007-03 gap: templates are vendored to
    `<target>/.claude/servo/templates`, and `scaffold.py` must resolve them
    there rather than the stale `plugin_root()/templates` fallback.
    """

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)
        self.vendored_scaffold = (
            self.target / ".claude" / "skills"
            / f"{SKILL_PREFIX}scaffold-init" / "scaffold.py"
        )

    def _run(self, args, env):
        return subprocess.run(
            [sys.executable, str(self.vendored_scaffold), *args],
            capture_output=True, text=True, env=env,
        )

    def test_oracle_install_runs_with_plugin_root_unset(self):
        env = dict(os.environ)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        result = self._run([str(self.target)], env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.target / "oracle.sh").is_file())

    def test_oracle_install_runs_with_plugin_root_invalid(self):
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(self.target / "no-such-dir-xyz")
        result = self._run([str(self.target)], env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.target / "oracle.sh").is_file())

    def test_force_reinstall_runs_with_plugin_root_unset(self):
        env = dict(os.environ)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        self.assertEqual(self._run([str(self.target)], env).returncode, 0)
        result = self._run([str(self.target), "--force"], env)
        self.assertEqual(result.returncode, 0, result.stderr)


# The exhaustive classification of every scaffold-mode helper command found
# in the vendored SKILL.md files. A command is RUNNABLE if it can be executed
# in a temp scaffold target with CLAUDE_PLUGIN_ROOT unset and must not fail on
# a missing/stale path. It is ILLUSTRATIVE if it needs a live external
# dependency (a real `claude` binary, a scored oracle) and so cannot smoke-run
# in this test. `test_every_scaffold_command_is_classified` FAILS if a command
# appears in the vendored docs that is in neither set — so a new unclassified
# example cannot silently ship unrun.

# (regex on the captured command tail after `<helper>.py`) -> reason
ILLUSTRATIVE_COMMANDS = {
    "gate.py": "needs an already-scaffolded, runnable oracle.sh",
    "loop.py": "needs a live `claude` binary and burns real cost per iteration",
    "hook.py": "install/uninstall mutate settings.json against an already-scaffolded "
    "oracle.sh + .servo/install.json; not a bare-scaffold smoke command",
    "heartbeat.py": "needs scheduler credentials and an already-scaffolded oracle for "
    "dispatch/run; not a bare-scaffold smoke command",
}
# helper basename -> list of (argv-after-helper) that the test executes
RUNNABLE_COMMAND_ARGS = {
    "scaffold.py": [
        ["<target>"],
        ["<target>", "--force"],
        ["detect", "<target>"],
    ],
}

_HELPER_CMD_RE = re.compile(
    r'python3\s+"?\.claude/skills/[^/]+/(?P<helper>[A-Za-z0-9_.-]+\.py)"?'
    r'(?P<tail>[^\n`]*)'
)


def _scaffold_commands(target: Path) -> list[tuple[str, str]]:
    """Extract (helper, tail) for every vendored-helper invocation in SKILL.md."""
    found: list[tuple[str, str]] = []
    for skill_md in _vendored_skill_md_paths(target):
        for m in _HELPER_CMD_RE.finditer(skill_md.read_text()):
            found.append((m.group("helper"), m.group("tail").strip()))
    return found


class ScaffoldCommandClassificationTests(unittest.TestCase):
    """AC2: every emitted scaffold-mode command is runnable or marked illustrative."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)

    def test_commands_were_found(self):
        # Guard against the regex silently matching nothing (which would make
        # the classification test vacuously pass).
        self.assertTrue(_scaffold_commands(self.target))

    def test_every_scaffold_command_is_classified(self):
        unclassified = []
        for helper, _tail in _scaffold_commands(self.target):
            if helper in RUNNABLE_COMMAND_ARGS or helper in ILLUSTRATIVE_COMMANDS:
                continue
            unclassified.append(helper)
        self.assertEqual(
            unclassified, [],
            f"unclassified scaffold-mode helper command(s): {unclassified}; "
            "add to RUNNABLE_COMMAND_ARGS or ILLUSTRATIVE_COMMANDS",
        )

    def test_runnable_commands_execute_without_plugin_root(self):
        env = dict(os.environ)
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        skills_root = self.target / ".claude" / "skills"
        helper_dir = {
            "scaffold.py": skills_root / f"{SKILL_PREFIX}scaffold-init",
        }
        for helper, arg_sets in RUNNABLE_COMMAND_ARGS.items():
            vendored = helper_dir[helper] / helper
            for args in arg_sets:
                concrete = [str(self.target) if a == "<target>" else a for a in args]
                result = subprocess.run(
                    [sys.executable, str(vendored), *concrete],
                    capture_output=True, text=True, env=env,
                )
                self.assertEqual(
                    result.returncode, 0,
                    f"runnable command {helper} {args} failed: {result.stderr}",
                )

    def test_illustrative_helpers_have_a_reason(self):
        for reason in ILLUSTRATIVE_COMMANDS.values():
            self.assertTrue(reason and isinstance(reason, str))


class LinkResolutionTests(unittest.TestCase):
    """AC3: relative links in vendored markdown resolve inside the target."""

    _LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)

    def _unresolved_links(self, md_path: Path) -> list[str]:
        bad = []
        for m in self._LINK_RE.finditer(md_path.read_text()):
            dest = m.group(2)
            if dest.startswith(("http://", "https://", "#", "mailto:")):
                continue
            target_path = dest.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (md_path.parent / target_path).resolve()
            if not resolved.exists():
                bad.append(dest)
        return bad

    def test_no_unresolved_relative_links_in_vendored_markdown(self):
        for md in _vendored_managed_markdown(self.target):
            self.assertEqual(
                self._unresolved_links(md), [],
                f"unresolved relative link(s) in {md}",
            )

    def test_adr_link_text_preserved_after_strip(self):
        # The agents linked `[ADR-0003](../docs/decisions/adr-0003-...)` which
        # cannot resolve inside the target; the visible text must survive.
        judge = self.target / ".claude" / "agents" / f"{AGENT_PREFIX}judge.md"
        text = judge.read_text()
        self.assertIn("ADR-0003", text)
        self.assertNotIn("../docs/decisions/adr-0003", text)

    def test_resolving_link_is_kept(self):
        # A vendored markdown file with a link that resolves inside the target
        # keeps its link untouched.
        src = _new_target()
        self.addCleanup(shutil.rmtree, src, True)
        scaffold_runtime.scaffold_runtime(src)
        skill_md = (
            src / ".claude" / "skills" / f"{SKILL_PREFIX}scaffold-init" / "SKILL.md"
        )
        # Sanity: rewriting must not have stripped ordinary prose links that
        # happen to resolve (there are none required, so this just asserts the
        # rewrite is link-preserving for resolvable targets via a synthetic case).
        sibling = skill_md.parent / "NOTE.md"
        sibling.write_text("note\n")
        skill_md.write_text(skill_md.read_text() + "\nSee [the note](NOTE.md).\n")
        # Re-run rewrite logic directly on this file.
        scaffold_runtime._rewrite_markdown_links(skill_md, src)
        self.assertIn("[the note](NOTE.md)", skill_md.read_text())


class VersionProvenanceTests(unittest.TestCase):
    """AC4: scaffold manifest records plugin.json version, no hardcoded fallback."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)
        self.manifest = json.loads(
            (self.target / RUNTIME_ROOT / "scaffold-install.json").read_text()
        )

    def test_source_version_equals_plugin_json_version(self):
        self.assertEqual(self.manifest["source_version"], PLUGIN_VERSION)

    def test_no_hardcoded_version_fallback_in_source(self):
        # The manifest version must come from plugin.json. Guard against a
        # regression that reintroduces a literal default. `plugin_version`
        # must raise rather than return a baked-in string when version is gone.
        src = (REPO_ROOT / "scripts" / "scaffold_runtime.py").read_text()
        self.assertNotRegex(
            src,
            r'source_version["\']?\s*[:=]\s*["\']\d+\.\d+',
            "scaffold_runtime.py appears to hardcode a source_version fallback",
        )

    def test_plugin_version_raises_when_version_missing(self):
        tmp = _new_target()
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / ".claude-plugin").mkdir(parents=True)
        (tmp / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "x"}))
        with self.assertRaises(ValueError):
            scaffold_runtime.plugin_version(tmp)


class IdempotentUpgradePreservesUnmanagedTests(unittest.TestCase):
    """AC5: re-run refreshes managed files but leaves unmanaged user files alone."""

    def setUp(self):
        self.target = _new_target()
        self.addCleanup(shutil.rmtree, self.target, True)
        scaffold_runtime.scaffold_runtime(self.target)

    def test_unmanaged_files_survive_rerun(self):
        claude_root = self.target / ".claude"
        custom_skill = claude_root / "skills" / "my-custom" / "note.txt"
        custom_skill.parent.mkdir(parents=True)
        custom_skill.write_text("my own skill\n")
        settings = claude_root / "settings.json"
        settings.write_text('{"hooks": {}}\n')
        extra_agent = claude_root / "agents" / "my-agent.md"
        extra_agent.write_text("# custom agent\n")

        scaffold_runtime.scaffold_runtime(self.target)

        self.assertTrue(custom_skill.is_file())
        self.assertEqual(custom_skill.read_text(), "my own skill\n")
        self.assertTrue(settings.is_file())
        self.assertEqual(settings.read_text(), '{"hooks": {}}\n')
        self.assertTrue(extra_agent.is_file())
        self.assertEqual(extra_agent.read_text(), "# custom agent\n")

    def test_managed_files_and_manifest_refreshed_on_rerun(self):
        helper = (
            self.target / ".claude" / "skills"
            / f"{SKILL_PREFIX}scaffold-init" / "scaffold.py"
        )
        helper.write_text("# tampered\n")
        manifest_path = self.target / RUNTIME_ROOT / "scaffold-install.json"
        manifest_path.write_text("{}\n")

        scaffold_runtime.scaffold_runtime(self.target)

        self.assertNotEqual(helper.read_text(), "# tampered\n")
        refreshed = json.loads(manifest_path.read_text())
        self.assertEqual(refreshed["source_version"], PLUGIN_VERSION)
        self.assertEqual(refreshed["managed_marker"], MANAGED_MARKER)

    def test_rerun_does_not_delete_managed_set(self):
        before = sorted(
            p.relative_to(self.target).as_posix()
            for p in (self.target / ".claude").rglob("*") if p.is_file()
        )
        scaffold_runtime.scaffold_runtime(self.target)
        after = sorted(
            p.relative_to(self.target).as_posix()
            for p in (self.target / ".claude").rglob("*") if p.is_file()
        )
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
