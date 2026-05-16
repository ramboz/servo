"""
AC verification tests for slices 001-01..001-04 of `/servo:scaffold-init`.

Run from the repo root:
    python3 -m unittest skills.scaffold-init.test_scaffold
or directly:
    python3 skills/scaffold-init/test_scaffold.py
"""

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCAFFOLD = REPO_ROOT / "skills" / "scaffold-init" / "scaffold.py"


def run_scaffold(target, *extra_args):
    """Invoke scaffold.py against a target directory."""
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, str(SCAFFOLD), str(target), *extra_args],
        capture_output=True,
        text=True,
        env=env,
    )


class GreenfieldScaffoldTests(unittest.TestCase):
    """AC #1 — empty-target install succeeds."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        self.result = run_scaffold(self.target)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_exit_code_zero(self):
        self.assertEqual(
            self.result.returncode, 0,
            f"scaffold.py failed: stderr={self.result.stderr}\nstdout={self.result.stdout}",
        )

    def test_oracle_sh_exists(self):
        oracle = self.target / "oracle.sh"
        self.assertTrue(oracle.exists(), "oracle.sh not created")

    def test_oracle_sh_executable(self):
        oracle = self.target / "oracle.sh"
        mode = oracle.stat().st_mode
        # owner / group / other all executable (-rwxr-xr-x or broader)
        self.assertTrue(mode & stat.S_IXUSR, "oracle.sh missing owner execute")
        self.assertTrue(mode & stat.S_IXGRP, "oracle.sh missing group execute")
        self.assertTrue(mode & stat.S_IXOTH, "oracle.sh missing other execute")

    def test_install_json_exists_and_parses(self):
        manifest_path = self.target / ".servo" / "install.json"
        self.assertTrue(manifest_path.exists(), ".servo/install.json not created")
        manifest = json.loads(manifest_path.read_text())
        self.assertIn("servo_version", manifest)
        self.assertIn("timestamp", manifest)
        self.assertEqual(manifest["installed_tier"], "tier-0")
        # 001-01 originally asserted signals == {}; 001-03 populates the
        # signals dict with explicit per-category flags. Empty target → all
        # flags False / language None / components empty.
        self.assertEqual(manifest["signals"],
                         {"tests": False, "lint": False, "ci": False, "language": None})
        self.assertEqual(manifest["components"], [])
        self.assertRegex(manifest["timestamp"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


class RefuseExistingOracleTests(unittest.TestCase):
    """AC #2 — refusal on existing oracle (re-run without --force)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        first = run_scaffold(self.target)
        self.assertEqual(first.returncode, 0, "first scaffold failed")
        self.oracle = self.target / "oracle.sh"
        self.manifest = self.target / ".servo" / "install.json"
        self.oracle_before = self.oracle.read_bytes()
        self.manifest_before = self.manifest.read_bytes()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_rerun_exits_nonzero(self):
        result = run_scaffold(self.target)
        self.assertNotEqual(result.returncode, 0, "re-run should exit non-zero")

    def test_rerun_mentions_oracle(self):
        result = run_scaffold(self.target)
        combined = (result.stderr + result.stdout).lower()
        self.assertIn("oracle.sh", combined,
                      "error message should name oracle.sh")

    def test_rerun_leaves_files_untouched(self):
        run_scaffold(self.target)
        self.assertEqual(self.oracle.read_bytes(), self.oracle_before,
                         "oracle.sh changed despite refusal")
        self.assertEqual(self.manifest.read_bytes(), self.manifest_before,
                         "install.json changed despite refusal")


class ForceOverwriteTests(unittest.TestCase):
    """AC #3 — --force overwrites oracle and rewrites install.json with new timestamp."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        first = run_scaffold(self.target)
        self.assertEqual(first.returncode, 0)
        self.manifest_path = self.target / ".servo" / "install.json"
        self.first_manifest = json.loads(self.manifest_path.read_text())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_force_succeeds(self):
        # Ensure timestamp differs (manifest has seconds-precision ISO8601)
        import time
        time.sleep(1.1)
        result = run_scaffold(self.target, "--force")
        self.assertEqual(
            result.returncode, 0,
            f"--force should succeed: stderr={result.stderr}",
        )
        new_manifest = json.loads(self.manifest_path.read_text())
        self.assertNotEqual(
            new_manifest["timestamp"],
            self.first_manifest["timestamp"],
            "timestamp should be rewritten on --force",
        )
        self.assertTrue((self.target / "oracle.sh").exists())


class MissingTargetTests(unittest.TestCase):
    """AC #4 — refusal on missing target path."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-test-")
        self.bogus = Path(self.tmpdir) / "does-not-exist"
        # Deliberately do NOT mkdir

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_target_exits_nonzero(self):
        result = run_scaffold(self.bogus)
        self.assertNotEqual(result.returncode, 0,
                            "missing target should exit non-zero")

    def test_missing_target_clear_error(self):
        result = run_scaffold(self.bogus)
        combined = (result.stderr + result.stdout).lower()
        # Some signal that target wasn't found / doesn't exist
        self.assertTrue(
            any(tok in combined for tok in ("not exist", "no such", "not found", "missing")),
            f"unclear error message: {combined!r}",
        )

    def test_missing_target_no_side_effects(self):
        run_scaffold(self.bogus)
        self.assertFalse(self.bogus.exists(),
                         "bogus path should not have been created")


class DependencyFreeTests(unittest.TestCase):
    """AC #5 — helper runs on system Python 3.10+ with no pip install."""

    def test_no_third_party_imports(self):
        text = SCAFFOLD.read_text()
        # Crude but adequate: every `import X` / `from X import` line targets a stdlib module.
        import re
        stdlib_top_levels = {
            "argparse", "json", "os", "re", "subprocess", "sys", "stat",
            "shutil", "pathlib", "dataclasses", "datetime", "typing",
            "collections", "itertools", "functools", "tempfile", "io",
            "contextlib", "errno", "enum", "uuid", "textwrap", "string",
            "platform",
        }
        for line in text.splitlines():
            line = line.strip()
            m = re.match(r"^(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", line)
            if not m:
                continue
            top = m.group(1)
            # Local modules under skills/* would be relative — flag absolute non-stdlib.
            self.assertIn(
                top, stdlib_top_levels,
                f"non-stdlib import found: {top!r} on line: {line!r}",
            )


# ============================================================================
# Slice 001-02 — template-content
# ============================================================================


def run_oracle(target, env_overrides=None):
    """Invoke the scaffolded oracle.sh in `target` with optional env overrides."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        ["bash", str(target / "oracle.sh")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(target),
    )


def _seed_placeholder_component(target: Path):
    """Append a controllable placeholder component to a scaffolded oracle.sh.

    After slice 001-03, the scaffold no longer ships a default placeholder —
    components only land when a real signal is detected. The 001-02 driver-
    mechanics tests still need a deterministic component to exercise weighting,
    threshold gating, and exit codes, so they seed this controllable stub
    after scaffolding."""
    oracle = target / "oracle.sh"
    text = oracle.read_text()
    # Insert into COMPONENTS=( ... )
    new_text, n = re.subn(
        r"COMPONENTS=\(\s*\n",
        'COMPONENTS=(\n  "placeholder:1.0"\n',
        text,
        count=1,
    )
    if n == 0:
        raise RuntimeError("could not find COMPONENTS=() to seed")
    # Insert SEED block before the driver loop.
    seed_block = (
        "\n# SEED:start placeholder\n"
        "score_placeholder() {\n"
        '  echo "${PLACEHOLDER_SCORE:-1.0}"\n'
        "}\n"
        "# SEED:end placeholder\n"
    )
    new_text2, n2 = re.subn(
        r'(weighted_sum="0")',
        seed_block + r"\1",
        new_text,
        count=1,
    )
    if n2 == 0:
        raise RuntimeError("could not find driver-loop anchor to insert SEED block")
    oracle.write_text(new_text2)


class _ScaffoldedFixture(unittest.TestCase):
    """Base class — scaffold an empty target and seed a controllable placeholder."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        result = run_scaffold(self.target)
        self.assertEqual(result.returncode, 0,
                         f"scaffold failed: {result.stderr}")
        _seed_placeholder_component(self.target)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class WeightedCompositeTests(_ScaffoldedFixture):
    """AC #1 — scaffolded oracle.sh runs and prints a single-line summary."""

    def test_exit_code_in_zero_one_two(self):
        result = run_oracle(self.target)
        self.assertIn(
            result.returncode, (0, 1, 2),
            f"unexpected exit code {result.returncode}; stderr={result.stderr}",
        )

    def test_default_exit_zero(self):
        # Default placeholder scores 1.0; default THRESHOLD must be reachable.
        result = run_oracle(self.target)
        self.assertEqual(
            result.returncode, 0,
            f"default install should pass: stderr={result.stderr}\nstdout={result.stdout}",
        )

    def test_summary_single_line(self):
        result = run_oracle(self.target)
        stdout_lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        self.assertEqual(len(stdout_lines), 1,
                         f"expected one summary line; got {stdout_lines!r}")
        import re
        self.assertRegex(
            stdout_lines[0],
            r"^oracle:\s+composite=[0-9]+(\.[0-9]+)?\s+threshold=[0-9]+(\.[0-9]+)?\s*$",
            f"summary format unexpected: {stdout_lines[0]!r}",
        )


class ThresholdGateTests(_ScaffoldedFixture):
    """AC #2 — threshold gate works."""

    def test_below_threshold_exits_one(self):
        result = run_oracle(self.target, {"PLACEHOLDER_SCORE": "0.0", "THRESHOLD": "1.0"})
        self.assertEqual(
            result.returncode, 1,
            f"score 0.0 < threshold 1.0 should exit 1: stderr={result.stderr}\nstdout={result.stdout}",
        )

    def test_at_or_above_threshold_exits_zero(self):
        result = run_oracle(self.target, {"PLACEHOLDER_SCORE": "0.0", "THRESHOLD": "0.0"})
        self.assertEqual(
            result.returncode, 0,
            f"score 0.0 >= threshold 0.0 should exit 0: stderr={result.stderr}\nstdout={result.stdout}",
        )


class EnvErrorDistinguishableTests(_ScaffoldedFixture):
    """AC #3 — env error (missing tool) is distinguishable from below-threshold."""

    def _inject_missing_tool_component(self):
        """Replace the placeholder block with a component that depends on a
        definitely-absent binary, then return."""
        oracle = self.target / "oracle.sh"
        text = oracle.read_text()
        # Replace the SEED block contents.
        import re
        new_block = (
            "# SEED:start placeholder\n"
            "score_placeholder() {\n"
            "  if ! command -v servo-test-nonexistent-tool >/dev/null 2>&1; then\n"
            "    echo \"missing: servo-test-nonexistent-tool\" >&2\n"
            "    return 2\n"
            "  fi\n"
            "  echo \"1.0\"\n"
            "}\n"
            "# SEED:end placeholder"
        )
        new_text, n = re.subn(
            r"# SEED:start placeholder\n.*?# SEED:end placeholder",
            new_block,
            text,
            count=1,
            flags=re.DOTALL,
        )
        self.assertEqual(n, 1, "could not find SEED:start/end placeholder block to patch")
        oracle.write_text(new_text)

    def test_missing_command_exits_two(self):
        self._inject_missing_tool_component()
        result = run_oracle(self.target)
        self.assertEqual(
            result.returncode, 2,
            f"missing tool should exit 2: stderr={result.stderr}\nstdout={result.stdout}",
        )

    def test_missing_command_names_component(self):
        self._inject_missing_tool_component()
        result = run_oracle(self.target)
        combined = result.stderr + result.stdout
        self.assertIn(
            "placeholder", combined,
            f"error should name the failing component 'placeholder': {combined!r}",
        )


class SeedBlockTests(unittest.TestCase):
    """AC #4 — # SEED:start <name> / # SEED:end <name> blocks demarcated.

    After 001-03, the per-component SEED blocks live in fragment files under
    `templates/components/`. This test asserts the fragment files follow the
    convention; the runtime presence of SEED blocks in a scaffolded oracle is
    covered by `SignalDetectionTests`."""

    def test_fragments_directory_exists(self):
        frag_dir = REPO_ROOT / "templates" / "components"
        self.assertTrue(
            frag_dir.is_dir(),
            f"expected fragment directory at {frag_dir}",
        )
        fragments = list(frag_dir.glob("*.sh.fragment"))
        self.assertGreaterEqual(len(fragments), 1,
                                "expected at least one *.sh.fragment file")

    def test_each_fragment_has_paired_seed_markers(self):
        frag_dir = REPO_ROOT / "templates" / "components"
        for frag in sorted(frag_dir.glob("*.sh.fragment")):
            text = frag.read_text()
            starts = re.findall(r"^# SEED:start (\S+)\s*$", text, flags=re.MULTILINE)
            ends = re.findall(r"^# SEED:end (\S+)\s*$", text, flags=re.MULTILINE)
            self.assertEqual(starts, ends,
                             f"{frag.name}: SEED start/end mismatch — {starts} vs {ends}")
            self.assertEqual(len(starts), 1,
                             f"{frag.name}: expected exactly one SEED block, got {len(starts)}")

    def test_each_fragment_has_score_function(self):
        frag_dir = REPO_ROOT / "templates" / "components"
        for frag in sorted(frag_dir.glob("*.sh.fragment")):
            text = frag.read_text()
            m = re.search(
                r"# SEED:start (\S+).*?score_\1\s*\(\)\s*\{.*?# SEED:end \1",
                text,
                flags=re.DOTALL,
            )
            self.assertIsNotNone(
                m, f"{frag.name}: expected a SEED block wrapping a score_<name> function",
            )


class SeedDocumentationTests(unittest.TestCase):
    """AC #4 — README documents how a project adds custom SEED blocks."""

    def test_readme_explains_seed_convention(self):
        readme = (REPO_ROOT / "README.md").read_text()
        self.assertIn("# SEED:start", readme,
                      "README should mention the # SEED:start marker")
        self.assertIn("# SEED:end", readme,
                      "README should mention the # SEED:end marker")
        self.assertIn("score_", readme,
                      "README should reference the score_<name> function convention")


class ShellcheckTests(unittest.TestCase):
    """AC #5 (slice 001-02) — the *rendered* oracle.sh is shellcheck-clean
    at warning severity. Post-001-03, the template carries `{{PLACEHOLDER}}`
    substitution markers and the fragment files lack shebangs (they're
    partial), so shellchecking those intermediates is meaningless — the
    contract is about what the user actually runs."""

    def test_rendered_oracle_shellcheck_clean(self):
        wrapper = REPO_ROOT / "scripts" / "shellcheck.sh"
        self.assertTrue(wrapper.exists(),
                        f"scripts/shellcheck.sh missing at {wrapper}")
        tmp = tempfile.mkdtemp(prefix="servo-shellcheck-")
        try:
            target = Path(tmp) / "demo"
            target.mkdir()
            # Seed every detector so the rendered oracle exercises every fragment.
            (target / "pyproject.toml").write_text(
                "[tool.pytest.ini_options]\n[tool.ruff]\n"
            )
            (target / "package.json").write_text(
                '{"devDependencies": {"vitest": "*", "jest": "*"}}'
            )
            (target / ".eslintrc.json").write_text("{}\n")
            (target / "Cargo.toml").write_text('[package]\nname = "x"\n')
            (target / "go.mod").write_text("module x\n")
            result = run_scaffold(target)
            self.assertEqual(result.returncode, 0,
                             f"scaffold failed: {result.stderr}")
            sc = subprocess.run(
                [str(wrapper), "-S", "warning", str(target / "oracle.sh")],
                capture_output=True, text=True,
            )
            # Wrapper returns 127 when neither local shellcheck nor docker
            # is available — only skip in that case, not when shellcheck
            # is merely absent.
            if sc.returncode == 127:
                self.skipTest(f"shellcheck unavailable: {sc.stderr.strip()}")
            self.assertEqual(
                sc.returncode, 0,
                f"shellcheck warnings:\n{sc.stdout}\n{sc.stderr}",
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ============================================================================
# Slice 001-03 — signal-detection
# ============================================================================


def _seed_pyproject_pytest(target: Path):
    (target / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nminversion = "6.0"\n'
    )


def _seed_package_json(target: Path, dev_deps: dict):
    payload = {"name": "demo", "devDependencies": dev_deps}
    (target / "package.json").write_text(json.dumps(payload) + "\n")


def _seed_eslintrc(target: Path):
    (target / ".eslintrc.json").write_text('{"rules": {}}\n')


class SignalDetectionTests(unittest.TestCase):
    """AC #1, #2, #3 — detected signals tailor the generated oracle."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-test-")
        self.target = Path(self.tmpdir) / "demo"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_pytest_only_gets_pytest_block(self):
        _seed_pyproject_pytest(self.target)
        result = run_scaffold(self.target)
        self.assertEqual(result.returncode, 0,
                         f"scaffold failed: {result.stderr}")
        oracle = (self.target / "oracle.sh").read_text()
        self.assertIn("score_pytest", oracle, "expected score_pytest block")
        self.assertIn("# SEED:start pytest", oracle)
        self.assertIn("# SEED:end pytest", oracle)
        self.assertNotIn("score_eslint", oracle, "should not have eslint block")
        self.assertNotIn("score_ruff", oracle, "should not have ruff block")
        manifest = json.loads((self.target / ".servo" / "install.json").read_text())
        self.assertIn("pytest", manifest["components"])
        self.assertNotIn("eslint", manifest["components"])

    def test_mixed_project_gets_multiple_components(self):
        _seed_package_json(self.target, {"vitest": "^1.0"})
        _seed_eslintrc(self.target)
        result = run_scaffold(self.target)
        self.assertEqual(result.returncode, 0,
                         f"scaffold failed: {result.stderr}")
        oracle = (self.target / "oracle.sh").read_text()
        self.assertIn("score_vitest", oracle)
        self.assertIn("score_eslint", oracle)
        self.assertIn("# SEED:start vitest", oracle)
        self.assertIn("# SEED:start eslint", oracle)
        # COMPONENTS array carries both names
        self.assertRegex(oracle, r'"vitest:[0-9.]+"', "COMPONENTS missing vitest entry")
        self.assertRegex(oracle, r'"eslint:[0-9.]+"', "COMPONENTS missing eslint entry")
        manifest = json.loads((self.target / ".servo" / "install.json").read_text())
        self.assertIn("vitest", manifest["components"])
        self.assertIn("eslint", manifest["components"])

    def test_no_signals_gets_comment_only_oracle(self):
        result = run_scaffold(self.target)
        self.assertEqual(result.returncode, 0,
                         f"scaffold failed: {result.stderr}")
        oracle_path = self.target / "oracle.sh"
        # 1. No score_* functions
        oracle_text = oracle_path.read_text()
        self.assertNotIn("score_pytest", oracle_text)
        self.assertNotIn("score_eslint", oracle_text)
        # 2. Still valid bash
        check = subprocess.run(
            ["bash", "-n", str(oracle_path)],
            capture_output=True, text=True,
        )
        self.assertEqual(check.returncode, 0,
                         f"oracle.sh not valid bash: {check.stderr}")
        # 3. Runs and exits 2 with a 'no signals' message
        run = run_oracle(self.target)
        self.assertEqual(
            run.returncode, 2,
            f"no-signals oracle should exit 2: stderr={run.stderr}\nstdout={run.stdout}",
        )
        combined = (run.stderr + run.stdout).lower()
        self.assertIn("no signals detected", combined,
                      f"expected 'no signals detected' in output: {combined!r}")
        # 4. Manifest reflects empty components
        manifest = json.loads((self.target / ".servo" / "install.json").read_text())
        self.assertEqual(manifest["components"], [])


class JigFallbackTests(unittest.TestCase):
    """AC #4 — built-in detector works for the primary test frameworks
    even when jig's tdd.py is absent (CLAUDE_PLUGIN_ROOT points at servo,
    which does not contain `jig/skills/tdd-loop/tdd.py`)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-test-")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _scaffold_with(self, fname: str, content: str, component: str):
        target = Path(self.tmpdir) / component
        target.mkdir()
        (target / fname).write_text(content)
        result = run_scaffold(target)
        self.assertEqual(
            result.returncode, 0,
            f"scaffold failed for {component}: {result.stderr}",
        )
        manifest = json.loads((target / ".servo" / "install.json").read_text())
        self.assertIn(
            component, manifest["components"],
            f"expected {component!r} in manifest.components, got {manifest['components']}",
        )

    def test_pytest(self):
        self._scaffold_with("pyproject.toml", "[tool.pytest.ini_options]\n", "pytest")

    def test_vitest(self):
        self._scaffold_with(
            "package.json", '{"devDependencies": {"vitest": "*"}}', "vitest"
        )

    def test_jest(self):
        self._scaffold_with(
            "package.json", '{"devDependencies": {"jest": "*"}}', "jest"
        )

    def test_cargo(self):
        self._scaffold_with("Cargo.toml", '[package]\nname = "x"\n', "cargo")

    def test_go(self):
        # Component is named `go` (not `go-test`) — bash function names
        # don't permit hyphens, so the manifest key matches the function
        # suffix exactly.
        self._scaffold_with("go.mod", "module x\n", "go")


class DetectSubcommandTests(unittest.TestCase):
    """AC #5 — `scaffold.py detect <target>` prints JSON, no side effects."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-test-")
        self.target = Path(self.tmpdir) / "demo"
        self.target.mkdir()
        _seed_pyproject_pytest(self.target)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_detect(self):
        env = os.environ.copy()
        env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
        return subprocess.run(
            [sys.executable, str(SCAFFOLD), "detect", str(self.target)],
            capture_output=True, text=True, env=env,
        )

    def test_detect_prints_valid_json(self):
        result = self._run_detect()
        self.assertEqual(result.returncode, 0,
                         f"detect failed: {result.stderr}")
        data = json.loads(result.stdout)
        self.assertIn("signals", data)
        self.assertIn("components", data)
        self.assertIn("pytest", data["components"])

    def test_detect_no_side_effects(self):
        self._run_detect()
        self.assertFalse(
            (self.target / "oracle.sh").exists(),
            "detect should not create oracle.sh",
        )
        self.assertFalse(
            (self.target / ".servo").exists(),
            "detect should not create .servo/",
        )


# ============================================================================
# Slice 001-04 — deferred-decisions
# ============================================================================


class RefinementTodoTests(unittest.TestCase):
    """ACs #1-5 — scaffolder emits `<target>/.servo/refinement-todo.md`
    with the right decision categories."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-test-")
        self.target = Path(self.tmpdir) / "demo"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed(self, *pairs):
        for relpath, content in pairs:
            (self.target / relpath).write_text(content)

    def _scaffold_ok(self, *extra_args):
        result = run_scaffold(self.target, *extra_args)
        self.assertEqual(result.returncode, 0,
                         f"scaffold failed: {result.stderr}")

    def _todo_text(self) -> str:
        path = self.target / ".servo" / "refinement-todo.md"
        self.assertTrue(path.exists(),
                        f".servo/refinement-todo.md missing at {path}")
        return path.read_text()

    # AC #2 — Threshold is always present.
    def test_threshold_decision_on_pytest_only(self):
        self._seed(("pyproject.toml", "[tool.pytest.ini_options]\n"))
        self._scaffold_ok()
        text = self._todo_text()
        self.assertIn("Threshold", text)
        self.assertIn("Resolution trigger", text)
        # The chosen default should be quoted somewhere in the entry.
        self.assertIn("0.5", text)

    def test_threshold_decision_on_no_signals(self):
        # Even empty installs get a Threshold flag (AC #2 — "every install").
        self._scaffold_ok()
        text = self._todo_text()
        self.assertIn("Threshold", text)

    # AC #1 — Multi-signal install creates a Weights decision.
    def test_weights_decision_on_multi_signal(self):
        # pytest + ruff = 2 components → Weights decision.
        self._seed(("pyproject.toml",
                    "[tool.pytest.ini_options]\n[tool.ruff]\n"))
        self._scaffold_ok()
        text = self._todo_text()
        self.assertIn("Weights", text)
        self.assertIn("equal weights applied", text.lower())
        self.assertIn("Resolution trigger", text)

    # AC #5 — Single-component install: ONLY Threshold (no Weights / no Ambiguous).
    def test_single_component_only_threshold(self):
        self._seed(("pyproject.toml", "[tool.pytest.ini_options]\n"))
        self._scaffold_ok()
        text = self._todo_text()
        self.assertIn("Threshold", text)
        self.assertNotIn("## Weights", text)
        self.assertNotIn("## Ambiguous", text)

    # AC #3 — Ambiguous test runner: project with both vitest + jest configs.
    def test_ambiguous_test_runner(self):
        self._seed((
            "package.json",
            '{"devDependencies": {"vitest": "*", "jest": "*"}}',
        ))
        self._scaffold_ok()
        text = self._todo_text()
        self.assertIn("Ambiguous test runner", text)
        self.assertIn("vitest", text)
        self.assertIn("jest", text)
        # The picked one should be flagged so the user knows the disposition.
        self.assertTrue(
            "(selected)" in text or "selected" in text.lower(),
            f"expected selection indicator: {text!r}",
        )

    # AC #4 — --force rewrites the file with no duplicate decisions.
    def test_force_rewrites_no_duplicate_entries(self):
        self._seed(("pyproject.toml",
                    "[tool.pytest.ini_options]\n[tool.ruff]\n"))
        self._scaffold_ok()
        first = self._todo_text()
        result = run_scaffold(self.target, "--force")
        self.assertEqual(result.returncode, 0,
                         f"--force re-scaffold failed: {result.stderr}")
        second = self._todo_text()
        # No duplicated section headings.
        self.assertEqual(second.count("## Threshold"), 1,
                         f"Threshold duplicated: {second!r}")
        self.assertEqual(second.count("## Weights"), 1,
                         f"Weights duplicated: {second!r}")
        # The two files should contain the same set of decision headings.
        import re
        def headings(t):
            return sorted(re.findall(r"^## (.+)$", t, flags=re.MULTILINE))
        self.assertEqual(headings(first), headings(second))


if __name__ == "__main__":
    unittest.main()
