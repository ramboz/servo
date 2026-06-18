"""
Surface tests for `skills/heartbeat/SKILL.md` — slice 011-05 (skill-and-dogfood).

Mirrors the sibling anti-greediness tests: the description names the phrases
that should fire `/servo:heartbeat`, keeps sibling-skill territory under an
explicit Do-NOT section, and the body documents the Tier-2 posture, guardrails,
Q&A flow, refusal handling, and scheduler recipes.

Run via unittest or pytest:
    python3 skills/heartbeat/test_skill_surface.py
    uvx pytest skills/heartbeat/test_skill_surface.py -q
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "heartbeat" / "SKILL.md"
CONTRACT = REPO_ROOT / ".claude-plugin" / "install-contract.json"


def _skill_text() -> str:
    if not SKILL_MD.exists():
        raise FileNotFoundError(f"SKILL.md missing at {SKILL_MD}")
    return SKILL_MD.read_text()


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not m:
        raise AssertionError("SKILL.md missing YAML frontmatter delimited by --- fences")
    return m.group(1)


class SkillFileShapeTests(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(SKILL_MD.exists(), f"SKILL.md missing at {SKILL_MD}")

    def test_has_frontmatter_with_name_and_description(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("name:", fm)
        self.assertIn("description:", fm)
        self.assertIn("servo:heartbeat", fm)

    def test_install_contract_lists_heartbeat_helper(self):
        contract = json.loads(CONTRACT.read_text())
        skills = contract["required"]["skills"]
        entry = next((s for s in skills if s.get("name") == "heartbeat"), None)
        self.assertIsNotNone(entry, "install contract must list the heartbeat skill")
        self.assertIn("SKILL.md", entry["files"])
        self.assertIn("heartbeat.py", entry["files"])


class DescriptionBoundsTests(unittest.TestCase):
    def setUp(self):
        self.text = _skill_text()
        self.description = _frontmatter(self.text).lower()
        marker = "do not" if "do not" in self.description else "don't"
        self.assertIn(marker, self.description, "description needs a Do-NOT section")
        idx = self.description.index(marker)
        self.fire_part = self.description[:idx]
        self.do_not_part = self.description[idx:]

    def test_positive_triggers_before_do_not_section(self):
        for phrase in (
            "run heartbeat",
            "scheduled heartbeat",
            "routine",
            "cron",
            "github actions schedule",
            "read the heartbeat inbox",
            "dispatch heartbeat findings",
        ):
            self.assertIn(
                phrase,
                self.fire_part,
                f"positive trigger {phrase!r} should be in the fire-on section",
            )

    def test_negative_triggers_in_do_not_section(self):
        for phrase in (
            "run the oracle",
            "iterate",
            "set up servo",
            "oracle hook",
            "spec oracle",
            "design eval",
        ):
            self.assertIn(
                phrase,
                self.do_not_part,
                f"negative trigger {phrase!r} should be under Do-NOT",
            )

    def test_points_at_sibling_skills(self):
        for skill in (
            "/servo:quality-gate",
            "/servo:agent-loop",
            "/servo:scaffold-init",
            "/servo:oracle-hook",
            "/servo:spec-oracle",
            "/servo:design-eval",
        ):
            self.assertIn(skill, self.text)


class Tier2GuardrailTests(unittest.TestCase):
    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_tier_2_explicit_opt_in(self):
        self.assertTrue("tier-2" in self.body or "tier 2" in self.body)
        self.assertIn("explicit", self.body)
        self.assertTrue("never auto" in self.body or "not auto" in self.body)

    def test_four_guardrails_documented_up_front(self):
        for phrase in (
            "read-only",
            ".servo/triage",
            "refuse-without-oracle",
            "untrusted data",
            "whole-heartbeat",
            "not per-loop",
        ):
            self.assertIn(phrase, self.body)

    def test_servo_ships_recipe_not_scheduler(self):
        self.assertIn("not a daemon", self.body)
        self.assertIn("not a scheduler", self.body)


class QAFlowTests(unittest.TestCase):
    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_q_and_a_names_operating_mode_and_caps(self):
        for phrase in (
            "target path",
            "discover",
            "status",
            "dispatch",
            "run",
            "--cost-ceiling",
            "--max-candidates",
            "--max-iterations",
        ):
            self.assertIn(phrase, self.body)

    def test_distinguishes_discovery_from_execution_prerequisites(self):
        self.assertIn("without an oracle", self.body)
        self.assertIn("dispatch", self.body)
        self.assertIn("run", self.body)
        self.assertIn("preflight", self.body)

    def test_scheduler_credentials_are_called_out(self):
        self.assertIn("gh", self.text)
        self.assertTrue("credential" in self.body or "authentication" in self.body)


class RefusalHandlingTests(unittest.TestCase):
    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_closed_exit_contract_and_reasons_documented(self):
        self.assertIn("{0, 2}", self.text)
        for reason in (
            "target_missing",
            "target_not_directory",
            "triage_dir_unwritable",
            "schema_version_unsupported",
            "schema_version_mixed",
            "lock_contended",
            "manifest_missing",
            "oracle_missing",
            "oracle_not_executable",
        ):
            self.assertIn(reason, self.body)

    def test_recovery_guidance_present(self):
        self.assertIn("/servo:scaffold-init", self.text)
        self.assertIn(".servo/triage", self.text)
        self.assertIn("re-run later", self.body)
        self.assertTrue("do not silently retry" in self.body or "verbatim" in self.body)


class RoutineRecipeTests(unittest.TestCase):
    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_recipes_cover_common_scheduler_shapes(self):
        for phrase in ("cron", "schedule:", "routine"):
            self.assertIn(phrase, self.body)

    def test_recipes_invoke_run_with_whole_ceiling(self):
        self.assertIn("heartbeat.py run", self.text)
        self.assertIn("--cost-ceiling", self.text)
        self.assertIn("--max-candidates", self.text)

    def test_recipe_is_non_mutating_by_default(self):
        self.assertIn("does not create", self.body)
        self.assertIn("explicitly asks", self.body)
        self.assertIn(".servo/triage", self.text)


if __name__ == "__main__":
    unittest.main()
