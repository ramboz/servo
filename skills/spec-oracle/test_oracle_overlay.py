"""
AC verification tests for slice 006-03 (oracle-overlay) of `/servo:spec-oracle`,
updated by slice 019-02 (colocate-artifacts, ADR-0023) for the new artifact
home under the spec's own directory tree.

Run from the repo root:
    python3 skills/spec-oracle/test_oracle_overlay.py
or via pytest:
    uvx pytest skills/spec-oracle/test_oracle_overlay.py -q

`oracle_overlay.py` compiles a checked plan into an installable oracle
component: it writes an `oracle.sh.fragment` (a `# SEED:start/end
spec_oracle_<id>` block wrapping `score_spec_oracle_<id>`), references the
shared stdlib check engine (or, opt-in, vendors a copy for clone-portability),
and splices the component into the target's `oracle.sh` as an ordinary servo
component — so `gate.py` scores it with no special-casing (slice 006-03 AC5).

Idiom mirrors `test_oracle_plan.py` / `test_checks.py`: modules are imported
by path (the `spec-oracle` dir is not an importable package); a real target
is built with `scaffold.install(...)` and driven through the stock `gate.py`
for the end-to-end pass/fail/env-error paths (the DoD's integration check).

ADR-0023 (slice 019-02): the durable artifacts (`plan.md`, `checks.json`,
`oracle.sh.fragment`, and an opt-in vendored `checks.py`) now live under
``<spec_dir>/oracle/<spec_id>/`` — resolved relative to the spec's own
directory, passed to `generate`/`install`/`uninstall`/`approve` as `spec_dir`
— instead of ``<target>/.servo/spec-oracles/<spec_id>/``. `.servo/` retains
only run-scoped state (unaffected by this slice).
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


def _write_plan(spec_dir: Path, spec_id: str, checks: list, residual=None) -> Path:
    """Write a checks.json plan under <spec_dir>/oracle/<id>/ (ADR-0023)."""
    out = spec_dir / "oracle" / spec_id
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
        frag = ov.render_fragment(
            "099-demo", spec_oracle_dir="docs/specs/099-demo/oracle/099-demo")
        self.assertIn("# SEED:start spec_oracle_099_demo", frag)
        self.assertIn("# SEED:end spec_oracle_099_demo", frag)

    def test_fragment_defines_score_function(self):
        frag = ov.render_fragment(
            "099-demo", spec_oracle_dir="docs/specs/099-demo/oracle/099-demo")
        self.assertRegex(frag, r"score_spec_oracle_099_demo\s*\(\)\s*\{")

    def test_fragment_invokes_engine_score_only(self):
        # ADR-0023 (slice 019-02): the fragment's `checks.json` path is
        # relative to the spec's own oracle dir, not
        # `.servo/spec-oracles/<id>/`. The shared engine is referenced at its
        # plugin-sibling location by default (AC3) — see
        # NoPerOverlayEngineCopyTests / VendorCopyOptInTests for the exact
        # engine-path assertions.
        frag = ov.render_fragment(
            "099-demo", spec_oracle_dir="docs/specs/099-demo/oracle/099-demo")
        self.assertIn("--score-only", frag)
        self.assertIn("docs/specs/099-demo/oracle/099-demo/checks.json", frag)
        self.assertNotIn(".servo/spec-oracles", frag)

    def test_fragment_enforces_freeze(self):
        # The installed component runs the engine with the freeze gate on, so
        # the loop can only score an approved, unmodified overlay (006-04).
        frag = ov.render_fragment(
            "099-demo", spec_oracle_dir="docs/specs/099-demo/oracle/099-demo")
        self.assertIn("--enforce-freeze", frag)

    def test_fragment_guards_missing_python(self):
        # A missing python3 is an environment error (rc=2), not a crash.
        frag = ov.render_fragment(
            "099-demo", spec_oracle_dir="docs/specs/099-demo/oracle/099-demo")
        self.assertIn("command -v python3", frag)
        self.assertIn("return 2", frag)

    def test_seed_block_is_balanced(self):
        frag = ov.render_fragment(
            "099-demo", spec_oracle_dir="docs/specs/099-demo/oracle/099-demo")
        starts = re.findall(r"^# SEED:start (\S+)\s*$", frag, re.MULTILINE)
        ends = re.findall(r"^# SEED:end (\S+)\s*$", frag, re.MULTILINE)
        self.assertEqual(starts, ends)
        self.assertEqual(len(starts), 1)


class GenerateTests(unittest.TestCase):
    """AC1 — generate writes the fragment; the engine is referenced, not
    copied, by default (AC3 — see NoPerOverlayEngineCopyTests for the
    dedicated assertions)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_generate_writes_fragment(self):
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])
        ov.generate(self.target, self.spec_dir, "099-demo")
        oracle_dir = self.spec_dir / "oracle" / "099-demo"
        self.assertTrue((oracle_dir / "oracle.sh.fragment").is_file())

    def test_generate_requires_a_plan(self):
        # No checks.json yet → generate refuses (nothing to compile).
        with self.assertRaises(FileNotFoundError):
            ov.generate(self.target, self.spec_dir, "099-demo")


# ===========================================================================
# AC1 — colocated artifact path (slice 019-02 / ADR-0023)
# ===========================================================================


class ColocatedArtifactPathTests(unittest.TestCase):
    """AC1 — plan/generate/install/approve read/write `plan.md`, `checks.json`,
    `oracle.sh.fragment` under `<spec_dir>/oracle/<spec_id>/` (resolved
    relative to the spec path, not the target), via one shared path helper."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
        scaffold.install(self.target, force=True)
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_shared_helper_resolves_spec_relative_dir(self):
        # `oracle_overlay.py` exposes the one shared path helper both it and
        # `oracle_plan.py` call — no independent path recomputation.
        expected = self.spec_dir / "oracle" / "099-demo"
        self.assertEqual(ov.oracle_dir_for_spec(self.spec_dir, "099-demo"), expected)

    def test_generate_writes_under_spec_dir_not_target_servo(self):
        ov.generate(self.target, self.spec_dir, "099-demo")
        oracle_dir = self.spec_dir / "oracle" / "099-demo"
        self.assertTrue((oracle_dir / "oracle.sh.fragment").is_file())
        self.assertFalse((self.target / ".servo" / "spec-oracles").exists())

    def test_install_writes_under_spec_dir(self):
        ov.install(self.target, self.spec_dir, "099-demo")
        oracle_dir = self.spec_dir / "oracle" / "099-demo"
        self.assertTrue((oracle_dir / "oracle.sh.fragment").is_file())
        self.assertFalse((self.target / ".servo" / "spec-oracles").exists())

    def test_approve_reads_and_writes_under_spec_dir(self):
        (self.target / "x").write_text("hi")
        ov.install(self.target, self.spec_dir, "099-demo")
        ov.approve(self.target, self.spec_dir, "099-demo")
        checks_json = self.spec_dir / "oracle" / "099-demo" / "checks.json"
        plan = json.loads(checks_json.read_text())
        self.assertEqual(plan["approval_status"], "approved")

    def test_spec_dir_can_differ_from_target(self):
        # The oracle dir is spec-relative, independent of the target root —
        # e.g. specs living outside the scaffolded target.
        other_root = Path(tempfile.mkdtemp())
        try:
            other_spec_dir = other_root / "docs" / "specs" / "042-elsewhere"
            other_spec_dir.mkdir(parents=True)
            _write_plan(other_spec_dir, "042-elsewhere",
                        [{"id": "AC-1", "family": "file_presence", "path": "x"}])
            ov.generate(self.target, other_spec_dir, "042-elsewhere")
            oracle_dir = other_spec_dir / "oracle" / "042-elsewhere"
            self.assertTrue((oracle_dir / "oracle.sh.fragment").is_file())
        finally:
            __import__("shutil").rmtree(other_root, ignore_errors=True)


class SpecIdValidationIsCentralizedTests(unittest.TestCase):
    """`oracle_dir_for_spec` (the one shared path-construction chokepoint)
    rejects a malformed / path-traversal-shaped `spec_id` itself, so every
    caller is protected regardless of whether it separately validates —
    closing the gap where `oracle_plan.py`'s `--spec-id` reached
    `oracle_dir_for_spec` with no guard against e.g. `../../../tmp/evil`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejects_traversal_spec_id(self):
        with self.assertRaises(ValueError):
            ov.oracle_dir_for_spec(self.spec_dir, "../../../tmp/evil")

    def test_rejects_dot_dot_spec_id(self):
        with self.assertRaises(ValueError):
            ov.oracle_dir_for_spec(self.spec_dir, "..")

    def test_accepts_ordinary_spec_id(self):
        # Sanity: the guard doesn't reject legitimate ids.
        result = ov.oracle_dir_for_spec(self.spec_dir, "099-demo")
        self.assertEqual(result, self.spec_dir / "oracle" / "099-demo")


# ===========================================================================
# AC2 — spec_id no longer restates the spec's own path
# ===========================================================================


class SpecIdNoLongerDuplicatesPathTests(unittest.TestCase):
    """AC2 — since artifacts live inside the spec's own directory, a bare
    slice fragment (e.g. `015-01`) suffices as spec_id; nothing requires it to
    restate the full spec path (e.g. `015-01-typed-cross-reference-schema`)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.spec_dir = self.target / "docs" / "specs" / "015-typed-refs"
        self.spec_dir.mkdir(parents=True)
        scaffold.install(self.target, force=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_bare_slice_fragment_is_a_valid_spec_id(self):
        _write_plan(self.spec_dir, "015-01",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])
        ov.install(self.target, self.spec_dir, "015-01")
        oracle_dir = self.spec_dir / "oracle" / "015-01"
        self.assertTrue((oracle_dir / "oracle.sh.fragment").is_file())
        self.assertIn("# SEED:start spec_oracle_015_01",
                      (self.target / "oracle.sh").read_text())

    def test_full_path_style_id_still_accepted_but_not_required(self):
        # The old, longer style remains a legal spec_id (no format is
        # enforced beyond the existing shell-safe slug rule) — AC2 only
        # removes the *need* to duplicate the path, not the ability to.
        long_id = "015-01-typed-cross-reference-schema"
        _write_plan(self.spec_dir, long_id,
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])
        ov.install(self.target, self.spec_dir, long_id)
        oracle_dir = self.spec_dir / "oracle" / long_id
        self.assertTrue((oracle_dir / "oracle.sh.fragment").is_file())


# ===========================================================================
# AC3 — checks.py referenced, not copied, by default; vendor is opt-in
# ===========================================================================


class NoPerOverlayEngineCopyTests(unittest.TestCase):
    """AC3 (default path) — no `checks.py` is written under the spec's oracle
    dir; the fragment references the shared, plugin-sibling `checks.py`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_generate_does_not_copy_checks_py(self):
        ov.generate(self.target, self.spec_dir, "099-demo")
        oracle_dir = self.spec_dir / "oracle" / "099-demo"
        self.assertFalse((oracle_dir / "checks.py").exists())

    def test_fragment_references_shared_engine_path(self):
        ov.generate(self.target, self.spec_dir, "099-demo")
        fragment = (self.spec_dir / "oracle" / "099-demo"
                    / "oracle.sh.fragment").read_text()
        # Resolved the same way oracle_overlay.py resolves its own sibling
        # engine: a path ending in skills/spec-oracle/checks.py.
        self.assertIn("skills/spec-oracle/checks.py", fragment)

    def test_install_does_not_copy_checks_py_by_default(self):
        oracle = self.target / "oracle.sh"
        oracle.write_text(scaffold._render_oracle([]))
        ov.install(self.target, self.spec_dir, "099-demo")
        oracle_dir = self.spec_dir / "oracle" / "099-demo"
        self.assertFalse((oracle_dir / "checks.py").exists())


class VendorCopyOptInTests(unittest.TestCase):
    """AC3 (opt-in) — `--vendor-engine` (`vendor_engine=True`) still copies
    `checks.py` alongside the plan, for the documented clone-portability case
    (a Routine/CI that clones the repo without the servo plugin installed)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_generate_with_vendor_flag_copies_checks_py(self):
        ov.generate(self.target, self.spec_dir, "099-demo", vendor_engine=True)
        oracle_dir = self.spec_dir / "oracle" / "099-demo"
        copied = oracle_dir / "checks.py"
        self.assertTrue(copied.is_file())
        body = copied.read_text()
        self.assertIn("def run_checks", body)
        self.assertIn("--score-only", body)

    def test_fragment_references_local_copy_when_vendored(self):
        ov.generate(self.target, self.spec_dir, "099-demo", vendor_engine=True)
        fragment = (self.spec_dir / "oracle" / "099-demo"
                    / "oracle.sh.fragment").read_text()
        self.assertIn("docs/specs/099-demo/oracle/099-demo/checks.py", fragment)

    def test_install_with_vendor_flag_via_cli(self):
        oracle = self.target / "oracle.sh"
        oracle.write_text(scaffold._render_oracle([]))
        res = subprocess.run(
            [sys.executable, str(OVERLAY_PY), "install", str(self.target),
             str(self.spec_dir), "099-demo", "--vendor-engine"],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        oracle_dir = self.spec_dir / "oracle" / "099-demo"
        self.assertTrue((oracle_dir / "checks.py").is_file())


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
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
        self.oracle = self.target / "oracle.sh"
        self.oracle.write_text(scaffold._render_oracle([]))
        _seed_placeholder(self.oracle)
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_adds_component_and_keeps_baseline(self):
        ov.install(self.target, self.spec_dir, "099-demo")
        text = self.oracle.read_text()
        # Baseline placeholder is untouched.
        self.assertIn("# SEED:start placeholder", text)
        self.assertIn('"placeholder:1.0"', text)
        # Overlay component added.
        self.assertIn("# SEED:start spec_oracle_099_demo", text)
        self.assertIn('"spec_oracle_099_demo:1.0"', text)

    def test_install_is_idempotent(self):
        ov.install(self.target, self.spec_dir, "099-demo")
        ov.install(self.target, self.spec_dir, "099-demo")
        text = self.oracle.read_text()
        self.assertEqual(text.count("# SEED:start spec_oracle_099_demo"), 1)
        self.assertEqual(text.count('"spec_oracle_099_demo:'), 1)

    def test_custom_weight(self):
        ov.install(self.target, self.spec_dir, "099-demo", weight=0.25)
        self.assertIn('"spec_oracle_099_demo:0.25"', self.oracle.read_text())

    def test_install_requires_oracle(self):
        bare = Path(tempfile.mkdtemp())
        try:
            bare_spec_dir = bare / "docs" / "specs" / "099-demo"
            _write_plan(bare_spec_dir, "099-demo",
                        [{"id": "AC-1", "family": "file_presence", "path": "x"}])
            with self.assertRaises(FileNotFoundError):
                ov.install(bare, bare_spec_dir, "099-demo")
        finally:
            __import__("shutil").rmtree(bare, ignore_errors=True)

    def test_installed_oracle_is_valid_bash(self):
        ov.install(self.target, self.spec_dir, "099-demo")
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
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
        self.oracle = self.target / "oracle.sh"
        self.oracle.write_text(scaffold._render_oracle([]))
        _seed_placeholder(self.oracle)
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])
        ov.install(self.target, self.spec_dir, "099-demo")

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
        # ADR-0023 (slice 019-02): the artifacts live under the spec's own
        # oracle dir now, not `.servo/spec-oracles/<id>/`; uninstall never
        # touches `.servo/` (AC4) and leaves the spec-dir artifacts intact.
        ov.uninstall(self.target, "099-demo")
        oracle_dir = self.spec_dir / "oracle" / "099-demo"
        self.assertTrue((oracle_dir / "checks.json").is_file())
        self.assertTrue((oracle_dir / "oracle.sh.fragment").is_file())

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
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
        # A real servo-scaffolded target (oracle.sh + install.json) so the
        # approved-overlay gate run has the manifest it requires.
        scaffold.install(self.target, force=True)
        (self.target / "present.txt").write_text("x")
        # A falsifiable check: its negative control points at an absent path,
        # which must turn the passing file_presence check into a failure.
        _write_plan(self.spec_dir, "099-demo", [
            {"id": "AC-1", "family": "file_presence", "path": "present.txt",
             "negative_control": {"path": "definitely-absent.txt"}},
        ])
        ov.install(self.target, self.spec_dir, "099-demo")

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self) -> dict:
        return json.loads(
            (self.spec_dir / "oracle" / "099-demo"
             / "checks.json").read_text())

    def test_approve_sets_status_and_records_hashes(self):
        ov.approve(self.target, self.spec_dir, "099-demo")
        plan = self._plan()
        self.assertEqual(plan["approval_status"], "approved")
        self.assertIn("oracle.sh.fragment", plan["approved_artifacts"])
        # No local checks.py by default (AC3) — only the fragment is hashed.
        self.assertNotIn("checks.py", plan["approved_artifacts"])
        self.assertTrue(
            plan["approved_artifacts"]["oracle.sh.fragment"].startswith("sha256:"))
        # The approved checks are tripwire-pinned too (review hardening).
        self.assertIn("approved_content_hash", plan)

    def test_approve_refuses_non_falsifiable_negative_control(self):
        # Negative control that does NOT flip the check to failing → the check
        # is not falsifiable → approval refused (AC4).
        _write_plan(self.spec_dir, "099-demo", [
            {"id": "AC-1", "family": "file_presence", "path": "present.txt",
             "negative_control": {"path": "present.txt"}},  # still present → passes
        ])
        with self.assertRaises(ValueError):
            ov.approve(self.target, self.spec_dir, "099-demo")
        self.assertNotEqual(self._plan().get("approval_status"), "approved")

    def test_approve_refuses_changed_source(self):
        spec = self.target / "spec.md"
        spec.write_text("# spec\n")
        digest = "sha256:" + hashlib.sha256(spec.read_bytes()).hexdigest()
        d = self.spec_dir / "oracle" / "099-demo"
        plan = json.loads((d / "checks.json").read_text())
        plan["source_spec_path"] = "spec.md"
        plan["source_hash"] = digest
        (d / "checks.json").write_text(json.dumps(plan))
        spec.write_text("# spec CHANGED\n")  # diverge from the recorded hash
        with self.assertRaises(ValueError):
            ov.approve(self.target, self.spec_dir, "099-demo")

    def test_approved_overlay_scores_through_gate(self):
        # The freeze gate is satisfied after approval, so the frozen component
        # scores normally.
        ov.approve(self.target, self.spec_dir, "099-demo")
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
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
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
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence",
                      "path": "present.txt"}])
        ov.install(self.target, self.spec_dir, "099-demo")
        ov.approve(self.target, self.spec_dir, "099-demo")  # freeze gate must pass to score
        res = self._gate()
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_fail_path(self):
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence",
                      "path": "absent.txt"}])
        ov.install(self.target, self.spec_dir, "099-demo")
        ov.approve(self.target, self.spec_dir, "099-demo")  # freeze gate must pass to score
        res = self._gate()
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)

    def test_env_error_path(self):
        # A check that cannot be evaluated → score fn returns 2 → oracle rc=2.
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "command"}])  # missing command
        ov.install(self.target, self.spec_dir, "099-demo")
        ov.approve(self.target, self.spec_dir, "099-demo")  # freeze gate must pass to score
        res = self._gate()
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)

    def test_ledger_appended_on_run(self):
        (self.target / "present.txt").write_text("x")
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence",
                      "path": "present.txt"}])
        ov.install(self.target, self.spec_dir, "099-demo")
        ov.approve(self.target, self.spec_dir, "099-demo")
        self._gate()
        ledger = (self.spec_dir / "oracle" / "099-demo" / "ledger.jsonl")
        self.assertTrue(ledger.is_file(), "oracle run should append a ledger")
        rows = [json.loads(ln) for ln in ledger.read_text().splitlines()
                if ln.strip()]
        self.assertTrue(any(r.get("check_id") == "AC-1" for r in rows))

    def test_gate_json_reports_composite(self):
        (self.target / "present.txt").write_text("x")
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence",
                      "path": "present.txt"}])
        ov.install(self.target, self.spec_dir, "099-demo")
        ov.approve(self.target, self.spec_dir, "099-demo")  # freeze gate must pass to score
        res = self._gate()
        payload = json.loads(res.stdout)
        # gate.py saw the overlay as an ordinary component and scored it; its
        # --json payload reports the weighted composite (key: "composite").
        self.assertEqual(payload.get("composite"), 1.0)
        self.assertEqual(payload.get("status"), "pass")


# ===========================================================================
# AC4 — .servo/ holds only ephemeral state
# ===========================================================================


class ServoDirHoldsNoDurableSpecOracleArtifactsTests(unittest.TestCase):
    """AC4 — after generate/install/approve/uninstall + a scored gate run,
    nothing new is written under `<target>/.servo/spec-oracles/`; `.servo/`
    only ever gains run-scoped state — the ledger now lives in the spec's own
    oracle dir too, per this slice's colocation."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
        scaffold.install(self.target, force=True)
        (self.target / "present.txt").write_text("x")
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence",
                      "path": "present.txt"}])

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_lifecycle_writes_nothing_under_servo_spec_oracles(self):
        ov.install(self.target, self.spec_dir, "099-demo")
        ov.approve(self.target, self.spec_dir, "099-demo")
        subprocess.run([sys.executable, str(GATE_PY), str(self.target), "--json"],
                       capture_output=True, text=True)
        ov.uninstall(self.target, "099-demo")
        self.assertFalse((self.target / ".servo" / "spec-oracles").exists())

    def test_generate_alone_writes_nothing_under_servo_spec_oracles(self):
        ov.generate(self.target, self.spec_dir, "099-demo")
        self.assertFalse((self.target / ".servo" / "spec-oracles").exists())


# ===========================================================================
# AC5 — migration path for existing `.servo/spec-oracles/<id>/` installs
# ===========================================================================


class ExistingOverlayMigrationTests(unittest.TestCase):
    """AC5 — a target that already has `.servo/spec-oracles/<id>/` from
    before this slice is not broken: the chosen approach is a soft
    read-fallback — `oracle_dir_for_spec` falls back to the legacy
    `.servo/spec-oracles/<id>/` location when the new spec-relative location
    is absent, so an old installed `oracle.sh`'s SEED block keeps working
    without a forced migration step."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
        scaffold.install(self.target, force=True)
        # Simulate a pre-019-02 install: artifacts under .servo/spec-oracles/.
        self.legacy_dir = self.target / ".servo" / "spec-oracles" / "099-demo"
        self.legacy_dir.mkdir(parents=True)
        (self.legacy_dir / "checks.json").write_text(json.dumps({
            "schema_version": 1, "spec_id": "099-demo",
            "checks": [{"id": "AC-1", "family": "file_presence", "path": "x"}],
            "residual_judgment": [],
        }))

    def tearDown(self):
        self.tmp.cleanup()

    def test_oracle_dir_for_spec_falls_back_to_legacy_location(self):
        # No new-location checks.json exists; the helper must resolve to the
        # legacy .servo/spec-oracles/<id>/ dir rather than a fresh, empty
        # spec-relative dir with nothing in it.
        resolved = ov.oracle_dir_for_spec(self.spec_dir, "099-demo", target=self.target)
        self.assertEqual(resolved, self.legacy_dir)

    def test_generate_still_works_against_legacy_location(self):
        # generate can compile a fragment for a legacy-location plan without
        # requiring a migration step first.
        ov.generate(self.target, self.spec_dir, "099-demo")
        self.assertTrue((self.legacy_dir / "oracle.sh.fragment").is_file())

    def test_new_location_takes_precedence_once_present(self):
        # Once the spec-relative location has its own checks.json (e.g. after
        # a re-plan with this slice's oracle_plan.py), it wins over the
        # legacy fallback.
        new_dir = self.spec_dir / "oracle" / "099-demo"
        new_dir.mkdir(parents=True)
        (new_dir / "checks.json").write_text(json.dumps({
            "schema_version": 1, "spec_id": "099-demo",
            "checks": [], "residual_judgment": [],
        }))
        resolved = ov.oracle_dir_for_spec(self.spec_dir, "099-demo", target=self.target)
        self.assertEqual(resolved, new_dir)


# ===========================================================================
# Slice 019-05 — single-to-multi-component upgrade
# ===========================================================================


class SingleToMultiComponentUpgradeTests(unittest.TestCase):
    """AC #4 — `install` splicing a second component into a freshly
    scaffolded single-component `oracle.sh` still finds the `COMPONENTS=(`
    anchor and `# SEED:` markers (the single-component runtime branch does
    not disturb the regexes `install` relies on), and the resulting
    oracle.sh correctly falls onto the multi-component weighted-average
    branch."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
        scaffold.install(self.target, force=True)
        # Seed a single real component (mirrors test_scaffold.py's
        # placeholder-seeding convention) so the target starts with exactly
        # one COMPONENTS entry before the overlay adds a second.
        oracle = self.target / "oracle.sh"
        text = oracle.read_text()
        text, n = re.subn(
            r"COMPONENTS=\(\s*\n", 'COMPONENTS=(\n  "placeholder:1.0"\n', text, count=1)
        assert n == 1, "could not seed a baseline placeholder component"
        text, n2 = re.subn(
            r'(weighted_sum="0")',
            "\n# SEED:start placeholder\n"
            "score_placeholder() {\n"
            '  echo "${PLACEHOLDER_SCORE:-1.0}"\n'
            "}\n"
            "# SEED:end placeholder\n"
            r"\1",
            text, count=1)
        assert n2 == 1, "could not insert baseline placeholder SEED block"
        oracle.write_text(text)

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_finds_anchors_on_single_component_oracle(self):
        oracle_before = (self.target / "oracle.sh").read_text()
        self.assertEqual(oracle_before.count('"placeholder:1.0"'), 1)
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "present.txt"}])
        # Must not raise — the COMPONENTS=( and SEED-block anchors must
        # still be present verbatim in the single-component template.
        ov.install(self.target, self.spec_dir, "099-demo")
        oracle_after = (self.target / "oracle.sh").read_text()
        self.assertIn("# SEED:start spec_oracle_099_demo", oracle_after)
        self.assertRegex(oracle_after, r'"spec_oracle_099_demo:[0-9.]+"')
        self.assertIn('"placeholder:1.0"', oracle_after,
                      "baseline component must survive the splice")

    def test_upgraded_oracle_takes_weighted_average_branch(self):
        (self.target / "present.txt").write_text("x")
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "present.txt"}])
        ov.install(self.target, self.spec_dir, "099-demo")
        ov.approve(self.target, self.spec_dir, "099-demo")
        env = os.environ.copy()
        env["PLACEHOLDER_SCORE"] = "0.0"
        result = subprocess.run(
            ["bash", str(self.target / "oracle.sh")],
            capture_output=True, text=True,
            env=env,
            cwd=str(self.target),
        )
        # placeholder=0.0 (weight 1.0) + spec-oracle=1.0 (weight 1.0),
        # equally weighted -> composite 0.5. Proves the two-component
        # oracle takes the weighted-average branch, not the single-score
        # direct-compare branch.
        self.assertIn("composite=0.5", result.stdout,
                      f"expected a weighted-average composite: {result.stdout!r}")


# ===========================================================================
# CLI
# ===========================================================================


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)
        self.spec_dir = self.target / "docs" / "specs" / "099-demo"
        self.spec_dir.mkdir(parents=True)
        self.oracle = self.target / "oracle.sh"
        self.oracle.write_text(scaffold._render_oracle([]))
        _write_plan(self.spec_dir, "099-demo",
                    [{"id": "AC-1", "family": "file_presence", "path": "x"}])

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(OVERLAY_PY), *[str(a) for a in args]],
            capture_output=True, text=True)

    def test_generate_via_cli(self):
        res = self._run("generate", self.target, self.spec_dir, "099-demo")
        self.assertEqual(res.returncode, 0, res.stderr)
        oracle_dir = self.spec_dir / "oracle" / "099-demo"
        self.assertTrue((oracle_dir / "oracle.sh.fragment").is_file())

    def test_approve_via_cli(self):
        self._run("install", self.target, self.spec_dir, "099-demo")
        res = self._run("approve", self.target, self.spec_dir, "099-demo")
        self.assertEqual(res.returncode, 0, res.stderr)
        plan = json.loads(
            (self.spec_dir / "oracle" / "099-demo"
             / "checks.json").read_text())
        self.assertEqual(plan["approval_status"], "approved")

    def test_install_then_uninstall_via_cli(self):
        res = self._run("install", self.target, self.spec_dir, "099-demo")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("# SEED:start spec_oracle_099_demo",
                      self.oracle.read_text())
        res2 = self._run("uninstall", self.target, "099-demo")
        self.assertEqual(res2.returncode, 0, res2.stderr)
        self.assertNotIn("# SEED:start spec_oracle_099_demo",
                         self.oracle.read_text())


if __name__ == "__main__":
    unittest.main()
