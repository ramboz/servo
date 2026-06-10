"""Tests for the servo oracle-hook installer + meta-judge script (spec 004-01).

Two test surfaces:

* ``InstallTests`` drive ``hook.py install`` against fixture targets (ACs 1-3).
* ``MetaJudgeScriptTests`` pipe synthetic ``Stop``-event JSON into the installed
  ``meta-judge.sh`` and assert its stdout/exit, with a stubbed ``gate.py`` so the
  full decision table is exercised deterministically (ACs 4-8). One integration
  test drives the *real* ``gate.py`` against a scaffolded fixture (AC8).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
HOOK_PY = HOOK_DIR / "hook.py"

# Import the installer module directly for the install-surface tests.
sys.path.insert(0, str(HOOK_DIR))
import hook  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def _make_scaffolded_target(
    root: Path, *, passing: bool = False, missing: list[str] | None = None
) -> Path:
    """Create a minimal servo-scaffolded target: manifest + executable oracle.sh.

    The oracle prints the ``oracle: composite=X threshold=Y`` line gate.py
    parses and exits 0 (pass) or 1 (below threshold), matching gate.py's
    exit-code-passthrough contract.
    """
    (root / ".servo").mkdir(parents=True, exist_ok=True)
    manifest = {
        "servo_version": "0.1.0",
        "installed_tier": "tier-0",
        "components": ["pytest"],
    }
    (root / ".servo" / "install.json").write_text(json.dumps(manifest))

    composite = "0.90" if passing else "0.20"
    lines = ["#!/bin/sh", f'echo "oracle: composite={composite} threshold=0.50"']
    if missing:
        lines.append(f'echo "oracle: missing components: {" ".join(missing)}" >&2')
    lines.append("exit 0" if passing else "exit 1")
    oracle = root / "oracle.sh"
    oracle.write_text("\n".join(lines) + "\n")
    oracle.chmod(0o755)
    return root


def _stub_gate(root: Path) -> Path:
    """A fake gate.py whose --json output + exit code are driven by env vars.

    ``STUB_GATE_RC``       — exit code to return (default 0)
    ``STUB_GATE_JSON``     — the one-line JSON to print (default ``{}``)
    ``STUB_GATE_SENTINEL`` — if set, a file written on invocation (so the
                             runaway-guard test can prove the gate was *not* run)
    """
    stub = root / "stub_gate.py"
    stub.write_text(
        "import os, sys\n"
        "sentinel = os.environ.get('STUB_GATE_SENTINEL')\n"
        "if sentinel:\n"
        "    open(sentinel, 'w').write('invoked')\n"
        "sys.stdout.write(os.environ.get('STUB_GATE_JSON', '{}'))\n"
        "sys.exit(int(os.environ.get('STUB_GATE_RC', '0')))\n"
    )
    return stub


def _run_meta_judge(
    script: Path, stdin_obj, *, project_dir: Path, extra_env: dict | None = None
) -> subprocess.CompletedProcess:
    """Run the installed meta-judge script. ``stdin_obj`` may be a dict (JSON-
    encoded) or a raw ``str`` (sent verbatim, to exercise unparseable stdin)."""
    payload = stdin_obj if isinstance(stdin_obj, str) else json.dumps(stdin_obj)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [str(script)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
    )


# --------------------------------------------------------------------------- #
# Install surface (ACs 1-3)
# --------------------------------------------------------------------------- #
class InstallTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_install_places_executable_script_with_substituted_gate_path(self):
        """AC1: script is copied to .servo/hooks/meta-judge.sh, +x, no placeholder."""
        _make_scaffolded_target(self.target)
        rc = hook.main(["install", str(self.target)])
        self.assertEqual(rc, 0)
        script = self.target / ".servo" / "hooks" / "meta-judge.sh"
        self.assertTrue(script.is_file())
        self.assertTrue(os.access(script, os.X_OK), "script must be executable")
        body = script.read_text()
        self.assertNotIn("__GATE_PY__", body, "gate path placeholder must be substituted")

    def test_install_registers_stop_hook_in_settings(self):
        """AC2: hooks.Stop[] entry points at the script, type command, has timeout."""
        _make_scaffolded_target(self.target)
        hook.main(["install", str(self.target)])
        settings = json.loads((self.target / ".claude" / "settings.json").read_text())
        stop = settings["hooks"]["Stop"]
        self.assertEqual(len(stop), 1)
        inner = stop[0]["hooks"][0]
        self.assertEqual(inner["type"], "command")
        self.assertIn(".servo/hooks/meta-judge.sh", inner["command"])
        self.assertIn("CLAUDE_PROJECT_DIR", inner["command"])
        self.assertIsInstance(inner["timeout"], int)

    def test_install_creates_claude_dir_and_settings_when_absent(self):
        """AC2: .claude/ + settings.json created from scratch with valid JSON."""
        _make_scaffolded_target(self.target)
        self.assertFalse((self.target / ".claude").exists())
        hook.main(["install", str(self.target)])
        settings_path = self.target / ".claude" / "settings.json"
        self.assertTrue(settings_path.is_file())
        json.loads(settings_path.read_text())  # parses

    def test_install_refuses_when_no_manifest(self):
        """AC3: no .servo/install.json → refuse, nonzero, point at scaffold-init."""
        (self.target / "oracle.sh").write_text("#!/bin/sh\nexit 0\n")
        (self.target / "oracle.sh").chmod(0o755)
        rc = hook.main(["install", str(self.target)])
        self.assertEqual(rc, 2)
        self.assertFalse((self.target / ".servo" / "hooks" / "meta-judge.sh").exists())

    def test_install_refuses_when_no_oracle(self):
        """AC3: manifest present but no oracle.sh → refuse, no half-install."""
        (self.target / ".servo").mkdir(parents=True)
        (self.target / ".servo" / "install.json").write_text(
            json.dumps({"installed_tier": "tier-0", "components": []})
        )
        rc = hook.main(["install", str(self.target)])
        self.assertEqual(rc, 2)
        self.assertFalse((self.target / ".servo" / "hooks" / "meta-judge.sh").exists())


# --------------------------------------------------------------------------- #
# Meta-judge script behaviour (ACs 4-8)
# --------------------------------------------------------------------------- #
class MetaJudgeScriptTests(unittest.TestCase):
    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name)
        _make_scaffolded_target(self.target)
        hook.main(["install", str(self.target)])
        self.script = self.target / ".servo" / "hooks" / "meta-judge.sh"
        self.stub = _stub_gate(self.target)

    def tearDown(self):
        self._tmp.cleanup()

    def _stub_env(self, rc: int, payload: dict, sentinel: Path | None = None) -> dict:
        env = {
            "SERVO_GATE_PY": str(self.stub),
            "STUB_GATE_RC": str(rc),
            "STUB_GATE_JSON": json.dumps(payload),
        }
        if sentinel is not None:
            env["STUB_GATE_SENTINEL"] = str(sentinel)
        return env

    def test_blocks_on_below_threshold_with_structured_hint(self):
        """AC4: gate rc=1 → block naming composite + threshold (the real evidence).

        Uses the *realistic* gate payload for a below-threshold run: the stock
        oracle reports ``missing`` only on its env-error (exit-2) path, so on a
        genuine exit-1 the gate's ``missing`` is empty (verified against
        oracle.sh.template). The hint therefore carries composite + threshold.
        """
        payload = {
            "schema_version": 1, "status": "below_threshold",
            "composite": 0.2, "threshold": 0.5, "missing": [],
        }
        proc = _run_meta_judge(
            self.script, {"stop_hook_active": False},
            project_dir=self.target, extra_env=self._stub_env(1, payload),
        )
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("0.2", out["reason"])
        self.assertIn("0.5", out["reason"])

    def test_hint_includes_missing_components_when_present(self):
        """Defensive: a (custom) oracle that surfaces ``missing`` alongside a
        below-threshold result has those components named in the hint. The stock
        oracle doesn't hit this on exit 1 — see the deviation log — so this is
        forward/defensive coverage, not the common path."""
        payload = {
            "status": "below_threshold", "composite": 0.2,
            "threshold": 0.5, "missing": ["pytest", "eslint"],
        }
        proc = _run_meta_judge(
            self.script, {"stop_hook_active": False},
            project_dir=self.target, extra_env=self._stub_env(1, payload),
        )
        reason = json.loads(proc.stdout)["reason"]
        self.assertIn("pytest", reason)
        self.assertIn("eslint", reason)

    def test_passes_silently_on_pass(self):
        """AC5: gate rc=0 → no decision, exit 0, no stdout JSON block."""
        payload = {"status": "pass", "composite": 0.9, "threshold": 0.5, "missing": []}
        proc = _run_meta_judge(
            self.script, {"stop_hook_active": False},
            project_dir=self.target, extra_env=self._stub_env(0, payload),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_runaway_guard_skips_oracle_when_stop_hook_active(self):
        """AC6: stop_hook_active true → exit 0, gate never invoked."""
        sentinel = self.target / "gate-was-invoked"
        proc = _run_meta_judge(
            self.script, {"stop_hook_active": True},
            project_dir=self.target,
            extra_env=self._stub_env(1, {"composite": 0.2}, sentinel=sentinel),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertFalse(sentinel.exists(), "gate must not run when stop_hook_active")

    def test_runaway_guard_suppresses_on_unparseable_stdin(self):
        """Indeterminate guard: non-JSON stdin → suppress (never block, never
        even invoke the gate). Biases toward never trapping a live session."""
        sentinel = self.target / "gate-was-invoked"
        proc = _run_meta_judge(
            self.script, "this is not valid json",
            project_dir=self.target,
            extra_env=self._stub_env(
                1, {"composite": 0.2, "threshold": 0.5}, sentinel=sentinel
            ),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertFalse(sentinel.exists(), "indeterminate guard must not block/score")

    def test_does_not_read_transcript(self):
        """AC7: a garbage transcript_path doesn't affect behaviour."""
        payload = {"status": "below_threshold", "composite": 0.2,
                   "threshold": 0.5, "missing": []}
        proc = _run_meta_judge(
            self.script,
            {"stop_hook_active": False,
             "transcript_path": "/nonexistent/garbage-\x00-path.jsonl"},
            project_dir=self.target, extra_env=self._stub_env(1, payload),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["decision"], "block")

    def test_fails_open_on_env_error(self):
        """gate rc=2 → never block (exit 0, no decision). 004-02 adds the warning."""
        payload = {"status": "env_error", "reason": "manifest_missing",
                   "composite": None, "threshold": None, "missing": []}
        proc = _run_meta_judge(
            self.script, {"stop_hook_active": False},
            project_dir=self.target, extra_env=self._stub_env(2, payload),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("block", proc.stdout)

    def test_integration_real_gate_blocks_below_threshold(self):
        """AC8: with the *real* baked gate.py + a below-threshold fixture oracle,
        the installed script blocks with a hint — proves the whole chain composes."""
        proc = _run_meta_judge(
            self.script, {"stop_hook_active": False}, project_dir=self.target,
        )
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertIn("0.2", out["reason"])

    def test_integration_real_gate_passes_silently(self):
        """AC8 mirror: a passing fixture oracle → silent pass through the real gate."""
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            passing = _make_scaffolded_target(Path(d), passing=True)
            hook.main(["install", str(passing)])
            script = passing / ".servo" / "hooks" / "meta-judge.sh"
            proc = _run_meta_judge(
                script, {"stop_hook_active": False}, project_dir=passing,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout.strip(), "")


class ResolveGatePyTests(unittest.TestCase):
    """`_resolve_gate_py` prefers a target-vendored gate.py (portable, relative)
    and otherwise bakes servo's own absolute path."""

    def test_prefers_vendored_relative_path(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            vend = target / ".claude" / "skills" / "servo-quality-gate"
            vend.mkdir(parents=True)
            (vend / "gate.py").write_text("# stub gate\n")
            ref = hook._resolve_gate_py(target)
            self.assertIn("CLAUDE_PROJECT_DIR", ref)
            self.assertIn(".claude/skills/servo-quality-gate/gate.py", ref)

    def test_falls_back_to_servo_gate_absolute(self):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            ref = hook._resolve_gate_py(Path(d))
            self.assertTrue(ref.endswith("quality-gate/gate.py"), ref)
            self.assertTrue(Path(ref).is_absolute())


if __name__ == "__main__":
    unittest.main()
