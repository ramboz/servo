"""
Surface tests for `/servo:autonomy-readiness` — slice 023-01.

Mirrors `skills/edd-suitability/test_skill_surface.py`: the SKILL.md description
lists the phrases that *should* fire the skill and the phrases that should *not*
(so trigger-matching stays narrow, delegating to siblings), and the body
documents the closed three-state verdict contract, the two tiers, and the
identity posture. Also pins the host/Compile-phase posture: this skill is
intentionally ABSENT from the plugin's `required.skills` (like edd-suitability),
so it is not vendored into a scaffolded target's runtime.

Run via unittest or pytest:
    python3 skills/autonomy-readiness/test_skill_surface.py
    python3 -m pytest skills/autonomy-readiness/test_skill_surface.py -q
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "autonomy-readiness" / "SKILL.md"
RUBRIC = REPO_ROOT / "skills" / "autonomy-readiness" / "readiness-rubric.md"
READINESS = REPO_ROOT / "skills" / "autonomy-readiness" / "readiness.py"
INSTALL_CONTRACT = REPO_ROOT / ".claude-plugin" / "install-contract.json"
EXAMPLES = REPO_ROOT / "skills" / "autonomy-readiness" / "examples"

VERDICTS = {"ready", "needs_tightening", "unsafe_for_autonomy"}
SIBLINGS = ("/servo:edd-suitability", "/servo:scaffold-init",
            "/servo:agent-loop", "/servo:quality-gate")


def _skill_text() -> str:
    if not SKILL_MD.exists():
        raise FileNotFoundError(f"SKILL.md missing at {SKILL_MD}")
    return SKILL_MD.read_text()


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not m:
        raise AssertionError("SKILL.md missing YAML frontmatter delimited by ---")
    return m.group(1)


class SkillSurfaceTriggerTests(unittest.TestCase):
    def test_skill_md_exists_with_frontmatter_name(self):
        self.assertIn("name: servo:autonomy-readiness", _frontmatter(_skill_text()))

    def test_declares_fire_triggers(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("Fire this skill when", fm)
        self.assertIn("unattended", fm.lower())

    def test_do_not_fire_delegates_to_each_sibling(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("Do NOT fire", fm)
        for sibling in SIBLINGS:
            self.assertIn(sibling, fm)
        # Readiness sits upstream of suitability — the boundary is named.
        self.assertIn("upstream", fm.lower())

    def test_body_documents_closed_three_state_verdict(self):
        body = _skill_text()
        for v in VERDICTS:
            self.assertIn(v, body)
        self.assertIn("fail-closed", body.lower())

    def test_body_documents_identity_posture_conditional(self):
        body = " ".join(_skill_text().split()).lower()
        self.assertIn("identity", body)
        self.assertIn("declares-autonomous-merge", body)
        self.assertIn("advisory", body)

    def test_body_documents_loop_seam_not_built_here(self):
        body = _skill_text()
        self.assertIn("023-02", body)
        self.assertIn("not built here", body)


class HostToolingContractTests(unittest.TestCase):
    """A host/Compile-phase tool like edd-suitability — NOT vendored into
    scaffolded targets. Absent from required.skills by design."""

    def test_not_in_required_skills(self):
        import json
        contract = json.loads(INSTALL_CONTRACT.read_text())
        names = {s["name"] for s in contract["required"]["skills"]}
        self.assertNotIn("autonomy-readiness", names)
        # Sanity: its Compile-phase sibling is also absent (the matched pair).
        self.assertNotIn("edd-suitability", names)

    def test_skill_md_marks_it_host_plugin_mode_tooling(self):
        body = " ".join(_skill_text().split())
        self.assertIn("host / Compile-phase tool", body)
        self.assertIn("not** vendored", body)


class RubricAndExamplesTests(unittest.TestCase):
    def test_builtin_rubric_scores_the_five_dimensions(self):
        text = RUBRIC.read_text().lower()
        for dim in ("precision", "scope", "stop", "safety surface", "contradiction"):
            self.assertIn(dim, text)

    def test_example_fixtures_exist(self):
        for name in ("good-bounded-brief.md", "open-ended-brief.md",
                     "secrets-deploy-brief.md"):
            self.assertTrue((EXAMPLES / name).is_file(), f"missing {name}")


if __name__ == "__main__":
    unittest.main()
