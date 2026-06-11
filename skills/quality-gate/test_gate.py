"""
AC verification tests for slices 002-01 + 002-02 of `/servo:quality-gate`.

Run from the repo root:
    python3 -m unittest skills.quality-gate.test_gate
or directly:
    python3 skills/quality-gate/test_gate.py
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
GATE = REPO_ROOT / "skills" / "quality-gate" / "gate.py"


def _make_oracle(target: Path, body: str) -> Path:
    """Write an executable oracle.sh into the target with the given body."""
    oracle = target / "oracle.sh"
    oracle.write_text(body)
    mode = oracle.stat().st_mode
    oracle.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return oracle


def _make_manifest(target: Path, overrides: dict | None = None) -> Path:
    """Drop a minimal `.servo/install.json` into the target.

    Mirrors the schema scaffold.py produces (servo_version, timestamp,
    installed_tier, signals, components). `overrides` lets a test inject a
    custom manifest dict for malformed/missing-key cases.
    """
    if overrides is None:
        manifest = {
            "servo_version": "0.1.0",
            "timestamp": "2026-05-18T00:00:00Z",
            "installed_tier": "tier-0",
            "signals": {"tests": False, "lint": False, "ci": False, "language": None},
            "components": [],
        }
    else:
        manifest = overrides
    servo_dir = target / ".servo"
    servo_dir.mkdir(parents=True, exist_ok=True)
    path = servo_dir / "install.json"
    path.write_text(json.dumps(manifest))
    return path


def _run_gate(target, *extra_args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), str(target), *extra_args],
        capture_output=True,
        text=True,
    )


def _passing_oracle(composite: float = 0.9, threshold: float = 0.5) -> str:
    return (
        f"#!/usr/bin/env bash\n"
        f"echo 'oracle: composite={composite:.4f} threshold={threshold}'\n"
        f"exit 0\n"
    )


def _below_threshold_oracle(composite: float = 0.2, threshold: float = 0.5) -> str:
    return (
        f"#!/usr/bin/env bash\n"
        f"echo 'oracle: composite={composite:.4f} threshold={threshold}'\n"
        f"exit 1\n"
    )


def _env_error_oracle(missing: str = "pytest") -> str:
    return (
        f"#!/usr/bin/env bash\n"
        f"echo 'oracle: missing components: {missing}' >&2\n"
        f"exit 2\n"
    )


# ============================================================================
# Slice 002-01 — AC #1: Passthrough exit codes (0/1/2)
# ============================================================================


class PassthroughTests(unittest.TestCase):
    """Slice 002-01 AC #1 / 002-02 AC #5 — gate passes through 0/1/2 verbatim."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_manifest(self.target)  # 002-03: gate requires manifest

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _oracle(self, exit_code: int) -> None:
        _make_oracle(
            self.target,
            f"#!/usr/bin/env bash\n"
            f"echo 'oracle: composite=0.7000 threshold=0.5'\n"
            f"exit {exit_code}\n",
        )

    def test_passthrough_exit_zero(self):
        self._oracle(0)
        result = _run_gate(self.target)
        self.assertEqual(
            result.returncode, 0,
            f"expected 0, got {result.returncode}; stderr={result.stderr}",
        )

    def test_passthrough_exit_one(self):
        self._oracle(1)
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 1)

    def test_passthrough_exit_two(self):
        # An oracle.sh that explicitly exits 2 (env error from a component).
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\n"
            "echo 'oracle: missing components: pytest' >&2\n"
            "exit 2\n",
        )
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)


# ============================================================================
# Slice 002-01 — AC #2: Refusal on missing oracle
# ============================================================================


class MissingOracleTests(unittest.TestCase):
    """002-01 AC #2 — refusal (rc=2) when oracle.sh is absent (but manifest IS present)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        # Manifest present (so the manifest check passes) but oracle absent —
        # isolates the oracle-missing branch from the manifest-missing branch.
        _make_manifest(self.target)
        self.result = _run_gate(self.target)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_exit_code_two(self):
        self.assertEqual(self.result.returncode, 2)

    def test_stderr_names_missing_oracle(self):
        self.assertIn("oracle.sh not found", self.result.stderr)
        self.assertIn(str(self.target), self.result.stderr)

    def test_stderr_directs_user_to_scaffold(self):
        self.assertIn("scaffold-init", self.result.stderr)

    def test_no_oracle_created(self):
        # Refusal must not create oracle.sh; only the pre-seeded manifest remains.
        self.assertFalse((self.target / "oracle.sh").exists())

    def test_summary_line_on_stdout(self):
        # 002-02 AC #1: every exit produces a structured summary, even refusal modes.
        self.assertIn("status=env_error", self.result.stdout)
        self.assertIn("exit=2", self.result.stdout)
        self.assertIn("reason=oracle_missing", self.result.stdout)
        self.assertIn("composite=null", self.result.stdout)
        self.assertIn("threshold=null", self.result.stdout)


# ============================================================================
# Slice 002-01 — AC #3: Refusal on bad target
# ============================================================================


class BadTargetTests(unittest.TestCase):
    """002-01 AC #3 — refusal (rc=2) on missing or non-directory targets."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_nonexistent_path_refused(self):
        result = _run_gate(Path(self.tmpdir) / "does-not-exist")
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not exist", result.stderr)
        # 002-02 AC #1: summary on stdout.
        self.assertIn("status=env_error", result.stdout)
        self.assertIn("reason=target_missing", result.stdout)

    def test_file_instead_of_directory_refused(self):
        regular_file = Path(self.tmpdir) / "a-file.txt"
        regular_file.write_text("not a directory")
        result = _run_gate(regular_file)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not a directory", result.stderr)
        self.assertIn("reason=target_not_directory", result.stdout)


# ============================================================================
# Slice 002-01 — AC #5: Helper is dependency-free
# ============================================================================


class DependencyFreeTests(unittest.TestCase):
    """002-01 AC #5 — gate.py uses only the Python 3.10+ standard library."""

    def test_no_third_party_imports(self):
        text = GATE.read_text()
        stdlib_top_levels = {
            "argparse", "json", "os", "re", "subprocess", "sys", "stat",
            "shutil", "pathlib", "dataclasses", "datetime", "typing",
            "collections", "itertools", "functools", "tempfile", "io",
            "contextlib", "errno", "enum", "uuid", "textwrap", "string",
            "platform", "signal",
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
                (GATE.parent / name).exists(),
                f"unexpected dependency descriptor at {GATE.parent / name}",
            )


# ============================================================================
# Slice 002-01 — AC #6: Closed exit-code contract (ADR-0002)
# ============================================================================


class UnexpectedExitTests(unittest.TestCase):
    """002-01 AC #6 — oracle exits outside {0,1,2} remap to gate rc=2."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_manifest(self.target)  # 002-03

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _oracle_exits(self, code: int) -> None:
        _make_oracle(
            self.target,
            f"#!/usr/bin/env bash\n"
            f"echo 'oracle: pretend score' \n"
            f"exit {code}\n",
        )

    def test_exit_99_remapped_to_two(self):
        self._oracle_exits(99)
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unexpected code 99", result.stderr)
        self.assertIn("expected 0/1/2", result.stderr)

    def test_exit_127_remapped_to_two(self):
        self._oracle_exits(127)
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unexpected code 127", result.stderr)

    def test_signal_killed_remapped_to_two(self):
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\n"
            "kill -TERM $$\n"
            "exit 0\n",
        )
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unexpected code", result.stderr)

    def test_summary_carries_unexpected_exit_reason(self):
        # 002-02 AC #1: structured summary on every exit path.
        self._oracle_exits(99)
        result = _run_gate(self.target)
        self.assertIn("reason=unexpected_exit", result.stdout)
        self.assertIn("code=99", result.stdout)


class NonExecutableOracleTests(unittest.TestCase):
    """002-01 AC #6 (clarify Q4) — refusal with chmod hint when oracle.sh is not executable."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_manifest(self.target)  # 002-03
        oracle = self.target / "oracle.sh"
        oracle.write_text("#!/usr/bin/env bash\nexit 0\n")
        mode = oracle.stat().st_mode
        oracle.chmod(mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
        self.oracle = oracle
        self.result = _run_gate(self.target)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_exit_code_two(self):
        self.assertEqual(self.result.returncode, 2)

    def test_stderr_names_chmod_recovery(self):
        self.assertIn("not executable", self.result.stderr)
        self.assertIn("chmod +x", self.result.stderr)
        self.assertIn(str(self.oracle), self.result.stderr)

    def test_oracle_unmodified(self):
        mode = self.oracle.stat().st_mode
        self.assertFalse(mode & stat.S_IXUSR, "oracle.sh executable bit was modified")

    def test_summary_carries_not_executable_reason(self):
        self.assertIn("reason=oracle_not_executable", self.result.stdout)


# ============================================================================
# Slice 002-02 — AC #1: Default summary line on stdout
# ============================================================================


class SummaryLineTests(unittest.TestCase):
    """002-02 AC #1 — `gate.py <target>` prints a normalized summary line."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_manifest(self.target)  # 002-03

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_pass_summary(self):
        _make_oracle(self.target, _passing_oracle(composite=0.9, threshold=0.5))
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 0)
        line = result.stdout.strip()
        self.assertTrue(line.startswith("gate:"), f"unexpected stdout: {line!r}")
        self.assertIn("status=pass", line)
        self.assertIn("exit=0", line)
        self.assertIn("composite=0.9", line)
        self.assertIn("threshold=0.5", line)

    def test_below_threshold_summary(self):
        _make_oracle(self.target, _below_threshold_oracle(composite=0.2, threshold=0.5))
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 1)
        self.assertIn("status=below_threshold", result.stdout)
        self.assertIn("exit=1", result.stdout)
        self.assertIn("composite=0.2", result.stdout)
        self.assertIn("threshold=0.5", result.stdout)

    def test_env_error_summary_with_missing(self):
        _make_oracle(self.target, _env_error_oracle(missing="pytest eslint"))
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("status=env_error", result.stdout)
        self.assertIn("exit=2", result.stdout)
        self.assertIn("missing=pytest,eslint", result.stdout)

    def test_env_error_summary_without_missing(self):
        # Oracle exits 2 with no "missing components" line — e.g., a "no signals" path.
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\n"
            "echo 'oracle: no signals detected — populate # SEED: blocks manually' >&2\n"
            "exit 2\n",
        )
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("status=env_error", result.stdout)
        self.assertNotIn("missing=", result.stdout)

    def test_oracle_stdout_suppressed_by_default(self):
        # 002-02 AC #3 (negative): oracle's free-form output is suppressed without --verbose.
        _make_oracle(self.target, _passing_oracle(composite=0.7, threshold=0.5))
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("oracle: composite=0.7000", result.stdout)
        self.assertIn("composite=0.7", result.stdout)  # gate's normalized form

    def test_summary_is_single_line(self):
        _make_oracle(self.target, _passing_oracle())
        result = _run_gate(self.target)
        # Exactly one non-empty line on stdout in default mode.
        nonempty = [line for line in result.stdout.split("\n") if line.strip()]
        self.assertEqual(len(nonempty), 1, f"stdout had {len(nonempty)} lines: {result.stdout!r}")


# ============================================================================
# Slice 002-02 — AC #2: JSON mode
# ============================================================================


class JsonOutputTests(unittest.TestCase):
    """002-02 AC #2 — `--json` mode emits a one-line JSON payload."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_manifest(self.target)  # 002-03

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _json_for(self, oracle_body: str) -> dict:
        _make_oracle(self.target, oracle_body)
        result = _run_gate(self.target, "--json")
        # AC: one-line JSON
        nonempty = [line for line in result.stdout.split("\n") if line.strip()]
        self.assertEqual(len(nonempty), 1, f"stdout had {len(nonempty)} lines: {result.stdout!r}")
        payload = json.loads(nonempty[0])
        return payload, result.returncode

    def test_pass_path_json(self):
        payload, rc = self._json_for(_passing_oracle(composite=0.9, threshold=0.5))
        self.assertEqual(rc, 0)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["status"], "pass")
        self.assertAlmostEqual(payload["composite"], 0.9)
        self.assertAlmostEqual(payload["threshold"], 0.5)
        self.assertEqual(payload["missing"], [])
        self.assertNotIn("reason", payload)
        self.assertNotIn("code", payload)

    def test_below_threshold_json(self):
        payload, rc = self._json_for(_below_threshold_oracle(composite=0.2, threshold=0.5))
        self.assertEqual(rc, 1)
        self.assertEqual(payload["exit_code"], 1)
        self.assertEqual(payload["status"], "below_threshold")
        self.assertAlmostEqual(payload["composite"], 0.2)
        self.assertAlmostEqual(payload["threshold"], 0.5)

    def test_env_error_json_with_missing(self):
        payload, rc = self._json_for(_env_error_oracle(missing="pytest eslint"))
        self.assertEqual(rc, 2)
        self.assertEqual(payload["status"], "env_error")
        self.assertEqual(payload["missing"], ["pytest", "eslint"])
        # No composite/threshold parsed from this oracle (only stderr).
        self.assertIsNone(payload["composite"])
        self.assertIsNone(payload["threshold"])

    def test_unexpected_exit_json(self):
        payload, rc = self._json_for(
            "#!/usr/bin/env bash\necho 'oracle: pretend' \nexit 99\n"
        )
        self.assertEqual(rc, 2)
        self.assertEqual(payload["status"], "env_error")
        self.assertEqual(payload["reason"], "unexpected_exit")
        self.assertEqual(payload["code"], 99)

    def test_refusal_json_has_schema_version_and_status(self):
        # Refusal modes (no oracle invocation) also emit JSON with schema_version.
        result = _run_gate(Path(self.tmpdir) / "no-such-target", "--json")
        nonempty = [line for line in result.stdout.split("\n") if line.strip()]
        self.assertEqual(len(nonempty), 1)
        payload = json.loads(nonempty[0])
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["exit_code"], 2)
        self.assertEqual(payload["status"], "env_error")
        self.assertEqual(payload["reason"], "target_missing")
        self.assertIsNone(payload["composite"])
        self.assertIsNone(payload["threshold"])
        self.assertEqual(payload["missing"], [])

    def test_schema_version_present_and_equals_one(self):
        # ADR-0002: schema_version=1 on every JSON payload (named to match
        # the ADR's Verification section).
        for oracle in [
            _passing_oracle(),
            _below_threshold_oracle(),
            _env_error_oracle(),
            "#!/usr/bin/env bash\nexit 99\n",
            # Unparseable-output branch (oracle exits 0 with no summary line).
            "#!/usr/bin/env bash\necho 'no summary here'\nexit 0\n",
        ]:
            payload, _ = self._json_for(oracle)
            self.assertEqual(
                payload["schema_version"], 1,
                f"missing or wrong schema_version in {payload!r}",
            )


# ============================================================================
# Slice 002-02 — AC #3: Verbose mode re-emits oracle output
# ============================================================================


class VerboseTests(unittest.TestCase):
    """002-02 AC #3 — `--verbose` surfaces the oracle's raw stdout/stderr."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_manifest(self.target)  # 002-03

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_verbose_emits_oracle_stdout(self):
        _make_oracle(self.target, _passing_oracle(composite=0.7, threshold=0.5))
        result = _run_gate(self.target, "--verbose")
        self.assertEqual(result.returncode, 0)
        # Both the gate's summary AND the original oracle line appear.
        self.assertIn("oracle: composite=0.7000", result.stdout)
        self.assertIn("gate:", result.stdout)
        self.assertIn("status=pass", result.stdout)

    def test_verbose_emits_oracle_stderr(self):
        _make_oracle(self.target, _env_error_oracle(missing="pytest"))
        result = _run_gate(self.target, "--verbose")
        self.assertEqual(result.returncode, 2)
        self.assertIn("oracle: missing components: pytest", result.stderr)

    def test_verbose_json_includes_raw_key(self):
        _make_oracle(self.target, _passing_oracle())
        result = _run_gate(self.target, "--json", "--verbose")
        nonempty = [line for line in result.stdout.split("\n") if line.strip()]
        self.assertEqual(len(nonempty), 1)
        payload = json.loads(nonempty[0])
        self.assertIn("raw", payload)
        self.assertIn("stdout", payload["raw"])
        self.assertIn("oracle: composite", payload["raw"]["stdout"])

    def test_non_verbose_omits_raw_key_in_json(self):
        _make_oracle(self.target, _passing_oracle())
        result = _run_gate(self.target, "--json")
        payload = json.loads(result.stdout.strip())
        self.assertNotIn("raw", payload)


# ============================================================================
# Slice 002-02 — AC #4: Unparseable oracle output → env error
# ============================================================================


class UnparseableOracleTests(unittest.TestCase):
    """002-02 AC #4 — oracle exits 0 with no composite line → rc=2 env_error."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_manifest(self.target)  # 002-03

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_pass_without_summary_line_remapped_to_two(self):
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\n"
            "echo 'I forgot to print composite/threshold'\n"
            "exit 0\n",
        )
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("status=env_error", result.stdout)
        self.assertIn("reason=unparseable_oracle_output", result.stdout)

    def test_unparseable_oracle_raw_output_surfaces_on_stderr(self):
        # AC #4: surface the raw output on stderr (without --verbose).
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\n"
            "echo 'I forgot to print composite/threshold'\n"
            "echo 'some diagnostic detail' >&2\n"
            "exit 0\n",
        )
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        # The raw stdout/stderr should be in the gate's stderr for diagnosis.
        self.assertIn("I forgot to print composite/threshold", result.stderr)
        self.assertIn("some diagnostic detail", result.stderr)

    def test_malformed_summary_treated_as_unparseable(self):
        # A summary line missing the threshold field.
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\n"
            "echo 'oracle: composite=0.9'\n"
            "exit 0\n",
        )
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("reason=unparseable_oracle_output", result.stdout)


# ============================================================================
# Slice 002-03 — AC #1: Refusal on missing manifest
# ============================================================================


class MissingManifestTests(unittest.TestCase):
    """002-03 AC #1 — refusal (rc=2) when `.servo/install.json` is absent."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        # oracle.sh present (so manifest check is what fails) but manifest absent.
        _make_oracle(self.target, _passing_oracle())
        self.result = _run_gate(self.target)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_exit_code_two(self):
        self.assertEqual(self.result.returncode, 2)

    def test_stderr_names_missing_manifest(self):
        self.assertIn(".servo/install.json not found", self.result.stderr)
        self.assertIn(str(self.target), self.result.stderr)

    def test_stderr_directs_user_to_scaffold(self):
        self.assertIn("scaffold-init", self.result.stderr)

    def test_summary_carries_manifest_missing_reason(self):
        self.assertIn("status=env_error", self.result.stdout)
        self.assertIn("reason=manifest_missing", self.result.stdout)

    def test_oracle_not_invoked(self):
        # Oracle.sh writes nothing on disk when run, but we can verify
        # the gate's stderr is the manifest-missing message (not the
        # oracle's "no signals" message, which would mean the oracle ran).
        self.assertNotIn("oracle:", self.result.stderr)


# ============================================================================
# Slice 002-03 — AC #2: Refusal on malformed manifest
# ============================================================================


class MalformedManifestTests(unittest.TestCase):
    """002-03 AC #2 — refusal (rc=2) when manifest is not valid JSON / missing required keys."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_oracle(self.target, _passing_oracle())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_manifest(self, content: str) -> None:
        servo_dir = self.target / ".servo"
        servo_dir.mkdir(parents=True, exist_ok=True)
        (servo_dir / "install.json").write_text(content)

    def test_invalid_json_refused(self):
        self._write_manifest("{ not valid json")
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("reason=manifest_malformed", result.stdout)
        self.assertIn("malformed", result.stderr)

    def test_non_object_refused(self):
        self._write_manifest('["not", "an", "object"]')
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("reason=manifest_malformed", result.stdout)

    def test_missing_installed_tier_key_refused(self):
        self._write_manifest(json.dumps({"components": []}))
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("reason=manifest_invalid_key", result.stdout)
        self.assertIn("installed_tier", result.stderr)

    def test_missing_components_key_refused(self):
        self._write_manifest(json.dumps({"installed_tier": "tier-0"}))
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("reason=manifest_invalid_key", result.stdout)
        self.assertIn("components", result.stderr)


# ============================================================================
# Slice 002-03 — AC #3: Audit subcommand text output
# ============================================================================


class AuditTextOutputTests(unittest.TestCase):
    """002-03 AC #3 — `gate.py audit <target>` prints a human-readable summary."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_audit(self, *extra_args) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GATE), "audit", str(self.target), *extra_args],
            capture_output=True, text=True,
        )

    def test_exits_zero(self):
        _make_manifest(self.target, {
            "servo_version": "0.1.0",
            "timestamp": "2026-05-18T00:00:00Z",
            "installed_tier": "tier-0",
            "signals": {"tests": True, "lint": False, "ci": False, "language": "python"},
            "components": ["pytest"],
        })
        result = self._run_audit()
        self.assertEqual(result.returncode, 0, f"stderr={result.stderr}")

    def test_prints_tier(self):
        _make_manifest(self.target)
        result = self._run_audit()
        self.assertIn("tier:", result.stdout)
        self.assertIn("tier-0", result.stdout)

    def test_prints_install_timestamp(self):
        _make_manifest(self.target, {
            "servo_version": "0.1.0",
            "timestamp": "2026-05-18T12:34:56Z",
            "installed_tier": "tier-0",
            "signals": {},
            "components": [],
        })
        result = self._run_audit()
        self.assertIn("installed:", result.stdout)
        self.assertIn("2026-05-18T12:34:56Z", result.stdout)

    def test_prints_signals(self):
        _make_manifest(self.target, {
            "servo_version": "0.1.0",
            "timestamp": "2026-05-18T00:00:00Z",
            "installed_tier": "tier-0",
            "signals": {"tests": True, "lint": False, "ci": False, "language": "python"},
            "components": ["pytest"],
        })
        result = self._run_audit()
        self.assertIn("signals:", result.stdout)
        # Booleans rendered as JSON-style lowercase to match the --json shape.
        self.assertIn("tests=true", result.stdout)
        self.assertIn("lint=false", result.stdout)
        self.assertIn("language=python", result.stdout)

    def test_prints_components_list(self):
        _make_manifest(self.target, {
            "servo_version": "0.1.0",
            "timestamp": "2026-05-18T00:00:00Z",
            "installed_tier": "tier-0",
            "signals": {},
            "components": ["pytest", "ruff"],
        })
        result = self._run_audit()
        self.assertIn("pytest", result.stdout)
        self.assertIn("ruff", result.stdout)

    def test_components_show_weight_when_oracle_present(self):
        # Manifest carries component names; weights are parsed from oracle.sh's COMPONENTS array.
        _make_manifest(self.target, {
            "servo_version": "0.1.0",
            "timestamp": "2026-05-18T00:00:00Z",
            "installed_tier": "tier-0",
            "signals": {},
            "components": ["pytest"],
        })
        _make_oracle(
            self.target,
            '#!/usr/bin/env bash\n'
            'COMPONENTS=(\n  "pytest:1.5"\n)\n'
            'exit 0\n',
        )
        result = self._run_audit()
        self.assertIn("pytest", result.stdout)
        self.assertIn("1.5", result.stdout)

    def test_does_not_invoke_oracle(self):
        # Audit should not run oracle.sh — verify by using an oracle that would
        # write a sentinel file. Audit should leave the filesystem unchanged.
        _make_manifest(self.target)
        sentinel = self.target / "oracle-ran.flag"
        _make_oracle(
            self.target,
            f'#!/usr/bin/env bash\ntouch {sentinel}\nexit 0\n',
        )
        result = self._run_audit()
        self.assertEqual(result.returncode, 0)
        self.assertFalse(sentinel.exists(), "audit invoked oracle.sh (sentinel created)")


# ============================================================================
# Slice 002-03 — AC #4: Audit subcommand JSON output
# ============================================================================


class AuditJsonOutputTests(unittest.TestCase):
    """002-03 AC #4 — `gate.py audit <target> --json` emits the manifest verbatim."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_audit(self, *extra_args) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GATE), "audit", str(self.target), *extra_args],
            capture_output=True, text=True,
        )

    def test_emits_valid_json(self):
        manifest = {
            "servo_version": "0.1.0",
            "timestamp": "2026-05-18T00:00:00Z",
            "installed_tier": "tier-0",
            "signals": {"tests": True, "lint": False, "ci": False, "language": "python"},
            "components": ["pytest"],
        }
        _make_manifest(self.target, manifest)
        result = self._run_audit("--json")
        self.assertEqual(result.returncode, 0)
        parsed = json.loads(result.stdout)
        # AC: manifest contents emitted verbatim.
        self.assertEqual(parsed, manifest)

    def test_json_mode_skips_oracle_weight_enrichment(self):
        # JSON mode is "verbatim" — the manifest dict as-stored, no enriched fields.
        _make_manifest(self.target, {
            "servo_version": "0.1.0",
            "timestamp": "2026-05-18T00:00:00Z",
            "installed_tier": "tier-0",
            "signals": {},
            "components": ["pytest"],
        })
        _make_oracle(
            self.target,
            '#!/usr/bin/env bash\nCOMPONENTS=(\n  "pytest:2.0"\n)\nexit 0\n',
        )
        result = self._run_audit("--json")
        parsed = json.loads(result.stdout)
        # `components` stays as a list of names, no weights merged in.
        self.assertEqual(parsed["components"], ["pytest"])
        self.assertNotIn("weights", parsed)


# ============================================================================
# Slice 002-03 — AC #5: Audit refusal modes mirror invocation refusal
# ============================================================================


class AuditRefusalTests(unittest.TestCase):
    """002-03 AC #5 — `gate.py audit` refuses on missing manifest / bad target."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_audit(self, target, *extra_args) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GATE), "audit", str(target), *extra_args],
            capture_output=True, text=True,
        )

    def test_nonexistent_target_refused(self):
        result = self._run_audit(Path(self.tmpdir) / "does-not-exist")
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not exist", result.stderr)
        self.assertIn("reason=target_missing", result.stdout)

    def test_not_a_directory_refused(self):
        regular_file = Path(self.tmpdir) / "a-file.txt"
        regular_file.write_text("not a directory")
        result = self._run_audit(regular_file)
        self.assertEqual(result.returncode, 2)
        self.assertIn("reason=target_not_directory", result.stdout)

    def test_missing_manifest_refused(self):
        target = Path(self.tmpdir) / "demo-project"
        target.mkdir()
        result = self._run_audit(target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("reason=manifest_missing", result.stdout)
        self.assertIn(".servo/install.json not found", result.stderr)

    def test_malformed_manifest_refused_in_audit(self):
        target = Path(self.tmpdir) / "demo-project"
        target.mkdir()
        servo_dir = target / ".servo"
        servo_dir.mkdir()
        (servo_dir / "install.json").write_text("{ not valid json")
        result = self._run_audit(target)
        self.assertEqual(result.returncode, 2)
        self.assertIn("reason=manifest_malformed", result.stdout)

    def test_json_refusal_carries_schema_version(self):
        # AC #5 + ADR-0002: refusal in JSON mode is still a structured payload with schema_version.
        result = self._run_audit(
            Path(self.tmpdir) / "does-not-exist", "--json"
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["status"], "env_error")
        self.assertEqual(payload["reason"], "target_missing")


# ============================================================================
# Slice 002-04 — AC #1..#5: Timeout safety
# ============================================================================


import time  # noqa: E402 — used only by slice 002-04 tests


def _run_gate_with_env(target, env_overrides, *extra_args) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    # Strip any inherited SERVO_GATE_TIMEOUT so env_overrides controls things cleanly.
    env.pop("SERVO_GATE_TIMEOUT", None)
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(GATE), str(target), *extra_args],
        capture_output=True, text=True, env=env,
    )


class TimeoutTests(unittest.TestCase):
    """002-04 AC #1, #2, #3 — default timeout, --timeout flag, env var override."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_manifest(self.target)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_default_timeout_constant_is_300(self):
        # AC #1: the architecture's documented 5-minute default.
        text = GATE.read_text()
        self.assertIn("DEFAULT_TIMEOUT_SECONDS = 300", text)

    def test_resolve_timeout_default_is_300_via_function_call(self):
        # AC #1: stronger proxy than grepping the source — import gate's
        # _resolve_timeout and call it with no flag and no env var. Should
        # return the 300s default. Refactor-resilient.
        import importlib.util
        spec = importlib.util.spec_from_file_location("_gate_under_test", GATE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        env_backup = os.environ.pop("SERVO_GATE_TIMEOUT", None)
        try:
            self.assertEqual(module._resolve_timeout(None), 300.0)
        finally:
            if env_backup is not None:
                os.environ["SERVO_GATE_TIMEOUT"] = env_backup

    def test_timeout_flag_kills_long_running_oracle(self):
        # AC #2: --timeout 1 against a 10s-sleeping oracle kills within ~2s.
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\n"
            "sleep 10\n"
            "echo 'oracle: composite=1.0 threshold=0.5'\n"
            "exit 0\n",
        )
        t0 = time.monotonic()
        result = _run_gate(self.target, "--timeout", "1")
        elapsed = time.monotonic() - t0
        self.assertEqual(result.returncode, 2, f"stderr={result.stderr}")
        self.assertIn("reason=timeout", result.stdout)
        # Kill happens at ~1s; grant generous CI headroom but cap below 10s
        # (the oracle's natural completion) to prove the timeout actually fired.
        self.assertLess(elapsed, 8.0, f"timeout took too long: {elapsed:.2f}s")

    def test_timeout_stderr_breadcrumb(self):
        # The stderr breadcrumb is part of the contract — describes which
        # signal sequence was used so a human reading logs can diagnose.
        _make_oracle(self.target, "#!/usr/bin/env bash\nsleep 10\nexit 0\n")
        result = _run_gate(self.target, "--timeout", "1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("timed out after", result.stderr)
        self.assertIn("SIGTERM", result.stderr)
        self.assertIn("SIGKILL", result.stderr)

    def test_timeout_summary_carries_timeout_field(self):
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\nsleep 10\nexit 0\n",
        )
        result = _run_gate(self.target, "--timeout", "1")
        self.assertEqual(result.returncode, 2)
        # argparse parses --timeout as float (1.0); _format_float preserves
        # the ".0" suffix. Field name aligns with the --timeout flag and
        # SERVO_GATE_TIMEOUT env var (not "duration", which would suggest
        # actual elapsed wall-clock).
        self.assertIn("timeout=1.0s", result.stdout)

    def test_timeout_json_carries_timeout_seconds(self):
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\nsleep 10\nexit 0\n",
        )
        result = _run_gate(self.target, "--timeout", "1", "--json")
        payload = json.loads(result.stdout.strip())
        self.assertEqual(payload["status"], "env_error")
        self.assertEqual(payload["reason"], "timeout")
        # argparse → float(1.0); JSON serializes as 1.0. Strict equality
        # rather than == 1 (Python int-float equivalence would mask drift).
        self.assertEqual(payload["timeout_seconds"], 1.0)
        self.assertIsInstance(payload["timeout_seconds"], float)

    def test_env_var_timeout_override(self):
        # AC #3: SERVO_GATE_TIMEOUT env var honored when --timeout absent.
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\nsleep 10\nexit 0\n",
        )
        t0 = time.monotonic()
        result = _run_gate_with_env(self.target, {"SERVO_GATE_TIMEOUT": "1"})
        elapsed = time.monotonic() - t0
        self.assertEqual(result.returncode, 2)
        self.assertIn("reason=timeout", result.stdout)
        self.assertLess(elapsed, 8.0)

    def test_flag_wins_over_env_var(self):
        # AC #3: when both set, --timeout wins.
        _make_oracle(
            self.target,
            "#!/usr/bin/env bash\nsleep 10\nexit 0\n",
        )
        # Env says 60s (would let the oracle finish before timeout, but
        # we're using --timeout 1 instead, so we expect timeout at ~1s).
        t0 = time.monotonic()
        result = _run_gate_with_env(
            self.target,
            {"SERVO_GATE_TIMEOUT": "60"},
            "--timeout", "1",
        )
        elapsed = time.monotonic() - t0
        self.assertEqual(result.returncode, 2)
        self.assertIn("reason=timeout", result.stdout)
        # If the env var won, we'd have waited up to 10s for the oracle to finish naturally.
        self.assertLess(elapsed, 8.0)

    def test_timeout_zero_disables_timeout(self):
        # Clarify Q2: --timeout 0 → no bound. The oracle finishes normally.
        _make_oracle(self.target, _passing_oracle())
        result = _run_gate(self.target, "--timeout", "0")
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=pass", result.stdout)
        self.assertNotIn("reason=timeout", result.stdout)

    def test_malformed_env_var_falls_back_to_default(self):
        # Garbage in env var → ignored, default used. Oracle finishes; no timeout.
        _make_oracle(self.target, _passing_oracle())
        result = _run_gate_with_env(self.target, {"SERVO_GATE_TIMEOUT": "not-a-number"})
        self.assertEqual(result.returncode, 0)
        self.assertIn("status=pass", result.stdout)
        self.assertIn("ignoring malformed SERVO_GATE_TIMEOUT", result.stderr)


class ProcessGroupKillTests(unittest.TestCase):
    """002-04 AC #4 — backgrounded oracle children are killed with the oracle."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_manifest(self.target)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_backgrounded_subprocess_killed_with_oracle(self):
        # Oracle backgrounds a sleep that touches a sentinel file. If the kill
        # signals only the foreground (not the process group), the sentinel
        # would land after the gate exits. With process-group kill, no sentinel.
        sentinel = self.target / "background-survived.flag"
        _make_oracle(
            self.target,
            f"#!/usr/bin/env bash\n"
            f"(sleep 5 && touch '{sentinel}') &\n"
            f"sleep 30\n"  # foreground blocks
            f"exit 0\n",
        )
        result = _run_gate(self.target, "--timeout", "1")
        self.assertEqual(result.returncode, 2)
        # Wait long enough that, had the background survived, the sentinel would
        # have been created (5s sleep + small margin).
        time.sleep(6)
        self.assertFalse(
            sentinel.exists(),
            "background subprocess survived the kill — process group not targeted",
        )


class FastPathRegressionTests(unittest.TestCase):
    """002-04 AC #5 — fast oracles aren't delayed by timeout machinery."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="servo-gate-test-")
        self.target = Path(self.tmpdir) / "demo-project"
        self.target.mkdir()
        _make_manifest(self.target)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_fast_oracle_no_delay(self):
        _make_oracle(self.target, _passing_oracle())
        t0 = time.monotonic()
        result = _run_gate(self.target)
        elapsed = time.monotonic() - t0
        self.assertEqual(result.returncode, 0)
        # The default timeout is 300s; a fast oracle should finish in ~100ms
        # of subprocess overhead. 3s wall-clock is plenty of CI headroom and
        # also well below "the timeout machinery added meaningful delay".
        self.assertLess(elapsed, 3.0, f"fast-path oracle took {elapsed:.2f}s")

    def test_no_timeout_field_on_fast_path(self):
        # Successful oracles should not emit a `timeout=...` field;
        # `timeout_seconds` is reserved for timeout summaries (rc=2 reason=timeout).
        _make_oracle(self.target, _passing_oracle())
        result = _run_gate(self.target)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("timeout=", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
