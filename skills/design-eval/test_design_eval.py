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
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
        # Scope the env mutation to this test rather than leaking it into the
        # rest of the run (craft-review nit): patch.dict restores on cleanup.
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("ANTHROPIC_API_KEY", None)
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


class InstallHardeningTests(unittest.TestCase):
    """012-02 depth: the install/uninstall path's structural + fail-closed
    invariants, not just the happy round-trip.

    Recorded gap (docs/refinement-todo.md, "012-02's install path is thinly
    asserted"): the original three tests proved a component splices and
    deregisters, but not that the result is a *valid* oracle.sh, that config is
    preserved, that the manifest stays duplicate-free, or that the error paths
    fail closed. These close that gap.
    """

    ORACLE = InstallTests.ORACLE

    def _target(self, tmp: Path):
        (tmp / ".servo").mkdir(parents=True, exist_ok=True)
        (tmp / "oracle.sh").write_text(self.ORACLE)
        (tmp / ".servo" / "install.json").write_text(json.dumps({"components": ["vitest"]}))
        _make_eval_dir(tmp)

    # --- AC1: the spliced oracle.sh stays a valid bash program ---------------

    @unittest.skipUnless(shutil.which("bash"), "bash not on PATH")
    def test_installed_oracle_is_bash_valid(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            de.install(tmp, weight=1.0)
            res = subprocess.run(
                ["bash", "-n", str(tmp / "oracle.sh")],
                capture_output=True, text=True)
            self.assertEqual(res.returncode, 0,
                             f"spliced oracle.sh is not `bash -n` clean:\n{res.stderr}")

    @unittest.skipUnless(shutil.which("bash"), "bash not on PATH")
    def test_oracle_is_bash_valid_after_uninstall(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            de.install(tmp)
            de.uninstall(tmp)
            res = subprocess.run(
                ["bash", "-n", str(tmp / "oracle.sh")],
                capture_output=True, text=True)
            self.assertEqual(res.returncode, 0,
                             f"oracle.sh not `bash -n` clean after uninstall:\n{res.stderr}")

    # --- the SEED block is well-formed (matched start/end) ------------------

    def test_seed_block_is_balanced(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            de.install(tmp)
            text = (tmp / "oracle.sh").read_text()
            self.assertEqual(text.count("# SEED:start design_fidelity"), 1)
            self.assertEqual(text.count("# SEED:end design_fidelity"), 1)
            self.assertLess(
                text.index("# SEED:start design_fidelity"),
                text.index("# SEED:end design_fidelity"),
                "SEED start must precede SEED end",
            )

    # --- idempotence at the manifest layer (not just oracle.sh) -------------

    def test_repeated_install_does_not_duplicate_manifest_entry(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            de.install(tmp)
            de.install(tmp)
            components = json.loads((tmp / ".servo" / "install.json").read_text())["components"]
            self.assertEqual(components.count("design_fidelity"), 1,
                             "re-install must not append a duplicate manifest entry")

    def test_uninstall_is_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            de.install(tmp)
            de.uninstall(tmp)
            de.uninstall(tmp)  # second uninstall is a clean no-op
            text = (tmp / "oracle.sh").read_text()
            self.assertNotIn("design_fidelity", text)
            components = json.loads((tmp / ".servo" / "install.json").read_text())["components"]
            self.assertNotIn("design_fidelity", components)

    # --- install must not clobber an authored config.json -------------------

    def test_install_preserves_existing_config(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            cfg_path = tmp / ".servo" / "design-eval" / "config.json"
            authored = json.loads(cfg_path.read_text())
            authored["threshold"] = 0.91  # a project edit install must not lose
            cfg_path.write_text(json.dumps(authored, indent=2))
            de.install(tmp)  # calls init() internally to vendor the runtime
            after = json.loads(cfg_path.read_text())
            self.assertEqual(after["threshold"], 0.91,
                             "install()'s init() step must not overwrite an authored config.json")

    # --- fail-closed error paths --------------------------------------------

    def test_install_without_oracle_raises(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / ".servo").mkdir(parents=True, exist_ok=True)
            _make_eval_dir(tmp)
            # no oracle.sh
            with self.assertRaises(FileNotFoundError):
                de.install(tmp)

    def test_uninstall_without_oracle_raises(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            with self.assertRaises(FileNotFoundError):
                de.uninstall(tmp)


class FreezeCliTests(unittest.TestCase):
    """012-02 depth: `design_eval.py`'s `freeze()` CLI verb.

    The existing `FreezeTests` exercise `score.py`'s freeze *validator*;
    `de.freeze()` — which writes the approval fields the validator later reads —
    had no direct coverage.
    """

    def test_freeze_approves_and_hashes(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_eval_dir(tmp)
            d = tmp / ".servo" / "design-eval"
            # freeze() also requires each screen's setup file to exist.
            (d / "setups").mkdir(exist_ok=True)
            cfg = json.loads((d / "config.json").read_text())
            for s in cfg["screens"]:
                s["setup"] = f"setups/{s['id']}.mjs"
                (d / "setups" / f"{s['id']}.mjs").write_text("export default async () => {};\n")
            (d / "config.json").write_text(json.dumps(cfg, indent=2))

            frozen = de.freeze(tmp)
            self.assertEqual(frozen["approval_status"], "approved")
            self.assertIn("approved_content_hash", frozen)
            self.assertIn("hashes", frozen)
            self.assertIn("rubric", frozen["hashes"])
            # the on-disk config reflects the freeze (not just the return value)
            on_disk = json.loads((d / "config.json").read_text())
            self.assertEqual(on_disk["approval_status"], "approved")

    def test_freeze_refuses_when_reference_missing(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = tmp / ".servo" / "design-eval"
            (d / "refs").mkdir(parents=True, exist_ok=True)
            cfg = _base_config()
            # reference files deliberately absent
            (d / "config.json").write_text(json.dumps(cfg, indent=2))
            with self.assertRaises(FileNotFoundError):
                de.freeze(tmp)

    def test_freeze_without_config_raises(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / ".servo" / "design-eval").mkdir(parents=True, exist_ok=True)
            with self.assertRaises(FileNotFoundError):
                de.freeze(tmp)


class CliDispatchTests(unittest.TestCase):
    """012-04 surface: `main()`'s argparse dispatch — the entry point the
    SKILL.md flow tells a user to invoke. Exercises the verb wiring end-to-end
    without a browser or a judge."""

    def test_main_requires_a_subcommand(self):
        with self.assertRaises(SystemExit) as cm:
            de.main([])
        self.assertNotEqual(cm.exception.code, 0)

    def test_main_init_scaffolds(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = de.main(["init", str(tmp)])
            self.assertEqual(rc, 0)
            self.assertTrue((tmp / ".servo" / "design-eval" / "config.json").is_file())

    def test_main_install_then_uninstall_roundtrip(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / ".servo").mkdir(parents=True, exist_ok=True)
            (tmp / "oracle.sh").write_text(InstallTests.ORACLE)
            (tmp / ".servo" / "install.json").write_text(json.dumps({"components": ["vitest"]}))
            _make_eval_dir(tmp)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(de.main(["install", str(tmp), "--weight", "2.5"]), 0)
                self.assertEqual(de.main(["uninstall", str(tmp)]), 0)
            self.assertNotIn("design_fidelity", (tmp / "oracle.sh").read_text())


class MalformedDefinitionHonestyTests(unittest.TestCase):
    """Craft-review finding: a malformed config.json escaped `main()` as a raw
    traceback instead of the standard `design-eval: env_error — …` line."""

    def test_malformed_config_is_env_error_not_traceback(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = tmp / ".servo" / "design-eval"
            d.mkdir(parents=True, exist_ok=True)
            (d / "config.json").write_text("{ this is not json")
            rc, out, err = _capture_main(d)
            self.assertEqual(rc, score.EXIT_ENV_ERROR)
            self.assertEqual(out.strip(), "")   # never a 0.0
            self.assertIn("env_error", err)
            self.assertNotIn("Traceback", err)  # a clean line, not a stack trace

    def test_config_missing_screens_is_env_error(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = tmp / ".servo" / "design-eval"
            d.mkdir(parents=True, exist_ok=True)
            (d / "config.json").write_text(json.dumps({"schema_version": 1}))
            rc, out, err = _capture_main(d)
            self.assertEqual(rc, score.EXIT_ENV_ERROR)
            self.assertEqual(out.strip(), "")
            # An unapproved/empty definition legitimately refuses as *stale*
            # before it can be malformed. Either way the contract is the same:
            # rc 2, no score on stdout, and a clean `design-eval: ` line rather
            # than a traceback.
            self.assertTrue(err.startswith("design-eval: "), err)
            self.assertNotIn("Traceback", err)


class CaptureAppHonestyTests(unittest.TestCase):
    """012-01 AC5 / 012-03: `capture_app`'s three failure branches.

    Compliance review flagged these as implemented-but-untested: a capture
    failure must surface as EnvError (→ rc 2), never a silent 0.0.
    """

    def _screen(self):
        return {"id": "home", "reference": "refs/home.png"}

    def test_missing_node_raises_env_error(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            orig = score.subprocess.run

            def boom(*a, **k):
                raise FileNotFoundError("node")

            score.subprocess.run = boom
            try:
                with self.assertRaises(score.EnvError) as cm:
                    score.capture_app(d, self._screen())
                self.assertIn("node", str(cm.exception).lower())
            finally:
                score.subprocess.run = orig

    def test_capture_timeout_raises_env_error(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            orig = score.subprocess.run

            def slow(*a, **k):
                raise score.subprocess.TimeoutExpired(cmd="node", timeout=180)

            score.subprocess.run = slow
            try:
                with self.assertRaises(score.EnvError) as cm:
                    score.capture_app(d, self._screen())
                self.assertIn("timed out", str(cm.exception))
            finally:
                score.subprocess.run = orig

    def test_nonzero_rc_raises_env_error(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            orig = score.subprocess.run

            class _P:
                returncode = 2
                stderr = "selector not found"

            score.subprocess.run = lambda *a, **k: _P()
            try:
                with self.assertRaises(score.EnvError) as cm:
                    score.capture_app(d, self._screen())
                self.assertIn("capture failed", str(cm.exception))
            finally:
                score.subprocess.run = orig


class JudgeCliTransportTests(unittest.TestCase):
    """012-03 AC4: the `cli` judge transport (`_judge_cli`).

    Compliance review flagged this transport as shipped-but-entirely-untested —
    and, unlike the `api` path, it has NO retry, so every failure must fail
    closed on the first attempt rather than degrade to a score.
    """

    def _png(self, d: Path, name: str) -> Path:
        # _judge_cli cwd's to app_png.parent.parent, so nest one level down.
        sub = d / "shots"
        sub.mkdir(parents=True, exist_ok=True)
        p = sub / name
        p.write_bytes(b"\x89PNG")
        return p

    def _run(self, d: Path, fake):
        orig_run, orig_resolve = score.subprocess.run, score._resolve_claude
        score.subprocess.run = fake
        score._resolve_claude = lambda: "/usr/bin/claude"
        try:
            return score._judge_cli(
                self._png(d, "app.png"), self._png(d, "ref.png"), _base_config())
        finally:
            score.subprocess.run, score._resolve_claude = orig_run, orig_resolve

    def test_happy_path_parses_score(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)

            class _P:
                returncode = 0
                stdout = json.dumps({"is_error": False, "result": '{"score": 0.83}'})
                stderr = ""

            self.assertAlmostEqual(self._run(d, lambda *a, **k: _P()), 0.83)

    def test_score_is_clamped_to_unit_interval(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)

            class _P:
                returncode = 0
                stdout = json.dumps({"is_error": False, "result": '{"score": 4.2}'})
                stderr = ""

            self.assertEqual(self._run(d, lambda *a, **k: _P()), 1.0)

    def test_nonzero_rc_is_env_error(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)

            class _P:
                returncode = 1
                stdout = ""
                stderr = "boom"

            with self.assertRaises(score.EnvError):
                self._run(d, lambda *a, **k: _P())

    def test_is_error_envelope_is_env_error(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)

            class _P:
                returncode = 0
                stdout = json.dumps({"is_error": True, "result": "rate limited"})
                stderr = ""

            with self.assertRaises(score.EnvError):
                self._run(d, lambda *a, **k: _P())

    def test_unparseable_reply_is_env_error(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)

            class _P:
                returncode = 0
                stdout = json.dumps({"is_error": False, "result": "I cannot score this."})
                stderr = ""

            with self.assertRaises(score.EnvError):
                self._run(d, lambda *a, **k: _P())

    def test_missing_claude_binary_is_env_error(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)

            def boom(*a, **k):
                raise FileNotFoundError("claude")

            with self.assertRaises(score.EnvError):
                self._run(d, boom)


class CaptureRefsTests(unittest.TestCase):
    """012-02 AC2: `capture_refs` — previously the one CLI verb with neither
    error handling nor a test (compliance-review finding)."""

    def test_passes_through_the_node_return_code(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            de.init(tmp)
            orig = de.subprocess.run

            class _P:
                returncode = 0

            de.subprocess.run = lambda *a, **k: _P()
            try:
                self.assertEqual(de.capture_refs(tmp), 0)
            finally:
                de.subprocess.run = orig

    def test_missing_node_returns_env_error_rc_not_traceback(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            de.init(tmp)
            orig = de.subprocess.run

            def boom(*a, **k):
                raise FileNotFoundError("node")

            de.subprocess.run = boom
            try:
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc = de.capture_refs(tmp)
                self.assertEqual(rc, de.ENV_ERROR_RC)
                self.assertIn("node unavailable", err.getvalue())
            finally:
                de.subprocess.run = orig


class PreflightTests(unittest.TestCase):
    """026-01 AC1-AC3, AC5-AC7: probe node + library before spawning capture."""

    def _no_node(self, *a, **k):
        raise AssertionError("preflight must not spawn node when which(node) is None")

    def test_node_missing_raises_with_remedy(self):
        with tempfile.TemporaryDirectory() as td:
            orig_which, orig_run = score.shutil.which, score.subprocess.run
            score.shutil.which = lambda n: None
            score.subprocess.run = self._no_node   # AC2: no spawn when (a) failed
            try:
                with self.assertRaises(score.EnvError) as cm:
                    score.preflight_capture(Path(td))
                self.assertIn("node", str(cm.exception).lower())
            finally:
                score.shutil.which, score.subprocess.run = orig_which, orig_run

    def test_library_missing_raises_with_exact_command(self):
        with tempfile.TemporaryDirectory() as td:
            orig, orig_which = score.subprocess.run, score.shutil.which
            score.shutil.which = lambda n: "/usr/bin/node"

            class _P:
                returncode = 1
                stderr = "Error [ERR_MODULE_NOT_FOUND]: ... MODULE_NOT_FOUND ..."
                stdout = ""

            score.subprocess.run = lambda *a, **k: _P()
            try:
                with self.assertRaises(score.EnvError) as cm:
                    score.preflight_capture(Path(td))
                msg = str(cm.exception)
                self.assertIn("npm i -D playwright", msg)
                self.assertIn("npx playwright install", msg)
            finally:
                score.subprocess.run, score.shutil.which = orig, orig_which

    def test_fails_open_on_ambiguous_probe_failure(self):
        # AC1/AC6: non-zero WITHOUT the token must NOT halt — e.g.
        # NODE_OPTIONS=--input-type=module making `require` undefined.
        with tempfile.TemporaryDirectory() as td:
            orig, orig_which = score.subprocess.run, score.shutil.which
            score.shutil.which = lambda n: "/usr/bin/node"

            class _P:
                returncode = 1
                stderr = "ReferenceError: require is not defined in ES module scope"
                stdout = ""

            score.subprocess.run = lambda *a, **k: _P()
            try:
                score.preflight_capture(Path(td))   # must not raise
            finally:
                score.subprocess.run, score.shutil.which = orig, orig_which

    def test_probe_spawns_with_cwd_base_dir(self):
        # AC1: CJS module.paths must walk the same chain as capture.mjs's ESM import.
        with tempfile.TemporaryDirectory() as td:
            seen, orig = {}, score.subprocess.run
            orig_which = score.shutil.which
            score.shutil.which = lambda n: "/usr/bin/node"

            class _P:
                returncode = 0
                stderr = ""
                stdout = ""

            def spy(*a, **k):
                seen.update(k)
                seen["argv"] = a[0] if a else None
                return _P()

            score.subprocess.run = spy
            try:
                score.preflight_capture(Path(td))
                self.assertEqual(seen.get("cwd"), str(Path(td)))
                # AC2/AC3: pin the ARGV, not just the kwargs — a probe rewritten
                # to launch a browser would otherwise pass this test.
                argv = seen.get("argv")
                self.assertEqual(argv[:2], ["node", "-e"])
                self.assertIn("require.resolve", argv[2])
                self.assertNotIn("chromium", " ".join(argv).lower())
                self.assertNotIn("launch", " ".join(argv).lower())
            finally:
                score.subprocess.run, score.shutil.which = orig, orig_which

    def test_all_clear_is_silent(self):
        with tempfile.TemporaryDirectory() as td:
            orig, orig_which = score.subprocess.run, score.shutil.which
            score.shutil.which = lambda n: "/usr/bin/node"

            class _P:
                returncode = 0
                stderr = ""
                stdout = ""

            score.subprocess.run = lambda *a, **k: _P()
            try:
                score.preflight_capture(Path(td))
            finally:
                score.subprocess.run, score.shutil.which = orig, orig_which

    def test_fake_scores_path_still_scores_with_node_absent(self):
        # AC5 regression guard: the preflight lives in the live-capture arm only,
        # so every offline/CI run using the fake-scores hook must be unaffected.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            orig_which = score.shutil.which
            score.shutil.which = lambda n: None   # node absent
            os.environ[score._FAKE_SCORES_ENV] = json.dumps(
                {"home": [0.9, 0.9], "settings": [0.9, 0.9]})
            try:
                rc, out, _ = _capture_main(d)
                self.assertEqual(rc, score.EXIT_OK)
                self.assertGreater(float(out.strip()), 0.0)
            finally:
                score.shutil.which = orig_which
                os.environ.pop(score._FAKE_SCORES_ENV, None)


class AttestationParseTests(unittest.TestCase):
    """026-03 AC1a: marker-delimited, first-match, adopter logging discarded.

    CI-runnable (pytest). The JS-side guard (safeAttest) is node-skipped and
    lives in test_capture_lib.mjs — a Python fake cannot substitute for it.
    """

    def test_takes_first_marker_line_and_ignores_adopter_logging(self):
        stdout = "\n".join([
            "seeded 3 orders",                                  # adopter console.log
            json.dumps({"notOurs": True}),                      # adopter JSON
            '##servo-capture:{"engine":"chromium","version":"131.0","transport":"bundled"}',
            '##servo-capture:{"engine":"firefox","version":"99"}',   # later collision loses
        ])
        got = score.parse_attestation(stdout)
        self.assertEqual(got["engine"], "chromium")
        self.assertEqual(got["version"], "131.0")

    def test_contaminated_stdout_still_attests(self):
        # The test that would have caught the false "stdout is free" premise:
        # capture.mjs runs the ADOPTER's setup module in-process.
        stdout = 'log line\n{"their":"json"}\n##servo-capture:{"engine":"chromium","version":"1"}'
        self.assertIsNotNone(score.parse_attestation(stdout))

    def test_absent_or_malformed_returns_none_never_raises(self):
        self.assertIsNone(score.parse_attestation("just logs\nnothing"))
        self.assertIsNone(score.parse_attestation("##servo-capture:{not json"))
        self.assertIsNone(score.parse_attestation(""))
        self.assertIsNone(score.parse_attestation(None))

    def test_does_not_use_extract_json(self):
        # _extract_json (first { to last }) would span the adopter's object and
        # the attestation, or return the adopter's data AS the attestation.
        src = (HERE / "score.py").read_text()
        block = src[src.index("def parse_attestation"):src.index("def capture_app")]
        # Assert on an INVOCATION, not the docstring explaining why we avoid it.
        self.assertNotIn("_extract_json(", block)


class LedgerProvenanceTests(unittest.TestCase):
    """026-03 AC2/AC2a/AC5: per-screen provenance under a distinct key, with
    reason tokens that keep not_captured separate from not_attested.

    CI-RUNNABLE (pytest). The JS-side guard (safeAttest against a throwing
    thunk) is NODE-SKIPPED and lives in test_capture_lib.mjs — a Python fake
    cannot substitute for it, which is why AC1c moved that logic out of the
    untestable capture.mjs in the first place.
    """

    def _row(self, d):
        line = (d / "ledger.jsonl").read_text().strip().splitlines()[-1]
        return json.loads(line)

    def test_fake_scores_row_records_not_captured(self):
        # A synthetic score must never be byte-indistinguishable from a real
        # capture: no browser ran at all.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            os.environ[score._FAKE_SCORES_ENV] = json.dumps(
                {"home": [0.9, 0.9], "settings": [0.9, 0.9]})
            try:
                _capture_main(d)
                row = self._row(d)
                for s in row["screens"]:
                    self.assertEqual(s["provenance"], "not_captured")
                    self.assertIsNone(s["engine"])
            finally:
                os.environ.pop(score._FAKE_SCORES_ENV, None)

    def test_capture_transport_key_is_distinct_from_judge_transport(self):
        # AC2a: the row's top-level `transport` means the JUDGE transport in
        # every historical row; reusing it would destroy a human's ability to
        # spot a judge-transport change.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            os.environ[score._FAKE_SCORES_ENV] = json.dumps(
                {"home": [0.9, 0.9], "settings": [0.9, 0.9]})
            try:
                _capture_main(d)
                row = self._row(d)
                self.assertIn("transport", row)                 # judge transport
                self.assertIn("capture_transport", row["screens"][0])
                # The meaningful assertion: capture_transport must NOT appear at
                # the row level, where `transport` already means the judge one.
                self.assertNotIn("capture_transport", row)
            finally:
                os.environ.pop(score._FAKE_SCORES_ENV, None)

    def _live_row(self, tmp, stdout, versions=None):
        """Drive a LIVE-capture run (not the fake-scores arm) with a stubbed
        capture.mjs stdout, and return the ledger row.

        Calls `score.score()` directly rather than `_capture_main`, because that
        helper loads a FRESH copy of score.py from the eval dir — monkeypatches
        on this module would not reach it.
        """
        d = _make_eval_dir(tmp)
        de.freeze(tmp)
        seen = {"n": 0}
        orig_run, orig_which, orig_judge = (
            score.subprocess.run, score.shutil.which, score.judge)

        class _P:
            returncode = 0
            stderr = ""
            stdout = ""

        def fake_run(*a, **k):
            argv = a[0]
            if "--out" not in argv:
                # the preflight probe (`node -e require.resolve(...)`), not capture
                _P.stdout = ""
                return _P()
            out = Path(argv[argv.index("--out") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x89PNG")
            if versions:
                v = versions[min(seen["n"], len(versions) - 1)]
                _P.stdout = ('##servo-capture:{"engine":"chromium","version":"%s",'
                             '"transport":"bundled","error":null}' % v)
            else:
                _P.stdout = stdout
            seen["n"] += 1
            return _P()

        score.subprocess.run = fake_run
        score.shutil.which = lambda n: "/usr/bin/node"
        score.judge = lambda *a, **k: 0.9
        os.environ["ANTHROPIC_API_KEY"] = "x"
        try:
            composite = score.score(d)
            rows = (d / "ledger.jsonl").read_text().strip().splitlines()
            return composite, json.loads(rows[-1])
        finally:
            score.subprocess.run, score.shutil.which, score.judge = (
                orig_run, orig_which, orig_judge)
            os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_live_capture_records_attested_provenance(self):
        with tempfile.TemporaryDirectory() as t:
            line = ('##servo-capture:{"engine":"chromium","version":"131.0",'
                    '"transport":"bundled","error":null}')
            composite, row = self._live_row(Path(t), line)
            self.assertGreater(composite, 0.0)
            for s in row["screens"]:
                self.assertEqual(s["provenance"], "attested")
                self.assertEqual(s["engine"], "chromium")
                self.assertEqual(s["engine_version"], "131.0")
                self.assertEqual(s["capture_transport"], "bundled")

    def test_missing_line_on_a_LIVE_capture_is_not_attested_not_not_captured(self):
        # THE regression this exists for: an earlier version derived `fake_run`
        # from `att is None`, making `not_attested` unreachable — so a real
        # capture with no marker line reported "no browser ran at all".
        with tempfile.TemporaryDirectory() as t:
            _composite, row = self._live_row(Path(t), "just adopter logging\n")
            for s in row["screens"]:
                self.assertEqual(s["provenance"], "not_attested")

    def test_null_engine_is_distinct_from_no_line(self):
        """The DoD box I had ticked without a test. `_provenance`'s null-engine
        branch (score.py `if not att.get("engine")`) was production-reachable and
        completely uncovered — the same shape as the two bugs this slice shipped."""
        with tempfile.TemporaryDirectory() as t:
            line = ('##servo-capture:{"engine":null,"version":null,'
                    '"transport":"bundled","error":"accessor-threw: boom"}')
            _c, row = self._live_row(Path(t), line)
            for s in row["screens"]:
                self.assertEqual(s["provenance"], "not_attested")
                self.assertEqual(s["provenance_error"], "accessor-threw: boom")
                # distinct from the no-line case, which carries NO error string
                self.assertEqual(s["capture_transport"], "bundled")

    def test_no_line_and_null_engine_differ_in_the_record(self):
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            _c1, no_line = self._live_row(Path(t1), "adopter logging only\n")
            line = ('##servo-capture:{"engine":null,"version":null,'
                    '"transport":"bundled","error":"no-accessor"}')
            _c2, null_eng = self._live_row(Path(t2), line)
            a, b = no_line["screens"][0], null_eng["screens"][0]
            self.assertEqual(a["provenance"], b["provenance"])          # both not_attested
            self.assertIsNone(a["provenance_error"])                    # but distinguishable
            self.assertEqual(b["provenance_error"], "no-accessor")
            self.assertIsNone(a["capture_transport"])
            self.assertEqual(b["capture_transport"], "bundled")

    def test_garbage_and_non_object_payloads_still_score(self):
        # AC4: provenance is never load-bearing. A non-object JSON payload after
        # the marker previously raised AttributeError out of main()'s catch tuple.
        for stdout in ("##servo-capture:123", '##servo-capture:"a string"',
                       "##servo-capture:{not json", "binary junk"):
            with tempfile.TemporaryDirectory() as t:
                composite, row = self._live_row(Path(t), stdout)
                self.assertGreater(composite, 0.0, f"failed to score on {stdout!r}")
                self.assertEqual(row["screens"][0]["provenance"], "not_attested")

    def test_two_screens_with_differing_attestations_are_recorded_separately(self):
        # AC2: capture_app runs once per screen, so a row has N attestations. A
        # single row-level field would silently report one of them.
        with tempfile.TemporaryDirectory() as t:
            _composite, row = self._live_row(Path(t), "", versions=["131.0", "132.0"])
            got = [s["engine_version"] for s in row["screens"]]
            self.assertEqual(got, ["131.0", "132.0"],
                             "a mid-run engine change must be visible per screen")

    def test_provenance_is_not_in_the_definition_hash(self):
        """AC3: environmental, never a staleness trigger.

        Varies something provenance-SHAPED — an earlier form hashed a
        byte-identical copy and would have passed even if provenance were hashed.
        """
        cfg = _base_config()
        h0 = score.definition_hash(cfg)
        polluted = dict(cfg, capture={"transport": "system-chrome"})
        polluted["screens"] = [dict(s, engine="chromium", engine_version="131.0")
                               for s in cfg["screens"]]
        self.assertEqual(score.definition_hash(polluted), h0,
                         "provenance-shaped fields must not move the definition hash")

    def test_marker_constant_matches_across_the_language_boundary(self):
        """ATTEST_MARKER is the ENTIRE cross-language contract, and it was
        duplicated with nothing holding the copies together — a drift here breaks
        production silently (capture.mjs emits one prefix, score.py scans another)."""
        js = (HERE / "capture_lib.mjs").read_text()
        line = [ln for ln in js.splitlines() if "ATTEST_MARKER =" in ln][0]
        js_marker = line.split("=", 1)[1].strip().rstrip(";").strip("'\"")
        self.assertEqual(js_marker, score._ATTEST_MARKER,
                         "capture_lib.mjs ATTEST_MARKER drifted from score.py _ATTEST_MARKER")


class SalientStderrTests(unittest.TestCase):
    """026-01 AC4: salient-line surfacing replaces the blind `stderr[:200]` head.

    Fixture (i) is RECORDED REAL stderr (see fixtures/ provenance header), not a
    hand-written one with the remedy conveniently placed — three defects in this
    slice came from grounding the easy case.
    """

    FIXTURES = HERE / "fixtures"

    def _fixture(self, name):
        raw = (self.FIXTURES / name).read_text()
        # strip the leading provenance comment block
        return "\n".join(ln for ln in raw.splitlines() if not ln.startswith("# "))

    def test_library_absent_first_line_is_the_cause_exact(self):
        # AC4 DoD: exact match on the EMITTED FIRST line — "survives anywhere"
        # cannot detect a rank-1 corruption, which is how R5's defect hid.
        out = score._fe.salient_stderr(self._fixture("stderr-library-absent.txt"))
        first = out.split(" | ")[0]
        # EXACT match on the emitted first line. `startswith` cannot detect a
        # corrupted tail — which is how the elision defect hid.
        expected = [ln for ln in self._fixture("stderr-library-absent.txt").splitlines()
                    if ln.startswith("Error [ERR_MODULE_NOT_FOUND]")][0].strip()
        self.assertEqual(first, expected, "rank 1 must be the cause line, verbatim")

    def test_library_absent_drops_node_internals(self):
        out = score._fe.salient_stderr(self._fixture("stderr-library-absent.txt"))
        for noise in ("node:internal/", "throw new ERR_MODULE_NOT_FOUND(",
                      "Node.js v", "code: 'ERR_MODULE_NOT_FOUND'", "    at "):
            self.assertNotIn(noise, out, f"noise leaked into the surfaced message: {noise!r}")

    def test_remedy_ranks_above_prose_at_the_stated_budget(self):
        # AC4: command-shape ranking. The prose line "was just installed or
        # updated" sits ABOVE the command in Playwright's box; a bare `install`
        # substring would rank it first and exhaust the budget (R4's defect).
        # NOTE: this input is a RECONSTRUCTION, not a recorded fixture —
        # Playwright is not installable in this repo, so fixture (ii) could not
        # be captured here. Logged as a deviation; see the slice deviation log.
        box = (
            "browserType.launch: Executable doesn't exist at "
            "/Users/x/Library/Caches/ms-playwright/chromium-1234/chrome-mac/Chromium.app\n"
            "╔══╗\n"
            "║ Looks like Playwright was just installed or updated. ║\n"
            "║ Please run the following command to download new browsers: ║\n"
            "║     npx playwright install ║\n"
            "╚══╝\n"
            "    at Object.<anonymous> (/t/capture.mjs:31:33)\n"
            "Node.js v22.16.0\n"
        )
        out = score._fe.salient_stderr(box, budget=score._fe.SALIENT_BUDGET)
        self.assertIn("npx playwright install", out, "the runnable remedy must survive at 400")
        parts = out.split(" | ")
        self.assertTrue(parts[0].startswith("browserType.launch:"), f"rank 1: {parts[0]!r}")
        self.assertLess(parts.index([p for p in parts if "npx playwright install" in p][0]),
                        parts.index([p for p in parts if "was just installed" in p][0]),
                        "command must outrank prose")

    def test_emitted_form_is_box_stripped(self):
        out = score._fe.salient_stderr("cause here\n║   npx playwright install   ║\n")
        self.assertNotIn("║", out)
        self.assertIn("npx playwright install", out)

    def test_zero_survivor_floor_falls_back_to_head_slice(self):
        # AC4: never emit an empty diagnostic — a strict regression on today's [:200].
        only_noise = "    at a (x:1:1)\n    at b (y:2:2)\nNode.js v22.16.0\n"
        out = score._fe.salient_stderr(only_noise)
        self.assertTrue(out, "zero survivors must fall back, not return empty")
        self.assertEqual(out, only_noise.strip()[:score._fe.SALIENT_FLOOR_BUDGET])

    def test_over_budget_line_is_skipped_whole_not_truncated(self):
        # AC4: a truncated `npx playwright inst` is the failure this prevents.
        long_cause = "C" * 380
        out = score._fe.salient_stderr(f"{long_cause}\nnpx playwright install\n")
        # The cause fits (380 < 400); the remedy does not fit alongside it, so it
        # must be SKIPPED WHOLE — never emitted truncated. Assert the exact
        # output, so this can actually fail (the earlier form was tautological:
        # `out` never contains a newline, and endswith() also passes for "").
        self.assertEqual(out, long_cause)
        self.assertNotIn("npx", out)


class PreflightExitContractTests(unittest.TestCase):
    """DoD: stdout empty + rc 2 on a preflight failure, end to end through main()."""

    def test_preflight_failure_exits_2_with_empty_stdout(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            d = _make_eval_dir(tmp)
            de.freeze(tmp)
            os.environ["ANTHROPIC_API_KEY"] = "x"        # get past the judge check
            orig_which = score.shutil.which
            score.shutil.which = lambda n: None          # node absent -> preflight halts
            try:
                rc, out, err = _capture_main(d)
                self.assertEqual(rc, score.EXIT_ENV_ERROR)
                self.assertEqual(out.strip(), "")        # never a silent 0.0
                self.assertIn("node", err.lower())
            finally:
                score.shutil.which = orig_which
                os.environ.pop("ANTHROPIC_API_KEY", None)


class SalientStderrRegressionTests(unittest.TestCase):
    """Guards for defects found in review rather than in authoring."""

    FIXTURES = HERE / "fixtures"

    def _fixture(self, name):
        raw = (self.FIXTURES / name).read_text()
        return "\n".join(ln for ln in raw.splitlines() if not ln.startswith("# "))

    def test_app_down_fixture_surfaces_the_cause_first(self):
        # Fixture (iii): the node run is real, but the ERROR SHAPE is constructed
        # (Playwright is not installable here) — see the fixture's own header.
        # Labelled rather than passed off as a recording.
        out = score._fe.salient_stderr(self._fixture("stderr-app-down.txt"))
        self.assertTrue(out.split(" | ")[0].startswith("capture: net::ERR_CONNECTION_REFUSED"),
                        f"rank 1 should be the cause, got {out.split(' | ')[0]!r}")

    def test_over_long_sole_survivor_is_elided_not_deleted(self):
        # REGRESSION (compliance review): the elision branch was arithmetically
        # dead — an over-long sole survivor returned "", an empty diagnostic and
        # a strict regression on the old head slice.
        long_cause = "Executable doesn't exist at /Users/x/" + "deep/" * 90 + "headless_shell"
        out = score._fe.salient_stderr(long_cause + "\n")
        self.assertTrue(out, "must never return an empty diagnostic")
        self.assertIn("...", out, "an over-long sole survivor must be middle-elided")
        self.assertTrue(out.startswith("Executable doesn't exist at"))
        self.assertTrue(out.endswith("headless_shell"), "the actionable tail must survive")
        self.assertLessEqual(len(out), score._fe.SALIENT_BUDGET)

    def test_judge_path_still_uses_head_slice(self):
        # AC4a guard: the node-grammar filter must NOT be wired to the `claude`
        # CLI producer, which has a different grammar and no fixture.
        src = (HERE / "score.py").read_text()
        judge = [ln for ln in src.splitlines() if "claude judge failed" in ln][0]
        self.assertIn("[:200]", judge, "judge path must keep the head slice (AC4a)")
        self.assertNotIn("salient_stderr", judge)

    def test_capture_app_routes_through_the_helper(self):
        """BEHAVIOURAL wiring test (craft finding): reverting score.py to
        `[:200]` must fail the suite. Asserting on the source text would not
        catch a semantically-equivalent revert."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            stderr = self._fixture("stderr-library-absent.txt")
            orig = score.subprocess.run

            class _P:
                returncode = 1
                stdout = ""

            _P.stderr = stderr
            score.subprocess.run = lambda *a, **k: _P()
            try:
                with self.assertRaises(score.EnvError) as cm:
                    score.capture_app(d, {"id": "home"})
                msg = str(cm.exception)
                self.assertIn("Cannot find package 'playwright'", msg,
                              "the cause must reach the operator")
                self.assertNotIn("node:internal/", msg,
                                 "node internals must not reach the operator ([:200] would)")
            finally:
                score.subprocess.run = orig


class ACParityTests(unittest.TestCase):
    """026-01 DoD: the mechanical control against code being stricter than its AC.

    Three defects in this slice came from exactly that gap, and a checkbox saying
    "the suite matches the prose" cannot fail. This binds the shipped constants to
    the slice text. Mirrors the doc-parity pattern in test_skill_surface.py.
    """

    SLICE = (HERE.parent.parent / "docs" / "specs" / "026-design-eval-browser-acquisition"
             / "slice-01-runtime-preflight-guidance.md")

    def _slice_text(self):
        # Join AC line-wraps precisely: strip the leading indent of continuation
        # lines. Do NOT normalize whitespace generally — loosening this comparison
        # would gut the control it exists to be.
        return re.sub(r"\n\s+", "", self.SLICE.read_text())

    def test_slice_file_exists(self):
        self.assertTrue(self.SLICE.is_file(), f"slice not found at {self.SLICE}")

    def test_remedy_regex_matches_the_ac(self):
        self.assertIn(score._fe.SALIENT_REMEDY, self._slice_text(),
                      "SALIENT_REMEDY drifted from AC4's stated command-shape pattern")

    def test_stack_frame_pattern_matches_the_ac_literally(self):
        """The constant that DID drift: code had `^\\s+at\\s` where AC4 says
        `^\\s+at ` (literal space). This is the exact defect class the parity
        control exists for, and it was the one constant not covered."""
        self.assertIn(r"^\s+at ", self._slice_text(),
                      "AC4 must quote the stack-frame pattern")
        self.assertIn(r"^\s+at ", score._fe.SALIENT_DROP_LINE,
                      "SALIENT_DROP_LINE drifted from AC4's stack-frame literal")

    def test_remedy_pattern_is_not_case_insensitive_beyond_the_ac(self):
        """AC4 states no case-insensitivity; compiling with re.I would be code
        looser than its AC — invisible to a pattern-string comparison."""
        src = (HERE.parent / "_common" / "fidelity_eval.py").read_text()
        compile_line = [ln for ln in src.splitlines()
                        if "re.compile(SALIENT_REMEDY" in ln][0]
        code = compile_line.split("#")[0]   # ignore an explanatory comment
        self.assertNotIn("re.I", code,
                         "AC4 states no case-insensitivity for the remedy pattern")
        self.assertNotIn("IGNORECASE", code)

    def test_frame_header_regex_matches_the_ac(self):
        self.assertIn(score._fe.SALIENT_FRAME_HEADER, self._slice_text(),
                      "SALIENT_FRAME_HEADER drifted from AC4's stated block rule")

    def test_budget_matches_the_ac(self):
        self.assertIn(f"budget is {score._fe.SALIENT_BUDGET} characters", self.SLICE.read_text(),
                      "SALIENT_BUDGET drifted from the number stated in AC4")


class CaptureLibNodeTests(unittest.TestCase):
    """Bridge the browser-free capture_lib.mjs node tests into the Python suite.

    `capture.mjs` launches Playwright at import time, so it cannot be unit
    tested directly; its pure helpers were extracted into `capture_lib.mjs`
    (imported by capture.mjs, so this exercises the *real* shipped code, not a
    copy) and are tested with node's built-in runner.

    node is not part of servo's CI image (pytest-only), so this **skips** where
    node is absent rather than failing — honest partial coverage: it runs on any
    dev machine with node and in any host that provisions it. Recorded in
    docs/refinement-todo.md as the reason capture.mjs coverage is dev-local.
    """

    CAPTURE_LIB = HERE / "capture_lib.mjs"
    NODE_TEST = HERE / "test_capture_lib.mjs"

    @unittest.skipUnless(shutil.which("node"), "node not on PATH (CI is pytest-only)")
    def test_capture_lib_node_suite_passes(self):
        res = subprocess.run(
            ["node", "--test", str(self.NODE_TEST)],
            capture_output=True, text=True)
        self.assertEqual(
            res.returncode, 0,
            f"capture_lib.mjs node suite failed:\n{res.stdout}\n{res.stderr}")
        self.assertIn("# fail 0", res.stdout)
        # Pin the count too: "# fail 0" alone also passes for an emptied or
        # renamed node suite (craft-review nit).
        m = re.search(r"^# pass (\d+)$", res.stdout, flags=re.MULTILINE)
        self.assertIsNotNone(m, f"no pass count in node output:\n{res.stdout}")
        self.assertGreaterEqual(int(m.group(1)), 10,
                                "capture_lib node suite shrank unexpectedly")

    def test_capture_mjs_imports_the_extracted_lib(self):
        # Guard the extraction: capture.mjs must delegate to capture_lib.mjs,
        # not re-inline the geometry (which would silently un-cover it).
        cap = (HERE / "capture.mjs").read_text()
        self.assertIn("from './capture_lib.mjs'", cap)
        self.assertIn("computeClip(", cap)
        # The geometry must be *called*, not re-inlined: a real re-inline would
        # reintroduce the width/height subtraction that now lives only in
        # capture_lib.computeClip. (The prior `box.width - (c.left` guard was
        # vacuous — that exact spelling never existed.)
        self.assertNotIn("box.width -", cap,
                         "clip width math should live in capture_lib.computeClip, not inline")
        self.assertNotIn("box.height -", cap,
                         "clip height math should live in capture_lib.computeClip, not inline")

    def test_capture_mjs_delegates_attestation_to_the_lib(self):
        """026-03 AC1c: the attestation guard must stay in capture_lib.mjs, where
        the node suite can test it — capture.mjs imports Playwright at module
        load and is structurally untestable, so a guard inlined there would ship
        with a ticked checkbox and no coverage."""
        cap = (HERE / "capture.mjs").read_text()
        self.assertIn("attestationLine", cap)
        self.assertIn("safeAttest", cap)
        # Anchor on the EMISSION, not the import — cap.index("attestationLine")
        # would match the import statement at the top of the file and prove
        # nothing about ordering.
        emission = cap.index("console.log(attestationLine")
        self.assertLess(emission, cap.index("screen.setup"),
                        "the attestation must be emitted before the adopter's setup import")


class InitVendorsRuntimeTests(unittest.TestCase):
    """`init()` must vendor every runtime file the copied capture.mjs needs —
    including `capture_lib.mjs`, or an installed target's capture.mjs fails to
    import at run time (the vendored-import contract)."""

    def test_init_copies_capture_lib(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            de.init(tmp)
            d = tmp / ".servo" / "design-eval"
            for runtime in ("score.py", "capture.mjs", "capture_lib.mjs", "fidelity_eval.py"):
                self.assertTrue((d / runtime).is_file(),
                                f"init() must vendor {runtime} into the target")


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
    if not (eval_dir / "score.py").is_file():
        shutil.copyfile(HERE / "score.py", eval_dir / "score.py")
    if not (eval_dir / "fidelity_eval.py").is_file():
        shutil.copyfile(HERE.parent / "_common" / "fidelity_eval.py",
                        eval_dir / "fidelity_eval.py")
    mod = _load("design_eval_score_run", str(eval_dir / "score.py"))
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = mod.main([])
    return rc, out.getvalue(), err.getvalue()


if __name__ == "__main__":
    unittest.main()
