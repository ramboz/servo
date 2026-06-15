"""End-to-end dogfood for `/servo:oracle-hook` — slice 004-05 (ACs 5-7).

Proves the whole thing composes against a real scaffolded fixture target — the
capstone that makes spec 004 a real, invocable, *proven* feature:

    scaffolded oracle  →  hook.py install  →  installed meta-judge.sh
                       →  gate.py  →  oracle.sh
                       →  block-with-hint (below threshold) / silent-pass (above)

Everything in that chain is the **real** artifact: `hook.py` (the installer),
the placed `meta-judge.sh` (rendered from `templates/meta-judge.sh.template`),
and servo's own `gate.py`. The only stand-in is the fixture's `oracle.sh`, which
is a hand-rolled *real* shell script that prints the `composite=X threshold=Y`
line gate.py parses and exits 0/1 — exactly the shape `scaffold-init`'s template
produces, minus the external-tool dependency (`pytest` on PATH, …) that would
make a nested real-tool run non-deterministic under `uvx pytest`. So the scores
are deterministic by construction while the runtime chain is exercised for real.

Run via unittest or pytest:
    python3 skills/oracle-hook/test_dogfood.py
    uvx pytest skills/oracle-hook/test_dogfood.py -q
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import hook  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixture + real-artifact drivers
# --------------------------------------------------------------------------- #
def _scaffold_fixture(root: Path, *, passing: bool) -> Path:
    """Build a servo-scaffolded fixture: `.servo/install.json` + an executable
    `oracle.sh` that deterministically scores above (`passing`) or below the
    0.50 threshold, matching gate.py's exit-code-passthrough contract."""
    (root / ".servo").mkdir(parents=True, exist_ok=True)
    (root / ".servo" / "install.json").write_text(json.dumps({
        "servo_version": "0.1.0", "installed_tier": "tier-0", "components": ["pytest"],
    }))
    composite = "0.90" if passing else "0.20"
    oracle = root / "oracle.sh"
    oracle.write_text(
        "#!/bin/sh\n"
        f'echo "oracle: composite={composite} threshold=0.50"\n'
        f"exit {0 if passing else 1}\n"
    )
    oracle.chmod(0o755)
    return root


def _hook(*argv: str) -> int:
    """Run the real installer in-process, swallowing its stdout/stderr."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return hook.main(list(argv))


def _status_state(target: Path) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        rc = hook.main(["status", str(target), "--json"])
    assert rc == 0, "status must succeed"
    return json.loads(out.getvalue())["state"]


def _fire_stop(target: Path, *, stop_hook_active: bool = False) -> subprocess.CompletedProcess:
    """Pipe a synthetic `Stop`-event JSON into the *installed* meta-judge.sh,
    with `CLAUDE_PROJECT_DIR` pointed at the fixture (as Claude Code sets it)."""
    script = target / ".servo" / "hooks" / "meta-judge.sh"
    env = dict(os.environ)
    # The meta-judge shells out to bare `python3`; pin it to the interpreter
    # running this suite (servo's >=3.11 floor) so it can't fall back to an
    # older system python3 on a dev box — gate.py uses 3.10+ `X | Y` unions and
    # dies under 3.9 with an empty-stdout rc=1 the chain misreads as a silent
    # pass. CI's python3 is already >=3.11, so this is a no-op there.
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    env["CLAUDE_PROJECT_DIR"] = str(target)
    payload = {"hook_event_name": "Stop", "stop_hook_active": stop_hook_active}
    return subprocess.run(
        [str(script)], input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )


# --------------------------------------------------------------------------- #
# AC5 — below threshold blocks (with the amended-004-01 composite/threshold hint)
# --------------------------------------------------------------------------- #
class DogfoodBelowThresholdBlocksTests(unittest.TestCase):
    def test_below_threshold_blocks_with_evidence_hint(self):
        with tempfile.TemporaryDirectory() as d:
            target = _scaffold_fixture(Path(d), passing=False)
            self.assertEqual(_hook("install", str(target)), 0)

            proc = _fire_stop(target)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["decision"], "block")
            # The hint names the real evidence: composite + threshold (amended
            # 004-01 AC4 — no per-component scores on a stock below-threshold run).
            self.assertIn("0.2", out["reason"])   # composite
            self.assertIn("0.5", out["reason"])   # threshold


# --------------------------------------------------------------------------- #
# AC6 — above threshold passes silently
# --------------------------------------------------------------------------- #
class DogfoodAboveThresholdPassesTests(unittest.TestCase):
    def test_above_threshold_passes_silently(self):
        with tempfile.TemporaryDirectory() as d:
            target = _scaffold_fixture(Path(d), passing=True)
            self.assertEqual(_hook("install", str(target)), 0)

            proc = _fire_stop(target)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "", "a passing oracle emits no decision")


# --------------------------------------------------------------------------- #
# AC7 — round-trip clean
# --------------------------------------------------------------------------- #
class DogfoodRoundTripCleanTests(unittest.TestCase):
    """`uninstall` after the dogfood leaves `settings.json` equivalent to its
    pre-install state (modulo the `.servo-bak` backup), and `status` reaches
    `not_installed`."""

    def test_uninstall_restores_pre_install_settings(self):
        with tempfile.TemporaryDirectory() as d:
            target = _scaffold_fixture(Path(d), passing=False)
            settings_path = target / ".claude" / "settings.json"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            # A realistic pre-existing settings.json with unrelated user content.
            pre = json.dumps(
                {"env": {"FOO": "bar"}, "permissions": {"allow": ["Bash(ls:*)"]}},
                indent=2,
            ) + "\n"
            settings_path.write_text(pre)

            self.assertEqual(_hook("install", str(target)), 0)
            self.assertEqual(_status_state(target), "installed")
            self.assertNotEqual(settings_path.read_text(), pre, "install must mutate the live file")

            self.assertEqual(_hook("uninstall", str(target)), 0)

            # Equivalent to the pre-install state — unrelated keys preserved, the
            # emptied hooks structure cleaned up (compared semantically, not byte-wise).
            self.assertEqual(json.loads(settings_path.read_text()), json.loads(pre))
            # The backup exists (modulo it) — the pre-mutation state is recoverable.
            self.assertTrue((target / ".claude" / "settings.json.servo-bak").is_file())

    def test_status_reaches_not_installed_after_full_removal(self):
        with tempfile.TemporaryDirectory() as d:
            target = _scaffold_fixture(Path(d), passing=False)
            self.assertEqual(_status_state(target), "not_installed")  # baseline
            self.assertEqual(_hook("install", str(target)), 0)
            self.assertEqual(_status_state(target), "installed")

            self.assertEqual(_hook("uninstall", str(target)), 0)
            # uninstall deliberately leaves the project-owned meta-judge.sh on
            # disk (004-04 AC2), so the precise post-uninstall state is the
            # orphaned-script `inconsistent` (004-04 AC5) — reconciles the AC7
            # "not_installed" wording the same way 004-04 did.
            self.assertEqual(_status_state(target), "inconsistent")
            (target / ".servo" / "hooks" / "meta-judge.sh").unlink()
            self.assertEqual(_status_state(target), "not_installed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
