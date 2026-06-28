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

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
