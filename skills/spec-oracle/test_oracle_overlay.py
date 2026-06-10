"""
AC verification tests for slice 006-03 (oracle-overlay) of `/servo:spec-oracle`.

Run from the repo root:
    python3 skills/spec-oracle/test_oracle_overlay.py
or via pytest:
    uvx pytest skills/spec-oracle/test_oracle_overlay.py -q

`oracle_overlay.py` compiles a checked plan into an installable oracle
component: it writes an `oracle.sh.fragment` (a `# SEED:start/end
spec_oracle_<id>` block wrapping `score_spec_oracle_<id>`), copies the
stdlib check engine alongside the plan, and splices the component into the
target's `oracle.sh` as an ordinary servo component — so `gate.py` scores it
with no special-casing (slice 006-03 AC5).

Idiom mirrors `test_oracle_plan.py` / `test_checks.py`: modules are imported
by path (the `spec-oracle` dir is not an importable package); a real target
is built with `scaffold.install(...)` and driven through the stock `gate.py`
for the end-to-end pass/fail/env-error paths (the DoD's integration check).
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OVERLAY_PY = REPO_ROOT / "skills" / "spec-oracle" / "oracle_overlay.py"
CHECKS_PY = REPO_ROOT / "skills" / "spec-oracle" / "checks.py"
GATE_PY = REPO_ROOT / "skills" / "quality-gate" / "gate.py"
SCAFFOLD_PY = REPO_ROOT / "skills" / "scaffold-init" / "scaffold.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ov = _load("oracle_overlay", OVERLAY_PY)
scaffold = _load("scaffold", SCAFFOLD_PY)


def _write_plan(target: Path, spec_id: str, checks: list, residual=None) -> Path:
    """Write a checks.json plan under <target>/.servo/spec-oracles/<id>/."""
    out = target / ".servo" / "spec-oracles" / spec_id
    out.mkdir(parents=True, exist_ok=True)
    p = out / "checks.json"
    p.write_text(json.dumps({
        "schema_version": 1, "spec_id": spec_id, "checks": checks,
        "residual_judgment": residual or [],
    }))
    return p


# ===========================================================================
# AC1 — Fragment generation
# ===========================================================================


class FragmentTests(unittest.TestCase):
    """AC1 — a valid `# SEED:start/end spec_oracle_<id>` block."""

    def test_component_name_is_shell_safe(self):
        # Hyphens in the spec id are not valid in a shell function name, so the
        # component name sanitizes them to underscores.
        self.assertEqual(ov.component_name("006-spec-oracle"),
                         "spec_oracle_006_spec_oracle")

    def test_traversal_or_degenerate_spec_id_rejected(self):
        # `/` is rejected by the slug regex; "."/".."/all-punctuation ids have
        # no shell-safe name and could escape the spec-oracle dir.
        for bad in ("..", ".", "---", "../evil", "a/b", ""):
            with self.assertRaises(ValueError):
                ov.component_name(bad)

    def test_fragment_has_seed_markers(self):
        frag = ov.render_fragment("099-demo")
        self.assertIn("# SEED:start spec_oracle_099_demo", frag)
        self.assertIn("# SEED:end spec_oracle_099_demo", frag)

    def test_fragment_defines_score_function(self):
        frag = ov.render_fragment("099-demo")
        self.assertRegex(frag, r"score_spec_oracle_099_demo\s*\(\)\s*\{")

    def test_fragment_invokes_engine_score_only(self):
        frag = ov.render_fragment("099-demo")
        self.assertIn("--score-only", frag)
        self.assertIn(".servo/spec-oracles/099-demo/checks.py", frag)
        self.assertIn(".servo/spec-oracles/099-demo/checks.json", frag)

    def test_fragment_enforces_freeze(self):
        # The installed component runs the engine with the freeze gate on, so
        # the loop can only score an approved, unmodified overlay (006-04).
        self.assertIn("--enforce-freeze", ov.render_fragment("099-demo"))

    def test_fragment_guards_missing_python(self):
        # A missing python3 is an environment error (rc=2), not a crash.
        frag = ov.render_fragment("099-demo")
        self.assertIn("command -v python3", frag)
        self.assertIn("return 2", frag)

    def test_seed_block_is_balanced(self):
        frag = ov.render_fragment("099-demo")
        starts = re.findall(r"^# SEED:start (\S+)\s*$", frag, re.MULTILINE)
        ends = re.findall(r"^# SEED:end (\S+)\s*$", frag, re.MULTILINE)
        self.assertEqual(starts, ends)
        self.assertEqual(len(starts), 1)


class GenerateTests(unittest.TestCase):
    """AC1 — generate writes the fragment + a self-contained engine copy."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_generate_writes_fragment_and_checks_copy(self):
        _write_plan(self.target, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])
        ov.generate(self.target, "099-demo")
        oracle_dir = self.target / ".servo" / "spec-oracles" / "099-demo"
        self.assertTrue((oracle_dir / "oracle.sh.fragment").is_file())
        copied = oracle_dir / "checks.py"
        self.assertTrue(copied.is_file())
        # The copy is the real engine (self-contained, project-owned).
        body = copied.read_text()
        self.assertIn("def run_checks", body)
        self.assertIn("--score-only", body)

    def test_generate_requires_a_plan(self):
        # No checks.json yet → generate refuses (nothing to compile).
        with self.assertRaises(FileNotFoundError):
            ov.generate(self.target, "099-demo")


# ===========================================================================
# AC2 — Install (splice into oracle.sh without disturbing the baseline)
# ===========================================================================


def _seed_placeholder(oracle: Path) -> None:
    """Inject a controllable `placeholder` baseline component (mirrors
    test_scaffold.py) so install can be shown not to disturb it."""
    text = oracle.read_text()
    text, n = re.subn(r"COMPONENTS=\(\s*\n",
                      'COMPONENTS=(\n  "placeholder:1.0"\n', text, count=1)
    assert n == 1, "could not seed COMPONENTS"
    seed = ('\n# SEED:start placeholder\n'
            'score_placeholder() {\n'
            '  echo "${PLACEHOLDER_SCORE:-1.0}"\n'
            '}\n'
            '# SEED:end placeholder\n')
    text, n2 = re.subn(r'(weighted_sum="0")', seed + r"\1", text, count=1)
    assert n2 == 1, "could not seed SEED block"
    oracle.write_text(text)


class InstallTests(unittest.TestCase):
    """AC2 — install adds the component without disturbing baseline ones."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.oracle = self.target / "oracle.sh"
        self.oracle.write_text(scaffold._render_oracle([]))
        _seed_placeholder(self.oracle)
        _write_plan(self.target, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_adds_component_and_keeps_baseline(self):
        ov.install(self.target, "099-demo")
        text = self.oracle.read_text()
        # Baseline placeholder is untouched.
        self.assertIn("# SEED:start placeholder", text)
        self.assertIn('"placeholder:1.0"', text)
        # Overlay component added.
        self.assertIn("# SEED:start spec_oracle_099_demo", text)
        self.assertIn('"spec_oracle_099_demo:1.0"', text)

    def test_install_is_idempotent(self):
        ov.install(self.target, "099-demo")
        ov.install(self.target, "099-demo")
        text = self.oracle.read_text()
        self.assertEqual(text.count("# SEED:start spec_oracle_099_demo"), 1)
        self.assertEqual(text.count('"spec_oracle_099_demo:'), 1)

    def test_custom_weight(self):
        ov.install(self.target, "099-demo", weight=0.25)
        self.assertIn('"spec_oracle_099_demo:0.25"', self.oracle.read_text())

    def test_install_requires_oracle(self):
        bare = Path(tempfile.mkdtemp())
        try:
            _write_plan(bare, "099-demo",
                        [{"id": "AC-1", "family": "file_presence", "path": "x"}])
            with self.assertRaises(FileNotFoundError):
                ov.install(bare, "099-demo")
        finally:
            __import__("shutil").rmtree(bare, ignore_errors=True)

    def test_installed_oracle_is_valid_bash(self):
        ov.install(self.target, "099-demo")
        res = subprocess.run(["bash", "-n", str(self.oracle)],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)


# ===========================================================================
# AC6 — Uninstall (remove component, keep plan/check artifacts)
# ===========================================================================


class UninstallTests(unittest.TestCase):
    """AC6 — uninstall removes the component but keeps the artifacts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.oracle = self.target / "oracle.sh"
        self.oracle.write_text(scaffold._render_oracle([]))
        _seed_placeholder(self.oracle)
        _write_plan(self.target, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])
        ov.install(self.target, "099-demo")

    def tearDown(self):
        self.tmp.cleanup()

    def test_uninstall_removes_block_and_entry(self):
        ov.uninstall(self.target, "099-demo")
        text = self.oracle.read_text()
        self.assertNotIn("# SEED:start spec_oracle_099_demo", text)
        self.assertNotIn('"spec_oracle_099_demo:', text)

    def test_uninstall_keeps_baseline(self):
        ov.uninstall(self.target, "099-demo")
        text = self.oracle.read_text()
        self.assertIn("# SEED:start placeholder", text)
        self.assertIn('"placeholder:1.0"', text)

    def test_uninstall_keeps_plan_artifacts(self):
        ov.uninstall(self.target, "099-demo")
        oracle_dir = self.target / ".servo" / "spec-oracles" / "099-demo"
        self.assertTrue((oracle_dir / "checks.json").is_file())
        self.assertTrue((oracle_dir / "checks.py").is_file())

    def test_oracle_valid_bash_after_uninstall(self):
        ov.uninstall(self.target, "099-demo")
        res = subprocess.run(["bash", "-n", str(self.oracle)],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)


# ===========================================================================
# AC1/AC2/AC3/AC4 — approve: negative controls + source/artifact hashes
# ===========================================================================


class ApproveTests(unittest.TestCase):
    """`approve` records the freeze state: it verifies the source spec is
    unchanged, runs each check's negative control and refuses if a check
    cannot be made to fail (AC4), then records artifact hashes and flips
    `approval_status` to approved (AC1)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        # A real servo-scaffolded target (oracle.sh + install.json) so the
        # approved-overlay gate run has the manifest it requires.
        scaffold.install(self.target, force=True)
        (self.target / "present.txt").write_text("x")
        # A falsifiable check: its negative control points at an absent path,
        # which must turn the passing file_presence check into a failure.
        _write_plan(self.target, "099-demo", [
            {"id": "AC-1", "family": "file_presence", "path": "present.txt",
             "negative_control": {"path": "definitely-absent.txt"}},
        ])
        ov.install(self.target, "099-demo")

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self) -> dict:
        return json.loads(
            (self.target / ".servo" / "spec-oracles" / "099-demo"
             / "checks.json").read_text())

    def test_approve_sets_status_and_records_hashes(self):
        ov.approve(self.target, "099-demo")
        plan = self._plan()
        self.assertEqual(plan["approval_status"], "approved")
        self.assertIn("checks.py", plan["approved_artifacts"])
        self.assertIn("oracle.sh.fragment", plan["approved_artifacts"])
        self.assertTrue(plan["approved_artifacts"]["checks.py"].startswith("sha256:"))
        # The approved checks are tripwire-pinned too (review hardening).
        self.assertIn("approved_content_hash", plan)

    def test_approve_refuses_non_falsifiable_negative_control(self):
        # Negative control that does NOT flip the check to failing → the check
        # is not falsifiable → approval refused (AC4).
        _write_plan(self.target, "099-demo", [
            {"id": "AC-1", "family": "file_presence", "path": "present.txt",
             "negative_control": {"path": "present.txt"}},  # still present → passes
        ])
        with self.assertRaises(ValueError):
            ov.approve(self.target, "099-demo")
        self.assertNotEqual(self._plan().get("approval_status"), "approved")

    def test_approve_refuses_changed_source(self):
        spec = self.target / "spec.md"
        spec.write_text("# spec\n")
        digest = "sha256:" + hashlib.sha256(spec.read_bytes()).hexdigest()
        d = self.target / ".servo" / "spec-oracles" / "099-demo"
        plan = json.loads((d / "checks.json").read_text())
        plan["source_spec_path"] = "spec.md"
        plan["source_hash"] = digest
        (d / "checks.json").write_text(json.dumps(plan))
        spec.write_text("# spec CHANGED\n")  # diverge from the recorded hash
        with self.assertRaises(ValueError):
            ov.approve(self.target, "099-demo")

    def test_approved_overlay_scores_through_gate(self):
        # The freeze gate is satisfied after approval, so the frozen component
        # scores normally.
        ov.approve(self.target, "099-demo")
        res = subprocess.run(
            [sys.executable, str(GATE_PY), str(self.target), "--json"],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


# ===========================================================================
# AC3 / AC4 / AC5 — end-to-end through a scaffolded target + stock gate.py
# ===========================================================================


class GateIntegrationTests(unittest.TestCase):
    """The overlay installs into a real servo-scaffolded target and is scored
    by the stock `gate.py` with no special-casing (AC5); the composite reflects
    the check summary score (AC3), env errors surface as rc=2 (AC3), and a run
    appends evidence to the ledger (AC4)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        # A real servo-scaffolded target (empty → no baseline component), so
        # the composite is exactly the overlay's score.
        scaffold.install(self.target, force=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _gate(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GATE_PY), str(self.target), "--json"],
            capture_output=True, text=True)

    def test_pass_path(self):
        (self.target / "present.txt").write_text("x")
        _write_plan(self.target, "099-demo",
                    [{"id": "AC-1", "family": "file_presence",
                      "path": "present.txt"}])
        ov.install(self.target, "099-demo")
        ov.approve(self.target, "099-demo")  # freeze gate must pass to score
        res = self._gate()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_fail_path(self):
        _write_plan(self.target, "099-demo",
                    [{"id": "AC-1", "family": "file_presence",
                      "path": "absent.txt"}])
        ov.install(self.target, "099-demo")
        ov.approve(self.target, "099-demo")  # freeze gate must pass to score
        res = self._gate()
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)

    def test_env_error_path(self):
        # A check that cannot be evaluated → score fn returns 2 → oracle rc=2.
        _write_plan(self.target, "099-demo",
                    [{"id": "AC-1", "family": "command"}])  # missing command
        ov.install(self.target, "099-demo")
        ov.approve(self.target, "099-demo")  # freeze gate must pass to score
        res = self._gate()
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)

    def test_ledger_appended_on_run(self):
        (self.target / "present.txt").write_text("x")
        _write_plan(self.target, "099-demo",
                    [{"id": "AC-1", "family": "file_presence",
                      "path": "present.txt"}])
        ov.install(self.target, "099-demo")
        ov.approve(self.target, "099-demo")
        self._gate()
        ledger = (self.target / ".servo" / "spec-oracles" / "099-demo"
                  / "ledger.jsonl")
        self.assertTrue(ledger.is_file(), "oracle run should append a ledger")
        rows = [json.loads(ln) for ln in ledger.read_text().splitlines()
                if ln.strip()]
        self.assertTrue(any(r.get("check_id") == "AC-1" for r in rows))

    def test_gate_json_reports_composite(self):
        (self.target / "present.txt").write_text("x")
        _write_plan(self.target, "099-demo",
                    [{"id": "AC-1", "family": "file_presence",
                      "path": "present.txt"}])
        ov.install(self.target, "099-demo")
        ov.approve(self.target, "099-demo")  # freeze gate must pass to score
        res = self._gate()
        payload = json.loads(res.stdout)
        # gate.py saw the overlay as an ordinary component and scored it; its
        # --json payload reports the weighted composite (key: "composite").
        self.assertEqual(payload.get("composite"), 1.0)
        self.assertEqual(payload.get("status"), "pass")


# ===========================================================================
# CLI
# ===========================================================================


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.oracle = self.target / "oracle.sh"
        self.oracle.write_text(scaffold._render_oracle([]))
        _write_plan(self.target, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(OVERLAY_PY), *[str(a) for a in args]],
            capture_output=True, text=True)

    def test_generate_via_cli(self):
        res = self._run("generate", self.target, "099-demo")
        self.assertEqual(res.returncode, 0, res.stderr)
        oracle_dir = self.target / ".servo" / "spec-oracles" / "099-demo"
        self.assertTrue((oracle_dir / "oracle.sh.fragment").is_file())
        self.assertTrue((oracle_dir / "checks.py").is_file())

    def test_approve_via_cli(self):
        self._run("install", self.target, "099-demo")
        res = self._run("approve", self.target, "099-demo")
        self.assertEqual(res.returncode, 0, res.stderr)
        plan = json.loads(
            (self.target / ".servo" / "spec-oracles" / "099-demo"
             / "checks.json").read_text())
        self.assertEqual(plan["approval_status"], "approved")

    def test_install_then_uninstall_via_cli(self):
        res = self._run("install", self.target, "099-demo")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("# SEED:start spec_oracle_099_demo",
                      self.oracle.read_text())
        res2 = self._run("uninstall", self.target, "099-demo")
        self.assertEqual(res2.returncode, 0, res2.stderr)
        self.assertNotIn("# SEED:start spec_oracle_099_demo",
                         self.oracle.read_text())


if __name__ == "__main__":
    unittest.main()
