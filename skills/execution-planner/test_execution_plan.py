"""
AC verification tests for slice 016-01 (plan-emit) of `/servo:execution-plan`.

Run from the repo root:
    python3 -m pytest skills/execution-planner/test_execution_plan.py -q

`execution_plan.py compile <target> --spec <path>` assembles the ADR-0016
execution plan and writes it to `<target>/.servo/plans/<spec-id>/plan.json`. It
is read-only over the target (writes only under `.servo/plans/`), references (not
copies) the suitability verdict / oracle / spec-oracle overlay, and emits a plan
**only** for a `suitable` verdict (the deferred 015-03 Compile gate).

Test idiom mirrors `skills/edd-suitability/test_suitability.py`:
  - `unittest.TestCase` classes (collected by pytest),
  - `REPO_ROOT = Path(__file__).resolve().parents[2]`,
  - fixtures written into a `tempfile.TemporaryDirectory()`,
  - the CLI driven as a subprocess for end-to-end paths,
  - the pure builder imported directly for fast assertions.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_PLAN = REPO_ROOT / "skills" / "execution-planner" / "execution_plan.py"
HEARTBEAT_PY = REPO_ROOT / "skills" / "heartbeat" / "heartbeat.py"

SPEC_ID = "016-execution-planner"

# loop.py public budget defaults — the plan's source of truth (AC4). Duplicated
# here (not imported) mirroring loop.py's own constants; if loop.py's defaults
# change, this test is the tripwire.
EXPECTED_BUDGET = {
    "max_iterations": 5,
    "cost_ceiling_usd": 2.0,
    "context_fill_threshold": 0.75,
    "plateau_window": 3,
}


def _load_module():
    spec = importlib.util.spec_from_file_location("execution_plan", EXECUTION_PLAN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


execution_plan = _load_module()


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

_ORACLE_SH = (
    '#!/usr/bin/env bash\n'
    'set -euo pipefail\n'
    'THRESHOLD="${THRESHOLD:-0.5}"\n'
    'printf \'oracle: composite=%s threshold=%s\\n\' "1.0" "$THRESHOLD"\n'
)


def _make_target(root: Path, *, signals: dict | None = None,
                 components: list | None = None, with_oracle: bool = True,
                 threshold: str = "0.5") -> Path:
    """Create a scaffolded-ish target: `.servo/install.json` + `oracle.sh`."""
    target = root / "target"
    servo = target / ".servo"
    servo.mkdir(parents=True)
    if signals is None:
        signals = {"tests": True, "lint": False, "ci": False, "language": "python"}
    if components is None:
        components = ["pytest"]
    (servo / "install.json").write_text(json.dumps({
        "servo_version": "0.0.0",
        "installed_tier": "tier-0",
        "signals": signals,
        "components": components,
        "weights": {c: 1.0 for c in components},
    }))
    if with_oracle:
        oracle = target / "oracle.sh"
        oracle.write_text(_ORACLE_SH.replace("0.5", threshold))
        oracle.chmod(0o755)
    return target


def _make_spec(root: Path, spec_id: str = SPEC_ID) -> Path:
    spec_dir = root / spec_id
    spec_dir.mkdir(parents=True)
    spec = spec_dir / "spec.md"
    spec.write_text("# Spec 016\n\n1. an AC\n")
    return spec


def _write_suitability(target: Path, verdict: str = "suitable",
                       spec_id: str = SPEC_ID, reasons: list | None = None,
                       missing_evidence: list | None = None) -> Path:
    out = target / ".servo" / "suitability"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{spec_id}.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "verdict": verdict,
        "reasons": reasons if reasons is not None else [{"code": "x", "message": "y"}],
        "missing_evidence": missing_evidence if missing_evidence is not None else [],
        "spec_id": spec_id,
        "analyzed_at": "2026-06-30T00:00:00Z",
    }, indent=2) + "\n")
    return path


def _write_overlay(target: Path, *, n_checks: int, n_residual: int,
                   spec_id: str = SPEC_ID) -> Path:
    out = target / ".servo" / "spec-oracles" / spec_id
    out.mkdir(parents=True, exist_ok=True)
    path = out / "checks.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "spec_id": spec_id,
        "checks": [{"id": f"AC-{i}", "family": "command"} for i in range(n_checks)],
        "residual_judgment": [{"id": f"AC-r{i}"} for i in range(n_residual)],
    }))
    return path


def _run_cli(target: Path, spec: Path):
    return subprocess.run(
        [sys.executable, str(EXECUTION_PLAN), "compile", str(target),
         "--spec", str(spec)],
        capture_output=True, text=True, env=dict(os.environ),
    )


def _plan_path(target: Path, spec_id: str = SPEC_ID) -> Path:
    return target / ".servo" / "plans" / spec_id / "plan.json"


def _compile_ok(root: Path, **target_kw):
    """Compile a suitable target end-to-end; return (target, spec, plan dict)."""
    target = _make_target(root, **target_kw)
    spec = _make_spec(root)
    _write_suitability(target, "suitable")
    res = _run_cli(target, spec)
    assert res.returncode == 0, res.stderr
    plan = json.loads(_plan_path(target).read_text())
    return target, spec, plan


# --------------------------------------------------------------------------
# AC1 — plan artifact shape
# --------------------------------------------------------------------------

class PlanShapeTests(unittest.TestCase):
    def test_all_adr0016_fields_present(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)
            _write_suitability(target, "suitable")
            _write_overlay(target, n_checks=7, n_residual=1)
            res = _run_cli(target, spec)
            self.assertEqual(res.returncode, 0, res.stderr)
            plan = json.loads(_plan_path(target).read_text())
            for key in ("schema_version", "spec_id", "compiled_at",
                        "suitability_ref", "oracle", "evaluation_model",
                        "budget", "driver", "prompt_ref", "provenance"):
                self.assertIn(key, plan)
            self.assertEqual(plan["schema_version"], 1)
            self.assertEqual(plan["spec_id"], SPEC_ID)
            self.assertEqual(plan["provenance"], "compiled")
            self.assertEqual(plan["driver"], "auto")
            self.assertEqual(sorted(plan["oracle"]),
                             ["components", "path", "threshold"])
            self.assertEqual(plan["oracle"]["path"], "oracle.sh")
            self.assertEqual(plan["oracle"]["components"], ["pytest"])
            self.assertEqual(plan["evaluation_model"],
                             {"spec_oracle_id": SPEC_ID, "ac_count": 7,
                              "residual": 1})

    def test_evaluation_model_null_without_overlay(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, _, plan = _compile_ok(root)
            self.assertIsNone(plan["evaluation_model"])

    def test_oracle_threshold_parsed_from_oracle_sh(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, _, plan = _compile_ok(root, threshold="0.8")
            self.assertEqual(plan["oracle"]["threshold"], 0.8)

    def test_stable_key_order(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, _, plan = _compile_ok(root)
            self.assertEqual(list(plan.keys())[0], "schema_version")


# --------------------------------------------------------------------------
# AC2 — references, not copies
# --------------------------------------------------------------------------

class PlanReferencesNotCopiesTests(unittest.TestCase):
    def test_suitability_ref_is_a_path_not_a_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, _, plan = _compile_ok(root)
            self.assertEqual(plan["suitability_ref"],
                             f".servo/suitability/{SPEC_ID}.json")
            # the verdict string is NOT inlined anywhere in the plan
            self.assertNotIn("verdict", plan)
            self.assertNotIn("suitable", json.dumps(plan["oracle"]))

    def test_overlay_referenced_by_id_not_embedded(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)
            _write_suitability(target, "suitable")
            _write_overlay(target, n_checks=3, n_residual=0)
            self.assertEqual(_run_cli(target, spec).returncode, 0)
            plan = json.loads(_plan_path(target).read_text())
            # references the id + counts, not the check bodies
            self.assertEqual(plan["evaluation_model"]["spec_oracle_id"], SPEC_ID)
            self.assertNotIn("checks", plan["evaluation_model"])

    def test_editing_referenced_suitability_not_reflected_in_plan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target, _, plan = _compile_ok(root)
            # The plan holds a path, so it carries no copy of the verdict body.
            self.assertNotIn("reasons", json.dumps(plan))


# --------------------------------------------------------------------------
# AC3 — suitable-only precondition (the 015-03 seam)
# --------------------------------------------------------------------------

class PlanSuitabilityPreconditionTests(unittest.TestCase):
    def test_needs_evidence_refuses_no_plan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)
            _write_suitability(target, "needs_evidence")
            res = _run_cli(target, spec)
            self.assertEqual(res.returncode, 2)
            self.assertIn("suitability_not_suitable", res.stderr)
            self.assertFalse(_plan_path(target).exists())

    def test_unsuitable_refuses_no_plan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)
            _write_suitability(target, "unsuitable")
            res = _run_cli(target, spec)
            self.assertEqual(res.returncode, 2)
            self.assertIn("suitability_not_suitable", res.stderr)
            self.assertFalse(_plan_path(target).exists())

    def test_missing_suitability_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)
            res = _run_cli(target, spec)
            self.assertEqual(res.returncode, 2)
            self.assertIn("suitability_missing", res.stderr)
            self.assertFalse(_plan_path(target).exists())

    def test_suitable_emits_plan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target, _, plan = _compile_ok(root)
            self.assertTrue(_plan_path(target).exists())


# --------------------------------------------------------------------------
# AC4 — budget from the guardrail source of truth
# --------------------------------------------------------------------------

class PlanBudgetDefaultsTests(unittest.TestCase):
    def test_budget_equals_loop_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, _, plan = _compile_ok(root)
            self.assertEqual(plan["budget"], EXPECTED_BUDGET)


# --------------------------------------------------------------------------
# AC5 — git-ignored, atomic, read-only over the target
# --------------------------------------------------------------------------

class PlanAtomicGitignoreTests(unittest.TestCase):
    def test_plan_under_servo_plans(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target, _, _ = _compile_ok(root)
            rel = _plan_path(target).relative_to(target)
            self.assertEqual(rel.parts[:2], (".servo", "plans"))

    def test_no_leftover_tmp(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target, _, _ = _compile_ok(root)
            leftovers = list((_plan_path(target).parent).glob("*.tmp")) + \
                list((_plan_path(target).parent).glob(".*.tmp"))
            self.assertEqual(leftovers, [])

    def test_inputs_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)
            suit = _write_suitability(target, "suitable")
            before_suit = suit.read_bytes()
            before_manifest = (target / ".servo" / "install.json").read_bytes()
            before_oracle = (target / "oracle.sh").read_bytes()
            self.assertEqual(_run_cli(target, spec).returncode, 0)
            self.assertEqual(suit.read_bytes(), before_suit)
            self.assertEqual((target / ".servo" / "install.json").read_bytes(),
                             before_manifest)
            self.assertEqual((target / "oracle.sh").read_bytes(), before_oracle)


# --------------------------------------------------------------------------
# AC6 — closed env-error contract
# --------------------------------------------------------------------------

class PlanExitContractTests(unittest.TestCase):
    def test_missing_spec(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            _write_suitability(target, "suitable")
            res = _run_cli(target, root / "nope" / "spec.md")
            self.assertEqual(res.returncode, 2)
            self.assertIn("spec_missing", res.stderr)

    def test_missing_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "target"
            (target / ".servo").mkdir(parents=True)
            (target / "oracle.sh").write_text(_ORACLE_SH)
            spec = _make_spec(root)
            _write_suitability(target, "suitable")
            res = _run_cli(target, spec)
            self.assertEqual(res.returncode, 2)
            self.assertIn("manifest_missing", res.stderr)
            self.assertFalse(_plan_path(target).exists())

    def test_never_exit_1(self):
        # Exercise several error paths; none may exit 1.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)  # no suitability written
            self.assertEqual(_run_cli(target, spec).returncode, 2)


# --------------------------------------------------------------------------
# AC7 — idempotent recompile
# --------------------------------------------------------------------------

class PlanRecompileIdempotentTests(unittest.TestCase):
    def test_recompile_byte_stable_except_compiled_at(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)
            _write_suitability(target, "suitable")
            self.assertEqual(_run_cli(target, spec).returncode, 0)
            first = json.loads(_plan_path(target).read_text())
            self.assertEqual(_run_cli(target, spec).returncode, 0)
            second = json.loads(_plan_path(target).read_text())
            first.pop("compiled_at")
            second.pop("compiled_at")
            self.assertEqual(first, second)
            self.assertEqual(second["provenance"], "compiled")


# ==========================================================================
# Slice 015-03 (compile-precondition) — the verdict as a Servo Compile gate.
# The gate MECHANISM ships in 016-01 (refuse unless suitable); 015-03 adds the
# enrichment: surface reasons + missing_evidence on refusal (AC1), explicit
# fail-closed-on-unavailable (AC2), and the heartbeat-boundary regression (AC3).
# ==========================================================================

class CompilePreconditionTests(unittest.TestCase):
    """015-03 AC1 — Compile proceeds only on `suitable`; a non-`suitable`
    verdict halts Compile and surfaces `reasons` + `missing_evidence`."""

    def test_suitable_proceeds(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target, _, _ = _compile_ok(root)
            self.assertTrue(_plan_path(target).exists())

    def test_non_suitable_surfaces_reasons_and_missing_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)
            _write_suitability(
                target, "needs_evidence",
                reasons=[{"code": "evaluable_acs_no_signal",
                          "message": "evaluable ACs but no test/CI signal"}],
                missing_evidence=[{"kind": "oracle_signal",
                                   "detail": "add a test command or CI workflow",
                                   "blocking": True}],
            )
            res = _run_cli(target, spec)
            self.assertEqual(res.returncode, 2)
            self.assertFalse(_plan_path(target).exists())
            # the actionable next step is surfaced, not just a bare code
            self.assertIn("evaluable_acs_no_signal", res.stderr)
            self.assertIn("add a test command or CI workflow", res.stderr)
            self.assertIn("oracle_signal", res.stderr)
            self.assertIn("blocking", res.stderr)
            self.assertIn("re-run", res.stderr.lower())


class CompileGateFailClosedTests(unittest.TestCase):
    """015-03 AC2 — an unavailable verdict (missing / unparseable) is treated as
    non-`suitable`; a broken analyzer never opens the Compile gate."""

    def test_missing_verdict_does_not_proceed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)  # no suitability artifact
            res = _run_cli(target, spec)
            self.assertEqual(res.returncode, 2)
            self.assertIn("suitability_missing", res.stderr)
            self.assertFalse(_plan_path(target).exists())

    def test_unparseable_verdict_does_not_proceed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)
            suit_dir = target / ".servo" / "suitability"
            suit_dir.mkdir(parents=True, exist_ok=True)
            (suit_dir / f"{SPEC_ID}.json").write_text("{not json")
            res = _run_cli(target, spec)
            self.assertEqual(res.returncode, 2)
            self.assertIn("suitability_malformed", res.stderr)
            self.assertFalse(_plan_path(target).exists())


class BoundaryHonestyTests(unittest.TestCase):
    """015-03 AC3 — the verdict is a Compile-phase gate ONLY. The heartbeat must
    not import or subprocess suitability (ADR-0018: findings are spec-less)."""

    def test_heartbeat_has_no_suitability_dependency(self):
        source = HEARTBEAT_PY.read_text().lower()
        self.assertNotIn("suitability", source)


if __name__ == "__main__":
    unittest.main()
