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


def _make_mock_claude(bindir: Path, body: str) -> Path:
    """Write an executable `claude` script into `bindir`. PATH-injected by tests."""
    bindir.mkdir(parents=True, exist_ok=True)
    claude = bindir / "claude"
    claude.write_text(body)
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
    """
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
        per_iter = [l for l in lines if "iteration" in l]
        self.assertEqual(len(per_iter), 2)
        # Iteration numbers are 1-indexed and contiguous.
        self.assertEqual([l["iteration"] for l in per_iter], [1, 2])


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
        per_iter = [l for l in lines if "iteration" in l]
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
        per_iter = [l for l in _stdout_json_lines(result.stdout) if "iteration" in l]
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
        per_iter = [l for l in _stdout_json_lines(result.stdout) if "iteration" in l]
        self.assertEqual([l["iteration"] for l in per_iter], [1, 2, 3, 4])


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
        per_iter = [l for l in _stdout_json_lines(result.stdout) if "iteration" in l]
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
        per_iter = [l for l in _stdout_json_lines(result.stdout) if "iteration" in l]
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
        per_iter = [l for l in _stdout_json_lines(result.stdout) if "iteration" in l]
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
        per_iter = [l for l in lines if "iteration" in l]
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


if __name__ == "__main__":
    unittest.main()
