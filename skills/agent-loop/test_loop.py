"""
AC verification tests for slice 003-01 of `/servo:agent-loop` (`loop.py`).

Run from the repo root:
    python3 -m unittest skills.agent-loop.test_loop
or directly:
    python3 skills/agent-loop/test_loop.py

Test classes map 1:1 to slice 003-01 acceptance criteria:
    AC1 → IterationCapDefaultTests
    AC2 → IterationCapOverrideTests
    AC3 → EarlyHaltOnOracleTests
    AC4 → PreflightRefusalTests
    AC5 → PerIterationJsonTests
    AC6 → SummaryLineTests
    AC7 → DependencyFreeTests
    AC8 → MockClaudeHarnessTests
    AC9 → ClaudeInvocationFailedTests

The mock-claude harness (AC8) is a bash script written into a per-test
`bin/` directory; PATH is set to `<bindir>:/bin:/usr/bin` so:
  - the mock shadows any real `claude` (which typically lives outside
    /bin or /usr/bin — claude.app, /usr/local/bin, ~/.nvm/.../bin, etc.)
  - bash/env stay available for the scaffolded `oracle.sh` shebang
"""

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
LOOP = REPO_ROOT / "skills" / "agent-loop" / "loop.py"
# Slice 023-02: the 023-01 autonomy-readiness skill loop.py's readiness
# preflight subprocesses. Tests seed artifacts by importing `_goal_id` from
# this module directly (a test-only shortcut — production loop.py never
# re-derives the hash; see `_seed_readiness_artifact` below).
READINESS = REPO_ROOT / "skills" / "autonomy-readiness" / "readiness.py"

# Minimal system PATH for tests. /bin + /usr/bin host bash/env on Linux and
# macOS; intentionally excludes /usr/local/bin and any nvm/asdf shim dirs
# so the real `claude` binary cannot accidentally satisfy the test.
SYSTEM_PATH = "/bin:/usr/bin"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _make_manifest(target: Path) -> Path:
    """Drop a minimal `.servo/install.json` matching scaffold.py's schema."""
    servo_dir = target / ".servo"
    servo_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "servo_version": "0.1.0",
        "timestamp": "2026-05-19T00:00:00Z",
        "installed_tier": "tier-0",
        "signals": {"tests": False, "lint": False, "ci": False, "language": None},
        "components": [],
    }
    path = servo_dir / "install.json"
    path.write_text(json.dumps(manifest))
    return path


def _make_oracle(target: Path, body: str) -> Path:
    oracle = target / "oracle.sh"
    oracle.write_text(body)
    _make_executable(oracle)
    return oracle


def _passing_oracle(composite: float = 0.9, threshold: float = 0.5) -> str:
    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        echo 'oracle: composite={composite:.4f} threshold={threshold}'
        exit 0
    """)


def _below_threshold_oracle(composite: float = 0.2, threshold: float = 0.5) -> str:
    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        echo 'oracle: composite={composite:.4f} threshold={threshold}'
        exit 1
    """)


def _flipping_oracle(sentinel: str) -> str:
    """Below-threshold by default; passes when `<target>/<sentinel>` exists.

    Lets a test write a sentinel file from the mock claude to flip the
    next gate scoring from `below_threshold` to `pass`.
    """
    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        if [ -f '{sentinel}' ]; then
            echo 'oracle: composite=0.9 threshold=0.5'
            exit 0
        else
            echo 'oracle: composite=0.2 threshold=0.5'
            exit 1
        fi
    """)


def _markdown_section(text: str, heading: str) -> str:
    pattern = rf"(?ims)^##\s+{re.escape(heading)}\s*\n.*?(?=^##\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(0) if match else ""


def _claude_json_payload(
    *, session_id: str = "mock-session-1",
    cost: float = 0.05,
    terminal_reason: str = "completed",
) -> str:
    """Canonical claude JSON output for the mock harness (AC8).

    Mirrors the spike-captured schema with the load-bearing fields for
    003-01: session_id, total_cost_usd, terminal_reason, plus the
    usage/modelUsage scaffolding 003-02..03 will read for cost / context-fill.
    """
    payload = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "session_id": session_id,
        "total_cost_usd": cost,
        "terminal_reason": terminal_reason,
        "stop_reason": "end_turn",
        "num_turns": 1,
        "result": "ok",
        "usage": {
            "input_tokens": 100,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "output_tokens": 10,
        },
        "modelUsage": {
            "claude-sonnet-4-6": {
                "inputTokens": 100,
                "outputTokens": 10,
                "contextWindow": 200000,
            },
        },
    }
    return json.dumps(payload)


# Slice 003-07: the mock stands in for a `/goal`-capable claude, so its version
# must clear `GOAL_MIN_VERSION` (2.1.139). Host-scope routing (AC4) gates the
# goal driver on `claude --version`; goal-mode + auto-routing tests need the mock
# to read as capable. No test asserts this literal value (the version-mismatch
# resume tests use a distinct `9.9.9-stale-version`).
MOCK_CLAUDE_VERSION = "2.1.175"

# Slice 003-07: an isolated, empty HOME so the routing audit's *user* settings
# layer (`~/.claude/settings.json`, read by `_audit_hook_settings`) is hermetic
# across dev machines / CI — a dev's real `disableAllHooks` must not flip a test.
# Tests that exercise the user layer override HOME via `extra_env`.
import atexit as _atexit  # noqa: E402

_ISOLATED_HOME = tempfile.mkdtemp(prefix="servo-home-")
_atexit.register(lambda: shutil.rmtree(_ISOLATED_HOME, ignore_errors=True))


def _make_mock_claude(bindir: Path, body: str, *, version: str = MOCK_CLAUDE_VERSION) -> Path:
    """Write an executable `claude` script into `bindir`. PATH-injected by tests.

    Wraps `body` with a `--version` short-circuit so slice 003-04's
    `_get_claude_version()` capture (which runs once per fresh-run /
    resume) does not interfere with the body's iteration counter or args
    log. Body's shebang is preserved; the --version branch is inserted
    immediately after it.
    """
    lines = body.split("\n", 1)
    if len(lines) == 2 and lines[0].startswith("#!"):
        shebang, rest = lines
    else:
        shebang = "#!/usr/bin/env bash"
        rest = body
    wrapped = (
        f"{shebang}\n"
        f'if [ "$1" = "--version" ]; then\n'
        f'    echo "{version}"\n'
        f'    exit 0\n'
        f"fi\n"
        f"{rest}"
    )
    bindir.mkdir(parents=True, exist_ok=True)
    claude = bindir / "claude"
    claude.write_text(wrapped)
    _make_executable(claude)
    return claude


def _mock_claude_constant(bindir: Path, json_payload: str, counter_file: Path) -> Path:
    """Mock that emits the same JSON every iteration; increments a counter file."""
    body = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        counter_file='{counter_file}'
        if [ -f "$counter_file" ]; then
            n=$(cat "$counter_file")
        else
            n=0
        fi
        n=$((n + 1))
        echo "$n" > "$counter_file"
        cat <<'__JSON_EOF__'
        {json_payload}
        __JSON_EOF__
    """)
    return _make_mock_claude(bindir, body)


def _mock_claude_flip_at(
    bindir: Path,
    json_payload: str,
    counter_file: Path,
    flip_at: int,
    sentinel_path: Path,
) -> Path:
    """Mock that, on its `flip_at`-th invocation (1-indexed), touches sentinel_path.

    Combined with `_flipping_oracle`, lets a test simulate "claude made a
    change that the oracle now scores as a pass."
    """
    body = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        counter_file='{counter_file}'
        if [ -f "$counter_file" ]; then
            n=$(cat "$counter_file")
        else
            n=0
        fi
        n=$((n + 1))
        echo "$n" > "$counter_file"
        if [ "$n" -ge "{flip_at}" ]; then
            touch '{sentinel_path}'
        fi
        cat <<'__JSON_EOF__'
        {json_payload}
        __JSON_EOF__
    """)
    return _make_mock_claude(bindir, body)


def _run_loop(
    target: Path,
    *extra_args: str,
    mock_bindir: Optional[Path] = None,
    path_override: Optional[str] = None,
    extra_env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    """Invoke loop.py with a sandboxed PATH.

    `mock_bindir` is prepended to /bin:/usr/bin so the mock claude shadows
    any real claude on the host. `path_override` lets a test set PATH
    explicitly (e.g., AC9 binary-not-on-PATH test). `extra_env` adds
    arbitrary env vars (e.g., SERVO_CLAUDE_TIMEOUT) on top of the sandboxed
    PATH.

    Slice 003-05: plateau detection is disabled by default in tests
    (`--plateau-window 0` is prepended unless the caller explicitly passes
    `--plateau-window`). Slice-003-01..04 tests use constant-composite
    mocks that would otherwise trip the default plateau brake at iter 4
    instead of running to the test's expected iteration count. Plateau-
    specific tests opt back in by passing their own `--plateau-window N`.

    Slice 003-07: pins `--driver loop` (unless the caller passes `--driver`)
    so these loop-driver tests exercise the driver they target regardless of
    the new `auto` default, and defaults HOME to an isolated empty dir so the
    routing audit's user-settings layer stays hermetic.

    Slice 023-02: defaults `SERVO_READINESS_GATE=0` (the readiness preflight's
    bypass seam) so these pre-existing surface tests keep testing what they
    test, unaffected by the new gate on `--background` / `--emit-routine-
    prompt`. A test exercising the real readiness gate passes `extra_env=
    {"SERVO_READINESS_GATE": "1"}` (or any non-bypass value) to re-enable it.
    """
    if "--plateau-window" not in extra_args:
        extra_args = ("--plateau-window", "0", *extra_args)
    if "--driver" not in extra_args:
        extra_args = ("--driver", "loop", *extra_args)
    if path_override is not None:
        path = path_override
    elif mock_bindir is not None:
        path = f"{mock_bindir}:{SYSTEM_PATH}"
    else:
        path = SYSTEM_PATH
    env = {**os.environ, "PATH": path, "HOME": _ISOLATED_HOME,
           "SERVO_READINESS_GATE": "0"}
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, str(LOOP), str(target), *extra_args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _stdout_json_lines(stdout: str) -> list[dict]:
    """Parse every non-empty stdout line as JSON."""
    return [json.loads(line) for line in stdout.strip().splitlines() if line.strip()]


# ============================================================================
# Slice 003-01 — AC #1: Iteration cap (default = 5)
# ============================================================================


class IterationCapDefaultTests(unittest.TestCase):
    """AC #1 — default iteration cap halts the loop at 5 iterations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac1-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_runs_exactly_five_iterations(self):
        result = _run_loop(
            self.target,
            "--prompt", "make it pass",
            mock_bindir=self.bindir,
        )
        self.assertEqual(
            result.returncode, 0,
            f"expected rc=0, got {result.returncode}; stderr={result.stderr}",
        )
        self.assertTrue(self.counter.exists())
        self.assertEqual(int(self.counter.read_text().strip()), 5)

    def test_summary_terminal_reason_is_max_iterations_reached(self):
        result = _run_loop(
            self.target,
            "--prompt", "x",
            mock_bindir=self.bindir,
        )
        lines = _stdout_json_lines(result.stdout)
        summary = lines[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertEqual(summary["iterations_completed"], 5)


# ============================================================================
# Slice 003-01 — AC #2: Iteration cap (--max-iterations override)
# ============================================================================


class IterationCapOverrideTests(unittest.TestCase):
    """AC #2 — `--max-iterations N` runs exactly N iterations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac2-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_override_to_three_iterations(self):
        result = _run_loop(
            self.target,
            "--prompt", "x",
            "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 3)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["iterations_completed"], 3)
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")

    def test_override_to_one_iteration(self):
        result = _run_loop(
            self.target,
            "--prompt", "x",
            "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 1)

    def test_max_iterations_zero_rejected(self):
        # --max-iterations 0 is meaningless for 003-01 (no iteration → no
        # scoring possible). argparse's parser.error() exits rc=2 — matching
        # the closed {0, 2} exit-code contract loop.py promises.
        result = _run_loop(
            self.target,
            "--prompt", "x",
            "--max-iterations", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--max-iterations must be >= 1", result.stderr)


# ============================================================================
# Slice 003-01 — AC #3: Early halt on oracle pass
# ============================================================================


class EarlyHaltOnOracleTests(unittest.TestCase):
    """AC #3 — loop halts at iteration K when gate exits 0 (oracle pass).

    Setup: scaffolded oracle that flips behavior based on a sentinel file
    inside the target. The mock claude touches the sentinel on its 2nd
    invocation, so:
      - iteration 1: sentinel absent → composite < threshold → gate exits 1
      - iteration 2: sentinel present → composite ≥ threshold → gate exits 0
      - iteration 3..5: never run
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac3-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        self.sentinel_name = ".servo-test-pass-sentinel"
        _make_oracle(self.target, _flipping_oracle(self.sentinel_name))
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        # Sentinel path is relative-to-target (the oracle runs with cwd=target).
        sentinel_path = self.target / self.sentinel_name
        _mock_claude_flip_at(
            self.bindir,
            _claude_json_payload(),
            self.counter,
            flip_at=2,
            sentinel_path=sentinel_path,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_halts_at_iteration_two(self):
        result = _run_loop(
            self.target,
            "--prompt", "fix it",
            "--max-iterations", "5",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # claude invoked exactly twice — iteration 3 should not have fired.
        self.assertEqual(int(self.counter.read_text().strip()), 2)

    def test_summary_reports_oracle_passed(self):
        result = _run_loop(
            self.target,
            "--prompt", "fix it",
            "--max-iterations", "5",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_passed")
        self.assertEqual(summary["iterations_completed"], 2)
        self.assertEqual(summary["final_oracle_status"], "pass")

    def test_iteration_three_not_invoked(self):
        result = _run_loop(
            self.target,
            "--prompt", "fix it",
            "--max-iterations", "5",
            mock_bindir=self.bindir,
        )
        # Per-iteration JSON lines: exactly 2 lines + 1 summary = 3 total.
        lines = _stdout_json_lines(result.stdout)
        per_iter = [line for line in lines if "iteration" in line]
        self.assertEqual(len(per_iter), 2)
        # Iteration numbers are 1-indexed and contiguous.
        self.assertEqual([line["iteration"] for line in per_iter], [1, 2])


# ============================================================================
# Slice 003-01 — AC #4: Preflight refusal (missing target/manifest/oracle)
# ============================================================================


class PreflightRefusalTests(unittest.TestCase):
    """AC #4 — loop refuses with rc=2 before iteration 1 when preconditions fail.

    Each refusal mode shares the gate.py reason vocabulary:
      target_missing / manifest_missing / oracle_missing.

    All three modes must NOT invoke claude (verified via the counter file).
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac4-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        # Mock that records every invocation. Iff this fires, AC4 is violated.
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _assert_summary_reason(self, stdout: str, expected_reason: str):
        summary = _stdout_json_lines(stdout)[-1]
        self.assertEqual(summary["terminal_reason"], expected_reason)
        self.assertEqual(summary["iterations_completed"], 0)
        self.assertEqual(summary["final_oracle_status"], "env_error")
        self.assertEqual(summary["cumulative_cost_usd"], 0.0)

    def test_missing_target(self):
        bogus = self.tmp / "does-not-exist"
        result = _run_loop(
            bogus, "--prompt", "x", mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("target does not exist", result.stderr)
        self._assert_summary_reason(result.stdout, "target_missing")
        self.assertFalse(self.counter.exists(), "claude should not have fired")

    def test_target_not_a_directory(self):
        not_a_dir = self.tmp / "file.txt"
        not_a_dir.write_text("not a directory")
        result = _run_loop(
            not_a_dir, "--prompt", "x", mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("not a directory", result.stderr)
        self._assert_summary_reason(result.stdout, "target_not_directory")
        self.assertFalse(self.counter.exists())

    def test_missing_manifest(self):
        target = self.tmp / "demo"
        target.mkdir()
        # Oracle present but manifest absent — isolates the manifest branch.
        _make_oracle(target, _passing_oracle())
        result = _run_loop(target, "--prompt", "x", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 2)
        self.assertIn("install.json", result.stderr)
        self.assertIn("scaffold-init", result.stderr)
        self._assert_summary_reason(result.stdout, "manifest_missing")
        self.assertFalse(self.counter.exists())

    def test_missing_oracle(self):
        target = self.tmp / "demo"
        target.mkdir()
        # Manifest present but oracle absent — isolates the oracle branch.
        _make_manifest(target)
        result = _run_loop(target, "--prompt", "x", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 2)
        self.assertIn("oracle.sh not found", result.stderr)
        self.assertIn("scaffold-init", result.stderr)
        self._assert_summary_reason(result.stdout, "oracle_missing")
        self.assertFalse(self.counter.exists())


# ============================================================================
# Slice 003-01 — AC #5: Per-iteration JSON shape
# ============================================================================


class PerIterationJsonTests(unittest.TestCase):
    """AC #5 — each completed iteration emits a stdout JSON line with required fields."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac5-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle(0.3, 0.5))
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(
            self.bindir,
            _claude_json_payload(
                session_id="iter-session-77", cost=0.12, terminal_reason="completed",
            ),
            self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_required_fields_present(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        lines = _stdout_json_lines(result.stdout)
        per_iter = [line for line in lines if "iteration" in line]
        self.assertEqual(len(per_iter), 2)
        for line in per_iter:
            # AC5 required minimum field set.
            self.assertIn("iteration", line)
            self.assertIn("session_id", line)
            self.assertIn("cost_usd", line)
            self.assertIn("terminal_reason", line)
            self.assertIn("oracle_exit_code", line)
            self.assertIn("oracle_composite", line)
            self.assertIn("oracle_threshold", line)
            # Types per AC5.
            self.assertIsInstance(line["iteration"], int)
            self.assertIsInstance(line["session_id"], str)
            self.assertIsInstance(line["cost_usd"], (int, float))
            self.assertIsInstance(line["terminal_reason"], str)
            self.assertIsInstance(line["oracle_exit_code"], int)
            self.assertIn(line["oracle_exit_code"], (0, 1, 2))

    def test_field_values_reflect_inputs(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        per_iter = [line for line in _stdout_json_lines(result.stdout) if "iteration" in line]
        self.assertEqual(len(per_iter), 1)
        line = per_iter[0]
        self.assertEqual(line["iteration"], 1)
        self.assertEqual(line["session_id"], "iter-session-77")
        self.assertAlmostEqual(line["cost_usd"], 0.12, places=6)
        self.assertEqual(line["terminal_reason"], "completed")
        self.assertEqual(line["oracle_exit_code"], 1)  # below_threshold
        self.assertAlmostEqual(line["oracle_composite"], 0.3, places=6)
        self.assertAlmostEqual(line["oracle_threshold"], 0.5, places=6)

    def test_iteration_field_is_one_indexed_and_contiguous(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "4",
            mock_bindir=self.bindir,
        )
        per_iter = [line for line in _stdout_json_lines(result.stdout) if "iteration" in line]
        self.assertEqual([line["iteration"] for line in per_iter], [1, 2, 3, 4])


# ============================================================================
# Slice 003-01 — AC #6: Summary line shape
# ============================================================================


class SummaryLineTests(unittest.TestCase):
    """AC #6 — final JSON line shape after the last iteration (or refusal)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac6-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(
            self.bindir, _claude_json_payload(cost=0.20), self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_max_iterations_summary_shape(self):
        _make_oracle(self.target, _below_threshold_oracle())
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        # Required field set.
        self.assertIn("terminal_reason", summary)
        self.assertIn("iterations_completed", summary)
        self.assertIn("cumulative_cost_usd", summary)
        self.assertIn("final_oracle_status", summary)
        self.assertIn("run_id", summary)
        # Values.
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertEqual(summary["iterations_completed"], 2)
        self.assertAlmostEqual(summary["cumulative_cost_usd"], 0.40, places=6)
        self.assertEqual(summary["final_oracle_status"], "below_threshold")

    def test_oracle_passed_summary_shape(self):
        _make_oracle(self.target, _passing_oracle())
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_passed")
        self.assertEqual(summary["iterations_completed"], 1)
        self.assertAlmostEqual(summary["cumulative_cost_usd"], 0.20, places=6)
        self.assertEqual(summary["final_oracle_status"], "pass")

    def test_run_id_format(self):
        _make_oracle(self.target, _below_threshold_oracle())
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        # Per ADR-0004: YYYYMMDDTHHMMSS-XXXX (4-hex suffix).
        self.assertRegex(summary["run_id"], r"^\d{8}T\d{6}-[0-9a-f]{4}$")
        # Per-iteration JSON carries the same run_id.
        per_iter = [line for line in _stdout_json_lines(result.stdout) if "iteration" in line]
        self.assertEqual(per_iter[0]["run_id"], summary["run_id"])

    def test_run_id_unique_per_invocation(self):
        # Two consecutive invocations produce two distinct run-ids.
        _make_oracle(self.target, _below_threshold_oracle())
        r1 = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        # Reset the counter so the second run starts fresh.
        self.counter.unlink(missing_ok=True)
        r2 = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        id1 = _stdout_json_lines(r1.stdout)[-1]["run_id"]
        id2 = _stdout_json_lines(r2.stdout)[-1]["run_id"]
        self.assertNotEqual(id1, id2)


# ============================================================================
# Slice 003-01 — AC #7: Dependency-free
# ============================================================================


class DependencyFreeTests(unittest.TestCase):
    """AC #7 — loop.py uses only the Python 3.10+ standard library."""

    def test_no_third_party_imports(self):
        text = LOOP.read_text()
        stdlib_top_levels = {
            "__future__",
            "argparse", "json", "os", "re", "subprocess", "sys", "stat",
            "shutil", "pathlib", "dataclasses", "datetime", "typing",
            "collections", "itertools", "functools", "tempfile", "io",
            "contextlib", "errno", "enum", "uuid", "textwrap", "string",
            "platform", "signal", "secrets", "hashlib", "math", "time",
            "importlib",  # stdlib: load the consumer-only identity reader
        }
        for line in text.splitlines():
            stripped = line.strip()
            m = re.match(r"^(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
            if not m:
                continue
            top = m.group(1)
            self.assertIn(
                top, stdlib_top_levels,
                f"non-stdlib import found: {top!r} on line: {stripped!r}",
            )

    def test_no_requirements_file_alongside_helper(self):
        for name in ("requirements.txt", "setup.py", "pyproject.toml"):
            self.assertFalse(
                (LOOP.parent / name).exists(),
                f"unexpected dependency descriptor at {LOOP.parent / name}",
            )


# ============================================================================
# Slice 003-01 — AC #8: Mock-claude harness
# ============================================================================


class MockClaudeHarnessTests(unittest.TestCase):
    """AC #8 — fake `claude` binary via PATH; emits canned schema JSON."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac8-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_canned_schema_round_trip(self):
        """Mock-emitted JSON parses cleanly and load-bearing fields surface."""
        counter = Path(self.tmpdir) / "counter.txt"
        _mock_claude_constant(
            self.bindir,
            _claude_json_payload(
                session_id="harness-test-uuid", cost=0.077,
                terminal_reason="completed",
            ),
            counter,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        per_iter = [line for line in _stdout_json_lines(result.stdout) if "iteration" in line]
        self.assertEqual(len(per_iter), 1)
        self.assertEqual(per_iter[0]["session_id"], "harness-test-uuid")
        self.assertAlmostEqual(per_iter[0]["cost_usd"], 0.077, places=6)
        self.assertEqual(per_iter[0]["terminal_reason"], "completed")

    def test_path_injection_shadows_real_claude(self):
        """The mock claude must be the binary loop.py picks up, not any host claude."""
        counter = Path(self.tmpdir) / "counter.txt"
        sentinel_session = "mock-only-9f3a-b21d"
        _mock_claude_constant(
            self.bindir,
            _claude_json_payload(session_id=sentinel_session),
            counter,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        per_iter = [line for line in _stdout_json_lines(result.stdout) if "iteration" in line]
        self.assertEqual(per_iter[0]["session_id"], sentinel_session)

    def test_canned_payload_carries_spike_schema_fields(self):
        """Sanity-check that the canonical payload helper still carries the
        fields downstream slices (003-02, 003-03) need to read."""
        payload = json.loads(_claude_json_payload())
        # 003-01: session_id, total_cost_usd, terminal_reason
        self.assertIn("session_id", payload)
        self.assertIn("total_cost_usd", payload)
        self.assertIn("terminal_reason", payload)
        # 003-02 / 003-03 forward references — needed once cost ceiling
        # and context-fill gate land. Keeping them in the canned payload
        # avoids re-authoring the mock in later slices.
        self.assertIn("usage", payload)
        self.assertIn("modelUsage", payload)
        self.assertIn("input_tokens", payload["usage"])
        self.assertIn("contextWindow", payload["modelUsage"]["claude-sonnet-4-6"])


# ============================================================================
# Slice 003-01 — AC #9: claude invocation failures
# ============================================================================


class ClaudeInvocationFailedTests(unittest.TestCase):
    """AC #9 — failures invoking `claude -p` map to rc=2 / claude_invocation_failed.

    Three test paths cover the AC9 enumeration:
      - claude not on PATH (FileNotFoundError)
      - claude exits non-zero with empty stdout
      - claude exits zero but emits unparseable JSON
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac9-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _summary(self, stdout: str) -> dict:
        return _stdout_json_lines(stdout)[-1]

    def test_claude_not_on_path(self):
        # An empty bindir means claude won't be found anywhere on PATH —
        # /bin:/usr/bin reliably exclude the host claude binary location.
        self.bindir.mkdir()
        # Explicit path override: bindir + system bins, no nvm/local.
        result = _run_loop(
            self.target,
            "--prompt", "x",
            path_override=f"{self.bindir}:{SYSTEM_PATH}",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("loop: claude not on PATH", result.stderr)

    def test_copilot_not_on_path(self):
        # Native autonomy refuses even before executable discovery (ADR-0043).
        self.bindir.mkdir()
        result = _run_loop(
            self.target,
            "--prompt", "x",
            "--host", "copilot",
            path_override=f"{self.bindir}:{SYSTEM_PATH}",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("autonomy is unavailable", result.stderr)
        summary = self._summary(result.stdout)
        self.assertEqual(summary["terminal_reason"], "native_capability_unavailable")
        self.assertEqual(summary["iterations_completed"], 0)

    def test_claude_exits_nonzero_with_empty_stdout(self):
        _make_mock_claude(self.bindir, textwrap.dedent("""\
            #!/usr/bin/env bash
            exit 1
        """))
        result = _run_loop(self.target, "--prompt", "x", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "loop: claude -p exited 1 without JSON output",
            result.stderr,
        )
        summary = self._summary(result.stdout)
        self.assertEqual(summary["terminal_reason"], "claude_invocation_failed")
        self.assertEqual(summary["iterations_completed"], 0)

    def test_claude_exits_zero_with_invalid_json(self):
        _make_mock_claude(self.bindir, textwrap.dedent("""\
            #!/usr/bin/env bash
            echo 'this is definitely not json'
        """))
        result = _run_loop(self.target, "--prompt", "x", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 2)
        self.assertIn("loop: claude JSON parse error", result.stderr)
        summary = self._summary(result.stdout)
        self.assertEqual(summary["terminal_reason"], "claude_invocation_failed")
        self.assertEqual(summary["iterations_completed"], 0)

    def test_claude_exits_nonzero_breadcrumb_carries_exit_code(self):
        """The breadcrumb names the specific exit code (forensics; AC9)."""
        _make_mock_claude(self.bindir, textwrap.dedent("""\
            #!/usr/bin/env bash
            exit 42
        """))
        result = _run_loop(self.target, "--prompt", "x", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 2)
        self.assertIn("exited 42", result.stderr)


class ClaudeErrorEnvelopeTests(unittest.TestCase):
    """Bug 001 — a hard `claude -p` error envelope is an invocation failure.

    A `claude -p` run that cannot authenticate emits *parseable* JSON with
    `is_error: true` / `api_error_status: 401` and exits 0. Before the fix,
    `_invoke_claude` returned any parseable dict as success, so the loop scored
    the errored turn as a normal below-threshold iteration and halted on
    `oracle_plateau` / `max_iterations_reached` — masking the auth failure.
    The loop must instead halt on `claude_invocation_failed` (rc=2) and name
    the real cause. Budget/turn halts (`error_max_budget_usd` /
    `error_max_turns`) are the only legitimate `is_error: true` envelopes in
    loop mode and must stay scored.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-bug001-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _summary(self, stdout: str) -> dict:
        return _stdout_json_lines(stdout)[-1]

    def test_auth_error_envelope_halts_invocation_failed(self):
        # Mirrors the reported repro: valid JSON, exit 0, but is_error/401 and
        # no modelUsage — exactly what a gateway auth failure returns.
        payload = json.dumps({
            "type": "result",
            "subtype": "error_during_execution",
            "is_error": True,
            "api_error_status": 401,
            "session_id": "auth-fail",
            "total_cost_usd": 0,
            "num_turns": 0,
            "result": (
                "Failed to authenticate. API Error: 401 Invalid "
                "authentication credentials"
            ),
        })
        _mock_claude_constant(self.bindir, payload, self.counter)
        result = _run_loop(self.target, "--prompt", "x", mock_bindir=self.bindir)
        self.assertEqual(
            result.returncode, 2,
            f"expected rc=2, got {result.returncode}; stderr={result.stderr}",
        )
        summary = self._summary(result.stdout)
        self.assertEqual(
            summary["terminal_reason"], "claude_invocation_failed")
        self.assertEqual(summary["iterations_completed"], 0)
        # The operator must see the real cause, not "the model isn't improving".
        self.assertIn("401", result.stderr)

    def test_budget_halt_envelope_is_still_scored(self):
        # A per-iteration --max-budget-usd halt is is_error:true too, but it
        # carries partial work and must remain a scored iteration.
        payload = json.dumps({
            "type": "result",
            "subtype": "error_max_budget_usd",
            "is_error": True,
            "session_id": "budget-halt",
            "total_cost_usd": 0.05,
            "num_turns": 1,
            "result": "partial work done before budget hit",
            "usage": {
                "input_tokens": 100,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "output_tokens": 10,
            },
            "modelUsage": {
                "claude-sonnet-4-6": {
                    "inputTokens": 100,
                    "outputTokens": 10,
                    "contextWindow": 200000,
                },
            },
        })
        _mock_claude_constant(self.bindir, payload, self.counter)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        self.assertEqual(
            result.returncode, 0,
            f"expected rc=0, got {result.returncode}; stderr={result.stderr}",
        )
        summary = self._summary(result.stdout)
        self.assertEqual(
            summary["terminal_reason"], "max_iterations_reached")
        self.assertEqual(summary["iterations_completed"], 2)


class LoopForwardsTargetSettingsTests(unittest.TestCase):
    """Bug 002 — the loop driver forwards the target's own .claude/settings.json.

    A headless `claude -p` inherits the host's default (prompt-on-tool)
    permission mode, which denies Write/Edit/Bash unattended. A target repo
    that pre-authorizes its tools in a committed `.claude/settings.json` must
    have that file forwarded via `--settings` so the runner can edit. Only the
    target's OWN settings are forwarded — this never injects a bypass mode, so
    host managed policy still governs. When the target declares no settings,
    the flag is omitted (host default preserved).
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-bug002-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        self.args_log = tmp / "args.log"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_forwards_settings_when_target_declares_them(self):
        settings = self.target / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(
            {"permissions": {"allow": ["Bash", "Edit", "Write"]}}))
        _mock_claude_with_args_log(
            self.bindir, _claude_json_payload(), self.counter, self.args_log)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, result.stderr)
        invocations = _read_args_log(self.args_log)
        self.assertEqual(len(invocations), 1)
        settings_arg = _find_flag_value(invocations[0], "--settings")
        self.assertIsNotNone(
            settings_arg, "loop did not forward the target's --settings")
        # loop.py resolves the target, so compare resolved paths (macOS
        # /var -> /private/var symlink otherwise trips the equality).
        self.assertEqual(Path(settings_arg).resolve(), settings.resolve())

    def test_no_settings_flag_when_target_has_none(self):
        _mock_claude_with_args_log(
            self.bindir, _claude_json_payload(), self.counter, self.args_log)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, result.stderr)
        invocations = _read_args_log(self.args_log)
        self.assertEqual(len(invocations), 1)
        self.assertNotIn("--settings", invocations[0])


# ============================================================================
# PR-review follow-on: schema_version on every JSON line (ADR-0002 mirror)
# ============================================================================


class SchemaVersionTests(unittest.TestCase):
    """Every stdout JSON line carries `schema_version: 1`.

    Mirrors gate.py's `schema_version` contract (ADR-0002) and ADR-0004's
    `state_schema_version`. Asserts the field across all three emission paths:
    per-iteration, summary, preflight-refusal.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-schema-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_per_iteration_lines_carry_schema_version(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        lines = _stdout_json_lines(result.stdout)
        per_iter = [line for line in lines if "iteration" in line]
        self.assertEqual(len(per_iter), 2)
        for line in per_iter:
            self.assertEqual(line.get("schema_version"), 1)

    def test_summary_line_carries_schema_version(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary.get("schema_version"), 1)

    def test_preflight_refusal_carries_schema_version(self):
        bogus = self.tmp / "does-not-exist"
        result = _run_loop(bogus, "--prompt", "x", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 2)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary.get("schema_version"), 1)

    def test_schema_version_is_first_key_for_grep_friendliness(self):
        """`schema_version` should appear as the first key in every line.

        Not load-bearing for JSON consumers (key order is preserved in JSON
        but unordered by spec), but useful for the human readable case: a
        `head -c 30` on any line reveals the version immediately. Mirrors
        gate.py's emission shape.
        """
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        for line in result.stdout.strip().splitlines():
            if line.strip():
                self.assertTrue(
                    line.startswith('{"schema_version": 1'),
                    f"line does not start with schema_version: {line[:60]!r}",
                )


# ============================================================================
# PR-review follow-on: per-invocation claude -p timeout
# ============================================================================


class ClaudeTimeoutTests(unittest.TestCase):
    """Per-invocation `claude -p` wall-clock timeout.

    Default DEFAULT_CLAUDE_TIMEOUT_SECONDS=1800 (30 min); tests override via
    `SERVO_CLAUDE_TIMEOUT=1` env var to keep wall-clock fast. The mock claude
    sleeps longer than the timeout, so `subprocess.run` raises TimeoutExpired,
    Python sends SIGKILL, and the loop emits `claude_invocation_failed` with
    a timeout-naming breadcrumb.

    Maps a `claude -p` hang (network stall, deadlocked tool use, etc.) to
    the same AC9 terminal_reason for uniformity, with the breadcrumb naming
    the timeout as the specific cause.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-timeout-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_claude_timeout_maps_to_invocation_failed(self):
        # Mock claude that sleeps 10s — well beyond the 1s test timeout.
        _make_mock_claude(self.bindir, textwrap.dedent("""\
            #!/usr/bin/env bash
            sleep 10
            echo '{"session_id":"never-emitted","total_cost_usd":0}'
        """))
        result = _run_loop(
            self.target, "--prompt", "x",
            mock_bindir=self.bindir,
            extra_env={"SERVO_CLAUDE_TIMEOUT": "1"},
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("loop: claude -p timed out after 1.0s", result.stderr)
        self.assertIn("(killed)", result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "claude_invocation_failed")
        self.assertEqual(summary["iterations_completed"], 0)

    def test_disabled_timeout_lets_long_claude_run(self):
        """SERVO_CLAUDE_TIMEOUT=0 disables the bound — used by callers
        enforcing a wall-clock budget out-of-band (or by no-budget tests)."""
        # Sleep just briefly — long enough to prove the timeout didn't fire,
        # short enough not to bog down the suite.
        counter = Path(self.tmpdir) / "counter.txt"
        _make_mock_claude(self.bindir, textwrap.dedent(f"""\
            #!/usr/bin/env bash
            counter_file='{counter}'
            if [ -f "$counter_file" ]; then
                n=$(cat "$counter_file")
            else
                n=0
            fi
            n=$((n + 1))
            echo "$n" > "$counter_file"
            sleep 0.2
            cat <<'__JSON_EOF__'
            {_claude_json_payload()}
            __JSON_EOF__
        """))
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
            extra_env={"SERVO_CLAUDE_TIMEOUT": "0"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(counter.read_text().strip()), 1)

    def test_malformed_env_var_falls_back_to_default(self):
        """A non-numeric SERVO_CLAUDE_TIMEOUT logs a breadcrumb and continues
        with the default (which is far longer than the mock's sleep)."""
        counter = Path(self.tmpdir) / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), counter)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
            extra_env={"SERVO_CLAUDE_TIMEOUT": "not-a-number"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn(
            "ignoring malformed SERVO_CLAUDE_TIMEOUT='not-a-number'",
            result.stderr,
        )
        self.assertIn("using default 1800s", result.stderr)


# ============================================================================
# Slice 003-02 — cost-ceiling: shared fixture helpers
# ============================================================================


def _mock_claude_with_args_log(
    bindir: Path, json_payload: str, counter_file: Path, args_log: Path,
) -> Path:
    """Constant-payload mock that also appends each invocation's argv to args_log.

    Slice 003-05 made the per-iteration prompt multi-line (embedded gate
    JSON + verdict block), so `$*` newline-joins are no longer safe to
    parse line-by-line. Each invocation is written as a single line with
    args separated by the U+001F (Unit Separator) byte, and lines are
    terminated with U+001E (Record Separator) so embedded newlines in
    args don't fragment the log. `_read_args_log` parses on these
    delimiters; the legacy `len(invocations) == N` and
    `--max-budget-usd <val>` assertions still hold.
    """
    body = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        counter_file='{counter_file}'
        args_log='{args_log}'
        if [ -f "$counter_file" ]; then
            n=$(cat "$counter_file")
        else
            n=0
        fi
        n=$((n + 1))
        echo "$n" > "$counter_file"
        for arg in "$@"; do
            printf '%s\\037' "$arg" >> "$args_log"
        done
        printf '\\036' >> "$args_log"
        cat <<'__JSON_EOF__'
        {json_payload}
        __JSON_EOF__
    """)
    return _make_mock_claude(bindir, body)


def _mock_claude_costs_per_iter(
    bindir: Path, costs: list, counter_file: Path,
    args_log: Optional[Path] = None,
) -> Path:
    """Mock that emits cost[n-1] (USD) as `total_cost_usd` on its n-th invocation.

    `costs` is a list of floats; iteration N reads the N-th line of
    `costs.txt`. Lets a test engineer a specific cumulative trajectory (e.g.,
    "cumulative must land within $0.005 of the ceiling after iter-1").
    """
    costs_file = bindir / "costs.txt"
    costs_file.parent.mkdir(parents=True, exist_ok=True)
    costs_file.write_text("\n".join(str(c) for c in costs) + "\n")
    # Args log uses U+001F / U+001E delimiters (see _mock_claude_with_args_log
    # docstring) so embedded newlines in the iteration prompt don't fragment.
    args_log_cmd = (
        f'for arg in "$@"; do printf "%s\\037" "$arg" >> \'{args_log}\'; done\n'
        f'printf "\\036" >> \'{args_log}\'\n'
    ) if args_log else ""
    # Bash heredoc must be UNQUOTED for $n / $cost substitution; literal
    # `{` / `}` in the JSON must be doubled in this Python f-string.
    body = (
        f"#!/usr/bin/env bash\n"
        f"counter_file='{counter_file}'\n"
        f"costs_file='{costs_file}'\n"
        f'if [ -f "$counter_file" ]; then\n'
        f'    n=$(cat "$counter_file")\n'
        f"else\n"
        f"    n=0\n"
        f"fi\n"
        f"n=$((n + 1))\n"
        f'echo "$n" > "$counter_file"\n'
        f"{args_log_cmd}"
        f'cost=$(sed -n "${{n}}p" "$costs_file")\n'
        f"cat <<JSON_EOF\n"
        f'{{"type":"result","subtype":"success","is_error":false,'
        f'"session_id":"mock-session-$n","total_cost_usd":$cost,'
        f'"terminal_reason":"completed","stop_reason":"end_turn",'
        f'"num_turns":1,"result":"ok",'
        f'"usage":{{"input_tokens":100,"cache_read_input_tokens":0,'
        f'"cache_creation_input_tokens":0,"output_tokens":10}},'
        f'"modelUsage":{{"claude-sonnet-4-6":{{"inputTokens":100,'
        f'"outputTokens":10,"contextWindow":200000}}}}}}\n'
        f"JSON_EOF\n"
    )
    return _make_mock_claude(bindir, body)


def _read_args_log(args_log: Path) -> list:
    """Parse the args log into a list of argv lists (one per invocation).

    Slice 003-05: args are separated by U+001F and invocations by U+001E
    (matches the mock-helper write format). Each U+001F-separated arg
    keeps its embedded whitespace / newlines intact, which is what the
    multi-line iteration-prompt assembly needs.
    """
    if not args_log.exists():
        return []
    raw = args_log.read_text()
    invocations: list = []
    for record in raw.split("\x1e"):
        if not record:
            continue
        args = record.split("\x1f")
        # Trailing U+001F after the last arg leaves an empty trailing element.
        if args and args[-1] == "":
            args.pop()
        if args:
            invocations.append(args)
    return invocations


def _find_flag_value(argv: list, flag: str) -> Optional[str]:
    """Return the value following `flag` in argv, or None if absent."""
    for i, token in enumerate(argv):
        if token == flag and i + 1 < len(argv):
            return argv[i + 1]
    return None


# ============================================================================
# Slice 003-02 — AC #1: Default cost-ceiling halts at cumulative > $2.00
# ============================================================================


class CostCeilingDefaultTests(unittest.TestCase):
    """AC #1 — with no flag, loop halts when cumulative `total_cost_usd` > $2.00.

    Mock emits $0.75 / iter. After iter-3 cumulative = $2.25 (first exceeds).
    Loop halts after iter-3 completes (gate scored, per-iter line emitted),
    summary carries `terminal_reason=cost_ceiling_reached cumulative_cost_usd=2.25`.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac1-cost-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        # Constant $0.75 per iteration. Use the costs-per-iter helper with 10
        # entries so we don't run out before the loop halts.
        _mock_claude_costs_per_iter(
            self.bindir, [0.75] * 10, self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_halts_after_iter_three(self):
        # Default --max-iterations=5, default --cost-ceiling=$2.00. Cumulative
        # reaches 0.75 → 1.50 → 2.25 across iters 1..3; iter-3 puts it over,
        # post-iter check halts before iter-4.
        result = _run_loop(
            self.target, "--prompt", "x",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 3)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "cost_ceiling_reached")
        self.assertEqual(summary["iterations_completed"], 3)
        self.assertAlmostEqual(summary["cumulative_cost_usd"], 2.25, places=6)

    def test_default_ceiling_is_two_dollars(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertAlmostEqual(summary["cost_ceiling_usd"], 2.0, places=6)


# ============================================================================
# Slice 003-02 — AC #2: --cost-ceiling override
# ============================================================================


class CostCeilingOverrideTests(unittest.TestCase):
    """AC #2 — `--cost-ceiling 0.50` halts on first iteration emitting > $0.50."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac2-cost-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        # $0.75 per iter exceeds $0.50 immediately.
        _mock_claude_costs_per_iter(
            self.bindir, [0.75] * 10, self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_override_halts_at_iter_one(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            "--cost-ceiling", "0.50",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 1)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "cost_ceiling_reached")
        self.assertEqual(summary["iterations_completed"], 1)
        self.assertAlmostEqual(summary["cumulative_cost_usd"], 0.75, places=6)
        self.assertAlmostEqual(summary["cost_ceiling_usd"], 0.50, places=6)


# ============================================================================
# Slice 003-02 — AC #3: Per-iteration --max-budget-usd passthrough
# ============================================================================


class PerIterationBudgetCapTests(unittest.TestCase):
    """AC #3 — each `claude -p` invocation receives `--max-budget-usd <remaining>`."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac3-cost-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        self.args_log = tmp / "args.log"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_max_budget_usd_arg_passed_each_iteration(self):
        _mock_claude_costs_per_iter(
            self.bindir, [0.10] * 5, self.counter, args_log=self.args_log,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            "--cost-ceiling", "2.00",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        invocations = _read_args_log(self.args_log)
        self.assertEqual(len(invocations), 3)
        for argv in invocations:
            self.assertIn("--max-budget-usd", argv)

    def test_max_budget_usd_decreases_as_budget_burns(self):
        # Each iter costs $0.50; ceiling = $2.00. Remaining budget at the
        # START of each iter: 2.00, 1.50, 1.00, 0.50. (iter-4 would have
        # remaining = 0.50, but after iter-4 cumulative = 2.00 == ceiling
        # → still under; iter-5 would have remaining = 0 < floor → halt.)
        _mock_claude_costs_per_iter(
            self.bindir, [0.50] * 5, self.counter, args_log=self.args_log,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "4",
            "--cost-ceiling", "2.00",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        invocations = _read_args_log(self.args_log)
        self.assertEqual(len(invocations), 4)
        budgets = [
            float(_find_flag_value(argv, "--max-budget-usd"))
            for argv in invocations
        ]
        # Strictly monotonic decreasing.
        for prev, curr in zip(budgets, budgets[1:]):
            self.assertGreater(prev, curr, f"budgets={budgets}")
        # First iter sees the full ceiling.
        self.assertAlmostEqual(budgets[0], 2.00, places=6)
        # Subsequent iters reflect remaining = ceiling - cumulative_before.
        self.assertAlmostEqual(budgets[1], 1.50, places=6)
        self.assertAlmostEqual(budgets[2], 1.00, places=6)
        self.assertAlmostEqual(budgets[3], 0.50, places=6)


# ============================================================================
# Slice 003-02 — AC #4: Per-iteration budget floor
# ============================================================================


class PerIterationBudgetFloorTests(unittest.TestCase):
    """AC #4 — `--max-budget-usd` floor at MIN_BUDGET_FLOOR_USD = 0.01.

    Two scenarios:
      - Mid-loop: cumulative is within $0.01 of ceiling → halt without
        invoking the next iteration. Guarantees we never call claude with
        `--max-budget-usd 0` or anything sub-cent.
      - First-iter: ceiling itself is below the floor → halt before iter-1.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac4-cost-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        self.args_log = tmp / "args.log"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_remaining_below_floor_halts_without_next_invocation(self):
        # iter-1 cost = $0.495; ceiling = $0.50 → remaining = $0.005 < floor.
        # iter-2 must NOT fire.
        _mock_claude_costs_per_iter(
            self.bindir, [0.495, 0.495, 0.495], self.counter,
            args_log=self.args_log,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            "--cost-ceiling", "0.50",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 1)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "cost_ceiling_reached")
        self.assertEqual(summary["iterations_completed"], 1)

    def test_ceiling_below_floor_halts_before_any_iteration(self):
        # ceiling = $0.005 < floor = $0.01 → iter-1 never fires.
        _mock_claude_costs_per_iter(
            self.bindir, [0.10] * 5, self.counter, args_log=self.args_log,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            "--cost-ceiling", "0.005",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertFalse(
            self.counter.exists(),
            "claude should not have been invoked at all",
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "cost_ceiling_reached")
        self.assertEqual(summary["iterations_completed"], 0)
        self.assertAlmostEqual(summary["cumulative_cost_usd"], 0.0, places=6)

    def test_floor_does_not_fire_when_remaining_well_above(self):
        # Remaining well above floor → loop proceeds normally to max_iterations.
        _mock_claude_costs_per_iter(
            self.bindir, [0.05] * 3, self.counter, args_log=self.args_log,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            "--cost-ceiling", "2.00",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 3)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")

    def test_passed_budget_never_below_floor(self):
        # Even when cumulative approaches the ceiling, the --max-budget-usd
        # value we pass to claude is at least MIN_BUDGET_FLOOR_USD. (We never
        # send claude an effectively-zero budget.)
        _mock_claude_costs_per_iter(
            self.bindir, [0.49, 0.49, 0.49], self.counter,
            args_log=self.args_log,
        )
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            "--cost-ceiling", "1.00",
            mock_bindir=self.bindir,
        )
        invocations = _read_args_log(self.args_log)
        for argv in invocations:
            budget = float(_find_flag_value(argv, "--max-budget-usd"))
            self.assertGreaterEqual(budget, 0.01)


# ============================================================================
# Slice 003-02 — AC #5: Summary line carries cost-ceiling fields
# ============================================================================


class CostCeilingSummaryTests(unittest.TestCase):
    """AC #5 — when cost-ceiling halts the loop, summary carries the documented fields."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac5-cost-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_summary_has_required_cost_fields_on_ceiling_halt(self):
        _mock_claude_costs_per_iter(
            self.bindir, [0.40, 0.40, 0.40, 0.40, 0.40], self.counter,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "10",
            "--cost-ceiling", "1.00",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "cost_ceiling_reached")
        self.assertIn("cumulative_cost_usd", summary)
        self.assertIn("cost_ceiling_usd", summary)
        self.assertAlmostEqual(summary["cost_ceiling_usd"], 1.00, places=6)
        self.assertGreater(summary["cumulative_cost_usd"], 1.00)

    def test_cost_ceiling_usd_present_on_non_ceiling_halt(self):
        # Even when the loop ends for other reasons (oracle pass or iter cap),
        # the summary should still expose the configured ceiling so consumers
        # can correlate the bound that was in effect.
        _mock_claude_costs_per_iter(
            self.bindir, [0.05] * 3, self.counter,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            "--cost-ceiling", "5.00",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertAlmostEqual(summary["cost_ceiling_usd"], 5.00, places=6)


# ============================================================================
# Slice 003-02 — AC #6: Cumulative cost in per-iteration JSON
# ============================================================================


class CumulativeCostPerIterationTests(unittest.TestCase):
    """AC #6 — each per-iteration line carries both `cost_usd` and `cumulative_cost_usd`."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac6-cost-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cumulative_cost_matches_running_sum(self):
        # Varying per-iter costs let us verify the running sum is correct.
        costs = [0.10, 0.20, 0.30]
        _mock_claude_costs_per_iter(self.bindir, costs, self.counter)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            "--cost-ceiling", "10.00",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        self.assertEqual(len(per_iter), 3)
        running = 0.0
        for line, expected_cost in zip(per_iter, costs):
            running += expected_cost
            self.assertIn("cost_usd", line)
            self.assertIn("cumulative_cost_usd", line)
            self.assertAlmostEqual(line["cost_usd"], expected_cost, places=6)
            self.assertAlmostEqual(
                line["cumulative_cost_usd"], running, places=6,
            )


# ============================================================================
# Slice 003-02 — AC #7: --cost-ceiling 0 disables the cumulative ceiling
# ============================================================================


class CostCeilingDisabledTests(unittest.TestCase):
    """AC #7 — `--cost-ceiling 0` disables cumulative ceiling; per-iter cap defaults."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac7-cost-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        self.args_log = tmp / "args.log"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_ceiling_zero_does_not_halt_on_cost(self):
        # Cumulative would be 5 * $5.00 = $25 — far above default ceiling, but
        # with --cost-ceiling 0, cumulative-tracking is disabled and the loop
        # runs to its iter cap.
        _mock_claude_costs_per_iter(
            self.bindir, [5.00] * 5, self.counter, args_log=self.args_log,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            "--cost-ceiling", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 3)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertAlmostEqual(summary["cost_ceiling_usd"], 0.0, places=6)

    def test_ceiling_zero_uses_default_per_iter_budget(self):
        # With cumulative disabled, the per-iter cap defaults to
        # DEFAULT_PER_ITER_BUDGET_USD = $1.00 so a runaway agentic turn still
        # has a brake. Every invocation must carry --max-budget-usd 1.0.
        _mock_claude_costs_per_iter(
            self.bindir, [0.05] * 3, self.counter, args_log=self.args_log,
        )
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            "--cost-ceiling", "0",
            mock_bindir=self.bindir,
        )
        invocations = _read_args_log(self.args_log)
        self.assertEqual(len(invocations), 2)
        for argv in invocations:
            self.assertIn("--max-budget-usd", argv)
            self.assertAlmostEqual(
                float(_find_flag_value(argv, "--max-budget-usd")),
                1.00, places=6,
            )


# ============================================================================
# Slice 003-02 — CLI validation: negative --cost-ceiling rejected
# ============================================================================


class CostCeilingValidationTests(unittest.TestCase):
    """`--cost-ceiling` validation — negatives are meaningless; argparse rejects them.

    Mirrors the `--max-iterations < 1` rejection pattern (closed {0, 2} exit
    contract, with the helpful stderr breadcrumb).
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-validation-cost-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_negative_cost_ceiling_rejected(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            "--cost-ceiling", "-1.5",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--cost-ceiling must be >= 0", result.stderr)
        self.assertFalse(self.counter.exists())


# ============================================================================
# Slice 003-02 — non-zero claude exit WITH parseable JSON treated as completion
# ============================================================================


class ClaudeNonzeroWithParseableJsonTests(unittest.TestCase):
    """When `--max-budget-usd` is honored, claude can exit non-zero with a
    parseable JSON body (budget_exceeded). Per AC9's literal wording ("exit
    non-zero WITHOUT parseable JSON output"), that path is NOT a claude
    invocation failure — the loop accepts the JSON, records the cost, and
    lets its own cumulative tracking decide whether to halt.

    This closes the 003-01 deviation-log forward reference: "Slice 003-02 will
    need to revisit when budget-exceeded paths surface a non-zero exit with
    parseable JSON — at that point the breadcrumb will split into 'without
    JSON output' vs 'with unparseable output' sub-cases."
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-nonzero-json-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_nonzero_exit_with_parseable_json_records_iteration(self):
        # Mock that exits 1 but with a clean JSON body — simulates claude's
        # `--max-budget-usd` halt path. The loop should treat this as a
        # successful iteration completion (cost recorded), then halt via its
        # own cumulative-cost check.
        payload = _claude_json_payload(
            session_id="budget-hit-sess", cost=1.50,
            terminal_reason="budget_exceeded",
        )
        body = textwrap.dedent(f"""\
            #!/usr/bin/env bash
            cat <<'__JSON_EOF__'
            {payload}
            __JSON_EOF__
            exit 1
        """)
        _make_mock_claude(self.bindir, body)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            "--cost-ceiling", "1.00",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        # First iter recorded; cumulative ($1.50) > ceiling ($1.00) → halt.
        self.assertEqual(len(per_iter), 1)
        self.assertEqual(per_iter[0]["session_id"], "budget-hit-sess")
        self.assertAlmostEqual(per_iter[0]["cost_usd"], 1.50, places=6)
        self.assertEqual(per_iter[0]["terminal_reason"], "budget_exceeded")
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "cost_ceiling_reached")

    def test_nonzero_exit_with_unparseable_stdout_still_fails(self):
        # Non-zero exit + non-JSON stdout = real failure (AC9 path).
        body = textwrap.dedent("""\
            #!/usr/bin/env bash
            echo 'definitely not json'
            exit 1
        """)
        _make_mock_claude(self.bindir, body)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "claude_invocation_failed")


# ============================================================================
# Slice 003-03 — context-fill-gate: shared fixture helper
# ============================================================================


def _mock_claude_input_tokens_per_iter(
    bindir: Path,
    *,
    input_tokens_per_iter: list,
    counter_file: Path,
    context_window: Optional[int] = 200000,
    cache_read_tokens: int = 0,
    cache_create_tokens: int = 0,
    cost: float = 0.05,
) -> Path:
    """Mock that emits input_tokens[n-1] on its n-th invocation.

    Lets a test engineer a specific context-fill ratio trajectory. The
    ratio is computed as `(input_tokens + cache_read + cache_create) /
    contextWindow`. With the default `contextWindow=200000` and
    `cache_*=0`, setting `input_tokens_per_iter=[160000, ...]` produces
    a 0.80 ratio on iter 1.

    `context_window=None` omits the `modelUsage.<model>.contextWindow`
    field entirely — used by the AC8 fail-open test to verify the loop
    keeps iterating without the gate when the field is absent.

    `cost` is kept small (default $0.05) so context-fill tests don't
    accidentally trip the cost ceiling.
    """
    tokens_file = bindir / "tokens.txt"
    bindir.mkdir(parents=True, exist_ok=True)
    tokens_file.write_text(
        "\n".join(str(t) for t in input_tokens_per_iter) + "\n"
    )
    if context_window is None:
        model_entry = '"inputTokens":100,"outputTokens":10'
    else:
        model_entry = (
            f'"inputTokens":100,"outputTokens":10,'
            f'"contextWindow":{context_window}'
        )
    body = (
        f"#!/usr/bin/env bash\n"
        f"counter_file='{counter_file}'\n"
        f"tokens_file='{tokens_file}'\n"
        f'if [ -f "$counter_file" ]; then\n'
        f'    n=$(cat "$counter_file")\n'
        f"else\n"
        f"    n=0\n"
        f"fi\n"
        f"n=$((n + 1))\n"
        f'echo "$n" > "$counter_file"\n'
        f'tokens=$(sed -n "${{n}}p" "$tokens_file")\n'
        f"cat <<JSON_EOF\n"
        f'{{"type":"result","subtype":"success","is_error":false,'
        f'"session_id":"mock-session-$n","total_cost_usd":{cost},'
        f'"terminal_reason":"completed","stop_reason":"end_turn",'
        f'"num_turns":1,"result":"ok",'
        f'"usage":{{"input_tokens":$tokens,'
        f'"cache_read_input_tokens":{cache_read_tokens},'
        f'"cache_creation_input_tokens":{cache_create_tokens},'
        f'"output_tokens":10}},'
        f'"modelUsage":{{"claude-sonnet-4-6":{{{model_entry}}}}}}}\n'
        f"JSON_EOF\n"
    )
    return _make_mock_claude(bindir, body)


# ============================================================================
# Slice 003-03 — AC #1: Default threshold (0.75) gates iter N+1
# ============================================================================


class ContextFillThresholdDefaultTests(unittest.TestCase):
    """AC #1 — with no flag, ratio 0.80 (input=160000/cw=200000) halts iter 2.

    Iter 1 runs (no prior ratio), produces context_fill_ratio=0.80.
    Pre-iter-2 gate: 0.80 ≥ 0.75 → halt. Summary carries
    `terminal_reason=context_full`, `context_fill_ratio=0.80`,
    `context_fill_threshold=0.75`.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac1-ctx-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_input_tokens_per_iter(
            self.bindir,
            input_tokens_per_iter=[160000] * 5,
            counter_file=self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_halts_at_iter_two_on_default_threshold(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # Iter 1 ran; pre-iter-2 gate caught the 0.80 ratio.
        self.assertEqual(int(self.counter.read_text().strip()), 1)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "context_full")
        self.assertEqual(summary["iterations_completed"], 1)
        self.assertAlmostEqual(summary["context_fill_ratio"], 0.80, places=6)
        self.assertAlmostEqual(summary["context_fill_threshold"], 0.75, places=6)

    def test_default_threshold_is_three_quarters(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertAlmostEqual(summary["context_fill_threshold"], 0.75, places=6)


# ============================================================================
# Slice 003-03 — AC #2: --context-fill-threshold override
# ============================================================================


class ContextFillThresholdOverrideTests(unittest.TestCase):
    """AC #2 — `--context-fill-threshold 0.50` refuses at ≥ 50%."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac2-ctx-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        # 120000 / 200000 = 0.60 (above 0.50 override).
        _mock_claude_input_tokens_per_iter(
            self.bindir,
            input_tokens_per_iter=[120000] * 5,
            counter_file=self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_override_halts_at_iter_two(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            "--context-fill-threshold", "0.50",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 1)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "context_full")
        self.assertAlmostEqual(summary["context_fill_ratio"], 0.60, places=6)
        self.assertAlmostEqual(summary["context_fill_threshold"], 0.50, places=6)

    def test_override_with_higher_threshold_does_not_gate_low_ratio(self):
        # Override to 0.90 — the 0.60 ratio does NOT trigger. Loop runs to
        # the default --max-iterations cap.
        result = _run_loop(
            self.target, "--prompt", "x",
            "--context-fill-threshold", "0.90",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 5)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertAlmostEqual(summary["context_fill_threshold"], 0.90, places=6)


# ============================================================================
# Slice 003-03 — AC #3: Below-threshold iterations continue; ratio logged
# ============================================================================


class ContextFillBelowThresholdTests(unittest.TestCase):
    """AC #3 — iterations with ratio below threshold continue; ratio is logged.

    Ratio 0.40 (80000 / 200000) is well below default 0.75; loop runs to
    the iteration cap. Each per-iter JSON line carries `context_fill_ratio`.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac3-ctx-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_input_tokens_per_iter(
            self.bindir,
            input_tokens_per_iter=[80000] * 5,
            counter_file=self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_below_threshold_runs_to_max_iterations(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 5)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")

    def test_per_iteration_json_carries_context_fill_ratio(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        self.assertEqual(len(per_iter), 3)
        for line in per_iter:
            self.assertIn("context_fill_ratio", line)
            self.assertAlmostEqual(line["context_fill_ratio"], 0.40, places=6)

    def test_summary_carries_last_observed_ratio(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertAlmostEqual(summary["context_fill_ratio"], 0.40, places=6)
        self.assertAlmostEqual(summary["context_fill_threshold"], 0.75, places=6)


# ============================================================================
# Slice 003-03 — AC #4: Equality triggers refusal (≥, not strict >)
# ============================================================================


class ContextFillEqualThresholdTests(unittest.TestCase):
    """AC #4 — exact-equal ratio (0.75 with default threshold) triggers refusal.

    150000 / 200000 = 0.75 exactly. The comparison is `≥`, so iter 2 is
    refused. Off-by-one in the comparison direction is a classic bug; this
    test pins the choice explicitly.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac4-ctx-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_input_tokens_per_iter(
            self.bindir,
            input_tokens_per_iter=[150000] * 5,
            counter_file=self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_exact_equal_ratio_triggers_refusal(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 1)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "context_full")
        self.assertAlmostEqual(summary["context_fill_ratio"], 0.75, places=6)


# ============================================================================
# Slice 003-03 — AC #5: Iteration 1 always proceeds (no prior to gate on)
# ============================================================================


class ContextFillIterationOneTests(unittest.TestCase):
    """AC #5 — iter 1 is unconditional regardless of threshold setting.

    A very low threshold (0.05) would gate every reasonable iteration's
    output — but iter 1 has no prior to read context from, so it always
    runs. Two complementary tests:
      (a) `--max-iterations 1 --context-fill-threshold 0.05` runs iter 1,
          ends on max_iterations_reached (no iter 2 to gate).
      (b) Same threshold with `--max-iterations 5` lets iter 1 run, then
          the pre-iter-2 gate fires (proving iter 1 wasn't blocked by the
          gate, only iter 2 was).
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac5-ctx-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        # 180000 / 200000 = 0.90 — would gate iter 2 against any threshold
        # below 0.90, but iter 1 still runs.
        _mock_claude_input_tokens_per_iter(
            self.bindir,
            input_tokens_per_iter=[180000] * 5,
            counter_file=self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_iteration_one_runs_with_very_low_threshold(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            "--max-iterations", "1",
            "--context-fill-threshold", "0.05",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 1)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertEqual(summary["iterations_completed"], 1)

    def test_iter_one_runs_then_iter_two_gated(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            "--max-iterations", "5",
            "--context-fill-threshold", "0.05",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # Counter=1 proves iter 1 ran AND iter 2 was gated. Either iter 1
        # being blocked OR iter 2 being uncatched would fail this.
        self.assertEqual(int(self.counter.read_text().strip()), 1)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "context_full")
        self.assertEqual(summary["iterations_completed"], 1)


# ============================================================================
# Slice 003-03 — AC #6: Refusal happens before claude -p invocation
# ============================================================================


class ContextFillRefusalBeforeClaudeTests(unittest.TestCase):
    """AC #6 — pre-iter-2 gate refuses BEFORE invoking claude.

    Verified by counting mock-claude invocations: with iter 1 producing a
    ratio of 0.80 (above default 0.75), iter 2's claude must never be
    invoked. Counter must be exactly 1; per-iter JSON lines must be exactly
    one (iter 1 only).
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac6-ctx-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_input_tokens_per_iter(
            self.bindir,
            input_tokens_per_iter=[160000] * 5,
            counter_file=self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_claude_invoked_only_for_iter_one(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 1)
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        self.assertEqual(len(per_iter), 1)
        self.assertEqual(per_iter[0]["iteration"], 1)


# ============================================================================
# Slice 003-03 — AC #7: --context-fill-threshold 0 disables the gate
# ============================================================================


class ContextFillDisabledTests(unittest.TestCase):
    """AC #7 — `--context-fill-threshold 0` disables the gate entirely.

    With a near-full context (199000 / 200000 = 0.995) and the gate disabled,
    the loop runs to the iteration cap. The iteration cap and cost ceiling
    still apply — only the context-fill brake is off.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac7-ctx-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_input_tokens_per_iter(
            self.bindir,
            input_tokens_per_iter=[199000] * 5,
            counter_file=self.counter,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_disabled_gate_runs_all_iterations(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            "--max-iterations", "3",
            "--context-fill-threshold", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 3)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertEqual(summary["iterations_completed"], 3)
        self.assertEqual(summary["context_fill_threshold"], 0)

    def test_disabled_gate_still_logs_ratio_per_iteration(self):
        # Disable the gate but per-iter JSON still carries the ratio for
        # observability. (Useful for callers enforcing the limit out-of-band.)
        result = _run_loop(
            self.target, "--prompt", "x",
            "--max-iterations", "2",
            "--context-fill-threshold", "0",
            mock_bindir=self.bindir,
        )
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        self.assertEqual(len(per_iter), 2)
        for line in per_iter:
            self.assertAlmostEqual(line["context_fill_ratio"], 0.995, places=4)


# ============================================================================
# Slice 003-03 — AC #8: Missing contextWindow field → fail-open
# ============================================================================


class ContextFillMissingContextWindowTests(unittest.TestCase):
    """AC #8 — missing `modelUsage.<model>.contextWindow` → fail-open.

    The gate refuses to enforce when the field is absent; the loop logs a
    stderr breadcrumb and continues. Iteration cap and cost ceiling still
    apply, so the loop terminates on max_iterations_reached. Per-iter JSON's
    `context_fill_ratio` is null.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac8-ctx-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        # Omit the contextWindow field; ratio cannot be computed.
        _mock_claude_input_tokens_per_iter(
            self.bindir,
            input_tokens_per_iter=[160000] * 5,
            counter_file=self.counter,
            context_window=None,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_missing_context_window_does_not_halt(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 3)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")

    def test_stderr_breadcrumb_emitted(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        self.assertIn("context-fill gate", result.stderr)
        self.assertIn("contextWindow", result.stderr)

    def test_per_iter_ratio_is_null_when_unparseable(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        self.assertEqual(len(per_iter), 2)
        for line in per_iter:
            self.assertIsNone(line["context_fill_ratio"])

    def test_summary_ratio_is_null_when_unparseable(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertIsNone(summary["context_fill_ratio"])
        # Threshold is still emitted even when ratio can't be computed.
        self.assertAlmostEqual(summary["context_fill_threshold"], 0.75, places=6)


# ============================================================================
# Slice 003-03 — unit tests for _extract_context_fill_ratio failure paths
# ============================================================================


class ExtractContextFillRatioUnitTests(unittest.TestCase):
    """Direct unit tests for `_extract_context_fill_ratio` failure modes.

    The end-to-end tests above exercise the success path and one fail-open
    path (missing contextWindow). The helper has more internal branches:
    missing/non-dict `usage`, non-numeric tokens, missing/empty `modelUsage`,
    non-dict model entries, bool-as-int contextWindow, non-positive
    contextWindow. Each branch is fail-open with its own breadcrumb; these
    direct tests pin them all.
    """

    def setUp(self):
        # Import the helper from loop.py without spawning a subprocess.
        import importlib.util
        spec = importlib.util.spec_from_file_location("loop", LOOP)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.extract = module._extract_context_fill_ratio

    def _good_payload(self) -> dict:
        return {
            "usage": {
                "input_tokens": 100,
                "cache_read_input_tokens": 50,
                "cache_creation_input_tokens": 25,
                "output_tokens": 10,
            },
            "modelUsage": {
                "claude-sonnet-4-6": {
                    "inputTokens": 100, "outputTokens": 10,
                    "contextWindow": 200000,
                },
            },
        }

    def test_happy_path_returns_ratio(self):
        ratio, err = self.extract(self._good_payload())
        # (100 + 50 + 25) / 200000 = 0.000875
        self.assertAlmostEqual(ratio, 175 / 200000, places=9)
        self.assertIsNone(err)

    def test_missing_usage_block(self):
        payload = self._good_payload()
        del payload["usage"]
        ratio, err = self.extract(payload)
        self.assertIsNone(ratio)
        self.assertIn("missing `usage` block", err)

    def test_non_dict_usage_block(self):
        payload = self._good_payload()
        payload["usage"] = "not-a-dict"
        ratio, err = self.extract(payload)
        self.assertIsNone(ratio)
        self.assertIn("missing `usage` block", err)

    def test_non_numeric_tokens(self):
        payload = self._good_payload()
        payload["usage"]["input_tokens"] = "lots"
        ratio, err = self.extract(payload)
        self.assertIsNone(ratio)
        self.assertIn("non-numeric", err)

    def test_missing_model_usage(self):
        payload = self._good_payload()
        del payload["modelUsage"]
        ratio, err = self.extract(payload)
        self.assertIsNone(ratio)
        self.assertIn("missing `modelUsage` block", err)

    def test_empty_model_usage(self):
        payload = self._good_payload()
        payload["modelUsage"] = {}
        ratio, err = self.extract(payload)
        self.assertIsNone(ratio)
        self.assertIn("missing `modelUsage` block", err)

    def test_non_dict_model_entry_skipped(self):
        # First entry is garbage; second entry has the contextWindow. The
        # helper should skip the garbage entry and find the good one.
        payload = self._good_payload()
        payload["modelUsage"] = {
            "garbage": "not-a-dict",
            "claude-sonnet-4-6": {"contextWindow": 200000},
        }
        ratio, err = self.extract(payload)
        self.assertIsNotNone(ratio)
        self.assertIsNone(err)

    def test_bool_context_window_excluded(self):
        # `True` is an instance of `int` in Python — without the explicit
        # bool exclusion at loop.py:_extract_context_fill_ratio, this would
        # be accepted as contextWindow=1 and the ratio would explode. The
        # exclusion routes to fail-open.
        payload = self._good_payload()
        payload["modelUsage"]["claude-sonnet-4-6"]["contextWindow"] = True
        ratio, err = self.extract(payload)
        self.assertIsNone(ratio)
        self.assertIn("contextWindow", err)

    def test_zero_context_window_excluded(self):
        payload = self._good_payload()
        payload["modelUsage"]["claude-sonnet-4-6"]["contextWindow"] = 0
        ratio, err = self.extract(payload)
        self.assertIsNone(ratio)
        self.assertIn("contextWindow", err)

    def test_negative_context_window_excluded(self):
        payload = self._good_payload()
        payload["modelUsage"]["claude-sonnet-4-6"]["contextWindow"] = -100
        ratio, err = self.extract(payload)
        self.assertIsNone(ratio)
        self.assertIn("contextWindow", err)

    def test_zero_input_tokens_yields_zero_ratio(self):
        # Pathological corner: usage with all zeros. Ratio = 0.0, gate
        # never fires. Documented and tested so a future refactor doesn't
        # accidentally treat this as fail-open.
        payload = self._good_payload()
        payload["usage"] = {
            "input_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "output_tokens": 0,
        }
        ratio, err = self.extract(payload)
        self.assertEqual(ratio, 0.0)
        self.assertIsNone(err)

    def test_none_tokens_treated_as_zero(self):
        # The implementation's `or 0` idiom maps None to 0. Tested to pin
        # the choice: a future Claude Code release that emits `"input_tokens": null`
        # is treated as zero rather than fail-open.
        payload = self._good_payload()
        payload["usage"]["input_tokens"] = None
        ratio, err = self.extract(payload)
        # 0 + 50 + 25 = 75 → 75 / 200000
        self.assertAlmostEqual(ratio, 75 / 200000, places=9)
        self.assertIsNone(err)


# ============================================================================
# Slice 003-03 — CLI validation: --context-fill-threshold bounds [0.0, 1.0]
# ============================================================================


class ContextFillValidationTests(unittest.TestCase):
    """`--context-fill-threshold` must be in [0.0, 1.0]; argparse rejects others.

    A ratio is by construction in [0, 1]; thresholds outside that range are
    either always-fire (negative) or never-fire (> 1.0). Both shapes are
    user-error; reject upstream with rc=2 + a parser.error breadcrumb.
    Mirrors the `--max-iterations < 1` and `--cost-ceiling < 0` rejection
    patterns from earlier slices.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-validation-ctx-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_negative_threshold_rejected(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            "--context-fill-threshold", "-0.1",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "--context-fill-threshold must be in [0.0, 1.0]", result.stderr,
        )
        self.assertFalse(self.counter.exists())

    def test_greater_than_one_threshold_rejected(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            "--context-fill-threshold", "1.5",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "--context-fill-threshold must be in [0.0, 1.0]", result.stderr,
        )
        self.assertFalse(self.counter.exists())


# ============================================================================
# Slice 003-04 — checkpoint-resume: shared fixture helpers
# ============================================================================


def _state_path(target: Path, run_id: str) -> Path:
    return target / ".servo" / "runs" / run_id / "state.json"


def _read_state(target: Path, run_id: str) -> dict:
    return json.loads(_state_path(target, run_id).read_text())


def _find_only_run_id(target: Path) -> str:
    """Return the single run-id under `<target>/.servo/runs/`. Asserts exactly one exists."""
    runs_dir = target / ".servo" / "runs"
    children = [p for p in runs_dir.iterdir() if p.is_dir()]
    if len(children) != 1:
        raise AssertionError(
            f"expected exactly one run-id under {runs_dir}, found {len(children)}: "
            f"{[c.name for c in children]}"
        )
    return children[0].name


def _wait_until(predicate, *, timeout: float = 10.0, interval: float = 0.01,
                what: str = "condition") -> None:
    """Block until `predicate()` is truthy — a deterministic test barrier.

    Signal-handling tests must deliver SIGINT/SIGTERM only after the loop has
    reached the specific checkpoint under test. A fixed `time.sleep()` races
    loop.py's variable startup latency (cold interpreter spawn + preflight +
    run-dir creation + initial state write), so under load the signal can land
    in the pre-iteration checkpoint instead of the during-claude/during-gate
    one — recording iteration_count=0 and failing the assertion. Polling a
    marker the subprocess writes removes the race.
    """
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except Exception:
            pass
        time.sleep(interval)
    raise AssertionError(f"timed out after {timeout}s waiting for {what}")


def _mock_claude_session_per_iter(
    bindir: Path, counter_file: Path, *,
    cost: float = 0.05,
    input_tokens: int = 100,
    cache_read_tokens: int = 0,
    cache_create_tokens: int = 0,
    output_tokens: int = 10,
    context_window: int = 200000,
) -> Path:
    """Mock that emits a fresh `session_id` per invocation.

    Shape: `mock-session-1`, `mock-session-2`, etc. Lets state-file tests
    verify that `current_session_id` updates as iterations progress.
    """
    body = (
        f"#!/usr/bin/env bash\n"
        f"counter_file='{counter_file}'\n"
        f'if [ -f "$counter_file" ]; then\n'
        f'    n=$(cat "$counter_file")\n'
        f"else\n"
        f"    n=0\n"
        f"fi\n"
        f"n=$((n + 1))\n"
        f'echo "$n" > "$counter_file"\n'
        f"cat <<JSON_EOF\n"
        f'{{"type":"result","subtype":"success","is_error":false,'
        f'"session_id":"mock-session-$n","total_cost_usd":{cost},'
        f'"terminal_reason":"completed","stop_reason":"end_turn",'
        f'"num_turns":1,"result":"ok",'
        f'"usage":{{"input_tokens":{input_tokens},'
        f'"cache_read_input_tokens":{cache_read_tokens},'
        f'"cache_creation_input_tokens":{cache_create_tokens},'
        f'"output_tokens":{output_tokens}}},'
        f'"modelUsage":{{"claude-sonnet-4-6":{{"inputTokens":{input_tokens},'
        f'"outputTokens":{output_tokens},"contextWindow":{context_window}}}}}}}\n'
        f"JSON_EOF\n"
    )
    return _make_mock_claude(bindir, body)


def _slow_oracle(
    sleep_seconds: float = 3.0, marker_file: Optional[Path] = None,
) -> str:
    """Oracle that traps SIGINT/SIGTERM and sleeps before emitting a score.

    Used by `SignalHandlingDuringGateTests` to let a SIGINT arrive AFTER
    claude has returned (mock claude is fast) but DURING gate.py's invocation
    of oracle.sh. Trap mirrors a real oracle that cleans up under signal.

    When `marker_file` is given, the oracle touches it immediately before
    sleeping, so a test can poll for the marker and deliver the signal
    deterministically inside the gate window instead of racing a fixed sleep.
    """
    lines = ["#!/usr/bin/env bash", "trap 'exit 130' INT TERM"]
    if marker_file is not None:
        lines.append(f"touch '{marker_file}'")
    lines += [
        f"sleep {sleep_seconds} &",
        "wait $!",
        "echo 'oracle: composite=0.2000 threshold=0.5'",
        "exit 1",
    ]
    return "\n".join(lines) + "\n"


def _mock_claude_sleep_then_emit(
    bindir: Path, counter_file: Path, *,
    sleep_seconds: float = 3.0,
    cost: float = 0.05,
) -> Path:
    """Mock that sleeps before emitting JSON; traps SIGINT/SIGTERM to exit cleanly.

    Used by signal-handling tests (AC9). The trap mirrors how a real
    `claude -p` would behave under SIGINT in a foreground process group —
    the parent loop forwards the signal to this mock, the trap fires,
    the mock exits with 130, and the loop's `proc.communicate()` returns.

    On normal completion (no signal), the mock emits the standard JSON
    payload after sleeping.
    """
    body = (
        f"#!/usr/bin/env bash\n"
        f"trap 'exit 130' INT TERM\n"
        f"counter_file='{counter_file}'\n"
        f'if [ -f "$counter_file" ]; then\n'
        f'    n=$(cat "$counter_file")\n'
        f"else\n"
        f"    n=0\n"
        f"fi\n"
        f"n=$((n + 1))\n"
        f'echo "$n" > "$counter_file"\n'
        f"sleep {sleep_seconds} &\n"
        f"wait $!\n"
        f"cat <<JSON_EOF\n"
        f'{{"type":"result","subtype":"success","is_error":false,'
        f'"session_id":"mock-session-$n","total_cost_usd":{cost},'
        f'"terminal_reason":"completed","stop_reason":"end_turn",'
        f'"num_turns":1,"result":"ok",'
        f'"usage":{{"input_tokens":100,"cache_read_input_tokens":0,'
        f'"cache_creation_input_tokens":0,"output_tokens":10}},'
        f'"modelUsage":{{"claude-sonnet-4-6":{{"inputTokens":100,'
        f'"outputTokens":10,"contextWindow":200000}}}}}}\n'
        f"JSON_EOF\n"
    )
    return _make_mock_claude(bindir, body)


# ============================================================================
# Slice 003-04 — AC #1: State file written each iteration
# ============================================================================


class StateFilePersistenceTests(unittest.TestCase):
    """AC #1 — `<target>/.servo/runs/<run-id>/state.json` is updated each iter.

    After a 3-iteration normal run, the state file exists, is parseable
    JSON, and reflects all iterations' progress: iteration_count=3,
    cumulative_cost_usd accumulated, current_session_id is the iter-3
    session, oracle_score_history has three entries.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac1-state-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_state_file_exists_after_run(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        self.assertTrue(_state_path(self.target, run_id).exists())

    def test_state_iteration_count_matches_iterations(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["iteration_count"], 3)

    def test_state_current_session_id_is_last_iter(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["current_session_id"], "mock-session-3")

    def test_state_cumulative_cost_accumulates(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["cumulative_cost_usd"], 0.15, places=6)

    def test_state_oracle_score_history_one_entry_per_iter(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(len(state["oracle_score_history"]), 3)
        # Each entry has the canonical shape.
        for i, entry in enumerate(state["oracle_score_history"], start=1):
            self.assertEqual(entry["iteration"], i)
            self.assertIn("composite", entry)
            self.assertIn("threshold", entry)
            self.assertEqual(entry["status"], "below_threshold")

    def test_state_last_terminal_reason_set(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        # After max_iterations halt, last_terminal_reason carries the halt
        # cause (not the per-iter claude reason).
        self.assertEqual(state["last_terminal_reason"], "max_iterations_reached")


# ============================================================================
# Slice 003-04 — AC #2: State schema fields (ADR-0004)
# ============================================================================


class StateFileSchemaTests(unittest.TestCase):
    """AC #2 — state file carries every canonical ADR-0004 field with the right type."""

    REQUIRED_FIELDS = {
        "state_schema_version": int,
        "run_id": str,
        "started_at": str,
        "last_updated_at": str,
        "target_path": str,
        "current_session_id": str,
        "iteration_count": int,
        "max_iterations": int,
        "cost_ceiling_usd": float,
        "cumulative_cost_usd": float,
        "cumulative_input_tokens": int,
        "cumulative_output_tokens": int,
        "context_fill_threshold": float,
        # last_context_fill_ratio is float-or-None (depends on JSON shape).
        "oracle_score_history": list,
        # last_terminal_reason is str-or-None (None on initial write, str after).
        # claude_version is str-or-None.
    }

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac2-state-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_and_read(self) -> dict:
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        return _read_state(self.target, run_id)

    def test_all_required_fields_present(self):
        state = self._run_and_read()
        for field, expected_type in self.REQUIRED_FIELDS.items():
            self.assertIn(field, state, f"missing field: {field}")
            self.assertIsInstance(
                state[field], expected_type,
                f"field {field} is {type(state[field]).__name__}, "
                f"expected {expected_type.__name__}",
            )

    def test_state_schema_version_is_one(self):
        state = self._run_and_read()
        self.assertEqual(state["state_schema_version"], 1)

    def test_iso8601_timestamps(self):
        state = self._run_and_read()
        # Strict ISO8601 parse — fromisoformat handles the canonical shape.
        from datetime import datetime as dt
        dt.fromisoformat(state["started_at"])
        dt.fromisoformat(state["last_updated_at"])

    def test_target_path_is_absolute(self):
        state = self._run_and_read()
        self.assertTrue(Path(state["target_path"]).is_absolute())

    def test_last_context_fill_ratio_field_present_nullable(self):
        state = self._run_and_read()
        self.assertIn("last_context_fill_ratio", state)
        val = state["last_context_fill_ratio"]
        self.assertTrue(val is None or isinstance(val, (int, float)))

    def test_claude_version_field_present_nullable(self):
        state = self._run_and_read()
        self.assertIn("claude_version", state)
        val = state["claude_version"]
        self.assertTrue(val is None or isinstance(val, str))

    def test_last_terminal_reason_field_present(self):
        state = self._run_and_read()
        self.assertIn("last_terminal_reason", state)
        # After a max_iterations halt, the field is set.
        self.assertEqual(state["last_terminal_reason"], "max_iterations_reached")


# ============================================================================
# Slice 003-04 — AC #3: Resume reads state, continues from iter N+1
# ============================================================================


class ResumeFlowTests(unittest.TestCase):
    """AC #3 — `--resume <run-id>` picks up from iteration_count + 1."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac3-resume-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_resume_continues_from_next_iteration(self):
        # Initial run: 2 iterations.
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        self.assertEqual(int(self.counter.read_text().strip()), 2)
        # Resume with cap 4: should run iter 3 + iter 4.
        result = _run_loop(
            self.target, "--resume", run_id, "--max-iterations", "4",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # Total claude invocations: 2 (initial) + 2 (resume) = 4.
        self.assertEqual(int(self.counter.read_text().strip()), 4)
        # Per-iter lines on the RESUME invocation: iter 3 + iter 4 only.
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        self.assertEqual([line["iteration"] for line in per_iter], [3, 4])

    def test_resume_carries_cumulative_cost(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        _run_loop(
            self.target, "--resume", run_id, "--max-iterations", "4",
            mock_bindir=self.bindir,
        )
        state = _read_state(self.target, run_id)
        # 4 iters × $0.05 = $0.20
        self.assertAlmostEqual(state["cumulative_cost_usd"], 0.20, places=6)
        self.assertEqual(state["iteration_count"], 4)

    def test_resume_carries_oracle_score_history(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        _run_loop(
            self.target, "--resume", run_id, "--max-iterations", "4",
            mock_bindir=self.bindir,
        )
        state = _read_state(self.target, run_id)
        self.assertEqual(len(state["oracle_score_history"]), 4)
        self.assertEqual(
            [e["iteration"] for e in state["oracle_score_history"]],
            [1, 2, 3, 4],
        )

    def test_resume_omits_prompt_uses_persisted(self):
        # Initial run with a specific prompt.
        _run_loop(
            self.target, "--prompt", "original-seed",
            "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        state_before = _read_state(self.target, run_id)
        self.assertEqual(state_before["prompt"], "original-seed")
        # Resume without --prompt: persisted prompt should still apply.
        result = _run_loop(
            self.target, "--resume", run_id, "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        state_after = _read_state(self.target, run_id)
        self.assertEqual(state_after["prompt"], "original-seed")

    def test_resume_run_uses_same_run_id(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        result = _run_loop(
            self.target, "--resume", run_id, "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        # Summary's run_id matches the resumed id (not a new one).
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["run_id"], run_id)
        # Only one run-id directory exists; resume didn't create a new one.
        self.assertEqual(_find_only_run_id(self.target), run_id)

    def test_resume_prompt_override_replaces_persisted(self):
        # Initial run with one prompt.
        _run_loop(
            self.target, "--prompt", "original-seed",
            "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        # Resume with --prompt override: state should hold the new prompt.
        _run_loop(
            self.target, "--resume", run_id, "--prompt", "revised-seed",
            "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        state = _read_state(self.target, run_id)
        self.assertEqual(state["prompt"], "revised-seed")


# ============================================================================
# Slice 003-04 — AC #4: Resume preserves overrides; CLI override re-applies
# ============================================================================


class ResumePreservesOverridesTests(unittest.TestCase):
    """AC #4 — flags persisted in state are re-applied on resume; CLI overrides win."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac4-resume-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_persisted_max_iterations_used_when_no_override(self):
        # Initial run captures --max-iterations 2 and --cost-ceiling 3.50.
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            "--cost-ceiling", "3.50",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        state_before = _read_state(self.target, run_id)
        self.assertEqual(state_before["max_iterations"], 2)
        self.assertAlmostEqual(state_before["cost_ceiling_usd"], 3.50, places=6)

        # Resume without overrides — values stay.
        _run_loop(
            self.target, "--resume", run_id,
            mock_bindir=self.bindir,
        )
        state_after = _read_state(self.target, run_id)
        # max-iterations is 2 from state; iter_count was already 2, so no
        # more iters run on resume. The state's max_iterations stays at 2.
        self.assertEqual(state_after["max_iterations"], 2)
        self.assertAlmostEqual(state_after["cost_ceiling_usd"], 3.50, places=6)

    def test_max_iterations_override_re_applied(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        # Resume with --max-iterations 5: state's max should update.
        _run_loop(
            self.target, "--resume", run_id, "--max-iterations", "5",
            mock_bindir=self.bindir,
        )
        state = _read_state(self.target, run_id)
        self.assertEqual(state["max_iterations"], 5)
        # Iter count is now 5 (the resume ran iter 3-5).
        self.assertEqual(state["iteration_count"], 5)

    def test_cost_ceiling_override_re_applied(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            "--cost-ceiling", "2.00",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        _run_loop(
            self.target, "--resume", run_id, "--cost-ceiling", "0.50",
            "--max-iterations", "3",
            mock_bindir=self.bindir,
        )
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["cost_ceiling_usd"], 0.50, places=6)

    def test_context_fill_threshold_override_re_applied(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            "--context-fill-threshold", "0.80",
            mock_bindir=self.bindir,
        )
        run_id = _find_only_run_id(self.target)
        _run_loop(
            self.target, "--resume", run_id,
            "--context-fill-threshold", "0.30",
            "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["context_fill_threshold"], 0.30, places=6)


# ============================================================================
# Slice 003-04 — AC #5: Refusal on schema / claude-version mismatch
# ============================================================================


class ResumeRefusalTests(unittest.TestCase):
    """AC #5 — stale schema or claude-version mismatch refuses unless --resume-anyway."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac5-resume-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)
        # Seed an initial run so we have a state file to mutate.
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        self.run_id = _find_only_run_id(self.target)
        self.state_path = _state_path(self.target, self.run_id)
        # Reset counter so post-tamper resume invocations have a clean slate.
        self.counter.unlink(missing_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _mutate_state(self, **fields) -> None:
        state = json.loads(self.state_path.read_text())
        state.update(fields)
        self.state_path.write_text(json.dumps(state))

    def test_state_schema_mismatch_refuses(self):
        self._mutate_state(state_schema_version=999)
        result = _run_loop(
            self.target, "--resume", self.run_id,
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("state_schema_version mismatch", result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "state_schema_mismatch")
        # Claude was not invoked.
        self.assertFalse(self.counter.exists())

    def test_resume_anyway_escapes_schema_mismatch(self):
        self._mutate_state(state_schema_version=999)
        result = _run_loop(
            self.target, "--resume", self.run_id, "--resume-anyway",
            "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # Iter 2 ran on resume.
        self.assertEqual(int(self.counter.read_text().strip()), 1)

    def test_claude_version_mismatch_refuses(self):
        self._mutate_state(claude_version="9.9.9-stale-version")
        result = _run_loop(
            self.target, "--resume", self.run_id,
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("claude_version mismatch", result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "claude_version_mismatch")
        self.assertFalse(self.counter.exists())

    def test_resume_anyway_escapes_claude_version_mismatch(self):
        self._mutate_state(claude_version="9.9.9-stale-version")
        result = _run_loop(
            self.target, "--resume", self.run_id, "--resume-anyway",
            "--max-iterations", "2",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 1)

    def test_resume_anyway_without_resume_rejected(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--resume-anyway",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--resume-anyway requires --resume", result.stderr)


# ============================================================================
# Slice 003-04 — AC #6: Refusal on missing state
# ============================================================================


class ResumeMissingStateTests(unittest.TestCase):
    """AC #6 — `--resume <bogus>` rc=2 with `state_missing`."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac6-resume-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_bogus_run_id_refuses(self):
        result = _run_loop(
            self.target, "--resume", "20260520T120000-deadbeef",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("state file not found", result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "state_missing")
        # Claude was not invoked.
        self.assertFalse(self.counter.exists())

    def test_state_missing_summary_carries_run_id(self):
        bogus = "20260520T120000-cafebabe"
        result = _run_loop(
            self.target, "--resume", bogus,
            mock_bindir=self.bindir,
        )
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["run_id"], bogus)

    def test_resume_with_unparseable_state_json(self):
        # Pre-create the run dir but write garbage as state.json.
        run_dir = self.target / ".servo" / "runs" / "20260520T120000-aaaa"
        run_dir.mkdir(parents=True)
        (run_dir / "state.json").write_text("definitely not json")
        result = _run_loop(
            self.target, "--resume", "20260520T120000-aaaa",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        # Malformed state also routes to state_missing (per the helper docstring).
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "state_missing")


# ============================================================================
# Slice 003-04 — AC #7: Fresh run gets fresh run-id
# ============================================================================


class FreshRunIdTests(unittest.TestCase):
    """AC #7 — back-to-back fresh runs each get distinct run-ids."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac7-fresh-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_two_fresh_runs_produce_two_run_ids(self):
        r1 = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        r2 = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        rid1 = _stdout_json_lines(r1.stdout)[-1]["run_id"]
        rid2 = _stdout_json_lines(r2.stdout)[-1]["run_id"]
        self.assertNotEqual(rid1, rid2)
        # Both directories exist on disk.
        runs_dir = self.target / ".servo" / "runs"
        children = sorted(p.name for p in runs_dir.iterdir() if p.is_dir())
        self.assertEqual(len(children), 2)
        self.assertIn(rid1, children)
        self.assertIn(rid2, children)

    def test_run_id_shape_is_timestamp_plus_suffix(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        run_id = _stdout_json_lines(result.stdout)[-1]["run_id"]
        self.assertRegex(run_id, r"^\d{8}T\d{6}-[0-9a-f]{4}$")


# ============================================================================
# Slice 003-04 — AC #8: Runs directory auto-created
# ============================================================================


class RunsDirectoryAutoCreateTests(unittest.TestCase):
    """AC #8 — `<target>/.servo/runs/` is created if absent."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac8-runs-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_runs_dir_does_not_exist_pre_run(self):
        self.assertFalse((self.target / ".servo" / "runs").exists())

    def test_runs_dir_created_on_first_run(self):
        _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
        )
        self.assertTrue((self.target / ".servo" / "runs").is_dir())
        # And the run dir exists inside.
        run_id = _find_only_run_id(self.target)
        self.assertTrue(_state_path(self.target, run_id).exists())


# ============================================================================
# Slice 003-04 — AC #9: Signal handling (SIGINT / SIGTERM)
# ============================================================================


class SignalHandlingTests(unittest.TestCase):
    """AC #9 — SIGINT/SIGTERM trap finalizes state and emits `interrupted` summary."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac9-signal-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        # Sleep mock so we can interrupt mid-iteration.
        _mock_claude_sleep_then_emit(
            self.bindir, self.counter, sleep_seconds=3.0,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _spawn(self, *extra: str) -> subprocess.Popen:
        env = {
            **os.environ,
            "PATH": f"{self.bindir}:{SYSTEM_PATH}",
        }
        cmd = [
            sys.executable, str(LOOP), str(self.target),
            "--driver", "loop", "--prompt", "x", "--max-iterations", "3",
            *extra,
        ]
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env,
        )

    def _wait_for_signal_window(self) -> None:
        """Block until mock claude has spawned (counter written) so a SIGINT
        lands in the during-claude checkpoint, not the pre-iteration one.

        Replaces a fixed sleep that raced loop.py's startup latency.
        """
        _wait_until(
            lambda: self.counter.exists()
            and self.counter.read_text().strip().isdigit(),
            what="mock claude to spawn (counter file written)",
        )

    def test_sigint_during_claude_emits_interrupted_summary(self):
        import signal as sigmod
        proc = self._spawn()
        try:
            # Barrier: wait until the mock claude has spawned (it writes the
            # counter before its 3s sleep) so the SIGINT lands while claude is
            # in flight, not during loop startup.
            self._wait_for_signal_window()
            proc.send_signal(sigmod.SIGINT)
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("loop did not exit within 10s of SIGINT")
        self.assertEqual(
            proc.returncode, 130,
            f"expected rc=130, got {proc.returncode}; stderr={stderr}",
        )
        # Summary is the LAST JSON line on stdout.
        lines = _stdout_json_lines(stdout)
        self.assertTrue(lines, f"no JSON on stdout; stderr={stderr}")
        summary = lines[-1]
        self.assertEqual(summary["terminal_reason"], "interrupted")
        self.assertEqual(summary["final_oracle_status"], "unknown_interrupted")

    def test_sigterm_during_claude_emits_interrupted_summary(self):
        import signal as sigmod
        proc = self._spawn()
        try:
            self._wait_for_signal_window()
            proc.send_signal(sigmod.SIGTERM)
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("loop did not exit within 10s of SIGTERM")
        self.assertEqual(proc.returncode, 130)
        summary = _stdout_json_lines(stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "interrupted")

    def test_state_file_finalized_with_interrupted_reason(self):
        import signal as sigmod
        proc = self._spawn()
        try:
            self._wait_for_signal_window()
            proc.send_signal(sigmod.SIGINT)
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("loop did not exit within 10s of SIGINT")
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["last_terminal_reason"], "interrupted")
        # Iteration was treated as completed for state-file purposes
        # (AC9 — "iteration_count reflects the partial iteration").
        self.assertEqual(state["iteration_count"], 1)

    def test_interrupt_summary_iterations_completed_one(self):
        import signal as sigmod
        proc = self._spawn()
        try:
            self._wait_for_signal_window()
            proc.send_signal(sigmod.SIGINT)
            stdout, _stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("loop did not exit within 10s of SIGINT")
        summary = _stdout_json_lines(stdout)[-1]
        self.assertEqual(summary["iterations_completed"], 1)


class SignalHandlingDuringGateTests(unittest.TestCase):
    """AC #9 — signal arriving DURING gate.py.

    Mock claude is fast (no sleep). The oracle is slow (sleeps 3s). A SIGINT
    sent ~0.5s into the run lands while gate.py is invoking oracle.sh,
    NOT during claude. The post-gate interrupt branch fires:
    `iteration_count` is set to the in-flight iteration, oracle status is
    `unknown_interrupted`, the summary emits `terminal_reason=interrupted`,
    and the loop exits 130.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac9-gate-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        # Slow oracle: gate.py invokes this, then sleeps 3s before scoring.
        # The marker lets the test poll for "oracle is running" instead of
        # racing a fixed sleep (see _wait_until).
        self.oracle_started = tmp / "oracle_started"
        _make_oracle(
            self.target,
            _slow_oracle(sleep_seconds=3.0, marker_file=self.oracle_started),
        )
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        # Fast mock claude — emits JSON immediately.
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _spawn(self) -> subprocess.Popen:
        env = {
            **os.environ,
            "PATH": f"{self.bindir}:{SYSTEM_PATH}",
        }
        cmd = [
            sys.executable, str(LOOP), str(self.target),
            "--driver", "loop", "--prompt", "x", "--max-iterations", "3",
        ]
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env,
        )

    def _wait_for_signal_window(self) -> None:
        """Block until oracle.sh has started (marker touched) so a SIGINT
        lands during gate.py, not during claude or loop startup.

        Replaces a fixed sleep that raced loop.py's startup latency.
        """
        _wait_until(
            self.oracle_started.exists,
            what="oracle.sh to start (gate window)",
        )

    def test_sigint_during_gate_emits_unknown_interrupted(self):
        import signal as sigmod
        proc = self._spawn()
        try:
            # Barrier: wait until oracle.sh has started (it touches a marker
            # before its 3s sleep). Mock claude is instant, so once the oracle
            # is sleeping the SIGINT deterministically lands during gate.py.
            self._wait_for_signal_window()
            proc.send_signal(sigmod.SIGINT)
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("loop did not exit within 10s of SIGINT")
        self.assertEqual(
            proc.returncode, 130,
            f"expected rc=130, got {proc.returncode}; stderr={stderr}",
        )
        summary = _stdout_json_lines(stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "interrupted")
        self.assertEqual(summary["final_oracle_status"], "unknown_interrupted")
        # Claude was invoked once (iter 1's claude completed; gate was
        # interrupted before scoring); the counter reflects that.
        self.assertEqual(int(self.counter.read_text().strip()), 1)

    def test_state_file_after_sigint_during_gate(self):
        import signal as sigmod
        proc = self._spawn()
        try:
            self._wait_for_signal_window()
            proc.send_signal(sigmod.SIGINT)
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail("loop did not exit within 10s of SIGINT")
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["last_terminal_reason"], "interrupted")
        # iteration_count reflects the in-flight (interrupted-during-gate)
        # iteration per AC9's "treated as completed for state-file purposes."
        self.assertEqual(state["iteration_count"], 1)
        # No oracle history entry was recorded for this iteration (the
        # append at gate-scored time didn't run); session_id from claude
        # DID get captured (it returned before the interrupt).
        self.assertEqual(state["current_session_id"], "mock-session-1")
        self.assertEqual(len(state["oracle_score_history"]), 0)


# ============================================================================
# Slice 003-04 — AC #10: Run-id collision retry policy
# ============================================================================


class RunIdCollisionTests(unittest.TestCase):
    """AC #10 — bounded retry (3 attempts total), then refuse with run_id_collision.

    Uses the `SERVO_TEST_RUN_IDS` test hook to deterministically force the
    next-generated run-ids. Pre-creates directories that conflict with
    those ids, then verifies retry behavior.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac10-collision-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_single_collision_retry_succeeds(self):
        # Pre-create the first id; second id should succeed.
        runs_dir = self.target / ".servo" / "runs"
        runs_dir.mkdir(parents=True)
        (runs_dir / "20260520T120000-aaaa").mkdir()
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
            extra_env={
                "SERVO_TEST_RUN_IDS": (
                    "20260520T120000-aaaa,20260520T120000-bbbb"
                ),
            },
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # The successful run uses the second id.
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["run_id"], "20260520T120000-bbbb")

    def test_triple_collision_refuses(self):
        runs_dir = self.target / ".servo" / "runs"
        runs_dir.mkdir(parents=True)
        for suffix in ("aaaa", "bbbb", "cccc"):
            (runs_dir / f"20260520T120000-{suffix}").mkdir()
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir,
            extra_env={
                "SERVO_TEST_RUN_IDS": (
                    "20260520T120000-aaaa,20260520T120000-bbbb,"
                    "20260520T120000-cccc"
                ),
            },
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("could not allocate a fresh run-id", result.stderr)
        # Stderr breadcrumb names the colliding ids.
        for suffix in ("aaaa", "bbbb", "cccc"):
            self.assertIn(f"20260520T120000-{suffix}", result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "run_id_collision")
        # Claude was not invoked.
        self.assertFalse(self.counter.exists())


# ============================================================================
# Slice 003-05 — stuck-loop-and-handoff: shared fixture helpers
# ============================================================================


# Triple-backtick fences inside a bash heredoc would trigger command
# substitution. Encode them as ``` Unicode escapes inside the JSON
# string — `json.loads` in loop.py decodes them back to literal backticks
# before the verdict parser sees the block.
_BTICK = "\\u0060\\u0060\\u0060"  # JSON-encoded triple backtick (18 chars)


def _runner_verdict_block(
    *, verdict: str = "CHANGES_MADE",
    files_changed: Optional[str] = None,
    assumptions: Optional[str] = None,
    reasoning: str = "mock runner",
) -> str:
    """JSON-encoded runner-shaped verdict block for embedding in `result`."""
    lines = [
        f"{_BTICK}verdict",
        "schema_version: 1",
        f"verdict: {verdict}",
    ]
    if files_changed:
        lines.append(f"files_changed: {files_changed}")
    if assumptions:
        lines.append(f"assumptions: {assumptions}")
    lines.append(f"reasoning: {reasoning}")
    lines.append(_BTICK)
    return "\\n" + "\\n".join(lines) + "\\n"


def _judge_verdict_block(
    *, verdict: str = "PASS", score: float = 0.5,
    reasoning: str = "mock judge",
) -> str:
    """JSON-encoded judge-shaped verdict block for embedding in `result`."""
    lines = [
        f"{_BTICK}verdict",
        "schema_version: 1",
        f"verdict: {verdict}",
        f"score: {score:.2f}",
        f"reasoning: {reasoning}",
        _BTICK,
    ]
    return "\\n" + "\\n".join(lines) + "\\n"


def _mock_claude_with_verdict(
    bindir: Path, counter_file: Path, *,
    runner_block: Optional[str] = None,
    judge_block: Optional[str] = None,
    cost: float = 0.05,
    args_log: Optional[Path] = None,
) -> Path:
    """Mock that alternates runner / judge verdict blocks per invocation.

    Default: emits runner-shape block on odd invocations and judge-shape on
    even (matches the loop's `_agent_for_iteration` alternation). The
    `--agent <name>` arg the loop passes is not consulted by the mock; the
    alternation is keyed off the invocation counter so the mock's block
    shape matches what the loop expects to see.

    Optional `args_log` records each invocation's args using the U+001F /
    U+001E delimiter scheme (see `_mock_claude_with_args_log`).
    """
    runner_block = runner_block or _runner_verdict_block()
    judge_block = judge_block or _judge_verdict_block()
    args_log_cmd = (
        f'for arg in "$@"; do printf "%s\\037" "$arg" >> \'{args_log}\'; done\n'
        f'printf "\\036" >> \'{args_log}\'\n'
    ) if args_log else ""
    body = (
        f"#!/usr/bin/env bash\n"
        f"counter_file='{counter_file}'\n"
        f'if [ -f "$counter_file" ]; then\n'
        f'    n=$(cat "$counter_file")\n'
        f"else\n"
        f"    n=0\n"
        f"fi\n"
        f"n=$((n + 1))\n"
        f'echo "$n" > "$counter_file"\n'
        f"{args_log_cmd}"
        f'if [ $((n % 2)) -eq 1 ]; then\n'
        f'    block=\'{runner_block}\'\n'
        f"else\n"
        f'    block=\'{judge_block}\'\n'
        f"fi\n"
        f"cat <<JSON_EOF\n"
        f'{{"type":"result","subtype":"success","is_error":false,'
        f'"session_id":"mock-session-$n","total_cost_usd":{cost},'
        f'"terminal_reason":"completed","stop_reason":"end_turn",'
        f'"num_turns":1,'
        f'"result":"agent text$block",'
        f'"usage":{{"input_tokens":100,"cache_read_input_tokens":0,'
        f'"cache_creation_input_tokens":0,"output_tokens":10}},'
        f'"modelUsage":{{"claude-sonnet-4-6":{{"inputTokens":100,'
        f'"outputTokens":10,"contextWindow":200000}}}}}}\n'
        f"JSON_EOF\n"
    )
    return _make_mock_claude(bindir, body)


def _mock_claude_with_raw_result(
    bindir: Path, counter_file: Path, *,
    result_text: str, cost: float = 0.05,
) -> Path:
    """Mock with a literal `result` field — for malformed-block AC10 tests.

    `result_text` is JSON-encoded as-is. Test harnesses building this
    string must include the JSON-encoded backticks (use `_BTICK`).
    """
    body = (
        f"#!/usr/bin/env bash\n"
        f"counter_file='{counter_file}'\n"
        f'if [ -f "$counter_file" ]; then\n'
        f'    n=$(cat "$counter_file")\n'
        f"else\n"
        f"    n=0\n"
        f"fi\n"
        f"n=$((n + 1))\n"
        f'echo "$n" > "$counter_file"\n'
        f"cat <<JSON_EOF\n"
        f'{{"type":"result","subtype":"success","is_error":false,'
        f'"session_id":"mock-session-$n","total_cost_usd":{cost},'
        f'"terminal_reason":"completed","stop_reason":"end_turn",'
        f'"num_turns":1,"result":"{result_text}",'
        f'"usage":{{"input_tokens":100,"cache_read_input_tokens":0,'
        f'"cache_creation_input_tokens":0,"output_tokens":10}},'
        f'"modelUsage":{{"claude-sonnet-4-6":{{"inputTokens":100,'
        f'"outputTokens":10,"contextWindow":200000}}}}}}\n'
        f"JSON_EOF\n"
    )
    return _make_mock_claude(bindir, body)


def _composite_progression_oracle(composites: list) -> str:
    """Oracle that emits a different composite per invocation (1-indexed).

    Uses a counter file at `<target>/.oracle-counter` to step through the
    list. Lets a test engineer a specific composite trajectory for plateau
    detection (e.g., [0.2, 0.3, 0.4, 0.5, 0.5, 0.5] → plateau at iter 6).
    Each invocation always exits 1 (below_threshold) unless the last
    composite is >= 0.5.
    """
    composites_csv = ",".join(str(c) for c in composites)
    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        counter='.oracle-counter'
        if [ -f "$counter" ]; then
            n=$(cat "$counter")
        else
            n=0
        fi
        n=$((n + 1))
        echo "$n" > "$counter"
        IFS=',' read -r -a comps <<< '{composites_csv}'
        idx=$((n - 1))
        if [ $idx -ge ${{#comps[@]}} ]; then
            idx=$((${{#comps[@]}} - 1))
        fi
        comp=${{comps[$idx]}}
        echo "oracle: composite=$comp threshold=0.5"
        # Pass iff composite >= 0.5
        if awk "BEGIN {{ exit !($comp >= 0.5) }}"; then
            exit 0
        else
            exit 1
        fi
    """)


# ============================================================================
# Slice 003-05 — AC #1: Plateau detection (default window=3)
# ============================================================================


class PlateauDetectionDefaultTests(unittest.TestCase):
    """AC #1 — three consecutive non-improving iters halt with `oracle_plateau`.

    Uses constant composites (0.3) with default `--plateau-window 3`.
    History fills to 4 entries; max-prior (excluding last 3) = max([0.3]) = 0.3;
    overall max = 0.3; 0.3 ≤ 0.3 → plateau. Halt at iter 4.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac1-plateau-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        # Constant composite 0.3 (below threshold 0.5) for plateau testing.
        _make_oracle(self.target, _below_threshold_oracle(composite=0.3))
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_with_verdict(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_default_plateau_halts_at_iter_four(self):
        # Default --plateau-window 3 with constant composite → halt at iter 4.
        # Override the test default of --plateau-window 0 by passing the
        # default explicitly (3).
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "10",
            "--plateau-window", "3",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 4)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")
        self.assertEqual(summary["iterations_completed"], 4)
        self.assertEqual(summary["plateau_window"], 3)
        # History should be in the summary.
        self.assertEqual(len(summary["oracle_score_history"]), 4)


# ============================================================================
# Slice 003-05 — AC #2: --plateau-window override
# ============================================================================


class PlateauWindowOverrideTests(unittest.TestCase):
    """AC #2 — `--plateau-window 5` requires 5 non-improving iterations."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac2-plateau-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle(composite=0.3))
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_with_verdict(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_window_five_halts_at_iter_six(self):
        # window=5 requires 6 iters (1 baseline + 5 non-improving) for plateau.
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "10",
            "--plateau-window", "5",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 6)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")
        self.assertEqual(summary["plateau_window"], 5)

    def test_window_two_halts_at_iter_three(self):
        # window=2: needs 3 iters (1 baseline + 2 non-improving).
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "10",
            "--plateau-window", "2",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 3)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")


# ============================================================================
# Slice 003-05 — AC #3: Plateau semantics (≤ vs >)
# ============================================================================


class PlateauThresholdSemanticsTests(unittest.TestCase):
    """AC #3 — equality counts as non-improving; strict GT is improvement."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac3-plateau-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_equality_counts_as_non_improving(self):
        # Composites: 0.4, 0.4, 0.4, 0.4. All equal. Plateau fires.
        _make_oracle(
            self.target,
            _composite_progression_oracle([0.4, 0.4, 0.4, 0.4, 0.4, 0.4]),
        )
        _mock_claude_with_verdict(self.bindir, self.counter)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "10",
            "--plateau-window", "3",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")

    def test_strict_improvement_resets_plateau_counter(self):
        # Composites: 0.3, 0.3, 0.3, 0.4 (improvement on iter 4), 0.4, 0.4, 0.4.
        # Plateau is computed over the WHOLE history vs the last 3:
        #   - After iter 4 (history=[0.3,0.3,0.3,0.4]): max-overall=0.4,
        #     max-prior-3=max([0.3])=0.3. 0.4 > 0.3 → NOT plateaued.
        #   - After iter 5 (history=[0.3,0.3,0.3,0.4,0.4]): max-overall=0.4,
        #     max-prior-3=max([0.3,0.3])=0.3. 0.4 > 0.3 → NOT plateaued.
        #   - After iter 6 (history=[..,0.4]): max-overall=0.4,
        #     max-prior-3=max([0.3,0.3,0.3])=0.3. 0.4 > 0.3 → NOT plateaued.
        #   - After iter 7 (history=[..,0.4,0.4]): max-overall=0.4,
        #     max-prior-3=max([0.3,0.3,0.3,0.4])=0.4. 0.4 ≤ 0.4 → plateau! Halt.
        _make_oracle(
            self.target,
            _composite_progression_oracle([0.3, 0.3, 0.3, 0.4, 0.4, 0.4, 0.4]),
        )
        _mock_claude_with_verdict(self.bindir, self.counter)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "10",
            "--plateau-window", "3",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 7)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")


# ============================================================================
# Slice 003-05 — AC #4: --plateau-window 0 disables
# ============================================================================


class PlateauDisabledTests(unittest.TestCase):
    """AC #4 — `--plateau-window 0` disables plateau detection entirely."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac4-plateau-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle(composite=0.3))
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_with_verdict(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_window_zero_runs_to_max_iterations(self):
        # Constant composite normally trips plateau at iter 4. With
        # --plateau-window 0, the loop runs to the iteration cap.
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 5)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertEqual(summary["plateau_window"], 0)


# ============================================================================
# Slice 003-05 — AC #5: runner.md ships, runner verdict parses
# ============================================================================


class RunnerVerdictBlockTests(unittest.TestCase):
    """AC #5 — `agents/runner.md` is real; runner verdict block parses + surfaces."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac5-runner-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_runner_md_is_not_placeholder(self):
        runner_md = REPO_ROOT / "agents" / "runner.md"
        text = runner_md.read_text()
        self.assertNotIn("Status: placeholder", text)
        # Verdict block schema documented in the prompt.
        self.assertIn("schema_version: 1", text)
        self.assertIn("CHANGES_MADE", text)
        self.assertIn("NO_CHANGES", text)
        self.assertIn("BLOCKED", text)

    def test_runner_md_forbids_editing_approved_spec_oracle(self):
        # Spec 006-04 AC5 — loop protection: the runner prompt must tell the
        # runner not to edit frozen spec-oracle artifacts (no self-grading).
        text = (REPO_ROOT / "agents" / "runner.md").read_text().lower()
        self.assertIn(".servo/spec-oracles", text)
        self.assertTrue(
            "don't edit" in text or "do not edit" in text or "frozen" in text,
            "runner.md must forbid editing the frozen spec-oracle artifacts")
        self.assertIn("self-grading", text)

    def test_runner_md_documents_narrow_first_investigation(self):
        # Spec 021-01 — runner prompt carries the coherent narrow-first block.
        text = _markdown_section(
            (REPO_ROOT / "agents" / "runner.md").read_text(),
            "Investigation discipline",
        ).lower()
        self.assertIn("## investigation discipline", text)
        for phrase in (
            "files that changed",
            "oracle output",
            "locate before you read",
            "glob",
            "grep",
            "batch that discovery",
            "focused ranges",
            "simpler query",
        ):
            self.assertIn(phrase, text)

    def test_runner_md_documents_load_bearing_assumptions_field(self):
        # Spec 021-02 — runner records headless assumptions instead of asking.
        prompt = (REPO_ROOT / "agents" / "runner.md").read_text()
        posture = _markdown_section(prompt, "Operating posture").lower()
        output = _markdown_section(
            prompt, "Required output: fenced `verdict` block",
        ).lower()
        avoid = _markdown_section(prompt, "What to avoid").lower()
        self.assertIn("no clarifying questions", posture)
        self.assertIn("load-bearing assumptions", posture)
        self.assertIn("assumptions:", output)
        self.assertIn("optional under `schema_version: 1`", output)
        self.assertIn("omit the field", output)
        self.assertIn("record any load-bearing interpretation", avoid)

    def test_runner_verdict_block_surfaces_in_per_iter_json(self):
        # Iter 1 is runner; emit a CHANGES_MADE verdict and verify it
        # appears in the per-iter JSON line.
        block = _runner_verdict_block(
            verdict="CHANGES_MADE", files_changed="a.py, b.py",
            reasoning="Added null-check",
        )
        _mock_claude_with_verdict(
            self.bindir, self.counter,
            runner_block=block,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        self.assertEqual(len(per_iter), 1)
        v = per_iter[0]["verdict"]
        self.assertEqual(v["schema_version"], 1)
        self.assertEqual(v["verdict"], "CHANGES_MADE")
        self.assertEqual(v["files_changed"], "a.py, b.py")
        self.assertEqual(v["reasoning"], "Added null-check")

    def test_runner_verdict_block_surfaces_assumptions_in_per_iter_json(self):
        # Spec 021-02 — optional assumptions survive parser/log round-trip.
        assumption = "Prompt targets Python API behavior, not CLI output."
        block = _runner_verdict_block(
            verdict="CHANGES_MADE",
            files_changed="a.py",
            assumptions=assumption,
            reasoning="Added API regression coverage",
        )
        _mock_claude_with_verdict(
            self.bindir, self.counter,
            runner_block=block,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        self.assertEqual(len(per_iter), 1)
        v = per_iter[0]["verdict"]
        self.assertEqual(v["schema_version"], 1)
        self.assertEqual(v["assumptions"], assumption)


# ============================================================================
# Slice 003-05 — AC #6: judge.md ships, judge verdict parses
# ============================================================================


class JudgeVerdictBlockTests(unittest.TestCase):
    """AC #6 — `agents/judge.md` is real; judge verdict block parses + surfaces."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac6-judge-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_judge_md_is_not_placeholder(self):
        judge_md = REPO_ROOT / "agents" / "judge.md"
        text = judge_md.read_text()
        self.assertNotIn("Status: placeholder", text)
        # Verdict block schema documented in the prompt.
        self.assertIn("schema_version: 1", text)
        self.assertIn("PASS", text)
        self.assertIn("FAIL", text)
        self.assertIn("INCONCLUSIVE", text)

    def test_judge_md_documents_narrow_first_investigation(self):
        # Spec 021-01 — judge prompt carries the parallel narrow-first block.
        text = _markdown_section(
            (REPO_ROOT / "agents" / "judge.md").read_text(),
            "Investigation discipline",
        ).lower()
        self.assertIn("## investigation discipline", text)
        for phrase in (
            "files_changed",
            "oracle output",
            "locate before you read",
            "glob",
            "grep",
            "batch that discovery",
            "focused ranges",
            "simpler query",
        ):
            self.assertIn(phrase, text)

    def test_judge_md_documents_assumption_verification(self):
        # Spec 021-02 — judge verifies runner assumptions against evidence.
        text = (REPO_ROOT / "agents" / "judge.md").read_text()
        prompt_shape = _markdown_section(text, "Iteration prompt shape").lower()
        output = _markdown_section(
            text, "Required output: fenced `verdict` block",
        ).lower()
        self.assertIn("assumptions:", prompt_shape)
        self.assertIn("verify each load-bearing assumption", prompt_shape)
        self.assertIn("changed code", prompt_shape)
        self.assertIn("oracle output", prompt_shape)
        self.assertIn("unsupported or violated assumption", prompt_shape)
        self.assertIn("verdict", prompt_shape)
        self.assertIn("reasoning", output)
        self.assertIn("unsupported or violated", output)

    def test_judge_verdict_block_surfaces_in_per_iter_json(self):
        # Iter 2 is judge; emit a PASS verdict and verify it appears in
        # the per-iter JSON line for iter 2.
        judge_block = _judge_verdict_block(
            verdict="PASS", score=0.85,
            reasoning="Change correctly addresses failing component",
        )
        _mock_claude_with_verdict(
            self.bindir, self.counter,
            judge_block=judge_block,
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        self.assertEqual(len(per_iter), 2)
        v = per_iter[1]["verdict"]  # iter 2 is judge
        self.assertEqual(v["schema_version"], 1)
        self.assertEqual(v["verdict"], "PASS")
        self.assertEqual(v["score"], "0.85")
        self.assertEqual(v["reasoning"], "Change correctly addresses failing component")


# ============================================================================
# Slice 003-05 — AC #7: Agent alternation via `claude --agent <name>`
# ============================================================================


class AgentAlternationDispatchTests(unittest.TestCase):
    """AC #7 — each iteration invokes `claude --agent <runner|judge>` alternating."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac7-agent-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        self.args_log = tmp / "args.log"
        _mock_claude_with_verdict(
            self.bindir, self.counter, args_log=self.args_log,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_alternation_in_argv(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "4",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        invocations = _read_args_log(self.args_log)
        self.assertEqual(len(invocations), 4)
        agents = [_find_flag_value(argv, "--agent") for argv in invocations]
        self.assertEqual(agents, ["runner", "judge", "runner", "judge"])

    def test_per_iter_json_carries_agent_field(self):
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "4",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        self.assertEqual(len(per_iter), 4)
        self.assertEqual(
            [line["agent"] for line in per_iter],
            ["runner", "judge", "runner", "judge"],
        )


# ============================================================================
# Slice 003-05 — AC #8: Per-iteration prompt assembly
# ============================================================================


class PromptAssemblyTests(unittest.TestCase):
    """AC #8 — iter 2+ prompt = seed + last oracle output + last verdict block."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac8-prompt-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle(composite=0.42))
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        self.args_log = tmp / "args.log"
        _mock_claude_with_verdict(
            self.bindir, self.counter, args_log=self.args_log,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_iter_one_prompt_is_seed_only(self):
        result = _run_loop(
            self.target, "--prompt", "my-seed-prompt",
            "--max-iterations", "1", "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        invocations = _read_args_log(self.args_log)
        self.assertEqual(len(invocations), 1)
        # Last arg in each invocation is the assembled prompt.
        prompt_arg = invocations[0][-1]
        # Iter 1 has no prior oracle / verdict — prompt is the seed verbatim.
        self.assertEqual(prompt_arg, "my-seed-prompt")

    def test_iter_two_prompt_includes_oracle_and_verdict(self):
        result = _run_loop(
            self.target, "--prompt", "my-seed-prompt",
            "--max-iterations", "2", "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        invocations = _read_args_log(self.args_log)
        self.assertEqual(len(invocations), 2)
        iter2_prompt = invocations[1][-1]
        # Seed is the first chunk.
        self.assertTrue(iter2_prompt.startswith("my-seed-prompt"))
        # Last oracle output (JSON-encoded) is embedded.
        self.assertIn("Last oracle output", iter2_prompt)
        self.assertIn("composite", iter2_prompt)
        self.assertIn("0.42", iter2_prompt)
        # Last verdict block is embedded.
        self.assertIn("Last agent verdict", iter2_prompt)
        self.assertIn("schema_version: 1", iter2_prompt)
        self.assertIn("CHANGES_MADE", iter2_prompt)


# ============================================================================
# Slice 003-05 — AC #10: verdict_schema_mismatch refusal (three paths)
# ============================================================================


class VerdictSchemaMismatchTests(unittest.TestCase):
    """AC #10 — three refusal paths: (a) field absent, (b) ≠ 1, (c) wrong type."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-ac10-verdict-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_mock_with_block_text(self, block_body_lines: list) -> None:
        """Build a mock that emits a verdict block with the supplied lines."""
        block_text = (
            "\\n" + f"{_BTICK}verdict\\n" + "\\n".join(block_body_lines) + f"\\n{_BTICK}\\n"
        )
        _mock_claude_with_raw_result(
            self.bindir, self.counter,
            result_text=f"agent text{block_text}",
        )

    def test_a_schema_version_absent_within_block(self):
        # Block exists but lacks schema_version (some other field is first).
        self._make_mock_with_block_text([
            "verdict: CHANGES_MADE",
            "reasoning: missing schema_version",
        ])
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("schema_version", result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "verdict_schema_mismatch")

    def test_b_schema_version_wrong_value(self):
        # Block has schema_version: 2 (expected 1).
        self._make_mock_with_block_text([
            "schema_version: 2",
            "verdict: CHANGES_MADE",
            "reasoning: wrong version",
        ])
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("schema_version", result.stderr)
        self.assertIn("2", result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "verdict_schema_mismatch")

    def test_c_schema_version_string_type(self):
        # Block has schema_version: "1" (string instead of int).
        self._make_mock_with_block_text([
            'schema_version: \\"1\\"',
            "verdict: CHANGES_MADE",
            "reasoning: string-typed schema_version",
        ])
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("schema_version", result.stderr)
        self.assertIn("string", result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "verdict_schema_mismatch")

    def test_d_schema_version_non_integer(self):
        # Block has schema_version: abc (non-integer literal).
        self._make_mock_with_block_text([
            "schema_version: abc",
            "verdict: CHANGES_MADE",
        ])
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("non-integer", result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "verdict_schema_mismatch")

    def test_e_malformed_field_line_refuses(self):
        # Spec 021-02 — multiline/truncated assumptions cannot silently parse.
        self._make_mock_with_block_text([
            "schema_version: 1",
            "verdict: CHANGES_MADE",
            "files_changed: a.py",
            "assumptions: Prompt targets Python API behavior",
            "not CLI output",
            "reasoning: malformed multiline assumption",
        ])
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("malformed field line", result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "verdict_schema_mismatch")

    def test_no_block_at_all_is_not_a_refusal(self):
        # AC10 enumerates three refusal paths within a block; "no block" is
        # informational, not a refusal. Loop continues with last_verdict=None.
        # Mock emits a `result` with no verdict block.
        _mock_claude_with_raw_result(
            self.bindir, self.counter,
            result_text="agent text without a verdict block",
        )
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "2",
            "--plateau-window", "0",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # Iters ran normally.
        self.assertEqual(int(self.counter.read_text().strip()), 2)
        # Per-iter JSON carries `verdict: null`.
        per_iter = [
            line for line in _stdout_json_lines(result.stdout) if "iteration" in line
        ]
        for line in per_iter:
            self.assertIsNone(line["verdict"])


# ============================================================================
# Slice 003-05 — Unit tests for _parse_verdict_block helper
# ============================================================================


class ParseVerdictBlockUnitTests(unittest.TestCase):
    """Direct unit tests for the verdict block parser.

    Covers shapes that are tedious to exercise end-to-end (multiple blocks
    in one response → last wins; empty blocks; extra whitespace).
    """

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("loop", LOOP)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.parse = module._parse_verdict_block

    def test_happy_path(self):
        text = (
            "intro\n\n"
            "```verdict\n"
            "schema_version: 1\n"
            "verdict: PASS\n"
            "score: 0.9\n"
            "reasoning: looks good\n"
            "```\n"
        )
        fields, err = self.parse(text)
        self.assertIsNone(err)
        self.assertEqual(fields["schema_version"], 1)
        self.assertEqual(fields["verdict"], "PASS")
        self.assertEqual(fields["score"], "0.9")
        self.assertEqual(fields["reasoning"], "looks good")

    def test_optional_assumptions_field_is_accepted_under_schema_v1(self):
        assumption = "Prompt targets Python API behavior, not CLI output."
        text = (
            "```verdict\n"
            "schema_version: 1\n"
            "verdict: CHANGES_MADE\n"
            "files_changed: src/auth.py\n"
            f"assumptions: {assumption}\n"
            "reasoning: added regression coverage\n"
            "```\n"
        )
        fields, err = self.parse(text)
        self.assertIsNone(err)
        self.assertEqual(fields["schema_version"], 1)
        self.assertEqual(fields["assumptions"], assumption)
        self.assertEqual(fields["reasoning"], "added regression coverage")

    def test_malformed_multiline_assumptions_field_refuses(self):
        text = (
            "```verdict\n"
            "schema_version: 1\n"
            "verdict: CHANGES_MADE\n"
            "files_changed: src/auth.py\n"
            "assumptions: Prompt targets Python API behavior\n"
            "not CLI output.\n"
            "reasoning: added regression coverage\n"
            "```\n"
        )
        fields, err = self.parse(text)
        self.assertIsNone(fields)
        self.assertIn("malformed field line", err)

    def test_no_block_returns_none_none(self):
        fields, err = self.parse("no block here at all")
        self.assertIsNone(fields)
        self.assertIsNone(err)

    def test_multiple_blocks_last_wins(self):
        text = (
            "```verdict\nschema_version: 1\nverdict: PASS\n```\n"
            "intermediate text\n"
            "```verdict\nschema_version: 1\nverdict: FAIL\n```\n"
        )
        fields, err = self.parse(text)
        self.assertIsNone(err)
        self.assertEqual(fields["verdict"], "FAIL")

    def test_empty_block_is_an_error(self):
        text = "```verdict\n\n```\n"
        fields, err = self.parse(text)
        self.assertIsNone(fields)
        self.assertIn("empty", err)

    def test_schema_version_not_first_key(self):
        # Field order matters per AC10.
        text = (
            "```verdict\n"
            "verdict: PASS\n"
            "schema_version: 1\n"  # not the first non-empty line
            "```\n"
        )
        fields, err = self.parse(text)
        self.assertIsNone(fields)
        self.assertIn("first key", err)

    def test_schema_version_quoted_string_single_quotes(self):
        text = "```verdict\nschema_version: '1'\nverdict: PASS\n```\n"
        fields, err = self.parse(text)
        self.assertIsNone(fields)
        self.assertIn("string", err)


# ============================================================================
# Slice 003-06 — goal-driven loop (ADR-0008 rebase)
#
# Test classes map to the slice's acceptance criteria:
#   AC1 → GoalDriverDispatchTests        (driver routing; loop unchanged)
#   AC2 → GoalSentinelContractTests      (sentinel parse incl. bare-substring negative)
#   AC3 → GoalOuterCapsTests             (--max-turns + --max-budget-usd on the outer call)
#   AC4 → GoalOracleAuthorityTests       (final gate is authority; oracle_disagreement)
#   AC5 → GoalTerminalReasonMapTests     (subtype → terminal_reason map)
#   AC6 → GoalUnavailableTests           (refuse, don't silently degrade)
#   AC7 → GoalStateRecordingTests        (state.json shape; resume refusal)
# plus direct unit tests for the pure helpers.
#
# The goal-driver mock emits a stream-json (JSONL) body — an optional assistant
# text event (carrying the sentinel and/or the /goal refusal breadcrumb), then a
# final `type=result` event with a chosen subtype/terminal_reason/cost/num_turns
# (the strings empirically re-confirmed on claude 2.1.175; ADR-0008 V2).
# ============================================================================


def _goal_result_event(
    *, subtype="success", terminal_reason="completed", is_error=False,
    num_turns=2, cost=0.05, session_id="goal-session-1", result_text="done",
) -> dict:
    """A `type=result` stream event matching the shape `claude -p` emits."""
    return {
        "type": "result", "subtype": subtype, "is_error": is_error,
        "terminal_reason": terminal_reason, "num_turns": num_turns,
        "total_cost_usd": cost, "session_id": session_id, "result": result_text,
    }


# A full, real oracle pass sentinel (with the composite=/threshold= tail).
GOAL_PASS_SENTINEL = "SERVO_ORACLE_VERDICT exit=0 status=pass composite=0.9000 threshold=0.5"
# The bare substring the /goal condition text carries — must NOT count (AC2).
GOAL_BARE_SUBSTRING = "SERVO_ORACLE_VERDICT exit=0 status=pass"
# The verbatim /goal hook-restriction refusal (ADR-0008 V3).
GOAL_HOOK_REFUSAL = (
    "/goal can't run while hooks are restricted (disableAllHooks or "
    "allowManagedHooksOnly is set in settings or by policy)."
)


def _goal_stream_jsonl(*, assistant_text=None, result_event=None) -> str:
    """Build a stream-json (JSONL) body: init + optional assistant text + result."""
    events = [{"type": "system", "subtype": "init", "session_id": "goal-session-1"}]
    if assistant_text is not None:
        events.append({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": assistant_text}]},
        })
    events.append(result_event if result_event is not None else _goal_result_event())
    return "\n".join(json.dumps(e) for e in events)


def _mock_claude_goal(
    bindir: Path, jsonl: str, *,
    args_log: Optional[Path] = None, counter_file: Optional[Path] = None,
) -> Path:
    """Mock `claude` emitting a fixed stream-json body (goal-driver tests).

    `--version` is short-circuited by `_make_mock_claude` (so the goal driver's
    `_get_claude_version()` capture never consumes the counter / args log).
    Optionally bumps `counter_file` and appends argv to `args_log` (the
    U+001F/U+001E format `_read_args_log` parses).
    """
    parts = ["#!/usr/bin/env bash"]
    if counter_file is not None:
        parts += [
            f"counter_file='{counter_file}'",
            'if [ -f "$counter_file" ]; then n=$(cat "$counter_file"); else n=0; fi',
            "n=$((n + 1))",
            'echo "$n" > "$counter_file"',
        ]
    if args_log is not None:
        parts += [
            f'for arg in "$@"; do printf "%s\\037" "$arg" >> \'{args_log}\'; done',
            f"printf '\\036' >> '{args_log}'",
        ]
    parts += ["cat <<'__JSONL_EOF__'", jsonl, "__JSONL_EOF__", ""]
    return _make_mock_claude(bindir, "\n".join(parts))


def _run_goal(
    target: Path,
    *extra_args: str,
    mock_bindir: Optional[Path] = None,
    path_override: Optional[str] = None,
    extra_env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    """Invoke `loop.py --driver goal` with a sandboxed PATH.

    Uses `sys.executable` so the goal driver's final `gate.py` run executes
    under the same (modern) interpreter as the test runner. Unlike `_run_loop`
    this does not inject `--plateau-window` (a loop-mode-only brake).

    Slice 003-07: defaults HOME to an isolated empty dir and neutralises the
    managed-settings layer so the host-scope routing audit is hermetic (the goal
    driver is now gated by `_decide_route`, which reads the settings hierarchy).
    """
    if path_override is not None:
        path = path_override
    elif mock_bindir is not None:
        path = f"{mock_bindir}:{SYSTEM_PATH}"
    else:
        path = SYSTEM_PATH
    env = {**os.environ, "PATH": path, "HOME": _ISOLATED_HOME,
           "SERVO_MANAGED_SETTINGS_PATH": ""}
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, str(LOOP), str(target), "--driver", "goal", *extra_args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


class _GoalTargetMixin:
    """Per-test scaffolded target + bindir; oracle body chosen by the test."""

    def _setup_target(self, oracle_body: str):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-goal-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, oracle_body)
        self.bindir = tmp / "bin"
        self.bindir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _summary(self, result):
        return _stdout_json_lines(result.stdout)[-1]

    def _state(self):
        states = list(self.target.glob(".servo/runs/*/state.json"))
        self.assertEqual(len(states), 1, "expected exactly one run state file")
        return json.loads(states[0].read_text())


# ---------------------------------------------------------------------------
# Direct unit tests for the goal-driver pure helpers
# ---------------------------------------------------------------------------


class GoalPureHelperUnitTests(unittest.TestCase):
    """Sentinel scan (AC2), prompt composition (AC1/AC2), refusal detection (AC6)."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("loop", LOOP)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_full_sentinel_counts_as_pass(self):
        self.assertTrue(self.m._scan_pass_sentinel(
            "noise\n" + GOAL_PASS_SENTINEL + "\nmore"))

    def test_bare_substring_is_not_a_pass(self):
        # AC2: the /goal condition text echoes the bare substring; it lacks the
        # composite=/threshold= tail and must NOT count as a real pass.
        self.assertFalse(self.m._scan_pass_sentinel(GOAL_BARE_SUBSTRING))

    def test_placeholder_instruction_line_is_not_a_pass(self):
        self.assertFalse(self.m._scan_pass_sentinel(
            "SERVO_ORACLE_VERDICT exit=<exit_code> status=<status> "
            "composite=<composite> threshold=<threshold>"))

    def test_full_sentinel_with_fail_status_is_not_a_pass(self):
        self.assertFalse(self.m._scan_pass_sentinel(
            "SERVO_ORACLE_VERDICT exit=1 status=fail composite=0.2 threshold=0.5"))

    def test_full_sentinel_nonzero_exit_is_not_a_pass(self):
        # Defensive: a (malformed) line claiming status=pass but exit!=0.
        self.assertFalse(self.m._scan_pass_sentinel(
            "SERVO_ORACLE_VERDICT exit=2 status=pass composite=0.9 threshold=0.5"))

    def test_compose_prompt_shape(self):
        prompt = self.m._compose_goal_prompt("fix the failing tests")
        self.assertIn("/goal", prompt)
        self.assertIn(self.m.SENTINEL_PASS_BARE, prompt)       # the fact-check cue
        self.assertIn("fix the failing tests", prompt)          # the seed task
        self.assertIn(str(self.m.GATE_PATH), prompt)            # how to run the gate
        self.assertIn("--json", prompt)

    def test_compose_prompt_cannot_self_satisfy(self):
        # The composed prompt (and any transcript echo of it) must never trip
        # the strict pass predicate — placeholders + bare cue only.
        prompt = self.m._compose_goal_prompt("do the thing")
        self.assertFalse(self.m._scan_pass_sentinel(prompt))

    def test_goal_unavailable_matches_verbatim_refusal(self):
        # The discriminating refusal sentence fires regardless of turn count.
        self.assertTrue(self.m._detect_goal_unavailable(GOAL_HOOK_REFUSAL, 0))
        self.assertTrue(self.m._detect_goal_unavailable(GOAL_HOOK_REFUSAL, 3))

    def test_goal_unavailable_ignores_normal_output(self):
        self.assertFalse(self.m._detect_goal_unavailable(
            "ran the gate, it passed, all good", 2))

    def test_goal_unavailable_keys_only_count_on_zero_turn_run(self):
        # The bare config keys could appear in an agent's own work — they only
        # signal goal_unavailable when nothing actually ran (num_turns == 0).
        keys_text = "I edited settings.json to set disableAllHooks: false"
        self.assertFalse(self.m._detect_goal_unavailable(keys_text, 4))
        self.assertTrue(self.m._detect_goal_unavailable(keys_text, 0))


# ---------------------------------------------------------------------------
# AC1 — driver dispatch (goal runs; loop stays the unchanged default)
# ---------------------------------------------------------------------------


class GoalDriverDispatchTests(_GoalTargetMixin, unittest.TestCase):
    def setUp(self):
        self._setup_target(_passing_oracle())

    def test_goal_driver_runs_and_labels_summary(self):
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="ran gate\n" + GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success", cost=0.1),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = self._summary(result)
        self.assertEqual(summary["driver"], "goal")
        self.assertEqual(summary["terminal_reason"], "oracle_pass")

    def test_loop_only_flags_warn_under_goal_driver(self):
        # nit: --plateau-window / --context-fill-threshold are loop-mode brakes;
        # goal mode ignores them but says so (no silent surprise).
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        result = _run_goal(self.target, "--prompt", "x", "--plateau-window", "5",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["terminal_reason"], "oracle_pass")
        self.assertIn("--plateau-window", result.stderr)
        self.assertIn("ignored", result.stderr)

    def test_plateau_noise_floor_warns_under_goal_driver(self):
        # --plateau-noise-floor is a plateau brake too, so like --plateau-window
        # it is a loop-mode-only flag: goal mode ignores it but says so.
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           "--plateau-noise-floor", "0.05",
                           mock_bindir=self.bindir,
                           extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["terminal_reason"], "oracle_pass")
        self.assertIn("--plateau-noise-floor", result.stderr)
        self.assertIn("ignored", result.stderr)

    def test_default_driver_is_loop_and_unchanged(self):
        # Default (no --driver) routes to the hand-rolled loop: a constant mock
        # emits the 003-01..05 single-result JSON; the summary carries loop-mode
        # fields and is NOT labelled driver=goal.
        counter = Path(self.tmpdir) / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), counter)
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertNotIn("driver", summary)            # loop summary has no driver key
        self.assertIn("oracle_score_history", summary)  # loop-mode-only field


# ---------------------------------------------------------------------------
# AC2 — sentinel contract (shared format; bare-substring negative)
# ---------------------------------------------------------------------------


class GoalSentinelContractTests(_GoalTargetMixin, unittest.TestCase):
    def test_full_sentinel_marks_transcript_pass(self):
        self._setup_target(_passing_oracle())
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertTrue(self._summary(result)["transcript_showed_pass"])

    def test_bare_substring_does_not_mark_transcript_pass(self):
        # The agent only echoed the bare /goal cue (no tail). Even with a
        # below-threshold final gate this must be oracle_below_threshold, NOT
        # oracle_disagreement — the bare substring is not a real pass.
        self._setup_target(_below_threshold_oracle())
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="working on it: " + GOAL_BARE_SUBSTRING,
            result_event=_goal_result_event(subtype="success"),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        summary = self._summary(result)
        self.assertFalse(summary["transcript_showed_pass"])
        self.assertEqual(summary["terminal_reason"], "oracle_below_threshold")


# ---------------------------------------------------------------------------
# AC3 — hard caps on the outer call (--max-turns + --max-budget-usd)
# ---------------------------------------------------------------------------


class GoalOuterCapsTests(_GoalTargetMixin, unittest.TestCase):
    def setUp(self):
        self._setup_target(_passing_oracle())
        self.args_log = Path(self.tmpdir) / "args.log"
        _mock_claude_goal(
            self.bindir,
            _goal_stream_jsonl(assistant_text=GOAL_PASS_SENTINEL),
            args_log=self.args_log,
        )

    def _argv(self):
        invocations = _read_args_log(self.args_log)
        self.assertEqual(len(invocations), 1, "expected a single claude -p call")
        return invocations[0]

    def test_defaults_max_turns_5_budget_2(self):
        _run_goal(self.target, "--prompt", "x",
                  mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        argv = self._argv()
        self.assertEqual(_find_flag_value(argv, "--max-turns"), "5")
        self.assertEqual(_find_flag_value(argv, "--max-budget-usd"), "2.000000")
        self.assertIn("stream-json", argv)
        self.assertIn("--verbose", argv)

    def test_overrides_carry_to_outer_caps(self):
        _run_goal(self.target, "--prompt", "x",
                  "--max-iterations", "3", "--cost-ceiling", "0.50",
                  mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        argv = self._argv()
        self.assertEqual(_find_flag_value(argv, "--max-turns"), "3")
        self.assertEqual(_find_flag_value(argv, "--max-budget-usd"), "0.500000")

    def test_cost_ceiling_zero_omits_budget_flag(self):
        # Ceiling disabled → no --max-budget-usd, but --max-turns still binds.
        _run_goal(self.target, "--prompt", "x", "--cost-ceiling", "0",
                  mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        argv = self._argv()
        self.assertIsNone(_find_flag_value(argv, "--max-budget-usd"))
        self.assertEqual(_find_flag_value(argv, "--max-turns"), "5")


class GoalDriverParityTests(_GoalTargetMixin, unittest.TestCase):
    """Bug 004 — the goal driver mirrors the loop driver's 001/002 safeguards.

    (1) It forwards the target's own `.claude/settings.json` via `--settings`
    (bug 002 twin). (2) A hard `/goal` error envelope (`is_error: true` with an
    `api_error_status`, and a non-cap subtype) halts on `claude_invocation_failed`
    (exit 2) naming the cause, instead of running the final gate and reporting a
    misleading `oracle_below_threshold` (bug 001 twin).
    """

    def test_goal_forwards_target_settings(self):
        self._setup_target(_passing_oracle())
        settings = self.target / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(
            {"permissions": {"allow": ["Bash", "Edit", "Write"]}}))
        args_log = Path(self.tmpdir) / "args.log"
        _mock_claude_goal(
            self.bindir,
            _goal_stream_jsonl(assistant_text=GOAL_PASS_SENTINEL),
            args_log=args_log,
        )
        _run_goal(self.target, "--prompt", "x",
                  mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        invocations = _read_args_log(args_log)
        self.assertEqual(len(invocations), 1, "expected a single claude -p call")
        settings_arg = _find_flag_value(invocations[0], "--settings")
        self.assertIsNotNone(
            settings_arg, "goal driver did not forward the target's --settings")
        self.assertEqual(Path(settings_arg).resolve(), settings.resolve())

    def test_goal_auth_error_envelope_halts_invocation_failed(self):
        self._setup_target(_below_threshold_oracle())
        ev = _goal_result_event(
            subtype="error_during_execution", is_error=True,
            result_text=("Failed to authenticate. API Error: 401 Invalid "
                         "authentication credentials"),
        )
        ev["api_error_status"] = 401
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(result_event=ev))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir,
                           extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(
            result.returncode, 2,
            f"expected rc=2, got {result.returncode}; stderr={result.stderr}")
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "claude_invocation_failed")
        # The operator must see the real cause, not a below-threshold oracle.
        self.assertIn("401", result.stderr)


# ---------------------------------------------------------------------------
# AC4 — oracle stays the authority (fail-closed on disagreement)
# ---------------------------------------------------------------------------


class GoalOracleAuthorityTests(_GoalTargetMixin, unittest.TestCase):
    def test_transcript_pass_but_gate_fails_is_disagreement(self):
        # /goal stopped on a real pass sentinel, but the authoritative final
        # gate scores below threshold → fail-closed (exit 2).
        self._setup_target(_below_threshold_oracle())
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "oracle_disagreement")
        self.assertEqual(summary["final_oracle_status"], "below_threshold")

    def test_final_gate_pass_is_authority(self):
        # The final gate.py — not the transcript — is the verdict. Passing
        # oracle + pass sentinel → oracle_pass, exit 0.
        self._setup_target(_passing_oracle())
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["terminal_reason"], "oracle_pass")

    def test_success_without_transcript_pass_and_below_is_below_threshold(self):
        # success subtype but the agent never printed a pass sentinel; final
        # gate below threshold → oracle_below_threshold (not disagreement).
        self._setup_target(_below_threshold_oracle())
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="made some progress but not done",
            result_event=_goal_result_event(subtype="success"),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["terminal_reason"], "oracle_below_threshold")


# ---------------------------------------------------------------------------
# AC5 — terminal-reason mapping (subtype → reason)
# ---------------------------------------------------------------------------


class GoalTerminalReasonMapTests(_GoalTargetMixin, unittest.TestCase):
    def _run_with(self, *, subtype, oracle_body, assistant_text="working"):
        self._setup_target(oracle_body)
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=assistant_text,
            result_event=_goal_result_event(subtype=subtype, is_error=subtype.startswith("error_")),
        ))
        return _run_goal(self.target, "--prompt", "x",
                         mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})

    def test_error_max_turns_maps_to_iteration_cap_reached(self):
        result = self._run_with(subtype="error_max_turns", oracle_body=_below_threshold_oracle())
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["terminal_reason"], "iteration_cap_reached")

    def test_error_max_budget_maps_to_cost_ceiling_reached(self):
        result = self._run_with(
            subtype="error_max_budget_usd", oracle_body=_below_threshold_oracle())
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["terminal_reason"], "cost_ceiling_reached")

    def test_success_plus_pass_maps_to_oracle_pass(self):
        result = self._run_with(subtype="success", oracle_body=_passing_oracle(),
                                assistant_text=GOAL_PASS_SENTINEL)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["terminal_reason"], "oracle_pass")

    def test_success_plus_fail_maps_to_oracle_below_threshold(self):
        result = self._run_with(subtype="success", oracle_body=_below_threshold_oracle())
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["terminal_reason"], "oracle_below_threshold")

    def test_cap_precedence_over_disagreement(self):
        # Edge: a cap subtype AND a transcript pass sentinel AND a below-
        # threshold final gate. The cap wins (iteration_cap_reached, exit 0) —
        # NOT oracle_disagreement — because had /goal actually seen a pass it
        # would have stopped success before the cap. The oracle's verdict is
        # still recorded honestly in final_oracle_status.
        result = self._run_with(subtype="error_max_turns",
                                oracle_body=_below_threshold_oracle(),
                                assistant_text=GOAL_PASS_SENTINEL)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "iteration_cap_reached")
        self.assertEqual(summary["final_oracle_status"], "below_threshold")
        self.assertTrue(summary["transcript_showed_pass"])


# ---------------------------------------------------------------------------
# AC6 — headless-/goal precondition (refuse, don't silently degrade)
# ---------------------------------------------------------------------------


class GoalUnavailableTests(_GoalTargetMixin, unittest.TestCase):
    def setUp(self):
        self._setup_target(_passing_oracle())

    def test_hook_restriction_refusal_is_goal_unavailable(self):
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_HOOK_REFUSAL,
            result_event=_goal_result_event(subtype="success", num_turns=0, cost=0.0),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "goal_unavailable")
        self.assertEqual(summary["schema_version"], 1)  # auto-prefixed contract
        # The breadcrumb names the portable fallback.
        self.assertIn("--driver loop", result.stderr)

    def test_goal_unavailable_reports_real_cost(self):
        # nit fix: the refusal SENTENCE fires regardless of turn count; if the
        # run burned cost before refusing, the summary reports it (not $0).
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_HOOK_REFUSAL,
            result_event=_goal_result_event(subtype="success", num_turns=2, cost=0.07),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "goal_unavailable")
        self.assertAlmostEqual(summary["cumulative_cost_usd"], 0.07, places=6)

    def test_successful_run_mentioning_hook_keys_is_not_goal_unavailable(self):
        # Regression: an agent whose own (successful, multi-turn) work surfaces
        # the `disableAllHooks` key name must NOT be mis-flagged as
        # goal_unavailable — the keys only count on a zero-turn run.
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="audited settings.json — disableAllHooks is unset\n"
                            + GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success", num_turns=3),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "oracle_pass")


# ---------------------------------------------------------------------------
# AC7 — state recording + resume refusal
# ---------------------------------------------------------------------------


class GoalPreflightRefusalTests(_GoalTargetMixin, unittest.TestCase):
    """Goal mode reuses the shared existence checks but renders a goal-shaped
    refusal summary (`_refuse_goal`) — distinct from loop mode's."""

    def setUp(self):
        self._setup_target(_passing_oracle())
        # A mock is present, but preflight refuses before claude is invoked.
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(assistant_text=GOAL_PASS_SENTINEL))

    def test_missing_oracle_refuses_goal_shaped(self):
        (self.target / "oracle.sh").unlink()
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        summary = self._summary(result)
        self.assertEqual(summary["driver"], "goal")
        self.assertEqual(summary["terminal_reason"], "oracle_missing")
        self.assertIn("/servo:scaffold-init", result.stderr)
        # Refusal happens before any run dir is created.
        self.assertEqual(list(self.target.glob(".servo/runs/*/state.json")), [])

    def test_missing_manifest_refuses_goal_shaped(self):
        (self.target / ".servo" / "install.json").unlink()
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "manifest_missing")


class GoalStateRecordingTests(_GoalTargetMixin, unittest.TestCase):
    def setUp(self):
        self._setup_target(_passing_oracle())

    def test_state_records_run_id_cost_and_verdict(self):
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success", cost=0.42, num_turns=4),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        state = self._state()
        self.assertEqual(state["driver"], "goal")
        self.assertEqual(state["state_schema_version"], 1)
        self.assertTrue(state["run_id"])
        self.assertAlmostEqual(state["cumulative_cost_usd"], 0.42, places=6)
        self.assertEqual(state["terminal_reason"], "oracle_pass")
        self.assertEqual(state["final_oracle_status"], "pass")
        # The summary's run_id matches the on-disk directory.
        self.assertEqual(self._summary(result)["run_id"], state["run_id"])

    def test_goal_driver_refuses_resume(self):
        # A goal-capable mock so host-scope routing (003-07) admits the goal
        # driver; the resume refusal is then the operative reason (not the
        # host-unsupported one). The mock body is never invoked — resume refuses
        # first — but its --version short-circuit lets the routing probe pass.
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_PASS_SENTINEL))
        result = _run_goal(self.target, "--resume", "20260101T000000-abcd",
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "goal_resume_unsupported")
        self.assertIn("--resume is not supported", result.stderr)

    def test_loop_driver_refuses_to_resume_a_goal_run(self):
        # Produce a goal run, then try to resume its run-id with the loop driver.
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        _run_goal(self.target, "--prompt", "x",
                  mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        run_id = self._state()["run_id"]
        result = _run_loop(self.target, "--resume", run_id,
                           mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(
            _stdout_json_lines(result.stdout)[-1]["terminal_reason"],
            "goal_resume_unsupported",
        )


# ============================================================================
# Slice 003-07 — portable guardrails (ADR-0008 rebase)
#
# Test classes map to the slice's acceptance criteria:
#   AC1     → VendorGateUnitTests / VendorGateIntegrationTests
#   AC2/AC3 → DirtyTreeLoopTests / DirtyTreeGoalTests / DirtyTreeUnitTests
#   AC4/AC5 → RoutingUnitTests / HostScopeRoutingDispatchTests / ExplainRoutingTests
#   AC6     → SafeDefaultsTests
# ============================================================================


def _load_loop_module():
    """Import loop.py as an in-process module (for unit tests + monkeypatching)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("loop_mod_0307", LOOP)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _git_init(target: Path) -> None:
    """Initialise a quiet, identity-pinned git repo at `target`."""
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
    subprocess.run(["git", "init", "-q"], cwd=target, check=True, env=env,
                   capture_output=True)


def _git_commit_all(target: Path, message: str = "init") -> None:
    env = {**os.environ,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
    subprocess.run(["git", "add", "-A"], cwd=target, check=True, env=env,
                   capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=target, check=True,
                   env=env, capture_output=True)


# ---------------------------------------------------------------------------
# AC1 — vendor gate.py into the target (idempotent), relative path
# ---------------------------------------------------------------------------


class VendorGateUnitTests(unittest.TestCase):
    """`_ensure_vendored_gate` idempotence + path; goal prompt + authoritative
    gate run resolve gate.py on the vendored relative path (ADR-0008 V4)."""

    def setUp(self):
        self.m = _load_loop_module()
        self.tmpdir = tempfile.mkdtemp(prefix="servo-vendor-")
        self.target = Path(self.tmpdir) / "demo"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _vendored(self) -> Path:
        return self.target / ".claude" / "skills" / "servo-quality-gate" / "gate.py"

    def test_creates_byte_identical_vendored_copy(self):
        dest, err = self.m._ensure_vendored_gate(self.target)
        self.assertIsNone(err)
        self.assertEqual(dest, self._vendored())
        self.assertTrue(dest.is_file())
        self.assertEqual(dest.read_bytes(), self.m.GATE_PATH.read_bytes())

    def test_noop_when_present_and_current(self):
        dest, _ = self.m._ensure_vendored_gate(self.target)
        first_mtime = dest.stat().st_mtime_ns
        dest2, err = self.m._ensure_vendored_gate(self.target)
        self.assertIsNone(err)
        # Current copy → no rewrite (mtime unchanged), so the vendoring preflight
        # is cheap on every run.
        self.assertEqual(dest2.stat().st_mtime_ns, first_mtime)

    def test_refreshes_stale_copy(self):
        v = self._vendored()
        v.parent.mkdir(parents=True, exist_ok=True)
        v.write_text("# stale — not the real gate\n")
        dest, err = self.m._ensure_vendored_gate(self.target)
        self.assertIsNone(err)
        self.assertEqual(dest.read_bytes(), self.m.GATE_PATH.read_bytes())

    def test_breadcrumb_when_destination_unwritable(self):
        # `.claude` is a FILE, so mkdir of the skills subtree must fail → the
        # helper returns a breadcrumb rather than raising (fail-closed caller).
        (self.target / ".claude").write_text("not a dir")
        dest, err = self.m._ensure_vendored_gate(self.target)
        self.assertIsNone(dest)
        self.assertIsNotNone(err)

    def test_compose_goal_prompt_references_vendored_path(self):
        vendored = self._vendored()
        prompt = self.m._compose_goal_prompt("do the task", gate_path=vendored)
        self.assertIn(str(vendored), prompt)

    def test_run_goal_uses_vendored_path_for_authoritative_gate(self):
        # Spy on the authoritative final gate to capture the gate_path it runs,
        # and stub claude so no subprocess spawns.
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())
        captured = {}

        def fake_gate(target, gate_path=None):
            captured["gate_path"] = gate_path
            return {"exit_code": 0, "status": "pass",
                    "composite": 0.9, "threshold": 0.5}

        def fake_claude_goal(prompt, target, **kw):
            return ({"type": "result", "subtype": "success",
                     "terminal_reason": "completed", "num_turns": 1,
                     "total_cost_usd": 0.01}, "transcript", None)

        self.m._invoke_gate = fake_gate
        self.m._invoke_claude_goal = fake_claude_goal
        self.m._get_claude_version = lambda: "2.1.175"
        rc = self.m.run_goal_loop(self.target, prompt="x",
                                  max_iterations=3, cost_ceiling=1.0)
        self.assertEqual(rc, 0)
        self.assertEqual(captured["gate_path"], self._vendored())


class VendorGateIntegrationTests(_GoalTargetMixin, unittest.TestCase):
    """End-to-end: a goal run vendors gate.py and the vendored copy is functional."""

    def test_goal_run_creates_functional_vendored_gate(self):
        self._setup_target(_passing_oracle())
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        result = _run_goal(self.target, "--prompt", "x",
                           mock_bindir=self.bindir,
                           extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        vendored = (self.target / ".claude" / "skills"
                    / "servo-quality-gate" / "gate.py")
        self.assertTrue(vendored.is_file(), msg=result.stderr)
        servo_gate = REPO_ROOT / "skills" / "quality-gate" / "gate.py"
        self.assertEqual(vendored.read_bytes(), servo_gate.read_bytes())
        # The vendored copy actually scored the oracle: a passing run.
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["terminal_reason"], "oracle_pass")


# ---------------------------------------------------------------------------
# AC2/AC3 — refuse-on-dirty-tree + --allow-dirty opt-out + non-git skip
# ---------------------------------------------------------------------------


class _DirtyTreeContract:
    """Shared AC2/AC3 contract, exercised against BOTH drivers (ADR-0008 V4).

    Concrete subclasses set `GOAL` and inherit `unittest.TestCase`. The target is
    a git repo with a committed baseline; tests dirty a tracked file (or not) and
    assert the refusal / bypass / skip behaviour.
    """

    GOAL = False

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-dirty-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())
        (self.target / "src.txt").write_text("baseline\n")
        self.bindir = tmp / "bin"
        self.bindir.mkdir(parents=True, exist_ok=True)
        if self.GOAL:
            _mock_claude_goal(self.bindir, _goal_stream_jsonl(
                assistant_text=GOAL_PASS_SENTINEL,
                result_event=_goal_result_event(subtype="success"),
            ))
        else:
            _mock_claude_constant(self.bindir, _claude_json_payload(),
                                  tmp / "counter.txt")
        _git_init(self.target)
        _git_commit_all(self.target)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, *extra):
        fn = _run_goal if self.GOAL else _run_loop
        return fn(self.target, "--prompt", "x", *extra,
                  mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})

    def _summary(self, result):
        return _stdout_json_lines(result.stdout)[-1]

    def test_refuses_dirty_tracked_file(self):
        (self.target / "src.txt").write_text("uncommitted edit\n")
        result = self._run()
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "dirty_tree")
        # AC2: the breadcrumb names the dirty path.
        self.assertIn("src.txt", result.stderr)

    def test_allow_dirty_bypasses(self):
        (self.target / "src.txt").write_text("uncommitted edit\n")
        result = self._run("--allow-dirty")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotEqual(self._summary(result)["terminal_reason"], "dirty_tree")

    def test_clean_tree_runs(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotEqual(self._summary(result)["terminal_reason"], "dirty_tree")

    def test_untracked_files_do_not_trigger(self):
        # AC2 is scoped to "uncommitted changes to tracked files"; a stray
        # untracked file (incl. servo's own .servo/ + vendored gate artifacts) is
        # not a tracked-file change and must not false-refuse.
        (self.target / "scratch.tmp").write_text("untracked\n")
        result = self._run()
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotEqual(self._summary(result)["terminal_reason"], "dirty_tree")


class DirtyTreeLoopTests(_DirtyTreeContract, unittest.TestCase):
    GOAL = False


class DirtyTreeGoalTests(_DirtyTreeContract, unittest.TestCase):
    GOAL = True


class DirtyTreeUnitTests(unittest.TestCase):
    """Direct unit coverage of the `_dirty_tree_paths` predicate (AC2/AC3)."""

    def setUp(self):
        self.m = _load_loop_module()
        self.tmpdir = tempfile.mkdtemp(prefix="servo-dirtyunit-")
        self.target = Path(self.tmpdir) / "demo"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_non_git_target_returns_none(self):
        (self.target / "a.txt").write_text("x")
        self.assertIsNone(self.m._dirty_tree_paths(self.target))

    def test_clean_repo_returns_none(self):
        (self.target / "a.txt").write_text("x")
        _git_init(self.target)
        _git_commit_all(self.target)
        self.assertIsNone(self.m._dirty_tree_paths(self.target))

    def test_modified_tracked_file_listed(self):
        (self.target / "a.txt").write_text("x")
        _git_init(self.target)
        _git_commit_all(self.target)
        (self.target / "a.txt").write_text("changed")
        dirty = self.m._dirty_tree_paths(self.target)
        self.assertIsNotNone(dirty)
        self.assertIn("a.txt", dirty)

    def test_untracked_only_returns_none(self):
        (self.target / "a.txt").write_text("x")
        _git_init(self.target)
        _git_commit_all(self.target)
        (self.target / "b.txt").write_text("new untracked")
        self.assertIsNone(self.m._dirty_tree_paths(self.target))


# ---------------------------------------------------------------------------
# AC4/AC5 — host-scope routing + --explain-routing
# ---------------------------------------------------------------------------


def _loop_mock_body() -> str:
    return "#!/usr/bin/env bash\ncat <<'__J__'\n" + _claude_json_payload() + "\n__J__\n"


def _goal_mock_body(*, assistant_text=GOAL_PASS_SENTINEL, subtype="success") -> str:
    jsonl = _goal_stream_jsonl(
        assistant_text=assistant_text,
        result_event=_goal_result_event(subtype=subtype),
    )
    return "#!/usr/bin/env bash\ncat <<'__J__'\n" + jsonl + "\n__J__\n"


def _run_raw(target, *extra, mock_bindir=None, extra_env=None):
    """Invoke loop.py with NO injected --driver (exercises the real default).

    Isolates HOME (user settings layer) and neutralises the managed-settings
    layer (`SERVO_MANAGED_SETTINGS_PATH=""`) so the routing audit is hermetic
    regardless of the host's real settings hierarchy. A test that wants a managed
    restriction overrides `SERVO_MANAGED_SETTINGS_PATH` via `extra_env`.

    Slice 023-02: defaults `SERVO_READINESS_GATE=0` (the readiness preflight's
    bypass seam) so pre-existing `--background` / `--emit-routine-prompt`
    surface tests are unaffected by the new gate. A test exercising the real
    readiness gate passes `extra_env={"SERVO_READINESS_GATE": "1"}` (or any
    non-bypass value) to re-enable it.
    """
    path = f"{mock_bindir}:{SYSTEM_PATH}" if mock_bindir else SYSTEM_PATH
    env = {**os.environ, "PATH": path, "HOME": _ISOLATED_HOME,
           "SERVO_MANAGED_SETTINGS_PATH": "", "SERVO_READINESS_GATE": "0"}
    if extra_env:
        env.update(extra_env)
    cmd = [sys.executable, str(LOOP), str(target), *extra]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


class RoutingUnitTests(unittest.TestCase):
    """Pure-logic coverage of the host-support probe + routing decision (AC4)."""

    def setUp(self):
        self.m = _load_loop_module()
        self.tmpdir = tempfile.mkdtemp(prefix="servo-route-")
        self.target = Path(self.tmpdir) / "demo"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # --- version parsing / goal availability ---
    def test_parse_version_variants(self):
        self.assertEqual(self.m._parse_claude_version("2.1.175 (Claude Code)"), (2, 1, 175))
        self.assertEqual(self.m._parse_claude_version("1.0.0-mock"), (1, 0, 0))
        self.assertIsNone(self.m._parse_claude_version("not-a-version"))
        self.assertIsNone(self.m._parse_claude_version(None))

    def test_goal_available_at_and_below_min_version(self):
        self.m._get_claude_version = lambda: "2.1.139"
        avail, _v, reason = self.m._goal_primitive_available()
        self.assertTrue(avail)
        self.assertIsNone(reason)
        self.m._get_claude_version = lambda: "2.1.138"
        avail, _v, reason = self.m._goal_primitive_available()
        self.assertFalse(avail)
        self.assertIn("predates", reason)

    def test_goal_unavailable_when_claude_absent(self):
        self.m._get_claude_version = lambda: None
        avail, _v, reason = self.m._goal_primitive_available()
        self.assertFalse(avail)
        self.assertIn("not found", reason)

    # --- settings-hierarchy audit ---
    def test_audit_disable_all_hooks_user_layer(self):
        from unittest import mock
        home = Path(self.tmpdir) / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".claude" / "settings.json").write_text(json.dumps({"disableAllHooks": True}))
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            audit = self.m._audit_hook_settings(self.target)
        self.assertFalse(audit["hooks_permitted"])
        self.assertEqual(audit["forcing_layer"], "user:disableAllHooks")

    def test_audit_allow_managed_hooks_only_binds_in_managed_tier(self):
        managed = Path(self.tmpdir) / "managed.json"
        managed.write_text(json.dumps({"allowManagedHooksOnly": True}))
        self.m._managed_settings_paths = lambda: [managed]
        from unittest import mock
        empty_home = Path(self.tmpdir) / "emptyhome"
        empty_home.mkdir()
        with mock.patch.dict(os.environ, {"HOME": str(empty_home)}):
            audit = self.m._audit_hook_settings(self.target)
        self.assertFalse(audit["hooks_permitted"])
        self.assertEqual(audit["forcing_layer"], "managed:allowManagedHooksOnly")

    def test_audit_allow_managed_hooks_only_inert_in_project_layer(self):
        # allowManagedHooksOnly only binds in the managed tier (per the docs).
        (self.target / ".claude").mkdir(parents=True)
        (self.target / ".claude" / "settings.local.json").write_text(
            json.dumps({"allowManagedHooksOnly": True}))
        from unittest import mock
        empty_home = Path(self.tmpdir) / "emptyhome2"
        empty_home.mkdir()
        self.m._managed_settings_paths = lambda: [Path(self.tmpdir) / "absent.json"]
        with mock.patch.dict(os.environ, {"HOME": str(empty_home)}):
            audit = self.m._audit_hook_settings(self.target)
        self.assertTrue(audit["hooks_permitted"])

    # --- decision logic (audit + probe stubbed) ---
    def _stub(self, *, hooks_permitted, goal_available, forcing_layer=None):
        self.m._audit_hook_settings = lambda target: {
            "hooks_permitted": hooks_permitted, "forcing_layer": forcing_layer,
            "layers": [],
        }
        reason = None if goal_available else "claude too old"
        self.m._goal_primitive_available = lambda: (goal_available, "2.1.175", reason)

    def test_auto_picks_goal_when_eligible(self):
        self._stub(hooks_permitted=True, goal_available=True)
        v = self.m._decide_route(self.target, self.m.DRIVER_AUTO)
        self.assertEqual(v["chosen_driver"], "goal")
        self.assertFalse(v["refused"])

    def test_auto_downgrades_to_loop_when_hooks_restricted(self):
        self._stub(hooks_permitted=False, goal_available=True,
                   forcing_layer="project:disableAllHooks")
        v = self.m._decide_route(self.target, self.m.DRIVER_AUTO)
        self.assertEqual(v["chosen_driver"], "loop")
        self.assertFalse(v["refused"])
        self.assertIn("hooks restricted", v["ineligible_reason"])

    def test_auto_downgrades_to_loop_when_goal_unavailable(self):
        self._stub(hooks_permitted=True, goal_available=False)
        v = self.m._decide_route(self.target, self.m.DRIVER_AUTO)
        self.assertEqual(v["chosen_driver"], "loop")
        self.assertFalse(v["refused"])

    def test_explicit_goal_refused_when_ineligible(self):
        self._stub(hooks_permitted=False, goal_available=True,
                   forcing_layer="managed:allowManagedHooksOnly")
        v = self.m._decide_route(self.target, self.m.DRIVER_GOAL)
        self.assertTrue(v["refused"])
        self.assertEqual(v["chosen_driver"], "goal")

    def test_explicit_goal_admitted_when_eligible(self):
        self._stub(hooks_permitted=True, goal_available=True)
        v = self.m._decide_route(self.target, self.m.DRIVER_GOAL)
        self.assertFalse(v["refused"])

    def test_explicit_loop_never_refused(self):
        self._stub(hooks_permitted=False, goal_available=False,
                   forcing_layer="user:disableAllHooks")
        v = self.m._decide_route(self.target, self.m.DRIVER_LOOP)
        self.assertEqual(v["chosen_driver"], "loop")
        self.assertFalse(v["refused"])


class HostScopeRoutingDispatchTests(unittest.TestCase):
    """End-to-end wiring of the routing verdict into the dispatch (AC4)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-routedisp-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())
        self.bindir = tmp / "bin"
        self.bindir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _restrict_hooks(self):
        (self.target / ".claude").mkdir(parents=True, exist_ok=True)
        (self.target / ".claude" / "settings.json").write_text(
            json.dumps({"disableAllHooks": True}))

    def _summary(self, result):
        return _stdout_json_lines(result.stdout)[-1]

    def test_auto_routes_to_goal_on_eligible_host(self):
        _make_mock_claude(self.bindir, _goal_mock_body(), version="2.1.175")
        result = _run_raw(self.target, "--driver", "auto", "--prompt", "x",
                          mock_bindir=self.bindir,
                          extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["driver"], "goal")

    def test_auto_downgrades_to_loop_when_hooks_restricted(self):
        self._restrict_hooks()
        _make_mock_claude(self.bindir, _loop_mock_body(), version="2.1.175")
        result = _run_raw(self.target, "--driver", "auto", "--prompt", "x",
                          "--plateau-window", "0",
                          mock_bindir=self.bindir,
                          extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        # Loop-shaped summary (no `driver` key; has iterations_completed).
        summary = self._summary(result)
        self.assertNotIn("driver", summary)
        self.assertIn("iterations_completed", summary)
        self.assertIn("auto-routing to --driver loop", result.stderr)
        self.assertIn("hooks restricted", result.stderr)

    def test_auto_downgrades_to_loop_when_claude_too_old(self):
        _make_mock_claude(self.bindir, _loop_mock_body(), version="1.0.0")
        result = _run_raw(self.target, "--driver", "auto", "--prompt", "x",
                          "--plateau-window", "0",
                          mock_bindir=self.bindir,
                          extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("iterations_completed", self._summary(result))
        self.assertIn("auto-routing to --driver loop", result.stderr)
        self.assertIn("predates", result.stderr)

    def test_explicit_goal_refuses_when_hooks_restricted(self):
        self._restrict_hooks()
        _make_mock_claude(self.bindir, _goal_mock_body(), version="2.1.175")
        result = _run_raw(self.target, "--driver", "goal", "--prompt", "x",
                          mock_bindir=self.bindir,
                          extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "goal_unavailable")
        self.assertIn("project:disableAllHooks", result.stderr)

    def test_explicit_goal_refuses_when_claude_too_old(self):
        _make_mock_claude(self.bindir, _goal_mock_body(), version="1.0.0")
        result = _run_raw(self.target, "--driver", "goal", "--prompt", "x",
                          mock_bindir=self.bindir,
                          extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "goal_unavailable")
        self.assertIn("predates", result.stderr)

    def test_explicit_goal_refuses_when_managed_allow_managed_hooks_only(self):
        # End-to-end exercise of the managed-tier audit via the test seam.
        managed = Path(self.tmpdir) / "managed.json"
        managed.write_text(json.dumps({"allowManagedHooksOnly": True}))
        _make_mock_claude(self.bindir, _goal_mock_body(), version="2.1.175")
        result = _run_raw(self.target, "--driver", "goal", "--prompt", "x",
                          mock_bindir=self.bindir,
                          extra_env={"SERVO_CLAUDE_TIMEOUT": "20",
                                     "SERVO_MANAGED_SETTINGS_PATH": str(managed)})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "goal_unavailable")
        self.assertIn("managed:allowManagedHooksOnly", result.stderr)

    def test_explicit_loop_runs_loop_on_eligible_host(self):
        _make_mock_claude(self.bindir, _loop_mock_body(), version="2.1.175")
        result = _run_raw(self.target, "--driver", "loop", "--prompt", "x",
                          "--plateau-window", "0",
                          mock_bindir=self.bindir,
                          extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("iterations_completed", self._summary(result))


class ExplainRoutingTests(unittest.TestCase):
    """`--explain-routing` prints the verdict + forcing layer, runs nothing (AC5)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-explain-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())
        self.bindir = tmp / "bin"
        self.bindir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_explain_eligible_host_chooses_goal(self):
        _make_mock_claude(self.bindir, _goal_mock_body(), version="2.1.175")
        result = _run_raw(self.target, "--explain-routing",
                          mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("chosen driver    : goal", result.stdout)
        self.assertIn("/goal eligible   : YES", result.stdout)
        # No run happened: no state file written.
        self.assertEqual(list(self.target.glob(".servo/runs/*/state.json")), [])

    def test_explain_names_forcing_layer(self):
        (self.target / ".claude").mkdir(parents=True, exist_ok=True)
        (self.target / ".claude" / "settings.local.json").write_text(
            json.dumps({"disableAllHooks": True}))
        _make_mock_claude(self.bindir, _goal_mock_body(), version="2.1.175")
        result = _run_raw(self.target, "--explain-routing", "--driver", "auto",
                          mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("chosen driver    : loop", result.stdout)
        self.assertIn("project-local:disableAllHooks", result.stdout)
        self.assertIn("← forces", result.stdout)

    def test_explain_explicit_goal_on_unsupported_warns(self):
        _make_mock_claude(self.bindir, _goal_mock_body(), version="1.0.0")
        result = _run_raw(self.target, "--explain-routing", "--driver", "goal",
                          mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("would refuse", result.stdout)
        self.assertIn("predates", result.stdout)

    def test_explain_needs_no_prompt(self):
        # --explain-routing is read-only and must not require --prompt.
        _make_mock_claude(self.bindir, _goal_mock_body(), version="2.1.175")
        result = _run_raw(self.target, "--explain-routing", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)


# ---------------------------------------------------------------------------
# AC6 — safe defaults (host-scope routing + dirty-tree refusal on by default)
# ---------------------------------------------------------------------------


class SafeDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-defaults-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())
        self.bindir = tmp / "bin"
        self.bindir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _summary(self, result):
        return _stdout_json_lines(result.stdout)[-1]

    def test_default_driver_is_auto_and_routes_to_goal(self):
        # No --driver: the default engages host-scope routing (AC6) and, on an
        # eligible host, picks the goal driver.
        _make_mock_claude(self.bindir, _goal_mock_body(), version="2.1.175")
        result = _run_raw(self.target, "--prompt", "x", mock_bindir=self.bindir,
                          extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["driver"], "goal")

    def test_dirty_tree_refusal_on_by_default(self):
        # No --allow-dirty: a dirty git tree refuses by default (fail-closed).
        (self.target / "src.txt").write_text("baseline\n")
        _git_init(self.target)
        _git_commit_all(self.target)
        (self.target / "src.txt").write_text("uncommitted\n")
        _make_mock_claude(self.bindir, _goal_mock_body(), version="2.1.175")
        result = _run_raw(self.target, "--prompt", "x", mock_bindir=self.bindir,
                          extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "dirty_tree")


class PlateauNoiseFloorTests(unittest.TestCase):
    """ADR-0005 clause 4 (δ): `_check_plateau`'s frozen noise floor lets a
    wobbling non-deterministic eval component neither fake progress (dodging a
    real plateau halt) nor fake a plateau (halting early).

    Verification obligation (ADR-0005 §Verification): sub-δ wobble still fires
    the plateau halt (no false progress), and a supra-δ gain does NOT fire it
    early (genuine progress resets the brake). These unit-test the predicate;
    PlateauNoiseFloorLoopTests drives the same obligation through the loop.
    """

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("loop", LOOP)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.check = module._check_plateau

    @staticmethod
    def _hist(*composites):
        return [{"composite": c} for c in composites]

    def test_default_floor_zero_is_legacy_strict(self):
        # δ defaults to 0.0 → exact prior behaviour (equality is non-improving).
        self.assertTrue(self.check(self._hist(0.3, 0.3, 0.3, 0.3), 3))
        self.assertFalse(self.check(self._hist(0.3, 0.4, 0.5, 0.6), 3))

    def test_sub_delta_wobble_still_plateaus(self):
        # Composite wobbles ±0.01 around 0.80 with δ=0.05 → reads as flat → halt.
        self.assertTrue(self.check(self._hist(0.80, 0.81, 0.79, 0.805), 3, 0.05))

    def test_sub_delta_climb_does_not_count_as_improvement(self):
        # A monotone but sub-δ climb (overall_max 0.83 ≤ earlier_max 0.80 + δ
        # 0.05) is still a plateau — no false progress.
        self.assertTrue(self.check(self._hist(0.80, 0.81, 0.82, 0.83), 3, 0.05))

    def test_supra_delta_gain_resets_plateau_no_early_halt(self):
        # A genuine jump beyond δ (0.80 → 0.90 > earlier_max + 0.05) is real
        # improvement → not a plateau; the brake must not fire early.
        self.assertFalse(self.check(self._hist(0.80, 0.79, 0.81, 0.90), 3, 0.05))

    def test_gain_exactly_at_floor_is_non_improving(self):
        # Boundary: a gain of exactly δ does not exceed earlier_max + δ → plateau
        # (the `≤` direction, consistent with AC3's equality-is-non-improving).
        self.assertTrue(self.check(self._hist(0.80, 0.80, 0.80, 0.85), 3, 0.05))


class PlateauNoiseFloorLoopTests(unittest.TestCase):
    """End-to-end wiring for `--plateau-noise-floor` δ (ADR-0005 clause 4).

    PlateauNoiseFloorTests above unit-test the `_check_plateau` predicate; these
    drive the whole loop so the flag's plumbing — CLI parse + validation,
    persistence into run state, and the threading into the plateau call site —
    is actually exercised, discharging the ADR §Verification obligation against
    real loop behaviour rather than the predicate in isolation.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-loop-noise-floor-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # Strictly-increasing sub-δ climb: every iteration sets a new max, but the
    # whole span (0.30 → 0.309) is far under δ=0.05. Used by the with/without
    # pair below to isolate the floor's effect.
    _SUB_DELTA_CLIMB = [
        0.30, 0.301, 0.302, 0.303, 0.304,
        0.305, 0.306, 0.307, 0.308, 0.309,
    ]

    def test_sub_delta_climb_halts_with_noise_floor(self):
        # With δ=0.05 the tiny gains read as flat, so the plateau halt fires at
        # iter 4: history=[0.30,0.301,0.302,0.303]; earlier_max (excl. last 3)
        # =0.30; overall=0.303 ≤ 0.30+0.05. No false progress.
        _make_oracle(
            self.target, _composite_progression_oracle(self._SUB_DELTA_CLIMB),
        )
        _mock_claude_with_verdict(self.bindir, self.counter)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "10",
            "--plateau-window", "3", "--plateau-noise-floor", "0.05",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 4)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")
        self.assertEqual(summary["plateau_noise_floor"], 0.05)

    def test_sub_delta_climb_runs_on_without_noise_floor(self):
        # Same climb, default floor (0.0): each tiny gain is a strict
        # improvement, so plateau never fires and the loop runs to the cap.
        # The control proving the floor — not some other change — is what halts
        # the run above, i.e. the flag is wired through end-to-end.
        _make_oracle(
            self.target, _composite_progression_oracle(self._SUB_DELTA_CLIMB),
        )
        _mock_claude_with_verdict(self.bindir, self.counter)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "5",
            "--plateau-window", "3",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 5)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertEqual(summary["plateau_noise_floor"], 0.0)

    def test_supra_delta_gain_does_not_halt_early(self):
        # A genuine >δ jump (0.30→0.40) resets the brake. With δ=0.05 the jump
        # at iter 4 keeps the loop running past where a flat run would halt; it
        # only halts once the 0.40 level itself plateaus, at iter 7
        # (history=[0.30,0.31,0.31,0.40,0.40,0.40,0.40]; earlier_max excl. last
        # 3 = 0.40; overall 0.40 ≤ 0.40+0.05). Asserting iter 7 (not 4) is the
        # "does not fire early" half of the ADR obligation.
        _make_oracle(
            self.target,
            _composite_progression_oracle(
                [0.30, 0.31, 0.31, 0.40, 0.40, 0.40, 0.40],
            ),
        )
        _mock_claude_with_verdict(self.bindir, self.counter)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "10",
            "--plateau-window", "3", "--plateau-noise-floor", "0.05",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(int(self.counter.read_text().strip()), 7)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")

    def test_negative_noise_floor_rejected(self):
        # Mirrors the --cost-ceiling / --plateau-window validation: a negative
        # floor is meaningless; argparse rejects it (rc=2) before any run.
        _mock_claude_with_verdict(self.bindir, self.counter)
        result = _run_loop(
            self.target, "--prompt", "x",
            "--plateau-noise-floor", "-0.1",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--plateau-noise-floor must be >= 0", result.stderr)
        self.assertFalse(self.counter.exists())


# ===========================================================================
# Slice 003-08 — AC1: `--background` detached run mode
# ===========================================================================


def _await_terminal_state(target: Path, timeout: float = 30.0) -> dict:
    """Poll the single detached run's state.json until it carries a terminal_reason.

    A poll-until-condition (NOT a fixed sleep): the parent seeds state.json with
    `terminal_reason=None`, the detached child overwrites it as it runs, and the
    child's finalize writes the real terminal_reason. Bounded by `timeout` so a
    wedged child fails loudly instead of hanging.
    """
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        states = list(target.glob(".servo/runs/*/state.json"))
        if states:
            try:
                data = json.loads(states[0].read_text())
            except (json.JSONDecodeError, OSError):
                data = {}
            if data.get("terminal_reason"):
                return data
        time.sleep(0.1)
    raise AssertionError(
        f"detached run under {target} did not reach a terminal_reason within {timeout}s"
    )


class BackgroundArgvUnitTests(unittest.TestCase):
    """Pure helpers behind `--background`: child argv + the detach summary shape."""

    def setUp(self):
        self.m = _load_loop_module()

    def test_child_argv_core_shape(self):
        argv = self.m._build_detached_child_argv(
            Path("/tmp/t"), "RID", prompt="do it",
            max_iterations=None, cost_ceiling=None,
        )
        # Re-execs THIS file as the goal driver, into the parent's run-id, with
        # --allow-dirty (the parent already cleared the tree before detaching).
        self.assertEqual(argv[0], sys.executable)
        self.assertEqual(argv[1], str(self.m._LOOP_PY))
        self.assertEqual(argv[2], "/tmp/t")
        self.assertEqual(argv[argv.index("--driver") + 1], "goal")
        self.assertIn("--allow-dirty", argv)
        self.assertEqual(argv[argv.index("--_detached-run-id") + 1], "RID")
        self.assertEqual(argv[argv.index("--prompt") + 1], "do it")
        # Caps omitted when unset → the child applies the parent's computed defaults.
        self.assertNotIn("--max-iterations", argv)
        self.assertNotIn("--cost-ceiling", argv)

    def test_child_argv_forwards_caps_when_set(self):
        argv = self.m._build_detached_child_argv(
            Path("/tmp/t"), "RID", prompt="p", max_iterations=4, cost_ceiling=0.5,
        )
        self.assertEqual(argv[argv.index("--max-iterations") + 1], "4")
        self.assertEqual(argv[argv.index("--cost-ceiling") + 1], "0.5")

    def test_detach_summary_shape(self):
        s = self.m._detach_summary(
            run_id="RID", pid=4321, state_path=Path("/t/state.json"),
            log_path=Path("/t/bg.log"), cost_ceiling=2.0, max_turns=5,
        )
        self.assertTrue(s["detached"])
        self.assertEqual(s["terminal_reason"], self.m.REASON_DETACHED)
        self.assertEqual(s["driver"], "goal")
        self.assertEqual(s["run_id"], "RID")
        self.assertEqual(s["pid"], 4321)
        self.assertEqual(s["state_path"], "/t/state.json")
        self.assertEqual(s["log_path"], "/t/bg.log")


class BackgroundDispatchTests(_GoalTargetMixin, unittest.TestCase):
    """End-to-end `--background`: detach, return the run-id, child runs to verdict (AC1)."""

    def test_launches_detached_and_completes(self):
        self._setup_target(_passing_oracle())
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(assistant_text=GOAL_PASS_SENTINEL))
        result = _run_raw(
            self.target, "--background", "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "30"},
        )
        # The parent returns immediately with the detach summary (run continues
        # in the child).
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = self._summary(result)
        self.assertTrue(summary["detached"])
        self.assertEqual(summary["terminal_reason"], "detached")
        self.assertIsInstance(summary["pid"], int)
        run_id = summary["run_id"]
        self.assertTrue(run_id)
        # The detached child runs the real goal loop to an authoritative verdict.
        state = _await_terminal_state(self.target)
        self.assertTrue(state["detached"])
        self.assertEqual(state["terminal_reason"], "oracle_pass")
        self.assertEqual(state["run_id"], run_id)
        # Child output went to the run-dir log, not the parent's stdout.
        self.assertTrue(
            (self.target / ".servo" / "runs" / run_id / "background.log").is_file()
        )

    def test_refuses_on_dirty_tree_before_detaching(self):
        # AC4: a scheduled rerun must start from a clean baseline — the dirty-tree
        # brake runs BEFORE any detach, so no child is spawned against dirty state.
        self._setup_target(_passing_oracle())
        (self.target / "tracked.txt").write_text("baseline\n")
        _git_init(self.target)
        _git_commit_all(self.target)
        (self.target / "tracked.txt").write_text("uncommitted\n")
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(assistant_text=GOAL_PASS_SENTINEL))
        result = _run_raw(
            self.target, "--background", "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "30"},
        )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "dirty_tree")
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])  # no detach

    def test_refuses_when_target_not_scaffolded(self):
        # Preflight refuses synchronously (visible to the user), not buried in the
        # detached child's log.
        self.tmpdir = tempfile.mkdtemp(prefix="servo-bg-")
        self.target = Path(self.tmpdir) / "bare"
        self.target.mkdir()
        self.bindir = Path(self.tmpdir) / "bin"
        self.bindir.mkdir()
        _make_mock_claude(self.bindir, _goal_mock_body(), version="2.1.175")
        result = _run_raw(
            self.target, "--background", "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "30"},
        )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "manifest_missing")

    def test_refuses_on_unsupported_host(self):
        # --background needs the goal driver; an old claude can't run /goal, so it
        # refuses rather than silently downgrading to a non-detachable loop run.
        self._setup_target(_passing_oracle())
        _make_mock_claude(self.bindir, _goal_mock_body(), version="1.0.0")
        result = _run_raw(
            self.target, "--background", "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "30"},
        )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "goal_unavailable")
        self.assertIn("--background needs the goal driver", result.stderr)


class BackgroundFlagConflictTests(unittest.TestCase):
    """`--background`'s argparse-level guards (no run; rc=2 straight from argparse)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-bgflag-")
        self.target = Path(self.tmpdir) / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_background_with_loop_driver_rejected(self):
        result = _run_raw(self.target, "--background", "--driver", "loop", "--prompt", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--background requires the goal driver", result.stderr)

    def test_background_with_resume_rejected(self):
        result = _run_raw(self.target, "--background", "--resume", "RID")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--background does not support --resume", result.stderr)


# ===========================================================================
# Slice 003-08 — AC2/AC3: `--emit-routine-prompt` (Routine-ready target)
# ===========================================================================


class EmitRoutinePromptTests(_GoalTargetMixin, unittest.TestCase):
    """`--emit-routine-prompt` vendors gate.py + prints the paste-ready /goal prompt."""

    def test_emits_portable_routine_prompt_and_vendors_gate(self):
        self._setup_target(_passing_oracle())
        result = _run_raw(self.target, "--emit-routine-prompt", "--prompt", "fix the tests")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        out = result.stdout
        # The /goal loop-body shape (AC2): a /goal condition that fact-checks the
        # sentinel, the seed task, and a per-turn gate run.
        self.assertIn("/goal", out)
        self.assertIn("SERVO_ORACLE_VERDICT", out)
        self.assertIn("fix the tests", out)
        # PORTABLE gate command — relative vendored path + bare `python3` — because
        # the Routine runs in a cloud clone, not on this host.
        self.assertIn("python3 .claude/skills/servo-quality-gate/gate.py . --json", out)
        self.assertNotIn(sys.executable, out)  # no absolute local interpreter leaks
        # AC3: states gate.py is the authority + the meta-judge is moot in a Routine.
        self.assertIn("authority", out.lower())
        self.assertIn("meta-judge", out.lower())
        # The target is now Routine-ready: the clone-portable gate.py is vendored.
        self.assertTrue(
            (self.target / ".claude" / "skills" / "servo-quality-gate" / "gate.py").is_file()
        )
        # Emit runs nothing — no run dir created.
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])

    def test_emitted_prompt_cannot_self_satisfy(self):
        # The emitted prompt (and any echo of it) must not trip the strict pass
        # predicate — bare cue + placeholders only (the AC2 bare-substring guard).
        self._setup_target(_passing_oracle())
        result = _run_raw(self.target, "--emit-routine-prompt", "--prompt", "do the thing")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertFalse(_load_loop_module()._scan_pass_sentinel(result.stdout))

    def test_refuses_when_target_not_scaffolded(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-emit-")
        self.target = Path(self.tmpdir) / "bare"
        self.target.mkdir()
        self.bindir = Path(self.tmpdir) / "bin"
        self.bindir.mkdir()
        result = _run_raw(self.target, "--emit-routine-prompt", "--prompt", "x")
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertIn("install.json not found", result.stderr)

    def test_requires_prompt(self):
        self._setup_target(_passing_oracle())
        result = _run_raw(self.target, "--emit-routine-prompt")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--prompt is required", result.stderr)


# ============================================================================
# Slice 016-02 — run-consume: loop.py reads budget + driver from a plan.json
#
# Test classes map 1:1 to the slice's acceptance criteria:
#   AC1 → PlanConsumeDefaultsTests      (plan supplies budget + driver defaults)
#   AC2 → PlanPrecedenceTests           (explicit flag > plan > loop.py default)
#   AC3 → PlanDriverAwareBudgetTests    (goal-driver carve-out; no stray warning)
#   AC4 → PlanPromptStillRequiredTests  (--prompt still required; no prompt_ref)
#   AC5 → NoPlanUnchangedTests          (no --plan ⇒ byte-for-byte today)
#   AC6 → PlanReadContractTests         (missing / malformed / schema mismatch)
#   AC7 → PlanHumanEditedDeferredTests  (provenance: human_edited ⇒ clamp=016-03)
#   AC8 → PlanResumeExclusiveTests      (--plan + --resume mutually exclusive)
# ============================================================================


def _compiled_plan(
    *,
    max_iterations=5,
    cost_ceiling_usd=2.0,
    context_fill_threshold=0.75,
    plateau_window=3,
    driver="loop",
    provenance="compiled",
    schema_version=1,
    spec_id="016-execution-planner",
) -> dict:
    """A minimal ADR-0016 `plan.json` dict (built inline; the producer is NOT called).

    Only the fields 016-02 consumes (`budget` + `driver`) are load-bearing;
    the reference fields (`oracle`, `suitability_ref`, etc.) are present for
    shape fidelity but are inert to the consumer this slice ships.
    """
    return {
        "schema_version": schema_version,
        "spec_id": spec_id,
        "compiled_at": "2026-07-02T00:00:00+00:00",
        "suitability_ref": f".servo/suitability/{spec_id}.json",
        "oracle": {"path": "oracle.sh", "components": ["tests"], "threshold": 0.5},
        "evaluation_model": None,
        "budget": {
            "max_iterations": max_iterations,
            "cost_ceiling_usd": cost_ceiling_usd,
            "context_fill_threshold": context_fill_threshold,
            "plateau_window": plateau_window,
        },
        "driver": driver,
        "prompt_ref": f"docs/specs/{spec_id}/spec.md",
        "provenance": provenance,
    }


def _write_plan(tmp: Path, plan: dict, *, name: str = "plan.json") -> Path:
    """Serialize `plan` to a JSON file under `tmp` and return its path."""
    path = tmp / name
    path.write_text(json.dumps(plan))
    return path


class PlanConsumeDefaultsTests(unittest.TestCase):
    """AC1 — a compiled plan supplies budget + driver as defaults for un-passed knobs.

    Under the loop driver all four budget knobs come from the plan when the
    caller passes none of them; the enforced budget is observable in state.json.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-plan-defaults-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_state_records_plan_budget_when_no_flags_passed(self):
        plan = _compiled_plan(
            max_iterations=2, cost_ceiling_usd=1.25,
            context_fill_threshold=0.5, plateau_window=4, driver="loop",
        )
        plan_path = _write_plan(self.tmp, plan)
        # No budget flags, no --driver, no --plateau-window: everything from the plan.
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["max_iterations"], 2)
        self.assertAlmostEqual(state["cost_ceiling_usd"], 1.25, places=6)
        self.assertAlmostEqual(state["context_fill_threshold"], 0.5, places=6)
        self.assertEqual(state["plateau_window"], 4)

    def test_plan_max_iterations_bounds_the_run(self):
        # A plan max_iterations of 2 halts the loop at 2 iterations (observable
        # via oracle_score_history length) with no CLI --max-iterations.
        plan = _compiled_plan(max_iterations=2, plateau_window=0, driver="loop")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["iteration_count"], 2)


class PlanPrecedenceTests(unittest.TestCase):
    """AC2 — precedence: explicit CLI flag > plan value > loop.py default."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-plan-precedence-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_explicit_flag_overrides_plan(self):
        plan = _compiled_plan(max_iterations=2, cost_ceiling_usd=1.25, driver="loop")
        plan_path = _write_plan(self.tmp, plan)
        # Explicit --max-iterations 1 must win over the plan's 2.
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            "--max-iterations", "1", "--plateau-window", "0",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["max_iterations"], 1)
        # A knob the caller did NOT pass still takes the plan value.
        self.assertAlmostEqual(state["cost_ceiling_usd"], 1.25, places=6)

    def test_plan_overrides_default_for_unpassed_knob(self):
        # cost_ceiling not passed → plan's 1.25, not the built-in $2.00 default.
        plan = _compiled_plan(cost_ceiling_usd=1.25, driver="loop")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            "--max-iterations", "1", "--plateau-window", "0",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["cost_ceiling_usd"], 1.25, places=6)

    def test_explicit_driver_overrides_plan_driver(self):
        # Plan says goal; explicit --driver loop wins → a loop-mode summary
        # (no "driver" key, loop-only oracle_score_history field).
        plan = _compiled_plan(driver="goal")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            "--driver", "loop", "--max-iterations", "1", "--plateau-window", "0",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertNotIn("driver", summary)
        self.assertIn("oracle_score_history", summary)


class PlanDriverAwareBudgetTests(_GoalTargetMixin, unittest.TestCase):
    """AC3 — driver-aware budget: goal-driver carve-out for plan-sourced brakes.

    Under the goal driver (incl. driver:auto routed to goal) the loop-only
    brakes (context_fill_threshold, plateau_window) from the plan are dropped
    exactly as explicit flags are — and NO "stray brake" warning is emitted for
    plan-sourced values. max_iterations / cost_ceiling still apply under goal.
    Under the loop driver all four apply (covered by PlanConsumeDefaultsTests).
    """

    def setUp(self):
        self._setup_target(_passing_oracle())
        self.tmp = Path(self.tmpdir)

    def test_goal_driver_plan_max_iterations_and_ceiling_apply(self):
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="ran gate\n" + GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success", cost=0.1),
        ))
        plan = _compiled_plan(
            max_iterations=7, cost_ceiling_usd=3.5,
            context_fill_threshold=0.5, plateau_window=4, driver="goal",
        )
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = self._summary(result)
        self.assertEqual(summary["driver"], "goal")
        # max_iterations → outer --max-turns; cost_ceiling → --max-budget-usd cap.
        self.assertEqual(summary["max_turns"], 7)
        self.assertAlmostEqual(summary["cost_ceiling_usd"], 3.5, places=6)

    def test_goal_driver_does_not_warn_for_plan_sourced_brakes(self):
        # AC3 KEY: a plan carrying context_fill_threshold + plateau_window under
        # the goal driver must NOT trip the "loop-mode brake ... is ignored"
        # warning — those are plan defaults, not a user request.
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="ran gate\n" + GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        plan = _compiled_plan(
            context_fill_threshold=0.5, plateau_window=4, driver="goal",
        )
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("loop-mode brake", result.stderr)
        self.assertNotIn("--context-fill-threshold", result.stderr)
        self.assertNotIn("--plateau-window", result.stderr)

    def test_explicit_brake_still_warns_under_goal_with_plan(self):
        # A plan does not suppress the warning for an EXPLICITLY-passed brake:
        # the carve-out only spares plan-sourced values.
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="ran gate\n" + GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        plan = _compiled_plan(driver="goal")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            "--plateau-window", "5",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("--plateau-window", result.stderr)
        self.assertIn("ignored", result.stderr)

    def test_background_launch_forwards_plan_budget(self):
        # AC1 (blocker fix): --plan + --background on a goal-eligible host must
        # carry the plan's max_iterations + cost_ceiling into the DETACHED goal
        # launch — not silently fall back to the built-in defaults. The parent's
        # synchronous detach summary echoes the resolved caps (max_turns /
        # cost_ceiling_usd), so we assert against it without awaiting the child.
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="ran gate\n" + GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        plan = _compiled_plan(max_iterations=7, cost_ceiling_usd=3.5, driver="goal")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--background", "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "30"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = self._summary(result)
        self.assertTrue(summary["detached"])
        self.assertEqual(summary["terminal_reason"], "detached")
        # Plan budget forwarded, not the DEFAULT_* (5 / $2.00).
        self.assertEqual(summary["max_turns"], 7)
        self.assertAlmostEqual(summary["cost_ceiling_usd"], 3.5, places=6)

    def test_goal_unavailable_refusal_echoes_plan_budget_not_default(self):
        # Bug fix (016-02 deviation log #3, loop.py:3221-3224): the
        # goal_unavailable refusal summary must echo the plan-resolved budget
        # (already computed above the routing check), not args.*/DEFAULT_*,
        # when a plan supplies a driver that turns out to be unavailable.
        _make_mock_claude(self.bindir, _goal_mock_body(), version="1.0.0")
        plan = _compiled_plan(max_iterations=9, cost_ceiling_usd=4.25, driver="goal")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "goal_unavailable")
        self.assertEqual(summary["max_turns"], 9)
        self.assertAlmostEqual(summary["cost_ceiling_usd"], 4.25, places=6)


class PlanPromptStillRequiredTests(unittest.TestCase):
    """AC4 — --prompt stays required; 016-02 does NOT consume prompt_ref."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-plan-prompt-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_plan_without_prompt_still_refuses(self):
        plan = _compiled_plan(driver="loop")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path))
        self.assertEqual(result.returncode, 2)
        self.assertIn("--prompt is required", result.stderr)
        # No run started: no state.json written.
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])


class NoPlanUnchangedTests(unittest.TestCase):
    """AC5 — no --plan ⇒ byte-for-byte today's behavior (the load-bearing invariant)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-noplan-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_plan_uses_builtin_defaults(self):
        # No --plan, no budget brakes → the built-in DEFAULT_* constants, exactly
        # as a pre-016-02 invocation. (ceiling=$2.00, context-fill=0.75,
        # plateau_window=3.) Uses `_run_raw` with an explicit loop driver so no
        # test-harness --plateau-window 0 is injected — the default must surface.
        result = _run_raw(
            self.target, "--driver", "loop", "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["cost_ceiling_usd"], 2.0, places=6)
        self.assertAlmostEqual(state["context_fill_threshold"], 0.75, places=6)
        self.assertEqual(state["plateau_window"], 3)

    def test_no_plan_summary_shape_unchanged(self):
        # The summary line carries the same keys / values as a pre-slice run.
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertAlmostEqual(summary["cost_ceiling_usd"], 2.0, places=6)
        # No plan-read reason ever surfaces on the no-plan path.
        self.assertNotIn(summary["terminal_reason"],
                         {"plan_missing", "plan_malformed",
                          "plan_schema_mismatch", "plan_requires_clamp"})

    def test_no_plan_does_not_read_a_stray_plan_file(self):
        # A plan.json sitting in the target must be inert without --plan (loop.py
        # never derives a spec-id / plan path). Behavior stays today's default.
        _write_plan(Path(self.tmpdir), _compiled_plan(max_iterations=2))
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        # max_iterations came from the CLI flag (1), not the stray plan (2).
        self.assertEqual(state["max_iterations"], 1)


class PlanReadContractTests(unittest.TestCase):
    """AC6 — fail-closed plan-read: missing / malformed / schema-mismatch ⇒ rc2."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-plan-read-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _assert_refused(self, result, reason):
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], reason)
        # No run started: no state.json written.
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])

    def test_missing_plan_file_refuses(self):
        missing = self.tmp / "nope.json"
        result = _run_raw(self.target, "--plan", str(missing), "--prompt", "x")
        self._assert_refused(result, "plan_missing")

    def test_malformed_json_refuses(self):
        bad = self.tmp / "plan.json"
        bad.write_text("{ this is not json ]")
        result = _run_raw(self.target, "--plan", str(bad), "--prompt", "x")
        self._assert_refused(result, "plan_malformed")

    def test_non_object_json_refuses(self):
        # Valid JSON but not an object (e.g. a bare list) is malformed as a plan.
        bad = self.tmp / "plan.json"
        bad.write_text("[1, 2, 3]")
        result = _run_raw(self.target, "--plan", str(bad), "--prompt", "x")
        self._assert_refused(result, "plan_malformed")

    def test_schema_version_mismatch_refuses(self):
        plan = _compiled_plan(schema_version=2)
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "plan_schema_mismatch")

    def test_missing_schema_version_refuses(self):
        plan = _compiled_plan()
        del plan["schema_version"]
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "plan_schema_mismatch")


class PlanHumanEditedDeferredTests(unittest.TestCase):
    """AC7 (016-02) — unrecognized provenance still refuses (plan_requires_clamp).

    Slice 016-03 AC2 supersedes 016-02 AC7's blanket "any non-compiled
    provenance refuses" rule: `human_edited` is now accepted and consumable
    (see `PlanHumanEditedConsumableTests`); only a provenance value that is
    neither "compiled" nor "human_edited" still refuses here, unchanged.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-plan-human-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_unknown_provenance_refuses(self):
        # Anything other than "compiled"/"human_edited" is refused (fail-closed).
        plan = _compiled_plan(provenance="mystery")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "plan_requires_clamp")


class PlanResumeExclusiveTests(unittest.TestCase):
    """AC8 — --plan and --resume are mutually exclusive (parser.error, rc2)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-plan-resume-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_plan_plus_resume_is_a_parser_error(self):
        plan = _compiled_plan()
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path),
            "--resume", "20260101T000000-abcd",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--plan", result.stderr)
        self.assertIn("--resume", result.stderr)
        # A parser.error is caught before any plan-read refusal summary line.
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])


# ============================================================================
# Slice 016-03 (clamp-and-review, ADR-0016 amendment 2026-07-04)
# ============================================================================


class PlanClampTests(unittest.TestCase):
    """AC1 — clamp-never-disable for plan-sourced budget, driver-scoped (A6).

    `cost_ceiling_usd=0` is clamped up to DEFAULT_COST_CEILING_USD
    unconditionally (either driver). `context_fill_threshold=0` /
    `plateau_window=0` are clamped only on the loop-driver branch that
    actually forwards them to run_loop; under goal they are dropped exactly
    as 016-02 AC3 already specifies, with no clamp breadcrumb. A plan value
    that *raises* a knob above DEFAULT_* is honored as-is. An explicit CLI
    flag is never clamped.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-plan-clamp-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cost_ceiling_zero_clamped_under_loop_driver(self):
        plan = _compiled_plan(cost_ceiling_usd=0, plateau_window=0, driver="loop")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            "--max-iterations", "1",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["cost_ceiling_usd"], 2.0, places=6)
        self.assertIn("cost_ceiling_usd", result.stderr)
        self.assertIn("0", result.stderr)

    def test_context_fill_threshold_zero_clamped_under_loop_driver(self):
        plan = _compiled_plan(
            context_fill_threshold=0, plateau_window=0, driver="loop",
        )
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            "--max-iterations", "1",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["context_fill_threshold"], 0.75, places=6)
        self.assertIn("context_fill_threshold", result.stderr)

    def test_plateau_window_zero_clamped_under_loop_driver(self):
        plan = _compiled_plan(plateau_window=0, driver="loop")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            "--max-iterations", "1",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["plateau_window"], 3)
        self.assertIn("plateau_window", result.stderr)

    def test_cost_ceiling_zero_clamped_under_goal_driver_too(self):
        # A1/A6: cost_ceiling_usd's clamp is driver-independent.
        goal_tmp = tempfile.mkdtemp(prefix="servo-plan-clamp-goal-")
        tmp = Path(goal_tmp)
        target = tmp / "demo"
        target.mkdir()
        _make_manifest(target)
        _make_oracle(target, _passing_oracle())
        bindir = tmp / "bin"
        bindir.mkdir(parents=True, exist_ok=True)
        _mock_claude_goal(bindir, _goal_stream_jsonl(
            assistant_text="ran gate\n" + GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        try:
            plan = _compiled_plan(cost_ceiling_usd=0, driver="goal")
            plan_path = _write_plan(tmp, plan)
            result = _run_raw(
                target, "--plan", str(plan_path), "--prompt", "x",
                mock_bindir=bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            summary = _stdout_json_lines(result.stdout)[-1]
            self.assertAlmostEqual(summary["cost_ceiling_usd"], 2.0, places=6)
            self.assertIn("cost_ceiling_usd", result.stderr)
        finally:
            shutil.rmtree(goal_tmp, ignore_errors=True)

    def test_context_fill_and_plateau_zero_not_clamped_under_goal_driver(self):
        # A6: these two are dropped entirely under goal (016-02 AC3) — a
        # disable-sentinel is just one more dropped value, no clamp breadcrumb.
        tmp = Path(tempfile.mkdtemp(prefix="servo-plan-clamp-goal2-"))
        target = tmp / "demo"
        target.mkdir()
        _make_manifest(target)
        _make_oracle(target, _passing_oracle())
        bindir = tmp / "bin"
        bindir.mkdir(parents=True, exist_ok=True)
        _mock_claude_goal(bindir, _goal_stream_jsonl(
            assistant_text="ran gate\n" + GOAL_PASS_SENTINEL,
            result_event=_goal_result_event(subtype="success"),
        ))
        try:
            plan = _compiled_plan(
                context_fill_threshold=0, plateau_window=0, driver="goal",
            )
            plan_path = _write_plan(tmp, plan)
            result = _run_raw(
                target, "--plan", str(plan_path), "--prompt", "x",
                mock_bindir=bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertNotIn("context_fill_threshold", result.stderr)
            self.assertNotIn("plateau_window", result.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_max_iterations_never_clamped(self):
        # No disable sentinel exists for max_iterations; even a plan value
        # of 0 is out-of-range (AC3 refusal), not a clamp target. Here we
        # confirm a small positive value is honored unchanged (not bumped
        # to DEFAULT_MAX_ITERATIONS=5).
        plan = _compiled_plan(max_iterations=1, plateau_window=0, driver="loop")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["max_iterations"], 1)
        self.assertNotIn("max_iterations", result.stderr)

    def test_plan_value_raising_a_knob_is_honored_unchanged(self):
        # A1: no cap from above — a raised value passes through untouched.
        plan = _compiled_plan(
            cost_ceiling_usd=9.0, context_fill_threshold=0.99,
            plateau_window=10, driver="loop",
        )
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            "--max-iterations", "1",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["cost_ceiling_usd"], 9.0, places=6)
        self.assertAlmostEqual(state["context_fill_threshold"], 0.99, places=6)
        self.assertEqual(state["plateau_window"], 10)
        self.assertNotIn("clamp", result.stderr)

    def test_explicit_cli_cost_ceiling_zero_never_clamped(self):
        # A3: clamping applies to plan-sourced values only; an explicit
        # --cost-ceiling 0 still disables the brake exactly as today.
        plan = _compiled_plan(driver="loop")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            "--cost-ceiling", "0", "--max-iterations", "1",
            "--plateau-window", "0",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["cost_ceiling_usd"], 0.0, places=6)
        self.assertNotIn("clamp", result.stderr)


class PlanHumanEditedConsumableTests(unittest.TestCase):
    """AC2 — a `human_edited` plan is consumable (016-02 AC7 superseded).

    Rewrites `PlanHumanEditedDeferredTests.test_human_edited_plan_refuses_
    pending_clamp`: a human_edited plan now runs successfully, going through
    the same clamp (AC1) and validation (AC3) as a compiled plan.
    `test_unknown_provenance_refuses` (provenance "mystery") is retained
    unchanged in `PlanHumanEditedDeferredTests` above.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-plan-human-consume-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_human_edited_plan_runs_successfully(self):
        plan = _compiled_plan(
            provenance="human_edited", max_iterations=1, plateau_window=0,
            driver="loop",
        )
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["max_iterations"], 1)

    def test_human_edited_plan_goes_through_same_clamp_as_compiled(self):
        plan = _compiled_plan(
            provenance="human_edited", cost_ceiling_usd=0, max_iterations=1,
            plateau_window=0, driver="loop",
        )
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["cost_ceiling_usd"], 2.0, places=6)
        self.assertIn("cost_ceiling_usd", result.stderr)

    def test_human_edited_plan_goes_through_same_validation_as_compiled(self):
        plan = _compiled_plan(provenance="human_edited", max_iterations=-1)
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "plan_value_invalid")


class PlanValueValidationTests(unittest.TestCase):
    """AC3 — fail-closed plan-value validation precedes clamping.

    A plan-sourced budget value of the wrong type, or one that would fail
    the same range check as the equivalent CLI flag, refuses exit 2 with
    reason `plan_value_invalid`, naming the offending key. An invalid
    `driver` value refuses the same way rather than defaulting to auto.
    Validation runs before clamping — a `0` is a valid (clampable) value,
    not an invalid one.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-plan-validate-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _assert_refused(self, result, offending_key):
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "plan_value_invalid")
        self.assertIn(offending_key, result.stderr)
        # No run started: no state.json written.
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])

    def test_max_iterations_wrong_type_refuses(self):
        plan = _compiled_plan(max_iterations="five")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "max_iterations")

    def test_max_iterations_negative_refuses(self):
        plan = _compiled_plan(max_iterations=-1)
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "max_iterations")

    def test_cost_ceiling_wrong_type_refuses(self):
        plan = _compiled_plan(cost_ceiling_usd="free")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "cost_ceiling_usd")

    def test_cost_ceiling_negative_refuses(self):
        plan = _compiled_plan(cost_ceiling_usd=-1.0)
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "cost_ceiling_usd")

    def test_context_fill_threshold_wrong_type_refuses(self):
        plan = _compiled_plan(context_fill_threshold="high")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "context_fill_threshold")

    def test_context_fill_threshold_out_of_range_refuses(self):
        plan = _compiled_plan(context_fill_threshold=1.5)
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "context_fill_threshold")

    def test_context_fill_threshold_negative_refuses(self):
        plan = _compiled_plan(context_fill_threshold=-0.1)
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "context_fill_threshold")

    def test_plateau_window_wrong_type_refuses(self):
        plan = _compiled_plan(plateau_window="many")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "plateau_window")

    def test_plateau_window_negative_refuses(self):
        plan = _compiled_plan(plateau_window=-1)
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "plateau_window")

    def test_invalid_driver_string_refuses(self):
        plan = _compiled_plan(driver="rogue")
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(self.target, "--plan", str(plan_path), "--prompt", "x")
        self._assert_refused(result, "driver")

    def test_zero_is_valid_not_refused(self):
        # 0 is a valid (clampable) value, not an invalid one — validation
        # must not refuse the disable sentinel; AC1's clamp handles it.
        plan = _compiled_plan(
            cost_ceiling_usd=0, context_fill_threshold=0, plateau_window=0,
            driver="loop",
        )
        plan_path = _write_plan(self.tmp, plan)
        bindir = self.tmp / "bin"
        counter = self.tmp / "counter.txt"
        _mock_claude_session_per_iter(bindir, counter)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            "--max-iterations", "1",
            mock_bindir=bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class PlanClampNoOpTests(unittest.TestCase):
    """AC5 — no --plan, or a plan that never hits the disable sentinel on any
    knob (including one that *raises* a knob above default), is unaffected:
    behavior/state.json byte-for-byte identical to pre-016-03, no clamp
    breadcrumb. Extends `NoPlanUnchangedTests`.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-plan-clamp-noop-")
        tmp = Path(self.tmpdir)
        self.tmp = tmp
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_session_per_iter(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_plan_no_clamp_breadcrumb(self):
        result = _run_raw(
            self.target, "--driver", "loop", "--prompt", "x",
            "--max-iterations", "1", "--plateau-window", "0",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("clamp", result.stderr)

    def test_plan_with_no_disable_sentinel_is_a_noop(self):
        plan = _compiled_plan(
            max_iterations=2, cost_ceiling_usd=1.25,
            context_fill_threshold=0.5, plateau_window=4, driver="loop",
        )
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["max_iterations"], 2)
        self.assertAlmostEqual(state["cost_ceiling_usd"], 1.25, places=6)
        self.assertAlmostEqual(state["context_fill_threshold"], 0.5, places=6)
        self.assertEqual(state["plateau_window"], 4)
        self.assertNotIn("clamp", result.stderr)

    def test_plan_raising_a_knob_above_default_is_a_noop(self):
        plan = _compiled_plan(
            max_iterations=1, cost_ceiling_usd=9.0,
            context_fill_threshold=0.95, plateau_window=8, driver="loop",
        )
        plan_path = _write_plan(self.tmp, plan)
        result = _run_raw(
            self.target, "--plan", str(plan_path), "--prompt", "x",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertAlmostEqual(state["cost_ceiling_usd"], 9.0, places=6)
        self.assertAlmostEqual(state["context_fill_threshold"], 0.95, places=6)
        self.assertEqual(state["plateau_window"], 8)
        self.assertNotIn("clamp", result.stderr)


# ============================================================================
# Slice 023-02 — loop.py readiness preflight (ADR-0029)
#
# Test classes map 1:1 to the slice's acceptance criteria:
#   AC1 → ReadinessBackgroundGateTests
#   AC2 → ReadinessEmitRoutinePromptGateTests
#   AC3 → ReadinessHeartbeatExemptionTests
#   AC4 → ReadinessGatedSurfaceSetTests
#   AC5 → ReadinessGateBypassTests
# ============================================================================


def _load_readiness_module():
    """Import readiness.py (023-01) as an in-process module — TEST-only, so a
    test can seed a realistic artifact via `_goal_id` without loop.py ever
    doing the same (arch-review note, readiness.py:_goal_id: production
    loop.py subprocesses `check` rather than re-deriving this hash)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("readiness_mod_023_02", READINESS)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _seed_readiness_artifact(target: Path, prompt: str, *, approval_status: str) -> str:
    """Write a minimal, schema-valid readiness artifact for `prompt` directly to
    `<target>/.servo/readiness/<goal-id>.json`. Returns the goal-id.

    TEST-only shortcut (per the 023-02 brief): production loop.py never reads
    this path or derives the goal-id itself — it always subprocesses
    `readiness.py check`, which is exercised for real by every test below.
    """
    readiness_mod = _load_readiness_module()
    goal_id = readiness_mod._goal_id(prompt)
    out_dir = target / ".servo" / "readiness"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "schema_version": 1,
        "goal_id": goal_id,
        "verdict": "ready",
        "approval_status": approval_status,
        "approved_at": "2026-08-12T00:00:00Z" if approval_status == "approved" else None,
        "reasons": [{"code": "all_clear", "message": "test fixture"}],
        "checks": [],
        "safety_surface": [],
        "analyzed_at": "2026-08-12T00:00:00Z",
        "inputs": {},
    }
    (out_dir / f"{goal_id}.json").write_text(json.dumps(artifact))
    return goal_id


class ReadinessBackgroundGateTests(_GoalTargetMixin, unittest.TestCase):
    """AC1 — `--background` refuses to *start* without an approved readiness
    artifact, and proceeds once `approved`. Gate explicitly ENABLED via
    `extra_env` (the harness default bypasses it for pre-existing tests)."""

    def test_refuses_with_no_artifact(self):
        self._setup_target(_passing_oracle())
        result = _run_raw(
            self.target, "--background", "--prompt", "x",
            mock_bindir=self.bindir,
            extra_env={"SERVO_READINESS_GATE": "1", "SERVO_CLAUDE_TIMEOUT": "30"},
        )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "readiness_unapproved")
        # Refused BEFORE any detach — no run dir created.
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])

    def test_refuses_with_proposed_artifact(self):
        self._setup_target(_passing_oracle())
        _seed_readiness_artifact(self.target, "x", approval_status="proposed")
        result = _run_raw(
            self.target, "--background", "--prompt", "x",
            mock_bindir=self.bindir,
            extra_env={"SERVO_READINESS_GATE": "1", "SERVO_CLAUDE_TIMEOUT": "30"},
        )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "readiness_unapproved")
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])

    def test_proceeds_once_approved(self):
        self._setup_target(_passing_oracle())
        _seed_readiness_artifact(self.target, "x", approval_status="approved")
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(assistant_text=GOAL_PASS_SENTINEL))
        result = _run_raw(
            self.target, "--background", "--prompt", "x", "--max-iterations", "2",
            mock_bindir=self.bindir,
            extra_env={"SERVO_READINESS_GATE": "1", "SERVO_CLAUDE_TIMEOUT": "30"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = self._summary(result)
        self.assertTrue(summary["detached"])
        self.assertEqual(summary["terminal_reason"], "detached")
        # The detached child runs the real goal loop to an authoritative verdict.
        state = _await_terminal_state(self.target)
        self.assertEqual(state["terminal_reason"], "oracle_pass")

    def test_refuses_when_the_readiness_check_itself_fails(self):
        # Compliance follow-up: the fail-CLOSED `readiness_check_unavailable`
        # branch (rc != 0 and != 1 — env-error, spawn failure, or timeout) had
        # ZERO coverage; dropping it would let a broken readiness install fail
        # OPEN. Point --background at a target directory that does not exist:
        # readiness.py's own `check` verb refuses with a real rc=2
        # (`_require_target`) BEFORE any of loop.py's other preflight checks
        # run (this gate fires first) — a genuine end-to-end refusal through
        # `main()`, no monkeypatching required.
        #
        # `self.tmpdir` (not a local) so the base `_GoalTargetMixin.tearDown`
        # cleans it up — this test deliberately skips `_setup_target` since
        # the target must NOT exist.
        self.tmpdir = tempfile.mkdtemp(prefix="servo-readiness-unavailable-")
        missing_target = Path(self.tmpdir) / "does-not-exist"
        result = _run_raw(
            missing_target, "--background", "--prompt", "x",
            extra_env={"SERVO_READINESS_GATE": "1", "SERVO_CLAUDE_TIMEOUT": "30"},
        )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(
            self._summary(result)["terminal_reason"], "readiness_check_unavailable"
        )
        # The underlying readiness.py failure reason is folded into the
        # breadcrumb (robustness follow-up), not just the bare exit code.
        self.assertIn("target_missing", result.stderr)
        # Refused BEFORE any detach — no run dir created.
        self.assertEqual(list(missing_target.glob(".servo/runs/*")), [])


class ReadinessEmitRoutinePromptGateTests(_GoalTargetMixin, unittest.TestCase):
    """AC2 — `--emit-routine-prompt` refuses to *emit* without an approved
    readiness artifact, and emits once `approved`."""

    def test_refuses_with_no_artifact(self):
        self._setup_target(_passing_oracle())
        result = _run_raw(
            self.target, "--emit-routine-prompt", "--prompt", "fix the tests",
            extra_env={"SERVO_READINESS_GATE": "1"},
        )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "readiness_unapproved")
        self.assertNotIn("/goal", result.stdout)

    def test_refuses_with_proposed_artifact(self):
        self._setup_target(_passing_oracle())
        _seed_readiness_artifact(self.target, "fix the tests", approval_status="proposed")
        result = _run_raw(
            self.target, "--emit-routine-prompt", "--prompt", "fix the tests",
            extra_env={"SERVO_READINESS_GATE": "1"},
        )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(self._summary(result)["terminal_reason"], "readiness_unapproved")
        self.assertNotIn("/goal", result.stdout)

    def test_emits_once_approved(self):
        self._setup_target(_passing_oracle())
        _seed_readiness_artifact(self.target, "fix the tests", approval_status="approved")
        result = _run_raw(
            self.target, "--emit-routine-prompt", "--prompt", "fix the tests",
            extra_env={"SERVO_READINESS_GATE": "1"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("/goal", result.stdout)
        self.assertIn("fix the tests", result.stdout)

    def test_refuses_when_the_readiness_check_itself_fails(self):
        # Bonus parallel case (compliance follow-up primarily requires
        # --background; this exercises the same fail-closed branch for the
        # other gated surface). Same lever as the --background case: a
        # nonexistent target makes the real `readiness.py check` return rc=2.
        #
        # `self.tmpdir` (not a local) so the base `_GoalTargetMixin.tearDown`
        # cleans it up — this test deliberately skips `_setup_target` since
        # the target must NOT exist.
        self.tmpdir = tempfile.mkdtemp(prefix="servo-readiness-unavailable-emit-")
        missing_target = Path(self.tmpdir) / "does-not-exist"
        result = _run_raw(
            missing_target, "--emit-routine-prompt", "--prompt", "x",
            extra_env={"SERVO_READINESS_GATE": "1"},
        )
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        self.assertEqual(
            self._summary(result)["terminal_reason"], "readiness_check_unavailable"
        )
        self.assertIn("target_missing", result.stderr)
        self.assertNotIn("/goal", result.stdout)


class ReadinessHeartbeatExemptionTests(unittest.TestCase):
    """AC3 — loop-layer regression guard: a `loop.py --prompt` run setting
    NEITHER `--background` nor `--emit-routine-prompt` is not refused for
    missing readiness, even with the gate explicitly enabled and NO readiness
    artifact anywhere under the target. This is exactly the shape the
    heartbeat dispatches (`loop.py <worktree> --prompt`, synchronously)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-readiness-exempt-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())
        self.bindir = tmp / "bin"
        _mock_claude_constant(self.bindir, _claude_json_payload(), tmp / "counter.txt")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_prompt_only_run_not_refused_for_missing_readiness(self):
        result = _run_loop(
            self.target, "--prompt", "x",
            mock_bindir=self.bindir,
            extra_env={"SERVO_READINESS_GATE": "1"},
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertNotIn(
            summary["terminal_reason"],
            ("readiness_unapproved", "readiness_check_unavailable"),
        )
        # The exemption is by construction (no gated surface set) — the run
        # never even consults readiness, so no artifact is written either.
        self.assertEqual(list(self.target.glob(".servo/readiness/*")), [])


class ReadinessGatedSurfaceSetTests(unittest.TestCase):
    """AC4 — the gate is pinned to an explicit unattended-launch-surface set
    (frame-critique follow-up #1): a future third surface can't silently
    escape the gate without also updating `_READINESS_GATED_SURFACES`."""

    def test_pinned_surface_set(self):
        m = _load_loop_module()
        self.assertEqual(
            m._READINESS_GATED_SURFACES, ("--background", "--emit-routine-prompt")
        )

    def test_readiness_gated_surface_maps_flags_to_names(self):
        m = _load_loop_module()
        from argparse import Namespace
        self.assertEqual(
            m._readiness_gated_surface(
                Namespace(background=True, emit_routine_prompt=False)),
            "--background",
        )
        self.assertEqual(
            m._readiness_gated_surface(
                Namespace(background=False, emit_routine_prompt=True)),
            "--emit-routine-prompt",
        )
        self.assertIsNone(
            m._readiness_gated_surface(
                Namespace(background=False, emit_routine_prompt=False)),
        )


class ReadinessCheckDetailUnitTests(unittest.TestCase):
    """Robustness follow-up (compliance Medium / craft nit 3 / arch nit 2) —
    `_readiness_check_rc` returns `(rc, detail)`, not a bare rc: a
    `readiness_check_unavailable` refusal must name WHY, not just that it
    failed."""

    def test_missing_readiness_path_reports_a_nonempty_detail(self):
        # The interpreter itself spawns fine (sys.executable exists) but
        # errors reading the nonexistent script — a real, non-OSError
        # failure mode distinct from the spawn-failure case below, and one
        # that must still surface a detail instead of a bare "exited 2".
        m = _load_loop_module()
        rc, detail = m._readiness_check_rc(
            Path("/tmp"), "x", readiness_path=Path("/nonexistent/readiness.py"),
        )
        self.assertEqual(rc, 2)
        self.assertIn("readiness.py", detail)

    def test_spawn_failure_reports_a_failed_to_spawn_detail(self):
        from unittest import mock
        m = _load_loop_module()
        with mock.patch.object(
            m.subprocess, "run", side_effect=OSError("no such executable")
        ):
            rc, detail = m._readiness_check_rc(Path("/tmp"), "x")
        self.assertEqual(rc, 2)
        self.assertIn("failed to spawn", detail)

    def test_timeout_reports_a_timed_out_detail(self):
        from unittest import mock
        m = _load_loop_module()
        with mock.patch.object(
            m.subprocess, "run",
            side_effect=m.subprocess.TimeoutExpired(cmd="readiness.py", timeout=30),
        ):
            rc, detail = m._readiness_check_rc(Path("/tmp"), "x")
        self.assertEqual(rc, 2)
        self.assertIn("timed out", detail)

    def test_real_check_env_error_surfaces_its_own_reason(self):
        m = _load_loop_module()
        tmpdir = tempfile.mkdtemp(prefix="servo-readiness-detail-")
        try:
            missing_target = Path(tmpdir) / "nope"
            rc, detail = m._readiness_check_rc(missing_target, "x")
            self.assertEqual(rc, 2)
            self.assertIn("target_missing", detail)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_approved_check_reports_no_detail(self):
        # A clean rc=0 has nothing to report — `detail` stays empty so the
        # (never-emitted, since rc==0 skips both refusal branches) message
        # would carry no spurious suffix.
        m = _load_loop_module()
        tmpdir = tempfile.mkdtemp(prefix="servo-readiness-detail-clean-")
        try:
            target = Path(tmpdir)
            _seed_readiness_artifact(target, "x", approval_status="approved")
            rc, detail = m._readiness_check_rc(target, "x")
            self.assertEqual(rc, 0)
            self.assertEqual(detail, "")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class ReadinessGateBypassTests(unittest.TestCase):
    """AC5 — `SERVO_READINESS_GATE` bypass seam (`0`/`false`/`off`/`no`, any
    case, skips the gate; anything else — including unset — keeps it active)."""

    def test_bypass_values_skip_the_gate(self):
        m = _load_loop_module()
        from unittest import mock
        for value in ("0", "false", "off", "no", "FALSE", "Off", "NO", " 0 "):
            with mock.patch.dict(os.environ, {"SERVO_READINESS_GATE": value}):
                self.assertTrue(
                    m._readiness_gate_bypassed(), msg=f"expected bypass for {value!r}"
                )

    def test_non_bypass_values_keep_the_gate_active(self):
        m = _load_loop_module()
        from unittest import mock
        for value in ("1", "true", "on", "yes", "garbage"):
            with mock.patch.dict(os.environ, {"SERVO_READINESS_GATE": value}):
                self.assertFalse(
                    m._readiness_gate_bypassed(), msg=f"expected active for {value!r}"
                )

    def test_unset_keeps_the_gate_active(self):
        m = _load_loop_module()
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SERVO_READINESS_GATE", None)
            self.assertFalse(m._readiness_gate_bypassed())

    def test_bypass_env_var_skips_the_gate_end_to_end(self):
        tmpdir = tempfile.mkdtemp(prefix="servo-readiness-bypass-")
        tmp = Path(tmpdir)
        target = tmp / "demo"
        target.mkdir()
        _make_manifest(target)
        _make_oracle(target, _passing_oracle())
        try:
            # No readiness artifact anywhere, yet --emit-routine-prompt
            # succeeds because SERVO_READINESS_GATE=0 bypasses the preflight.
            result = _run_raw(
                target, "--emit-routine-prompt", "--prompt", "x",
                extra_env={"SERVO_READINESS_GATE": "0"},
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ============================================================================
# Slice 032-05 — execution-primitive-mapping (Copilot host mode, ADR-0038)
#
# The optional loop driver gains a `--host {claude,copilot}` mode. The loop's
# own Python per-iteration oracle gate is unchanged; only the per-iteration
# subprocess changes from `claude -p --output-format json` to
# `copilot -p <prompt> -s --allow-all-tools --agent <name> --output-format json
# --usage-output-file <f>`. Copilot's JSONL + usage-file are normalized into the
# SAME result-dict shape so every downstream consumer is untouched.
#
# Pure parse/normalize/build helpers are exercised as unit tests via an
# importlib load of loop.py (the hyphenated `agent-loop/` dir is not a package,
# so it cannot be `import`ed by name); end-to-end behavior is exercised via the
# subprocess harness with a mock `copilot` binary, matching the file's style.
# ============================================================================

import importlib.util as _ilu  # noqa: E402

_copilot_spec = _ilu.spec_from_file_location("servo_loop_for_copilot_tests", LOOP)
loop_mod = _ilu.module_from_spec(_copilot_spec)
_copilot_spec.loader.exec_module(loop_mod)


# Usage-file fixture built from the spike's recorded live shape (032-01):
# cost in premium-requests / nano-AIU (NOT USD), a native edit-signal
# (`codeChanges.filesModifiedCount`), and `tokenDetails`.
_COPILOT_USAGE_FIXTURE = {
    "totalPremiumRequestCost": 2,
    "totalUserRequests": 1,
    "totalNanoAiu": 123456,
    "tokenDetails": {"input": 1200, "cache_read": 300, "cache_write": 50, "output": 240},
    "totalApiDurationMs": 5432,
    "codeChanges": {
        "linesAdded": 12,
        "linesRemoved": 3,
        "filesModifiedCount": 2,
        "filesModified": ["a.py", "b.py"],
    },
    "modelMetrics": {"claude-sonnet-4.5": {"requests": {"count": 1}}},
}

# A terminal result-event text carrying a valid ```verdict``` block, so a test
# can prove the extracted result text still feeds the loop's verdict parser.
_COPILOT_VERDICT_TEXT = (
    "Made an edit to fix the bug.\n\n"
    "```verdict\nschema_version: 1\nstatus: in_progress\n```\n"
)


def _copilot_jsonl_fixture(result_text="ok", *, session_id=None):
    """JSONL event stream matching the spike shape: ephemeral events + a
    terminal non-ephemeral `result` event carrying the response text."""
    events = [
        {"type": "assistant_message", "data": {"text": "thinking"}, "id": "e1",
         "timestamp": "2026-09-18T00:00:00Z", "ephemeral": True},
        {"type": "tool_call", "data": {"name": "edit"}, "id": "e2",
         "timestamp": "2026-09-18T00:00:01Z", "parentId": "e1", "ephemeral": True},
    ]
    terminal = {"type": "result", "data": {"content": result_text}, "id": "e3",
                "parentId": "e2", "timestamp": "2026-09-18T00:00:02Z",
                "ephemeral": False}
    if session_id:
        terminal["data"]["session_id"] = session_id
    return "\n".join(json.dumps(e) for e in [*events, terminal]) + "\n"


def _mock_copilot(bindir, jsonl_payload, usage_payload, counter_file, args_log=None):
    """Write an executable mock `copilot` into `bindir` (PATH-injected).

    Emits `jsonl_payload` on stdout, copies `usage_payload` to whatever path
    follows `--usage-output-file` in its argv, increments `counter_file`, and
    (optionally) appends each invocation's argv to `args_log` using the same
    U+001F/U+001E delimiters as `_mock_claude_with_args_log` so `_read_args_log`
    parses it. A `--version` short-circuit keeps any version probe hermetic.
    """
    bindir.mkdir(parents=True, exist_ok=True)
    jsonl_file = bindir / "copilot_jsonl.txt"
    jsonl_file.write_text(jsonl_payload)
    usage_src = bindir / "copilot_usage_src.json"
    usage_src.write_text(usage_payload)
    log_cmd = ""
    if args_log is not None:
        log_cmd = (
            f'for a in "$@"; do printf "%s\\037" "$a" >> \'{args_log}\'; done\n'
            f'printf "\\036" >> \'{args_log}\'\n'
        )
    body = (
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "--version" ]; then echo "1.0.86-2"; exit 0; fi\n'
        f"counter_file='{counter_file}'\n"
        'if [ -f "$counter_file" ]; then n=$(cat "$counter_file"); else n=0; fi\n'
        "n=$((n + 1))\n"
        'echo "$n" > "$counter_file"\n'
        f"{log_cmd}"
        'usage_out=""\n'
        'prev=""\n'
        'for a in "$@"; do\n'
        '  if [ "$prev" = "--usage-output-file" ]; then usage_out="$a"; fi\n'
        '  prev="$a"\n'
        "done\n"
        f'if [ -n "$usage_out" ]; then cp \'{usage_src}\' "$usage_out"; fi\n'
        f"cat '{jsonl_file}'\n"
    )
    copilot = bindir / "copilot"
    copilot.write_text(body)
    _make_executable(copilot)
    return copilot


class CopilotUsageParseTests(unittest.TestCase):
    """AC2 — parse the `--usage-output-file` JSON for native cost + edit-signal."""

    def _parse(self, payload):
        d = tempfile.mkdtemp(prefix="servo-copilot-usage-")
        try:
            p = Path(d) / "usage.json"
            p.write_text(json.dumps(payload))
            return loop_mod._parse_copilot_usage(p)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_parses_cost_and_edit_signal(self):
        out = self._parse(_COPILOT_USAGE_FIXTURE)
        self.assertEqual(out["premium_request_cost"], 2)
        self.assertEqual(out["nano_aiu"], 123456)
        self.assertEqual(out["files_modified"], 2)
        self.assertEqual(out["token_details"]["input"], 1200)
        self.assertEqual(out["token_details"]["output"], 240)

    def test_zero_files_modified_is_the_no_edit_signal(self):
        payload = dict(_COPILOT_USAGE_FIXTURE)
        payload["codeChanges"] = {"filesModifiedCount": 0}
        out = self._parse(payload)
        self.assertEqual(out["files_modified"], 0)

    def test_missing_file_fails_closed_nano_none(self):
        # Spec 041-02 AC3: a missing usage file yields nano_aiu=None (the
        # fail-closed credit signal), never 0. Observability-only fields
        # (premium_request_cost / files_modified) stay 0.
        out = loop_mod._parse_copilot_usage(Path("/nonexistent/servo/usage.json"))
        self.assertEqual(out["premium_request_cost"], 0)
        self.assertIsNone(out["nano_aiu"])
        self.assertIsNone(out["ai_credits_status"])
        self.assertEqual(out["files_modified"], 0)


_EV_041 = REPO_ROOT / "docs" / "specs" / "041-host-aware-budget-unit" / "evidence"


class Copilot041UsageParseTests(unittest.TestCase):
    """Spec 041-02 AC3 — sharpened usage parse: exact nano, aiCreditsStatus,
    currentModel, and None (not 0) for a missing credit field."""

    def _parse(self, payload):
        d = tempfile.mkdtemp(prefix="servo-copilot-usage-")
        try:
            p = Path(d) / "usage.json"
            p.write_text(json.dumps(payload))
            return loop_mod._parse_copilot_usage(p)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_status_and_model_surfaced(self):
        out = self._parse({
            "totalNanoAiu": 5350600000, "aiCreditsStatus": "complete",
            "currentModel": "gpt-6.1-sol",
        })
        self.assertEqual(out["nano_aiu"], 5350600000)
        self.assertEqual(out["ai_credits_status"], "complete")
        self.assertEqual(out["current_model"], "gpt-6.1-sol")

    def test_missing_nano_is_none_not_zero(self):
        out = self._parse({"aiCreditsStatus": "unavailable"})
        self.assertIsNone(out["nano_aiu"])
        self.assertEqual(out["ai_credits_status"], "unavailable")

    def test_exact_nano_not_truncated(self):
        out = self._parse({"totalNanoAiu": 12893040000, "totalPremiumRequestCost": 1.5})
        self.assertEqual(out["nano_aiu"], 12893040000)

    def test_real_evidence_run_a(self):
        p = _EV_041 / "run-a-usage.json"
        self.assertTrue(p.exists(), p)
        out = loop_mod._parse_copilot_usage(p)
        self.assertEqual(out["nano_aiu"], 12893040000)
        self.assertEqual(out["ai_credits_status"], "complete")
        self.assertEqual(out["current_model"], "gpt-6.1-sol")


class CopilotCreditGateTests(unittest.TestCase):
    """Spec 041-02 AC3 — fail-closed per-iteration credit computation from the
    usage report + the OpenTelemetry span file, using 041-01's real evidence.
    All arithmetic is in exact nano-AIU integers."""

    def test_otel_sum_matches_usage_fresh(self):
        self.assertEqual(
            loop_mod._sum_otel_call_nano(_EV_041 / "run-a-otel.jsonl"), 12893040000)

    def test_missing_otel_returns_none(self):
        self.assertIsNone(loop_mod._sum_otel_call_nano(Path("/nonexistent/otel.jsonl")))

    def test_fresh_iteration_nano_ok(self):
        nano, err = loop_mod._copilot_iteration_nano(
            _EV_041 / "run-a-usage.json", _EV_041 / "run-a-otel.jsonl",
            resumed=False, prior_cumulative_nano=None)
        self.assertIsNone(err)
        self.assertEqual(nano, 12893040000)

    def test_resumed_delta_reconciles_against_otel(self):
        # Run B resumed Run A: usage totalNanoAiu is session-cumulative
        # (37,175,690,000); the invocation's own spend is the delta
        # (= 24,282,650,000), which equals Run B's per-invocation OTel sum.
        nano, err = loop_mod._copilot_iteration_nano(
            _EV_041 / "run-b-usage.json", _EV_041 / "run-b-otel.jsonl",
            resumed=True, prior_cumulative_nano=12893040000)
        self.assertIsNone(err)
        self.assertEqual(nano, 24282650000)

    def test_partial_status_fails_closed(self):
        d = tempfile.mkdtemp()
        try:
            u = Path(d) / "u.json"
            u.write_text(json.dumps(
                {"totalNanoAiu": 5000000000, "aiCreditsStatus": "partial"}))
            nano, err = loop_mod._copilot_iteration_nano(
                u, _EV_041 / "run-a-otel.jsonl", resumed=False,
                prior_cumulative_nano=None)
            self.assertIsNone(nano)
            self.assertEqual(err, loop_mod.REASON_CREDIT_USAGE_UNAVAILABLE)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_missing_otel_fails_closed(self):
        nano, err = loop_mod._copilot_iteration_nano(
            _EV_041 / "run-a-usage.json", Path("/nonexistent/otel.jsonl"),
            resumed=False, prior_cumulative_nano=None)
        self.assertIsNone(nano)
        self.assertEqual(err, loop_mod.REASON_CREDIT_USAGE_UNAVAILABLE)

    def test_otel_sum_mismatch_fails_closed(self):
        d = tempfile.mkdtemp()
        try:
            u = Path(d) / "u.json"
            u.write_text(json.dumps(
                {"totalNanoAiu": 999000000000, "aiCreditsStatus": "complete"}))
            nano, err = loop_mod._copilot_iteration_nano(
                u, _EV_041 / "run-a-otel.jsonl", resumed=False,
                prior_cumulative_nano=None)
            self.assertIsNone(nano)
            self.assertEqual(err, loop_mod.REASON_CREDIT_USAGE_UNAVAILABLE)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class CopilotJsonlParseTests(unittest.TestCase):
    """AC1 — parse the JSONL event stream: filter ephemeral, take terminal text."""

    def test_filters_ephemeral_and_extracts_terminal_text(self):
        terminal, text = loop_mod._parse_copilot_jsonl(
            _copilot_jsonl_fixture("hello world"))
        self.assertIsNotNone(terminal)
        self.assertNotEqual(terminal.get("ephemeral"), True)
        self.assertEqual(text, "hello world")

    def test_no_nonephemeral_event_returns_none(self):
        only_ephemeral = json.dumps(
            {"type": "x", "data": {}, "ephemeral": True}) + "\n"
        terminal, text = loop_mod._parse_copilot_jsonl(only_ephemeral)
        self.assertIsNone(terminal)
        self.assertEqual(text, "")

    def test_tolerates_noise_lines(self):
        noisy = "not json\n" + _copilot_jsonl_fixture("clean")
        terminal, text = loop_mod._parse_copilot_jsonl(noisy)
        self.assertEqual(text, "clean")

    def test_session_id_extracted_when_present(self):
        terminal, _ = loop_mod._parse_copilot_jsonl(
            _copilot_jsonl_fixture("x", session_id="sess-9"))
        self.assertEqual(loop_mod._extract_copilot_session_id(terminal), "sess-9")

    def test_session_id_empty_when_absent(self):
        terminal, _ = loop_mod._parse_copilot_jsonl(_copilot_jsonl_fixture("x"))
        self.assertEqual(loop_mod._extract_copilot_session_id(terminal), "")


class CopilotNormalizeTests(unittest.TestCase):
    """AC1/AC2 — the normalized dict carries every field downstream consumes."""

    def _normalized(self, result_text=_COPILOT_VERDICT_TEXT, session_id="sess-1"):
        d = tempfile.mkdtemp(prefix="servo-copilot-norm-")
        try:
            p = Path(d) / "usage.json"
            p.write_text(json.dumps(_COPILOT_USAGE_FIXTURE))
            usage = loop_mod._parse_copilot_usage(p)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        terminal, text = loop_mod._parse_copilot_jsonl(
            _copilot_jsonl_fixture(result_text))
        return loop_mod._normalize_copilot_result(terminal, text, session_id, usage)

    def test_claude_shaped_fields_present(self):
        norm = self._normalized()
        # The exact keys the loop body reads off `claude_data`.
        self.assertEqual(norm["session_id"], "sess-1")
        self.assertFalse(norm["is_error"])
        self.assertIn("result", norm)
        self.assertEqual(norm["usage"]["input_tokens"], 1200)
        self.assertEqual(norm["usage"]["cache_read_input_tokens"], 300)
        self.assertEqual(norm["usage"]["cache_creation_input_tokens"], 50)
        self.assertEqual(norm["usage"]["output_tokens"], 240)

    def test_no_usd_fabrication(self):
        # Cost-unit decision: copilot reports premium-requests / nano-AIU, not
        # USD. `total_cost_usd` MUST be 0.0 so the USD ceiling stays honest.
        norm = self._normalized()
        self.assertEqual(norm["total_cost_usd"], 0.0)

    def test_native_cost_and_edit_signal_surfaced(self):
        norm = self._normalized()
        self.assertEqual(norm["copilot_premium_request_cost"], 2)
        self.assertEqual(norm["copilot_nano_aiu"], 123456)
        self.assertEqual(norm["copilot_files_modified"], 2)

    def test_result_text_feeds_verdict_parser(self):
        # Proves the extracted result text is what downstream verdict parsing
        # reads — the load-bearing "downstream is unchanged" guarantee.
        norm = self._normalized()
        fields, err = loop_mod._parse_verdict_block(norm["result"])
        self.assertIsNone(err)
        self.assertEqual(fields["schema_version"], 1)
        self.assertEqual(fields["status"], "in_progress")


class CopilotBuildCmdTests(unittest.TestCase):
    """AC1 — the Copilot argv form; AC2 — `--max-ai-credits`; resume mapping."""

    def _cmd(self, **kw):
        base = dict(agent_name="runner", session_id=None,
                    usage_file=Path("/tmp/u.json"), max_ai_credits=None)
        base.update(kw)
        return loop_mod._build_copilot_cmd("do the task", **base)

    def test_argv_form(self):
        cmd = self._cmd()
        self.assertEqual(cmd[0], "copilot")
        # `-p` takes the prompt as its value (verified against copilot --help).
        self.assertIn("-p", cmd)
        self.assertEqual(cmd[cmd.index("-p") + 1], "do the task")
        self.assertIn("-s", cmd)
        self.assertIn("--allow-all-tools", cmd)
        self.assertEqual(cmd[cmd.index("--agent") + 1], "runner")
        self.assertEqual(cmd[cmd.index("--output-format") + 1], "json")
        self.assertEqual(cmd[cmd.index("--usage-output-file") + 1], "/tmp/u.json")
        # Claude-only knobs must NOT leak into the copilot form.
        self.assertNotIn("--max-budget-usd", cmd)
        # Default: no per-invocation credit cap, no resume.
        self.assertNotIn("--max-ai-credits", cmd)
        self.assertFalse(any(t.startswith("--resume") for t in cmd))

    def test_resume_mapping_when_session_carried(self):
        cmd = self._cmd(agent_name="judge", session_id="abc123")
        self.assertIn("--resume=abc123", cmd)

    def test_max_ai_credits_forwarded_when_set(self):
        cmd = self._cmd(max_ai_credits=5)
        self.assertIn("--max-ai-credits", cmd)
        self.assertEqual(cmd[cmd.index("--max-ai-credits") + 1], "5")


# Slice 031-01 — edit-permission-wall diagnosis (ADR-0037)
#
# The loop driver relabels a nothing-landed halt (oracle_plateau /
# max_iterations_reached, oracle below threshold, runner never edited) to
# `edit_permission_unavailable` (rc=2) with a fix breadcrumb, on a git target.
# The signal is an untracked-inclusive per-runner-iteration disk delta persisted
# as `runner_ever_edited`. Test classes map to ACs:
#   AC1/AC5/AC6/AC9 (helper) → RelabelDecisionUnitTests
#   AC2/AC7 (helper)         → TreeSnapshotUnitTests
#   AC1/AC5/AC8 (loop)       → EditPermissionRelabelLoopTests
#   AC2/AC3 (loop)           → RunnerEverEditedArmTests
#   AC4 (loop)               → JudgeIterationExclusionTests
#   AC6 (loop)               → CapableRunNotMislabeledTests
#   AC7 (loop)               → BookkeepingNoFalseArmTests
#   AC9 (loop)               → NonGitFallbackTests
# ============================================================================


def _edit_perm_git_target(tmp: Path, oracle_body: str) -> Path:
    """A scaffolded git-repo target: manifest + oracle committed, clean tree."""
    target = tmp / "demo"
    target.mkdir()
    _make_manifest(target)
    _make_oracle(target, oracle_body)
    _git_init(target)
    _git_commit_all(target)
    return target


def _mock_claude_editing(
    bindir: Path, counter_file: Path, *, create_rel: str, when: str,
) -> Path:
    """Mock claude that writes `<cwd>/<create_rel>` when the shell test `when`
    (on `$n`, the 1-indexed invocation count) passes. cwd is the target (per
    `_invoke_claude`), so `create_rel` lands inside the git tree under test.
    """
    payload = _claude_json_payload()
    body = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        counter_file='{counter_file}'
        if [ -f "$counter_file" ]; then n=$(cat "$counter_file"); else n=0; fi
        n=$((n + 1))
        echo "$n" > "$counter_file"
        if {when}; then
            mkdir -p "$(dirname '{create_rel}')" 2>/dev/null || true
            echo "content-$n" > '{create_rel}'
        fi
        cat <<'__JSON_EOF__'
        {payload}
        __JSON_EOF__
    """)
    return _make_mock_claude(bindir, body)


def _mock_claude_bookkeeping_only(bindir: Path, counter_file: Path) -> Path:
    """Mock claude whose only on-disk residue is servo/tooling bookkeeping
    (`.servo/`, `__pycache__`, `*.pyc`, coverage) — the false-arm hazard AC7
    guards against.
    """
    payload = _claude_json_payload()
    body = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        counter_file='{counter_file}'
        if [ -f "$counter_file" ]; then n=$(cat "$counter_file"); else n=0; fi
        n=$((n + 1))
        echo "$n" > "$counter_file"
        mkdir -p "__pycache__" ".servo/scratch" 2>/dev/null || true
        echo x > "__pycache__/mod.cpython-313.pyc"
        echo x > ".servo/scratch/junk-$n.txt"
        echo x > ".coverage"
        cat <<'__JSON_EOF__'
        {payload}
        __JSON_EOF__
    """)
    return _make_mock_claude(bindir, body)


class TreeSnapshotUnitTests(unittest.TestCase):
    """AC2/AC7 (helper): `_tree_snapshot` is untracked-inclusive, delta-able,
    None on a non-git target, and filters bookkeeping paths."""

    def setUp(self):
        self.m = _load_loop_module()
        self.tmpdir = tempfile.mkdtemp(prefix="servo-snap-")
        self.target = Path(self.tmpdir) / "demo"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _repo(self):
        (self.target / "a.txt").write_text("x")
        _git_init(self.target)
        _git_commit_all(self.target)

    def test_non_git_returns_none(self):
        # AC9 at helper level: mirrors _dirty_tree_paths' None for non-git.
        (self.target / "a.txt").write_text("x")
        self.assertIsNone(self.m._tree_snapshot(self.target))

    def test_untracked_new_file_registers_in_delta(self):
        # AC2 + mutation (c): a created untracked file MUST change the snapshot
        # (unlike _dirty_tree_paths, which drops `??`).
        self._repo()
        before = self.m._tree_snapshot(self.target)
        (self.target / "created.py").write_text("new")
        after = self.m._tree_snapshot(self.target)
        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertNotEqual(before, after)
        self.assertNotEqual(after - before, set())

    def test_modified_tracked_file_registers_in_delta(self):
        self._repo()
        before = self.m._tree_snapshot(self.target)
        (self.target / "a.txt").write_text("changed")
        after = self.m._tree_snapshot(self.target)
        self.assertNotEqual(before, after)

    def test_bookkeeping_paths_filtered(self):
        # AC7: .servo/, __pycache__, *.pyc, coverage never enter the snapshot,
        # so a runner subprocess that only touches them cannot false-arm.
        self._repo()
        before = self.m._tree_snapshot(self.target)
        (self.target / ".servo").mkdir(exist_ok=True)
        (self.target / ".servo" / "scratch.txt").write_text("x")
        (self.target / "__pycache__").mkdir(exist_ok=True)
        (self.target / "__pycache__" / "m.pyc").write_text("x")
        (self.target / ".coverage").write_text("x")
        after = self.m._tree_snapshot(self.target)
        self.assertEqual(before, after)


class RelabelDecisionUnitTests(unittest.TestCase):
    """AC1/AC5/AC6/AC9 (helper): the `_relabel_terminal_reason` conjuncts, each
    proven load-bearing by an isolating case."""

    def setUp(self):
        self.m = _load_loop_module()

    def _call(self, reason, *, edited, status, git=True):
        return self.m._relabel_terminal_reason(
            reason, runner_ever_edited=edited,
            final_oracle_status=status, edit_signal_available=git,
        )

    def test_reason_constant_value(self):
        # AC1: the new terminal-reason string is stable contract.
        self.assertEqual(
            self.m.REASON_EDIT_PERMISSION_UNAVAILABLE,
            "edit_permission_unavailable",
        )

    def test_plateau_below_unarmed_git_relabels(self):
        self.assertEqual(
            self._call(self.m.REASON_ORACLE_PLATEAU, edited=False,
                       status=self.m.STATUS_BELOW_THRESHOLD),
            self.m.REASON_EDIT_PERMISSION_UNAVAILABLE)

    def test_max_iterations_below_unarmed_git_relabels(self):
        self.assertEqual(
            self._call(self.m.REASON_MAX_ITERATIONS_REACHED, edited=False,
                       status=self.m.STATUS_BELOW_THRESHOLD),
            self.m.REASON_EDIT_PERMISSION_UNAVAILABLE)

    def test_iteration_cap_below_unarmed_git_relabels(self):
        # 031-02: the goal driver's iteration-cap terminal is relabel-eligible
        # through the SAME shared helper (unit-level, complementing the
        # end-to-end GoalEditPermissionRelabelTests).
        self.assertEqual(
            self._call(self.m.REASON_ITERATION_CAP_REACHED, edited=False,
                       status=self.m.STATUS_BELOW_THRESHOLD),
            self.m.REASON_EDIT_PERMISSION_UNAVAILABLE)

    def test_oracle_below_threshold_reason_unarmed_git_relabels(self):
        # 031-02: the goal driver's below-threshold terminal is relabel-eligible.
        self.assertEqual(
            self._call(self.m.REASON_ORACLE_BELOW_THRESHOLD, edited=False,
                       status=self.m.STATUS_BELOW_THRESHOLD),
            self.m.REASON_EDIT_PERMISSION_UNAVAILABLE)

    def test_pass_status_suppresses_relabel(self):
        # Mutation (a): the not-a-pass conjunct. A pass is never relabeled.
        self.assertIsNone(
            self._call(self.m.REASON_ORACLE_PLATEAU, edited=False,
                       status=self.m.STATUS_PASS))

    def test_env_error_status_suppresses_relabel(self):
        # A broken-gate (env_error) halt is a different diagnosis, not a wall.
        self.assertIsNone(
            self._call(self.m.REASON_MAX_ITERATIONS_REACHED, edited=False,
                       status=self.m.STATUS_ENV_ERROR))

    def test_armed_flag_suppresses_relabel(self):
        # Mutation (b): an edit proves permission → never relabel.
        self.assertIsNone(
            self._call(self.m.REASON_ORACLE_PLATEAU, edited=True,
                       status=self.m.STATUS_BELOW_THRESHOLD))

    def test_non_git_suppresses_relabel(self):
        # AC9: no computable signal → keep today's terminal reason.
        self.assertIsNone(
            self._call(self.m.REASON_ORACLE_PLATEAU, edited=False,
                       status=self.m.STATUS_BELOW_THRESHOLD, git=False))

    def test_other_terminal_reasons_never_relabel(self):
        # Only the four relabel-eligible halts (two loop + two goal) fire; any
        # other reason never relabels, even with the other conjuncts satisfied
        # (so the relabel never fires early / on a cost-ceiling or context halt).
        for reason in (self.m.REASON_ORACLE_PASSED,
                       self.m.REASON_COST_CEILING_REACHED,
                       self.m.REASON_CONTEXT_FULL,
                       self.m.REASON_INTERRUPTED):
            self.assertIsNone(
                self._call(reason, edited=False,
                           status=self.m.STATUS_BELOW_THRESHOLD),
                msg=reason)


class CopilotLoopDriverIntegrationTests(unittest.TestCase):
    """ADR-0043 gates the September native prototype before paid dispatch."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-copilot-loop-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        self.args_log = tmp / "args.log"
        _mock_copilot(
            self.bindir,
            _copilot_jsonl_fixture(_COPILOT_VERDICT_TEXT),
            json.dumps(_COPILOT_USAGE_FIXTURE),
            self.counter,
            self.args_log,
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_copilot_launch_refused_before_argv_emitted(self):
        result = _run_loop(
            self.target, "--host", "copilot", "--prompt", "make it pass",
            "--max-iterations", "2", mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertFalse(self.counter.exists())
        self.assertFalse(self.args_log.exists())
        self.assertFalse((self.target / ".servo/runs").exists())

    def test_refusal_does_not_fabricate_usage_or_verdict(self):
        result = _run_loop(
            self.target, "--host", "copilot", "--prompt", "x",
            "--max-iterations", "1", mock_bindir=self.bindir,
        )
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        lines = _stdout_json_lines(result.stdout)
        self.assertEqual(len(lines), 1)
        self.assertNotIn("verdict", lines[0])
        self.assertIsNone(lines[0]["cumulative_cost_usd"])
        self.assertEqual(lines[0]["final_oracle_status"], "env_error")

    def test_claude_argv_unchanged_for_default_host(self):
        # Default host = claude: a mock claude is used and the claude argv form
        # (with --max-budget-usd) is emitted; `copilot` is never invoked.
        claude_bindir = Path(self.tmpdir) / "claude_bin"
        claude_counter = Path(self.tmpdir) / "claude_counter.txt"
        claude_args = Path(self.tmpdir) / "claude_args.log"
        _mock_claude_with_args_log(
            claude_bindir, _claude_json_payload(), claude_counter, claude_args)
        result = _run_loop(
            self.target, "--prompt", "x", "--max-iterations", "1",
            mock_bindir=claude_bindir,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        argv = _read_args_log(claude_args)[0]
        # The Claude form is byte-unchanged: --max-budget-usd present, and none
        # of the Copilot-only tokens leak in.
        self.assertIn("--max-budget-usd", argv)
        self.assertNotIn("--allow-all-tools", argv)
        self.assertNotIn("-s", argv)
        self.assertNotIn("--usage-output-file", argv)


class EditPermissionRelabelLoopTests(unittest.TestCase):
    """AC1/AC5/AC8: a walled loop-driver run (git target, runner never edits,
    oracle below threshold) relabels to edit_permission_unavailable, rc=2, with
    a fix breadcrumb — for both max-iterations and plateau halts."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-editperm-")
        tmp = Path(self.tmpdir)
        self.target = _edit_perm_git_target(tmp, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _summary(self, result):
        return _stdout_json_lines(result.stdout)[-1]

    def test_max_iterations_halt_relabels_rc2(self):
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                           mock_bindir=self.bindir)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"],
                         "edit_permission_unavailable")
        # AC1: distinct from a clean max_iterations exit (rc=0).
        self.assertEqual(result.returncode, 2, msg=result.stderr)

    def test_plateau_halt_relabels_rc2(self):
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "5",
                           "--plateau-window", "1", mock_bindir=self.bindir)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"],
                         "edit_permission_unavailable")
        self.assertEqual(result.returncode, 2, msg=result.stderr)

    def test_breadcrumb_present_in_terminal_record(self):
        # AC8: the terminal record names the grant to add.
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                           mock_bindir=self.bindir)
        summary = self._summary(result)
        self.assertIn("terminal_breadcrumb", summary)
        crumb = summary["terminal_breadcrumb"]
        self.assertIn("settings.local.json", crumb)
        self.assertIn("Routine", crumb)

    def test_state_records_runner_never_edited(self):
        _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                  mock_bindir=self.bindir)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertFalse(state["runner_ever_edited"])
        # On a real git target the signal WAS computable — the relabel is
        # gated on this, not on a fresh _is_git_work_tree probe.
        self.assertTrue(state["edit_signal_computed"])


class CopilotGoalFamilyRefusalTests(unittest.TestCase):
    """AC3 — the /goal family refuses (explicitly) under `--host copilot`.

    Autopilot has no oracle-gated stop and the target-side agentStop gate's
    live firing is unverifiable headless (jig 113-08 / ADR-0038), so the goal
    driver is a documented residual under Copilot — never a silent un-gated run.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-copilot-goal-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_driver_goal_refuses(self):
        result = _run_raw(self.target, "--host", "copilot", "--driver", "goal",
                          "--prompt", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("copilot", result.stderr.lower())
        self.assertIn("--driver loop", result.stderr)

    def test_background_refuses(self):
        result = _run_raw(self.target, "--host", "copilot", "--background",
                          "--prompt", "x", extra_env={"SERVO_READINESS_GATE": "0"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("copilot", result.stderr.lower())

    def test_emit_routine_prompt_refuses(self):
        result = _run_raw(self.target, "--host", "copilot",
                          "--emit-routine-prompt", "--prompt", "x",
                          extra_env={"SERVO_READINESS_GATE": "0"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("copilot", result.stderr.lower())

    def test_summary_reason_is_goal_unsupported_host(self):
        result = _run_raw(self.target, "--host", "copilot", "--driver", "goal",
                          "--prompt", "x")
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "native_capability_unavailable")


class RunnerEverEditedArmTests(unittest.TestCase):
    """AC2/AC3: the untracked-inclusive delta arms runner_ever_edited on the
    first runner edit, treats a pre-existing dirty tree as not-this-iteration's
    change, and persists the flag across --resume."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-arm-")
        self.tmp = Path(self.tmpdir)
        self.target = _edit_perm_git_target(self.tmp, _below_threshold_oracle())
        self.bindir = self.tmp / "bin"
        self.counter = self.tmp / "counter.txt"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_created_untracked_file_arms_flag(self):
        # AC2: a runner whose only change is CREATING a new untracked file arms.
        _mock_claude_editing(self.bindir, self.counter,
                             create_rel="created_module.py",
                             when='[ "$n" -eq 1 ]')
        _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                  mock_bindir=self.bindir)
        run_id = _find_only_run_id(self.target)
        self.assertTrue(_read_state(self.target, run_id)["runner_ever_edited"])

    def test_preexisting_untracked_dirt_does_not_arm(self):
        # AC2: a delta, not an absolute clean-tree check — a pre-existing
        # untracked file is in both snapshots, so it is not this iteration's
        # change (guards the --allow-dirty / --resume dirty-tree case).
        (self.target / "preexisting.txt").write_text("was here before\n")
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)
        _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                  mock_bindir=self.bindir)
        run_id = _find_only_run_id(self.target)
        self.assertFalse(_read_state(self.target, run_id)["runner_ever_edited"])

    def test_flag_persists_across_resume(self):
        # AC3: arm at iter 1, resume; the reloaded state still shows armed even
        # though the resumed judge iteration lands nothing (proves persistence,
        # not re-derivation).
        _mock_claude_editing(self.bindir, self.counter,
                             create_rel="created_module.py",
                             when='[ "$n" -eq 1 ]')
        _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                  mock_bindir=self.bindir)
        run_id = _find_only_run_id(self.target)
        self.assertTrue(_read_state(self.target, run_id)["runner_ever_edited"])
        _run_loop(self.target, "--resume", run_id, "--max-iterations", "2",
                  mock_bindir=self.bindir)
        self.assertTrue(_read_state(self.target, run_id)["runner_ever_edited"])


class JudgeIterationExclusionTests(unittest.TestCase):
    """AC4: only runner iterations arm/count. A judge iteration that lands a
    change (contrary to its read-only contract) must NOT arm the flag, so a run
    whose only on-disk change came on a judge turn is still relabeled."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-judge-")
        tmp = Path(self.tmpdir)
        self.target = _edit_perm_git_target(tmp, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        # Creates a file only on EVEN invocations (= judge iterations).
        _mock_claude_editing(self.bindir, self.counter,
                             create_rel="judge_only_edit.txt",
                             when='[ $((n % 2)) -eq 0 ]')

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_judge_edit_does_not_arm_and_run_is_relabeled(self):
        # Mutation (d): if judge iterations were snapshotted, the judge's edit
        # would arm the flag and suppress the relabel.
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "2",
                           mock_bindir=self.bindir)
        run_id = _find_only_run_id(self.target)
        self.assertFalse(_read_state(self.target, run_id)["runner_ever_edited"])
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"],
                         "edit_permission_unavailable")
        self.assertEqual(result.returncode, 2, msg=result.stderr)


class CapableRunNotMislabeledTests(unittest.TestCase):
    """AC6: once the runner edits, a later plateau / max-iterations halt keeps
    its original reason — the edit proves permission."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-capable-")
        tmp = Path(self.tmpdir)
        self.target = _edit_perm_git_target(tmp, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_editing(self.bindir, self.counter,
                             create_rel="real_edit.py", when='[ "$n" -eq 1 ]')

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _summary(self, result):
        return _stdout_json_lines(result.stdout)[-1]

    def test_edit_then_max_iterations_keeps_reason(self):
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                           mock_bindir=self.bindir)
        self.assertEqual(self._summary(result)["terminal_reason"],
                         "max_iterations_reached")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_edit_then_plateau_keeps_reason(self):
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "5",
                           "--plateau-window", "1", mock_bindir=self.bindir)
        self.assertEqual(self._summary(result)["terminal_reason"],
                         "oracle_plateau")
        self.assertEqual(result.returncode, 0, msg=result.stderr)


class BookkeepingNoFalseArmTests(unittest.TestCase):
    """AC7: a walled runner whose only residue is gate/.servo/cache bookkeeping
    leaves runner_ever_edited false, so the halt is still relabeled."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-bk-")
        tmp = Path(self.tmpdir)
        self.target = _edit_perm_git_target(tmp, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_bookkeeping_only(self.bindir, self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_bookkeeping_does_not_arm_and_relabels(self):
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                           mock_bindir=self.bindir)
        run_id = _find_only_run_id(self.target)
        self.assertFalse(_read_state(self.target, run_id)["runner_ever_edited"])
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"],
                         "edit_permission_unavailable")
        self.assertEqual(result.returncode, 2, msg=result.stderr)


class CopilotHostSelectionTests(unittest.TestCase):
    """Default remains Claude; native selection never falls back to Claude."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-copilot-host-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        self.args_log = tmp / "args.log"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_bogus_host_rejected(self):
        result = _run_raw(self.target, "--host", "banana", "--prompt", "x")
        self.assertEqual(result.returncode, 2)

    def test_default_host_uses_claude(self):
        # No --host, no --driver: real default routing, mock claude only.
        _mock_claude_with_args_log(
            self.bindir, _claude_json_payload(), self.counter, self.args_log)
        result = _run_raw(self.target, "--prompt", "x", "--max-iterations", "1",
                          "--driver", "loop", "--plateau-window", "0",
                          mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        argv = _read_args_log(self.args_log)[0]
        self.assertIn("--max-budget-usd", argv)  # the Claude loop-driver form
        self.assertNotIn("--allow-all-tools", argv)

    def test_auto_copilot_refuses_without_claude_fallback(self):
        claude_args = Path(self.tmpdir) / "claude_args.log"
        _mock_claude_goal(
            self.bindir,
            _goal_stream_jsonl(assistant_text=GOAL_PASS_SENTINEL),
            args_log=claude_args,
        )
        _mock_copilot(
            self.bindir, _copilot_jsonl_fixture(_COPILOT_VERDICT_TEXT),
            json.dumps(_COPILOT_USAGE_FIXTURE), self.counter, self.args_log)
        result = _run_raw(self.target, "--host", "copilot", "--prompt", "x",
                          "--max-iterations", "1", "--plateau-window", "0",
                          mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertFalse(self.args_log.exists())
        self.assertFalse(claude_args.exists())

    def test_max_ai_credits_validation(self):
        result = _run_raw(self.target, "--host", "copilot", "--prompt", "x",
                          "--max-ai-credits", "-1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--max-ai-credits", result.stderr)


class NonGitFallbackTests(unittest.TestCase):
    """AC9: on a non-git target the delta cannot be computed; the loop keeps
    today's terminal reason and never crashes or false-relabels."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-nongit-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_non_git_keeps_max_iterations_reason(self):
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                           mock_bindir=self.bindir)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        self.assertFalse(_read_state(self.target, run_id)["runner_ever_edited"])


def _make_fake_git(bindir: Path) -> Path:
    """A PATH-injected fake `git`: `rev-parse` reports a healthy work tree, but
    `status` always fails. Simulates a rev-parse-healthy tree whose `git status`
    errors during the run — the case that must NOT relabel (nit 1)."""
    bindir.mkdir(parents=True, exist_ok=True)
    body = textwrap.dedent("""\
        #!/usr/bin/env bash
        for a in "$@"; do
            if [ "$a" = "status" ]; then exit 1; fi
            if [ "$a" = "rev-parse" ]; then echo "true"; exit 0; fi
        done
        exit 0
    """)
    git = bindir / "git"
    git.write_text(body)
    _make_executable(git)
    return git


def _below_threshold_oracle_that_writes(marker_rel: str) -> str:
    """A below-threshold oracle that ALSO creates a non-bookkeeping untracked
    file when it runs (cwd=target). The gate/oracle runs AFTER the runner invoke
    returns, so this residue falls OUTSIDE the before/after-invoke bracket and
    must not arm runner_ever_edited (nit 2)."""
    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        echo 'gate-oracle-ran' > '{marker_rel}'
        echo 'oracle: composite=0.2000 threshold=0.5'
        exit 1
    """)


class PersistentGitErrorFallbackTests(unittest.TestCase):
    """Nit 1 (reconciliation): the relabel gates on `edit_signal_computed` (a
    runner-iteration `_tree_snapshot` returned non-None at least once), NOT a
    fresh `_is_git_work_tree` probe. A rev-parse-healthy tree whose `git status`
    fails throughout leaves the signal never-computed → keep today's terminal
    reason, so a capable-but-below-threshold run is never mislabeled."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-giterr-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)
        _make_fake_git(self.bindir)  # rev-parse -> true, status -> fail

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_persistent_git_status_error_no_relabel(self):
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                           mock_bindir=self.bindir)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "max_iterations_reached")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        # Signal never computable → gate stays closed even though rev-parse is
        # healthy (the exact case the old _is_git_work_tree guard mislabeled).
        self.assertFalse(state["edit_signal_computed"])
        self.assertFalse(state["runner_ever_edited"])


class GateResidueBracketTests(unittest.TestCase):
    """Nit 2 (reconciliation): proves the before/after-INVOKE bracket, not just
    the bookkeeping filter, is load-bearing. A gate/oracle that writes a
    NON-bookkeeping untracked file (after the runner invoke returns) must not arm
    the flag — so snapshot_after must be taken BEFORE the gate call."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-bracket-")
        tmp = Path(self.tmpdir)
        self.target = _edit_perm_git_target(
            tmp, _below_threshold_oracle_that_writes("oracle_marker.txt"))
        self.bindir = tmp / "bin"
        self.counter = tmp / "counter.txt"
        _mock_claude_constant(self.bindir, _claude_json_payload(), self.counter)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_gate_residue_after_invoke_does_not_arm(self):
        result = _run_loop(self.target, "--prompt", "x", "--max-iterations", "1",
                           mock_bindir=self.bindir)
        # The oracle actually ran and left its non-bookkeeping marker...
        self.assertTrue((self.target / "oracle_marker.txt").exists())
        run_id = _find_only_run_id(self.target)
        # ...but it landed AFTER snapshot_after, so it did not arm the flag.
        self.assertFalse(_read_state(self.target, run_id)["runner_ever_edited"])
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"],
                         "edit_permission_unavailable")
        self.assertEqual(result.returncode, 2, msg=result.stderr)


# ============================================================================
# Slice 031-02 — edit-permission-wall diagnosis, GOAL driver (ADR-0037)
#
# The goal driver (`run_goal_loop`) issues ONE long `claude -p` with no
# per-iteration checkpoint. This slice extends the 031-01 relabel to it: a
# whole-run disk delta bracketing the single `_invoke_claude_goal` call, and a
# terminal relabel of `iteration_cap_reached` / `oracle_below_threshold` to
# `edit_permission_unavailable` (rc=2) with the shared breadcrumb when nothing
# landed and the oracle is below threshold. Reuses 031-01's `_tree_snapshot`,
# `_is_bookkeeping_path`, `_relabel_terminal_reason`, and the breadcrumb string.
# Test classes map to ACs:
#   AC1 (whole-run delta)                    → GoalEditSignalRecordingTests
#   AC2 (relabel, both reasons, pass never)  → GoalEditPermissionRelabelTests
#   AC3 (capable run never mislabeled)       → GoalCapableRunNotMislabeledTests
#   AC4 (bookkeeping no false-arm / non-git) → GoalBookkeepingAndNonGitTests
# ============================================================================


class _GoalGitTargetMixin(_GoalTargetMixin):
    """A `_GoalTargetMixin` whose scaffolded target is a committed git repo, so
    `_tree_snapshot` yields a computable (non-None) whole-run delta."""

    def _setup_git_target(self, oracle_body: str):
        self._setup_target(oracle_body)
        _git_init(self.target)
        _git_commit_all(self.target)


def _mock_claude_goal_editing(bindir: Path, jsonl: str, *, create_rel: str) -> Path:
    """Goal-driver mock that creates a NON-bookkeeping file (`<cwd>/<create_rel>`,
    cwd=target) during the single /goal invoke, then emits the stream-json — a
    *capable* goal run that lands a real edit. The `--version` short-circuit in
    `_make_mock_claude` means the file lands only on the real `-p` invoke (the
    sole non-version claude call in a goal run), which falls inside the
    before/after-invoke bracket."""
    body = "\n".join([
        "#!/usr/bin/env bash",
        f"mkdir -p \"$(dirname '{create_rel}')\" 2>/dev/null || true",
        f"printf 'goal-created\\n' > '{create_rel}'",
        "cat <<'__JSONL_EOF__'",
        jsonl,
        "__JSONL_EOF__",
        "",
    ])
    return _make_mock_claude(bindir, body)


def _mock_claude_goal_bookkeeping(bindir: Path, jsonl: str) -> Path:
    """Goal-driver mock whose only on-disk residue is servo/tooling bookkeeping
    (`.servo/`, `__pycache__`, `*.pyc`, coverage) — the false-arm hazard AC4
    guards against — then emits the stream-json."""
    body = "\n".join([
        "#!/usr/bin/env bash",
        "mkdir -p '__pycache__' '.servo/scratch' 2>/dev/null || true",
        "echo x > '__pycache__/mod.cpython-313.pyc'",
        "echo x > '.servo/scratch/junk.txt'",
        "echo x > '.coverage'",
        "cat <<'__JSONL_EOF__'",
        jsonl,
        "__JSONL_EOF__",
        "",
    ])
    return _make_mock_claude(bindir, body)


class GoalEditSignalRecordingTests(_GoalGitTargetMixin, unittest.TestCase):
    """AC1: the whole-run disk delta around `_invoke_claude_goal` records a goal
    run that lands a change as edited, and one that lands nothing as not."""

    def test_nothing_landed_records_not_edited(self):
        self._setup_git_target(_below_threshold_oracle())
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="ran gate, still failing",
            result_event=_goal_result_event(subtype="success"),
        ))
        _run_goal(self.target, "--prompt", "x", mock_bindir=self.bindir,
                  extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        state = self._state()
        self.assertFalse(state["runner_ever_edited"])
        # On a real git target the signal WAS computable.
        self.assertTrue(state["edit_signal_computed"])

    def test_created_file_records_edited(self):
        self._setup_git_target(_below_threshold_oracle())
        _mock_claude_goal_editing(
            self.bindir,
            _goal_stream_jsonl(assistant_text="made a change",
                               result_event=_goal_result_event(subtype="success")),
            create_rel="capable_edit.py")
        _run_goal(self.target, "--prompt", "x", mock_bindir=self.bindir,
                  extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertTrue((self.target / "capable_edit.py").exists())
        state = self._state()
        self.assertTrue(state["runner_ever_edited"])
        self.assertTrue(state["edit_signal_computed"])


class GoalEditPermissionRelabelTests(_GoalGitTargetMixin, unittest.TestCase):
    """AC2: a walled goal run (git target, nothing landed, oracle below
    threshold) relabels iteration_cap_reached / oracle_below_threshold to
    edit_permission_unavailable (rc=2) with the breadcrumb; a passing oracle is
    never relabeled."""

    def _walled(self, *, subtype):
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="ran gate, still red",
            result_event=_goal_result_event(
                subtype=subtype, is_error=subtype.startswith("error_")),
        ))
        return _run_goal(self.target, "--prompt", "x", mock_bindir=self.bindir,
                         extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})

    def test_oracle_below_threshold_relabels_rc2(self):
        self._setup_git_target(_below_threshold_oracle())
        result = self._walled(subtype="success")
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "edit_permission_unavailable")
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        crumb = summary["terminal_breadcrumb"]
        self.assertIn("settings.local.json", crumb)
        self.assertIn("Routine", crumb)

    def test_iteration_cap_reached_relabels_rc2(self):
        self._setup_git_target(_below_threshold_oracle())
        result = self._walled(subtype="error_max_turns")
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "edit_permission_unavailable")
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertIn("settings.local.json", summary["terminal_breadcrumb"])

    def test_oracle_passed_is_never_relabeled(self):
        # Mutation (a): the oracle-below-threshold conjunct as it applies to the
        # goal reasons. subtype=error_max_turns → iteration_cap_reached, but the
        # final gate PASSED (not below threshold) → no relabel, rc=0.
        self._setup_git_target(_passing_oracle())
        result = self._walled(subtype="error_max_turns")
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "iteration_cap_reached")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("terminal_breadcrumb", summary)


class GoalCapableRunNotMislabeledTests(_GoalGitTargetMixin, unittest.TestCase):
    """AC3: a goal run that lands any change keeps its original terminal reason —
    the edit proves permission (guards the did-anything-land gate)."""

    def _capable(self, *, subtype, oracle_body):
        self._setup_git_target(oracle_body)
        _mock_claude_goal_editing(
            self.bindir,
            _goal_stream_jsonl(
                assistant_text="edited a file",
                result_event=_goal_result_event(
                    subtype=subtype, is_error=subtype.startswith("error_"))),
            create_rel="capable_edit.py")
        return _run_goal(self.target, "--prompt", "x", mock_bindir=self.bindir,
                         extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})

    def test_created_file_keeps_oracle_below_threshold(self):
        # Mutation (b): the did-anything-land gate. A capable run below threshold
        # keeps oracle_below_threshold (rc=0), NOT relabel.
        result = self._capable(subtype="success",
                               oracle_body=_below_threshold_oracle())
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "oracle_below_threshold")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("terminal_breadcrumb", summary)

    def test_created_file_keeps_iteration_cap_reached(self):
        result = self._capable(subtype="error_max_turns",
                               oracle_body=_below_threshold_oracle())
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "iteration_cap_reached")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("terminal_breadcrumb", summary)


class GoalBookkeepingAndNonGitTests(_GoalGitTargetMixin, unittest.TestCase):
    """AC4: gate/.servo/cache residue must not count as an edit, and a non-git
    target falls back to today's terminal reason rather than false-relabeling."""

    def test_bookkeeping_only_still_relabels(self):
        self._setup_git_target(_below_threshold_oracle())
        _mock_claude_goal_bookkeeping(self.bindir, _goal_stream_jsonl(
            assistant_text="ran gate, still red",
            result_event=_goal_result_event(subtype="success")))
        result = _run_goal(self.target, "--prompt", "x", mock_bindir=self.bindir,
                           extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        state = self._state()
        self.assertFalse(state["runner_ever_edited"])
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "edit_permission_unavailable")
        self.assertEqual(result.returncode, 2, msg=result.stderr)

    def test_non_git_target_falls_back(self):
        # Non-git target: _tree_snapshot is None → signal not computable → keep
        # today's terminal reason, never crash or false-relabel.
        self._setup_target(_below_threshold_oracle())  # NOTE: no git init
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text="ran gate, still red",
            result_event=_goal_result_event(subtype="success")))
        result = _run_goal(self.target, "--prompt", "x", mock_bindir=self.bindir,
                           extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "oracle_below_threshold")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        state = self._state()
        self.assertFalse(state["edit_signal_computed"])
        self.assertFalse(state["runner_ever_edited"])


# ============================================================================
# Slice 038-01 — per-iteration accounting + bug 007 (resumed-session cost)
# ============================================================================

_RT_MOCK_PY = r'''
import json, os, sys
d = os.path.dirname(os.path.abspath(__file__))
plan = json.load(open(os.path.join(d, "plan.json")))
sf = os.path.join(d, "mockstate.json")
st = json.load(open(sf)) if os.path.exists(sf) else {"n": 0, "sessions": {}}
n = st["n"]
call = plan["calls"][min(n, len(plan["calls"]) - 1)]
st["n"] = n + 1
argv = sys.argv[1:]
with open(os.path.join(d, "args.log"), "a") as fh:
    for a in argv:
        fh.write(a + "\x1f")
    fh.write("\x1e")
resumed = argv[argv.index("--resume") + 1] if "--resume" in argv else None
sid = call.get("session_id") or resumed or "sess-%d" % (n + 1)
sess = st["sessions"].setdefault(sid, {"cost": 0.0, "models": {}})
call_cost = 0.0
usage = {"input_tokens": 0, "output_tokens": 0,
         "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
this_models = {}
for model, spec in call["models"].items():
    cost, (i, o, cr, cc) = spec["cost"], spec["tokens"]
    call_cost += cost
    usage["input_tokens"] += i
    usage["output_tokens"] += o
    usage["cache_read_input_tokens"] += cr
    usage["cache_creation_input_tokens"] += cc
    for bucket in (sess["models"], this_models):
        m = bucket.setdefault(model, {"costUSD": 0.0, "inputTokens": 0,
            "outputTokens": 0, "cacheReadInputTokens": 0,
            "cacheCreationInputTokens": 0, "contextWindow": 1000000})
        m["costUSD"] += cost
        m["inputTokens"] += i
        m["outputTokens"] += o
        m["cacheReadInputTokens"] += cr
        m["cacheCreationInputTokens"] += cc
sess["cost"] += call_cost
if plan.get("mode") == "per_call":
    total, mu = call_cost, this_models
else:
    total, mu = sess["cost"], sess["models"]
if call.get("advisor"):
    usage["iterations"] = [{"type": "message"},
        {"type": "advisor_message", "model": call["advisor"]}, {"type": "message"}]
payload = {"type": "result", "subtype": "success", "is_error": False,
    "session_id": sid, "total_cost_usd": total, "terminal_reason": "completed",
    "stop_reason": "end_turn", "num_turns": 1, "result": "ok", "usage": usage,
    "modelUsage": mu}
if plan.get("drop_model_usage"):
    del payload["modelUsage"]
json.dump(st, open(sf, "w"))
print(json.dumps(payload))
'''


def _mock_claude_running_total(
    bindir: Path, calls: list, *, mode: str = "running",
    drop_model_usage: bool = False,
) -> Path:
    """Mock `claude` keeping per-session running totals across `--resume`.

    Each invocation n emits `usage` = THIS call only and `modelUsage` /
    `total_cost_usd` = the session RUNNING TOTAL (what `claude -p` really does,
    bug 007). A call may force `session_id` (different-id case) or name an
    `advisor` model (adds an `advisor_message` iteration). `mode="per_call"`
    breaks the running-total identity (reports this call only). Each call is
    `{"models": {id: {"cost": f, "tokens": [in, out, cache_read, cache_create]}}}`.
    """
    bindir.mkdir(parents=True, exist_ok=True)
    (bindir / "plan.json").write_text(json.dumps(
        {"calls": calls, "mode": mode, "drop_model_usage": drop_model_usage}))
    (bindir / "mock_rt.py").write_text(_RT_MOCK_PY)
    body = f"#!/usr/bin/env bash\nexec '{sys.executable}' '{bindir / 'mock_rt.py'}' \"$@\"\n"
    return _make_mock_claude(bindir, body)


HAIKU = "claude-haiku-5-5"
OPUS = "claude-opus-5-5"


def _rt_call(cost: float, tokens=(2, 4, 100, 50), model: str = HAIKU, **extra) -> dict:
    return {"models": {model: {"cost": cost, "tokens": list(tokens)}}, **extra}


class _AccountingTarget:
    def _setup_acct(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-acct-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _below_threshold_oracle())
        self.bindir = tmp / "bin"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _iters(self, result):
        return [ln for ln in _stdout_json_lines(result.stdout) if "iteration" in ln]

    def _run(self, n: int, *extra):
        return _run_loop(
            self.target, "--prompt", "x", "--max-iterations", str(n),
            "--cost-ceiling", "10.00", *extra, mock_bindir=self.bindir)


class ResumedSessionCostDeltaTests(_AccountingTarget, unittest.TestCase):
    """Bug 007 / 038-01 AC3, AC5 — a resumed iteration costs its own delta."""

    def setUp(self):
        self._setup_acct()

    def test_resumed_iterations_cost_the_delta_not_the_running_total(self):
        _mock_claude_running_total(
            self.bindir, [_rt_call(0.10), _rt_call(0.20), _rt_call(0.30)])
        result = self._run(3)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        it = self._iters(result)
        self.assertEqual([round(i["cost_usd"], 6) for i in it], [0.10, 0.20, 0.30])
        self.assertEqual(
            [i["cost_basis"] for i in it],
            ["reported", "session_delta", "session_delta"])
        # Pre-fix this was 0.1 + 0.3 + 0.6 = 1.0.
        self.assertAlmostEqual(it[-1]["cumulative_cost_usd"], 0.60, places=6)

    def test_state_cumulative_is_sum_of_per_iteration_costs(self):
        _mock_claude_running_total(
            self.bindir, [_rt_call(0.10), _rt_call(0.20), _rt_call(0.30)])
        self._run(3)
        state = _read_state(self.target, _find_only_run_id(self.target))
        hist = state["oracle_score_history"]
        self.assertAlmostEqual(
            state["cumulative_cost_usd"], sum(h["cost_usd"] for h in hist), places=6)
        self.assertAlmostEqual(state["cumulative_cost_usd"], 0.60, places=6)

    def test_model_usage_is_per_invocation_on_resumed_session(self):
        _mock_claude_running_total(
            self.bindir, [_rt_call(0.10, (2, 4, 100, 50)), _rt_call(0.20, (3, 5, 200, 60))])
        result = self._run(2)
        second = self._iters(result)[1]
        got = dict(second["model_usage"][HAIKU])
        self.assertAlmostEqual(got.pop("cost_usd"), 0.20, places=6)
        self.assertEqual(got, {
            "input_tokens": 3, "output_tokens": 5,
            "cache_read_input_tokens": 200, "cache_creation_input_tokens": 60})
        self.assertEqual(second["usage"]["input_tokens"], 3)

    def test_max_budget_uses_corrected_cumulative(self):
        _mock_claude_running_total(
            self.bindir, [_rt_call(0.10), _rt_call(0.20), _rt_call(0.30)])
        self._run(3)
        argvs = _read_args_log(self.bindir / "args.log")
        self.assertEqual(len(argvs), 3)
        # Before iteration 3 the true spend is 0.10 + 0.20 (pre-fix: 0.4).
        self.assertAlmostEqual(
            float(_find_flag_value(argvs[2], "--max-budget-usd")), 10.0 - 0.30, places=6)

    def test_no_new_flags_added_to_argv(self):
        _mock_claude_running_total(self.bindir, [_rt_call(0.10), _rt_call(0.20)])
        self._run(2)
        for argv in _read_args_log(self.bindir / "args.log"):
            for flag in ("--model", "--effort", "--advisor"):
                self.assertNotIn(flag, argv)

    def test_snapshot_persisted_for_current_session(self):
        _mock_claude_running_total(self.bindir, [_rt_call(0.10), _rt_call(0.20)])
        self._run(2)
        state = _read_state(self.target, _find_only_run_id(self.target))
        snap = state["current_session_usage_snapshot"]
        self.assertEqual(snap["session_id"], state["current_session_id"])
        self.assertAlmostEqual(snap["total_cost_usd"], 0.30, places=6)
        self.assertEqual(snap["model_usage"][HAIKU]["inputTokens"], 4)


class ResumedSessionFailSafeTests(_AccountingTarget, unittest.TestCase):
    """AC3 BR-2 — unproven running-total semantics over-count, visibly."""

    def setUp(self):
        self._setup_acct()

    def test_different_session_id_returned_falls_back_to_reported(self):
        _mock_claude_running_total(self.bindir, [
            _rt_call(0.10), _rt_call(0.20, session_id="sess-other")])
        result = self._run(2)
        second = self._iters(result)[1]
        self.assertEqual(second["cost_basis"], "reported")
        self.assertAlmostEqual(second["cost_usd"], 0.20, places=6)
        self.assertIn("loop: ", result.stderr)

    def test_failed_identity_proof_falls_back_to_reported(self):
        # per_call mode reports only this call, so modelUsage tokens are below
        # snapshot + usage tokens: the proof fails and cost is the reported total.
        _mock_claude_running_total(
            self.bindir, [_rt_call(0.10), _rt_call(0.20), _rt_call(0.30)],
            mode="per_call")
        result = self._run(3)
        it = self._iters(result)
        self.assertEqual([i["cost_basis"] for i in it], ["reported"] * 3)
        self.assertAlmostEqual(it[-1]["cumulative_cost_usd"], 0.60, places=6)

    def test_resumed_reported_fallback_prints_one_breadcrumb_per_resumed_iteration(self):
        _mock_claude_running_total(
            self.bindir, [_rt_call(0.10), _rt_call(0.20), _rt_call(0.30)],
            mode="per_call")
        result = self._run(3)
        lines = [ln for ln in result.stderr.splitlines()
                 if ln.startswith("loop: iteration ")
                 and "cost basis fell back to the reported session total" in ln]
        # Iteration 1 is fresh (no --resume): breadcrumbs for iterations 2 and 3.
        self.assertEqual(len(lines), 2, msg=result.stderr)
        self.assertIn("iteration 2:", lines[0])
        self.assertIn("iteration 3:", lines[1])

    def test_reported_cost_below_snapshot_falls_back_to_reported(self):
        # Token identity holds (running mode) but the reported total is below
        # the snapshot: fail-safe to reported, never a clamped-to-zero delta.
        _mock_claude_running_total(
            self.bindir, [_rt_call(0.30), _rt_call(0.05)])
        # Rewrite the plan so the running cost dips: second call costs negative.
        plan = json.loads((self.bindir / "plan.json").read_text())
        plan["calls"][1]["models"][HAIKU]["cost"] = -0.10
        (self.bindir / "plan.json").write_text(json.dumps(plan))
        result = self._run(2)
        second = self._iters(result)[1]
        self.assertEqual(second["cost_basis"], "reported")
        self.assertAlmostEqual(second["cost_usd"], 0.20, places=6)

    def test_fresh_first_iteration_prints_no_breadcrumb(self):
        _mock_claude_running_total(self.bindir, [_rt_call(0.10)])
        result = self._run(1)
        self.assertNotIn("cost basis fell back", result.stderr)


class OldStateResumeTests(_AccountingTarget, unittest.TestCase):
    """AC6 — a pre-038 state.json (no snapshot, bare history) resumes."""

    def setUp(self):
        self._setup_acct()

    def test_old_state_resumes_with_reported_first_iteration(self):
        _mock_claude_running_total(self.bindir, [_rt_call(0.10), _rt_call(0.20)])
        self._run(1)
        run_id = _find_only_run_id(self.target)
        sp = _state_path(self.target, run_id)
        state = json.loads(sp.read_text())
        state.pop("current_session_usage_snapshot", None)
        keep = ("iteration", "composite", "threshold", "status")
        state["oracle_score_history"] = [
            {k: h[k] for k in keep if k in h} for h in state["oracle_score_history"]]
        old_entry = dict(state["oracle_score_history"][0])
        sp.write_text(json.dumps(state))
        result = _run_loop(
            self.target, "--resume", run_id, "--max-iterations", "2",
            "--cost-ceiling", "10.00", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        it = self._iters(result)
        self.assertEqual(it[0]["cost_basis"], "reported")
        self.assertAlmostEqual(it[0]["cost_usd"], 0.30, places=6)  # running total
        new = _read_state(self.target, run_id)
        self.assertEqual(new["state_schema_version"], 1)
        self.assertEqual(new["oracle_score_history"][0], old_entry)
        self.assertIn("cost_basis", new["oracle_score_history"][1])
        self.assertIn("loop: ", result.stderr)


class SnapshotResumeTests(_AccountingTarget, unittest.TestCase):
    """AC3 — a 038-era snapshot survives `--resume <run-id>`."""

    def setUp(self):
        self._setup_acct()

    def test_snapshot_survives_resume_and_gives_session_delta(self):
        _mock_claude_running_total(self.bindir, [_rt_call(0.10), _rt_call(0.20)])
        self._run(1)
        run_id = _find_only_run_id(self.target)
        self.assertIn(
            "current_session_usage_snapshot", _read_state(self.target, run_id))
        result = _run_loop(
            self.target, "--resume", run_id, "--max-iterations", "2",
            "--cost-ceiling", "10.00", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        first = self._iters(result)[0]
        self.assertEqual(first["cost_basis"], "session_delta")
        self.assertAlmostEqual(first["cost_usd"], 0.20, places=6)
        self.assertNotIn("cost basis fell back", result.stderr)


class IterationAccountingRecordTests(_AccountingTarget, unittest.TestCase):
    """AC1, AC2, BR-3 — accounting keys on history entries and stdout lines."""

    def setUp(self):
        self._setup_acct()

    def test_history_and_stdout_carry_accounting_keys(self):
        _mock_claude_running_total(self.bindir, [_rt_call(0.10), _rt_call(0.20)])
        result = self._run(2)
        state = _read_state(self.target, _find_only_run_id(self.target))
        keys = ("agent", "session_id", "cost_usd", "cost_basis", "usage",
                "model_usage", "model", "requested")
        for h in state["oracle_score_history"]:
            for k in ("iteration", "composite", "threshold", "status", *keys):
                self.assertIn(k, h)
        for ln in self._iters(result):
            for k in keys:
                self.assertIn(k, ln)
        hist = state["oracle_score_history"]
        self.assertEqual([h["agent"] for h in hist], ["runner", "judge"])
        self.assertEqual(hist[0]["session_id"], "sess-1")
        self.assertEqual(hist[0]["usage"], {
            "input_tokens": 2, "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 50, "output_tokens": 4})
        self.assertEqual(
            hist[0]["requested"], {"model": None, "effort": None, "advisor": None})
        self.assertEqual(hist[0]["model"], HAIKU)
        self.assertNotIn("advisor", hist[0]["model_usage"][HAIKU])

    def test_advisor_attribution_and_primary_model(self):
        call = {"models": {
            HAIKU: {"cost": 0.01, "tokens": [2, 4, 100, 50]},
            OPUS: {"cost": 0.50, "tokens": [500, 20, 0, 0]}}, "advisor": OPUS}
        # Advisor out-costs the executor; primary `model` must be the executor.
        _mock_claude_running_total(self.bindir, [call])
        result = self._run(1)
        rec = self._iters(result)[0]
        self.assertTrue(rec["model_usage"][OPUS]["advisor"])
        self.assertNotIn("advisor", rec["model_usage"][HAIKU])
        self.assertEqual(rec["model"], HAIKU)
        self.assertAlmostEqual(rec["model_usage"][OPUS]["cost_usd"], 0.50, places=6)

    def test_missing_model_usage_does_not_fail_iteration(self):
        _mock_claude_running_total(
            self.bindir, [_rt_call(0.10)], drop_model_usage=True)
        result = self._run(1)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        rec = self._iters(result)[0]
        self.assertEqual(rec["model_usage"], {})
        self.assertIsNone(rec["model"])
        self.assertAlmostEqual(rec["cost_usd"], 0.10, places=6)


class GoalDriverAccountingTests(_GoalTargetMixin, unittest.TestCase):
    """AC4 — the goal driver records its single invocation."""

    def setUp(self):
        self._setup_target(_passing_oracle())

    def _event(self):
        ev = _goal_result_event(subtype="success", cost=0.40, session_id="goal-s")
        ev["usage"] = {
            "input_tokens": 2, "output_tokens": 4,
            "cache_read_input_tokens": 100, "cache_creation_input_tokens": 50,
            "iterations": [{"type": "advisor_message", "model": OPUS}]}
        ev["modelUsage"] = {
            HAIKU: {"costUSD": 0.10, "inputTokens": 2, "outputTokens": 4,
                    "cacheReadInputTokens": 100, "cacheCreationInputTokens": 50},
            OPUS: {"costUSD": 0.30, "inputTokens": 9, "outputTokens": 1}}
        return ev

    def test_state_and_summary_gain_accounting(self):
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_PASS_SENTINEL, result_event=self._event()))
        result = _run_goal(self.target, "--prompt", "x", mock_bindir=self.bindir,
                           extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        for blob in (self._summary(result), self._state()):
            self.assertEqual(blob["session_id"], "goal-s")
            self.assertEqual(blob["cost_basis"], "reported")
            self.assertEqual(blob["usage"]["cache_read_input_tokens"], 100)
            self.assertEqual(blob["model"], HAIKU)
            self.assertTrue(blob["model_usage"][OPUS]["advisor"])
            self.assertEqual(
                blob["requested"], {"model": None, "effort": None, "advisor": None})
            self.assertAlmostEqual(blob["cumulative_cost_usd"], 0.40, places=6)
            self.assertNotIn("agent", blob)

    _ACCT_KEYS = ("session_id", "usage", "model_usage", "model", "requested",
                  "cost_basis")

    def test_goal_unavailable_exit_carries_accounting(self):
        ev = self._event()
        ev["num_turns"] = 0
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(
            assistant_text=GOAL_HOOK_REFUSAL, result_event=ev))
        result = _run_goal(self.target, "--prompt", "x", mock_bindir=self.bindir,
                           extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(
            self._summary(result)["terminal_reason"], "goal_unavailable",
            msg=result.stdout)
        for blob in (self._summary(result), self._state()):
            for k in self._ACCT_KEYS:
                self.assertIn(k, blob)
            self.assertEqual(blob["session_id"], "goal-s")
            self.assertEqual(blob["cost_basis"], "reported")

    def test_refusal_before_invoke_has_no_accounting_keys(self):
        # Negative guard (cannot fail when the feature is removed): a path that
        # never invokes Claude keeps today's summary shape.
        _mock_claude_goal(self.bindir, _goal_stream_jsonl(result_event=self._event()))
        result = _run_goal(
            self.target, "--prompt", "x", "--resume", "20260101T000000-abcd",
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 2, msg=result.stdout)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "goal_resume_unsupported")
        for k in self._ACCT_KEYS:
            self.assertNotIn(k, summary)


class AccountingHelperUnitTests(unittest.TestCase):
    """Pure helpers: `_normalize_model_usage`, `_advisor_model_ids`,
    `_iteration_cost_delta`, `_iteration_accounting`."""

    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("loop", LOOP)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def _mu(self, cost, i=2, o=4, cr=100, cc=50):
        return {"costUSD": cost, "inputTokens": i, "outputTokens": o,
                "cacheReadInputTokens": cr, "cacheCreationInputTokens": cc}

    def test_normalize_maps_and_zeroes_bad_values(self):
        out = self.m._normalize_model_usage({"modelUsage": {
            "a": {"costUSD": "x", "inputTokens": True, "outputTokens": 7},
            "b": "junk"}})
        self.assertEqual(out["a"], {
            "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 7,
            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0})
        self.assertEqual(out["b"]["output_tokens"], 0)

    def test_normalize_non_dict_is_empty(self):
        self.assertEqual(self.m._normalize_model_usage({"modelUsage": [1]}), {})
        self.assertEqual(self.m._normalize_model_usage({}), {})

    def test_advisor_ids(self):
        data = {"usage": {"iterations": [
            {"type": "message"},
            {"type": "advisor_message", "model": OPUS},
            {"type": "advisor_message"}, "junk"]}}
        self.assertEqual(self.m._advisor_model_ids(data), {OPUS})
        self.assertEqual(self.m._advisor_model_ids({"usage": 3}), set())

    def _data(self, total, mu, usage):
        return {"session_id": "S", "total_cost_usd": total,
                "modelUsage": mu, "usage": usage}

    _USAGE = {"input_tokens": 3, "output_tokens": 5,
              "cache_read_input_tokens": 200, "cache_creation_input_tokens": 60}

    def _snap(self):
        return {"session_id": "S", "total_cost_usd": 0.10,
                "model_usage": {HAIKU: self._mu(0.10)}}

    def test_delta_proven(self):
        data = self._data(0.30, {HAIKU: self._mu(0.30, 5, 9, 300, 110)}, self._USAGE)
        cost, mu, basis = self.m._iteration_cost_delta(
            data, resumed_session_id="S", snapshot=self._snap())
        self.assertEqual(basis, "session_delta")
        self.assertAlmostEqual(cost, 0.20, places=6)
        self.assertEqual(mu[HAIKU]["input_tokens"], 3)
        self.assertAlmostEqual(mu[HAIKU]["cost_usd"], 0.20, places=6)

    def test_delta_drops_models_not_used_this_invocation(self):
        data = self._data(0.30, {HAIKU: self._mu(0.30, 5, 9, 300, 110),
                                 OPUS: self._mu(0.05, 7, 7, 7, 7)}, self._USAGE)
        snap = self._snap()
        snap["model_usage"][OPUS] = self._mu(0.05, 7, 7, 7, 7)
        _, mu, basis = self.m._iteration_cost_delta(
            data, resumed_session_id="S", snapshot=snap)
        self.assertEqual(basis, "session_delta")
        self.assertEqual(list(mu), [HAIKU])

    def test_returned_session_id_must_match_resumed_id(self):
        # Isolates the `returned_id == resumed_session_id` conjunct: resumed S,
        # snapshot for S, token identity satisfied, but Claude returned T.
        data = self._data(0.30, {HAIKU: self._mu(0.30, 5, 9, 300, 110)}, self._USAGE)
        data["session_id"] = "T"
        cost, _, basis = self.m._iteration_cost_delta(
            data, resumed_session_id="S", snapshot=self._snap())
        self.assertEqual(basis, "reported")
        self.assertAlmostEqual(cost, 0.30, places=6)

    def test_cost_below_snapshot_falls_back_to_reported(self):
        data = self._data(0.05, {HAIKU: self._mu(0.05, 5, 9, 300, 110)}, self._USAGE)
        cost, _, basis = self.m._iteration_cost_delta(
            data, resumed_session_id="S", snapshot=self._snap())
        self.assertEqual(basis, "reported")
        self.assertAlmostEqual(cost, 0.05, places=6)

    def test_non_finite_numbers_count_as_absent(self):
        nan, inf = float("nan"), float("inf")
        out = self.m._normalize_model_usage({"modelUsage": {
            "a": {"costUSD": nan, "inputTokens": inf, "outputTokens": -inf,
                  "cacheReadInputTokens": 3}}})
        self.assertEqual(out["a"], {
            "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0,
            "cache_read_input_tokens": 3, "cache_creation_input_tokens": 0})
        rec = self.m._iteration_accounting(
            {"usage": {"input_tokens": nan, "output_tokens": inf}},
            agent="runner", cost_usd=0.0, cost_basis="reported",
            model_usage={}, requested={})
        self.assertEqual(rec["usage"]["input_tokens"], 0)
        self.assertEqual(rec["usage"]["output_tokens"], 0)

    def test_null_session_id_is_empty_string(self):
        rec = self.m._iteration_accounting(
            {"session_id": None}, agent="runner", cost_usd=0.0,
            cost_basis="reported", model_usage={}, requested={})
        self.assertEqual(rec["session_id"], "")

    def test_breadcrumb_suppressed_off_claude_host(self):
        w = self.m._warn_reported_fallback
        self.assertTrue(w("S", "reported", self.m.HOST_CLAUDE))
        self.assertFalse(w("S", "reported", "copilot"))
        self.assertFalse(w("S", "session_delta", self.m.HOST_CLAUDE))
        self.assertFalse(w(None, "reported", self.m.HOST_CLAUDE))

    def test_fallbacks_are_reported(self):
        data = self._data(0.30, {HAIKU: self._mu(0.30, 5, 9, 300, 110)}, self._USAGE)
        for kwargs in (
            {"resumed_session_id": None, "snapshot": self._snap()},
            {"resumed_session_id": "S", "snapshot": None},
            {"resumed_session_id": "T", "snapshot": self._snap()},
            {"resumed_session_id": "S",
             "snapshot": {**self._snap(), "session_id": "T"}},
        ):
            cost, mu, basis = self.m._iteration_cost_delta(data, **kwargs)
            self.assertEqual(basis, "reported", msg=kwargs)
            self.assertAlmostEqual(cost, 0.30, places=6)
            self.assertEqual(mu[HAIKU]["input_tokens"], 5)

    def test_unproven_when_tokens_below_identity(self):
        data = self._data(0.30, {HAIKU: self._mu(0.30, 3, 5, 200, 60)}, self._USAGE)
        _, _, basis = self.m._iteration_cost_delta(
            data, resumed_session_id="S", snapshot=self._snap())
        self.assertEqual(basis, "reported")

    def test_accounting_record_shape(self):
        data = self._data(0.30, {
            HAIKU: self._mu(0.10), OPUS: self._mu(0.10)},
            {**self._USAGE, "iterations": [
                {"type": "advisor_message", "model": OPUS}]})
        mu = self.m._normalize_model_usage(data)
        req = {"model": None, "effort": None, "advisor": None}
        rec = self.m._iteration_accounting(
            data, agent="runner", cost_usd=0.2, cost_basis="session_delta",
            model_usage=mu, requested=req)
        self.assertEqual(rec["cost_basis"], "session_delta")
        self.assertEqual(rec["agent"], "runner")
        self.assertEqual(rec["session_id"], "S")
        self.assertEqual(rec["model"], HAIKU)  # tie -> first non-advisor entry
        self.assertTrue(rec["model_usage"][OPUS]["advisor"])
        goal = self.m._iteration_accounting(
            data, agent=None, cost_usd=None, cost_basis="reported",
            model_usage=mu, requested=req)
        self.assertNotIn("agent", goal)
        self.assertNotIn("cost_usd", goal)

    def test_model_null_when_only_advisor(self):
        data = self._data(0.1, {OPUS: self._mu(0.1)}, {
            "iterations": [{"type": "advisor_message", "model": OPUS}]})
        rec = self.m._iteration_accounting(
            data, agent="runner", cost_usd=0.1, cost_basis="reported",
            model_usage=self.m._normalize_model_usage(data), requested={})
        self.assertIsNone(rec["model"])


# ============================================================================
# Slice 038-02 — role model placement (`--models` / plan `models`)
# ============================================================================

_SPLIT_BLOCK = {"runner": {"model": "sonnet"}, "judge": {"model": "opus"}}


def _models_arg(block) -> str:
    return json.dumps(block)


class ModelsValidationUnitTests(unittest.TestCase):
    """AC1/AC2 — the shared validator and the flag loader (pure)."""

    def setUp(self):
        self.m = _load_loop_module()

    def _ok(self, block, **kw):
        norm, err = self.m._validate_models(block, **kw)
        self.assertIsNone(err, msg=err)
        return norm

    def _bad(self, block, **kw):
        norm, err = self.m._validate_models(block, **kw)
        self.assertIsNone(norm)
        self.assertTrue(err)
        return err

    def test_valid_block_normalizes_and_drops_inherit(self):
        norm = self._ok({
            "runner": {"model": "sonnet", "effort": "inherit", "advisor": "opus"},
            "judge": {"model": "inherit"}})
        self.assertEqual(norm, {
            "runner": {"model": "sonnet", "advisor": "opus"}, "judge": {}})

    def test_empty_block_and_missing_roles_are_valid(self):
        self.assertEqual(self._ok({}), {"runner": {}, "judge": {}})
        self.assertEqual(
            self._ok({"judge": {"effort": "max"}}),
            {"runner": {}, "judge": {"effort": "max"}})

    def test_every_effort_level_accepted(self):
        for level in ("low", "medium", "high", "xhigh", "max", "inherit"):
            self._ok({"runner": {"effort": level}})

    def test_model_charset_accepts_real_ids(self):
        for model in ("sonnet", "claude-opus-5-5", "claude-opus-5-5[1m]",
                      "vendor/model:v1.2_x"):
            self._ok({"runner": {"model": model}})

    def test_refusals(self):
        for bad in (
            [], "x", 3, None,                                  # non-object block
            {"orchestrator": {}},                              # unknown top key
            {"runner": []}, {"runner": "sonnet"},              # non-object role
            {"runner": {"temperature": "1"}},                  # unknown role key
            {"runner": {"model": 3}}, {"runner": {"model": None}},
            {"runner": {"model": True}}, {"judge": {"advisor": ["a"]}},
            {"runner": {"effort": "turbo"}}, {"runner": {"effort": ""}},
            {"runner": {"effort": "HIGH"}},
            {"runner": {"model": "-bad"}}, {"runner": {"model": "a b"}},
            {"runner": {"model": ""}}, {"judge": {"advisor": "x y"}},
            {"judge": {"advisor": "--evil"}}, {"runner": {"model": "a\nb"}},
            {"runner": {"model": "opus\n"}},
        ):
            with self.subTest(bad=bad):
                self._bad(bad)

    def test_escalation_key_gated_by_allow_escalation(self):
        # 038-03 flips this on; in 038-02 `escalation` is an unknown key.
        block = {"escalation": [{"model": "opus"}]}
        self._bad(block)
        self._bad(block, allow_escalation=False)
        self.assertEqual(
            self._ok(block, allow_escalation=True)["escalation"],
            [{"model": "opus"}])

    def test_load_models_arg_inline_and_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "m.json"
            f.write_text(json.dumps(_SPLIT_BLOCK))
            self.assertEqual(
                self.m._load_models_arg(json.dumps(_SPLIT_BLOCK)),
                (_SPLIT_BLOCK, None))
            self.assertEqual(
                self.m._load_models_arg("  " + json.dumps(_SPLIT_BLOCK)),
                (_SPLIT_BLOCK, None))
            self.assertEqual(self.m._load_models_arg(str(f)), (_SPLIT_BLOCK, None))
            for bad in (str(Path(d) / "missing.json"), "{not json"):
                block, err = self.m._load_models_arg(bad)
                self.assertIsNone(block)
                self.assertTrue(err)
            f.write_text("{bad")
            self.assertTrue(self.m._load_models_arg(str(f))[1])

    def test_role_args_fixed_order_and_empty(self):
        self.assertEqual(self.m._role_args({}), [])
        self.assertEqual(self.m._role_args(None), [])
        self.assertEqual(
            self.m._role_args({"advisor": "a", "effort": "high", "model": "m"}),
            ["--model", "m", "--effort", "high", "--advisor", "a"])

    def test_mark_requested_advisor_signals(self):
        mu = {OPUS: {"cost_usd": 1.0}, HAIKU: {"cost_usd": 0.1}}
        marked = self.m._mark_requested_advisor(mu, "opus", "haiku")
        self.assertTrue(marked[OPUS]["advisor"])
        self.assertNotIn("advisor", marked[HAIKU])
        self.assertNotIn("advisor", mu[OPUS])  # input not mutated
        # exact id (with an explicit own model)
        self.assertTrue(
            self.m._mark_requested_advisor(mu, OPUS, "haiku")[OPUS]["advisor"])
        # an inherited model disables the second signal entirely
        self.assertNotIn(
            "advisor", self.m._mark_requested_advisor(mu, OPUS, None)[OPUS])
        # a substring that is not a `-`-delimited token does not match
        self.assertNotIn(
            "advisor", self.m._mark_requested_advisor(mu, "opu", None)[OPUS])
        # the id also matches the role's own requested model -> not marked
        self.assertNotIn(
            "advisor", self.m._mark_requested_advisor(mu, "opus", "opus")[OPUS])
        # no requested advisor -> nothing marked
        self.assertNotIn(
            "advisor", self.m._mark_requested_advisor(mu, None, None)[OPUS])

    def test_inherited_model_disables_second_advisor_signal(self):
        # With an inherited model the executor's own `claude-opus-*` entry would
        # share the advisor's family token; only advisor_message may mark it.
        mu = {OPUS: {"cost_usd": 1.0}}
        data = {"session_id": "S", "usage": {}}
        rec = self.m._iteration_accounting(
            data, agent="runner", cost_usd=1.0, cost_basis="reported",
            model_usage=mu,
            requested={"model": None, "effort": None, "advisor": "opus"})
        self.assertNotIn("advisor", rec["model_usage"][OPUS])
        self.assertEqual(rec["model"], OPUS)
        # ... while the advisor_message signal still works.
        data["usage"] = {"iterations": [
            {"type": "advisor_message", "model": OPUS}]}
        rec = self.m._iteration_accounting(
            data, agent="runner", cost_usd=1.0, cost_basis="reported",
            model_usage=mu,
            requested={"model": None, "effort": None, "advisor": "opus"})
        self.assertTrue(rec["model_usage"][OPUS]["advisor"])

    def test_load_models_arg_clear_errors(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "m.json"
            f.write_bytes(b"\xff\xfe\x00bad")
            block, err = self.m._load_models_arg(str(f))
            self.assertIsNone(block)
            self.assertIn("unreadable", err)
            f.write_text("[1]")
            block, err = self.m._load_models_arg(str(f))
            self.assertIsNone(block)
            self.assertIn("must be a JSON object", err)
        block, err = self.m._load_models_arg("[1]")
        self.assertIsNone(block)
        self.assertIn("must be a JSON object", err)
        self.assertNotIn("unreadable", err)

    def test_reported_total_cost_ignores_non_finite_and_strings(self):
        for bad in (float("nan"), float("inf"), "0.5", "nan", True, [1], None):
            with self.subTest(bad=bad):
                self.assertEqual(
                    self.m._reported_total_cost({"total_cost_usd": bad}), 0.0)
        self.assertEqual(
            self.m._reported_total_cost({"total_cost_usd": 0.25}), 0.25)
        self.assertEqual(
            self.m._reported_total_cost({"total_cost_usd": 2}), 2.0)

    def test_empty_snapshot_model_usage_falls_back_to_reported(self):
        data = {"session_id": "S", "total_cost_usd": 0.30,
                "modelUsage": {HAIKU: {"costUSD": 0.30, "inputTokens": 5}},
                "usage": {"input_tokens": 1}}
        snap = {"session_id": "S", "total_cost_usd": 0.10, "model_usage": {}}
        cost, _mu, basis = self.m._iteration_cost_delta(
            data, resumed_session_id="S", snapshot=snap)
        self.assertEqual(basis, "reported")
        self.assertAlmostEqual(cost, 0.30, places=6)

    def test_accounting_second_advisor_signal_recomputes_model(self):
        data = {"session_id": "S", "total_cost_usd": 1.1, "usage": {}}
        mu = {OPUS: {"cost_usd": 1.0, "input_tokens": 0, "output_tokens": 0,
                     "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
              HAIKU: {"cost_usd": 0.1, "input_tokens": 0, "output_tokens": 0,
                      "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}
        rec = self.m._iteration_accounting(
            data, agent="runner", cost_usd=1.1, cost_basis="reported",
            model_usage=mu,
            requested={"model": "haiku", "effort": None, "advisor": "opus"})
        self.assertTrue(rec["model_usage"][OPUS]["advisor"])
        self.assertEqual(rec["model"], HAIKU)
        self.assertEqual(rec["requested"]["advisor"], "opus")


class ModelsRefusalTests(_AccountingTarget, unittest.TestCase):
    """AC2 — fail-closed before any run dir / state / claude call."""

    def setUp(self):
        self._setup_acct()
        _mock_claude_running_total(self.bindir, [_rt_call(0.10)])

    def _assert_refused(self, result, reason):
        self.assertEqual(result.returncode, 2, msg=result.stdout + result.stderr)
        self.assertEqual(_stdout_json_lines(result.stdout)[-1]["terminal_reason"], reason)
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])
        self.assertEqual(_read_args_log(self.bindir / "args.log"), [])

    def test_bad_flag_blocks_refuse_models_invalid(self):
        for bad in (
            '{"runner": {"effort": "turbo"}}', '{"nope": {}}', '{"runner": 3}',
            '{"runner": {"model": "-x"}}', '{"runner": {"model": 5}}',
            '[1]', '{bad json',
        ):
            with self.subTest(bad=bad):
                result = self._run(1, "--models", bad)
                self._assert_refused(result, "models_invalid")

    def test_unreadable_models_file_refuses(self):
        result = self._run(1, "--models", str(self.target / "absent.json"))
        self._assert_refused(result, "models_invalid")

    def test_bad_models_file_contents_refuse(self):
        f = self.target.parent / "m.json"
        f.write_text('{"runner": {"effort": "turbo"}}')
        self._assert_refused(self._run(1, "--models", str(f)), "models_invalid")

    def test_non_utf8_models_file_refuses_without_traceback(self):
        f = self.target.parent / "m.json"
        f.write_bytes(b"\xff\xfe\x00{")
        result = self._run(1, "--models", str(f))
        self._assert_refused(result, "models_invalid")
        self.assertNotIn("Traceback", result.stderr)

    def test_non_object_json_file_says_so(self):
        f = self.target.parent / "m.json"
        f.write_text("[1]")
        result = self._run(1, "--models", str(f))
        self._assert_refused(result, "models_invalid")
        self.assertIn("JSON object", result.stderr)

    def test_inline_array_says_must_be_object_not_unreadable(self):
        result = self._run(1, "--models", "[1]")
        self._assert_refused(result, "models_invalid")
        self.assertIn("must be a JSON object", result.stderr)
        self.assertNotIn("unreadable", result.stderr)

    def test_invalid_persisted_models_refuses_resume_unchanged(self):
        self._run(1)
        run_id = _find_only_run_id(self.target)
        sp = _state_path(self.target, run_id)
        state = json.loads(sp.read_text())
        state["models"] = {"runner": {"effort": "turbo"}}
        sp.write_text(json.dumps(state))
        before = _read_state(self.target, run_id)
        n_calls = len(_read_args_log(self.bindir / "args.log"))
        result = _run_loop(
            self.target, "--resume", run_id, "--max-iterations", "2",
            "--cost-ceiling", "10", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 2, msg=result.stderr)
        self.assertEqual(
            _stdout_json_lines(result.stdout)[-1]["terminal_reason"],
            "models_invalid")
        self.assertEqual(len(_read_args_log(self.bindir / "args.log")), n_calls)
        self.assertEqual(_read_state(self.target, run_id), before)

    def test_valid_flag_replaces_invalid_persisted_models_on_resume(self):
        self._run(1)
        run_id = _find_only_run_id(self.target)
        sp = _state_path(self.target, run_id)
        state = json.loads(sp.read_text())
        state["models"] = "garbage"
        sp.write_text(json.dumps(state))
        result = _run_loop(
            self.target, "--resume", run_id, "--max-iterations", "2",
            "--cost-ceiling", "10", "--models", _models_arg(_SPLIT_BLOCK),
            mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_bad_plan_models_refuses_plan_value_invalid(self):
        plan = _compiled_plan(driver="loop")
        plan["models"] = {"runner": {"effort": "turbo"}}
        path = _write_plan(self.target.parent, plan)
        result = self._run(1, "--plan", str(path))
        self._assert_refused(result, "plan_value_invalid")

    def test_bad_plan_models_refuses_even_when_flag_overrides(self):
        plan = _compiled_plan(driver="loop")
        plan["models"] = "sonnet"
        path = _write_plan(self.target.parent, plan)
        result = self._run(1, "--plan", str(path), "--models", _models_arg(_SPLIT_BLOCK))
        self._assert_refused(result, "plan_value_invalid")

    def test_bad_flag_refuses_on_resume_too(self):
        self._run(1)
        run_id = _find_only_run_id(self.target)
        before = _read_state(self.target, run_id)
        n_calls = len(_read_args_log(self.bindir / "args.log"))
        result = _run_loop(
            self.target, "--resume", run_id, "--models", '{"runner": {"effort": "x"}}',
            mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(_read_args_log(self.bindir / "args.log")), n_calls)
        self.assertEqual(_read_state(self.target, run_id), before)


class RoleArgvTests(_AccountingTarget, unittest.TestCase):
    """AC3 — role fields reach the argv; no config leaves argv untouched."""

    def setUp(self):
        self._setup_acct()
        _mock_claude_running_total(self.bindir, [_rt_call(0.10)])

    def test_each_role_gets_its_own_flags_in_fixed_order(self):
        block = {
            "runner": {"model": "sonnet", "effort": "high", "advisor": "opus"},
            "judge": {"model": "opus", "effort": "xhigh"}}
        result = self._run(2, "--models", _models_arg(block))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        runner, judge = _read_args_log(self.bindir / "args.log")
        self.assertEqual(runner[runner.index("--model"):runner.index("--model") + 6],
                         ["--model", "sonnet", "--effort", "high",
                          "--advisor", "opus"])
        self.assertEqual(_find_flag_value(runner, "--agent"), "runner")
        self.assertEqual(judge[judge.index("--model"):judge.index("--model") + 4],
                         ["--model", "opus", "--effort", "xhigh"])
        self.assertNotIn("--advisor", judge)
        self.assertEqual(_find_flag_value(judge, "--agent"), "judge")
        self.assertLess(runner.index("--max-budget-usd"), runner.index("--model"))

    def test_inherited_fields_add_no_flag(self):
        block = {"runner": {"model": "sonnet", "effort": "inherit"}}
        self._run(2, "--models", _models_arg(block))
        runner, judge = _read_args_log(self.bindir / "args.log")
        self.assertIn("--model", runner)
        self.assertNotIn("--effort", runner)
        for flag in ("--model", "--effort", "--advisor"):
            self.assertNotIn(flag, judge)

    def test_no_config_argv_is_byte_identical(self):
        # Negative guard: with no block (or an all-inherit block) the argv is the
        # pre-038-02 shape - same tokens, none of the new flags.
        self._run(2)
        base = _read_args_log(self.bindir / "args.log")
        (self.bindir / "args.log").unlink()
        (self.bindir / "mockstate.json").unlink()
        self._run(2, "--models",
                  _models_arg({"runner": {"model": "inherit"}, "judge": {}}))
        inherit = _read_args_log(self.bindir / "args.log")
        self.assertEqual(len(base), 2)
        self.assertEqual(base, inherit)
        for argv in base:
            for flag in ("--model", "--effort", "--advisor"):
                self.assertNotIn(flag, argv)
            self.assertEqual(argv[:3], ["-p", "--output-format", "json"])


class JudgeSplitTests(_AccountingTarget, unittest.TestCase):
    """AC4 — a configured run gives the judge a fresh session; none = shared."""

    def setUp(self):
        self._setup_acct()
        self.calls = [_rt_call(0.10), _rt_call(0.20), _rt_call(0.30), _rt_call(0.40)]

    def test_split_judge_omits_resume_runner_keeps_it(self):
        _mock_claude_running_total(self.bindir, self.calls)
        result = self._run(4, "--models", _models_arg(_SPLIT_BLOCK))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        argvs = _read_args_log(self.bindir / "args.log")
        agents = [_find_flag_value(a, "--agent") for a in argvs]
        self.assertEqual(agents, ["runner", "judge", "runner", "judge"])
        self.assertNotIn("--resume", argvs[0])
        self.assertNotIn("--resume", argvs[1])           # judge: fresh
        self.assertEqual(_find_flag_value(argvs[2], "--resume"), "sess-1")
        self.assertNotIn("--resume", argvs[3])           # judge: fresh again

    def test_judge_never_moves_runner_session_or_snapshot(self):
        _mock_claude_running_total(self.bindir, self.calls)
        self._run(4, "--models", _models_arg(_SPLIT_BLOCK))
        state = _read_state(self.target, _find_only_run_id(self.target))
        hist = state["oracle_score_history"]
        runner_sids = [h["session_id"] for h in hist if h["agent"] == "runner"]
        judge_sids = [h["session_id"] for h in hist if h["agent"] == "judge"]
        # Runner turns share one session; each judge has its own, recorded.
        self.assertEqual(runner_sids, ["sess-1", "sess-1"])
        self.assertEqual(judge_sids, ["sess-2", "sess-4"])
        self.assertEqual(state["current_session_id"], "sess-1")
        self.assertEqual(state["current_session_usage_snapshot"]["session_id"], "sess-1")

    def test_judge_cost_basis_reported_and_costs_exact(self):
        _mock_claude_running_total(self.bindir, self.calls)
        self._run(4, "--models", _models_arg(_SPLIT_BLOCK))
        hist = _read_state(
            self.target, _find_only_run_id(self.target))["oracle_score_history"]
        self.assertEqual(
            [h["cost_basis"] for h in hist],
            ["reported", "reported", "session_delta", "reported"])
        # runner turn 3 is a delta against the RUNNER snapshot (0.10 + 0.30).
        self.assertEqual([round(h["cost_usd"], 6) for h in hist],
                         [0.10, 0.20, 0.30, 0.40])

    def test_split_no_fallback_warning_for_fresh_judge(self):
        _mock_claude_running_total(self.bindir, self.calls)
        result = self._run(4, "--models", _models_arg(_SPLIT_BLOCK))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        argvs = _read_args_log(self.bindir / "args.log")
        # Red if the split is removed: a shared judge resumes the runner session.
        self.assertNotIn("--resume", argvs[1])
        self.assertNotIn("cost basis fell back", result.stderr)

    def test_no_block_shares_one_session_as_today(self):
        # Negative guard: shared-lane behaviour is unchanged without a block.
        _mock_claude_running_total(self.bindir, self.calls)
        self._run(3)
        argvs = _read_args_log(self.bindir / "args.log")
        self.assertNotIn("--resume", argvs[0])
        self.assertEqual(_find_flag_value(argvs[1], "--resume"), "sess-1")
        self.assertEqual(_find_flag_value(argvs[2], "--resume"), "sess-1")

    def test_all_inherit_block_is_not_configured(self):
        _mock_claude_running_total(self.bindir, self.calls)
        self._run(3, "--models", _models_arg(
            {"runner": {"model": "inherit"}, "judge": {"effort": "inherit"}}))
        argvs = _read_args_log(self.bindir / "args.log")
        self.assertEqual(_find_flag_value(argvs[1], "--resume"), "sess-1")

    def test_runner_only_block_still_splits_the_judge(self):
        _mock_claude_running_total(self.bindir, self.calls)
        self._run(3, "--models", _models_arg({"runner": {"model": "sonnet"}}))
        argvs = _read_args_log(self.bindir / "args.log")
        self.assertNotIn("--resume", argvs[1])
        self.assertEqual(_find_flag_value(argvs[2], "--resume"), "sess-1")

    def test_state_persists_resolved_block(self):
        _mock_claude_running_total(self.bindir, self.calls)
        self._run(1, "--models", _models_arg(
            {"runner": {"model": "sonnet", "effort": "inherit"}}))
        state = _read_state(self.target, _find_only_run_id(self.target))
        self.assertEqual(
            state["models"], {"runner": {"model": "sonnet"}, "judge": {}})

    def test_no_block_state_models_is_null(self):
        _mock_claude_running_total(self.bindir, self.calls)
        self._run(1)
        state = _read_state(self.target, _find_only_run_id(self.target))
        self.assertIsNone(state["models"])


class ModelsSourcePrecedenceTests(_AccountingTarget, unittest.TestCase):
    """AC1 — flag > plan, block-level; inline JSON or a file."""

    def setUp(self):
        self._setup_acct()
        _mock_claude_running_total(self.bindir, [_rt_call(0.10)])

    def _plan(self, models):
        plan = _compiled_plan(driver="loop", max_iterations=2, plateau_window=0)
        if models is not None:
            plan["models"] = models
        return _write_plan(self.target.parent, plan)

    def test_plan_block_applies(self):
        path = self._plan({"runner": {"model": "sonnet"}, "judge": {"model": "opus"}})
        result = _run_loop(
            self.target, "--plan", str(path), "--prompt", "x",
            "--cost-ceiling", "10", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        runner, judge = _read_args_log(self.bindir / "args.log")
        self.assertEqual(_find_flag_value(runner, "--model"), "sonnet")
        self.assertEqual(_find_flag_value(judge, "--model"), "opus")
        self.assertNotIn("--resume", judge)

    def test_flag_replaces_plan_block_entirely_no_field_merge(self):
        path = self._plan({
            "runner": {"model": "sonnet", "effort": "high"},
            "judge": {"model": "opus"}})
        result = _run_loop(
            self.target, "--plan", str(path), "--prompt", "x", "--cost-ceiling", "10",
            "--models", _models_arg({"runner": {"advisor": "opus"}}),
            mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        runner, judge = _read_args_log(self.bindir / "args.log")
        self.assertEqual(_find_flag_value(runner, "--advisor"), "opus")
        self.assertNotIn("--model", runner)
        self.assertNotIn("--effort", runner)
        self.assertNotIn("--model", judge)

    def test_models_file_path(self):
        f = self.target.parent / "m.json"
        f.write_text(json.dumps({"runner": {"effort": "low"}}))
        self._run(1, "--models", str(f))
        (runner,) = _read_args_log(self.bindir / "args.log")
        self.assertEqual(_find_flag_value(runner, "--effort"), "low")

    def test_plan_without_models_and_no_flag_is_unchanged(self):
        path = self._plan(None)
        result = _run_loop(
            self.target, "--plan", str(path), "--prompt", "x",
            "--cost-ceiling", "10", mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        argvs = _read_args_log(self.bindir / "args.log")
        self.assertTrue(argvs)
        for argv in argvs:
            self.assertNotIn("--model", argv)


class ModelsResumeTests(_AccountingTarget, unittest.TestCase):
    """AC5 — resume replaces / keeps the persisted block."""

    def setUp(self):
        self._setup_acct()
        _mock_claude_running_total(
            self.bindir, [_rt_call(0.10), _rt_call(0.20), _rt_call(0.30),
                          _rt_call(0.40)])

    def _resume(self, n, run_id, *extra):
        return _run_loop(
            self.target, "--resume", run_id, "--max-iterations", str(n),
            "--cost-ceiling", "10", *extra, mock_bindir=self.bindir)

    def test_resume_keeps_persisted_block(self):
        self._run(1, "--models", _models_arg(_SPLIT_BLOCK))
        run_id = _find_only_run_id(self.target)
        result = self._resume(3, run_id)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        argvs = _read_args_log(self.bindir / "args.log")
        self.assertEqual(_find_flag_value(argvs[1], "--model"), "opus")  # judge
        self.assertNotIn("--resume", argvs[1])
        self.assertEqual(_find_flag_value(argvs[2], "--model"), "sonnet")
        self.assertEqual(_find_flag_value(argvs[2], "--resume"), "sess-1")
        self.assertEqual(
            _read_state(self.target, run_id)["models"],
            {"runner": {"model": "sonnet"}, "judge": {"model": "opus"}})

    def test_resume_flag_replaces_persisted_block_and_keeps_runner_session(self):
        self._run(1, "--models", _models_arg(_SPLIT_BLOCK))
        run_id = _find_only_run_id(self.target)
        new = {"runner": {"model": "haiku"}}
        self._resume(3, run_id, "--models", _models_arg(new))
        argvs = _read_args_log(self.bindir / "args.log")
        self.assertNotIn("--model", argvs[1])            # old judge model gone
        self.assertEqual(_find_flag_value(argvs[2], "--model"), "haiku")
        self.assertEqual(_find_flag_value(argvs[2], "--resume"), "sess-1")
        self.assertEqual(
            _read_state(self.target, run_id)["models"],
            {"runner": {"model": "haiku"}, "judge": {}})

    def test_resume_with_all_inherit_block_ends_the_split(self):
        self._run(1, "--models", _models_arg(_SPLIT_BLOCK))
        run_id = _find_only_run_id(self.target)
        self._resume(2, run_id, "--models", "{}")
        argvs = _read_args_log(self.bindir / "args.log")
        self.assertEqual(_find_flag_value(argvs[1], "--resume"), "sess-1")
        self.assertNotIn("--model", argvs[1])

    def test_old_state_without_models_resumes_with_no_block(self):
        self._run(1)
        run_id = _find_only_run_id(self.target)
        sp = _state_path(self.target, run_id)
        state = json.loads(sp.read_text())
        state.pop("models", None)
        sp.write_text(json.dumps(state))
        result = self._resume(2, run_id)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        argvs = _read_args_log(self.bindir / "args.log")
        self.assertEqual(_find_flag_value(argvs[1], "--resume"), "sess-1")
        self.assertNotIn("--model", argvs[1])
        self.assertIsNone(_read_state(self.target, run_id)["models"])


class RequestedAndAdvisorSignalTests(_AccountingTarget, unittest.TestCase):
    """AC7 — `requested` per role; advisor second signal; persisted block."""

    def setUp(self):
        self._setup_acct()

    def test_requested_names_each_roles_block(self):
        _mock_claude_running_total(self.bindir, [_rt_call(0.10)])
        block = {"runner": {"model": "sonnet", "advisor": "opus"},
                 "judge": {"effort": "max"}}
        result = self._run(2, "--models", _models_arg(block))
        runner, judge = self._iters(result)
        self.assertEqual(runner["requested"],
                         {"model": "sonnet", "effort": None, "advisor": "opus"})
        self.assertEqual(judge["requested"],
                         {"model": None, "effort": "max", "advisor": None})
        hist = _read_state(
            self.target, _find_only_run_id(self.target))["oracle_score_history"]
        self.assertEqual(hist[0]["requested"], runner["requested"])

    def test_no_block_requested_all_null(self):
        _mock_claude_running_total(self.bindir, [_rt_call(0.10)])
        result = self._run(1)
        self.assertEqual(self._iters(result)[0]["requested"],
                         {"model": None, "effort": None, "advisor": None})

    def test_requested_advisor_flags_model_usage_without_advisor_message(self):
        # No `advisor_message` iteration in usage: only the second signal can
        # mark the opus entry.
        call = {"models": {
            HAIKU: {"cost": 0.1, "tokens": [2, 4, 100, 50]},
            OPUS: {"cost": 0.9, "tokens": [3, 1, 0, 0]}}}
        _mock_claude_running_total(self.bindir, [call])
        block = {"runner": {"model": "haiku", "advisor": "opus"}}
        result = self._run(1, "--models", _models_arg(block))
        entry = self._iters(result)[0]
        self.assertTrue(entry["model_usage"][OPUS]["advisor"])
        self.assertNotIn("advisor", entry["model_usage"][HAIKU])
        self.assertEqual(entry["model"], HAIKU)

    def test_no_requested_advisor_leaves_model_usage_unmarked(self):
        # Negative guard: without a requested advisor the heuristic never fires.
        call = {"models": {
            HAIKU: {"cost": 0.1, "tokens": [2, 4, 100, 50]},
            OPUS: {"cost": 0.9, "tokens": [3, 1, 0, 0]}}}
        _mock_claude_running_total(self.bindir, [call])
        result = self._run(1)
        entry = self._iters(result)[0]
        self.assertNotIn("advisor", entry["model_usage"][OPUS])
        self.assertEqual(entry["model"], OPUS)


class GoalDriverModelsTests(_GoalTargetMixin, unittest.TestCase):
    """AC6 — runner block on the single goal invocation; judge note; background."""

    def setUp(self):
        self._setup_target(_passing_oracle())
        self.args_log = self.bindir.parent / "args.log"
        _mock_claude_goal(
            self.bindir, _goal_stream_jsonl(assistant_text=GOAL_PASS_SENTINEL),
            args_log=self.args_log)

    def _goal(self, *extra):
        return _run_goal(
            self.target, "--prompt", "x", *extra, mock_bindir=self.bindir,
            extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})

    def test_runner_block_reaches_goal_argv_and_requested(self):
        block = {"runner": {"model": "sonnet", "effort": "high", "advisor": "opus"}}
        result = self._goal("--models", _models_arg(block))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        (argv,) = _read_args_log(self.args_log)
        i = argv.index("--model")
        self.assertEqual(argv[i:i + 6], ["--model", "sonnet", "--effort", "high",
                                         "--advisor", "opus"])
        self.assertLess(argv.index("--max-turns"), i)
        for blob in (self._summary(result), self._state()):
            self.assertEqual(blob["requested"], {
                "model": "sonnet", "effort": "high", "advisor": "opus"})
        self.assertEqual(self._state()["models"]["runner"]["model"], "sonnet")

    def test_judge_block_ignored_with_one_note(self):
        block = {"runner": {"model": "sonnet"}, "judge": {"model": "opus"}}
        result = self._goal("--models", _models_arg(block))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            result.stderr.count("models.judge is ignored"), 1, msg=result.stderr)
        self.assertIn("ignored", result.stderr)
        (argv,) = _read_args_log(self.args_log)
        self.assertEqual(argv.count("--model"), 1)
        self.assertEqual(_find_flag_value(argv, "--model"), "sonnet")

    def test_background_parent_prints_judge_note(self):
        block = {"runner": {"model": "sonnet"}, "judge": {"model": "opus"}}
        result = _run_raw(
            self.target, "--background", "--prompt", "x", "--max-iterations", "2",
            "--models", _models_arg(block), mock_bindir=self.bindir,
            extra_env={"SERVO_CLAUDE_TIMEOUT": "30"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            result.stderr.count("models.judge is ignored"), 1, msg=result.stderr)
        _await_terminal_state(self.target)

    def test_background_without_judge_block_prints_no_note(self):
        result = _run_raw(
            self.target, "--background", "--prompt", "x", "--max-iterations", "2",
            "--models", _models_arg({"runner": {"model": "sonnet"}}),
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "30"})
        self.assertNotIn("models.judge", result.stderr)
        _await_terminal_state(self.target)

    def test_emit_routine_prompt_notes_models_not_carried(self):
        result = _run_raw(
            self.target, "--emit-routine-prompt", "--prompt", "x",
            "--models", _models_arg({"runner": {"model": "sonnet"}}),
            mock_bindir=self.bindir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(
            result.stderr.count("not carried into the Routine prompt"), 1,
            msg=result.stderr)

    def test_emit_routine_prompt_without_models_prints_no_note(self):
        result = _run_raw(
            self.target, "--emit-routine-prompt", "--prompt", "x",
            mock_bindir=self.bindir)
        self.assertNotIn("Routine prompt", result.stderr)

    def test_inherit_judge_block_prints_no_note(self):
        result = self._goal("--models", _models_arg(
            {"runner": {"model": "sonnet"}, "judge": {"model": "inherit"}}))
        self.assertNotIn("judge", result.stderr)

    def test_no_block_goal_argv_unchanged(self):
        # Negative guard.
        result = self._goal()
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        (argv,) = _read_args_log(self.args_log)
        for flag in ("--model", "--effort", "--advisor"):
            self.assertNotIn(flag, argv)
        self.assertNotIn("judge", result.stderr)

    def test_invalid_block_refused_under_goal(self):
        result = self._goal("--models", '{"runner": {"effort": "turbo"}}')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self._summary(result)["terminal_reason"], "models_invalid")
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])

    def test_background_forwards_block_to_detached_child(self):
        block = {"runner": {"model": "sonnet", "effort": "low"}}
        result = _run_raw(
            self.target, "--background", "--prompt", "x", "--max-iterations", "2",
            "--models", _models_arg(block), mock_bindir=self.bindir,
            extra_env={"SERVO_CLAUDE_TIMEOUT": "30"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        state = _await_terminal_state(self.target)
        self.assertEqual(state["terminal_reason"], "oracle_pass")
        self.assertEqual(state["models"], {"runner": {"model": "sonnet", "effort": "low"},
                                           "judge": {}})
        (argv,) = _read_args_log(self.args_log)
        self.assertEqual(_find_flag_value(argv, "--model"), "sonnet")
        self.assertEqual(_find_flag_value(argv, "--effort"), "low")

    def test_child_argv_forwards_compact_models_only_when_set(self):
        m = _load_loop_module()
        block = {"runner": {"model": "sonnet"}, "judge": {}}
        argv = m._build_detached_child_argv(
            Path("/tmp/t"), "RID", prompt="p", max_iterations=None,
            cost_ceiling=None, models=block)
        self.assertEqual(
            json.loads(argv[argv.index("--models") + 1]), block)
        self.assertNotIn(" ", argv[argv.index("--models") + 1])
        argv = m._build_detached_child_argv(
            Path("/tmp/t"), "RID", prompt="p", max_iterations=None,
            cost_ceiling=None)
        self.assertNotIn("--models", argv)



# ============================================================================
# Slice 038-03 — plateau escalation ladder
# ============================================================================

_LADDER = {"runner": {"model": "sonnet"}, "judge": {"model": "haiku"},
           "escalation": [{"effort": "high"}, {"model": "opus"}]}
_FLAT = _below_threshold_oracle(composite=0.2)


def _fail_on_flag_wrapper(bindir: Path, calls: list, flag_pair: str) -> Path:
    """Running-total mock that exits 1 when argv contains `flag_pair`."""
    _mock_claude_running_total(bindir, calls)
    real = (bindir / "claude").read_text()
    wrapped = real.replace(
        "exec '", f'case " $* " in *" {flag_pair} "*) echo refused >&2; exit 1;;'
        " esac\nexec '", 1)
    (bindir / "claude").write_text(wrapped)
    return bindir / "claude"


def _fail_on_call_wrapper(bindir: Path, calls: list, n: int) -> Path:
    """Running-total mock whose `n`-th real invocation exits 1."""
    _mock_claude_running_total(bindir, calls)
    real = (bindir / "claude").read_text()
    guard = (
        f"cnt='{bindir / 'wrapcount'}'\n"
        'k=$(cat "$cnt" 2>/dev/null || echo 0); k=$((k + 1)); echo $k > "$cnt"\n'
        f'if [ "$k" = "{n}" ]; then echo refused >&2; exit 1; fi\n')
    (bindir / "claude").write_text(real.replace("exec '", guard + "exec '", 1))
    return bindir / "claude"


_VERDICT_WRAP_PY = r'''
import json, os, subprocess, sys
d = os.path.dirname(os.path.abspath(__file__))
out = subprocess.run([sys.executable, os.path.join(d, "mock_rt.py")] + sys.argv[1:],
                     capture_output=True, text=True).stdout
if "--effort" in sys.argv and sys.argv[sys.argv.index("--effort") + 1] == "high":
    data = json.loads(out)
    data["result"] = "```verdict\nschema_version: 9\n```"
    out = json.dumps(data)
sys.stdout.write(out)
'''


def _bad_verdict_on_raised_rung(bindir: Path, calls: list) -> Path:
    _mock_claude_running_total(bindir, calls)
    (bindir / "wrap.py").write_text(_VERDICT_WRAP_PY)
    body = f"#!/usr/bin/env bash\nexec '{sys.executable}' '{bindir / 'wrap.py'}' \"$@\"\n"
    return _make_mock_claude(bindir, body)


class LadderConfigUnitTests(unittest.TestCase):
    """AC1 - the ladder block, cumulative fold, in-effect rule (pure)."""

    def setUp(self):
        self.m = _load_loop_module()

    def test_runner_config_folds_rungs_cumulatively(self):
        block = {"runner": {"model": "sonnet"},
                 "escalation": [{"effort": "high"}, {"model": "opus"},
                                {"advisor": "opus", "effort": "xhigh"}]}
        cfg = self.m._runner_config_at_rung
        self.assertEqual(cfg(block, 0), {"model": "sonnet"})
        self.assertEqual(cfg(block, 1), {"model": "sonnet", "effort": "high"})
        self.assertEqual(cfg(block, 2), {"model": "opus", "effort": "high"})
        self.assertEqual(cfg(block, 3), {
            "model": "opus", "effort": "xhigh", "advisor": "opus"})
        self.assertEqual(cfg(None, 2), {})
        self.assertEqual(cfg({"runner": {"model": "sonnet"}}, 5),
                         {"model": "sonnet"})

    def test_escalation_only_block_is_in_effect(self):
        ev = self.m._models_in_effect
        self.assertTrue(ev({"runner": {}, "judge": {},
                            "escalation": [{"effort": "high"}]}))
        self.assertFalse(ev({"runner": {}, "judge": {}, "escalation": []}))
        self.assertFalse(ev({"runner": {}, "judge": {}}))

    def test_pure_validator_accepts_and_normalizes_ladder(self):
        ok, err = self.m._validate_models(
            {"escalation": [{"effort": "high"}]}, allow_escalation=True)
        self.assertIsNone(err)
        self.assertEqual(ok["escalation"], [{"effort": "high"}])
        for bad in ({"escalation": "x"}, {"escalation": [{}]},
                    {"escalation": [{"temperature": "1"}]},
                    {"escalation": [{"effort": "turbo"}]},
                    {"escalation": [3]}):
            with self.subTest(bad=bad):
                self.assertIsNotNone(
                    self.m._validate_models(bad, allow_escalation=True)[1])

    def test_rung_plateau_without_a_ladder_is_the_plain_check(self):
        flat = [{"iteration": i, "composite": 0.2} for i in range(1, 5)]
        state = {"oracle_score_history": flat, "plateau_window": 3,
                 "models": {"runner": {"model": "sonnet"}},
                 "escalation_rung": 1, "escalation_history_start": None}
        self.assertTrue(self.m._rung_plateau(state))
        state["models"] = {"escalation": [{"effort": "high"}]}
        self.assertFalse(self.m._rung_plateau(state))   # window not open yet

    def test_best_composite_first_iteration_reaching_it(self):
        best = self.m._best_composite
        self.assertEqual(best([]), (None, None))
        self.assertEqual(best([{"iteration": 1, "composite": None}]),
                         (None, None))
        self.assertEqual(best([
            {"iteration": 1, "composite": 0.2}, {"iteration": 2, "composite": 0.4},
            {"iteration": 3, "composite": 0.4}]), (0.4, 2))

    def test_escalation_guard_arithmetic(self):
        guard = self.m._escalation_guard

        def st(max_it, ceiling=0.0, spent=0.0, costs=(0.5,)):
            return {"plateau_window": 3, "max_iterations": max_it,
                    "cost_ceiling_usd": ceiling, "cumulative_cost_usd": spent,
                    "oracle_score_history": [{"cost_usd": c} for c in costs]}
        # next iteration 5 is a runner -> needed 3; 6 is a judge -> needed 4
        self.assertTrue(guard(st(7), 4)[0])
        self.assertFalse(guard(st(6), 4)[0])
        self.assertTrue(guard(st(11), 7)[0])
        self.assertFalse(guard(st(10), 7)[0])
        ok, crumb = guard(st(5), 4)
        self.assertFalse(ok)
        self.assertIn("1 iteration(s) left, 3 needed", crumb)
        # cost: needs needed * max per-iteration cost (1.5 here)
        self.assertTrue(guard(st(7, 6.0, 4.5), 4)[0])
        ok, crumb = guard(st(7, 5.9, 4.5), 4)
        self.assertFalse(ok)
        self.assertIn("$1.4000 left, $1.5000 needed", crumb)
        # no ceiling (0) -> cost not consulted; missing cost_usd counts as 0
        self.assertTrue(guard(st(7, 0.0, 99.0), 4)[0])
        old = st(7, 1.0, 0.99)
        old["oracle_score_history"] = [{"iteration": 1}]
        self.assertTrue(guard(old, 4)[0])

    def test_prompt_escalation_section_only_when_given(self):
        a = self.m._assemble_iteration_prompt
        self.assertEqual(a("seed", None, None), "seed")
        self.assertNotIn("Escalation", a("seed", {"c": 1}, None))
        out = a("seed", {"c": 1}, {"schema_version": 1, "x": "y"}, {
            "rung": 2, "best_composite": 0.4, "best_iteration": 3,
            "composite": 0.3})
        self.assertIn("Escalation", out)
        self.assertIn("rung 2", out)
        self.assertIn("0.4 (iteration 3)", out)
        self.assertIn("Composite at escalation: 0.3", out)
        self.assertIn("Last oracle output", out)
        self.assertIn("Last agent verdict", out)


class LadderEscalationTests(_AccountingTarget, unittest.TestCase):
    """AC2/AC3/AC4/AC5 - escalate vs halt, fresh sessions, recording."""

    def setUp(self):
        self._setup_acct()
        _make_oracle(self.target, _FLAT)
        _mock_claude_running_total(self.bindir, [_rt_call(0.10)])

    def _ladder(self, n, block=_LADDER, *extra, ceiling="10.00"):
        return _run_loop(
            self.target, "--prompt", "x", "--max-iterations", str(n),
            "--cost-ceiling", ceiling, "--plateau-window", "3",
            "--models", _models_arg(block), *extra, mock_bindir=self.bindir)

    def _summary(self, result):
        return _stdout_json_lines(result.stdout)[-1]

    def _argvs(self):
        return _read_args_log(self.bindir / "args.log")

    def test_worked_example_escalates_at_4_and_7_and_halts_at_11(self):
        result = self._ladder(11)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")
        self.assertEqual(summary["iterations_completed"], 11)
        self.assertEqual(summary["escalation_rung"], 2)
        self.assertEqual(summary["escalation_rungs"], 2)
        state = _read_state(self.target, summary["run_id"])
        self.assertEqual(state["escalation_rung"], 2)
        self.assertEqual(
            [(e["rung"], e["at_iteration"], e["baseline_composite"])
             for e in state["escalation_events"]], [(1, 4, 0.2), (2, 7, 0.2)])
        self.assertEqual(state["escalation_events"][0]["runner"],
                         {"model": "sonnet", "effort": "high"})
        self.assertEqual(state["escalation_events"][1]["runner"],
                         {"model": "opus", "effort": "high"})
        rungs = [e["rung"] for e in state["oracle_score_history"]]
        self.assertEqual(rungs, [0] * 4 + [1] * 3 + [2] * 4)
        stdout_rungs = [ln["rung"] for ln in self._iters(result)]
        self.assertEqual(stdout_rungs, rungs)
        self.assertEqual(result.stderr.count("escalating to rung"), 2,
                         msg=result.stderr)
        self.assertIn("escalating to rung 1 of 2", result.stderr)
        # requested reflects the rung's runner config
        hist = state["oracle_score_history"]
        self.assertEqual(hist[4]["requested"], {
            "model": "sonnet", "effort": "high", "advisor": None})
        self.assertEqual(hist[8]["requested"], {
            "model": "opus", "effort": "high", "advisor": None})
        # no cap was raised
        self.assertEqual(state["max_iterations"], 11)
        self.assertEqual(state["cost_ceiling_usd"], 10.0)

    def test_argv_cumulative_fold_fresh_sessions_and_judge_unchanged(self):
        self._ladder(11)
        argvs = self._argvs()
        self.assertEqual(len(argvs), 11)

        def cfg(i):
            a = argvs[i - 1]
            return (_find_flag_value(a, "--model"),
                    _find_flag_value(a, "--effort"))
        self.assertEqual(cfg(1), ("sonnet", None))
        self.assertEqual(cfg(5), ("sonnet", "high"))       # effort-only rung
        self.assertEqual(cfg(9), ("opus", "high"))         # cumulative
        for i in (2, 4, 6, 8, 10):                          # judge never moves
            self.assertEqual(cfg(i), ("haiku", None))
            self.assertNotIn("--resume", argvs[i - 1])
        # rung's first runner iteration is a fresh session, then it resumes
        self.assertNotIn("--resume", argvs[4])             # iter 5
        self.assertEqual(_find_flag_value(argvs[6], "--resume"), "sess-5")
        self.assertNotIn("--resume", argvs[8])             # iter 9
        self.assertEqual(_find_flag_value(argvs[10], "--resume"), "sess-9")
        # iteration 3 still resumes the rung-0 session (control)
        self.assertEqual(_find_flag_value(argvs[2], "--resume"), "sess-1")

    def test_max_iterations_5_never_escalates(self):
        result = self._ladder(5)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")
        self.assertEqual(summary["iterations_completed"], 4)
        self.assertEqual(summary["escalation_rung"], 0)
        state = _read_state(self.target, summary["run_id"])
        self.assertEqual(state["escalation_events"], [])
        self.assertIn("1 iteration(s) left, 3 needed", result.stderr)
        self.assertEqual(result.stderr.count("no escalation rung started"), 1)
        self.assertNotIn("escalating to rung", result.stderr)

    def test_default_budget_never_turns_plateau_into_max_iterations(self):
        # Defaults: 5 iterations, window 3 -> plateau at 4, guard refuses.
        result = _run_loop(
            self.target, "--prompt", "x", "--plateau-window", "3",
            "--models", _models_arg(_LADDER), mock_bindir=self.bindir)
        self.assertEqual(self._summary(result)["terminal_reason"],
                         "oracle_plateau")

    def test_two_rung_ladder_needs_eleven_iterations(self):
        for n, rung, reason_iters in ((6, 0, 4), (7, 1, 7), (10, 1, 7)):
            with self.subTest(max_iterations=n):
                shutil.rmtree(self.target / ".servo" / "runs", ignore_errors=True)
                (self.bindir / "mockstate.json").unlink(missing_ok=True)
                (self.bindir / "args.log").unlink(missing_ok=True)
                summary = self._summary(self._ladder(n))
                self.assertEqual(summary["terminal_reason"], "oracle_plateau")
                self.assertEqual(summary["escalation_rung"], rung)
                self.assertEqual(summary["iterations_completed"], reason_iters)

    def test_cost_guard_refuses_when_cost_left_below_needed(self):
        _mock_claude_running_total(self.bindir, [_rt_call(1.0)])
        # at iteration 4: spent 4.0, needed 3 x 1.0 = 3.0
        result = self._ladder(11, _LADDER, ceiling="6.50")
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")
        self.assertEqual(summary["escalation_rung"], 0)
        self.assertIn("$2.5000 left, $3.0000 needed", result.stderr)

    def test_cost_guard_allows_when_cost_left_covers_window(self):
        _mock_claude_running_total(self.bindir, [_rt_call(1.0)])
        result = self._ladder(11, _LADDER, ceiling="7.50")
        summary = self._summary(result)
        self.assertEqual(summary["escalation_rung"], 1)
        self.assertIn("escalating to rung 1", result.stderr)

    def test_cost_brake_still_fires_on_a_raised_rung(self):
        _mock_claude_running_total(self.bindir, [_rt_call(1.0)])
        _make_oracle(self.target, _composite_progression_oracle(
            [0.2, 0.2, 0.2, 0.2, 0.21, 0.22, 0.23, 0.24, 0.25, 0.26, 0.27]))
        result = self._ladder(11, _LADDER, ceiling="7.50")
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "cost_ceiling_reached")
        self.assertEqual(summary["escalation_rung"], 1)
        state = _read_state(self.target, summary["run_id"])
        self.assertEqual(state["cost_ceiling_usd"], 7.5)
        self.assertEqual(state["max_iterations"], 11)

    def test_rung_window_skips_a_leading_judge_iteration(self):
        # Plateau fires at iteration 5 (odd): iteration 6 is a judge turn that
        # re-scores the old tree and must not open the rung window.
        _make_oracle(self.target, _composite_progression_oracle(
            [0.2, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]))
        block = {"escalation": [{"effort": "high"}]}
        result = self._ladder(9, block)
        summary = self._summary(result)
        # window = runner 7, 8, 9 -> the last rung plateaus at 9, not at 8
        self.assertEqual(summary["iterations_completed"], 9)
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")
        state = _read_state(self.target, summary["run_id"])
        self.assertEqual(state["escalation_events"][0]["at_iteration"], 5)
        self.assertEqual(state["escalation_events"][0]["baseline_composite"], 0.3)
        self.assertEqual(state["escalation_history_start"], 6)   # iteration 7

    def test_escalation_prompt_section_on_first_runner_iteration_only(self):
        _make_oracle(self.target, _composite_progression_oracle(
            [0.2, 0.4, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]))
        block = {"escalation": [{"effort": "high"}]}
        self._ladder(9, block)
        argvs = self._argvs()

        def prompt(i):
            return "\n".join(argvs[i - 1])
        self.assertIn("Escalation", prompt(7))
        self.assertIn("rung 1", prompt(7))
        self.assertIn("Best composite so far: 0.4 (iteration 2)", prompt(7))
        self.assertIn("Composite at escalation: 0.3", prompt(7))
        for i in (1, 3, 5, 6, 8, 9):
            self.assertNotIn("Escalation", prompt(i), msg=f"iteration {i}")
        # the prompt still carries the usual last oracle / verdict context
        self.assertIn("Last oracle output", prompt(7))

    def test_effort_only_first_rung_still_starts_a_fresh_session(self):
        block = {"escalation": [{"effort": "high"}]}
        self._ladder(9, block)
        argvs = self._argvs()
        self.assertNotIn("--model", argvs[4])
        self.assertEqual(_find_flag_value(argvs[4], "--effort"), "high")
        self.assertNotIn("--resume", argvs[4])

    def test_passing_after_escalation_records_the_rung(self):
        _make_oracle(self.target, _composite_progression_oracle(
            [0.2, 0.2, 0.2, 0.2, 0.9]))
        result = self._ladder(11)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "oracle_passed")
        self.assertEqual(summary["escalation_rung"], 1)
        self.assertEqual(summary["iterations_completed"], 5)

    def test_improvement_pushes_plateau_later(self):
        _make_oracle(self.target, _composite_progression_oracle(
            [0.2, 0.2, 0.2, 0.2, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]))
        result = self._ladder(11)
        summary = self._summary(result)
        state = _read_state(self.target, summary["run_id"])
        # iteration 5 improves on the baseline, so rung 1 plateaus after 8
        self.assertEqual(state["escalation_events"][0]["at_iteration"], 4)
        self.assertGreater(
            state["escalation_events"][1]["at_iteration"], 7)

    def test_no_ladder_keeps_shapes_unchanged(self):
        # Negative guard: no escalation keys / `rung` anywhere without a ladder.
        for block in (None, {"runner": {"model": "sonnet"}},
                      {"runner": {"model": "sonnet"}, "escalation": []}):
            with self.subTest(block=block):
                shutil.rmtree(self.target / ".servo" / "runs", ignore_errors=True)
                (self.bindir / "mockstate.json").unlink(missing_ok=True)
                extra = ("--models", _models_arg(block)) if block else ()
                result = _run_loop(
                    self.target, "--prompt", "x", "--max-iterations", "11",
                    "--cost-ceiling", "10", "--plateau-window", "3", *extra,
                    mock_bindir=self.bindir)
                summary = self._summary(result)
                self.assertEqual(summary["terminal_reason"], "oracle_plateau")
                self.assertEqual(summary["iterations_completed"], 4)
                state = _read_state(self.target, summary["run_id"])
                for blob in (summary, state, self._iters(result)[0],
                             state["oracle_score_history"][0]):
                    for key in ("escalation_rung", "escalation_rungs",
                                "escalation_events", "rung",
                                "escalation_baseline_composite",
                                "escalation_history_start"):
                        self.assertNotIn(key, blob)

    def test_invocation_failure_on_a_raised_rung_names_rung_and_config(self):
        _fail_on_flag_wrapper(self.bindir, [_rt_call(0.10)], "--effort high")
        result = self._ladder(11)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "claude_invocation_failed")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(summary["escalation_rung"], 1)
        lines = [ln for ln in result.stderr.splitlines()
                 if "escalation rung 1" in ln]
        self.assertEqual(len(lines), 1, msg=result.stderr)
        self.assertIn('"effort": "high"', lines[0])
        self.assertIn("claude_invocation_failed", lines[0])
        # the same text rides the summary, so the heartbeat can pass it on
        crumb = summary["terminal_breadcrumb"]
        self.assertIn("escalation rung 1", crumb)
        self.assertIn('"effort": "high"', crumb)

    def test_judge_failure_on_a_raised_rung_names_the_judge_not_the_runner_config(self):
        _fail_on_call_wrapper(self.bindir, [_rt_call(0.10)], 6)   # judge, rung 1
        result = self._ladder(11)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "claude_invocation_failed")
        crumb = summary["terminal_breadcrumb"]
        self.assertIn("escalation rung 1", crumb)
        self.assertIn("judge", crumb)
        self.assertIn("unchanged", crumb)
        self.assertNotIn("effort", crumb)           # no runner config reported

    def test_verdict_mismatch_on_a_raised_rung_carries_breadcrumb(self):
        _bad_verdict_on_raised_rung(self.bindir, [_rt_call(0.10)])
        result = self._ladder(11)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "verdict_schema_mismatch")
        self.assertIn("escalation rung 1", summary["terminal_breadcrumb"])
        self.assertIn("verdict_schema_mismatch", summary["terminal_breadcrumb"])

    def test_escalation_discards_the_old_context_fill_ratio(self):
        # The plateau iteration (5, a runner turn) filled the old session; the
        # fresh rung session has no measured fill, so the gate must not halt.
        small, big = _rt_call(0.10), _rt_call(0.10, tokens=(2, 4, 600000, 0))
        _mock_claude_running_total(
            self.bindir, [small] * 4 + [big] + [small] * 10)
        _make_oracle(self.target, _composite_progression_oracle(
            [0.2, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]))
        result = self._ladder(
            9, {"escalation": [{"effort": "high"}]},
            "--context-fill-threshold", "0.5")
        summary = self._summary(result)
        self.assertNotEqual(summary["terminal_reason"], "context_full")
        self.assertGreaterEqual(summary["iterations_completed"], 7)
        state = _read_state(self.target, summary["run_id"])
        self.assertEqual(state["escalation_events"][0]["at_iteration"], 5)
        self.assertEqual(_find_flag_value(self._argvs()[6], "--effort"), "high")

    def test_invocation_failure_on_base_rung_names_no_rung(self):
        _fail_on_flag_wrapper(self.bindir, [_rt_call(0.10)], "--model sonnet")
        result = self._ladder(11)
        summary = self._summary(result)
        self.assertEqual(summary["terminal_reason"], "claude_invocation_failed")
        self.assertEqual(summary["escalation_rung"], 0)
        self.assertNotIn("escalation rung", result.stderr)


class LadderRoutingTests(unittest.TestCase):
    """Driver choice for a ladder lives in the node (038-03): `auto` + ladder
    routes to the loop driver; an explicit goal driver ignores the ladder."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-ladder-route-")
        tmp = Path(self.tmpdir)
        self.target = tmp / "demo"
        self.target.mkdir()
        _make_manifest(self.target)
        _make_oracle(self.target, _passing_oracle())
        self.bindir = tmp / "bin"
        self.bindir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _go(self, *extra, body=None):
        # Version 2.1.175: an eligible goal host, so `auto` would pick goal.
        _make_mock_claude(
            self.bindir, body or _loop_mock_body(), version="2.1.175")
        return _run_raw(self.target, "--prompt", "x", *extra,
                        mock_bindir=self.bindir,
                        extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})

    def _summary(self, result):
        return _stdout_json_lines(result.stdout)[-1]

    def test_auto_with_a_ladder_routes_to_the_loop_driver(self):
        for driver in ((), ("--driver", "auto")):
            with self.subTest(driver=driver):
                shutil.rmtree(self.target / ".servo" / "runs", ignore_errors=True)
                result = self._go(*driver, "--models", _models_arg(
                    {"escalation": [{"effort": "high"}]}))
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                summary = self._summary(result)
                self.assertNotIn("driver", summary)          # loop-shaped
                self.assertEqual(summary["escalation_rungs"], 1)
                self.assertEqual(
                    result.stderr.count("ladder needs the loop driver"), 1,
                    msg=result.stderr)
                self.assertNotIn("auto-routing to --driver loop", result.stderr)

    def test_auto_without_a_ladder_still_picks_goal(self):
        for block in (None, {"runner": {"model": "sonnet"}},
                      {"runner": {"model": "sonnet"}, "escalation": []}):
            with self.subTest(block=block):
                shutil.rmtree(self.target / ".servo" / "runs", ignore_errors=True)
                extra = ("--models", _models_arg(block)) if block else ()
                result = self._go(*extra, body=_goal_mock_body())
                self.assertEqual(result.returncode, 0, msg=result.stderr)
                self.assertEqual(self._summary(result)["driver"], "goal")
                self.assertNotIn("ladder needs", result.stderr)

    def test_explicit_goal_with_a_ladder_stays_goal_and_ignores_it(self):
        result = self._go(
            "--driver", "goal", "--models",
            _models_arg({"escalation": [{"effort": "high"}]}),
            body=_goal_mock_body())
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(self._summary(result)["driver"], "goal")
        self.assertEqual(result.stderr.count("models.escalation is ignored"), 1,
                         msg=result.stderr)
        self.assertNotIn("ladder needs the loop driver", result.stderr)


class LadderResumeTests(_AccountingTarget, unittest.TestCase):
    """AC6 - persisted rung, baseline and window index survive --resume."""

    def setUp(self):
        self._setup_acct()
        _make_oracle(self.target, _FLAT)
        _mock_claude_running_total(self.bindir, [_rt_call(0.10)])

    def _go(self, n, *extra):
        return _run_loop(
            self.target, "--prompt", "x", "--max-iterations", str(n),
            "--cost-ceiling", "10", "--plateau-window", "3", *extra,
            mock_bindir=self.bindir)

    def _resume(self, n, run_id, *extra):
        return _run_loop(
            self.target, "--resume", run_id, "--max-iterations", str(n),
            "--cost-ceiling", "10", "--plateau-window", "3", *extra,
            mock_bindir=self.bindir)

    def test_resume_continues_at_the_persisted_rung(self):
        self._go(7, "--models", _models_arg(_LADDER))
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["escalation_rung"], 1)
        self.assertEqual(state["escalation_history_start"], 4)
        self.assertEqual(state["escalation_events"][-1]["baseline_composite"], 0.2)
        self.assertNotIn("escalation_baseline_composite", state)
        result = self._resume(8, run_id)           # persisted ladder re-validated
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["oracle_score_history"][-1]["rung"], 1)
        self.assertEqual(state["escalation_rung"], 1)
        self.assertEqual(len(state["escalation_events"]), 1)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")
        self.assertEqual(summary["escalation_rung"], 1)

    def test_resumed_shorter_ladder_clamps_the_rung(self):
        self._go(11, "--models", _models_arg(_LADDER))
        run_id = _find_only_run_id(self.target)
        self.assertEqual(_read_state(self.target, run_id)["escalation_rung"], 2)
        short = {"runner": {"model": "sonnet"}, "escalation": [{"effort": "high"}]}
        result = self._resume(12, run_id, "--models", _models_arg(short))
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["escalation_rung"], 1)
        self.assertEqual(len(state["escalation_events"]), 2)   # nothing new
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["escalation_rung"], 1)
        self.assertEqual(summary["escalation_rungs"], 1)
        self.assertEqual(summary["terminal_reason"], "oracle_plateau")

    def test_ladderless_resume_before_rung_window_opens_keeps_plateau_brake(self):
        # Escalated, then the rung's first runner invocation failed: no window
        # start yet. A ladder-less resume must fall back to the plain check.
        _fail_on_flag_wrapper(self.bindir, [_rt_call(0.10)], "--effort high")
        result = self._go(11, "--models", _models_arg(_LADDER))
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["escalation_rung"], 1)
        self.assertIsNone(state["escalation_history_start"])
        _mock_claude_running_total(self.bindir, [_rt_call(0.10)])
        result = self._resume(
            12, run_id, "--models", _models_arg({"runner": {"model": "sonnet"}}))
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_plateau",
                         msg=result.stderr)
        state = _read_state(self.target, run_id)
        for key in ("escalation_rung", "escalation_history_start",
                    "escalation_baseline_composite"):
            self.assertNotIn(key, state)
        # the per-rung measurement record is kept
        self.assertEqual(len(state["escalation_events"]), 1)
        self.assertNotIn("escalation_rung", summary)
        self.assertNotIn("escalation_rungs", summary)

    def test_resume_mid_window_uses_the_persisted_baseline_and_window(self):
        # Baseline .4 (iteration 2) is beaten by nothing; the rung window opens
        # at iteration 7. Run 1 dies on call 8 with one window entry recorded.
        # Plateau at 9 needs BOTH the persisted baseline and the window start:
        # without the persisted window start the plateau fires earlier (8),
        # and without the baseline it fires later.
        flat = [0.2, 0.4] + [0.3] * 20
        _make_oracle(self.target, _composite_progression_oracle(flat))
        block = {"escalation": [{"effort": "high"}]}
        _fail_on_call_wrapper(self.bindir, [_rt_call(0.10)], 8)
        self._go(12, "--models", _models_arg(block))
        run_id = _find_only_run_id(self.target)
        state = _read_state(self.target, run_id)
        self.assertEqual(state["iteration_count"], 7)
        self.assertEqual(state["escalation_history_start"], 6)
        self.assertEqual(
            state["escalation_events"][0]["baseline_composite"], 0.4)
        result = self._resume(12, run_id)
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertEqual(summary["terminal_reason"], "oracle_plateau",
                         msg=result.stderr)
        self.assertEqual(summary["iterations_completed"], 9)
        self.assertEqual(summary["escalation_rung"], 1)

    def test_resumed_block_without_ladder_drops_ladder_keys_from_summary(self):
        self._go(7, "--models", _models_arg(_LADDER))
        run_id = _find_only_run_id(self.target)
        result = self._resume(8, run_id, "--models",
                              _models_arg({"runner": {"model": "sonnet"}}))
        summary = _stdout_json_lines(result.stdout)[-1]
        self.assertNotIn("escalation_rung", summary)
        self.assertNotIn("escalation_rungs", summary)

    def test_hand_edited_persisted_ladder_is_revalidated(self):
        self._go(2, "--models", _models_arg(_LADDER))
        run_id = _find_only_run_id(self.target)
        sp = _state_path(self.target, run_id)
        state = json.loads(sp.read_text())
        state["models"]["escalation"] = [{"effort": "turbo"}]
        sp.write_text(json.dumps(state))
        result = self._resume(3, run_id)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(_stdout_json_lines(result.stdout)[-1]["terminal_reason"],
                         "models_invalid")
        self.assertIn("models.escalation[0]", result.stderr)


class LadderFlagSurfaceTests(_AccountingTarget, unittest.TestCase):
    """AC1 - the ladder reaches the loop through flag, plan and the child."""

    def setUp(self):
        self._setup_acct()
        _make_oracle(self.target, _FLAT)
        _mock_claude_running_total(self.bindir, [_rt_call(0.10)])

    def test_flag_refuses_bad_ladders_before_any_run(self):
        for bad, needle in (
                ('{"escalation": "x"}', "models.escalation must be a list"),
                ('{"escalation": [{}]}', "models.escalation[0]"),
                ('{"escalation": [{"temperature": "1"}]}',
                 "models.escalation[0]"),
                ('{"escalation": [{"effort": "turbo"}]}',
                 "models.escalation[0]")):
            with self.subTest(bad=bad):
                result = self._run(2, "--models", bad)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(_stdout_json_lines(result.stdout)[-1]
                                 ["terminal_reason"], "models_invalid")
                self.assertIn(needle, result.stderr)
        self.assertEqual(list(self.target.glob(".servo/runs/*")), [])

    def test_plan_ladder_accepted_and_bad_plan_ladder_refused(self):
        for models, rc in (({"escalation": [{"effort": "high"}]}, 0),
                           ({"escalation": [{"effort": "turbo"}]}, 2)):
            with self.subTest(models=models):
                shutil.rmtree(self.target / ".servo" / "runs", ignore_errors=True)
                plan = _compiled_plan(
                    driver="loop", max_iterations=2, plateau_window=0)
                plan["models"] = models
                path = _write_plan(self.target.parent, plan)
                result = _run_loop(
                    self.target, "--plan", str(path), "--prompt", "x",
                    "--cost-ceiling", "10", mock_bindir=self.bindir)
                self.assertEqual(result.returncode, rc, msg=result.stderr)
                if rc:
                    self.assertEqual(_stdout_json_lines(result.stdout)[-1]
                                     ["terminal_reason"], "plan_value_invalid")
                    self.assertIn("models.escalation[0]", result.stderr)
                else:
                    run_id = _find_only_run_id(self.target)
                    self.assertEqual(
                        _read_state(self.target, run_id)["models"]["escalation"],
                        [{"effort": "high"}])


class GoalDriverLadderTests(_GoalTargetMixin, unittest.TestCase):
    """AC7 - the goal driver ignores a ladder with one note."""

    def setUp(self):
        self._setup_target(_passing_oracle())
        self.args_log = self.bindir.parent / "args.log"
        _mock_claude_goal(
            self.bindir, _goal_stream_jsonl(assistant_text=GOAL_PASS_SENTINEL),
            args_log=self.args_log)

    def test_goal_driver_prints_one_note_and_proceeds(self):
        block = {"runner": {"model": "sonnet"},
                 "escalation": [{"effort": "high"}]}
        result = _run_goal(
            self.target, "--prompt", "x", "--models", _models_arg(block),
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stderr.count("models.escalation is ignored"), 1,
                         msg=result.stderr)
        (argv,) = _read_args_log(self.args_log)
        self.assertEqual(_find_flag_value(argv, "--model"), "sonnet")
        self.assertNotIn("--effort", argv)

    def test_goal_driver_without_ladder_prints_no_note(self):
        result = _run_goal(
            self.target, "--prompt", "x", "--models",
            _models_arg({"runner": {"model": "sonnet"}}),
            mock_bindir=self.bindir, extra_env={"SERVO_CLAUDE_TIMEOUT": "20"})
        self.assertNotIn("escalation", result.stderr)

    def test_background_child_accepts_and_carries_the_ladder(self):
        block = {"runner": {"model": "sonnet"},
                 "escalation": [{"effort": "high"}]}
        result = _run_raw(
            self.target, "--background", "--prompt", "x", "--max-iterations",
            "2", "--models", _models_arg(block), mock_bindir=self.bindir,
            extra_env={"SERVO_CLAUDE_TIMEOUT": "30"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        state = _await_terminal_state(self.target)
        self.assertEqual(state["terminal_reason"], "oracle_pass")
        self.assertEqual(state["models"]["escalation"], [{"effort": "high"}])


if __name__ == "__main__":
    unittest.main()
