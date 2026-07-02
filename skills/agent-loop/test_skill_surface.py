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
ARCH_MD = REPO_ROOT / "docs" / "architecture.md"


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
    `--plateau-window`, `--plateau-noise-floor`, `--resume`, `--resume-anyway` are
    each named in the body."""

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

    def test_plateau_noise_floor_flag_documented(self):
        self.assertIn("--plateau-noise-floor", self.text)

    def test_resume_flag_documented(self):
        self.assertIn("--resume", self.text)
        # And the escape hatch must be documented too.
        self.assertIn("--resume-anyway", self.text)

    def test_env_var_documented(self):
        # SERVO_CLAUDE_TIMEOUT is the per-invocation timeout escape hatch.
        self.assertIn("SERVO_CLAUDE_TIMEOUT", self.text)

    def test_examples_present(self):
        # At least one fenced bash example block.
        self.assertIn(
            "```bash", self.text, "SKILL.md should include at least one fenced bash example"
        )


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


# ---------------------------------------------------------------------------
# Slice 003-08 — detach + Routine-ready + gate.py-authority + host matrix (DoD)
# ---------------------------------------------------------------------------


class Slice003_08SurfaceTests(unittest.TestCase):
    """SKILL.md documents `--background` + the Routine-ready / scheduled-run modes
    + the gate.py-authority contract; architecture.md carries the execution matrix
    + the clean-baseline expectation (003-08 DoD; AC3/AC4/AC5)."""

    def setUp(self):
        self.skill = _skill_text()
        self.skill_lower = self.skill.lower()
        self.assertTrue(ARCH_MD.exists(), f"architecture.md missing at {ARCH_MD}")
        self.arch_lower = ARCH_MD.read_text().lower()

    def test_background_flag_documented(self):
        self.assertIn("--background", self.skill)

    def test_emit_routine_prompt_documented(self):
        self.assertIn("--emit-routine-prompt", self.skill)

    def test_routine_run_mode_documented(self):
        self.assertIn("routine", self.skill_lower)

    def test_detached_terminal_reasons_documented(self):
        self.assertIn("detached", self.skill_lower)
        self.assertIn("detach_failed", self.skill)

    def test_gate_authority_contract_documented(self):
        # AC3: in a Routine / continuous invocation gate.py is the authority and
        # the meta-judge Stop hook is moot.
        self.assertIn("authority", self.skill_lower)
        self.assertTrue(
            "meta-judge" in self.skill_lower and "moot" in self.skill_lower,
            "SKILL.md should state the meta-judge is moot in a Routine (gate.py is authority)",
        )

    def test_architecture_execution_matrix_present(self):
        # AC5: the full host-scope execution matrix (the four host rows).
        for token in ("interactive", "headless", "routine", "non-claude"):
            self.assertIn(token, self.arch_lower, f"execution matrix missing {token!r} row")

    def test_architecture_clean_baseline_documented(self):
        # AC4: the clean-baseline / git-reset / fresh-clone expectation for runs.
        self.assertTrue(
            "git reset" in self.arch_lower
            or "fresh clone" in self.arch_lower
            or "fresh-clone" in self.arch_lower,
            "architecture.md should document the clean-baseline expectation for scheduled runs",
        )


# ---------------------------------------------------------------------------
# Slice 019-04 — oracle-as-a-service / bring-your-own-implementer
# ---------------------------------------------------------------------------


class OracleAsAServiceDocsTests(unittest.TestCase):
    """SKILL.md names the oracle-as-a-service flow: Compile produces a frozen,
    reviewable oracle; any driver (human, CI, another agent) may perform the
    edits; quality-gate is the pass/fail authority; the native loop is one
    optional driver, not a prerequisite. Cross-links ADR-0021 and
    quality-gate's SKILL.md (ADR-0021 / slice 019-04 AC2/AC4)."""

    def setUp(self):
        self.text = _skill_text()
        self.body = self.text.lower()

    def test_oracle_as_a_service_section_header_present(self):
        self.assertIn(
            "oracle-as-a-service", self.body,
            "SKILL.md should have a named oracle-as-a-service section",
        )
        self.assertIn("bring-your-own-implementer", self.body)

    def test_named_actors_present(self):
        # Compile / driver / quality-gate — the three actors of the flow.
        self.assertIn("compile", self.body)
        self.assertIn("driver", self.body)
        self.assertIn("quality-gate", self.body)

    def test_any_driver_examples_named(self):
        # human / CI / another agent — the flow is driver-agnostic.
        self.assertIn("human", self.body)
        self.assertIn("ci", self.body)
        self.assertIn("another agent", self.body)

    def test_loop_framed_as_optional_not_prerequisite(self):
        self.assertTrue(
            "optional driver" in self.body or "optional consumer" in self.body,
            "SKILL.md should frame the native loop as one optional driver",
        )
        self.assertIn("not a prerequisite", self.body)

    def test_links_to_quality_gate_skill(self):
        self.assertIn(
            "../quality-gate/SKILL.md", self.text,
            "SKILL.md should cross-link to skills/quality-gate/SKILL.md",
        )

    def test_links_to_adr_0021(self):
        self.assertIn(
            "adr-0021-oracle-first-agent-loop-optional-consumer.md", self.text,
            "SKILL.md should cross-link to ADR-0021",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
