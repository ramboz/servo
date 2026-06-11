"""Tests for the servo oracle-hook installer + meta-judge script (spec 004).

Surfaces:

* ``InstallTests`` — ``hook.py install`` against fixture targets (004-01 ACs 1-3).
* ``IdempotentInstallBackupTests`` — re-install idempotency, settings merge +
  byte-faithful backup, and safe refusal on malformed/odd-shaped settings.json
  (004-03 ACs 1-5).
* ``MetaJudgeScriptTests`` — pipe synthetic ``Stop``-event JSON into the installed
  ``meta-judge.sh`` and assert its stdout/exit, with a stubbed ``gate.py`` so the
  full decision table is exercised deterministically (004-01 ACs 4-8). One
  integration test drives the *real* ``gate.py`` against a scaffolded fixture (AC8).
* ``FailOpenSafetyTests`` — a broken/missing/slow/unparseable gate never blocks
  (004-02).
* ``ResolveGatePyTests`` — ``_resolve_gate_py`` vendored-vs-absolute resolution.
"""
from __future__ import annotations

import contextlib
import io
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
        "argv_file = os.environ.get('STUB_GATE_ARGV')\n"
        "if argv_file:\n"
        "    open(argv_file, 'w').write(' '.join(sys.argv[1:]))\n"
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
# Idempotent install + settings backup/merge (slice 004-03, ACs 1-5)
# --------------------------------------------------------------------------- #
class IdempotentInstallBackupTests(unittest.TestCase):
    """``install`` is safe to re-run against a *populated* ``settings.json``:
    idempotent (one servo Stop entry), merge-not-clobber, backup-before-mutate,
    a safe refusal on malformed/odd-shaped content, and a stable entry marker."""

    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name)
        _make_scaffolded_target(self.target)
        self.settings_path = self.target / ".claude" / "settings.json"
        self.backup_path = self.target / ".claude" / "settings.json.servo-bak"
        self.script = self.target / ".servo" / "hooks" / "meta-judge.sh"

    def tearDown(self):
        self._tmp.cleanup()

    # -- helpers -- #
    def _seed_settings(self, raw: str) -> None:
        """Write a pre-existing settings.json verbatim (raw text, not re-encoded)."""
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(raw)

    def _install(self, *args):
        """Run ``install`` capturing (rc, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = hook.main(["install", str(self.target), *args])
        return rc, out.getvalue(), err.getvalue()

    def _servo_entry_count(self) -> int:
        settings = json.loads(self.settings_path.read_text())
        stop = settings.get("hooks", {}).get("Stop", [])
        return sum(1 for e in stop if hook._entry_is_servo(e))

    # -- AC1: idempotent install -- #
    def test_second_install_yields_single_servo_entry(self):
        """AC1: running install twice produces exactly one servo Stop entry."""
        rc1, _, _ = self._install()
        rc2, _, _ = self._install()
        self.assertEqual((rc1, rc2), (0, 0))
        self.assertEqual(self._servo_entry_count(), 1)

    # -- AC2: merge, not clobber -- #
    def test_preserves_unrelated_top_level_keys(self):
        """AC2: env / permissions / model and friends survive the install."""
        self._seed_settings(json.dumps({
            "env": {"FOO": "bar"},
            "permissions": {"allow": ["Bash(ls:*)"]},
            "model": "claude-x",
        }))
        rc, _, _ = self._install()
        self.assertEqual(rc, 0)
        merged = json.loads(self.settings_path.read_text())
        self.assertEqual(merged["env"], {"FOO": "bar"})
        self.assertEqual(merged["permissions"], {"allow": ["Bash(ls:*)"]})
        self.assertEqual(merged["model"], "claude-x")
        self.assertEqual(self._servo_entry_count(), 1)

    def test_preserves_other_stop_entries_and_hook_events(self):
        """AC2: a user's own Stop hook and a non-Stop event are left intact;
        only servo's Stop entry is appended."""
        other_stop = {"hooks": [{"type": "command", "command": "/opt/my-own-stop.sh"}]}
        pretooluse = {"matcher": "Bash",
                      "hooks": [{"type": "command", "command": "echo hi"}]}
        self._seed_settings(json.dumps(
            {"hooks": {"PreToolUse": [pretooluse], "Stop": [other_stop]}}
        ))
        rc, _, _ = self._install()
        self.assertEqual(rc, 0)
        merged = json.loads(self.settings_path.read_text())
        self.assertEqual(merged["hooks"]["PreToolUse"], [pretooluse])  # other event intact
        stop = merged["hooks"]["Stop"]
        self.assertEqual(len(stop), 2)                                 # user's + servo's
        self.assertIn(other_stop, stop)                                # user's preserved verbatim
        self.assertEqual(self._servo_entry_count(), 1)

    # -- AC3: backup before mutate -- #
    def test_backs_up_existing_settings_before_mutating(self):
        """AC3: the pre-mutation file is copied byte-faithfully to .servo-bak."""
        original = '{\n    "env": {"FOO": "bar"}\n}\n'  # 4-space; != indent=2 output
        self._seed_settings(original)
        rc, _, _ = self._install()
        self.assertEqual(rc, 0)
        self.assertTrue(self.backup_path.is_file())
        self.assertEqual(self.backup_path.read_text(), original)       # exact pre-mutation bytes
        self.assertEqual(self._servo_entry_count(), 1)                 # live file did change

    def test_no_backup_when_creating_fresh_settings(self):
        """AC3: a brand-new settings.json (none existed) writes no backup."""
        self.assertFalse(self.settings_path.exists())
        rc, _, _ = self._install()
        self.assertEqual(rc, 0)
        self.assertFalse(self.backup_path.exists())

    def test_reinstall_does_not_rewrite_backup(self):
        """AC3: a no-change re-install does not rewrite the backup."""
        self._seed_settings(json.dumps({"env": {"FOO": "bar"}}))
        self._install()                                    # creates the backup
        self.assertTrue(self.backup_path.is_file())
        self.backup_path.write_text("SENTINEL-do-not-touch")
        rc, _, _ = self._install()                         # servo present → no-op
        self.assertEqual(rc, 0)
        self.assertEqual(self.backup_path.read_text(), "SENTINEL-do-not-touch")
        self.assertEqual(self._servo_entry_count(), 1)

    # -- AC4: malformed settings refuses safely -- #
    def test_malformed_settings_refuses_without_change_or_backup(self):
        """AC4: invalid JSON → refuse (nonzero, names the file), no write, no backup."""
        malformed = '{ "env": this is not json'
        self._seed_settings(malformed)
        rc, _out, err = self._install()
        self.assertEqual(rc, 2)
        self.assertIn(str(self.settings_path), err)                    # message names the file
        # unparseable content untouched
        self.assertEqual(self.settings_path.read_text(), malformed)
        self.assertFalse(self.backup_path.exists())                    # never backed up
        self.assertFalse(self.script.exists())                         # no half-install

    # -- AC5: stable entry identity -- #
    def test_servo_entry_carries_stable_marker(self):
        """AC5: servo's Stop entry is identifiable by a stable marker, and that
        marker does not match an unrelated user entry."""
        self._install()
        settings = json.loads(self.settings_path.read_text())
        servo = [e for e in settings["hooks"]["Stop"] if hook._entry_is_servo(e)]
        self.assertEqual(len(servo), 1)
        self.assertIn(hook.SERVO_HOOK_REL, servo[0]["hooks"][0]["command"])
        self.assertFalse(hook._entry_is_servo(
            {"hooks": [{"type": "command", "command": "/opt/other.sh"}]}
        ))

    # -- empty-file fixture (DoD): treated as an empty config, not malformed -- #
    def test_empty_settings_file_treated_as_empty_config(self):
        """An empty (content-free) settings.json installs cleanly with no backup
        — there is nothing to preserve, and refusing on it would be hostile."""
        self._seed_settings("")
        rc, _, _ = self._install()
        self.assertEqual(rc, 0)
        self.assertEqual(self._servo_entry_count(), 1)
        self.assertFalse(self.backup_path.exists())

    # -- non-destructive re-install preserves a customized script (slice theme) -- #
    def test_reinstall_preserves_customized_meta_judge_script(self):
        """Re-install must not clobber a user-customized meta-judge.sh (the spec
        calls the script user-customizable; this slice's promise is non-destructive
        re-install)."""
        self._install()
        self.assertTrue(self.script.is_file())
        customized = self.script.read_text() + "\n# user customization\n"
        self.script.write_text(customized)
        rc, _, _ = self._install()
        self.assertEqual(rc, 0)
        self.assertEqual(self.script.read_text(), customized)

    # -- structural refusal: hooks present but wrong shape (defensive, AC4 posture) -- #
    def test_refuses_when_hooks_is_not_an_object(self):
        """A valid-JSON but wrong-shaped ``hooks`` refuses rather than crashing
        mid-install."""
        self._seed_settings(json.dumps({"hooks": "oops"}))
        rc, _out, err = self._install()
        self.assertEqual(rc, 2)
        self.assertIn(str(self.settings_path), err)
        self.assertFalse(self.backup_path.exists())
        self.assertFalse(self.script.exists())

    def test_refuses_when_stop_is_not_an_array(self):
        """A wrong-shaped ``hooks.Stop`` refuses safely (no half-install)."""
        self._seed_settings(json.dumps({"hooks": {"Stop": {"not": "a list"}}}))
        rc, _, _ = self._install()
        self.assertEqual(rc, 2)
        self.assertFalse(self.script.exists())


# --------------------------------------------------------------------------- #
# Uninstall + status CLI (slice 004-04, ACs 1-6)
# --------------------------------------------------------------------------- #
class UninstallStatusTests(unittest.TestCase):
    """``uninstall`` reverses install's settings surgery (marker-matched,
    backup-first, script left on disk, idempotent) and ``status`` reports
    installed / not_installed / inconsistent in human and ``--json`` form."""

    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name)
        _make_scaffolded_target(self.target)
        self.settings_path = self.target / ".claude" / "settings.json"
        self.backup_path = self.target / ".claude" / "settings.json.servo-bak"
        self.script = self.target / ".servo" / "hooks" / "meta-judge.sh"

    def tearDown(self):
        self._tmp.cleanup()

    # -- helpers -- #
    def _run(self, *argv):
        """Run a CLI command capturing (rc, stdout, stderr); argparse's own
        SystemExit (e.g. an unknown subcommand) is mapped to its exit code."""
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = hook.main(list(argv))
        except SystemExit as e:  # argparse error path
            rc = e.code if isinstance(e.code, int) else 1
        return rc, out.getvalue(), err.getvalue()

    def _settings(self) -> dict:
        return json.loads(self.settings_path.read_text())

    def _seed_settings(self, raw: str) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(raw)

    def _servo_entry_count(self) -> int:
        stop = self._settings().get("hooks", {}).get("Stop", [])
        return sum(1 for e in stop if hook._entry_is_servo(e))

    def _status_json(self) -> dict:
        rc, out, _ = self._run("status", str(self.target), "--json")
        self.assertEqual(rc, 0)
        return json.loads(out)

    # ---- uninstall ---- #
    def test_uninstall_removes_only_servo_entry(self):
        """AC1: uninstall drops servo's entry but keeps other Stop entries, other
        hook events, and unrelated top-level keys."""
        self._run("install", str(self.target))
        settings = self._settings()
        other_stop = {"hooks": [{"type": "command", "command": "/opt/mine.sh"}]}
        settings["hooks"]["Stop"].append(other_stop)
        settings["hooks"]["PreToolUse"] = [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo hi"}]}
        ]
        settings["env"] = {"FOO": "bar"}
        self._seed_settings(json.dumps(settings))

        rc, _, _ = self._run("uninstall", str(self.target))
        self.assertEqual(rc, 0)
        merged = self._settings()
        self.assertEqual(self._servo_entry_count(), 0)            # servo gone
        self.assertEqual(merged["hooks"]["Stop"], [other_stop])   # user's kept
        self.assertIn("PreToolUse", merged["hooks"])              # other event kept
        self.assertEqual(merged["env"], {"FOO": "bar"})           # unrelated key kept

    def test_uninstall_cleans_up_emptied_stop_and_hooks(self):
        """AC1: removing the only Stop entry cleans up the dead Stop/hooks
        structure (no `Stop: []` / `hooks: {}` left behind)."""
        self._run("install", str(self.target))
        rc, _, _ = self._run("uninstall", str(self.target))
        self.assertEqual(rc, 0)
        self.assertNotIn("hooks", self._settings())

    def test_uninstall_leaves_meta_judge_script(self):
        """AC2: uninstall never deletes the script."""
        self._run("install", str(self.target))
        self.assertTrue(self.script.is_file())
        self._run("uninstall", str(self.target))
        self.assertTrue(self.script.is_file())

    def test_uninstall_idempotent_when_no_servo_entry(self):
        """AC3: uninstall with no servo entry is a no-op success; unrelated
        content is left byte-for-byte and no backup is written."""
        original = json.dumps({"env": {"A": 1}}, indent=2) + "\n"
        self._seed_settings(original)
        rc, _, _ = self._run("uninstall", str(self.target))
        self.assertEqual(rc, 0)
        self.assertEqual(self.settings_path.read_text(), original)
        self.assertFalse(self.backup_path.exists())

    def test_uninstall_idempotent_when_no_settings_file(self):
        """AC3: uninstall with no settings.json is a no-op success (not an error)
        and creates nothing."""
        self.assertFalse(self.settings_path.exists())
        rc, _, _ = self._run("uninstall", str(self.target))
        self.assertEqual(rc, 0)
        self.assertFalse(self.settings_path.exists())

    def test_uninstall_backs_up_before_mutating(self):
        """AC4: uninstall backs up the exact pre-mutation settings.json."""
        self._run("install", str(self.target))
        pre = self.settings_path.read_text()
        rc, _, _ = self._run("uninstall", str(self.target))
        self.assertEqual(rc, 0)
        self.assertTrue(self.backup_path.is_file())
        self.assertEqual(self.backup_path.read_text(), pre)

    def test_uninstall_refuses_malformed(self):
        """AC4: a malformed settings.json refuses safely (names file, no change,
        no backup)."""
        malformed = "{ not json"
        self._seed_settings(malformed)
        rc, _out, err = self._run("uninstall", str(self.target))
        self.assertEqual(rc, 2)
        self.assertIn(str(self.settings_path), err)
        self.assertEqual(self.settings_path.read_text(), malformed)
        self.assertFalse(self.backup_path.exists())

    # ---- status ---- #
    def test_status_installed(self):
        """AC5: after install, status reports installed (human + json)."""
        self._run("install", str(self.target))
        rc, out, _ = self._run("status", str(self.target))
        self.assertEqual(rc, 0)
        self.assertTrue(out.strip().startswith("oracle-hook: installed"))
        j = self._status_json()
        self.assertEqual(j["state"], "installed")
        self.assertTrue(j["entry_present"])
        self.assertTrue(j["script_present"])

    def test_status_not_installed(self):
        """AC5: a scaffolded-but-not-installed target reports not_installed."""
        j = self._status_json()
        self.assertEqual(j["state"], "not_installed")
        self.assertFalse(j["entry_present"])
        self.assertFalse(j["script_present"])

    def test_status_inconsistent_entry_without_script(self):
        """AC5: entry present but script missing → inconsistent."""
        self._run("install", str(self.target))
        self.script.unlink()
        j = self._status_json()
        self.assertEqual(j["state"], "inconsistent")
        self.assertTrue(j["entry_present"])
        self.assertFalse(j["script_present"])

    def test_status_inconsistent_script_without_entry(self):
        """AC5: script present but no entry (the post-uninstall orphan) →
        inconsistent."""
        self._run("install", str(self.target))
        self._run("uninstall", str(self.target))  # removes entry, leaves script
        j = self._status_json()
        self.assertEqual(j["state"], "inconsistent")
        self.assertFalse(j["entry_present"])
        self.assertTrue(j["script_present"])

    def test_status_json_has_expected_keys(self):
        """AC5: --json carries the machine-readable shape."""
        self._run("install", str(self.target))
        j = self._status_json()
        for k in ("schema_version", "state", "entry_present", "script_present"):
            self.assertIn(k, j)

    def test_status_refuses_malformed(self):
        """AC5/AC6: unparseable settings.json → env-error (exit 2, names file)."""
        self._seed_settings("{ not json")
        rc, out, err = self._run("status", str(self.target))
        self.assertEqual(rc, 2)
        self.assertIn("settings_malformed", out + err)
        self.assertIn(str(self.settings_path), err)

    # ---- round-trip + shared exit contract ---- #
    def test_roundtrip_install_status_uninstall_status(self):
        """DoD round-trip. NOTE: because uninstall leaves the script (AC2) and a
        script-without-entry is `inconsistent` (AC5), the precise post-uninstall
        state is `inconsistent` (orphaned script); removing the script then
        yields `not_installed`. Reconciles the DoD's looser
        'uninstall → not_installed' wording with AC2 + AC5."""
        self._run("install", str(self.target))
        self.assertEqual(self._status_json()["state"], "installed")
        self._run("uninstall", str(self.target))
        self.assertEqual(self._status_json()["state"], "inconsistent")
        self.script.unlink()
        self.assertEqual(self._status_json()["state"], "not_installed")

    def test_target_missing_is_env_error_for_all_commands(self):
        """AC6: a non-existent target is a uniform env-error (exit 2) across the
        install / uninstall / status surface."""
        missing = self.target / "nope"
        for cmd in ("install", "uninstall", "status"):
            with self.subTest(cmd=cmd):
                rc, out, err = self._run(cmd, str(missing))
                self.assertEqual(rc, 2)
                self.assertIn("target_missing", out + err)


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
        """gate rc=2 → never block (exit 0). The user-facing systemMessage warning
        is asserted by FailOpenSafetyTests (004-02); here we guard the no-block
        invariant from the 004-01 perspective."""
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


class FailOpenSafetyTests(unittest.TestCase):
    """Slice 004-02: a broken/missing/slow oracle must NEVER block — it fails
    open (lets the stop proceed) and warns the *user* via ``systemMessage``."""

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

    def _env(self, rc, payload, **extra):
        env = {
            "SERVO_GATE_PY": str(self.stub),
            "STUB_GATE_RC": str(rc),
            "STUB_GATE_JSON": json.dumps(payload),
        }
        env.update({k: str(v) for k, v in extra.items()})
        return env

    def test_env_error_emits_systemmessage_not_block(self):
        """AC1+AC2: env_error → systemMessage naming the reason, no block, exit 0."""
        payload = {"status": "env_error", "reason": "manifest_missing",
                   "composite": None, "threshold": None, "missing": []}
        proc = _run_meta_judge(
            self.script, {"stop_hook_active": False},
            project_dir=self.target, extra_env=self._env(2, payload),
        )
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        self.assertNotIn("decision", out)
        self.assertIn("systemMessage", out)
        self.assertIn("manifest_missing", out["systemMessage"])

    def test_all_env_error_reasons_fail_open(self):
        """AC1+AC5: every env_error reason class warns, none blocks."""
        for reason in ("oracle_missing", "oracle_not_executable", "timeout",
                       "unexpected_exit", "unparseable_oracle_output",
                       "invocation_failed"):
            with self.subTest(reason=reason):
                payload = {"status": "env_error", "reason": reason,
                           "composite": None, "threshold": None, "missing": []}
                proc = _run_meta_judge(
                    self.script, {"stop_hook_active": False},
                    project_dir=self.target, extra_env=self._env(2, payload),
                )
                self.assertEqual(proc.returncode, 0)
                self.assertNotIn("block", proc.stdout)
                self.assertIn(reason, proc.stdout)

    def test_gate_invocation_failure_fails_open(self):
        """AC3: gate.py itself uninvocable (path missing) → no block, exit 0."""
        proc = _run_meta_judge(
            self.script, {"stop_hook_active": False}, project_dir=self.target,
            extra_env={"SERVO_GATE_PY": str(self.target / "does-not-exist.py")},
        )
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("block", proc.stdout)

    def test_unparseable_env_error_emits_generic_warning(self):
        """AC3: rc=2 with non-JSON gate output → generic systemMessage, no block."""
        env = {"SERVO_GATE_PY": str(self.stub), "STUB_GATE_RC": "2",
               "STUB_GATE_JSON": "this is not json"}
        proc = _run_meta_judge(
            self.script, {"stop_hook_active": False},
            project_dir=self.target, extra_env=env,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("decision", proc.stdout)
        self.assertIn("systemMessage", proc.stdout)

    def test_gate_called_with_timeout_bound(self):
        """AC4: the meta-judge bounds its gate.py call with a --timeout flag."""
        argv_file = self.target / "gate-argv"
        payload = {"status": "pass", "composite": 0.9, "threshold": 0.5}
        _run_meta_judge(
            self.script, {"stop_hook_active": False}, project_dir=self.target,
            extra_env=self._env(0, payload, STUB_GATE_ARGV=str(argv_file)),
        )
        self.assertTrue(argv_file.exists())
        self.assertIn("--timeout", argv_file.read_text())

    def test_timeout_bound_is_env_overridable(self):
        """AC4: SERVO_META_JUDGE_GATE_TIMEOUT controls the --timeout value."""
        argv_file = self.target / "gate-argv"
        payload = {"status": "pass", "composite": 0.9, "threshold": 0.5}
        _run_meta_judge(
            self.script, {"stop_hook_active": False}, project_dir=self.target,
            extra_env=self._env(0, payload, STUB_GATE_ARGV=str(argv_file),
                                SERVO_META_JUDGE_GATE_TIMEOUT=17),
        )
        self.assertIn("--timeout 17", argv_file.read_text())


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
