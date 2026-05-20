"""
Surface tests for `skills/agent-loop/SKILL.md` — slice 003-05 (qa-wizard).

Mirrors `skills/quality-gate/test_skill_surface.py`'s anti-greediness
pattern: the SKILL.md description lists both the phrases that *should*
fire the skill and the phrases that should *not*, so the LLM's trigger-
matching stays narrow.

Run via either unittest or pytest:
    python3 skills/agent-loop/test_skill_surface.py
    pytest skills/agent-loop/test_skill_surface.py
"""

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "agent-loop" / "SKILL.md"


def _skill_text() -> str:
    if not SKILL_MD.exists():
        raise FileNotFoundError(f"SKILL.md missing at {SKILL_MD}")
    return SKILL_MD.read_text()


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not m:
        raise AssertionError("SKILL.md missing YAML frontmatter delimited by --- fences")
    return m.group(1)


# ---------------------------------------------------------------------------
# Existence / shape
# ---------------------------------------------------------------------------


class SkillFileShapeTests(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(SKILL_MD.exists(), f"SKILL.md missing at {SKILL_MD}")

    def test_has_frontmatter_with_name_and_description(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("name:", fm, "SKILL.md frontmatter must declare a `name:` field")
        self.assertIn("description:", fm, "SKILL.md frontmatter must declare a `description:` field")
        self.assertIn("servo:agent-loop", fm, "name should be `servo:agent-loop`")


# ---------------------------------------------------------------------------
# AC #9 — trigger phrases (positive + negative)
# ---------------------------------------------------------------------------


class DescriptionBoundsTests(unittest.TestCase):
    """Description lists in-scope phrases AND explicitly excludes out-of-scope
    ones so the LLM doesn't poach requests that belong to a sibling skill."""

    def setUp(self):
        self.text = _skill_text()
        self.description = _frontmatter(self.text)

    def test_positive_triggers_in_description(self):
        # The spec's named positive triggers (003-05 AC #9).
        for phrase in (
            "run an agent loop",
            "iterate on this codebase",
            "headless loop",
        ):
            self.assertIn(
                phrase, self.description.lower(),
                f"description should list positive trigger phrase {phrase!r}",
            )

    def test_resume_trigger_in_description(self):
        # Resume is a major operating mode; should surface as a trigger.
        self.assertIn(
            "resume", self.description.lower(),
            "description should reference the resume trigger phrase",
        )

    def test_negative_triggers_in_description(self):
        # AC #9: must NOT fire on score-this-code (that's quality-gate),
        # scaffold-init (that's scaffold-init), or PR review (out of scope).
        desc_lower = self.description.lower()
        self.assertTrue(
            "do not" in desc_lower or "don't" in desc_lower,
            "description should contain an explicit do-not / exclusion section",
        )
        for phrase in (
            "score this code",  # quality-gate's territory
            "scaffold the oracle",  # scaffold-init's territory
            "review my pr",  # out of scope
        ):
            self.assertIn(
                phrase, desc_lower,
                f"description should reference (and exclude) the bare phrase {phrase!r}",
            )

    def test_excludes_sibling_quality_gate(self):
        # Explicit pointer to quality-gate as the right skill for scoring
        # requests so the LLM doesn't grab the wrong one.
        self.assertIn(
            "/servo:quality-gate", self.text,
            "SKILL.md should point users at /servo:quality-gate for scoring requests",
        )

    def test_excludes_sibling_scaffold_init(self):
        # Same for scaffold-init.
        self.assertIn(
            "/servo:scaffold-init", self.text,
            "SKILL.md should point users at /servo:scaffold-init for scaffolding requests",
        )


# ---------------------------------------------------------------------------
# Options section documented
# ---------------------------------------------------------------------------


class OptionsSectionTests(unittest.TestCase):
    """`--prompt`, `--max-iterations`, `--cost-ceiling`, `--context-fill-threshold`,
    `--plateau-window`, `--resume`, `--resume-anyway` are each named in the body."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_prompt_flag_documented(self):
        self.assertIn("--prompt", self.text)

    def test_max_iterations_flag_documented(self):
        self.assertIn("--max-iterations", self.text)

    def test_cost_ceiling_flag_documented(self):
        self.assertIn("--cost-ceiling", self.text)

    def test_context_fill_threshold_flag_documented(self):
        self.assertIn("--context-fill-threshold", self.text)

    def test_plateau_window_flag_documented(self):
        self.assertIn("--plateau-window", self.text)

    def test_resume_flag_documented(self):
        self.assertIn("--resume", self.text)
        # And the escape hatch must be documented too.
        self.assertIn("--resume-anyway", self.text)

    def test_env_var_documented(self):
        # SERVO_CLAUDE_TIMEOUT is the per-invocation timeout escape hatch.
        self.assertIn("SERVO_CLAUDE_TIMEOUT", self.text)

    def test_examples_present(self):
        # At least one fenced bash example block.
        self.assertIn("```bash", self.text, "SKILL.md should include at least one fenced bash example")


# ---------------------------------------------------------------------------
# Refusal handling guidance
# ---------------------------------------------------------------------------


class RefusalHandlingTests(unittest.TestCase):
    """All terminal_reason values are surfaced in the refusal table; LLM is
    told never to silently retry."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_refusal_section_exists(self):
        self.assertIn("refusal", self.body)

    def test_terminal_reason_taxonomy_documented(self):
        # The full closed terminal_reason set the loop emits.
        for reason in (
            "oracle_passed",
            "max_iterations_reached",
            "cost_ceiling_reached",
            "context_full",
            "oracle_plateau",
            "interrupted",
            "claude_invocation_failed",
            "gate_invocation_failed",
            "verdict_schema_mismatch",
            "target_missing",
            "manifest_missing",
            "oracle_missing",
            "state_missing",
            "state_schema_mismatch",
            "claude_version_mismatch",
            "run_id_collision",
        ):
            self.assertIn(
                reason, self.body,
                f"refusal table missing terminal_reason {reason!r}",
            )

    def test_no_silent_retry(self):
        self.assertTrue(
            "do not silently retry" in self.body or "verbatim" in self.body,
            "SKILL.md should tell the LLM not to silently retry on refusal",
        )

    def test_resume_recovery_pointer_present(self):
        # The natural recovery for max_iterations/cost_ceiling is --resume.
        self.assertIn("--resume", self.text)

    def test_scaffold_recovery_pointer_present(self):
        # Recovery for manifest_missing / oracle_missing is /servo:scaffold-init.
        self.assertIn("/servo:scaffold-init", self.text)


# ---------------------------------------------------------------------------
# Operation modes (fresh vs resume) documented
# ---------------------------------------------------------------------------


class OperationModesTests(unittest.TestCase):
    """Both fresh and resume modes are documented with example invocations."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_fresh_run_mode_documented(self):
        self.assertIn("fresh run", self.body)

    def test_resume_mode_documented(self):
        self.assertIn("resumed run", self.body)
        # And an example of the resume invocation.
        self.assertIn("--resume", self.text)

    def test_state_path_documented(self):
        # The state-file path is part of the contract.
        self.assertIn(".servo/runs/", self.text)
        self.assertIn("state.json", self.text)


# ---------------------------------------------------------------------------
# Output shape documented
# ---------------------------------------------------------------------------


class OutputShapeTests(unittest.TestCase):
    """Per-iteration JSON and summary JSON shapes are documented."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_per_iteration_json_documented(self):
        # The body should mention per-iteration JSON.
        self.assertTrue(
            "per-iteration" in self.body or "per iteration" in self.body,
            "SKILL.md should mention per-iteration JSON output",
        )

    def test_summary_line_documented(self):
        self.assertIn("summary", self.body)

    def test_schema_version_documented(self):
        # The loop's schema_version is the forward-compat contract.
        self.assertIn("schema_version", self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
