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

    def test_changed_viewport_is_stale(self):
        # design-eval pins "viewport" into the definition hash via its
        # score.py wrapper's extra_fields argument (not hardcoded in the
        # shared module) — changing it must still invalidate the freeze.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            config["viewport"]["width"] = 1024
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, d)

    def test_definition_hash_unchanged_for_pre_existing_frozen_config(self):
        # Regression pin (020-01 fix round): generalizing definition_hash to
        # take extra_fields instead of hardcoding "viewport" must not change
        # the hash design-eval already produced/approved for this exact
        # config shape — a pre-existing frozen config.json's
        # approved_content_hash must still validate.
        config = _base_config()
        h = score.definition_hash(config)
        self.assertEqual(
            h, "sha256:4837a50759f77e0d55003a3328c3bf9ec1d203f3509b636ce28b63b303aa3e08")


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
            # ...and the install manifest is deregistered symmetrically (no drift).
            manifest = json.loads((tmp / ".servo" / "install.json").read_text())
            self.assertNotIn("design_fidelity", manifest["components"])
            self.assertIn("vitest", manifest["components"])  # baseline untouched


class _FakeResp:
    """Minimal stand-in for the urlopen context manager (a queued behaviour)."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def read(self):
        return self._body


@contextlib.contextmanager
def _patched_urlopen(behaviors):
    """Replay queued behaviours through score's urlopen (an Exception is raised,
    anything else is returned) and no-op the backoff sleep so retries are fast."""
    queue = list(behaviors)
    calls = {"n": 0}

    def fake(_req, timeout=None):
        item = queue[calls["n"]]
        calls["n"] += 1
        if isinstance(item, Exception):
            raise item
        return item

    orig_open, orig_sleep = score.urllib.request.urlopen, score.time.sleep
    score.urllib.request.urlopen = fake
    score.time.sleep = lambda *_a, **_k: None
    try:
        yield calls
    finally:
        score.urllib.request.urlopen = orig_open
        score.time.sleep = orig_sleep


class JudgeParseTests(unittest.TestCase):
    """The `_extract_json` + transient-retry paths behind AC4 (unparseable /
    unreachable judge → env_error, never a 0.0) — without a real API or browser."""

    def setUp(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_extract_json_from_noisy_reply(self):
        self.assertEqual(
            score._extract_json('Sure! {"score": 0.8, "reasoning": "x"} done'),
            '{"score": 0.8, "reasoning": "x"}')

    def test_extract_json_raises_without_object(self):
        with self.assertRaises(ValueError):
            score._extract_json("no json object here")

    def _pngs(self, tmp: Path):
        (tmp / "a.png").write_bytes(b"\x89PNG-app")
        (tmp / "b.png").write_bytes(b"\x89PNG-ref")
        return tmp / "a.png", tmp / "b.png"

    def _resp(self, text: str) -> _FakeResp:
        return _FakeResp(json.dumps({"content": [{"type": "text", "text": text}]}).encode())

    def test_api_unparseable_reply_is_env_error(self):
        # AC4: a reply with no JSON object → env_error, never a silent score.
        with tempfile.TemporaryDirectory() as t:
            app, ref = self._pngs(Path(t))
            with _patched_urlopen([self._resp("I cannot score this.")]):
                with self.assertRaises(score.EnvError):
                    score._judge_api(app, ref, _base_config())

    def test_api_retries_transient_then_succeeds(self):
        transient = score.urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None)
        with tempfile.TemporaryDirectory() as t:
            app, ref = self._pngs(Path(t))
            with _patched_urlopen([transient, self._resp('{"score": 0.91}')]) as calls:
                val = score._judge_api(app, ref, _base_config())
            self.assertEqual(calls["n"], 2)  # one retry, then success
            self.assertAlmostEqual(val, 0.91)

    def test_api_does_not_retry_on_4xx(self):
        bad = score.urllib.error.HTTPError("u", 400, "Bad Request", {}, None)
        with tempfile.TemporaryDirectory() as t:
            app, ref = self._pngs(Path(t))
            with _patched_urlopen([bad, bad]) as calls:
                with self.assertRaises(score.EnvError):
                    score._judge_api(app, ref, _base_config())
            self.assertEqual(calls["n"], 1)  # 4xx is surfaced immediately, not retried


# --- helper: run score.main() with the eval dir as the script's base dir ---

def _capture_main(eval_dir: Path):
    # Ensure the eval dir has a score.py copy whose __file__ is in the eval dir,
    # plus its sibling fidelity_eval.py (score.py's two-candidate import probe,
    # ADR-0024/020-01 — the copied-target layout) so the copy runs standalone.
    import shutil as _sh
    if not (eval_dir / "score.py").is_file():
        _sh.copyfile(HERE / "score.py", eval_dir / "score.py")
    if not (eval_dir / "fidelity_eval.py").is_file():
        _sh.copyfile(HERE.parent / "_common" / "fidelity_eval.py", eval_dir / "fidelity_eval.py")
    mod = _load("design_eval_score_run", str(eval_dir / "score.py"))
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = mod.main([])
    return rc, out.getvalue(), err.getvalue()


if __name__ == "__main__":
    unittest.main()
