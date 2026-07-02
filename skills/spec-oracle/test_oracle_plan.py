"""
AC verification tests for slice 006-01 (evidence-plan) of `/servo:spec-oracle`.

Run from the repo root:
    python3 -m unittest skills.spec-oracle.test_oracle_plan
or via pytest:
    uvx pytest skills/spec-oracle/test_oracle_plan.py -q

The planner is read-only over the *source spec* and writes only under
`<spec_path.parent>/oracle/<spec-id>/` (ADR-0023, slice 019-02 — resolved
relative to the spec's own directory, not the target's `.servo/`).
Classification is deterministic (keyword/regex), so the dogfood fixtures
below are stable and offline; no LLM or network call is involved.

Test idiom mirrors `skills/quality-gate/test_gate.py`:
  - `unittest.TestCase` classes (collected by pytest),
  - `REPO_ROOT = Path(__file__).resolve().parents[2]`,
  - fixtures written into a `tempfile.TemporaryDirectory()`,
  - the CLI driven as a subprocess for end-to-end (AC3/AC5) paths.
Pure classification logic (AC1/AC2/AC6) is also imported directly for
fast unit assertions.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ORACLE_PLAN = REPO_ROOT / "skills" / "spec-oracle" / "oracle_plan.py"


# Import oracle_plan as a module for direct unit assertions. The directory
# name `spec-oracle` is not a valid Python identifier, so load by path.
def _load_module():
    spec = importlib.util.spec_from_file_location("oracle_plan", ORACLE_PLAN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


op = _load_module()


# ---------------------------------------------------------------------------
# Fixture spec bodies
# ---------------------------------------------------------------------------

# A minimal spec with a slice heading so AC IDs use the slice id.
SLICE_SPEC = """---
status: DRAFT
---

# Spec 099 — demo

## Slice 099-01 — demo-slice

**Acceptance Criteria:**

1. **Exists.** `oracle.sh` exists in the target.
2. **Text.** The README contains the string "servo".
3. **Judgment.** The copy tone is appropriate and reads well.
"""

# A spec with a top-level Acceptance Criteria section and no slice heading,
# so AC IDs fall back to the spec_id.
TOPLEVEL_SPEC = """# Spec 100 — toplevel

## Acceptance Criteria

1. **First.** The file `foo.txt` is present.
2. **Second.** The test suite passes.
"""


# A spec whose first AC WRAPS across three physical lines, with the only
# classifying keyword ("valid JSON") on the *third* line. Guards the
# truncation bug: extract_acs once captured only the first physical line,
# which stripped continuation-line keywords and collapsed deterministic ACs
# into residual_judgment.
MULTILINE_SPEC = """# Spec 200 — multiline

## Slice 200-01 — wrap

**Acceptance Criteria:**

1. **Output written.** The planner produces, under the chosen
   output directory, a `checks.json` artifact that is
   valid JSON.
2. **Single line.** `oracle.sh` exists in the target.
"""


# 039-shaped: removed dead file, .gitignore guard, no live runtime refs.
SPEC_039 = """# Spec 039 — cleanup

## Slice 039-01 — purge

**Acceptance Criteria:**

1. **Dead file removed.** The file `legacy/dead_module.py` is removed and
   absent from the tree.
2. **Gitignore guard.** The `.gitignore` contains an entry for `*.pyc`.
3. **No live references.** No live runtime references to the removed module
   remain, excluding historical docs.
4. **Tone.** The migration note reads well and is appropriately worded.
"""


# 046-shaped: command works from scaffold target, local doc links resolve,
# version string present.
SPEC_046 = """# Spec 046 — scaffold fidelity

## Slice 046-01 — fidelity

**Acceptance Criteria:**

1. **Scaffold command.** The stocktake command works from the scaffold
   target, generated into a tempdir.
2. **Links resolve.** Local Markdown links in the generated docs resolve.
3. **Version provenance.** The manifest contains the version string
   `0.1.0`.
"""


# 047-shaped: install-contract JSON valid + required key, file present +
# executable, verifier command exits 0.
SPEC_047 = """# Spec 047 — install contract

## Slice 047-01 — contract

**Acceptance Criteria:**

1. **Install JSON valid.** The `install.json` manifest is valid JSON and
   has the required key `servo_version`.
2. **Executable present.** The `oracle.sh` file is present and the
   executable bit is set.
3. **Verifier command.** The verifier command runs and exits 0.
"""


def _write_spec(parent: Path, spec_dir_name: str, body: str) -> Path:
    """Write a spec.md under <parent>/<spec_dir_name>/spec.md and return it."""
    d = parent / spec_dir_name
    d.mkdir(parents=True, exist_ok=True)
    p = d / "spec.md"
    p.write_text(body)
    return p


def _run_cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ORACLE_PLAN), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )


def _classify_via_cli(spec_path: Path) -> dict:
    """Drive the dry `classify` subcommand and parse its JSON stdout."""
    result = subprocess.run(
        [sys.executable, str(ORACLE_PLAN), "classify", str(spec_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"classify failed: {result.stderr}"
    return json.loads(result.stdout)


def _families(checks: list) -> dict:
    """Map AC id -> family for convenient assertions."""
    return {c["id"]: c["family"] for c in checks}


def _snapshot_tree(root: Path) -> dict:
    """Map every file path (relative to root) -> its bytes, for diffing."""
    snapshot = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            snapshot[str(p.relative_to(root))] = p.read_bytes()
    return snapshot


# ===========================================================================
# AC1 — AC extraction (numbered ACs, stable IDs, source line references)
# ===========================================================================


class ExtractionTests(unittest.TestCase):
    """AC1 — extract numbered ACs with stable IDs and source line refs."""

    def test_extracts_all_numbered_acs(self):
        result = op.extract_acs(SLICE_SPEC)
        self.assertEqual(len(result), 3, "should extract exactly 3 ACs")

    def test_ids_use_slice_id_when_slice_heading_present(self):
        result = op.extract_acs(SLICE_SPEC)
        ids = [ac["id"] for ac in result]
        self.assertEqual(ids, ["AC-099-01-1", "AC-099-01-2", "AC-099-01-3"])

    def test_ids_fall_back_to_spec_id_without_slice_heading(self):
        # spec_id must be supplied explicitly for the no-slice fallback.
        result = op.extract_acs(TOPLEVEL_SPEC, spec_id="100-toplevel")
        ids = [ac["id"] for ac in result]
        self.assertEqual(ids, ["AC-100-toplevel-1", "AC-100-toplevel-2"])

    def test_source_line_is_one_based_and_correct(self):
        result = op.extract_acs(SLICE_SPEC)
        # The first numbered AC ("1. **Exists.**") is on line 10 (1-based).
        lines = SLICE_SPEC.splitlines()
        first_line_no = result[0]["source_line"]
        self.assertTrue(lines[first_line_no - 1].lstrip().startswith("1."))

    def test_statement_text_captured(self):
        result = op.extract_acs(SLICE_SPEC)
        self.assertIn("oracle.sh", result[0]["statement"])

    def test_no_acceptance_section_yields_empty(self):
        result = op.extract_acs("# Spec\n\nNo criteria here.\n", spec_id="x")
        self.assertEqual(result, [])

    def test_multiline_statement_joins_continuation_lines(self):
        # The first AC in MULTILINE_SPEC spans three physical lines; the
        # extracted statement must contain text from all three, joined with
        # spaces (no embedded newline).
        result = op.extract_acs(MULTILINE_SPEC)
        stmt = result[0]["statement"]
        self.assertIn("produces", stmt)       # line 1
        self.assertIn("checks.json", stmt)    # line 2
        self.assertIn("valid JSON", stmt)     # line 3
        self.assertNotIn("\n", stmt)

    def test_multiline_source_line_points_at_numbered_item(self):
        # source_line stays anchored to the numbered item, not a continuation.
        result = op.extract_acs(MULTILINE_SPEC)
        lines = MULTILINE_SPEC.splitlines()
        self.assertTrue(
            lines[result[0]["source_line"] - 1].lstrip().startswith("1."))


# ===========================================================================
# AC2 — Family classification (each AC lands in one of the 9 families)
# ===========================================================================


class FamilyClassificationTests(unittest.TestCase):
    """AC2 — every AC is classified into exactly one known family."""

    VALID_FAMILIES = {
        "command",
        "file_presence",
        "text_invariant",
        "json_contract",
        "archive_inventory",
        "markdown_links",
        "generated_artifact_command",
        "runtime_reference_scan",
        "residual_judgment",
    }

    def test_every_ac_gets_a_valid_family(self):
        for body, sid in (
            (SLICE_SPEC, None),
            (SPEC_039, None),
            (SPEC_046, None),
            (SPEC_047, None),
        ):
            checks = op.classify_acs(op.extract_acs(body, spec_id=sid))
            self.assertTrue(checks, f"no checks for {sid}")
            for c in checks:
                self.assertIn(
                    c["family"], self.VALID_FAMILIES,
                    f"AC {c['id']} got unknown family {c['family']!r}",
                )

    def test_file_presence_family(self):
        ac = {"id": "x", "statement": "The file foo.txt is present.",
              "source_line": 1}
        self.assertEqual(op.classify_one(ac)["family"], "file_presence")

    def test_text_invariant_family(self):
        ac = {"id": "x", "statement": 'The README contains the string "servo".',
              "source_line": 1}
        self.assertEqual(op.classify_one(ac)["family"], "text_invariant")

    def test_json_contract_family(self):
        ac = {"id": "x",
              "statement": "The manifest is valid JSON with required key servo_version.",
              "source_line": 1}
        self.assertEqual(op.classify_one(ac)["family"], "json_contract")

    def test_archive_inventory_family(self):
        ac = {"id": "x",
              "statement": "The release zip contains the required entries.",
              "source_line": 1}
        self.assertEqual(op.classify_one(ac)["family"], "archive_inventory")

    def test_markdown_links_family(self):
        ac = {"id": "x",
              "statement": "Local Markdown links in the generated docs resolve.",
              "source_line": 1}
        self.assertEqual(op.classify_one(ac)["family"], "markdown_links")

    def test_generated_artifact_command_family(self):
        ac = {"id": "x",
              "statement": "The command works from the scaffold target generated into a tempdir.",
              "source_line": 1}
        self.assertEqual(
            op.classify_one(ac)["family"], "generated_artifact_command")

    def test_runtime_reference_scan_family(self):
        ac = {"id": "x",
              "statement": "No live runtime references to the removed module remain.",
              "source_line": 1}
        self.assertEqual(
            op.classify_one(ac)["family"], "runtime_reference_scan")

    def test_command_family(self):
        ac = {"id": "x", "statement": "The test suite passes.",
              "source_line": 1}
        self.assertEqual(op.classify_one(ac)["family"], "command")

    def test_residual_judgment_for_taste(self):
        ac = {"id": "x", "statement": "The copy tone is appropriate.",
              "source_line": 1}
        self.assertEqual(op.classify_one(ac)["family"], "residual_judgment")

    def test_residual_judgment_for_unmatched(self):
        ac = {"id": "x", "statement": "Zorblax the frobnicator wibbles.",
              "source_line": 1}
        self.assertEqual(op.classify_one(ac)["family"], "residual_judgment")


# ===========================================================================
# AC3 — Plan output (writes plan.md + checks.json with required keys)
# ===========================================================================


class PlanOutputTests(unittest.TestCase):
    """AC3 — write plan.md + checks.json with the required top-level keys."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.target = self.root / "target"
        self.target.mkdir()
        self.specs = self.root / "docs" / "specs"
        self.spec_path = _write_spec(self.specs, "099-demo", SLICE_SPEC)
        self.result = _run_cli(self.target, self.spec_path)

    def tearDown(self):
        self.tmp.cleanup()

    def _out_dir(self) -> Path:
        # ADR-0023 (slice 019-02): the plan lives under the spec's own
        # directory, not <target>/.servo/spec-oracles/<id>/.
        return self.spec_path.parent / "oracle" / "099-demo"

    def test_exit_zero(self):
        self.assertEqual(
            self.result.returncode, 0,
            f"stderr={self.result.stderr}\nstdout={self.result.stdout}",
        )

    def test_plan_md_written(self):
        self.assertTrue((self._out_dir() / "plan.md").exists())

    def test_checks_json_written(self):
        self.assertTrue((self._out_dir() / "checks.json").exists())

    def test_checks_json_required_keys(self):
        data = json.loads((self._out_dir() / "checks.json").read_text())
        for key in ("schema_version", "spec_id", "source_spec_path",
                    "source_hash", "checks"):
            self.assertIn(key, data, f"missing key {key!r}")

    def test_schema_version_is_one(self):
        data = json.loads((self._out_dir() / "checks.json").read_text())
        self.assertEqual(data["schema_version"], 1)

    def test_spec_id_from_parent_dir(self):
        data = json.loads((self._out_dir() / "checks.json").read_text())
        self.assertEqual(data["spec_id"], "099-demo")

    def test_source_hash_is_sha256_of_source(self):
        data = json.loads((self._out_dir() / "checks.json").read_text())
        expected = "sha256:" + hashlib.sha256(
            self.spec_path.read_bytes()).hexdigest()
        self.assertEqual(data["source_hash"], expected)

    def test_one_entry_per_ac(self):
        data = json.loads((self._out_dir() / "checks.json").read_text())
        all_ids = ([c["id"] for c in data["checks"]]
                   + [r["id"] for r in data.get("residual_judgment", [])])
        # SLICE_SPEC has 3 ACs (one of which is residual_judgment).
        self.assertEqual(len(all_ids), 3)

    def test_spec_id_override_flag(self):
        target2 = self.root / "target2"
        target2.mkdir()
        res = _run_cli(target2, self.spec_path, "--spec-id", "custom-id")
        self.assertEqual(res.returncode, 0, res.stderr)
        # The oracle dir is spec-relative (ADR-0023), so it lands beside the
        # spec regardless of which target the CLI was pointed at.
        out = self.spec_path.parent / "oracle" / "custom-id"
        self.assertTrue((out / "checks.json").exists())
        data = json.loads((out / "checks.json").read_text())
        self.assertEqual(data["spec_id"], "custom-id")

    def test_source_spec_path_recorded_as_given_not_absolutised(self):
        # checks.json records the path as the user passed it (the spec's
        # schema example is repo-relative) rather than an absolute resolved
        # path that would leak the author's filesystem layout.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_spec(root / "docs" / "specs", "300-rel", SLICE_SPEC)
            rel = os.path.join("docs", "specs", "300-rel", "spec.md")
            result = subprocess.run(
                [sys.executable, str(ORACLE_PLAN), "classify", rel],
                capture_output=True, text=True, cwd=str(root),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["source_spec_path"], rel)
            self.assertFalse(os.path.isabs(payload["source_spec_path"]))


# ===========================================================================
# AC4 — Uncovered judgment visible (reason + suggested_review)
# ===========================================================================


class ResidualJudgmentTests(unittest.TestCase):
    """AC4 — residual_judgment ACs carry a reason and a suggested review."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.target = self.root / "target"
        self.target.mkdir()
        self.spec_path = _write_spec(
            self.root / "docs" / "specs", "099-demo", SLICE_SPEC)
        _run_cli(self.target, self.spec_path)
        out = self.spec_path.parent / "oracle" / "099-demo"
        self.data = json.loads((out / "checks.json").read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def test_residual_section_present(self):
        self.assertIn("residual_judgment", self.data)
        self.assertTrue(self.data["residual_judgment"],
                        "expected at least one residual-judgment AC")

    def test_residual_entries_have_reason_and_review(self):
        for entry in self.data["residual_judgment"]:
            self.assertIn("reason", entry)
            self.assertTrue(entry["reason"], "reason must be non-empty")
            self.assertIn("suggested_review", entry)
            self.assertTrue(entry["suggested_review"],
                            "suggested_review must be non-empty")

    def test_classify_one_residual_carries_reason_and_review(self):
        ac = {"id": "AC-X", "statement": "The tone is appropriate.",
              "source_line": 1}
        out = op.classify_one(ac)
        self.assertEqual(out["family"], "residual_judgment")
        self.assertIn("reason", out)
        self.assertIn("suggested_review", out)


# ===========================================================================
# AC5 — No target behavior change (nothing outside the spec-oracle dir)
# ===========================================================================


class NoTargetMutationTests(unittest.TestCase):
    """AC5 (slice 006-01) / ADR-0023 (slice 019-02) — only the spec's own
    `oracle/<id>/` dir is created; nothing else, and nothing under
    `<target>/.servo/`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.target = self.root / "target"
        self.target.mkdir()
        # Pre-seed pre-existing target files the slice must NOT touch.
        (self.target / "oracle.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        (self.target / ".servo").mkdir()
        (self.target / ".servo" / "install.json").write_text('{"x": 1}\n')
        (self.target / "src.py").write_text("print('hi')\n")
        self.spec_path = _write_spec(
            self.root / "docs" / "specs", "099-demo", SLICE_SPEC)

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_spec_oracle_dir_added(self):
        # ADR-0023 (slice 019-02): the planner writes under the spec's own
        # directory (docs/specs/099-demo/oracle/099-demo/), not
        # <target>/.servo/spec-oracles/099-demo/. Snapshot the whole root
        # (not just the target) since the spec dir now lives alongside it.
        before = _snapshot_tree(self.root)
        res = _run_cli(self.target, self.spec_path)
        self.assertEqual(res.returncode, 0, res.stderr)
        after = _snapshot_tree(self.root)

        # Every pre-existing file must be byte-identical afterwards.
        for path, content in before.items():
            self.assertIn(path, after, f"{path} disappeared")
            self.assertEqual(after[path], content,
                             f"{path} was modified by the planner")

        # Every newly-created path must live under the spec's own oracle dir.
        prefix = os.path.join("docs", "specs", "099-demo", "oracle", "099-demo")
        new_paths = set(after) - set(before)
        self.assertTrue(new_paths, "planner wrote nothing")
        for path in new_paths:
            self.assertTrue(
                path.startswith(prefix),
                f"planner wrote outside the spec's oracle dir: {path}",
            )

    def test_nothing_written_under_target_servo_dir(self):
        # AC4 — `.servo/` gains no new spec-oracle artifacts.
        before = _snapshot_tree(self.target / ".servo")
        _run_cli(self.target, self.spec_path)
        after = _snapshot_tree(self.target / ".servo")
        self.assertEqual(before, after,
                         "planner must not write under <target>/.servo/")
        self.assertFalse((self.target / ".servo" / "spec-oracles").exists())

    def test_oracle_sh_untouched(self):
        original = (self.target / "oracle.sh").read_bytes()
        _run_cli(self.target, self.spec_path)
        self.assertEqual((self.target / "oracle.sh").read_bytes(), original)

    def test_install_json_untouched(self):
        original = (self.target / ".servo" / "install.json").read_bytes()
        _run_cli(self.target, self.spec_path)
        self.assertEqual(
            (self.target / ".servo" / "install.json").read_bytes(), original)

    def test_source_spec_untouched(self):
        original = self.spec_path.read_bytes()
        _run_cli(self.target, self.spec_path)
        self.assertEqual(self.spec_path.read_bytes(), original,
                         "planner must not rewrite the source spec")

    def test_traversal_spec_id_refused_not_written_outside_spec_dir(self):
        # ADR-0023 (slice 019-02) craft-review finding: --spec-id reaches
        # oracle_dir_for_spec (the shared path helper) with no separate
        # guard in the planner; the helper itself must reject a
        # path-traversal-shaped id so `plan.mkdir(parents=True)` never
        # escapes the spec's own oracle directory.
        before = _snapshot_tree(self.root)
        res = _run_cli(self.target, self.spec_path,
                       "--spec-id", "../../../../tmp/evil")
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        after = _snapshot_tree(self.root)
        self.assertEqual(before, after,
                         "a refused --spec-id must leave no trace on disk")


# ===========================================================================
# AC6 — Dogfood classification fixtures (jig 039/046/047-shaped)
# ===========================================================================


class DogfoodClassificationTests(unittest.TestCase):
    """AC6 — obvious ACs land in deterministic families, not residual."""

    def test_039_shaped(self):
        fams = _families(op.classify_acs(op.extract_acs(SPEC_039)))
        self.assertEqual(fams["AC-039-01-1"], "file_presence")      # removed/absent
        self.assertEqual(fams["AC-039-01-2"], "text_invariant")     # .gitignore entry
        self.assertEqual(fams["AC-039-01-3"], "runtime_reference_scan")
        # The deliberately-judgment AC stays residual.
        self.assertEqual(fams["AC-039-01-4"], "residual_judgment")

    def test_046_shaped(self):
        fams = _families(op.classify_acs(op.extract_acs(SPEC_046)))
        self.assertEqual(
            fams["AC-046-01-1"], "generated_artifact_command")       # scaffold target
        self.assertEqual(fams["AC-046-01-2"], "markdown_links")      # links resolve
        self.assertEqual(fams["AC-046-01-3"], "text_invariant")      # version string

    def test_047_shaped(self):
        fams = _families(op.classify_acs(op.extract_acs(SPEC_047)))
        self.assertEqual(fams["AC-047-01-1"], "json_contract")       # valid JSON + key
        self.assertEqual(fams["AC-047-01-2"], "file_presence")       # present + executable
        self.assertEqual(fams["AC-047-01-3"], "command")             # verifier exits 0

    def test_dogfood_specs_are_mostly_deterministic(self):
        # Across the three jig-shaped specs, only the single explicit-taste
        # AC (039 #4) should be residual judgment.
        residual = 0
        total = 0
        for body in (SPEC_039, SPEC_046, SPEC_047):
            for c in op.classify_acs(op.extract_acs(body)):
                total += 1
                if c["family"] == "residual_judgment":
                    residual += 1
        self.assertEqual(residual, 1, f"{residual}/{total} residual; expected 1")

    def test_classify_subcommand_writes_nothing(self):
        # The dry `classify` path must not create a target dir.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec_path = _write_spec(root / "docs" / "specs", "046-x", SPEC_046)
            payload = _classify_via_cli(spec_path)
            self.assertIn("checks", payload)
            # No .servo anywhere under root.
            self.assertFalse(
                list(root.rglob(".servo")),
                "classify subcommand must not write artifacts",
            )
            # ADR-0023 (slice 019-02): nor the new spec-relative oracle dir.
            self.assertFalse(
                (spec_path.parent / "oracle").exists(),
                "classify subcommand must not write the spec's oracle dir",
            )


# ===========================================================================
# Regression — multi-line AC capture (the truncation bug)
# ===========================================================================


class MultilineRegressionTests(unittest.TestCase):
    """Deterministic ACs whose keyword lives on a continuation line must not
    collapse into residual_judgment. Before the multi-line fix, extract_acs
    captured only the first physical line of each AC."""

    def test_keyword_only_on_continuation_line_still_classifies(self):
        fams = _families(op.classify_acs(op.extract_acs(MULTILINE_SPEC)))
        # AC1's deterministic signal ("valid JSON") is on its third line.
        self.assertEqual(fams["AC-200-01-1"], "json_contract")

    def test_real_spec_006_yields_deterministic_checks(self):
        # Dogfood smoke against this repo's own (multi-line) 006-01 slice file.
        # The truncation bug produced ZERO deterministic checks on spec 006's
        # multi-line ACs. Assert > 0 so that catastrophic regression can never
        # return silently. (The 006-01 slice's six ACs yield 3 deterministic.)
        # Points at the slice file rather than spec.md because the jig-workflow
        # migration moved the ACs into per-slice files.
        slice006 = (REPO_ROOT / "docs" / "specs" / "006-spec-oracle"
                    / "slice-01-evidence-plan.md")
        self.assertTrue(slice006.is_file(), f"missing dogfood slice: {slice006}")
        checks = op.classify_acs(op.extract_acs(slice006.read_text()))
        deterministic = [c for c in checks
                         if c["family"] != "residual_judgment"]
        self.assertGreater(
            len(deterministic), 0,
            "006-01 yielded zero deterministic checks — multi-line AC "
            "truncation regression?",
        )


# Bug 003: a bold-label note between the AC header and the numbered list.
AC_BOLD_NOTE_SPEC = """# Spec 300 — preamble note

## Slice 300-01 — note

**Acceptance Criteria:**

**Note:** these criteria are provisional and may change.

1. **Exists.** `oracle.sh` exists in the target.
2. **Text.** The README contains the string "servo".
"""

# ACs followed by a sibling DoD list — the DoD must still be bounded out.
AC_WITH_DOD_SPEC = """# Spec 301 — dod bound

## Slice 301-01 — dod

**Acceptance Criteria:**

1. **Exists.** `oracle.sh` exists in the target.
2. **Text.** The README contains the string "servo".

**Definition of Done:**

1. All tests pass.
2. Lint is clean.
"""

# A present-but-empty AC section (header, then a real heading before any item).
AC_EMPTY_SECTION_SPEC = """# Spec 302 — empty

## Slice 302-01 — empty

**Acceptance Criteria:**

## Notes

1. This is not an acceptance criterion.
"""


class ACPreambleToleranceTests(unittest.TestCase):
    """Bug 003 — interstitial bold-label tolerance + non-silent empty section.

    A bold pseudo-heading label (`**Note:** …`) between the AC header and the
    first numbered item must not zero the section (it is interstitial prose, not
    a sibling section), while a real sibling list that FOLLOWS the ACs (a DoD)
    must still be bounded out. A present AC section that yields zero items must
    warn on stderr rather than silently returning 0.
    """

    def test_bold_label_note_before_first_item_still_yields_acs(self):
        result = op.extract_acs(AC_BOLD_NOTE_SPEC)
        self.assertEqual(len(result), 2, "bold-label note must not zero the ACs")
        self.assertIn("oracle.sh", result[0]["statement"])

    def test_dod_after_acs_is_still_bounded(self):
        # The DoD's own numbered list must NOT be swept into the ACs.
        result = op.extract_acs(AC_WITH_DOD_SPEC)
        self.assertEqual(len(result), 2)
        statements = " ".join(ac["statement"] for ac in result)
        self.assertNotIn("tests pass", statements.lower())

    def test_empty_ac_section_warns_not_silent(self):
        with tempfile.TemporaryDirectory() as d:
            spec = Path(d) / "spec.md"
            spec.write_text(AC_EMPTY_SECTION_SPEC)
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                plan = op.classify_only(spec, "302-empty")
            self.assertEqual(len(plan["checks"]), 0)
            self.assertEqual(len(plan["residual_judgment"]), 0)
            self.assertIn("0 acceptance criteria", buf.getvalue().lower())


# ===========================================================================
# Slice 019-03 — behavioral / negative-behavior AC recall
# ===========================================================================


class BehavioralNegativeACRecallTests(unittest.TestCase):
    """AC1 — negative-behavior phrasing recognized as `command`-checkable
    instead of falling through to `residual_judgment`.

    Narrow, anchored patterns only (Assumption A1): "fails when/if", "is
    excluded", "does NOT <verb>", "is never / never <verb>" — not bare
    "not"/"never" anywhere in the statement.
    """

    def _family(self, statement: str) -> str:
        return op.classify_one(
            {"id": "x", "statement": statement, "source_line": 1})["family"]

    def test_fails_when(self):
        self.assertEqual(
            self._family("The lint check fails when a stray console.log is left in."),
            "command")

    def test_fails_if(self):
        self.assertEqual(
            self._family("The build fails if the config file is missing."),
            "command")

    def test_is_excluded_from(self):
        self.assertEqual(
            self._family("The dev-only fixture is excluded from the release build."),
            "command")

    def test_is_excluded_bare(self):
        self.assertEqual(
            self._family("The vendored dependency is excluded."),
            "command")

    def test_is_excluded_does_not_collide_with_archive_inventory(self):
        # Rule 5 (archive_inventory) triggers on "package" + "excludes" (verb
        # form); "is excluded" (past participle) is a distinct token and must
        # not be swept into archive_inventory just because "package" is also
        # present in the statement.
        self.assertEqual(
            self._family(
                "The dev-only fixture package is excluded from the release "
                "build."),
            "command")

    def test_does_not_run(self):
        self.assertEqual(
            self._family("The deprecated migration does NOT run in CI anymore."),
            "command")

    def test_does_not_compile(self):
        self.assertEqual(
            self._family("The legacy module does not compile under the new target."),
            "command")

    def test_does_not_pass(self):
        self.assertEqual(
            self._family("The flaky test does not pass on a cold cache."),
            "command")

    def test_does_not_build(self):
        self.assertEqual(
            self._family("The removed widget does not build from the old branch."),
            "command")

    def test_is_never(self):
        self.assertEqual(
            self._family("The staging flag is never enabled in a production build."),
            "command")

    def test_never_happens(self):
        self.assertEqual(
            self._family("A duplicate submission never happens once the lock lands."),
            "command")

    def test_bare_not_does_not_trigger_family(self):
        # Assumption A1 guard: bare "not" anywhere must NOT be a trigger — only
        # the anchored phrasings above are. This statement has no other
        # deterministic keyword, so it should stay residual_judgment.
        self.assertEqual(
            self._family("Zorblax the frobnicator is not particularly happy."),
            "residual_judgment")

    def test_bare_never_does_not_trigger_family(self):
        # Same guard for "never" — anchored phrasing only.
        self.assertEqual(
            self._family("Zorblax the frobnicator never wibbles quietly."),
            "residual_judgment")

    def test_existing_family_precedence_preserved_file_presence(self):
        # "does not exist" must still win file_presence, not the new family.
        self.assertEqual(
            self._family("The temp scratch file does not exist after cleanup."),
            "file_presence")

    def test_existing_family_precedence_preserved_text_invariant(self):
        # "does not contain" must still win text_invariant, not the new family.
        self.assertEqual(
            self._family("The README does not contain the word TODO."),
            "text_invariant")

    def test_taste_language_still_forced_residual(self):
        # classify_one's taste override must still win over the new family.
        entry = op.classify_one({
            "id": "x", "source_line": 1,
            "statement": "The copy never feels awkward or fails to read well.",
        })
        self.assertEqual(entry["family"], "residual_judgment")


# ===========================================================================
# Slice 019-03 — dogfood-shaped behavioral AC fixture (AC4)
# ===========================================================================

# A servo-authored fixture matching the *pattern* of the dogfood's reported
# behavioral/negative-phrasing ACs (spec 019 "Why this spec" + Bug 003's
# record) — not a copy of any proprietary content.
SPEC_DOGFOOD_BEHAVIORAL = """# Spec 900 — dogfood-shaped behavioral ACs

## Slice 900-01 — behavioral-shape

**Acceptance Criteria:**

1. The lint check fails when a disallowed import is introduced.
2. The dev-only fixture data is excluded from the packaged release.
3. The removed legacy endpoint does NOT run after the migration.
4. The retired feature flag is never enabled once the cleanup lands.
"""


class DogfoodBehavioralPatternTests(unittest.TestCase):
    """AC4 — the dogfood's reported behavioral/negative-phrasing AC shape
    classifies as `checks`, not `residual_judgment`, without hand promotion."""

    def test_all_behavioral_acs_classify_as_checks(self):
        acs = op.extract_acs(SPEC_DOGFOOD_BEHAVIORAL, spec_id="900-dogfood")
        self.assertEqual(len(acs), 4)
        classified = op.classify_acs(acs)
        for entry in classified:
            self.assertEqual(
                entry["family"], "command",
                f"{entry['id']} ({entry['statement']!r}) fell through to "
                f"{entry['family']!r}")

    def test_build_plan_has_zero_residual(self):
        plan = op.build_plan(
            SPEC_DOGFOOD_BEHAVIORAL, spec_id="900-dogfood",
            source_spec_path="900-dogfood/spec.md", source_hash="sha256:test")
        self.assertEqual(len(plan["checks"]), 4)
        self.assertEqual(len(plan["residual_judgment"]), 0)


if __name__ == "__main__":
    unittest.main()
