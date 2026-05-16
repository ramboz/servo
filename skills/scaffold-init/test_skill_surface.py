"""
Surface tests for `skills/scaffold-init/SKILL.md` — slice 001-05 (qa-wizard).

Mirrors jig's `pr-review/test_skill_surface.py` `DescriptionBoundsTests`
pattern: a SKILL.md description should list both the phrases that *should*
fire it and the phrases that should *not*, so the LLM's trigger-matching
stays narrow.

Run via either unittest or pytest:
    python3 skills/scaffold-init/test_skill_surface.py
    pytest skills/scaffold-init/test_skill_surface.py
"""

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "scaffold-init" / "SKILL.md"


def _skill_text() -> str:
    if not SKILL_MD.exists():
        raise FileNotFoundError(f"SKILL.md missing at {SKILL_MD}")
    return SKILL_MD.read_text()


def _frontmatter(text: str) -> str:
    """Return the YAML frontmatter block between the leading `---` fences."""
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not m:
        raise AssertionError("SKILL.md missing YAML frontmatter delimited by --- fences")
    return m.group(1)


# ---------------------------------------------------------------------------
# Existence / shape
# ---------------------------------------------------------------------------

class SkillFileShapeTests(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(SKILL_MD.exists(),
                        f"SKILL.md missing at {SKILL_MD}")

    def test_has_frontmatter_with_description(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("description:", fm,
                      "SKILL.md frontmatter must declare a `description:` field")


# ---------------------------------------------------------------------------
# AC #1 — trigger phrases
# ---------------------------------------------------------------------------

class DescriptionBoundsTests(unittest.TestCase):
    """The description must mention the in-scope phrases AND explicitly
    exclude the out-of-scope ones, so the LLM doesn't grab unrelated
    requests."""

    def setUp(self):
        self.text = _skill_text()
        self.description = _frontmatter(self.text)

    def test_positive_triggers_in_description(self):
        for phrase in (
            "set up servo",
            "scaffold oracle",
            "install agent loop infrastructure",
        ):
            self.assertIn(
                phrase, self.description.lower(),
                f"description should list trigger phrase {phrase!r}",
            )

    def test_negative_triggers_in_description(self):
        # AC #1: must NOT fire on bare "oracle" or "score this code".
        # The description must explicitly exclude these (a do-not list).
        desc_lower = self.description.lower()
        self.assertTrue(
            'do not' in desc_lower or 'don\'t' in desc_lower or "skip" in desc_lower,
            "description should contain an explicit do-not / exclusion section",
        )
        # The two specific anti-trigger phrases the spec names.
        for phrase in ("oracle", "score this code"):
            self.assertIn(
                phrase, desc_lower,
                f"description should reference (and exclude) the bare phrase {phrase!r}",
            )


# ---------------------------------------------------------------------------
# AC #2 — five Q&A questions documented
# ---------------------------------------------------------------------------

class QAQuestionsTests(unittest.TestCase):
    """Five questions, in the order the spec enumerates them."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_project_type_documented(self):
        self.assertIn("project type", self.body)
        # The four documented options.
        for option in ("service", "library", "plugin", "unsure"):
            self.assertIn(option, self.body, f"missing project-type option {option!r}")

    def test_tier_documented(self):
        self.assertIn("tier 0", self.body)
        self.assertIn("tier 1", self.body)
        self.assertIn("tier 2", self.body)

    def test_loop_guardrails_documented(self):
        self.assertIn("loop guardrails", self.body)
        self.assertIn("iteration cap", self.body)
        self.assertIn("cost ceiling", self.body)

    def test_hook_installation_documented(self):
        self.assertIn("hook installation", self.body)

    def test_existing_install_documented(self):
        self.assertIn("existing servo install", self.body)


# ---------------------------------------------------------------------------
# AC #3, #4 — skippability + pure-inference path
# ---------------------------------------------------------------------------

class SkippabilityTests(unittest.TestCase):
    def setUp(self):
        self.text = _skill_text().lower()

    def test_each_question_is_skippable(self):
        # SKILL.md must document that each question is skippable.
        self.assertIn("skip", self.text)
        self.assertIn("independently skippable", self.text,
                      "SKILL.md should use the verbatim 'independently skippable' phrasing")

    def test_pure_inference_path_documented(self):
        # AC #4: skipping all = no flags = pure inference.
        self.assertIn("pure inference", self.text,
                      "SKILL.md should name the 'pure inference' path explicitly")
        # And the LLM should be told never to invent answers.
        self.assertTrue(
            "never invent" in self.text or "do not invent" in self.text
            or "no invented" in self.text,
            "SKILL.md should forbid inventing answers when the user skips",
        )


# ---------------------------------------------------------------------------
# AC #5 — refusal surfacing
# ---------------------------------------------------------------------------

class RefusalSurfacingTests(unittest.TestCase):
    """If the helper refuses (oracle.sh already present), the LLM must
    surface the message verbatim — not silently retry with --force."""

    def setUp(self):
        self.text = _skill_text()

    def test_refusal_scenario_documented(self):
        body = self.text.lower()
        self.assertIn("already", body,
                      "SKILL.md should mention the 'already scaffolded' refusal")
        self.assertIn("--force", self.text,
                      "SKILL.md should reference the --force escape hatch")

    def test_no_silent_retry(self):
        body = self.text.lower()
        self.assertTrue(
            "verbatim" in body or "do not silently retry" in body
            or "never retry" in body or "do not retry silently" in body,
            "SKILL.md should explicitly tell the LLM not to silently retry on refusal",
        )


if __name__ == "__main__":
    unittest.main()
