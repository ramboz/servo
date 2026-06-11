"""
Surface tests for `skills/oracle-hook/SKILL.md` — slice 004-05 (skill-and-dogfood).

Mirrors the anti-greediness pattern of the sibling surface tests
(`skills/quality-gate/test_skill_surface.py`, `skills/agent-loop/test_skill_surface.py`)
and the SKILL.md house style: the description lists the phrases that *should*
fire `/servo:oracle-hook` and the phrases that should *not* (so the LLM's
trigger-matching stays narrow and never poaches a sibling skill's territory),
and the body documents the Tier-2 explicit-opt-in framing plus the Q&A needed to
run the installer correctly.

Covers slice 004-05 ACs 1-4 (the dogfood ACs 5-7 live in `test_dogfood.py`):

  * AC1 — skill exists + is discoverable (frontmatter name/description; listed in
    `.claude-plugin/install-contract.json`).
  * AC2 — trigger bounds (positive install/uninstall/status phrases; explicit
    Do-NOT-fire boundaries against quality-gate / agent-loop / scaffold-init).
  * AC3 — Tier-2 opt-in surfaced (settings.json mutation, backup, never
    auto-installed, fail-open posture, one-nudge-per-sequence).
  * AC4 — Q&A coverage (which target, must be scaffolded first, block-vs-soft
    -context mode, how to uninstall, how to read status incl. `inconsistent`).

Run via unittest or pytest:
    python3 skills/oracle-hook/test_skill_surface.py
    uvx pytest skills/oracle-hook/test_skill_surface.py -q
"""

import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "oracle-hook" / "SKILL.md"
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


# ---------------------------------------------------------------------------
# AC1 — existence / shape / discoverability
# ---------------------------------------------------------------------------


class SkillFileShapeTests(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(SKILL_MD.exists(), f"SKILL.md missing at {SKILL_MD}")

    def test_has_frontmatter_with_name_and_description(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("name:", fm, "SKILL.md frontmatter must declare a `name:` field")
        self.assertIn("description:", fm, "SKILL.md frontmatter must declare a `description:` field")
        self.assertIn("servo:oracle-hook", fm, "name should be `servo:oracle-hook`")


class InstallContractTests(unittest.TestCase):
    """AC1: the runtime-install verifier (spec 007) must know about the skill +
    its template, so they ship across every install surface."""

    def setUp(self):
        self.contract = json.loads(CONTRACT.read_text())

    def test_oracle_hook_skill_listed_with_helper(self):
        skills = self.contract["required"]["skills"]
        entry = next((s for s in skills if s.get("name") == "oracle-hook"), None)
        self.assertIsNotNone(
            entry, "install-contract.json required.skills must list `oracle-hook`"
        )
        self.assertIn("SKILL.md", entry["files"])
        self.assertIn("hook.py", entry["files"], "oracle-hook must vendor hook.py")

    def test_meta_judge_template_listed(self):
        templates = self.contract["required"]["templates"]
        self.assertIn(
            "meta-judge.sh.template", templates,
            "install-contract.json required.templates must list the meta-judge template",
        )


# ---------------------------------------------------------------------------
# AC2 — trigger bounds (positive + negative; sibling pointers)
# ---------------------------------------------------------------------------


class DescriptionBoundsTests(unittest.TestCase):
    """Fires on install/uninstall/status of the hook; does NOT fire on the
    sibling skills' territory (run-once = quality-gate, iterate = agent-loop,
    set-up = scaffold-init)."""

    def setUp(self):
        self.text = _skill_text()
        self.description = _frontmatter(self.text).lower()
        # Split the description at the Do-NOT boundary so the trigger tests can
        # assert *placement*, not mere presence: a positive phrase that drifted
        # into the Do-NOT block (or vice versa) is a real anti-greediness bug
        # the substring-anywhere check would miss.
        marker = "do not" if "do not" in self.description else "don't"
        self.assertIn(marker, self.description, "description needs a Do-NOT section")
        idx = self.description.index(marker)
        self.fire_part = self.description[:idx]
        self.do_not_part = self.description[idx:]

    def test_positive_triggers_before_do_not_section(self):
        # The spec's named positive triggers (AC2) — must be in the fire-on half.
        for phrase in (
            "install the oracle hook",
            "add the stop hook",
            "remove the meta-judge",
            "is the oracle hook installed",
        ):
            self.assertIn(
                phrase, self.fire_part,
                f"positive trigger {phrase!r} should be in the fire-on section",
            )

    def test_has_explicit_do_not_section(self):
        self.assertTrue(
            "do not" in self.description or "don't" in self.description,
            "description should contain an explicit do-not / exclusion section",
        )

    def test_negative_triggers_in_do_not_section(self):
        # Must NOT poach: run/score-once (quality-gate), iterate (agent-loop),
        # set up servo (scaffold-init) — and they must sit under Do-NOT, not
        # merely appear somewhere in the description.
        for phrase in ("run the oracle", "iterate", "set up servo"):
            self.assertIn(
                phrase, self.do_not_part,
                f"phrase {phrase!r} should be excluded under the Do-NOT section",
            )

    def test_points_at_quality_gate_for_running(self):
        self.assertIn(
            "/servo:quality-gate", self.text,
            "SKILL.md should point 'run/score the oracle once' requests at /servo:quality-gate",
        )

    def test_points_at_agent_loop_for_iterating(self):
        self.assertIn(
            "/servo:agent-loop", self.text,
            "SKILL.md should point 'iterate headlessly' requests at /servo:agent-loop",
        )

    def test_points_at_scaffold_init_for_setup(self):
        self.assertIn(
            "/servo:scaffold-init", self.text,
            "SKILL.md should point 'set up servo' requests at /servo:scaffold-init",
        )


# ---------------------------------------------------------------------------
# AC3 — Tier-2 explicit opt-in surfaced
# ---------------------------------------------------------------------------


class Tier2OptInTests(unittest.TestCase):
    """SKILL.md states the hook mutates settings.json, is backed up, is offered
    explicitly (never auto-installed), explains fail-open + one-nudge-per-sequence."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_names_tier_2(self):
        self.assertTrue(
            "tier-2" in self.body or "tier 2" in self.body,
            "SKILL.md should name the Tier-2 surface class",
        )

    def test_states_settings_mutation_and_backup(self):
        self.assertIn("settings.json", self.body)
        self.assertTrue(
            "back up" in self.body or "backed up" in self.body or "backup" in self.body,
            "SKILL.md should state settings.json is backed up before mutation",
        )

    def test_states_explicit_never_auto_install(self):
        self.assertIn("explicit", self.body)
        self.assertTrue(
            "never auto" in self.body or "not auto" in self.body or "never auto-install" in self.body,
            "SKILL.md should state the hook is never auto-installed",
        )

    def test_explains_fail_open(self):
        self.assertTrue(
            "fail open" in self.body or "fail-open" in self.body,
            "SKILL.md should explain the fail-open posture",
        )

    def test_explains_one_nudge_per_sequence(self):
        self.assertTrue(
            "once per" in self.body or "one nudge" in self.body or "stop_hook_active" in self.body,
            "SKILL.md should explain the at-most-one-nudge-per-stop-sequence behavior",
        )


# ---------------------------------------------------------------------------
# AC4 — Q&A coverage
# ---------------------------------------------------------------------------


class QAFlowTests(unittest.TestCase):
    """Documents: which target, that the target must be servo-scaffolded first,
    the block-vs-soft-context mode, how to uninstall, and how to read status
    (including the `inconsistent` state)."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_asks_which_target(self):
        self.assertIn("target", self.body)

    def test_target_must_be_scaffolded_first(self):
        self.assertTrue(
            "scaffolded first" in self.body or "scaffold the target first" in self.body
            or "servo-scaffolded" in self.body,
            "Q&A should state the target must be servo-scaffolded first",
        )

    def test_documents_block_vs_soft_context_mode(self):
        # The two mutually exclusive feedback modes (ADR-0006).
        self.assertIn("block", self.body)
        self.assertTrue(
            "additionalcontext" in self.body or "soft context" in self.body
            or "soft-context" in self.body,
            "Q&A should document the block-vs-soft-context mode",
        )

    def test_documents_uninstall(self):
        self.assertIn("uninstall", self.body)

    def test_documents_status_including_inconsistent(self):
        self.assertIn("status", self.body)
        self.assertIn(
            "inconsistent", self.body,
            "Q&A should document the `inconsistent` status state",
        )


# ---------------------------------------------------------------------------
# Refusal handling + examples (house-style parity with sibling skills)
# ---------------------------------------------------------------------------


class RefusalHandlingTests(unittest.TestCase):
    """The closed 0/2 exit contract: env-error reasons are named and the LLM is
    told never to silently retry."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_refusal_section_exists(self):
        self.assertIn("refusal", self.body)

    def test_reason_field_documented(self):
        for reason in ("target_missing", "manifest_missing", "oracle_missing", "settings_malformed"):
            self.assertIn(reason, self.body, f"refusal table missing reason {reason!r}")

    def test_no_silent_retry(self):
        self.assertTrue(
            "do not silently retry" in self.body or "verbatim" in self.body,
            "SKILL.md should tell the LLM not to silently retry on refusal",
        )

    def test_points_at_scaffold_init_for_unscaffolded(self):
        # manifest_missing / oracle_missing → recover via scaffold-init.
        self.assertIn("/servo:scaffold-init", self.text)


class ExamplesTests(unittest.TestCase):
    """At least one worked example per subcommand, in fenced bash."""

    def setUp(self):
        self.text = _skill_text()

    def test_fenced_bash_present(self):
        self.assertIn("```bash", self.text)

    def test_each_subcommand_shown(self):
        for sub in ("hook.py install", "hook.py uninstall", "hook.py status"):
            self.assertIn(sub, self.text, f"SKILL.md should show a `{sub}` invocation")


if __name__ == "__main__":
    unittest.main(verbosity=2)
