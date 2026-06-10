"""
Surface + dogfood tests for `/servo:spec-oracle` — slice 006-05 (skill-and-dogfood).

Mirrors `skills/agent-loop/test_skill_surface.py`'s anti-greediness pattern: the
SKILL.md description lists the phrases that *should* fire the skill and the
phrases that should *not* (so the LLM's trigger-matching stays narrow), and the
body documents the Q&A flow, the no-silent-approval boundary, and worked
examples. The dogfood tests run the real planner against the two committed
example fixtures (no runtime dependency on the jig repo).

Run via unittest or pytest:
    python3 skills/spec-oracle/test_skill_surface.py
    uvx pytest skills/spec-oracle/test_skill_surface.py -q
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "spec-oracle" / "SKILL.md"
ORACLE_PLAN = REPO_ROOT / "skills" / "spec-oracle" / "oracle_plan.py"
EXAMPLES = REPO_ROOT / "skills" / "spec-oracle" / "examples"
EX_046 = EXAMPLES / "046-scaffold-fidelity.md"
EX_047 = EXAMPLES / "047-install-contract.md"


def _skill_text() -> str:
    if not SKILL_MD.exists():
        raise FileNotFoundError(f"SKILL.md missing at {SKILL_MD}")
    return SKILL_MD.read_text()


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not m:
        raise AssertionError("SKILL.md missing YAML frontmatter delimited by --- fences")
    return m.group(1)


def _classify(spec_path: Path) -> dict:
    res = subprocess.run(
        [sys.executable, str(ORACLE_PLAN), "classify", str(spec_path)],
        capture_output=True, text=True)
    assert res.returncode == 0, f"classify failed: {res.stderr}"
    return json.loads(res.stdout)


# ---------------------------------------------------------------------------
# Existence / shape
# ---------------------------------------------------------------------------


class SkillFileShapeTests(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(SKILL_MD.exists(), f"SKILL.md missing at {SKILL_MD}")

    def test_has_frontmatter_with_name_and_description(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("name:", fm)
        self.assertIn("description:", fm)
        self.assertIn("servo:spec-oracle", fm, "name should be `servo:spec-oracle`")


# ---------------------------------------------------------------------------
# AC1 — trigger bounds (positive + negative; sibling pointers)
# ---------------------------------------------------------------------------


class DescriptionBoundsTests(unittest.TestCase):
    """Fires on generate/specify/evaluate-an-oracle; not on run-the-oracle
    (quality-gate) or iterate (agent-loop)."""

    def setUp(self):
        self.text = _skill_text()
        self.description = _frontmatter(self.text).lower()

    def test_positive_triggers_in_description(self):
        for phrase in (
            "generate an oracle",
            "spec oracle",
            "turn this spec",
            "evaluate",
        ):
            self.assertIn(
                phrase, self.description,
                f"description should list positive trigger phrase {phrase!r}",
            )

    def test_has_explicit_do_not_section(self):
        self.assertTrue(
            "do not" in self.description or "don't" in self.description,
            "description should contain an explicit do-not / exclusion section",
        )

    def test_negative_triggers_excluded(self):
        # Must NOT fire on run-the-oracle (quality-gate) or iterate (agent-loop).
        for phrase in ("run the oracle", "iterate on this"):
            self.assertIn(
                phrase, self.description,
                f"description should reference (and exclude) the phrase {phrase!r}",
            )

    def test_points_at_quality_gate_for_running(self):
        self.assertIn(
            "/servo:quality-gate", self.text,
            "SKILL.md should point 'run the oracle' requests at /servo:quality-gate",
        )

    def test_points_at_agent_loop_for_iterating(self):
        self.assertIn(
            "/servo:agent-loop", self.text,
            "SKILL.md should point 'iterate' requests at /servo:agent-loop",
        )

    def test_points_at_scaffold_init_for_setup(self):
        self.assertIn("/servo:scaffold-init", self.text)


# ---------------------------------------------------------------------------
# AC2 — Q&A flow (target / spec path / baseline commands / stop point)
# ---------------------------------------------------------------------------


class QAFlowTests(unittest.TestCase):
    """The skill asks for target path, spec/slice path, baseline commands, and
    whether to stop after plan generation or install an approved overlay."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_asks_target_path(self):
        self.assertIn("target path", self.body)

    def test_asks_spec_or_slice_path(self):
        self.assertTrue(
            "spec / slice path" in self.body or "spec/slice path" in self.body
            or "spec or slice" in self.body,
            "Q&A should ask for the spec/slice path",
        )

    def test_asks_baseline_commands(self):
        self.assertIn("baseline command", self.body)

    def test_asks_stop_or_proceed(self):
        # Stop after plan generation vs proceed to install an approved overlay.
        self.assertIn("stop", self.body)
        self.assertTrue(
            "stop after plan" in self.body or "stop point" in self.body,
            "Q&A should ask whether to stop after plan generation",
        )


# ---------------------------------------------------------------------------
# AC5 — no silent approval
# ---------------------------------------------------------------------------


class NoSilentApprovalTests(unittest.TestCase):
    """The skill never marks an overlay approved without explicit instruction."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_states_never_auto_approves(self):
        self.assertIn("never", self.body)
        self.assertIn("approv", self.body)  # approve / approval / approved
        self.assertTrue(
            "explicit" in self.body,
            "SKILL.md should require an explicit instruction before approval",
        )

    def test_approve_is_a_separate_step(self):
        self.assertIn("oracle_overlay.py", self.text)
        self.assertIn("approve", self.body)

    def test_draft_overlay_is_refused(self):
        # A draft overlay must be refused by the frozen component.
        self.assertIn("spec_oracle_unapproved", self.text)


# ---------------------------------------------------------------------------
# AC3 — worked examples present (shaped like jig 046/047)
# ---------------------------------------------------------------------------


class WorkedExamplesTests(unittest.TestCase):
    def test_example_fixtures_exist(self):
        self.assertTrue(EX_046.is_file(), f"missing {EX_046}")
        self.assertTrue(EX_047.is_file(), f"missing {EX_047}")

    def test_skill_documents_worked_examples(self):
        body = _skill_text().lower()
        self.assertIn("worked example", body)
        self.assertIn("046", body)
        self.assertIn("047", body)

    def test_skill_shows_family_classification(self):
        # The worked-example tables name concrete families.
        text = _skill_text()
        for family in ("json_contract", "archive_inventory",
                       "generated_artifact_command", "residual_judgment"):
            self.assertIn(family, text)


# ---------------------------------------------------------------------------
# AC4 — dogfood plan quality (run the planner on the committed fixtures)
# ---------------------------------------------------------------------------


class DogfoodQualityTests(unittest.TestCase):
    """Validator/doc/install-contract ACs land mostly in deterministic families;
    residual judgment is explicit (reason + suggested review)."""

    def test_047_install_contract_all_deterministic(self):
        plan = _classify(EX_047)
        self.assertEqual(len(plan["residual_judgment"]), 0,
                         "047-shaped install-contract ACs should be deterministic")
        families = {c["family"] for c in plan["checks"]}
        self.assertEqual(len(plan["checks"]), 4)
        for fam in ("json_contract", "archive_inventory", "file_presence",
                    "command"):
            self.assertIn(fam, families)

    def test_046_scaffold_fidelity_mostly_deterministic(self):
        plan = _classify(EX_046)
        self.assertGreaterEqual(len(plan["checks"]), 3,
                                "046-shaped ACs should be mostly deterministic")
        self.assertEqual(len(plan["residual_judgment"]), 1,
                         "exactly the one taste AC stays residual")
        families = {c["family"] for c in plan["checks"]}
        self.assertIn("generated_artifact_command", families)
        self.assertIn("markdown_links", families)

    def test_residual_is_explicit(self):
        # Every residual entry carries a reason and a suggested review path.
        for fixture in (EX_046, EX_047):
            for entry in _classify(fixture)["residual_judgment"]:
                self.assertTrue(entry.get("reason"))
                self.assertTrue(entry.get("suggested_review"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
