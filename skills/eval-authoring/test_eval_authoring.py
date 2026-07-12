"""
AC verification tests for slice 008-01 (residual-triage) of
`/servo:eval-authoring`.

Run from the repo root:
    python3 -m pytest skills/eval-authoring/test_eval_authoring.py -q

All of spec 008's tests accrete in this one file (see spec.md "Test
surface") — this is the first tranche, covering slice 008-01's six ACs
only. Classification is deterministic (keyword/substring matching over the
AC statement text, no LLM/network call), so every fixture below is stable
and offline.

Test idiom mirrors `skills/spec-oracle/test_oracle_plan.py` /
`skills/edd-suitability/test_suitability.py`:
  - `unittest.TestCase` classes (collected by pytest),
  - `REPO_ROOT = Path(__file__).resolve().parents[2]`,
  - fixtures written into a `tempfile.TemporaryDirectory()`,
  - the CLI driven as a subprocess for end-to-end (AC4/AC5/AC6) paths,
  - the pure classification logic (AC1/AC2) imported directly for fast
    unit assertions, via the `importlib`/load-by-path idiom (the skill
    directory names are hyphenated and not importable Python packages).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_AUTHORING = REPO_ROOT / "skills" / "eval-authoring" / "eval_authoring.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("eval_authoring", EVAL_AUTHORING)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ea = _load_module()

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


if __name__ == "__main__":
    unittest.main()
