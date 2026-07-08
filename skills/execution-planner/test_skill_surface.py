"""
Surface + output-mode tests for `/servo:execution-planner` — slice 016-04
(skill-surface).

Mirrors `skills/edd-suitability/test_skill_surface.py`'s pattern: the SKILL.md
description lists fire triggers and explicit Do-NOT-fire sibling delegations,
the body documents the sibling-helper table, Q&A, refusal table, and install
posture, and this suite pins each of those load-bearing claims against
silent drift (in particular: every `EnvError` reason the helper actually
defines must appear in the refusal table).

Run via unittest or pytest:
    python3 skills/execution-planner/test_skill_surface.py
    python3 -m pytest skills/execution-planner/test_skill_surface.py -q
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "execution-planner" / "SKILL.md"
EXECUTION_PLAN = REPO_ROOT / "skills" / "execution-planner" / "execution_plan.py"
INSTALL_CONTRACT = REPO_ROOT / ".claude-plugin" / "install-contract.json"

SPEC_ID = "999-skill-surface-fixture"

_ORACLE_SH = (
    '#!/usr/bin/env bash\n'
    'set -euo pipefail\n'
    'THRESHOLD="${THRESHOLD:-0.5}"\n'
    'printf \'oracle: composite=%s threshold=%s\\n\' "1.0" "$THRESHOLD"\n'
)

# The exact EnvError reason strings `execution_plan.py` is known to define
# (016-01/03 taxonomy). This list is a sanity tripwire alongside the
# regex-derived extraction below — if the code and this list disagree, the
# regex-derived set is still what's checked against SKILL.md.
KNOWN_REASONS = {
    "spec_missing",
    "suitability_missing",
    "suitability_malformed",
    "suitability_not_suitable",
    "manifest_missing",
    "manifest_malformed",
    "oracle_missing",
    "plan_edit_detected",
}

_REASON_RE = re.compile(r'raise EnvError\(\s*"([a-z_]+)"')


def _defined_reasons() -> set:
    """Reasons `execution_plan.py` actually raises, extracted from source.

    Regex-derived (not hand-copied) so a future reason added to the code
    without a matching SKILL.md update fails this test, per AC2.
    """
    source = EXECUTION_PLAN.read_text()
    return set(_REASON_RE.findall(source))


def _skill_text() -> str:
    if not SKILL_MD.exists():
        raise FileNotFoundError(f"SKILL.md missing at {SKILL_MD}")
    return SKILL_MD.read_text()


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not m:
        raise AssertionError("SKILL.md missing YAML frontmatter delimited by ---")
    return m.group(1)


# ---------------------------------------------------------------------------
# Fixtures — mirrors test_execution_plan.py's passing-compile setup
# ---------------------------------------------------------------------------

def _make_target(root: Path, threshold: str = "0.5") -> Path:
    target = root / "target"
    servo = target / ".servo"
    servo.mkdir(parents=True)
    (servo / "install.json").write_text(json.dumps({
        "servo_version": "0.0.0",
        "installed_tier": "tier-0",
        "signals": {"tests": True, "lint": False, "ci": False, "language": "python"},
        "components": ["pytest"],
        "weights": {"pytest": 1.0},
    }))
    oracle = target / "oracle.sh"
    oracle.write_text(_ORACLE_SH.replace("0.5", threshold))
    oracle.chmod(0o755)
    return target


def _make_spec(root: Path, spec_id: str = SPEC_ID) -> Path:
    spec_dir = root / spec_id
    spec_dir.mkdir(parents=True)
    spec = spec_dir / "spec.md"
    spec.write_text("# Spec\n\n1. an AC\n")
    return spec


def _write_suitability(target: Path, verdict: str = "suitable",
                       spec_id: str = SPEC_ID) -> Path:
    out = target / ".servo" / "suitability"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{spec_id}.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "verdict": verdict,
        "reasons": [],
        "missing_evidence": [],
        "spec_id": spec_id,
        "analyzed_at": "2026-06-30T00:00:00Z",
    }))
    return path


def _run_cli(target: Path, spec: Path, *extra_args):
    return subprocess.run(
        [sys.executable, str(EXECUTION_PLAN), "compile", str(target),
         "--spec", str(spec), *extra_args],
        capture_output=True, text=True, env=dict(os.environ),
    )


def _plan_path(target: Path, spec_id: str = SPEC_ID) -> Path:
    return target / ".servo" / "plans" / spec_id / "plan.json"


def _compile_ok(root: Path):
    target = _make_target(root)
    spec = _make_spec(root)
    _write_suitability(target, "suitable")
    return target, spec


# ---------------------------------------------------------------------------
# AC1 — skill surface (fire / Do-NOT-fire triggers, sibling delegation)
# ---------------------------------------------------------------------------

class SkillSurfaceTriggerTests(unittest.TestCase):
    def test_skill_md_exists_with_frontmatter_name(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("name: servo:execution-planner", fm)

    def test_declares_fire_triggers(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("Fire this skill when", fm)
        self.assertIn('"compile the execution plan for this spec"', fm)
        self.assertIn('"produce the Compile→Run handoff"', fm)
        self.assertIn('"emit `plan.json` for this spec"', fm)

    def test_do_not_fire_delegates_to_each_sibling(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("Do NOT fire", fm)
        self.assertIn("/servo:edd-suitability", fm)   # suitability verdict
        self.assertIn("/servo:spec-oracle", fm)        # AC classification / overlay
        self.assertIn("/servo:agent-loop", fm)         # running / consuming the plan
        self.assertIn("/servo:quality-gate", fm)       # scoring a build

    def test_sibling_helper_table_mentions_engine_slices(self):
        body = _skill_text()
        self.assertIn("016-01", body)
        self.assertIn("016-02", body)
        self.assertIn("016-03", body)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/execution-planner/execution_plan.py",
                      body)

    def test_qa_before_compiling_block(self):
        body = _skill_text()
        self.assertIn("Q&A", body)
        self.assertIn("Target path", body)
        self.assertIn("Spec", body)
        self.assertIn("Output mode", body)
        self.assertIn("--json", body)

    def test_where_the_plan_sits_pointer(self):
        body = _skill_text()
        self.assertIn("loop.py --plan", body)
        self.assertIn("ADR-0016", body)
        self.assertIn("ADR-0004", body)
        self.assertIn("state.json", body)


# ---------------------------------------------------------------------------
# AC2 — refusal table + closed exit contract
# ---------------------------------------------------------------------------

class RefusalTableTests(unittest.TestCase):
    def test_reason_extraction_matches_known_taxonomy(self):
        # Sanity check on the extraction itself, not just the doc.
        self.assertEqual(_defined_reasons(), KNOWN_REASONS)

    def test_every_defined_reason_appears_in_skill_md(self):
        reasons = _defined_reasons()
        self.assertTrue(reasons, "no EnvError reasons extracted from source")
        body = _skill_text()
        for reason in reasons:
            self.assertIn(reason, body, f"reason {reason!r} missing from SKILL.md")

    def test_states_closed_exit_contract(self):
        body = _skill_text()
        self.assertIn("{0, 2}", body)
        self.assertIn("never exit", body.lower())


# ---------------------------------------------------------------------------
# AC3 — human + --json output mode
# ---------------------------------------------------------------------------

class OutputModeTests(unittest.TestCase):
    def test_default_is_human_line_not_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target, spec = _compile_ok(root)
            res = _run_cli(target, spec)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertFalse(res.stdout.lstrip().startswith("{"))
            self.assertIn(f"servo: execution plan for {SPEC_ID} compiled ->", res.stdout)

    def test_json_emits_exact_envelope_keys(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target, spec = _compile_ok(root)
            res = _run_cli(target, spec, "--json")
            self.assertEqual(res.returncode, 0, res.stderr)
            obj = json.loads(res.stdout)
            self.assertEqual(
                set(obj.keys()),
                {"schema_version", "spec_id", "status", "plan_path",
                 "provenance", "driver", "budget"},
            )
            self.assertEqual(obj["status"], "compiled")
            self.assertEqual(obj["spec_id"], SPEC_ID)
            self.assertEqual(Path(obj["plan_path"]).resolve(),
                             _plan_path(target).resolve())
            self.assertEqual(obj["provenance"], "compiled")
            self.assertEqual(obj["driver"], "auto")
            self.assertIn("max_iterations", obj["budget"])

    def test_json_refusal_still_prints_stderr_reason_no_envelope(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root)
            spec = _make_spec(root)
            # no suitability verdict written -> suitability_missing refusal
            res = _run_cli(target, spec, "--json")
            self.assertEqual(res.returncode, 2)
            self.assertIn("suitability_missing", res.stderr)
            self.assertFalse(res.stdout.strip().startswith("{"))
            self.assertFalse(_plan_path(target).exists())


# ---------------------------------------------------------------------------
# AC4 — install posture: plugin-discovered, not vendored
# ---------------------------------------------------------------------------

class InstallPostureTests(unittest.TestCase):
    def test_skill_md_present_on_disk(self):
        self.assertTrue(SKILL_MD.is_file())

    def test_execution_planner_not_in_required_skills(self):
        contract = json.loads(INSTALL_CONTRACT.read_text())
        names = {s["name"] for s in contract["required"]["skills"]}
        self.assertNotIn("execution-planner", names)

    def test_skill_md_states_host_compile_phase_posture(self):
        body = " ".join(_skill_text().split())
        self.assertIn("host / Compile-phase tool", body)
        self.assertIn("not** vendored", body)


if __name__ == "__main__":
    unittest.main()
