"""
AC verification tests for slices 008-01 (residual-triage) and 008-02
(rubric-shaping) of `/servo:eval-authoring`.

Run from the repo root:
    python3 -m pytest skills/eval-authoring/test_eval_authoring.py -q

All of spec 008's tests accrete in this one file (see spec.md "Test
surface"). The 008-01 tranche (classification) is deterministic
(keyword/substring matching over the AC statement text, no LLM/network
call), so every fixture there is stable and offline. The 008-02 tranche
(rubric shaping + the judge path in `score.py`) is also offline: the judge
HTTP call is monkeypatched exactly as `skills/content-fidelity/
test_content_fidelity.py` does (no real API key / network access needed).

Test idiom mirrors `skills/spec-oracle/test_oracle_plan.py` /
`skills/edd-suitability/test_suitability.py`:
  - `unittest.TestCase` classes (collected by pytest),
  - `REPO_ROOT = Path(__file__).resolve().parents[2]`,
  - fixtures written into a `tempfile.TemporaryDirectory()`,
  - the CLI driven as a subprocess for end-to-end (AC4/AC5/AC6) paths,
  - the pure classification/shaping logic imported directly for fast unit
    assertions, via the `importlib`/load-by-path idiom (the skill
    directory names are hyphenated and not importable Python packages).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_AUTHORING = REPO_ROOT / "skills" / "eval-authoring" / "eval_authoring.py"
EVAL_AUTHORING_SCORE = REPO_ROOT / "skills" / "eval-authoring" / "score.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("eval_authoring", EVAL_AUTHORING)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_score_module():
    spec = importlib.util.spec_from_file_location("eval_authoring_score", EVAL_AUTHORING_SCORE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ea = _load_module()
score = _load_score_module()

ORACLE_PLAN = REPO_ROOT / "skills" / "spec-oracle" / "oracle_plan.py"


def _load_oracle_plan_module():
    """Load spec-006's `oracle_plan.py` by path (same importlib idiom as
    `_load_module` above) — used only to drift-check the mirrored
    `RESIDUAL_REASON_*` literals, never for cross-skill data exchange at
    runtime (see `eval_authoring.py`'s module docstring)."""
    spec = importlib.util.spec_from_file_location("oracle_plan", ORACLE_PLAN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_plan(root: Path, *, spec_id: str = "042-demo", checks=None,
              residual=None, source_hash: str = "sha256:deadbeef") -> Path:
    """Write a spec-006-shaped `checks.json` plan under a fixture spec dir.

    Mirrors the real layout (`<spec-dir>/oracle/<spec-id>/checks.json`) so
    the plan's `source_spec_path` resolves to a real spec directory an
    eval-authoring artifact can be colocated beside (AC4).
    """
    spec_dir = root / spec_id
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / "spec.md"
    if not spec_path.exists():
        spec_path.write_text(f"# Spec {spec_id}\n")

    plan = {
        "schema_version": 1,
        "spec_id": spec_id,
        "source_spec_path": str(spec_path),
        "source_hash": source_hash,
        "planner_version": "0.1.0",
        "generated_at": "2026-01-01T00:00:00Z",
        "checks": checks or [],
        "residual_judgment": residual or [],
    }
    plan_dir = spec_dir / "oracle" / spec_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / "checks.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    return plan_path


def _out_dir(root: Path, spec_id: str = "042-demo") -> Path:
    return root / spec_id / "eval" / spec_id


def _run_cli(args: list) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(EVAL_AUTHORING)] + args,
        capture_output=True, text=True,
    )


MIXED_RESIDUAL = [
    {
        "id": "AC-042-demo-1",
        "statement": "The summary must not contradict any fact in the source document.",
        "source_line": 10,
        "reason": ea.RESIDUAL_REASON_UNMATCHED,
        "suggested_review": "human or craft-review pass",
    },
    {
        "id": "AC-042-demo-2",
        "statement": "The copy tone is appropriate and reads well.",
        "source_line": 14,
        "reason": ea.RESIDUAL_REASON_TASTE,
        "suggested_review": "human or craft-review pass",
    },
]

ALL_TASTE_RESIDUAL = [
    {
        "id": "AC-042-demo-1",
        "statement": "The onboarding copy reads well and is appropriately worded.",
        "source_line": 5,
        "reason": ea.RESIDUAL_REASON_TASTE,
        "suggested_review": "human or craft-review pass",
    },
    {
        "id": "AC-042-demo-2",
        "statement": "The landing page tone matches our brand positioning.",
        "source_line": 8,
        "reason": ea.RESIDUAL_REASON_TASTE,
        "suggested_review": "human or craft-review pass",
    },
]


# ---------------------------------------------------------------------------
# Cross-skill contract drift guard
# ---------------------------------------------------------------------------

class ResidualReasonDriftGuardTests(unittest.TestCase):
    """`RESIDUAL_REASON_TASTE` / `RESIDUAL_REASON_UNMATCHED` are mirrored here
    as literals, not imported (cross-skill data is JSON, never a Python
    import — see `eval_authoring.py`'s module docstring). If spec-006 ever
    changes those strings without a matching update here, every
    `residual_judgment` entry's `reason` would fail to match either mirrored
    literal and silently fall into the "unrecognized reason" branch —
    eval-able detection would drop to zero while every test in this file
    (which only ever uses `ea.RESIDUAL_REASON_*`) kept passing. Load
    spec-006's own module and compare against its live values so that drift
    fails loudly instead."""

    def test_mirrored_reason_literals_match_spec_006(self):
        oracle_plan = _load_oracle_plan_module()
        self.assertEqual(ea.RESIDUAL_REASON_TASTE, oracle_plan.RESIDUAL_REASON_TASTE)
        self.assertEqual(ea.RESIDUAL_REASON_UNMATCHED, oracle_plan.RESIDUAL_REASON_UNMATCHED)


# ---------------------------------------------------------------------------
# AC1 / AC2 — classification, fail-closed (unit, direct import)
# ---------------------------------------------------------------------------

class ClassifyEntryTests(unittest.TestCase):
    def test_taste_reason_is_never_promoted(self):
        """A TASTE-reasoned entry is never eval-able, regardless of statement text."""
        entry = {
            "id": "AC-1", "source_line": 1,
            "statement": "No taste-flavored words in this sentence whatsoever.",
            "reason": ea.RESIDUAL_REASON_TASTE,
        }
        result = ea.classify_entry(entry)
        self.assertEqual(result["classification"], "human-residual")

    def test_unmatched_reason_with_taste_language_stays_human_residual(self):
        """AC2: even an UNMATCHED entry defaults to human-residual when the
        statement itself reads as taste/policy/ADR-shaped."""
        entry = {
            "id": "AC-2", "source_line": 2,
            "statement": "This needs to reflect our brand's tone and positioning.",
            "reason": ea.RESIDUAL_REASON_UNMATCHED,
        }
        result = ea.classify_entry(entry)
        self.assertEqual(result["classification"], "human-residual")

    def test_unmatched_reason_without_taste_language_is_eval_able(self):
        entry = {
            "id": "AC-3", "source_line": 3,
            "statement": "The summary must not contradict any fact in the source document.",
            "reason": ea.RESIDUAL_REASON_UNMATCHED,
        }
        result = ea.classify_entry(entry)
        self.assertEqual(result["classification"], "eval-able")

    def test_unknown_reason_defaults_to_human_residual(self):
        """A reason value that isn't one of the two known constants is
        treated as uncertain — fail-closed (AC2)."""
        entry = {
            "id": "AC-4", "source_line": 4,
            "statement": "Some future classification reason.",
            "reason": "some as-yet-unknown reason string",
        }
        result = ea.classify_entry(entry)
        self.assertEqual(result["classification"], "human-residual")

    def test_missing_reason_defaults_to_human_residual(self):
        entry = {"id": "AC-5", "source_line": 5, "statement": "no reason field at all"}
        result = ea.classify_entry(entry)
        self.assertEqual(result["classification"], "human-residual")

    def test_every_entry_carries_a_rationale(self):
        for entry in (MIXED_RESIDUAL + ALL_TASTE_RESIDUAL):
            result = ea.classify_entry(entry)
            self.assertTrue(result["rationale"])

    def test_proposal_starts_unconfirmed(self):
        """AC1/AC2: classification is a proposal a human confirms — it never
        starts pre-confirmed."""
        entry = {
            "id": "AC-6", "source_line": 6, "statement": "x",
            "reason": ea.RESIDUAL_REASON_UNMATCHED,
        }
        result = ea.classify_entry(entry)
        self.assertIs(result["confirmed"], False)

    def test_short_taste_token_is_word_anchored_not_a_bare_substring(self):
        """Nit: 'tone' must not false-hit inside 'milestone' — short/
        ambiguous taste tokens are word-boundary matched (mirrors
        `oracle_plan.py::_has_word`), so an otherwise unmatched AC whose
        text merely contains 'milestone' stays eval-able rather than being
        pushed to human-residual for an unrelated reason."""
        entry = {
            "id": "AC-7", "source_line": 7,
            "statement": "The release milestone document lists every shipped item.",
            "reason": ea.RESIDUAL_REASON_UNMATCHED,
        }
        result = ea.classify_entry(entry)
        self.assertEqual(result["classification"], "eval-able")


# ---------------------------------------------------------------------------
# AC5 — structural determinism of ordering
# ---------------------------------------------------------------------------

class BuildTriageOrderingTests(unittest.TestCase):
    def test_entries_sorted_by_source_line_then_id_regardless_of_input_order(self):
        plan = {
            "spec_id": "x", "source_spec_path": "/tmp/x/spec.md",
            "residual_judgment": [
                {"id": "AC-3", "statement": "c", "source_line": 30,
                 "reason": ea.RESIDUAL_REASON_UNMATCHED},
                {"id": "AC-1", "statement": "a", "source_line": 10,
                 "reason": ea.RESIDUAL_REASON_UNMATCHED},
                {"id": "AC-2", "statement": "b", "source_line": 20,
                 "reason": ea.RESIDUAL_REASON_UNMATCHED},
            ],
        }
        triage = ea.build_triage(plan)
        self.assertEqual([e["id"] for e in triage["entries"]], ["AC-1", "AC-2", "AC-3"])

    def test_entries_without_source_line_sort_last_but_stay_deterministic(self):
        plan = {
            "spec_id": "x", "source_spec_path": "/tmp/x/spec.md",
            "residual_judgment": [
                {"id": "AC-b", "statement": "b", "reason": ea.RESIDUAL_REASON_UNMATCHED},
                {"id": "AC-1", "statement": "a", "source_line": 1,
                 "reason": ea.RESIDUAL_REASON_UNMATCHED},
                {"id": "AC-a", "statement": "a", "reason": ea.RESIDUAL_REASON_UNMATCHED},
            ],
        }
        triage = ea.build_triage(plan)
        self.assertEqual([e["id"] for e in triage["entries"]], ["AC-1", "AC-a", "AC-b"])


# ---------------------------------------------------------------------------
# AC6 — mixed plan / all-taste plan / round-trip (CLI end-to-end)
# ---------------------------------------------------------------------------

class MixedPlanTests(unittest.TestCase):
    def test_mixed_plan_triaged_correctly(self):
        """A plan with one eval-able (unmatched) AC and one taste AC is
        triaged correctly, without error."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)

            payload = json.loads((_out_dir(root) / "triage.json").read_text())
            by_id = {e["id"]: e for e in payload["entries"]}
            self.assertEqual(by_id["AC-042-demo-1"]["classification"], "eval-able")
            self.assertEqual(by_id["AC-042-demo-2"]["classification"], "human-residual")
            self.assertEqual(payload["eval_able"], ["AC-042-demo-1"])


class AllTastePlanTests(unittest.TestCase):
    def test_all_taste_plan_yields_zero_eval_able_without_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=ALL_TASTE_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)

            payload = json.loads((_out_dir(root) / "triage.json").read_text())
            self.assertEqual(payload["eval_able"], [])
            self.assertTrue(
                all(e["classification"] == "human-residual" for e in payload["entries"])
            )


class RoundTripTests(unittest.TestCase):
    def test_eval_able_list_is_a_wellformed_machine_contract_for_008_02(self):
        """AC3: eval-able ACs are queued as input to 008-02 — assert the
        `eval_able` list is a well-formed, re-readable machine contract."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)

            out = _out_dir(root) / "triage.json"
            payload = json.loads(out.read_text())

            self.assertIsInstance(payload["eval_able"], list)
            entries_by_id = {e["id"]: e for e in payload["entries"]}
            self.assertTrue(
                payload["eval_able"], "fixture must exercise a non-empty eval_able list")
            for ac_id in payload["eval_able"]:
                self.assertIsInstance(ac_id, str)
                self.assertIn(ac_id, entries_by_id)
                self.assertEqual(entries_by_id[ac_id]["classification"], "eval-able")

            # Re-reading the written bytes reproduces the exact same payload
            # (i.e. the artifact round-trips: write -> read -> same value).
            reloaded = json.loads(out.read_text())
            self.assertEqual(reloaded, payload)


# ---------------------------------------------------------------------------
# AC4 — colocation (ADR-0023): project-owned, spec-adjacent, not target state
# ---------------------------------------------------------------------------

class ColocationTests(unittest.TestCase):
    def test_artifact_written_beside_the_spec_not_under_dot_servo(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)

            self.assertTrue((_out_dir(root) / "triage.json").is_file())
            self.assertTrue((_out_dir(root) / "triage.md").is_file())
            self.assertFalse((root / ".servo").exists())

    def test_triage_md_makes_the_human_gate_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)

            md = (_out_dir(root) / "triage.md").read_text()
            self.assertIn("proposal", md.lower())
            self.assertIn("confirm", md.lower())

    def test_triage_md_includes_the_ac_statement_text(self):
        """Usability nit: the human-facing table must carry the AC statement
        itself, not just its id/line — otherwise the human gate needs a
        cross-reference back to the spec to know what each row is about."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)

            md = (_out_dir(root) / "triage.md").read_text()
            for entry in MIXED_RESIDUAL:
                self.assertIn(entry["statement"], md)


class RelativeSourcePathColocationTests(unittest.TestCase):
    """Pins the CWD-dependent-path blocker fix (AC4). `source_spec_path` is a
    *display* path recorded verbatim by `oracle_plan.py` — typically
    repo-relative — so resolving it with `.resolve()` anchors it to the
    process's current working directory rather than the plan file's own
    on-disk location. This is the fixture gap that masked the blocker: every
    other test in this file writes an absolute `source_spec_path` that
    happens to already point at the real fixture file, so it never exercised
    the CWD-dependent branch."""

    def test_relative_display_path_colocates_beside_the_plan_not_the_cwd(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec_id = "042-demo"
            # The real on-disk layout: <spec_dir>/oracle/<spec_id>/checks.json.
            spec_dir = root / "docs" / "specs" / spec_id
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "spec.md").write_text(f"# Spec {spec_id}\n")

            plan_dir = spec_dir / "oracle" / spec_id
            plan_dir.mkdir(parents=True, exist_ok=True)
            plan = {
                "schema_version": 1,
                "spec_id": spec_id,
                # A repo-relative *display* path, exactly as oracle_plan.py
                # records it — never the fixture's own absolute path.
                "source_spec_path": f"docs/specs/{spec_id}/spec.md",
                "source_hash": "sha256:deadbeef",
                "planner_version": "0.1.0",
                "generated_at": "2026-01-01T00:00:00Z",
                "checks": [],
                "residual_judgment": MIXED_RESIDUAL,
            }
            plan_path = plan_dir / "checks.json"
            plan_path.write_text(json.dumps(plan, indent=2))

            # Invoke from a DIFFERENT cwd than the spec dir (the tmp root).
            # A naive `Path(source_spec_path).resolve()` would anchor to
            # this cwd and land the artifact at `<root>/eval/<spec_id>/`.
            proc = subprocess.run(
                [sys.executable, str(EVAL_AUTHORING), "triage", str(plan_path)],
                capture_output=True, text=True, cwd=str(root),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

            expected_out = spec_dir / "eval" / spec_id / "triage.json"
            self.assertTrue(expected_out.is_file())
            self.assertFalse((root / "eval").exists())


# ---------------------------------------------------------------------------
# AC5 — byte-identical re-run over the same plan
# ---------------------------------------------------------------------------

class DeterminismTests(unittest.TestCase):
    def test_rerun_over_same_plan_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            out = _out_dir(root) / "triage.json"

            proc1 = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc1.returncode, 0, proc1.stderr)
            first_bytes = out.read_bytes()

            proc2 = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc2.returncode, 0, proc2.stderr)
            second_bytes = out.read_bytes()

            self.assertEqual(first_bytes, second_bytes)

    def test_pure_build_triage_is_deterministic_across_calls(self):
        plan = {
            "spec_id": "x", "source_spec_path": "/tmp/x/spec.md",
            "residual_judgment": MIXED_RESIDUAL,
        }
        self.assertEqual(ea.build_triage(plan), ea.build_triage(plan))


# ---------------------------------------------------------------------------
# AC6 — malformed / missing plan: clean env-error exit, not a stack trace
# ---------------------------------------------------------------------------

class MalformedPlanTests(unittest.TestCase):
    def test_missing_plan_path_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proc = _run_cli(["triage", str(root / "does-not-exist.json")])
            self.assertEqual(proc.returncode, 2)
            self.assertIn("error:", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_malformed_json_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad = root / "bad.json"
            bad.write_text("not valid json {")
            proc = _run_cli(["triage", str(bad)])
            self.assertEqual(proc.returncode, 2)
            self.assertIn("error:", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_missing_residual_judgment_key_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad = root / "bad.json"
            bad.write_text(json.dumps({
                "spec_id": "x", "source_spec_path": str(root / "spec.md"),
            }))
            proc = _run_cli(["triage", str(bad)])
            self.assertEqual(proc.returncode, 2)
            self.assertIn("error:", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_directory_instead_of_plan_file_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            proc = _run_cli(["triage", str(root)])
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("Traceback", proc.stderr)


# ---------------------------------------------------------------------------
# Slice 008-02 (rubric-shaping) — AC1/AC3/AC4/AC5: the `rubric` subcommand
# ---------------------------------------------------------------------------

def _triage_then_shape(root: Path, ac_id: str = "AC-042-demo-1", archetype=None):
    """Shared fixture flow: write a mixed-residual plan, run `triage`, then
    run `rubric` for `ac_id`. Returns `(plan_path, rubric_dir)`."""
    plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
    proc = _run_cli(["triage", str(plan_path)])
    assert proc.returncode == 0, proc.stderr

    args = ["rubric", str(plan_path), "--ac", ac_id]
    if archetype is not None:
        args += ["--archetype", archetype]
    proc2 = _run_cli(args)
    assert proc2.returncode == 0, proc2.stderr

    rubric_dir = _out_dir(root) / ea._slug(ac_id)
    return plan_path, rubric_dir


class RubricArchetypeTests(unittest.TestCase):
    """AC1/AC3/AC6: each of the three archetypes produces a valid rubric
    (named criteria + an explicit scale + a judge prompt) and a well-formed
    `config.json` in the shared harness shape."""

    def test_each_archetype_produces_a_named_criteria_and_scale_rubric(self):
        for archetype in sorted(ea.ARCHETYPES):
            with self.subTest(archetype=archetype):
                with tempfile.TemporaryDirectory() as d:
                    root = Path(d)
                    _plan_path, rubric_dir = _triage_then_shape(root, archetype=archetype)

                    config = json.loads((rubric_dir / "config.json").read_text())
                    rubric_md = (rubric_dir / "rubric.md").read_text()

                    # Well-formed config.json (AC5's harness shape, checked
                    # in full by DefinitionHashRoundTripTests below).
                    self.assertEqual(config["archetype"], archetype)
                    for key in ("judge", "samples", "threshold", "rubric", "cases"):
                        self.assertIn(key, config)
                    self.assertEqual(config["cases"], [])
                    self.assertEqual(config["approval_status"], "draft")

                    # AC1: named criteria + an explicit scale in the rubric text.
                    self.assertIn("criteri", config["rubric"].lower())
                    self.assertIn("scale", config["rubric"].lower())

                    # AC4: rubric.md makes the human-gate nature explicit.
                    self.assertIn("proposal", rubric_md.lower())
                    self.assertIn("approve", rubric_md.lower())
                    self.assertIn(config["rubric"], rubric_md)

    def test_comparative_archetype_frames_proposed_vs_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = _triage_then_shape(root, archetype="comparative")
            config = json.loads((rubric_dir / "config.json").read_text())
            self.assertIn("proposed", config["rubric"].lower())
            self.assertIn("baseline", config["rubric"].lower())

    def test_multi_criteria_archetype_is_weighted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = _triage_then_shape(root, archetype="multi_criteria")
            config = json.loads((rubric_dir / "config.json").read_text())
            self.assertIn("weight", config["rubric"].lower())

    def test_default_archetype_is_single_dimension(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = _triage_then_shape(root)  # no --archetype
            config = json.loads((rubric_dir / "config.json").read_text())
            self.assertEqual(config["archetype"], "single_dimension")

    def test_unknown_archetype_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc2 = _run_cli(
                ["rubric", str(plan_path), "--ac", "AC-042-demo-1", "--archetype", "bogus"])
            self.assertNotEqual(proc2.returncode, 0)
            self.assertNotIn("Traceback", proc2.stderr)


class RubricEligibilityTests(unittest.TestCase):
    """AC1/AC2 (extended to 008-02): only an eval-able AC gets a rubric
    shaped for it — a human-residual AC or an unknown id is a clean
    env_error, never a silently-shaped rubric."""

    def test_human_residual_ac_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # AC-042-demo-2 is TASTE-reasoned -> human-residual (see MIXED_RESIDUAL).
            proc2 = _run_cli(["rubric", str(plan_path), "--ac", "AC-042-demo-2"])
            self.assertEqual(proc2.returncode, 2)
            self.assertIn("error:", proc2.stderr)
            self.assertNotIn("Traceback", proc2.stderr)

    def test_unknown_ac_id_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc2 = _run_cli(["rubric", str(plan_path), "--ac", "AC-does-not-exist"])
            self.assertEqual(proc2.returncode, 2)
            self.assertNotIn("Traceback", proc2.stderr)

    def test_missing_triage_json_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            # No `triage` run first — no triage.json to read.
            proc = _run_cli(["rubric", str(plan_path), "--ac", "AC-042-demo-1"])
            self.assertEqual(proc.returncode, 2)
            self.assertNotIn("Traceback", proc.stderr)


class RubricColocationTests(unittest.TestCase):
    """AC4: the rubric artifact is project-owned and colocated beside the
    spec, under the triage dir — never target/plugin state."""

    def test_rubric_dir_lives_under_the_eval_dir_not_dot_servo(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = _triage_then_shape(root)
            self.assertTrue((rubric_dir / "config.json").is_file())
            self.assertTrue((rubric_dir / "rubric.md").is_file())
            self.assertEqual(rubric_dir.parent, _out_dir(root))
            self.assertFalse((root / ".servo").exists())


# ---------------------------------------------------------------------------
# Slice 008-02 (rubric-shaping) — AC5: exact harness-shape fidelity
# ---------------------------------------------------------------------------

class DefinitionHashRoundTripTests(unittest.TestCase):
    """AC5: the emitted `config.json` round-trips through
    `fidelity_eval.definition_hash` (via `score.py`'s thin wrapper) with no
    reshaping — proving 008-04/spec-006 can freeze/compile it as-is."""

    def test_emitted_config_round_trips_through_definition_hash(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = _triage_then_shape(root)
            config = json.loads((rubric_dir / "config.json").read_text())

            digest = score.definition_hash(config)
            self.assertTrue(digest.startswith("sha256:"))
            # Deterministic: re-hashing the same config reproduces the digest.
            self.assertEqual(digest, score.definition_hash(config))

    def test_round_trip_holds_for_every_archetype(self):
        for archetype in sorted(ea.ARCHETYPES):
            with self.subTest(archetype=archetype):
                with tempfile.TemporaryDirectory() as d:
                    root = Path(d)
                    _plan_path, rubric_dir = _triage_then_shape(root, archetype=archetype)
                    config = json.loads((rubric_dir / "config.json").read_text())
                    self.assertTrue(score.definition_hash(config).startswith("sha256:"))


# ---------------------------------------------------------------------------
# Slice 008-02 (rubric-shaping) — AC2/AC6: the structured judge-output
# contract in `score.py`, offline (monkeypatched HTTP, no real judge call)
# ---------------------------------------------------------------------------

def _base_rubric_config():
    return {
        "schema_version": 1,
        "approval_status": "draft",
        "archetype": "single_dimension",
        "judge": {
            "model": "claude-sonnet-4-6", "transport": "api",
            "temperature": 0.0, "max_tokens": 1024,
        },
        "samples": {"n": 4, "k": 1.0, "delta": 0.03},
        "threshold": 0.8,
        "rubric": "Score, in [0,1], how well the candidate satisfies the criterion.",
        "cases": [],
    }


class StructuredJudgeOutputTests(unittest.TestCase):
    """AC2: the judge prompt targets `{score, reasoning, strengths,
    weaknesses}` JSON at low temperature; a malformed/unreachable/
    unparseable reply raises `EnvError` — never a silent `0.0`."""

    def setUp(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_prompt_requests_the_four_field_structured_output(self):
        prompt = score._prompt("candidate text", _base_rubric_config())
        self.assertIn("score", prompt)
        self.assertIn("reasoning", prompt)
        self.assertIn("strengths", prompt)
        self.assertIn("weaknesses", prompt)
        self.assertIn("candidate text", prompt)

    def test_wellformed_reply_parses_to_clamped_score_and_captures_the_rest(self):
        def fake_post(req, timeout, attempts=3):
            return {"content": [{"type": "text", "text": json.dumps({
                "score": 1.4, "reasoning": "solid", "strengths": ["a"], "weaknesses": ["b"],
            })}]}

        orig = score._post_with_retry
        score._post_with_retry = fake_post
        try:
            result = score._judge_api("candidate", _base_rubric_config())
        finally:
            score._post_with_retry = orig
        self.assertEqual(result["score"], 1.0)  # clamped from 1.4
        self.assertEqual(result["reasoning"], "solid")
        self.assertEqual(result["strengths"], ["a"])
        self.assertEqual(result["weaknesses"], ["b"])

    def test_low_temperature_request_body(self):
        captured = {}

        def fake_post(req, timeout, attempts=3):
            captured["body"] = json.loads(req.data)
            return {"content": [{"type": "text", "text": '{"score": 0.5}'}]}

        orig = score._post_with_retry
        score._post_with_retry = fake_post
        try:
            score._judge_api("candidate", _base_rubric_config())
        finally:
            score._post_with_retry = orig
        self.assertAlmostEqual(captured["body"]["temperature"], 0.0)

    def test_missing_score_field_is_env_error_not_zero(self):
        def fake_post(req, timeout, attempts=3):
            return {"content": [{"type": "text",
                                  "text": json.dumps({"reasoning": "no score here"})}]}
        orig = score._post_with_retry
        score._post_with_retry = fake_post
        try:
            with self.assertRaises(score.EnvError):
                score._judge_api("candidate", _base_rubric_config())
        finally:
            score._post_with_retry = orig

    def test_non_numeric_score_field_is_env_error_not_zero(self):
        def fake_post(req, timeout, attempts=3):
            return {"content": [{"type": "text", "text": json.dumps({"score": "not-a-number"})}]}
        orig = score._post_with_retry
        score._post_with_retry = fake_post
        try:
            with self.assertRaises(score.EnvError):
                score._judge_api("candidate", _base_rubric_config())
        finally:
            score._post_with_retry = orig

    def test_malformed_json_reply_is_env_error_not_zero(self):
        def fake_post(req, timeout, attempts=3):
            return {"content": [{"type": "text", "text": "I refuse to answer in JSON."}]}
        orig = score._post_with_retry
        score._post_with_retry = fake_post
        try:
            with self.assertRaises(score.EnvError):
                score._judge_api("candidate", _base_rubric_config())
        finally:
            score._post_with_retry = orig

    def test_unreachable_judge_is_env_error_not_zero(self):
        def fake_post(req, timeout, attempts=3):
            raise score.EnvError("judge request failed: retries exhausted")
        orig = score._post_with_retry
        score._post_with_retry = fake_post
        try:
            with self.assertRaises(score.EnvError):
                score._judge_api("candidate", _base_rubric_config())
        finally:
            score._post_with_retry = orig

    def test_unknown_transport_is_env_error(self):
        config = _base_rubric_config()
        config["judge"]["transport"] = "carrier-pigeon"
        with self.assertRaises(score.EnvError):
            score.judge("candidate", config)

    def test_api_missing_key_is_env_error(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with self.assertRaises(score.EnvError):
            score._judge_api("candidate", _base_rubric_config())

    def test_extract_json_from_noisy_reply(self):
        self.assertEqual(
            score._extract_json('Sure! {"score": 0.8, "reasoning": "x"} done'),
            '{"score": 0.8, "reasoning": "x"}')


if __name__ == "__main__":
    unittest.main()
