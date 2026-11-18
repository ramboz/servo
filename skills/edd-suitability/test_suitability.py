"""
AC verification tests for slice 015-01 (verdict-contract) of
`/servo:edd-suitability`.

Run from the repo root:
    python3 -m pytest skills/edd-suitability/test_suitability.py -q

The analyzer is read-only over the *target* and writes only
`<target>/.servo/suitability/<spec-id>.json`. The verdict decision is a pure,
deterministic ordered rule table (no clock / network / randomness), so the unit
assertions below are stable and offline.

Test idiom mirrors `skills/spec-oracle/test_oracle_plan.py`:
  - `unittest.TestCase` classes (collected by pytest),
  - `REPO_ROOT = Path(__file__).resolve().parents[2]`,
  - fixtures written into a `tempfile.TemporaryDirectory()`,
  - the CLI driven as a subprocess for end-to-end paths,
  - the pure decision logic imported directly for fast assertions.

The 006 AC classification is obtained by subprocessing `oracle_plan.py classify`
(the established servo subprocess idiom — cf. heartbeat's gate.py/loop.py). Tests
inject a deterministic stub via `SERVO_SUITABILITY_ORACLE_PLAN` so no test
depends on oracle_plan's classifier behavior; one end-to-end test uses the real
classifier.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUITABILITY = REPO_ROOT / "skills" / "edd-suitability" / "suitability.py"
REAL_ORACLE_PLAN = REPO_ROOT / "skills" / "spec-oracle" / "oracle_plan.py"

VERDICTS = {"suitable", "needs_evidence", "unsuitable"}


def _load_module():
    spec = importlib.util.spec_from_file_location("suitability", SUITABILITY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


suitability = _load_module()


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def _make_target(root: Path, signals: dict | None) -> Path:
    """Create a target dir; drop `.servo/install.json` unless signals is None."""
    target = root / "target"
    servo = target / ".servo"
    servo.mkdir(parents=True)
    if signals is not None:
        (servo / "install.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "signals": signals,
                    "components": [],
                    "weights": {},
                }
            )
        )
    return target


def _make_spec(root: Path, text: str = "# Spec 015\n\n1. an AC\n") -> Path:
    spec_dir = root / "015-edd-suitability"
    spec_dir.mkdir(parents=True)
    spec = spec_dir / "spec.md"
    spec.write_text(text)
    return spec


def _stub_oracle_plan(root: Path, *, n_checks: int, n_residual: int,
                      spec_id: str = "015-edd-suitability",
                      exit_code: int = 0, garbage: bool = False) -> Path:
    """Write a deterministic stand-in for `oracle_plan.py classify`."""
    if garbage:
        body = "print('not json at all')\n"
    else:
        checks = [{"id": f"AC-{i}", "family": "command"} for i in range(n_checks)]
        residual = [{"id": f"AC-r{i}"} for i in range(n_residual)]
        payload = {"spec_id": spec_id, "checks": checks,
                   "residual_judgment": residual}
        body = f"print({json.dumps(json.dumps(payload))})\n"
    script = root / "stub_oracle_plan.py"
    script.write_text(f"import sys\n{body}sys.exit({exit_code})\n")
    return script


def _run_cli(target: Path, spec: Path, *, oracle_plan: Path | None,
             extra_env: dict | None = None):
    env = dict(os.environ)
    if oracle_plan is not None:
        env["SERVO_SUITABILITY_ORACLE_PLAN"] = str(oracle_plan)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SUITABILITY), "analyze", str(target),
         "--spec", str(spec)],
        capture_output=True, text=True, env=env,
    )


def _artifact_path(target: Path, spec_id: str = "015-edd-suitability") -> Path:
    return target / ".servo" / "suitability" / f"{spec_id}.json"


SIG_TESTS = {"tests": True, "lint": False, "ci": False, "language": "python"}
SIG_CI = {"tests": False, "lint": False, "ci": True, "language": "python"}
SIG_NONE = {"tests": False, "lint": False, "ci": False, "language": None}
SIG_LINT_ONLY = {"tests": False, "lint": True, "ci": False, "language": "python"}


# --------------------------------------------------------------------------
# AC1 — closed three-state verdict shape
# --------------------------------------------------------------------------

class VerdictShapeTests(unittest.TestCase):
    def test_artifact_has_required_fields(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            res = _run_cli(target, spec, oracle_plan=plan)
            self.assertEqual(res.returncode, 0, res.stderr)
            art = json.loads(_artifact_path(target).read_text())
            self.assertEqual(art["schema_version"], 1)
            self.assertIn(art["verdict"], VERDICTS)
            self.assertEqual(art["spec_id"], "015-edd-suitability")
            self.assertIn("analyzed_at", art)
            self.assertTrue(art["reasons"], "reasons must be non-empty")
            for r in art["reasons"]:
                self.assertIn("code", r)
                self.assertIn("message", r)

    def test_no_numeric_score_field(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            _run_cli(target, spec, oracle_plan=plan)
            art = json.loads(_artifact_path(target).read_text())
            self.assertNotIn("score", art)
            self.assertNotIn("confidence", art)

    def test_suitable_when_evaluable_acs_and_signal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=3, n_residual=1)
            res = _run_cli(target, spec, oracle_plan=plan)
            self.assertEqual(res.returncode, 0, res.stderr)
            art = json.loads(_artifact_path(target).read_text())
            self.assertEqual(art["verdict"], "suitable")


# --------------------------------------------------------------------------
# AC2 — fail-closed default (pure decision)
# --------------------------------------------------------------------------

class FailClosedDefaultTests(unittest.TestCase):
    def test_no_acs_no_signal_is_not_suitable(self):
        out = suitability.decide(SIG_NONE, n_evaluable=0, n_residual=0)
        self.assertNotEqual(out["verdict"], "suitable")

    def test_no_evaluable_acs_with_signal_is_not_suitable(self):
        out = suitability.decide(SIG_TESTS, n_evaluable=0, n_residual=2)
        self.assertNotEqual(out["verdict"], "suitable")

    def test_only_suitable_path_requires_evaluable_acs_and_signal(self):
        # Exhaustive small grid: suitable iff (n_evaluable >= 1 AND tests|ci).
        for tests in (True, False):
            for ci in (True, False):
                for n_eval in (0, 1, 3):
                    for n_res in (0, 2):
                        sig = {"tests": tests, "lint": False, "ci": ci,
                               "language": "python"}
                        out = suitability.decide(sig, n_evaluable=n_eval,
                                                  n_residual=n_res)
                        expect_suitable = n_eval >= 1 and (tests or ci)
                        self.assertEqual(
                            out["verdict"] == "suitable", expect_suitable,
                            f"tests={tests} ci={ci} n_eval={n_eval} "
                            f"n_res={n_res} -> {out['verdict']}",
                        )

    def test_indeterminate_resolves_to_named_or_unsuitable(self):
        out = suitability.decide(SIG_NONE, n_evaluable=0, n_residual=0)
        self.assertIn(out["verdict"], {"needs_evidence", "unsuitable"})
        self.assertTrue(out["reasons"])


# --------------------------------------------------------------------------
# AC3 — deterministic ordered first-match rule table
# --------------------------------------------------------------------------

class RuleTableDeterminismTests(unittest.TestCase):
    def test_same_inputs_same_decision(self):
        a = suitability.decide(SIG_CI, n_evaluable=2, n_residual=1)
        b = suitability.decide(SIG_CI, n_evaluable=2, n_residual=1)
        self.assertEqual(a, b)

    def test_decision_excludes_clock(self):
        # The pure decision carries no timestamp / nondeterministic field.
        out = suitability.decide(SIG_CI, n_evaluable=2, n_residual=1)
        self.assertNotIn("analyzed_at", out)

    def test_fired_rule_names_itself_in_reasons(self):
        out = suitability.decide(SIG_TESTS, n_evaluable=2, n_residual=0)
        codes = [r["code"] for r in out["reasons"]]
        self.assertIn("evaluable_acs_with_signal", codes)

    def test_cli_decision_byte_stable_across_runs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_CI)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=1)
            _run_cli(target, spec, oracle_plan=plan)
            first = json.loads(_artifact_path(target).read_text())
            _run_cli(target, spec, oracle_plan=plan)
            second = json.loads(_artifact_path(target).read_text())
            self.assertEqual(first["verdict"], second["verdict"])
            self.assertEqual(first["reasons"], second["reasons"])


# --------------------------------------------------------------------------
# AC4 — unsuitable vs needs_evidence discrimination
# --------------------------------------------------------------------------

class VerdictDiscriminationTests(unittest.TestCase):
    def test_all_residual_no_signal_is_unsuitable(self):
        out = suitability.decide(SIG_NONE, n_evaluable=0, n_residual=4)
        self.assertEqual(out["verdict"], "unsuitable")

    def test_evaluable_acs_missing_signal_is_needs_evidence(self):
        out = suitability.decide(SIG_NONE, n_evaluable=3, n_residual=0)
        self.assertEqual(out["verdict"], "needs_evidence")

    def test_signal_but_no_evaluable_acs_is_needs_evidence(self):
        out = suitability.decide(SIG_CI, n_evaluable=0, n_residual=2)
        self.assertEqual(out["verdict"], "needs_evidence")

    def test_lint_alone_is_not_a_sufficient_signal(self):
        # v1: only tests|ci count as the oracle signal; lint alone is weak.
        out = suitability.decide(SIG_LINT_ONLY, n_evaluable=2, n_residual=0)
        self.assertEqual(out["verdict"], "needs_evidence")


# --------------------------------------------------------------------------
# AC5 — read-only over target; persisted artifact
# --------------------------------------------------------------------------

class ReadOnlyArtifactTests(unittest.TestCase):
    def test_only_writes_suitability_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            # Snapshot every .servo file except the suitability dir.
            servo = target / ".servo"
            before = {
                p: p.read_bytes()
                for p in servo.rglob("*")
                if p.is_file() and "suitability" not in p.parts
            }
            _run_cli(target, spec, oracle_plan=plan)
            after = {
                p: p.read_bytes()
                for p in servo.rglob("*")
                if p.is_file() and "suitability" not in p.parts
            }
            self.assertEqual(before, after, "non-suitability .servo files changed")
            self.assertTrue(_artifact_path(target).is_file())

    def test_spec_source_not_mutated(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = _make_spec(root)
            before = spec.read_bytes()
            plan = _stub_oracle_plan(root, n_checks=1, n_residual=0)
            _run_cli(target, spec, oracle_plan=plan)
            self.assertEqual(spec.read_bytes(), before)

    def test_rerun_overwrites_idempotent_decision(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            _run_cli(target, spec, oracle_plan=plan)
            v1 = json.loads(_artifact_path(target).read_text())["verdict"]
            _run_cli(target, spec, oracle_plan=plan)
            v2 = json.loads(_artifact_path(target).read_text())["verdict"]
            self.assertEqual(v1, v2)


# --------------------------------------------------------------------------
# AC6 — closed env-error contract
# --------------------------------------------------------------------------

class EnvErrorContractTests(unittest.TestCase):
    def test_missing_spec(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            plan = _stub_oracle_plan(root, n_checks=1, n_residual=0)
            missing = root / "nope" / "spec.md"
            res = _run_cli(target, missing, oracle_plan=plan)
            self.assertEqual(res.returncode, 2)
            self.assertIn("spec_missing", res.stderr)
            self.assertFalse(_artifact_path(target).exists())

    def test_missing_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, None)  # no install.json
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=1, n_residual=0)
            res = _run_cli(target, spec, oracle_plan=plan)
            self.assertEqual(res.returncode, 2)
            self.assertIn("manifest_missing", res.stderr)
            self.assertFalse(_artifact_path(target).exists())

    def test_plan_unreadable_when_classifier_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=0, n_residual=0, exit_code=2)
            res = _run_cli(target, spec, oracle_plan=plan)
            self.assertEqual(res.returncode, 2)
            self.assertIn("plan_unreadable", res.stderr)
            self.assertFalse(_artifact_path(target).exists())

    def test_plan_unreadable_when_classifier_emits_garbage(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=0, n_residual=0, garbage=True)
            res = _run_cli(target, spec, oracle_plan=plan)
            self.assertEqual(res.returncode, 2)
            self.assertIn("plan_unreadable", res.stderr)
            self.assertFalse(_artifact_path(target).exists())

    def test_never_exit_one(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, None)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=0, n_residual=0)
            res = _run_cli(target, spec, oracle_plan=plan)
            self.assertIn(res.returncode, (0, 2))

    def test_manifest_malformed_when_install_json_unparseable(self):
        # 015-01 deviation log deferred an explicit test for the
        # `manifest_malformed` reason (present-but-unparseable manifest).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            (target / ".servo" / "install.json").write_text("{ not json ]")
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=1, n_residual=0)
            res = _run_cli(target, spec, oracle_plan=plan)
            self.assertEqual(res.returncode, 2)
            self.assertIn("manifest_malformed", res.stderr)
            self.assertFalse(_artifact_path(target).exists())


# --------------------------------------------------------------------------
# End-to-end against the REAL oracle_plan classifier (no stub)
# --------------------------------------------------------------------------

class RealClassifierIntegrationTests(unittest.TestCase):
    def test_real_classifier_produces_a_valid_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = _make_spec(
                root,
                "# Spec 015\n\n## Acceptance Criteria\n\n"
                "1. The CLI exits 0 on success.\n"
                "2. The output file exists at the path.\n",
            )
            res = _run_cli(target, spec, oracle_plan=REAL_ORACLE_PLAN)
            self.assertEqual(res.returncode, 0, res.stderr)
            art = json.loads(_artifact_path(target).read_text())
            self.assertIn(art["verdict"], VERDICTS)


# ==========================================================================
# Slice 015-02 — missing-evidence
# ==========================================================================

# Inputs that drive each needs_evidence path (the only verdict with a
# load-bearing missing_evidence list).
#   - SIG_NONE + evaluable ACs   -> evaluable_acs_no_signal   (missing signal)
#   - SIG_CI   + no evaluable ACs-> signal_without_evaluable_acs (missing ACs)
#   - SIG_NONE + no ACs at all   -> no_evidence_no_acs        (both gaps)
_NEEDS_EVIDENCE_CASES = (
    (SIG_NONE, 3, 0),   # evaluable ACs, no signal
    (SIG_CI, 0, 2),     # signal, no evaluable ACs
    (SIG_NONE, 0, 0),   # nothing at all
    (SIG_LINT_ONLY, 2, 0),  # evaluable ACs, lint-only (insufficient signal)
)


# --------------------------------------------------------------------------
# AC1 — closed `kind` taxonomy
# --------------------------------------------------------------------------

class MissingEvidenceKindTaxonomyTests(unittest.TestCase):
    def test_module_exposes_closed_taxonomy(self):
        self.assertEqual(
            suitability.MISSING_EVIDENCE_KINDS,
            ("tests", "lint", "ci", "oracle_signal", "reference_set"),
        )

    def test_every_emitted_kind_is_in_the_closed_set(self):
        allowed = set(suitability.MISSING_EVIDENCE_KINDS)
        for sig, n_eval, n_res in _NEEDS_EVIDENCE_CASES:
            out = suitability.decide(sig, n_evaluable=n_eval, n_residual=n_res)
            self.assertEqual(out["verdict"], "needs_evidence",
                             f"{sig} {n_eval} {n_res}")
            for item in out["missing_evidence"]:
                self.assertIn(item["kind"], allowed,
                              f"open-string kind {item['kind']!r} emitted")

    def test_no_open_string_kind_even_with_odd_signals(self):
        # An unknown signal key must not leak through as a missing_evidence kind.
        odd = {"tests": False, "ci": False, "lint": False, "weird": True}
        out = suitability.decide(odd, n_evaluable=1, n_residual=0)
        for item in out["missing_evidence"]:
            self.assertIn(item["kind"], set(suitability.MISSING_EVIDENCE_KINDS))


# --------------------------------------------------------------------------
# AC2 — actionable, blocking-flagged items
# --------------------------------------------------------------------------

class MissingEvidenceItemShapeTests(unittest.TestCase):
    def test_each_item_has_kind_detail_blocking(self):
        for sig, n_eval, n_res in _NEEDS_EVIDENCE_CASES:
            out = suitability.decide(sig, n_evaluable=n_eval, n_residual=n_res)
            self.assertTrue(out["missing_evidence"])
            for item in out["missing_evidence"]:
                self.assertEqual(set(item), {"kind", "detail", "blocking"})
                self.assertIsInstance(item["detail"], str)
                self.assertTrue(item["detail"].strip())
                self.assertIsInstance(item["blocking"], bool)

    def test_detail_is_actionable_next_step(self):
        # Every item names a concrete action, not a vague "needs more".
        out = suitability.decide(SIG_NONE, n_evaluable=0, n_residual=0)
        for item in out["missing_evidence"]:
            self.assertIn("add", item["detail"].lower(),
                          f"non-actionable detail: {item['detail']!r}")

    def test_blocking_flag_marks_the_causing_gap(self):
        # Missing-signal case: the oracle_signal gap is blocking; the lint nudge
        # is not.
        out = suitability.decide(SIG_NONE, n_evaluable=2, n_residual=0)
        by_kind = {it["kind"]: it for it in out["missing_evidence"]}
        self.assertTrue(by_kind["oracle_signal"]["blocking"])
        self.assertFalse(by_kind["lint"]["blocking"])


# --------------------------------------------------------------------------
# AC3 — verdict ⇔ list coherence
# --------------------------------------------------------------------------

class VerdictEvidenceCoherenceTests(unittest.TestCase):
    def test_needs_evidence_has_at_least_one_blocking_item(self):
        for sig, n_eval, n_res in _NEEDS_EVIDENCE_CASES:
            out = suitability.decide(sig, n_evaluable=n_eval, n_residual=n_res)
            blocking = [it for it in out["missing_evidence"] if it["blocking"]]
            self.assertTrue(blocking, f"{sig} {n_eval} {n_res} had no blocker")

    def test_suitable_has_empty_missing_evidence(self):
        out = suitability.decide(SIG_TESTS, n_evaluable=2, n_residual=0)
        self.assertEqual(out["verdict"], "suitable")
        self.assertEqual(out["missing_evidence"], [])

    def test_unsuitable_has_empty_missing_evidence(self):
        # All-residual, no-signal -> unsuitable; not a fixable evidence list.
        out = suitability.decide(SIG_NONE, n_evaluable=0, n_residual=4)
        self.assertEqual(out["verdict"], "unsuitable")
        self.assertEqual(out["missing_evidence"], [])

    def test_blocking_kinds_reflected_in_top_level_reasons(self):
        # Structural check: every blocking item contributes a dedicated
        # `missing_<kind>` reason code (stronger than a prose substring match).
        for sig, n_eval, n_res in _NEEDS_EVIDENCE_CASES:
            out = suitability.decide(sig, n_evaluable=n_eval, n_residual=n_res)
            reason_codes = {r["code"] for r in out["reasons"]}
            for item in out["missing_evidence"]:
                if item["blocking"]:
                    self.assertIn(f"missing_{item['kind']}", reason_codes,
                                  f"blocking kind {item['kind']} not in reasons")

    def test_non_blocking_kinds_not_forced_into_reasons(self):
        # Advisory (blocking=False) items must NOT manufacture a reason code —
        # only blocking gaps are reflected, so reasons stay aligned with cause.
        out = suitability.decide(SIG_NONE, n_evaluable=2, n_residual=0)
        reason_codes = {r["code"] for r in out["reasons"]}
        self.assertNotIn("missing_lint", reason_codes)
        self.assertNotIn("missing_tests", reason_codes)


# --------------------------------------------------------------------------
# AC4 — deterministic + re-runnable
# --------------------------------------------------------------------------

class MissingEvidenceRerunTests(unittest.TestCase):
    def test_same_inputs_yield_same_list(self):
        a = suitability.decide(SIG_NONE, n_evaluable=0, n_residual=0)
        b = suitability.decide(SIG_NONE, n_evaluable=0, n_residual=0)
        self.assertEqual(a["missing_evidence"], b["missing_evidence"])

    def test_stable_order_is_taxonomy_then_detail(self):
        out = suitability.decide(SIG_NONE, n_evaluable=0, n_residual=0)
        kinds = [it["kind"] for it in out["missing_evidence"]]
        rank = {k: i for i, k in enumerate(suitability.MISSING_EVIDENCE_KINDS)}
        pairs = [
            (rank[it["kind"]], it["detail"]) for it in out["missing_evidence"]
        ]
        self.assertEqual(pairs, sorted(pairs))
        # Sanity: taxonomy order places tests before reference_set.
        self.assertLess(kinds.index("tests"), kinds.index("reference_set"))

    def test_closing_the_gap_removes_item_and_flips_verdict(self):
        # No-signal target with evaluable ACs -> needs_evidence + a blocking
        # oracle_signal item. Add a test signal, re-analyze -> suitable, empty.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_NONE)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            _run_cli(target, spec, oracle_plan=plan)
            before = json.loads(_artifact_path(target).read_text())
            self.assertEqual(before["verdict"], "needs_evidence")
            kinds = {it["kind"] for it in before["missing_evidence"]}
            self.assertIn("oracle_signal", kinds)

            # Close the gap: the target now has a test signal.
            (target / ".servo" / "install.json").write_text(json.dumps(
                {"schema_version": 1, "signals": SIG_TESTS,
                 "components": [], "weights": {}}
            ))
            _run_cli(target, spec, oracle_plan=plan)
            after = json.loads(_artifact_path(target).read_text())
            self.assertEqual(after["verdict"], "suitable")
            self.assertEqual(after["missing_evidence"], [])

    def test_cli_artifact_carries_missing_evidence_for_needs_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_NONE)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=3, n_residual=0)
            res = _run_cli(target, spec, oracle_plan=plan)
            self.assertEqual(res.returncode, 0, res.stderr)
            art = json.loads(_artifact_path(target).read_text())
            self.assertEqual(art["verdict"], "needs_evidence")
            self.assertTrue(art["missing_evidence"])
            self.assertTrue(
                any(it["blocking"] for it in art["missing_evidence"])
            )


# ==========================================================================
# Slice 019-03 — shared-pipeline behavioral-AC recall + single-source guard
# ==========================================================================

# One unambiguous evaluable AC (`file_presence`) as a control, plus one
# behavioral/negative-phrasing AC that only classifies as evaluable after the
# 019-03 recall fix (oracle_plan.py::_classify_family rule 7b).
_SPEC_WITH_BEHAVIORAL_AC = (
    "# Spec 900\n\n## Acceptance Criteria\n\n"
    "1. The output file exists at the path.\n"
    "2. The lint check fails when a disallowed import is introduced.\n"
)


class SharedPipelineSuitabilityIntegrationTests(unittest.TestCase):
    """AC2 — extends `RealClassifierIntegrationTests`: because
    `suitability.py::_classify` delegates to the real `oracle_plan.py
    classify`, the same behavioral AC that reclassifies from
    `residual_judgment` to `checks` (AC1) increases `n_evaluable` in the
    suitability verdict, not just the spec-oracle plan."""

    def test_behavioral_ac_counted_as_evaluable_by_real_classifier(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_TESTS)
            spec = _make_spec(root, _SPEC_WITH_BEHAVIORAL_AC)
            res = _run_cli(target, spec, oracle_plan=REAL_ORACLE_PLAN)
            self.assertEqual(res.returncode, 0, res.stderr)
            art = json.loads(_artifact_path(target).read_text())
            counts = art["inputs"]["ac_counts"]
            # Both ACs are evaluable: the file-presence control AND the
            # behavioral AC (the pre-019-03 classifier would have counted
            # only 1 evaluable + 1 residual here).
            self.assertEqual(counts["evaluable"], 2, art)
            self.assertEqual(counts["residual"], 0, art)
            self.assertEqual(art["verdict"], "suitable")

    def test_real_classifier_via_oracle_plan_module_agrees(self):
        # Direct cross-check against oracle_plan's own classify_only, to
        # pin the exact mechanism (not just the end-to-end count above).
        oracle_plan_spec = importlib.util.spec_from_file_location(
            "oracle_plan", REAL_ORACLE_PLAN)
        oracle_plan = importlib.util.module_from_spec(oracle_plan_spec)
        oracle_plan_spec.loader.exec_module(oracle_plan)

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec = _make_spec(root, _SPEC_WITH_BEHAVIORAL_AC)
            plan = oracle_plan.classify_only(spec, None)
            self.assertEqual(len(plan["checks"]), 2)
            self.assertEqual(len(plan["residual_judgment"]), 0)


class NoDuplicateACParserTests(unittest.TestCase):
    """AC3 — regression guard: `suitability.py::_classify` must genuinely
    invoke `oracle_plan.py`'s `classify` entrypoint via subprocess, not a
    private/duplicate parser. If a future edit forks the two back apart
    (re-implements AC parsing/classification inside suitability.py instead of
    delegating), this test fails CI immediately."""

    def test_classify_subprocess_targets_oracle_plan_by_default(self):
        # The default env-unset path resolves to oracle_plan.py, not some
        # other script or an inline parser.
        self.assertEqual(
            suitability.DEFAULT_ORACLE_PLAN.name, "oracle_plan.py",
            "suitability.py's default classifier target must be oracle_plan.py",
        )
        self.assertTrue(
            suitability.DEFAULT_ORACLE_PLAN.is_file(),
            f"{suitability.DEFAULT_ORACLE_PLAN} does not exist",
        )

    def test_classify_invokes_the_given_oracle_plan_path_via_subprocess(self):
        # Spy on subprocess.run to confirm _classify's argv actually names
        # the oracle_plan_path argument's script — no private parser is
        # consulted instead. A fake path is used to prove wiring, not a
        # real classification (no need to run the real script for this AC).
        calls = []
        real_run = subprocess.run

        def spy(args, **kwargs):
            calls.append(args)
            return real_run(args, **kwargs)

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=1, n_residual=0)
            with unittest.mock.patch("subprocess.run", side_effect=spy):
                result = suitability._classify(spec, plan)

        self.assertTrue(calls, "suitability._classify must call subprocess.run")
        argv = calls[0]
        self.assertEqual(
            Path(argv[1]).name, plan.name,
            "the subprocess argv's script must be the oracle_plan_path passed in "
            "(the single shared classify entrypoint), not a hardcoded/private path",
        )
        self.assertIn("classify", argv, "must invoke oracle_plan's `classify` subcommand")
        self.assertEqual(len(result["checks"]), 1)

    def test_module_defines_no_private_ac_family_classifier(self):
        # suitability.py must not define its own `_classify_family` /
        # `classify_acs` — that logic lives exactly once, in oracle_plan.py.
        self.assertFalse(
            hasattr(suitability, "_classify_family"),
            "suitability.py must not define a private _classify_family — "
            "it must delegate to oracle_plan.py's classify entrypoint",
        )
        self.assertFalse(
            hasattr(suitability, "classify_acs"),
            "suitability.py must not define a private classify_acs — "
            "it must delegate to oracle_plan.py's classify entrypoint",
        )



# ==========================================================================
# Slice 030-01 — eval-component-signal (ADR-0036)
#
# `has_signal` is additionally satisfied by a reviewed, frozen, installed eval
# component, read purely from the two manifests servo already writes
# (install.json `components` + the eval's `.servo/<dir>/config.json` freeze
# facts). Only `approval_provenance: "reviewed"` credits. A judged-only signal
# yields `suitable` + a non-blocking counterweight advisory. tests/ci artifacts
# stay byte-identical. The eval widens only the signal leg — a purely-residual
# design spec (n_evaluable == 0) stays needs_evidence (AC6).
# ==========================================================================

# signals with NO deterministic signal (the eval is the only candidate).
SIG_EVAL_BASE = {"tests": False, "lint": False, "ci": False, "language": "python"}

# The reverse dir alias the slice keys on (mirrors suitability._EVAL_COMPONENT_DIRS).
_EVAL_DIRS = {"design_fidelity": "design-eval", "content_fidelity": "content-fidelity"}


def _write_install(target: Path, signals: dict, components: list) -> None:
    (target / ".servo" / "install.json").write_text(json.dumps(
        {"schema_version": 1, "signals": signals, "components": components,
         "weights": {}}
    ))


def _write_eval_config(target: Path, component: str, *,
                       status="approved", provenance="reviewed",
                       hashes=("score.py",), content_hash="deadbeef",
                       raw=None) -> None:
    """Write `<target>/.servo/<dir>/config.json` for `component`.

    Each freeze fact is independently suppressible so a negative fixture can
    neuter exactly one predicate (keeping every other fact valid — the mutation
    isolation AC2's DoD requires). `status=None` / `provenance=None` /
    `content_hash=None` omits that key; `hashes=()` writes an empty map;
    `raw=<str>` writes the config bytes verbatim (malformed-JSON fixture).
    """
    dir_name = _EVAL_DIRS.get(component, component)
    d = target / ".servo" / dir_name
    d.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        (d / "config.json").write_text(raw)
        return
    cfg: dict = {}
    if status is not None:
        cfg["approval_status"] = status
    if provenance is not None:
        cfg["approval_provenance"] = provenance
    cfg["hashes"] = {name: f"h-{name}" for name in hashes}
    if content_hash is not None:
        cfg["approved_content_hash"] = content_hash
    (d / "config.json").write_text(json.dumps(cfg))


def _blocking_kinds(art: dict) -> set:
    return {it["kind"] for it in art["missing_evidence"] if it["blocking"]}


def _advisory_kinds(art: dict) -> set:
    return {it["kind"] for it in art["missing_evidence"] if not it["blocking"]}


# --------------------------------------------------------------------------
# AC1 — a reviewed + frozen + registered eval alone flips to suitable + advisory
# --------------------------------------------------------------------------

class EvalSignalPositiveTests(unittest.TestCase):
    def test_reviewed_frozen_registered_eval_alone_is_suitable_with_advisory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_EVAL_BASE)
            _write_install(target, SIG_EVAL_BASE, ["design_fidelity"])
            _write_eval_config(target, "design_fidelity")  # approved+reviewed+frozen
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            res = _run_cli(target, spec, oracle_plan=plan)
            self.assertEqual(res.returncode, 0, res.stderr)
            art = json.loads(_artifact_path(target).read_text())
            self.assertEqual(art["verdict"], "suitable")
            # A reason code that NAMES the eval-signal source, distinct from the
            # deterministic-signal code.
            codes = [r["code"] for r in art["reasons"]]
            self.assertIn("evaluable_acs_with_eval_signal", codes)
            self.assertNotIn("evaluable_acs_with_signal", codes)
            # Non-blocking advisory on tests/ci; NO blocking item at all.
            self.assertEqual(_blocking_kinds(art), set())
            self.assertTrue({"tests", "ci"}.issubset(_advisory_kinds(art)))
            for it in art["missing_evidence"]:
                self.assertFalse(it["blocking"])

    def test_content_fidelity_dir_alias_resolves(self):
        # The second blessed preset: content_fidelity -> .servo/content-fidelity/.
        # (content-fidelity's real freeze records no provenance today, but a
        # manifest that DOES carry reviewed provenance must credit — the gate is
        # domain-agnostic, keyed on the recorded facts, not the producer.)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_EVAL_BASE)
            _write_install(target, SIG_EVAL_BASE, ["content_fidelity"])
            _write_eval_config(target, "content_fidelity")
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=1, n_residual=0)
            _run_cli(target, spec, oracle_plan=plan)
            art = json.loads(_artifact_path(target).read_text())
            self.assertEqual(art["verdict"], "suitable", art)

    def test_eval_authoring_dir_equals_component_name(self):
        # Eval-authoring components live at .servo/<component>/ (dir == name).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_EVAL_BASE)
            _write_install(target, SIG_EVAL_BASE, ["spec900_ac1"])
            _write_eval_config(target, "spec900_ac1")  # dir "spec900_ac1"
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=1, n_residual=0)
            _run_cli(target, spec, oracle_plan=plan)
            art = json.loads(_artifact_path(target).read_text())
            self.assertEqual(art["verdict"], "suitable", art)


# --------------------------------------------------------------------------
# AC2 — unfrozen / unapproved / self-approved / provenance-less / unregistered /
#        malformed never counts (each isolates ONE fail-closed predicate so the
#        mutation DoD holds: neuter that predicate and the fixture flips to
#        suitable, going red).
# --------------------------------------------------------------------------

class EvalSignalNegativeTests(unittest.TestCase):
    def _assert_refused(self, target, spec, plan):
        """A non-crediting eval leaves today's verdict: signals all false +
        >=1 evaluable AC -> needs_evidence with the blocking oracle_signal."""
        res = _run_cli(target, spec, oracle_plan=plan)
        self.assertEqual(res.returncode, 0, res.stderr)
        art = json.loads(_artifact_path(target).read_text())
        self.assertEqual(art["verdict"], "needs_evidence", art)
        self.assertIn("oracle_signal", _blocking_kinds(art))
        codes = [r["code"] for r in art["reasons"]]
        self.assertIn("evaluable_acs_no_signal", codes)
        self.assertNotIn("evaluable_acs_with_eval_signal", codes)
        return art

    def _target(self, root):
        target = _make_target(root, SIG_EVAL_BASE)
        _write_install(target, SIG_EVAL_BASE, ["design_fidelity"])
        return target

    def test_a_unapproved_status_does_not_count(self):
        # (a) approval_status "draft" — every other fact valid (isolates status).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = self._target(root)
            _write_eval_config(target, "design_fidelity", status="draft")
            self._assert_refused(target, _make_spec(root),
                                 _stub_oracle_plan(root, n_checks=2, n_residual=0))

    def test_a2_absent_status_does_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = self._target(root)
            _write_eval_config(target, "design_fidelity", status=None)
            self._assert_refused(target, _make_spec(root),
                                 _stub_oracle_plan(root, n_checks=2, n_residual=0))

    def test_b_unfrozen_empty_hashes_does_not_count(self):
        # (b) never frozen: empty hashes map — status/provenance/hash all valid
        # (isolates the hashes predicate).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = self._target(root)
            _write_eval_config(target, "design_fidelity", hashes=())
            self._assert_refused(target, _make_spec(root),
                                 _stub_oracle_plan(root, n_checks=2, n_residual=0))

    def test_c_unregistered_component_does_not_count(self):
        # (c) config fully approved+frozen+reviewed but NOT in components —
        # isolates the install.json membership check. Also fences the
        # scaffold-init --force case (ADR-0036 Verification): the wholesale
        # install.json rewrite erases the registration while the config survives,
        # so the surviving config alone must NOT credit.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_EVAL_BASE)
            _write_install(target, SIG_EVAL_BASE, [])  # registration erased
            _write_eval_config(target, "design_fidelity")  # valid config survives
            self._assert_refused(target, _make_spec(root),
                                 _stub_oracle_plan(root, n_checks=2, n_residual=0))

    def test_d_self_approved_provenance_does_not_count(self):
        # (d) approved+frozen but self_approved — isolates the provenance check.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = self._target(root)
            _write_eval_config(target, "design_fidelity", provenance="self_approved")
            self._assert_refused(target, _make_spec(root),
                                 _stub_oracle_plan(root, n_checks=2, n_residual=0))

    def test_e_provenanceless_does_not_count(self):
        # (e) approved+frozen with NO provenance field (today's content-fidelity
        # / eval-authoring stamps) — also the provenance predicate.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = self._target(root)
            _write_eval_config(target, "design_fidelity", provenance=None)
            self._assert_refused(target, _make_spec(root),
                                 _stub_oracle_plan(root, n_checks=2, n_residual=0))

    def test_f_missing_content_hash_does_not_count(self):
        # (f) approved+reviewed+hashes present but no approved_content_hash —
        # isolates the approved_content_hash predicate (ADR-0036 names it a
        # required freeze fact).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = self._target(root)
            _write_eval_config(target, "design_fidelity", content_hash=None)
            self._assert_refused(target, _make_spec(root),
                                 _stub_oracle_plan(root, n_checks=2, n_residual=0))

    def test_g_malformed_config_fails_closed_no_env_error(self):
        # (g) unreadable/malformed per-eval config -> no eval signal (fail-closed),
        # NEVER an env-error exit and NEVER a torn artifact (ADR-0036 guardrail 4).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = self._target(root)
            _write_eval_config(target, "design_fidelity", raw="{ not json ]")
            art = self._assert_refused(
                target, _make_spec(root),
                _stub_oracle_plan(root, n_checks=2, n_residual=0))
            self.assertEqual(art["schema_version"], 1)

    def test_config_absent_entirely_does_not_count(self):
        # components names a component with NO config dir at all -> fail-closed.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_EVAL_BASE)
            _write_install(target, SIG_EVAL_BASE, ["design_fidelity"])  # no config written
            self._assert_refused(target, _make_spec(root),
                                 _stub_oracle_plan(root, n_checks=2, n_residual=0))


# --------------------------------------------------------------------------
# AC3 — tests/ci behavior is byte-identical (with AND without an eval present)
# --------------------------------------------------------------------------

# Golden `decide()` outputs captured from the PRE-030-01 implementation for a
# representative slice of the 015-01/02 tests/ci matrix. The post-slice decide()
# must reproduce these byte-for-byte for any eval_signal value.
_GOLDEN_DECIDE = {
    # (tests, ci, lint, n_eval, n_res): decision
    (True, False, False, 2, 0): {
        "verdict": "suitable",
        "reasons": [{"code": "evaluable_acs_with_signal",
                     "message": "EDD-shaped: evaluable ACs and a compilable "
                                "test/CI signal are both present (2 evaluable "
                                "AC(s), 0 residual AC(s), a test/CI signal)"}],
        "missing_evidence": [],
    },
    (True, False, False, 0, 2): {
        "verdict": "needs_evidence",
        "reasons": [
            {"code": "signal_without_evaluable_acs",
             "message": "a test/CI signal exists but no evaluable ACs to gate "
                        "on (0 evaluable AC(s), 2 residual AC(s), a test/CI "
                        "signal)"},
            {"code": "missing_reference_set",
             "message": "no evaluable acceptance criteria detected; add at "
                        "least one deterministically-checkable AC (or a "
                        "reference set) so the oracle has something to gate on"},
        ],
        "missing_evidence": [
            {"kind": "lint", "detail": "no lint signal detected; adding one "
                                       "strengthens the oracle but is not "
                                       "required for suitability on its own",
             "blocking": False},
            {"kind": "reference_set", "detail": "no evaluable acceptance "
                                                "criteria detected; add at "
                                                "least one deterministically-"
                                                "checkable AC (or a reference "
                                                "set) so the oracle has "
                                                "something to gate on",
             "blocking": True},
        ],
    },
    (False, True, False, 3, 1): {
        "verdict": "suitable",
        "reasons": [{"code": "evaluable_acs_with_signal",
                     "message": "EDD-shaped: evaluable ACs and a compilable "
                                "test/CI signal are both present (3 evaluable "
                                "AC(s), 1 residual AC(s), a test/CI signal)"}],
        "missing_evidence": [],
    },
    (True, True, True, 0, 0): {
        "verdict": "needs_evidence",
        "reasons": [
            {"code": "signal_without_evaluable_acs",
             "message": "a test/CI signal exists but no evaluable ACs to gate "
                        "on (0 evaluable AC(s), 0 residual AC(s), a test/CI "
                        "signal)"},
            {"code": "missing_reference_set",
             "message": "no evaluable acceptance criteria detected; add at "
                        "least one deterministically-checkable AC (or a "
                        "reference set) so the oracle has something to gate on"},
        ],
        "missing_evidence": [
            {"kind": "reference_set", "detail": "no evaluable acceptance "
                                                "criteria detected; add at "
                                                "least one deterministically-"
                                                "checkable AC (or a reference "
                                                "set) so the oracle has "
                                                "something to gate on",
             "blocking": True},
        ],
    },
}


class EvalSignalByteIdentityTests(unittest.TestCase):
    def test_tests_ci_decide_byte_identical_to_pre_slice_golden(self):
        for (t, c, lint, ne, nr), expected in _GOLDEN_DECIDE.items():
            sig = {"tests": t, "ci": c, "lint": lint, "language": "python"}
            for ev in (False, True):  # with AND without an eval component
                got = suitability.decide(sig, n_evaluable=ne, n_residual=nr,
                                         eval_signal=ev)
                self.assertEqual(got, expected,
                                 f"byte drift at tests={t} ci={c} lint={lint} "
                                 f"n_eval={ne} n_res={nr} eval_signal={ev}")

    def test_eval_signal_is_inert_when_a_deterministic_signal_exists(self):
        # Exhaustive small grid: whenever tests|ci is truthy, the eval signal
        # changes nothing in the decision (the whole artifact-level AC3).
        for t in (True, False):
            for c in (True, False):
                if not (t or c):
                    continue
                for ne in (0, 1, 2):
                    for nr in (0, 2):
                        sig = {"tests": t, "ci": c, "lint": False,
                               "language": "python"}
                        a = suitability.decide(sig, n_evaluable=ne,
                                               n_residual=nr, eval_signal=False)
                        b = suitability.decide(sig, n_evaluable=ne,
                                               n_residual=nr, eval_signal=True)
                        self.assertEqual(a, b)

    def test_cli_artifact_byte_identical_with_and_without_eval_component(self):
        # End to end: a tests-truthy target, once with a valid reviewed+frozen
        # eval component present and once without — the persisted artifact is
        # byte-identical (modulo the volatile analyzed_at timestamp).
        def _run(with_eval: bool) -> dict:
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                target = _make_target(root, SIG_TESTS)
                comps = ["design_fidelity"] if with_eval else []
                _write_install(target, SIG_TESTS, comps)
                if with_eval:
                    _write_eval_config(target, "design_fidelity")
                spec = _make_spec(root)
                plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
                _run_cli(target, spec, oracle_plan=plan)
                art = json.loads(_artifact_path(target).read_text())
                art.pop("analyzed_at", None)
                return art
        self.assertEqual(_run(with_eval=True), _run(with_eval=False))
        # And the eval signal is NOT leaked into the persisted inputs.
        art = _run(with_eval=True)
        self.assertNotIn("eval_signal", json.dumps(art))


# --------------------------------------------------------------------------
# AC4 — the no-signal remedy list is truthful (names all three remedies)
# --------------------------------------------------------------------------

class NoSignalRemedyTruthfulnessTests(unittest.TestCase):
    def test_oracle_signal_detail_names_all_three_remedies(self):
        out = suitability.decide(SIG_EVAL_BASE, n_evaluable=2, n_residual=0,
                                 eval_signal=False)
        self.assertEqual(out["verdict"], "needs_evidence")
        osig = next(it for it in out["missing_evidence"]
                    if it["kind"] == "oracle_signal")
        detail = osig["detail"].lower()
        self.assertIn("test", detail)
        self.assertIn("ci", detail)
        # The third remedy — a reviewed, frozen eval component — is now named.
        self.assertIn("reviewed", detail)
        self.assertIn("frozen", detail)
        self.assertIn("eval", detail)

    def test_missing_oracle_signal_reason_mirror_still_holds(self):
        # 015-02 AC3 coherence: the blocking oracle_signal kind is reflected as a
        # dedicated missing_oracle_signal reason code.
        out = suitability.decide(SIG_EVAL_BASE, n_evaluable=2, n_residual=0,
                                 eval_signal=False)
        self.assertIn("missing_oracle_signal",
                      {r["code"] for r in out["reasons"]})


# --------------------------------------------------------------------------
# AC6 — scope boundary: the eval widens the SIGNAL leg, not the evaluable-AC leg.
#        A purely-residual design spec (n_evaluable == 0 under the REAL
#        classifier) stays needs_evidence even with a reviewed+frozen eval.
# --------------------------------------------------------------------------

_ALL_RESIDUAL_DESIGN_SPEC = (
    "# Spec 999: build the login screen to the redline\n\n"
    "## Acceptance Criteria\n\n"
    "1. The login screen matches the design mockup.\n"
    "2. The button colors match the redline.\n"
    "3. The spacing and typography match the Figma reference.\n"
)

# A *realistic* design-led spec: ≥1 AC the real classifier recognises as
# deterministic (AC1 -> file_presence) alongside visual-fidelity ACs.
_MIXED_DESIGN_SPEC = (
    "# Spec 888: build the login screen to the redline\n\n"
    "## Acceptance Criteria\n\n"
    "1. The built `dist/index.html` file is present.\n"
    "2. The login screen matches the design mockup.\n"
    "3. The button colors match the redline.\n"
)


class EvalSignalScopeBoundaryTests(unittest.TestCase):
    # AC6 asserts BOTH ends of the unsuitable -> needs_evidence delta (a testless
    # target class AC3's byte-identity fence does not cover): with the eval the
    # all-residual spec is needs_evidence; without any signal it is the terminal
    # unsuitable. The eval upgrades terminal -> recoverable, never to suitable.
    def test_all_residual_design_spec_with_eval_is_needs_evidence_never_suitable(self):
        # Uses the REAL oracle_plan classifier (not the stub), so the test pins
        # that visual-fidelity ACs classify as residual (n_evaluable == 0) and
        # the eval signal does NOT by itself make the spec suitable.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_EVAL_BASE)
            _write_install(target, SIG_EVAL_BASE, ["design_fidelity"])
            _write_eval_config(target, "design_fidelity")  # reviewed+frozen
            spec = _make_spec(root, _ALL_RESIDUAL_DESIGN_SPEC)
            res = _run_cli(target, spec, oracle_plan=REAL_ORACLE_PLAN)
            self.assertEqual(res.returncode, 0, res.stderr)
            art = json.loads(_artifact_path(target).read_text())
            # n_evaluable == 0 from the real classifier.
            self.assertEqual(art["inputs"]["ac_counts"]["evaluable"], 0, art)
            # The eval signal IS active: the reason is signal_without_evaluable_acs
            # (which requires has_signal == True) — NOT all_acs_residual_no_signal
            # (the no-eval verdict for the same spec would be unsuitable). This
            # proves the eval is credited yet the verdict stays needs_evidence.
            self.assertEqual(art["verdict"], "needs_evidence", art)
            codes = [r["code"] for r in art["reasons"]]
            self.assertIn("signal_without_evaluable_acs", codes)
            self.assertIn("reference_set", _blocking_kinds(art))

    def test_same_all_residual_spec_without_eval_is_unsuitable(self):
        # The OTHER end of the AC6 delta: with NO signal at all the same
        # all-residual spec is the terminal `unsuitable` (all_acs_residual_no_signal,
        # "route to a human"). The eval upgrades this to the recoverable
        # `needs_evidence` above — never to suitable — and a regression can
        # restore neither end.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_EVAL_BASE)
            _write_install(target, SIG_EVAL_BASE, [])  # no eval
            spec = _make_spec(root, _ALL_RESIDUAL_DESIGN_SPEC)
            _run_cli(target, spec, oracle_plan=REAL_ORACLE_PLAN)
            art = json.loads(_artifact_path(target).read_text())
            self.assertEqual(art["verdict"], "unsuitable", art)
            self.assertIn("all_acs_residual_no_signal",
                          [r["code"] for r in art["reasons"]])

    # AC7 — the positive realistic case, proven through the REAL classifier.
    def test_realistic_mixed_design_spec_with_eval_is_suitable(self):
        # ≥1 deterministically-phrased AC (AC1 -> file_presence under the real
        # classifier) + visual-fidelity ACs + a reviewed, frozen, registered eval
        # -> suitable via the eval signal, with the counterweight advisory.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_EVAL_BASE)
            _write_install(target, SIG_EVAL_BASE, ["design_fidelity"])
            _write_eval_config(target, "design_fidelity")
            spec = _make_spec(root, _MIXED_DESIGN_SPEC)
            res = _run_cli(target, spec, oracle_plan=REAL_ORACLE_PLAN)
            self.assertEqual(res.returncode, 0, res.stderr)
            art = json.loads(_artifact_path(target).read_text())
            self.assertGreaterEqual(
                art["inputs"]["ac_counts"]["evaluable"], 1, art)
            self.assertEqual(art["verdict"], "suitable", art)
            self.assertIn("evaluable_acs_with_eval_signal",
                          [r["code"] for r in art["reasons"]])
            self.assertEqual(_blocking_kinds(art), set())
            self.assertTrue({"tests", "ci"}.issubset(_advisory_kinds(art)))

    def test_realistic_mixed_design_spec_without_eval_is_needs_evidence(self):
        # Control: same spec, NO eval -> needs_evidence (evaluable AC but no
        # signal). Proves the eval signal is what flips AC7 to suitable.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = _make_target(root, SIG_EVAL_BASE)
            _write_install(target, SIG_EVAL_BASE, [])
            spec = _make_spec(root, _MIXED_DESIGN_SPEC)
            _run_cli(target, spec, oracle_plan=REAL_ORACLE_PLAN)
            art = json.loads(_artifact_path(target).read_text())
            self.assertEqual(art["verdict"], "needs_evidence", art)
            self.assertIn("evaluable_acs_no_signal",
                          [r["code"] for r in art["reasons"]])


# --------------------------------------------------------------------------
# Alias-map drift guard (DoR / ADR-0036 kill criterion): the reverse dir map the
# gate keys on must match the eval producers' forward (COMPONENT, dir) pairs.
# --------------------------------------------------------------------------

class EvalAliasMapDriftTests(unittest.TestCase):
    def test_module_alias_map_is_the_closed_set(self):
        self.assertEqual(
            suitability._EVAL_COMPONENT_DIRS,
            {"design_fidelity": "design-eval",
             "content_fidelity": "content-fidelity"},
        )

    def test_eval_authoring_components_resolve_dir_equals_name(self):
        # An unmapped component (eval-authoring) resolves to its own name.
        self.assertEqual(suitability._eval_config_dir("spec900_ac1"),
                         "spec900_ac1")

    def test_alias_map_matches_producer_source(self):
        # Drift guard against the producers without importing them (their deps
        # are heavy): the forward (COMPONENT, dir) each producer stamps must be
        # the reverse of suitability._EVAL_COMPONENT_DIRS.
        design = (REPO_ROOT / "skills" / "design-eval" / "design_eval.py").read_text()
        content = (REPO_ROOT / "skills" / "content-fidelity"
                   / "content_fidelity.py").read_text()
        self.assertIn('COMPONENT = "design_fidelity"', design)
        self.assertIn('"design-eval"', design)
        self.assertIn('COMPONENT = "content_fidelity"', content)
        self.assertIn('"content-fidelity"', content)
        for component, dir_name in suitability._EVAL_COMPONENT_DIRS.items():
            src = design if component == "design_fidelity" else content
            self.assertIn(f'COMPONENT = "{component}"', src)
            self.assertIn(f'"{dir_name}"', src)


# --------------------------------------------------------------------------
# Reconciliation-phase coverage (030-01 review nits: rule-3 source-aware
# message, render_human reason-code keying, path-separator guard, and the
# compliance coverage gap — non-list components + judged-only --explain).
# --------------------------------------------------------------------------

class EvalSignalReconCoverageTests(unittest.TestCase):
    def test_eval_signal_non_list_components_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            self.assertFalse(suitability._eval_signal(target, {"not": "a list"}))
            self.assertFalse(suitability._eval_signal(target, None))
            self.assertFalse(suitability._eval_signal(target, "design_fidelity"))

    def test_eval_signal_skips_non_string_entries(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            self.assertFalse(
                suitability._eval_signal(target, [123, None, {"x": 1}]))

    def test_path_separator_component_name_fails_closed(self):
        # Defense-in-depth: a component name with a path separator / traversal
        # never reaches the filesystem, even if a fully-valid reviewed+frozen
        # config sits at the traversed path.
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            evil = target / ".servo" / "evil"
            evil.mkdir(parents=True)
            (evil / "config.json").write_text(json.dumps({
                "approval_status": "approved",
                "approval_provenance": "reviewed",
                "hashes": {"x": "y"}, "approved_content_hash": "h"}))
            for bad in ("../evil", "..", "a/b", "a\\b", "."):
                self.assertFalse(
                    suitability._is_reviewed_frozen_eval(target, bad), bad)
            # And via the public entrypoint.
            self.assertFalse(suitability._eval_signal(target, ["../evil"]))

    def test_rule3_message_is_signal_source_aware(self):
        # The eval-only signal_without_evaluable_acs message must not claim
        # "a test/CI signal" (AC4 truthfulness, extended to rule 3).
        ev = {"tests": False, "ci": False, "lint": False, "language": "python"}
        out = suitability.decide(ev, n_evaluable=0, n_residual=3,
                                 eval_signal=True)
        msg = out["reasons"][0]["message"]
        self.assertIn("reviewed, frozen eval signal", msg)
        self.assertNotIn("test/CI signal exists", msg)
        # The deterministic case keeps the exact pre-slice prose (AC3 fence).
        det = suitability.decide(
            {"tests": True, "ci": False, "lint": False, "language": "python"},
            n_evaluable=0, n_residual=3)
        self.assertIn(
            "a test/CI signal exists but no evaluable ACs to gate on",
            det["reasons"][0]["message"])

    def test_render_human_keys_judged_only_on_reason_code_not_advisory(self):
        # The judged-only advisory block is gated on the decided reason code, so
        # a hypothetical deterministic-signal suitable carrying advisory items
        # would NOT print the "sole signal" line.
        art = {
            "verdict": "suitable", "spec_id": "x",
            "reasons": [{"code": "evaluable_acs_with_signal", "message": "m"}],
            "missing_evidence": [
                {"kind": "tests", "detail": "add a test", "blocking": False}],
        }
        out = suitability.render_human(art, Path("/tmp/x.json"))
        self.assertNotIn("sole signal", out)
        self.assertNotIn("advisory", out.lower())

    def test_explain_trace_surfaces_eval_signal_on_judged_only(self):
        # Coverage: the build_trace / render_trace judged-only --explain path.
        with tempfile.TemporaryDirectory() as dd:
            root = Path(dd)
            target = _make_target(root, SIG_EVAL_BASE)
            _write_install(target, SIG_EVAL_BASE, ["design_fidelity"])
            _write_eval_config(target, "design_fidelity")
            spec = _make_spec(root)
            plan = _stub_oracle_plan(root, n_checks=2, n_residual=0)
            env = dict(os.environ)
            env["SERVO_SUITABILITY_ORACLE_PLAN"] = str(plan)
            r = subprocess.run(
                [sys.executable, str(SUITABILITY), "analyze", str(target),
                 "--spec", str(spec), "--explain"],
                capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("eval_signal=True", r.stdout)
            self.assertIn("evaluable_acs_with_eval_signal", r.stdout)

if __name__ == "__main__":
    unittest.main()
