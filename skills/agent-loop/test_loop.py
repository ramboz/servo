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


MOCK_CLAUDE_VERSION = "1.0.0-mock"


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
    """
    if "--plateau-window" not in extra_args:
        extra_args = ("--plateau-window", "0", *extra_args)
    if path_override is not None:
        path = path_override
    elif mock_bindir is not None:
        path = f"{mock_bindir}:{SYSTEM_PATH}"
    else:
        path = SYSTEM_PATH
    env = {**os.environ, "PATH": path}
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
            "argparse", "json", "os", "re", "subprocess", "sys", "stat",
            "shutil", "pathlib", "dataclasses", "datetime", "typing",
            "collections", "itertools", "functools", "tempfile", "io",
            "contextlib", "errno", "enum", "uuid", "textwrap", "string",
            "platform", "signal", "secrets", "hashlib", "math", "time",
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
        summary = self._summary(result.stdout)
        self.assertEqual(summary["terminal_reason"], "claude_invocation_failed")
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
        for prev, curr in zip(budgets, budgets[1:], strict=False):
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
        for line, expected_cost in zip(per_iter, costs, strict=False):
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
            "--prompt", "x", "--max-iterations", "3",
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
            "--prompt", "x", "--max-iterations", "3",
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


class PlateauNoiseFloorTests(unittest.TestCase):
    """ADR-0005 clause 4 (δ): `_check_plateau`'s frozen noise floor lets a
    wobbling non-deterministic eval component neither fake progress (dodging a
    real plateau halt) nor fake a plateau (halting early).

    Verification obligation (ADR-0005 §Verification): sub-δ wobble still fires
    the plateau halt (no false progress), and a supra-δ gain does NOT fire it
    early (genuine progress resets the brake).
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


if __name__ == "__main__":
    unittest.main()
