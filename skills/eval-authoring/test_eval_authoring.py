"""
AC verification tests for slices 008-01 (residual-triage), 008-02
(rubric-shaping), 008-03 (reference-set), and 008-04 (frozen-params-and-emit)
of `/servo:eval-authoring`.

Run from the repo root:
    python3 -m pytest skills/eval-authoring/test_eval_authoring.py -q

All of spec 008's tests accrete in this one file (see spec.md "Test
surface"). The 008-01 tranche (classification) is deterministic
(keyword/substring matching over the AC statement text, no LLM/network
call), so every fixture there is stable and offline. The 008-02 tranche
(rubric shaping + the judge path in `score.py`) is also offline: the judge
HTTP call is monkeypatched exactly as `skills/content-fidelity/
test_content_fidelity.py` does (no real API key / network access needed). The
008-03 tranche (the `dataset` subcommand + the constraint DSL + case-shape
validation) is pure/offline too — no judge call is exercised by scaffolding
or validating a dataset.

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

import copy
import importlib.util
import json
import os
import stat
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


# ---------------------------------------------------------------------------
# Slice 008-03 (reference-set) — helpers + fixtures
# ---------------------------------------------------------------------------

EXAMPLE_EDGE_SPEC_MD = """# Spec 042-demo

## Examples

- Summarize a 3-paragraph article about quarterly earnings faithfully.
- Summarize a product changelog without adding new claims.

## Edge cases

- An article with no clear thesis statement.
- A source document containing contradictory statements.

## Acceptance criteria

- AC-042-demo-1: The summary must not contradict any fact in the source document.
"""

NO_HEADINGS_SPEC_MD = """# Spec 042-demo

Just some prose with no Examples or Edge cases sections at all.
"""


def _triage_shape_and_dataset(root: Path, spec_text=None, ac_id: str = "AC-042-demo-1"):
    """Shared fixture flow (008-03): optionally seed a custom `spec.md`, then
    `triage` -> `rubric` -> `dataset` for `ac_id`. Returns `(plan_path,
    rubric_dir, dataset_proc)` — `dataset_proc` is the `dataset` subcommand's
    completed process, so tests can inspect its stdout/stderr/returncode."""
    if spec_text is not None:
        spec_dir = root / "042-demo"
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "spec.md").write_text(spec_text)
    plan_path, rubric_dir = _triage_then_shape(root, ac_id=ac_id)
    proc = _run_cli(["dataset", str(plan_path), "--ac", ac_id])
    return plan_path, rubric_dir, proc


def _dataset_case(case_id: str = "case-1", **overrides) -> dict:
    case = {
        "id": case_id,
        "category": "happy_path",
        "scenario": "A simple happy-path scenario.",
        "input": "Some input text.",
        "expected_output": {"description": "A description of the expected output."},
    }
    case.update(overrides)
    return case


# ---------------------------------------------------------------------------
# AC2 — the string-constraint DSL: parse + evaluate + malformed errors
# ---------------------------------------------------------------------------

class ConstraintDSLTests(unittest.TestCase):
    def test_equality_constraint_parses_and_evaluates(self):
        constraint = ea.parse_constraint("tone == warm")
        self.assertEqual(constraint, {"field": "tone", "op": "==", "value": "warm"})
        self.assertTrue(ea.evaluate_constraint(constraint, {"tone": "warm"}))
        self.assertFalse(ea.evaluate_constraint(constraint, {"tone": "cold"}))

    def test_gte_constraint_parses_and_evaluates_numerically(self):
        constraint = ea.parse_constraint("length >= 100")
        self.assertEqual(constraint, {"field": "length", "op": ">=", "value": 100.0})
        self.assertTrue(ea.evaluate_constraint(constraint, {"length": 142}))
        self.assertFalse(ea.evaluate_constraint(constraint, {"length": 50}))

    def test_lte_constraint_parses_and_evaluates_numerically(self):
        constraint = ea.parse_constraint("length <= 500")
        self.assertEqual(constraint["op"], "<=")
        self.assertTrue(ea.evaluate_constraint(constraint, {"length": 300}))
        self.assertFalse(ea.evaluate_constraint(constraint, {"length": 600}))

    def test_constraint_parses_with_no_surrounding_whitespace(self):
        constraint = ea.parse_constraint("length>=100")
        self.assertEqual(constraint, {"field": "length", "op": ">=", "value": 100.0})

    def test_malformed_constraint_unknown_operator_errors_cleanly(self):
        with self.assertRaises(ea.EnvError):
            ea.parse_constraint("length != 100")

    def test_malformed_constraint_missing_value_errors_cleanly(self):
        with self.assertRaises(ea.EnvError):
            ea.parse_constraint("length >=")

    def test_malformed_constraint_missing_operator_errors_cleanly(self):
        with self.assertRaises(ea.EnvError):
            ea.parse_constraint("just some free text")

    def test_malformed_constraint_empty_string_errors_cleanly(self):
        with self.assertRaises(ea.EnvError):
            ea.parse_constraint("")

    def test_evaluate_missing_field_is_a_clean_error(self):
        constraint = ea.parse_constraint("length >= 100")
        with self.assertRaises(ea.EnvError):
            ea.evaluate_constraint(constraint, {})

    def test_evaluate_non_numeric_actual_for_inequality_is_a_clean_error(self):
        constraint = ea.parse_constraint("length >= 100")
        with self.assertRaises(ea.EnvError):
            ea.evaluate_constraint(constraint, {"length": "not-a-number"})

    def test_equality_constraint_preserves_version_string_without_float_coercion(self):
        # craft nit: "==" must not float-coerce its value — "3.10" would
        # collapse to 3.1 and silently stop distinguishing from "3.1".
        constraint = ea.parse_constraint("version == 3.10")
        self.assertEqual(constraint, {"field": "version", "op": "==", "value": "3.10"})
        self.assertTrue(ea.evaluate_constraint(constraint, {"version": "3.10"}))
        self.assertFalse(ea.evaluate_constraint(constraint, {"version": "3.1"}))

    def test_gte_non_numeric_operand_is_rejected_at_parse_time(self):
        # craft nit: a >=/<= operand must be numeric, checked at
        # parse_constraint/validate_case time — fails at authoring, not
        # later at score time.
        with self.assertRaises(ea.EnvError):
            ea.parse_constraint("size >= large")

    def test_lte_non_numeric_operand_is_rejected_at_parse_time(self):
        with self.assertRaises(ea.EnvError):
            ea.parse_constraint("size <= large")


# ---------------------------------------------------------------------------
# AC2 / AC5 — per-case shape validation: ground-truthed + rubric-only, mixed
# ---------------------------------------------------------------------------

class CaseShapeValidationTests(unittest.TestCase):
    def test_valid_ground_truthed_case_passes(self):
        case = {
            "id": "case-1", "category": "happy_path",
            "scenario": "A scenario.", "input": "Some input.",
            "expected_output": {
                "description": "A description.",
                "constraints": ["length >= 10", "tone == warm"],
            },
        }
        ea.validate_case(case, 0)  # no exception

    def test_valid_rubric_only_case_passes_with_no_expected_output(self):
        """AC5: a rubric-only judged case carries no hard label at all."""
        case = {
            "id": "case-2", "category": "edge_case",
            "scenario": "An edge scenario.", "input": "Some edge input.",
        }
        ea.validate_case(case, 0)  # no exception

    def test_mixed_dataset_validates(self):
        """AC5: ground-truthed and rubric-only cases coexist in one dataset."""
        cases = [
            {
                "id": "case-1", "category": "happy_path",
                "scenario": "A ground-truthed scenario.", "input": "Input A.",
                "expected_output": {"description": "Expected A.", "constraints": ["length >= 5"]},
            },
            {
                "id": "case-2", "category": "edge_case",
                "scenario": "A rubric-only scenario.", "input": "Input B.",
            },
        ]
        ea.validate_dataset(cases)  # no exception
        self.assertIn("expected_output", cases[0])
        self.assertNotIn("expected_output", cases[1])

    def test_invalid_category_is_a_clean_error(self):
        case = {"id": "case-1", "category": "bogus", "scenario": "s", "input": "i"}
        with self.assertRaises(ea.EnvError):
            ea.validate_case(case, 0)

    def test_missing_required_field_is_a_clean_error(self):
        case = {"id": "case-1", "category": "happy_path", "scenario": "s"}  # no `input`
        with self.assertRaises(ea.EnvError):
            ea.validate_case(case, 0)

    def test_malformed_constraint_inside_a_case_is_a_clean_error(self):
        case = {
            "id": "case-1", "category": "happy_path", "scenario": "s", "input": "i",
            "expected_output": {"description": "d", "constraints": ["length !! 100"]},
        }
        with self.assertRaises(ea.EnvError):
            ea.validate_case(case, 0)

    def test_duplicate_ids_are_a_clean_error(self):
        cases = [
            {"id": "case-1", "category": "happy_path", "scenario": "s1", "input": "i1"},
            {"id": "case-1", "category": "edge_case", "scenario": "s2", "input": "i2"},
        ]
        with self.assertRaises(ea.EnvError):
            ea.validate_dataset(cases)

    def test_baseline_field_carries_through_for_the_comparative_archetype(self):
        """008-02's carry-forward: the shape carries what 008-04's widened
        comparative scoring will need, without scoring anything here."""
        case = {
            "id": "case-1", "category": "happy_path", "scenario": "s", "input": "i",
            "baseline": "A baseline/reference text for PROPOSED-vs-BASELINE.",
        }
        ea.validate_case(case, 0)  # no exception


# ---------------------------------------------------------------------------
# AC1 — scaffolding: seeded from the spec's own Examples / Edge cases text
# ---------------------------------------------------------------------------

class DatasetScaffoldFromSpecTests(unittest.TestCase):
    def test_cases_seeded_from_examples_and_edge_cases_verbatim(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir, proc = _triage_shape_and_dataset(
                root, spec_text=EXAMPLE_EDGE_SPEC_MD)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            config = json.loads((rubric_dir / "config.json").read_text())
            cases = config["cases"]
            self.assertEqual(len(cases), 4)

            happy = [c for c in cases if c["category"] == "happy_path"]
            edge = [c for c in cases if c["category"] == "edge_case"]
            self.assertEqual(len(happy), 2)
            self.assertEqual(len(edge), 2)

            self.assertEqual(
                {c["scenario"] for c in happy},
                {
                    "Summarize a 3-paragraph article about quarterly earnings faithfully.",
                    "Summarize a product changelog without adding new claims.",
                },
            )
            self.assertEqual(
                {c["scenario"] for c in edge},
                {
                    "An article with no clear thesis statement.",
                    "A source document containing contradictory statements.",
                },
            )
            # Never invents an expected_output for spec-sourced examples/edge
            # cases — verbatim scenario/input text only (AC1's "never invent
            # case content or labels").
            for c in cases:
                self.assertNotIn("expected_output", c)
                self.assertEqual(c["scenario"], c["input"])


class DatasetPlaceholderScaffoldTests(unittest.TestCase):
    def test_no_headings_scaffolds_one_labeled_placeholder_per_category(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir, proc = _triage_shape_and_dataset(
                root, spec_text=NO_HEADINGS_SPEC_MD)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            config = json.loads((rubric_dir / "config.json").read_text())
            cases = config["cases"]
            self.assertEqual(len(cases), 3)
            self.assertEqual(
                {c["category"] for c in cases}, {"happy_path", "edge_case", "skip_case"})
            for c in cases:
                self.assertIn("EDIT ME", c["scenario"])
                self.assertIn("EDIT ME", c["input"])


# ---------------------------------------------------------------------------
# AC3 — minimum-viable-size guidance: warns, never autofills
# ---------------------------------------------------------------------------

class DatasetMinSizeWarningTests(unittest.TestCase):
    def test_under_floor_dataset_warns_without_autofill(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir, proc = _triage_shape_and_dataset(
                root, spec_text=EXAMPLE_EDGE_SPEC_MD)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("warning:", proc.stdout)
            self.assertIn("12", proc.stdout)

            config = json.loads((rubric_dir / "config.json").read_text())
            # Never autofilled toward the floor: exactly the 4 spec-sourced
            # cases, not padded with invented ones to reach 12.
            self.assertEqual(len(config["cases"]), 4)

    def test_floor_met_dataset_has_no_warning(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path, rubric_dir = _triage_then_shape(root)
            config_path = rubric_dir / "config.json"
            config = json.loads(config_path.read_text())
            config["cases"] = [_dataset_case(f"case-{i}") for i in range(ea.MIN_DATASET_SIZE)]
            config_path.write_text(json.dumps(config, indent=2) + "\n")

            proc = _run_cli(["dataset", str(plan_path), "--ac", "AC-042-demo-1"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("warning:", proc.stdout)


class DatasetNoOverwriteTests(unittest.TestCase):
    def test_rerun_never_overwrites_already_scaffolded_or_edited_cases(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path, rubric_dir, proc1 = _triage_shape_and_dataset(
                root, spec_text=EXAMPLE_EDGE_SPEC_MD)
            self.assertEqual(proc1.returncode, 0, proc1.stderr)
            self.assertIn("scaffolded", proc1.stdout)

            config_path = rubric_dir / "config.json"
            config = json.loads(config_path.read_text())
            # Simulate a human edit: add a real, hand-authored case.
            config["cases"].append(_dataset_case(
                "case-hand-1", scenario="A real hand-authored scenario.",
                input="Real input text.",
                expected_output={"description": "Real expected output."}))
            config_path.write_text(json.dumps(config, indent=2) + "\n")
            before = json.loads(config_path.read_text())["cases"]

            proc2 = _run_cli(["dataset", str(plan_path), "--ac", "AC-042-demo-1"])
            self.assertEqual(proc2.returncode, 0, proc2.stderr)
            self.assertIn("left", proc2.stdout)

            after = json.loads(config_path.read_text())["cases"]
            self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# AC4 — freeze integration: a case edit trips stale / changes definition_hash
# ---------------------------------------------------------------------------

class DatasetFreezeTests(unittest.TestCase):
    def test_case_edit_changes_definition_hash(self):
        config = _base_rubric_config()
        config["cases"] = [
            _dataset_case("case-1"),
            _dataset_case("case-2", category="edge_case", scenario="An edge scenario.",
                          input="Edge input.", expected_output=None),
        ]
        digest1 = score.definition_hash(config)

        edited = copy.deepcopy(config)
        edited["cases"][0]["input"] = "Changed input text."
        digest2 = score.definition_hash(edited)

        self.assertNotEqual(digest1, digest2)
        # Deterministic: re-hashing the unchanged config reproduces digest1.
        self.assertEqual(digest1, score.definition_hash(config))

    def test_baseline_field_is_pinned_by_value(self):
        config = _base_rubric_config()
        config["cases"] = [_dataset_case("case-1", baseline="Baseline text A.")]
        digest1 = score.definition_hash(config)

        edited = copy.deepcopy(config)
        edited["cases"][0]["baseline"] = "Baseline text B."
        digest2 = score.definition_hash(edited)

        self.assertNotEqual(digest1, digest2)

    def test_frozen_config_trips_stale_on_case_edit(self):
        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            config = _base_rubric_config()
            config["cases"] = [_dataset_case("case-1")]
            config["approval_status"] = "approved"
            config["approved_content_hash"] = score.definition_hash(config)
            config["hashes"] = score.artifact_hashes(config, base_dir)

            score.validate_freeze(config, base_dir)  # approved + matching -> no exception

            config["cases"][0]["expected_output"]["description"] = "A DIFFERENT expected output."
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, base_dir)


# ---------------------------------------------------------------------------
# AC6 — the dataset composite: a mixed labeled + rubric-only dataset scores
# end-to-end (fake judge scores + fake actuals for the constraint DSL, same
# offline hook idiom as content-fidelity's `_FAKE_SCORES_ENV`).
# ---------------------------------------------------------------------------

class DatasetCompositeScoreTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop(score._FAKE_SCORES_ENV, None)
        os.environ.pop(score._FAKE_ACTUALS_ENV, None)

    def tearDown(self):
        os.environ.pop(score._FAKE_SCORES_ENV, None)
        os.environ.pop(score._FAKE_ACTUALS_ENV, None)

    def _write_config(self, base_dir: Path, cases: list, n: int = 1, approve: bool = True) -> dict:
        """`approve=True` (the default) freezes the config before writing it
        — 008-04 AC5 wires `validate_freeze` into `score()` (see
        `test_score_enforces_freeze_stale_on_unapproved_config` below), so
        every test in this class that expects `score()` to actually run the
        composite needs an approved, hashed config, not a bare draft."""
        config = _base_rubric_config()
        config["samples"] = {"n": n, "k": 1.0, "delta": 0.03}
        config["cases"] = cases
        if approve:
            config["hashes"] = score.artifact_hashes(config, base_dir)
            config["approved_content_hash"] = score.definition_hash(config)
            config["approval_status"] = "approved"
            config["approved_at"] = "2026-01-01T00:00:00Z"
        (base_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        return config

    def test_mixed_labeled_and_rubric_only_dataset_scores_end_to_end(self):
        """AC6: a mixed labeled + rubric-only dataset, scored end-to-end,
        composes to a float in [0,1] — and, with n=1 (stderr 0, so the
        lower bound equals the sample itself), the composite is exactly the
        unweighted mean of the three *scored* cases (`skip_case` excluded
        from the denominator — see the next test for a dedicated check)."""
        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            self._write_config(base_dir, [
                _dataset_case("case-happy-1", expected_output={
                    "description": "A ground-truthed description.",
                    "constraints": ["length >= 100"],
                }),
                _dataset_case("case-rubric-1", category="edge_case", expected_output=None),
                _dataset_case("case-skip-1", category="skip_case", expected_output=None),
            ])
            os.environ[score._FAKE_SCORES_ENV] = json.dumps({
                "case-happy-1": [0.9], "case-rubric-1": [0.8],
                # Deliberately no "case-skip-1" entry: if the composite tried
                # to score the skip_case it would KeyError -> EnvError, so a
                # clean pass here is itself proof the skip_case was excluded.
            })
            os.environ[score._FAKE_ACTUALS_ENV] = json.dumps({"case-happy-1": {"length": 142}})

            composite = score.score(base_dir)
            self.assertGreaterEqual(composite, 0.0)
            self.assertLessEqual(composite, 1.0)
            self.assertAlmostEqual(composite, (0.9 + 0.8) / 2, places=6)

    def test_skip_case_is_excluded_from_the_denominator(self):
        """A skip_case sitting alongside scored cases must not change the
        composite versus the same dataset with the skip_case simply
        absent — direct proof it never enters the weighted mean."""
        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            self._write_config(base_dir, [
                _dataset_case("case-a", expected_output=None),
                _dataset_case("case-b", category="edge_case", expected_output=None),
            ])
            os.environ[score._FAKE_SCORES_ENV] = json.dumps(
                {"case-a": [0.9], "case-b": [0.7]})
            without_skip = score.score(base_dir)

        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            self._write_config(base_dir, [
                _dataset_case("case-a", expected_output=None),
                _dataset_case("case-b", category="edge_case", expected_output=None),
                _dataset_case("case-skip", category="skip_case", expected_output=None),
            ])
            os.environ[score._FAKE_SCORES_ENV] = json.dumps(
                {"case-a": [0.9], "case-b": [0.7]})  # no "case-skip" entry
            with_skip = score.score(base_dir)

        self.assertEqual(without_skip, with_skip)

    def test_failed_hard_constraint_changes_the_composite(self):
        """AC2's composition rule: a failed hard constraint zeroes that
        case's contribution, so the composite drops versus the same dataset
        with the constraint passing."""
        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            self._write_config(base_dir, [
                _dataset_case("case-a", expected_output={
                    "description": "d", "constraints": ["length >= 100"]}),
                _dataset_case("case-b", category="edge_case", expected_output=None),
            ])
            os.environ[score._FAKE_SCORES_ENV] = json.dumps(
                {"case-a": [0.9], "case-b": [0.9]})

            os.environ[score._FAKE_ACTUALS_ENV] = json.dumps({"case-a": {"length": 142}})
            passing = score.score(base_dir)
            self.assertAlmostEqual(passing, 0.9)

            os.environ[score._FAKE_ACTUALS_ENV] = json.dumps({"case-a": {"length": 10}})
            failing = score.score(base_dir)
            self.assertAlmostEqual(failing, 0.45)  # (0.0*1 + 0.9*1) / 2
            self.assertLess(failing, passing)

    def test_missing_fake_score_for_a_scored_case_is_env_error_not_zero(self):
        """Honesty (ADR-0005): a missing judged sample raises EnvError, it
        never silently scores 0.0."""
        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            self._write_config(base_dir, [
                _dataset_case("case-a", expected_output=None),
                _dataset_case("case-b", category="edge_case", expected_output=None),
            ])
            os.environ[score._FAKE_SCORES_ENV] = json.dumps({"case-a": [0.9]})
            # "case-b" is missing entirely.
            with self.assertRaises(score.EnvError):
                score.score(base_dir)

    def test_live_path_without_candidate_gather_is_env_error_not_zero(self):
        """Honesty (ADR-0005): with no fake-scores hook and no real
        candidate-gather yet (008-04), a live score() call raises EnvError
        rather than silently scoring a placeholder."""
        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            self._write_config(base_dir, [_dataset_case("case-a", expected_output=None)])
            with self.assertRaises(score.EnvError):
                score.score(base_dir)

    def test_score_enforces_freeze_stale_on_unapproved_config(self):
        """008-04 AC5 (resolves the 008-03 carry-forward): `score()` now
        calls `validate_freeze` first, so a still-`draft` (unapproved)
        config.json refuses as `StaleError` rather than silently scoring —
        the flip side of `test_score_does_not_enforce_freeze_on_a_draft_config`
        this slice supersedes."""
        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            self._write_config(
                base_dir, [_dataset_case("case-a", expected_output=None)], approve=False)
            config = json.loads((base_dir / "config.json").read_text())
            self.assertEqual(config["approval_status"], "draft")
            os.environ[score._FAKE_SCORES_ENV] = json.dumps({"case-a": [0.8]})
            with self.assertRaises(score.StaleError):
                score.score(base_dir)


# ---------------------------------------------------------------------------
# 008-04 carry-forward: guard the per-case `weight` parse (008-03 flagged
# this — a hand-edited non-numeric weight must raise the module's own clean
# `EnvError`, not a bare `ValueError`). Also closes the listed coverage
# follow-ups: mixed per-case weights, and the `total_w <= 0` guard.
# ---------------------------------------------------------------------------

class WeightGuardTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop(score._FAKE_SCORES_ENV, None)

    def tearDown(self):
        os.environ.pop(score._FAKE_SCORES_ENV, None)

    def _write_config(self, base_dir: Path, cases: list, n: int = 1) -> None:
        config = _base_rubric_config()
        config["samples"] = {"n": n, "k": 1.0, "delta": 0.03}
        config["cases"] = cases
        config["hashes"] = score.artifact_hashes(config, base_dir)
        config["approved_content_hash"] = score.definition_hash(config)
        config["approval_status"] = "approved"
        config["approved_at"] = "2026-01-01T00:00:00Z"
        (base_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")

    def test_non_numeric_weight_is_a_clean_env_error_not_a_bare_value_error(self):
        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            self._write_config(base_dir, [
                _dataset_case("case-a", expected_output=None, weight="not-a-number"),
            ])
            os.environ[score._FAKE_SCORES_ENV] = json.dumps({"case-a": [0.9]})
            with self.assertRaises(score.EnvError):
                score.score(base_dir)

    def test_mixed_case_weights_combine_into_a_weighted_mean(self):
        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            self._write_config(base_dir, [
                _dataset_case("case-a", expected_output=None, weight=3.0),
                _dataset_case("case-b", category="edge_case", expected_output=None, weight=1.0),
            ])
            os.environ[score._FAKE_SCORES_ENV] = json.dumps(
                {"case-a": [0.9], "case-b": [0.1]})
            composite = score.score(base_dir)
            # weighted mean: (0.9*3 + 0.1*1) / 4 = 0.7
            self.assertAlmostEqual(composite, 0.7, places=6)

    def test_zero_total_weight_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            base_dir = Path(d)
            self._write_config(base_dir, [
                _dataset_case("case-a", expected_output=None, weight=0.0),
                _dataset_case("case-b", category="edge_case", expected_output=None, weight=0.0),
            ])
            os.environ[score._FAKE_SCORES_ENV] = json.dumps(
                {"case-a": [0.9], "case-b": [0.5]})
            with self.assertRaises(score.EnvError):
                score.score(base_dir)


# ---------------------------------------------------------------------------
# 008-04 carry-forward: the constraint DSL vendored into score.py (so a
# standalone-installed score.py has zero cross-file dependency beyond
# fidelity_eval.py) must stay behaviourally identical to eval_authoring.py's
# canonical copy (mirrors the module's own RESIDUAL_REASON_* drift guard).
# ---------------------------------------------------------------------------

class VendoredConstraintDSLDriftGuardTests(unittest.TestCase):
    def test_vendored_parse_constraint_matches_canonical(self):
        for text in ("tone == warm", "length >= 100", "length <= 500", "version == 3.10"):
            with self.subTest(text=text):
                self.assertEqual(ea.parse_constraint(text), score.parse_constraint(text))

    def test_vendored_evaluate_constraint_matches_canonical(self):
        constraint_text = "length >= 100"
        canonical = ea.parse_constraint(constraint_text)
        vendored = score.parse_constraint(constraint_text)
        for actuals in ({"length": 142}, {"length": 50}):
            with self.subTest(actuals=actuals):
                self.assertEqual(
                    ea.evaluate_constraint(canonical, actuals),
                    score.evaluate_constraint(vendored, actuals),
                )

    def test_vendored_malformed_constraint_also_errors_cleanly(self):
        with self.assertRaises(score.EnvError):
            score.parse_constraint("length !! 100")


# ---------------------------------------------------------------------------
# CLI error / colocation coverage
# ---------------------------------------------------------------------------

class DatasetCLIErrorTests(unittest.TestCase):
    def test_dataset_before_rubric_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            # No `rubric` run first -> no config.json to grow.
            proc2 = _run_cli(["dataset", str(plan_path), "--ac", "AC-042-demo-1"])
            self.assertEqual(proc2.returncode, 2)
            self.assertIn("error:", proc2.stderr)
            self.assertNotIn("Traceback", proc2.stderr)


class DatasetColocationTests(unittest.TestCase):
    def test_dataset_artifacts_live_beside_the_rubric_not_dot_servo(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir, proc = _triage_shape_and_dataset(root)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((rubric_dir / "config.json").is_file())
            self.assertTrue((rubric_dir / "dataset.md").is_file())
            self.assertFalse((root / ".servo").exists())


# ---------------------------------------------------------------------------
# Slice 008-04 (frozen-params-and-emit) — AC1: the `params` subcommand
# ---------------------------------------------------------------------------

class ParamsDefaultsTests(unittest.TestCase):
    """AC1: a sane provisional default already applied by `rubric`; accepting
    every default (no override flags) leaves the config unchanged, and the
    guidance prints a one-line plain-language trade-off note per knob."""

    def test_accepting_defaults_leaves_config_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path, rubric_dir = _triage_then_shape(root)
            before = json.loads((rubric_dir / "config.json").read_text())

            proc = _run_cli(["params", str(plan_path), "--ac", "AC-042-demo-1"])
            self.assertEqual(proc.returncode, 0, proc.stderr)

            after = json.loads((rubric_dir / "config.json").read_text())
            self.assertEqual(before["judge"], after["judge"])
            self.assertEqual(before["samples"], after["samples"])
            self.assertEqual(before["threshold"], after["threshold"])

    def test_guidance_covers_every_knob_with_a_tradeoff_note(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path, _rubric_dir = _triage_then_shape(root)
            proc = _run_cli(["params", str(plan_path), "--ac", "AC-042-demo-1"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout.lower()
            for token in ("n =", "delta", "threshold", "model", "temperature"):
                self.assertIn(token, out)
            # plain-language trade-off language (ADR-0005 knobs), not just numbers
            self.assertIn("false-fail", out)

    def test_params_before_rubric_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc2 = _run_cli(["params", str(plan_path), "--ac", "AC-042-demo-1"])
            self.assertEqual(proc2.returncode, 2)
            self.assertIn("error:", proc2.stderr)
            self.assertNotIn("Traceback", proc2.stderr)


class ParamsOverrideTests(unittest.TestCase):
    """AC1: n/delta/threshold/judge model+params are settable, not just
    confirmable."""

    def test_overrides_are_written_into_config_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path, rubric_dir = _triage_then_shape(root)
            proc = _run_cli([
                "params", str(plan_path), "--ac", "AC-042-demo-1",
                "--n", "6", "--delta", "0.05", "--threshold", "0.9",
                "--model", "claude-haiku-4-5-20251001", "--temperature", "0.2",
                "--max-tokens", "2048", "--transport", "cli",
            ])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            config = json.loads((rubric_dir / "config.json").read_text())
            self.assertEqual(config["samples"]["n"], 6)
            self.assertEqual(config["samples"]["delta"], 0.05)
            self.assertEqual(config["threshold"], 0.9)
            self.assertEqual(config["judge"]["model"], "claude-haiku-4-5-20251001")
            self.assertEqual(config["judge"]["temperature"], 0.2)
            self.assertEqual(config["judge"]["max_tokens"], 2048)
            self.assertEqual(config["judge"]["transport"], "cli")


# ---------------------------------------------------------------------------
# Slice 008-04 — AC2/AC3/AC4: `emit` (freeze [+ install]) — the human-
# approval gate. Architecture note: there is no spec-006 eval-family compile
# step (verified against the current codebase) — the authoring skill
# self-freezes + self-installs the score_<name> component via the shared
# fidelity_eval.py splice machinery, exactly like the two shipped presets
# (content-fidelity / design-eval). `emit` with no --target freezes only
# (AC4's "approved, compilable definition" stopping point); `emit --target`
# additionally installs (never runs) the component (AC2/AC3).
# ---------------------------------------------------------------------------

class EmitFreezeTests(unittest.TestCase):
    def test_emit_without_target_freezes_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path, rubric_dir, proc = _triage_shape_and_dataset(
                root, spec_text=NO_HEADINGS_SPEC_MD)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            proc2 = _run_cli(["emit", str(plan_path), "--ac", "AC-042-demo-1"])
            self.assertEqual(proc2.returncode, 0, proc2.stderr)

            config = json.loads((rubric_dir / "config.json").read_text())
            self.assertEqual(config["approval_status"], "approved")
            self.assertIn("approved_content_hash", config)
            self.assertIn("hashes", config)
            score.validate_freeze(config, rubric_dir)  # no raise

    def test_emit_refuses_an_empty_dataset(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path, _rubric_dir = _triage_then_shape(root)  # no `dataset` run -> cases == []
            proc = _run_cli(["emit", str(plan_path), "--ac", "AC-042-demo-1"])
            self.assertEqual(proc.returncode, 2)
            self.assertIn("error:", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_emit_before_rubric_is_a_clean_env_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan_path = _make_plan(root, residual=MIXED_RESIDUAL)
            proc = _run_cli(["triage", str(plan_path)])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc2 = _run_cli(["emit", str(plan_path), "--ac", "AC-042-demo-1"])
            self.assertEqual(proc2.returncode, 2)
            self.assertNotIn("Traceback", proc2.stderr)


class ComponentNameCollisionTests(unittest.TestCase):
    """008-03 carry-forward: distinct AC ids across different specs must not
    collide to the same `score_<name>` component/dir."""

    def test_same_ac_id_across_different_specs_gets_distinct_component_names(self):
        name_a = ea.component_name("008-spec-a", "AC-1")
        name_b = ea.component_name("008-spec-b", "AC-1")
        self.assertNotEqual(name_a, name_b)

    def test_component_name_is_a_shell_safe_function_suffix(self):
        name = ea.component_name("008-eval-authoring", "AC-042-demo-1")
        self.assertRegex(f"score_{name}", r"^[A-Za-z_][A-Za-z0-9_]*$")


ORACLE_STUB = (
    "#!/usr/bin/env bash\nset -euo pipefail\nTHRESHOLD=\"${THRESHOLD:-0.5}\"\n"
    "COMPONENTS=(\n  \"vitest:1.0\"\n)\n\nweighted_sum=\"0\"\ntotal_weight=\"0\"\n"
)


def _make_stub_target(target: Path) -> None:
    """A minimal (non-runnable) oracle.sh + manifest, sufficient to exercise
    the splice/registration mechanics — mirrors content-fidelity's own
    `InstallTests._target()` fixture."""
    (target / ".servo").mkdir(parents=True, exist_ok=True)
    (target / "oracle.sh").write_text(ORACLE_STUB)
    (target / ".servo" / "install.json").write_text(json.dumps({"components": ["vitest"]}))


class InstallUninstallRoundTripTests(unittest.TestCase):
    """AC6: the freeze/install/uninstall round-trip is idempotent and
    baseline components stay untouched (mirrors content-fidelity's own
    InstallTests)."""

    def test_emit_with_target_freezes_and_installs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target_dir = Path(d) / "target"
            _make_stub_target(target_dir)
            plan_path, _rubric_dir, proc = _triage_shape_and_dataset(
                root, spec_text=NO_HEADINGS_SPEC_MD)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            proc2 = _run_cli([
                "emit", str(plan_path), "--ac", "AC-042-demo-1",
                "--target", str(target_dir), "--weight", "2.0",
            ])
            self.assertEqual(proc2.returncode, 0, proc2.stderr)

            component = ea.component_name("042-demo", "AC-042-demo-1")
            text = (target_dir / "oracle.sh").read_text()
            self.assertIn(f"# SEED:start {component}", text)
            self.assertIn(f"score_{component}()", text)
            self.assertIn(f'"{component}:2.0"', text)
            self.assertIn('"vitest:1.0"', text)  # baseline untouched

            comp_dir = target_dir / ".servo" / component
            self.assertTrue((comp_dir / "score.py").is_file())
            self.assertTrue((comp_dir / "fidelity_eval.py").is_file())
            frozen_config = json.loads((comp_dir / "config.json").read_text())
            self.assertEqual(frozen_config["approval_status"], "approved")

            manifest = json.loads((target_dir / ".servo" / "install.json").read_text())
            self.assertIn(component, manifest["components"])

    def test_reemit_with_target_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target_dir = Path(d) / "target"
            _make_stub_target(target_dir)
            plan_path, _rubric_dir, proc = _triage_shape_and_dataset(
                root, spec_text=NO_HEADINGS_SPEC_MD)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            for weight in ("1.0", "3.0"):
                proc2 = _run_cli([
                    "emit", str(plan_path), "--ac", "AC-042-demo-1",
                    "--target", str(target_dir), "--weight", weight,
                ])
                self.assertEqual(proc2.returncode, 0, proc2.stderr)

            component = ea.component_name("042-demo", "AC-042-demo-1")
            text = (target_dir / "oracle.sh").read_text()
            self.assertEqual(text.count(f"# SEED:start {component}"), 1)
            self.assertIn(f'"{component}:3.0"', text)
            self.assertNotIn(f'"{component}:1.0"', text)

    def test_uninstall_removes_component_keeps_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target_dir = Path(d) / "target"
            _make_stub_target(target_dir)
            plan_path, _rubric_dir, proc = _triage_shape_and_dataset(
                root, spec_text=NO_HEADINGS_SPEC_MD)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            proc2 = _run_cli([
                "emit", str(plan_path), "--ac", "AC-042-demo-1", "--target", str(target_dir),
            ])
            self.assertEqual(proc2.returncode, 0, proc2.stderr)

            proc3 = _run_cli([
                "uninstall", str(plan_path), "--ac", "AC-042-demo-1",
                "--target", str(target_dir),
            ])
            self.assertEqual(proc3.returncode, 0, proc3.stderr)

            component = ea.component_name("042-demo", "AC-042-demo-1")
            text = (target_dir / "oracle.sh").read_text()
            self.assertNotIn(component, text)
            self.assertIn('"vitest:1.0"', text)
            manifest = json.loads((target_dir / ".servo" / "install.json").read_text())
            self.assertNotIn(component, manifest["components"])
            self.assertIn("vitest", manifest["components"])

    def test_install_refuses_an_unapproved_config(self):
        """Defensive unit coverage of the approval-gate guard: the CLI's
        `emit --target` always freezes before installing, so this state is
        unreachable via the CLI — verified directly against
        `install_component`."""
        with tempfile.TemporaryDirectory() as d:
            target_dir = Path(d) / "target"
            _make_stub_target(target_dir)
            draft_config = _base_rubric_config()
            draft_config["cases"] = [_dataset_case("case-1")]
            score_mod = ea._load_score()
            with self.assertRaises(ea.EnvError):
                ea.install_component(draft_config, "some_component", target_dir, 1.0, score_mod)


# ---------------------------------------------------------------------------
# Slice 008-04 — AC5: a rubric / dataset / param change after `emit` refuses
# as stale (the `validate_freeze` carry-forward this slice wires into
# `score()`) — mirrors content-fidelity's own "changed X is stale" battery.
# ---------------------------------------------------------------------------

class EmitStaleOnChangeTests(unittest.TestCase):
    def _emit(self, root: Path, ac_id: str = "AC-042-demo-1"):
        plan_path, rubric_dir, proc = _triage_shape_and_dataset(
            root, spec_text=NO_HEADINGS_SPEC_MD, ac_id=ac_id)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc2 = _run_cli(["emit", str(plan_path), "--ac", ac_id])
        self.assertEqual(proc2.returncode, 0, proc2.stderr)
        return plan_path, rubric_dir

    def test_changed_rubric_is_stale(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = self._emit(root)
            config_path = rubric_dir / "config.json"
            config = json.loads(config_path.read_text())
            config["rubric"] = "a completely different rubric"
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, rubric_dir)

    def test_changed_samples_n_is_stale(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = self._emit(root)
            config = json.loads((rubric_dir / "config.json").read_text())
            config["samples"]["n"] = config["samples"]["n"] + 4
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, rubric_dir)

    def test_changed_delta_is_stale(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = self._emit(root)
            config = json.loads((rubric_dir / "config.json").read_text())
            config["samples"]["delta"] = config["samples"]["delta"] + 0.5
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, rubric_dir)

    def test_changed_threshold_is_stale(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = self._emit(root)
            config = json.loads((rubric_dir / "config.json").read_text())
            config["threshold"] = 0.99
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, rubric_dir)

    def test_changed_judge_model_is_stale(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = self._emit(root)
            config = json.loads((rubric_dir / "config.json").read_text())
            config["judge"]["model"] = "a-different-model"
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, rubric_dir)

    def test_changed_case_is_stale(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _plan_path, rubric_dir = self._emit(root)
            config = json.loads((rubric_dir / "config.json").read_text())
            config["cases"][0]["scenario"] = "a completely different scenario"
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, rubric_dir)

    def test_stale_config_exits_2_via_score_py_main_not_zero(self):
        """The full CLI contract (mirrors content-fidelity's own
        `test_stale_exits_2_not_zero`): a stale config's installed score.py
        never prints a composite, exits 2, and says "stale" on stderr."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target_dir = Path(d) / "target"
            _make_stub_target(target_dir)
            plan_path, _rubric_dir, proc = _triage_shape_and_dataset(
                root, spec_text=NO_HEADINGS_SPEC_MD)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc2 = _run_cli([
                "emit", str(plan_path), "--ac", "AC-042-demo-1", "--target", str(target_dir),
            ])
            self.assertEqual(proc2.returncode, 0, proc2.stderr)

            component = ea.component_name("042-demo", "AC-042-demo-1")
            comp_dir = target_dir / ".servo" / component
            config_path = comp_dir / "config.json"
            config = json.loads(config_path.read_text())
            config["threshold"] = 0.999  # tamper post-install, without re-emitting
            config_path.write_text(json.dumps(config, indent=2) + "\n")

            proc3 = subprocess.run(
                [sys.executable, str(comp_dir / "score.py"), str(target_dir)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc3.returncode, 2, proc3.stderr)
            self.assertEqual(proc3.stdout.strip(), "")  # never a 0.0 on the stale path
            self.assertIn("stale", proc3.stderr.lower())


# ---------------------------------------------------------------------------
# Slice 008-04 — AC6: the emitted+installed component runs under gate.py's
# real ADR-0002 0/1/2 contract (a real gate.py invocation over the genuine
# oracle.sh driver loop, not a stub).
# ---------------------------------------------------------------------------

class GateContractTests(unittest.TestCase):
    GATE = REPO_ROOT / "skills" / "quality-gate" / "gate.py"
    ORACLE_TEMPLATE = REPO_ROOT / "templates" / "oracle.sh.template"

    def setUp(self):
        os.environ.pop(score._FAKE_SCORES_ENV, None)

    def tearDown(self):
        os.environ.pop(score._FAKE_SCORES_ENV, None)

    def _scaffold_bare_target(self, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        (target / ".servo").mkdir(parents=True, exist_ok=True)
        (target / ".servo" / "install.json").write_text(json.dumps({
            "installed_tier": "tier-0", "components": [],
        }))
        text = self.ORACLE_TEMPLATE.read_text()
        text = (text
                .replace("{{COMPONENTS_LIST}}", "  # (no components — no signals detected)")
                .replace("{{SEED_BLOCKS}}", "# (no SEED blocks)")
                .replace("{{NO_COMPONENTS_MESSAGE}}", "no components registered"))
        oracle = target / "oracle.sh"
        oracle.write_text(text)
        mode = oracle.stat().st_mode
        oracle.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _emit_and_install(self, root: Path, target: Path, threshold: float = 0.8) -> str:
        plan_path, _rubric_dir, proc = _triage_shape_and_dataset(
            root, spec_text=NO_HEADINGS_SPEC_MD)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # `params --threshold` writes the author's intended bar into the
        # frozen definition (pinned into the hash — a later change trips
        # stale), but the pass/fail *decision* is oracle.sh's own global
        # $THRESHOLD env var (see templates/oracle.sh.template) — a
        # per-component score is always a bare [0,1], never self-judged
        # against its own config's threshold (content-fidelity's score.py
        # has the same split). `_run_gate` below passes THRESHOLD to match.
        proc2 = _run_cli(["params", str(plan_path), "--ac", "AC-042-demo-1",
                           "--threshold", str(threshold)])
        self.assertEqual(proc2.returncode, 0, proc2.stderr)
        proc3 = _run_cli([
            "emit", str(plan_path), "--ac", "AC-042-demo-1", "--target", str(target),
        ])
        self.assertEqual(proc3.returncode, 0, proc3.stderr)
        return ea.component_name("042-demo", "AC-042-demo-1")

    def _run_gate(self, target: Path, threshold: float = 0.8) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["THRESHOLD"] = str(threshold)
        return subprocess.run(
            [sys.executable, str(self.GATE), str(target)],
            capture_output=True, text=True, env=env)

    def test_gate_passes_when_composite_meets_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = Path(d) / "target"
            self._scaffold_bare_target(target)
            self._emit_and_install(root, target, threshold=0.8)

            os.environ[score._FAKE_SCORES_ENV] = json.dumps({
                "case-1": [0.9, 0.9, 0.9, 0.9], "case-2": [0.9, 0.9, 0.9, 0.9],
            })
            result = self._run_gate(target, threshold=0.8)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("status=pass", result.stdout)

    def test_gate_reports_below_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = Path(d) / "target"
            self._scaffold_bare_target(target)
            self._emit_and_install(root, target, threshold=0.8)

            os.environ[score._FAKE_SCORES_ENV] = json.dumps({
                "case-1": [0.5, 0.5, 0.5, 0.5], "case-2": [0.5, 0.5, 0.5, 0.5],
            })
            result = self._run_gate(target)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn("status=below_threshold", result.stdout)

    def test_gate_reports_env_error_with_no_fake_scores(self):
        """No fake-scores hook and no real candidate-gather yet (still a
        documented seam — see score.py's module docstring): the installed
        component's live path raises EnvError deterministically, regardless
        of ambient judge credentials, so gate.py reports env_error (rc=2)."""
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = Path(d) / "target"
            self._scaffold_bare_target(target)
            self._emit_and_install(root, target, threshold=0.8)

            result = self._run_gate(target)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("status=env_error", result.stdout)


if __name__ == "__main__":
    unittest.main()
