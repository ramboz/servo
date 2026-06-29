"""
Surface + dogfood tests for `/servo:edd-suitability` — slice 015-04
(skill-and-explain).

Mirrors `skills/spec-oracle/test_skill_surface.py`'s anti-greediness pattern: the
SKILL.md description lists the phrases that *should* fire the skill and the
phrases that should *not* (so the LLM's trigger-matching stays narrow,
delegating to siblings), and the body documents the output modes, the
`--explain` trace, the re-run flow, and the model-assist + waiver seams. The CLI
tests drive the real `suitability.py`; the dogfood test runs the real
`oracle_plan.py classify` against a committed example fixture.

Run via unittest or pytest:
    python3 skills/edd-suitability/test_skill_surface.py
    python3 -m pytest skills/edd-suitability/test_skill_surface.py -q
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "edd-suitability" / "SKILL.md"
SUITABILITY = REPO_ROOT / "skills" / "edd-suitability" / "suitability.py"
REAL_ORACLE_PLAN = REPO_ROOT / "skills" / "spec-oracle" / "oracle_plan.py"
EXAMPLE_RERUN = (
    REPO_ROOT / "skills" / "edd-suitability" / "examples"
    / "needs-evidence-then-suitable.md"
)

VERDICTS = {"suitable", "needs_evidence", "unsuitable"}


def _skill_text() -> str:
    if not SKILL_MD.exists():
        raise FileNotFoundError(f"SKILL.md missing at {SKILL_MD}")
    return SKILL_MD.read_text()


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not m:
        raise AssertionError("SKILL.md missing YAML frontmatter delimited by ---")
    return m.group(1)


def _make_target(root: Path, signals: dict) -> Path:
    target = root / "target"
    (target / ".servo").mkdir(parents=True)
    (target / ".servo" / "install.json").write_text(json.dumps(
        {"schema_version": 1, "signals": signals, "components": [], "weights": {}}
    ))
    return target


def _stub_oracle_plan(root: Path, *, n_checks: int, n_residual: int,
                      spec_id: str = "demo") -> Path:
    checks = [{"id": f"AC-{i}", "family": "command"} for i in range(n_checks)]
    residual = [{"id": f"AC-r{i}"} for i in range(n_residual)]
    payload = {"spec_id": spec_id, "checks": checks,
               "residual_judgment": residual}
    script = root / "stub_oracle_plan.py"
    script.write_text(
        "import sys\n"
        f"print({json.dumps(json.dumps(payload))})\n"
        "sys.exit(0)\n"
    )
    return script


def _run_cli(target: Path, spec: Path, *extra_args, oracle_plan: Path):
    env = dict(os.environ)
    env["SERVO_SUITABILITY_ORACLE_PLAN"] = str(oracle_plan)
    return subprocess.run(
        [sys.executable, str(SUITABILITY), "analyze", str(target),
         "--spec", str(spec), *extra_args],
        capture_output=True, text=True, env=env,
    )


SIG_NONE = {"tests": False, "lint": False, "ci": False, "language": "python"}
SIG_TESTS = {"tests": True, "lint": False, "ci": False, "language": "python"}


# ---------------------------------------------------------------------------
# AC1 — skill surface (fire / Do-NOT-fire triggers, sibling delegation)
# ---------------------------------------------------------------------------

class SkillSurfaceTriggerTests(unittest.TestCase):
    def test_skill_md_exists_with_frontmatter_name(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("name: servo:edd-suitability", fm)

    def test_declares_fire_triggers(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("Fire this skill when", fm)
        self.assertIn("suitable for EDD", fm)
        self.assertIn("missing", fm.lower())

    def test_do_not_fire_delegates_to_each_sibling(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("Do NOT fire", fm)
        # Each sibling boundary is named explicitly so trigger-matching stays narrow.
        self.assertIn("/servo:scaffold-init", fm)   # oracle synthesis
        self.assertIn("/servo:spec-oracle", fm)     # AC classification
        self.assertIn("/servo:agent-loop", fm)      # running the loop

    def test_body_documents_closed_three_state_gate(self):
        body = _skill_text()
        for v in VERDICTS:
            self.assertIn(v, body)
        self.assertIn("fail-closed", body.lower())


# ---------------------------------------------------------------------------
# AC2 — human + --json output
# ---------------------------------------------------------------------------

class OutputModeTests(unittest.TestCase):
    def test_default_is_human_summary_with_blocking_lines(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_NONE)
            spec = root / "spec.md"
            spec.write_text("# Spec\n\n1. an AC\n")
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            res = _run_cli(target, spec, oracle_plan=plan)
            self.assertEqual(res.returncode, 0, res.stderr)
            # Human, not JSON.
            self.assertFalse(res.stdout.lstrip().startswith("{"))
            self.assertIn("NEEDS_EVIDENCE", res.stdout)
            # One line per blocking item (oracle_signal blocks here).
            self.assertIn("blocking", res.stdout)
            self.assertIn("oracle_signal", res.stdout)

    def test_json_emits_full_adr0015_shape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = root / "spec.md"
            spec.write_text("# Spec\n\n1. an AC\n")
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            res = _run_cli(target, spec, "--json", oracle_plan=plan)
            self.assertEqual(res.returncode, 0, res.stderr)
            obj = json.loads(res.stdout)
            for key in ("schema_version", "verdict", "reasons",
                        "missing_evidence", "spec_id", "analyzed_at"):
                self.assertIn(key, obj)
            self.assertEqual(obj["verdict"], "suitable")

    def test_json_without_explain_has_no_trace(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = root / "spec.md"
            spec.write_text("# Spec\n\n1. an AC\n")
            plan = _stub_oracle_plan(root, n_checks=1, n_residual=0)
            res = _run_cli(target, spec, "--json", oracle_plan=plan)
            self.assertNotIn("rule_trace", json.loads(res.stdout))


# ---------------------------------------------------------------------------
# AC3 — --explain rationale (ordered rule trace)
# ---------------------------------------------------------------------------

class ExplainTraceTests(unittest.TestCase):
    def test_human_explain_shows_ordered_trace_and_decided_rule(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_NONE)
            spec = root / "spec.md"
            spec.write_text("# Spec\n\n1. an AC\n")
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            res = _run_cli(target, spec, "--explain", oracle_plan=plan)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("rule trace", res.stdout)
            # All five rule codes appear, in table order, and the fired one is marked.
            self.assertIn("evaluable_acs_with_signal", res.stdout)
            self.assertIn("DECIDED", res.stdout)
            # The decided rule for (eval>=1, no signal) is evaluable_acs_no_signal.
            decided_line = next(
                ln for ln in res.stdout.splitlines() if "DECIDED" in ln
            )
            self.assertIn("evaluable_acs_no_signal", decided_line)

    def test_json_explain_adds_rule_trace_view_not_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_NONE)
            spec = root / "spec.md"
            spec.write_text("# Spec\n\n1. an AC\n")
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            res = _run_cli(target, spec, "--json", "--explain", oracle_plan=plan)
            obj = json.loads(res.stdout)
            self.assertIn("rule_trace", obj)
            rules = obj["rule_trace"]["rules"]
            self.assertEqual(len(rules), 5)
            self.assertEqual(sum(1 for r in rules if r["decided"]), 1)
            # The persisted artifact stays clean (no rule_trace on disk).
            art = json.loads(
                (target / ".servo" / "suitability" / "demo.json").read_text()
            )
            self.assertNotIn("rule_trace", art)


# ---------------------------------------------------------------------------
# AC4 — re-run flow documented + demonstrated (dogfood)
# ---------------------------------------------------------------------------

class RerunDogfoodTests(unittest.TestCase):
    def test_skill_md_documents_rerun_flow(self):
        body = _skill_text()
        self.assertIn("Re-run after acquiring evidence", body)
        self.assertIn("needs-evidence-then-suitable.md", body)

    def test_example_fixture_exists(self):
        self.assertTrue(EXAMPLE_RERUN.is_file(), f"missing {EXAMPLE_RERUN}")

    def test_dogfood_flips_needs_evidence_to_suitable(self):
        # Uses the REAL classifier on the committed example: no signal →
        # needs_evidence; add a test signal → suitable.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_NONE)
            res1 = _run_cli(target, EXAMPLE_RERUN, "--json",
                            oracle_plan=REAL_ORACLE_PLAN)
            self.assertEqual(res1.returncode, 0, res1.stderr)
            v1 = json.loads(res1.stdout)
            self.assertEqual(v1["verdict"], "needs_evidence")
            self.assertTrue(
                any(it["blocking"] and it["kind"] == "oracle_signal"
                    for it in v1["missing_evidence"])
            )
            # Acquire evidence: the target now has a test signal.
            (target / ".servo" / "install.json").write_text(json.dumps(
                {"schema_version": 1, "signals": SIG_TESTS,
                 "components": [], "weights": {}}
            ))
            res2 = _run_cli(target, EXAMPLE_RERUN, "--json",
                            oracle_plan=REAL_ORACLE_PLAN)
            v2 = json.loads(res2.stdout)
            self.assertEqual(v2["verdict"], "suitable")
            self.assertEqual(v2["missing_evidence"], [])


# ---------------------------------------------------------------------------
# AC5 — extension-point + waiver docs (documented seams, not built)
# ---------------------------------------------------------------------------

class ExtensionPointDocTests(unittest.TestCase):
    def test_documents_model_assist_extension_as_flagged_and_bounded(self):
        body = _skill_text()
        self.assertIn("model-assist", body.lower())
        self.assertIn("ADR-0005", body)            # the freeze discipline it cites
        self.assertIn("not built here", body)

    def test_documents_waiver_posture(self):
        body = _skill_text()
        self.assertIn("Waiver", body)
        self.assertIn("waiver", body.lower())
        # Borrows spec-oracle's approval posture, explicitly not built here.
        # (collapse whitespace so the phrase matches even when line-wrapped.)
        collapsed = " ".join(body.split())
        self.assertIn("approval posture", collapsed)
        self.assertEqual(collapsed.count("not built here"), 2)  # extension + waiver


if __name__ == "__main__":
    unittest.main()
