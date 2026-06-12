"""Tests for the design-fidelity eval component (servo design-eval).

Exercises the freeze contract, the n-sample lower-bound aggregation, the
fail-closed honesty (stale / env_error → exit 2, never 0.0), and the oracle.sh
splice — all without an API key or a browser (the fake-scores hook).

Run:  python3 skills/design-eval/test_design_eval.py
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


score = _load("design_eval_score", "score.py")
de = _load("design_eval_cli", "design_eval.py")


def _base_config(rubric="Score layout/palette/type fidelity 0..1."):
    return {
        "schema_version": 1,
        "approval_status": "draft",
        "viewport": {"width": 392, "height": 812, "deviceScaleFactor": 2},
        "app_url": "http://localhost:4173/",
        "judge": {"model": "claude-sonnet-4-6", "temperature": 0.0, "max_tokens": 1024},
        "samples": {"n": 4, "k": 1.0, "delta": 0.03},
        "threshold": 0.8,
        "rubric": rubric,
        "screens": [
            {"id": "home", "reference": "refs/home.png", "weight": 1.0},
            {"id": "settings", "reference": "refs/settings.png", "weight": 1.0},
        ],
    }


def _make_eval_dir(tmp: Path, config=None):
    d = tmp / ".servo" / "design-eval"
    (d / "refs").mkdir(parents=True, exist_ok=True)
    (d / "refs" / "home.png").write_bytes(b"\x89PNG-home")
    (d / "refs" / "settings.png").write_bytes(b"\x89PNG-settings")
    (d / "config.json").write_text(json.dumps(config or _base_config(), indent=2))
    return d


class AggregationTests(unittest.TestCase):
    def test_lower_bound_below_mean_when_noisy(self):
        lb = score.aggregate_lower_bound([0.9, 0.7, 0.8, 0.6], 1.0)
        self.assertLess(lb, 0.75)  # mean 0.75 minus a real stderr

    def test_single_sample_has_no_stderr(self):
        self.assertAlmostEqual(score.aggregate_lower_bound([0.83], 1.0), 0.83)

    def test_confident_samples_stay_high(self):
        lb = score.aggregate_lower_bound([0.90, 0.90, 0.90, 0.90], 1.0)
        self.assertAlmostEqual(lb, 0.90)

    def test_clamped_to_unit_interval(self):
        self.assertEqual(score.aggregate_lower_bound([0.05, 0.0, 0.0], 5.0), 0.0)
        self.assertEqual(score.aggregate_lower_bound([1.0, 1.0], 1.0), 1.0)


class FreezeTests(unittest.TestCase):
    def test_freeze_then_validate_passes(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            self.assertEqual(config["approval_status"], "approved")
            score.validate_freeze(config, d)  # no raise

    def test_unapproved_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            with self.assertRaises(score.StaleError):
                score.validate_freeze(json.loads((d / "config.json").read_text()), d)

    def test_tampered_reference_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            (d / "refs" / "home.png").write_bytes(b"\x89PNG-TAMPERED")
            with self.assertRaises(score.StaleError):
                score.validate_freeze(json.loads((d / "config.json").read_text()), d)

    def test_changed_rubric_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            config["rubric"] = "different rubric"
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, d)

    def test_changed_definition_is_stale(self):
        # Bumping the model id / n / threshold must invalidate the freeze.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            config["judge"]["model"] = "claude-haiku-4-5-20251001"
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, d)

    def test_freeze_refuses_missing_reference(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            (d / "refs" / "home.png").unlink()
            with self.assertRaises(FileNotFoundError):
                de.freeze(tmp)


class ScoreHonestyTests(unittest.TestCase):
    """Stale / env_error → exit 2; a valid frozen run with fake scores → 0 + float."""

    def setUp(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop(score._FAKE_SCORES_ENV, None)

    def tearDown(self):
        os.environ.pop(score._FAKE_SCORES_ENV, None)

    def test_env_error_when_no_key_and_no_fake(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            rc, out, err = _capture_main(d)
            self.assertEqual(rc, score.EXIT_ENV_ERROR)
            self.assertEqual(out.strip(), "")  # never a 0.0 on the env-error path
            self.assertIn("env_error", err)

    def test_stale_exits_2_not_zero(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)  # not frozen → stale
            os.environ[score._FAKE_SCORES_ENV] = json.dumps({"home": [0.9], "settings": [0.9]})
            rc, out, err = _capture_main(d)
            self.assertEqual(rc, score.EXIT_ENV_ERROR)
            self.assertEqual(out.strip(), "")  # never prints a 0.0 on the stale path
            self.assertIn("stale", err)

    def test_fake_scores_happy_path_composite(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            os.environ[score._FAKE_SCORES_ENV] = json.dumps(
                {"home": [0.80, 0.82, 0.78, 0.80], "settings": [0.90, 0.90, 0.90, 0.90]})
            rc, out, _ = _capture_main(d)
            self.assertEqual(rc, score.EXIT_OK)
            composite = float(out.strip())
            self.assertGreater(composite, 0.7)
            self.assertLessEqual(composite, 1.0)
            # ledger written
            self.assertTrue((d / "ledger.jsonl").is_file())


class InstallTests(unittest.TestCase):
    ORACLE = (
        "#!/usr/bin/env bash\nset -euo pipefail\nTHRESHOLD=\"${THRESHOLD:-0.5}\"\n"
        "COMPONENTS=(\n  \"vitest:1.0\"\n)\n\nweighted_sum=\"0\"\ntotal_weight=\"0\"\n"
    )

    def _target(self, tmp: Path):
        (tmp / ".servo").mkdir(parents=True, exist_ok=True)
        (tmp / "oracle.sh").write_text(self.ORACLE)
        (tmp / ".servo" / "install.json").write_text(json.dumps({"components": ["vitest"]}))
        # design-eval dir + config so install's init() has something to copy into
        _make_eval_dir(tmp)

    def test_install_splices_component_and_registers(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            de.install(tmp, weight=2.0)
            text = (tmp / "oracle.sh").read_text()
            self.assertIn("# SEED:start design_fidelity", text)
            self.assertIn("score_design_fidelity()", text)
            self.assertIn('"design_fidelity:2.0"', text)
            self.assertIn('"vitest:1.0"', text)  # baseline untouched
            manifest = json.loads((tmp / ".servo" / "install.json").read_text())
            self.assertIn("design_fidelity", manifest["components"])

    def test_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            de.install(tmp, weight=1.0)
            de.install(tmp, weight=3.0)  # re-install refreshes weight, no dup
            text = (tmp / "oracle.sh").read_text()
            self.assertEqual(text.count("# SEED:start design_fidelity"), 1)
            self.assertIn('"design_fidelity:3.0"', text)
            self.assertNotIn('"design_fidelity:1.0"', text)

    def test_uninstall_removes_component(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            de.install(tmp)
            de.uninstall(tmp)
            text = (tmp / "oracle.sh").read_text()
            self.assertNotIn("design_fidelity", text)
            self.assertIn('"vitest:1.0"', text)


# --- helper: run score.main() with the eval dir as the script's base dir ---

def _capture_main(eval_dir: Path):
    # Ensure the eval dir has a score.py copy whose __file__ is in the eval dir.
    import shutil as _sh
    if not (eval_dir / "score.py").is_file():
        _sh.copyfile(HERE / "score.py", eval_dir / "score.py")
    mod = _load("design_eval_score_run", str(eval_dir / "score.py"))
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = mod.main([])
    return rc, out.getvalue(), err.getvalue()


if __name__ == "__main__":
    unittest.main()
