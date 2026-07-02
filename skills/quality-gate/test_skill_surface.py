"""
Surface tests for `skills/quality-gate/SKILL.md` — slice 002-05 (qa-wizard).

Mirrors `skills/scaffold-init/test_skill_surface.py`'s anti-greediness
pattern: the SKILL.md description lists both the phrases that *should* fire
the skill and the phrases that should *not*, so the LLM's trigger-matching
stays narrow.

Run via either unittest or pytest:
    python3 skills/quality-gate/test_skill_surface.py
    pytest skills/quality-gate/test_skill_surface.py
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "quality-gate" / "SKILL.md"


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
        self.assertIn(
            "description:", fm, "SKILL.md frontmatter must declare a `description:` field"
        )
        self.assertIn("servo:quality-gate", fm, "name should be `servo:quality-gate`")


# ---------------------------------------------------------------------------
# AC #1 — trigger phrases (positive + negative)
# ---------------------------------------------------------------------------


class DescriptionBoundsTests(unittest.TestCase):
    """Description lists in-scope phrases AND explicitly excludes out-of-scope
    ones so the LLM doesn't poach requests that belong to a sibling skill."""

    def setUp(self):
        self.text = _skill_text()
        self.description = _frontmatter(self.text)

    def test_positive_triggers_in_description(self):
        # The spec's named positive triggers (002-05 AC #1).
        for phrase in (
            "score this code",
            "run the oracle",
            "run quality gate",
            "oracle score",
        ):
            self.assertIn(
                phrase, self.description.lower(),
                f"description should list positive trigger phrase {phrase!r}",
            )

    def test_audit_trigger_in_description(self):
        # AC #4: audit example surfaces via "what does this servo install include".
        self.assertIn(
            "install include", self.description.lower(),
            "description should reference the audit trigger phrase",
        )

    def test_negative_triggers_in_description(self):
        # AC #1: must NOT fire on scaffold / fix-tests requests.
        desc_lower = self.description.lower()
        self.assertTrue(
            "do not" in desc_lower or "don't" in desc_lower,
            "description should contain an explicit do-not / exclusion section",
        )
        for phrase in ("scaffold", "fix the failing test", "make tests pass", "review my code"):
            self.assertIn(
                phrase, desc_lower,
                f"description should reference (and exclude) the bare phrase {phrase!r}",
            )

    def test_excludes_sibling_scaffold_init(self):
        # AC #1: explicit pointer to scaffold-init as the right skill for
        # "set up servo" / "scaffold oracle" so the LLM doesn't grab the wrong one.
        self.assertIn(
            "/servo:scaffold-init", self.text,
            "SKILL.md should point users at /servo:scaffold-init for scaffolding requests",
        )


# ---------------------------------------------------------------------------
# AC #2 — Options section documented
# ---------------------------------------------------------------------------


class OptionsSectionTests(unittest.TestCase):
    """`--json`, `--verbose`, `--timeout`, and the `audit` subcommand are
    each named with a one-line description plus an example invocation."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_json_flag_documented(self):
        self.assertIn("--json", self.text)

    def test_verbose_flag_documented(self):
        self.assertIn("--verbose", self.text)

    def test_timeout_flag_documented(self):
        self.assertIn("--timeout", self.text)
        # And the env var alternative.
        self.assertIn("SERVO_GATE_TIMEOUT", self.text)

    def test_audit_subcommand_documented(self):
        self.assertIn("audit", self.body)
        # Audit must explain it does NOT invoke the oracle.
        self.assertTrue(
            "without invoking" in self.body or "no oracle invocation" in self.body,
            "audit section should explain it does not invoke oracle.sh",
        )

    def test_examples_present(self):
        # At least one fenced bash block under "Examples" or similar.
        self.assertIn(
            "```bash",
            self.text,
            "SKILL.md should include at least one fenced bash example block",
        )


# ---------------------------------------------------------------------------
# AC #3 — Refusal handling guidance
# ---------------------------------------------------------------------------


class RefusalHandlingTests(unittest.TestCase):
    """Refusal modes are distinguished by `reason`; LLM is told never to silently retry."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_refusal_section_exists(self):
        self.assertIn("refusal", self.body)

    def test_reason_field_documented(self):
        # The closed `reason` taxonomy from spec 002 + ADR-0002.
        for reason in (
            "manifest_missing",
            "oracle_missing",
            "oracle_not_executable",
            "timeout",
            "unparseable_oracle_output",
            "unexpected_exit",
        ):
            self.assertIn(reason, self.body, f"refusal table missing reason {reason!r}")

    def test_no_silent_retry(self):
        # Don't auto-rerun on rc=2 — surface the message instead.
        self.assertTrue(
            "do not silently retry" in self.body or "verbatim" in self.body,
            "SKILL.md should tell the LLM not to silently retry on refusal",
        )

    def test_recovery_pointers_present(self):
        # AC #3: missing-oracle/missing-manifest → suggest scaffold-init.
        self.assertIn("/servo:scaffold-init", self.text)
        # Timeout → offer longer --timeout.
        self.assertIn("longer", self.body)
        # chmod hint for non-executable oracle.
        self.assertIn("chmod +x", self.text)


# ---------------------------------------------------------------------------
# AC #4 — Audit example
# ---------------------------------------------------------------------------


class AuditExampleTests(unittest.TestCase):
    """At least one example shows a user asking 'what does this servo install
    include' → the LLM runs gate.py audit <target> and surfaces the output."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_audit_example_present(self):
        # An example block that shows the audit invocation pattern.
        self.assertIn("gate.py audit", self.text)

    def test_audit_example_mentions_install_contents(self):
        # Audit's purpose: introspect what's installed.
        self.assertTrue(
            "tier" in self.body and "components" in self.body,
            "audit example should reference tier + components "
            "(the manifest's two load-bearing fields)",
        )

    def test_audit_example_shows_no_oracle_invocation(self):
        # AC #3 of slice 002-03 + AC #4 here: audit MUST NOT invoke the oracle.
        # The example should make this clear.
        self.assertTrue(
            "without invoking" in self.body or "no oracle invocation" in self.body,
            "SKILL.md should highlight that audit does not invoke the oracle",
        )


# ---------------------------------------------------------------------------
# Slice 019-04 — external-driver / bring-your-own-implementer contract
# ---------------------------------------------------------------------------


class ExternalDriverDocsTests(unittest.TestCase):
    """`gate.py` documents that it can be invoked standalone by an external
    driver (CI pipeline, another agent, a human) as the pass/fail authority
    over a Compiled oracle, independent of agent-loop — pointing at the
    already-shipped stateless / `--json` / closed-exit-code properties as
    *why*, and cross-linking back to agent-loop's SKILL.md and ADR-0021."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_external_driver_section_header_present(self):
        self.assertIn(
            "external-driver", self.body,
            "SKILL.md should have a named external-driver section",
        )

    def test_named_actors_present(self):
        # Compile / driver / quality-gate — the three actors of the flow.
        self.assertIn("compile", self.body)
        self.assertTrue(
            "driver" in self.body,
            "SKILL.md should name a (external) driver as an actor",
        )
        self.assertIn("quality-gate", self.body)

    def test_external_caller_examples_named(self):
        # CI pipeline / another agent / a human — the three example drivers.
        for phrase in ("ci pipeline", "another agent", "a human"):
            self.assertIn(
                phrase, self.body,
                f"SKILL.md should name {phrase!r} as an example external driver",
            )

    def test_why_it_already_works_properties_named(self):
        # The three existing properties that make this work with no new code.
        self.assertIn("stateless", self.body)
        self.assertIn("--json", self.text)
        self.assertTrue(
            "0, 1, 2" in self.body or "0/1/2" in self.body,
            "SKILL.md should cite the closed exit-code contract as a reason this works today",
        )

    def test_links_to_agent_loop_skill(self):
        self.assertIn(
            "../agent-loop/SKILL.md", self.text,
            "SKILL.md should cross-link to skills/agent-loop/SKILL.md",
        )

    def test_links_to_adr_0021(self):
        self.assertIn(
            "adr-0021-oracle-first-agent-loop-optional-consumer.md", self.text,
            "SKILL.md should cross-link to ADR-0021",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
