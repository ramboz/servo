"""
Surface tests for `/servo:design-eval` — spec slice 012-04 (guided-skill-surface).

Mirrors the sibling skills' anti-greediness pattern (`spec-oracle`,
`agent-loop`, `oracle-hook`): the SKILL.md description lists the phrases that
*should* fire the skill and the phrases that should *not*, and the body
documents the flow, the ownership split, and the honesty contract.

Two deliberate departures from the older sibling files, both closing gaps this
repo already logged in `docs/refinement-todo.md`:

* **Section-scoped assertions.** `_section()` slices the body by heading so a
  claim is checked *where it belongs*, rather than as a global substring that
  passes because the phrase happens to appear anywhere in the file.
* **Drift tripwires, not just substring checks.** The documented CLI verbs are
  asserted against `design_eval.py`'s real argparse subcommands, and the keys
  SKILL.md documents are asserted against the shipped
  `templates/config.example.json`. These fail when code and prose diverge —
  which is the failure mode a surface test is actually for.

Run:  python3 skills/design-eval/test_skill_surface.py
      pytest skills/design-eval/test_skill_surface.py -q
"""

import json
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_MD = HERE / "SKILL.md"
DESIGN_EVAL = HERE / "design_eval.py"
CONFIG_EXAMPLE = HERE / "templates" / "config.example.json"


def _skill_text() -> str:
    if not SKILL_MD.exists():
        raise FileNotFoundError(f"SKILL.md missing at {SKILL_MD}")
    return SKILL_MD.read_text()


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not m:
        raise AssertionError("SKILL.md missing YAML frontmatter delimited by --- fences")
    return m.group(1)


def _description(text: str) -> str:
    """The `description:` scalar only, whitespace-collapsed.

    Trigger assertions must check the *description* (what the host matches on),
    not the whole frontmatter — a phrase living in `name:` must not satisfy a
    trigger check. The value is a YAML folded scalar (`>-`): every following
    indented line is a continuation, joined with spaces.
    """
    fm = _frontmatter(text)
    m = re.search(r"^description:\s*>-?\s*\n((?:[ \t]+.*\n?)+)", fm, flags=re.MULTILINE)
    if not m:
        # tolerate a single-line `description: ...`
        m2 = re.search(r"^description:\s*(.+)$", fm, flags=re.MULTILINE)
        if not m2:
            raise AssertionError("SKILL.md frontmatter has no description: field")
        return re.sub(r"\s+", " ", m2.group(1)).strip()
    return re.sub(r"\s+", " ", m.group(1)).strip()


def _body(text: str) -> str:
    """Everything after the frontmatter fence."""
    m = re.match(r"^---\n.*?\n---\n(.*)$", text, flags=re.DOTALL)
    return m.group(1) if m else text


def _section(text: str, heading: str) -> str:
    """Return the body of a `## <heading>` section, up to the next `## `.

    Section-scoped so an assertion cannot be satisfied by the phrase appearing
    somewhere unrelated (the global-substring weakness recorded in
    refinement-todo, "SKILL.md body tests check substrings globally").
    """
    pattern = rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)"
    m = re.search(pattern, _body(text), flags=re.DOTALL | re.MULTILINE)
    if not m:
        raise AssertionError(
            f"SKILL.md has no `## {heading}` section (headings present: "
            f"{re.findall(r'^## (.+)$', _body(text), flags=re.MULTILINE)})"
        )
    return m.group(1)


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


class SkillFileShapeTests(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(SKILL_MD.exists(), f"SKILL.md missing at {SKILL_MD}")

    def test_has_frontmatter_with_name_and_description(self):
        fm = _frontmatter(_skill_text())
        self.assertIn("name:", fm)
        self.assertIn("description:", fm)

    def test_name_is_design_eval(self):
        fm = _frontmatter(_skill_text())
        self.assertRegex(fm, r"name:\s*design-eval\b")

    def test_documents_the_expected_sections(self):
        body = _body(_skill_text())
        headings = re.findall(r"^## (.+)$", body, flags=re.MULTILINE)
        for required in ("Prerequisites", "Flow", "Authoring tips"):
            self.assertIn(required, headings, f"SKILL.md should have a `## {required}` section")


# ---------------------------------------------------------------------------
# Trigger bounds (anti-greediness) — asserted against the description only
# ---------------------------------------------------------------------------


class DescriptionBoundsTests(unittest.TestCase):
    """Fires on design-fidelity authoring; not on deterministic checks or the
    per-iteration judge agent."""

    def setUp(self):
        # Assert against the description: scalar specifically (what the host
        # matches on) — not the whole frontmatter, so a phrase in name: cannot
        # satisfy a trigger check.
        self.description = _description(_skill_text()).lower()

    def test_positive_triggers_in_description(self):
        for phrase in (
            "design mockup",
            "does the ui match the design",
            "score_design_fidelity",
        ):
            self.assertIn(
                phrase, self.description,
                f"description should list positive trigger phrase {phrase!r}",
            )

    def test_has_explicit_do_not_section(self):
        self.assertTrue(
            "do not use" in self.description or "don't use" in self.description,
            "description should carry an explicit do-not / exclusion clause so the "
            "skill does not fire greedily",
        )

    def test_negative_triggers_named_in_description(self):
        # Must NOT fire for deterministic checks, nor for the per-iteration judge.
        for phrase in ("deterministic checks", "judge agent"):
            self.assertIn(
                phrase, self.description,
                f"description should name (and exclude) {phrase!r}",
            )

    def test_deterministic_work_is_redirected_to_siblings(self):
        self.assertTrue(
            "scaffold-init" in self.description and "spec-oracle" in self.description,
            "the do-not clause should redirect deterministic checks at "
            "scaffold-init / spec-oracle rather than just refusing",
        )


# ---------------------------------------------------------------------------
# Sibling pointers — where each downstream request should go
# ---------------------------------------------------------------------------


class SiblingPointerTests(unittest.TestCase):
    def setUp(self):
        self.text = _skill_text()

    def test_points_at_scaffold_init_for_an_unscaffolded_target(self):
        self.assertIn(
            "/servo:scaffold-init", _section(self.text, "Prerequisites"),
            "Prerequisites should send an unscaffolded target to /servo:scaffold-init",
        )

    def test_points_at_running_skills_in_the_flow(self):
        flow = _section(self.text, "Flow")
        for pointer in ("/servo:quality-gate", "/servo:agent-loop"):
            self.assertIn(
                pointer, flow,
                f"the Flow's run step should point at {pointer}",
            )


# ---------------------------------------------------------------------------
# Drift tripwires — prose vs. the code and the shipped template
# ---------------------------------------------------------------------------


class DocumentedCliMatchesCodeTests(unittest.TestCase):
    """The verbs SKILL.md teaches must be the verbs `design_eval.py` accepts.

    This is the assertion that actually earns its keep: it fails when a
    subcommand is renamed/added in code without updating the guided flow (or
    vice-versa), which no amount of substring-checking would catch.
    """

    def _code_subcommands(self) -> set:
        src = DESIGN_EVAL.read_text()
        m = re.search(r'for name in \(([^)]*)\)', src, flags=re.DOTALL)
        self.assertIsNotNone(m, "could not locate design_eval.py's subcommand tuple")
        return set(re.findall(r'"([a-z-]+)"', m.group(1)))

    def test_code_exposes_the_expected_verbs(self):
        self.assertEqual(
            self._code_subcommands(),
            {"init", "capture-refs", "freeze", "install", "uninstall",
             "advisory", "catalogue", "record-reenumeration"},
        )

    def test_flow_documents_every_mutating_verb(self):
        flow = _section(_skill_text(), "Flow")
        # `uninstall` is the reversal path, not part of the authoring flow.
        for verb in sorted(self._code_subcommands() - {"uninstall"}):
            self.assertIn(
                verb, flow,
                f"the Flow section should document the `{verb}` verb",
            )

    def test_flow_documents_verbs_in_execution_order(self):
        flow = _section(_skill_text(), "Flow")
        # Anchor on the numbered step markers (`N. **`verb`**`), not the first
        # substring: the word "freeze" also appears in step 2's prose, so a
        # naive first-index check would mis-order it.
        step_verbs = re.findall(r"^\d+\.\s+\*\*`([a-z-]+)`\*\*", flow, flags=re.MULTILINE)
        self.assertEqual(
            step_verbs, ["init", "capture-refs", "freeze", "install"],
            "Flow's numbered steps should teach the verbs in execution order",
        )


class DocumentedConfigMatchesTemplateTests(unittest.TestCase):
    """The policy keys SKILL.md describes must exist in the shipped template."""

    def setUp(self):
        self.config = json.loads(CONFIG_EXAMPLE.read_text())

    def test_template_is_valid_json(self):
        self.assertIsInstance(self.config, dict)

    def test_template_carries_the_documented_policy_keys(self):
        # 028-01 (ADR-0033): the free-text `rubric` was replaced by the structured
        # `dimensions` + `ignore` policy.
        for key in ("app_url", "viewport", "judge", "samples", "threshold",
                    "dimensions", "ignore", "screens"):
            self.assertIn(key, self.config, f"config.example.json should define {key!r}")
        self.assertNotIn("rubric", self.config, "the legacy free-text rubric is gone")

    def test_documented_sample_params_exist(self):
        # SKILL.md teaches n / k / δ — the template must actually expose them.
        for key in ("n", "k", "delta"):
            self.assertIn(key, self.config["samples"])

    def test_template_ships_unapproved(self):
        # A shipped template must never arrive pre-approved — that would let a
        # project score against an unreviewed definition (ADR-0005 clause 2).
        self.assertEqual(self.config.get("approval_status"), "draft")

    def test_screens_carry_reference_and_crop(self):
        screen = self.config["screens"][0]
        self.assertIn("reference", screen)
        self.assertIn("crop", screen["referenceSource"],
                      "the example must demonstrate the chrome-crop insets")

    def test_documented_transports_match_the_template_choice(self):
        prereq = _section(_skill_text(), "Prerequisites")
        for transport in ('"api"', '"cli"'):
            self.assertIn(transport, prereq,
                          f"Prerequisites should document the {transport} transport")
        self.assertIn(self.config["judge"]["transport"], ("api", "cli"))


# ---------------------------------------------------------------------------
# The honesty contract — the thing this skill must never soften
# ---------------------------------------------------------------------------


class DocumentedFilesMatchInitVendoringTests(unittest.TestCase):
    """Every runtime file `init()` vendors must appear in SKILL.md's Files table.

    Blocking craft-review finding: after `capture_lib.mjs`/`fidelity_eval.py`
    were added to `design_eval.py::init()`'s copy tuple, a reader who followed
    the Files table got a target whose `capture.mjs` cannot import at run time.
    This parses the copy tuple the same way `DocumentedCliMatchesCodeTests`
    parses the verb tuple, so the doc can never silently under-list the runtime
    again.
    """

    def _vendored_runtime(self) -> set:
        src = DESIGN_EVAL.read_text()
        # the `for runtime, src_dir in ( ("score.py", ...), ... ):` tuple
        m = re.search(r"for runtime, src_dir in \((.*?)\n    \):", src, flags=re.DOTALL)
        self.assertIsNotNone(m, "could not locate init()'s runtime copy tuple")
        return set(re.findall(r'"([\w.]+\.(?:py|mjs))"', m.group(1)))

    def test_files_table_lists_every_vendored_runtime_file(self):
        vendored = self._vendored_runtime()
        self.assertIn("capture_lib.mjs", vendored, "sanity: extraction is in the copy list")
        files_section = _section(_skill_text(), "Files (in `<target>/.servo/design-eval/`)")
        missing = [f for f in vendored if f not in files_section]
        self.assertEqual(
            missing, [],
            f"SKILL.md Files table omits vendored runtime file(s): {missing}",
        )


class HonestyContractTests(unittest.TestCase):
    def setUp(self):
        self.text = _skill_text()

    def test_states_the_ownership_split(self):
        body = _body(self.text).lower()
        self.assertIn("servo owns", body)
        self.assertIn("project", body)

    def test_states_scores_not_proves(self):
        self.assertIn(
            "does not prove", _body(self.text),
            "SKILL.md must keep the 'servo scores, it does not prove' honesty line",
        )

    def test_env_error_is_never_a_silent_zero(self):
        body = _body(self.text)
        self.assertIn("env_error", body)
        self.assertIn("0.0", body)
        self.assertRegex(
            body, r"never a\s+silent\s+`?0\.0`?",
            "SKILL.md must state that a missing key / unreachable judge is "
            "env_error and never a silent 0.0",
        )

    def test_stale_refusal_is_documented(self):
        self.assertIn("stale", _body(self.text).lower())

    def test_pairs_with_the_plateau_noise_floor(self):
        flow = _section(self.text, "Flow")
        self.assertIn("--plateau-noise-floor", flow)
        self.assertIn("ADR-0005", flow)


if __name__ == "__main__":
    unittest.main()
