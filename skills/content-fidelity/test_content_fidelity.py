"""Tests for the content-fidelity eval component (servo content-fidelity).

Exercises the freeze contract, the n-sample lower-bound aggregation, the
fail-closed honesty (stale / env_error → exit 2, never 0.0), the gather-once-
per-run contract (AC3), and the oracle.sh splice — all without an API key or
a live judge (the fake-scores hook).

Run:  python3 skills/content-fidelity/test_content_fidelity.py
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


score = _load("content_fidelity_score", "score.py")
cf = _load("content_fidelity_cli", "content_fidelity.py")


def _base_config(rubric="Score tone/content/style fidelity 0..1."):
    return {
        "schema_version": 1,
        "approval_status": "draft",
        "judge": {"model": "claude-sonnet-4-6", "temperature": 0.0, "max_tokens": 1024},
        "samples": {"n": 4, "k": 1.0, "delta": 0.03},
        "threshold": 0.8,
        "rubric": rubric,
        "cases": [
            {
                "id": "welcome",
                "reference": "refs/welcome.txt",
                "source": {"type": "file", "path": "generated/welcome.txt"},
                "weight": 1.0,
            },
            {
                "id": "support",
                "reference": "Reply warmly and acknowledge the issue.",
                "source": {"type": "command", "run": ["python3", "-c", "print('hi')"]},
                "weight": 1.0,
            },
        ],
    }


def _make_eval_dir(tmp: Path, config=None):
    d = tmp / ".servo" / "content-fidelity"
    (d / "refs").mkdir(parents=True, exist_ok=True)
    (d / "generated").mkdir(parents=True, exist_ok=True)
    (d / "refs" / "welcome.txt").write_text("Welcome! We are glad to have you.")
    (d / "generated" / "welcome.txt").write_text("Welcome aboard, glad you're here!")
    (d / "config.json").write_text(json.dumps(config or _base_config(), indent=2))
    return d


class AggregationTests(unittest.TestCase):
    """AC2/AC3 building block — reused straight from the shared module."""

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


class FreezeStaleOnEachFieldTests(unittest.TestCase):
    """AC2: rubric/case-set/judge/n/k/delta/threshold pinned + hashed; any
    change refuses as stale until re-frozen."""

    def test_freeze_then_validate_passes(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
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
            cf.freeze(tmp)
            (d / "refs" / "welcome.txt").write_text("TAMPERED reference text")
            with self.assertRaises(score.StaleError):
                score.validate_freeze(json.loads((d / "config.json").read_text()), d)

    def test_changed_rubric_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            config["rubric"] = "different rubric"
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, d)

    def test_changed_judge_model_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            config["judge"]["model"] = "claude-haiku-4-5-20251001"
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, d)

    def test_changed_samples_n_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            config["samples"]["n"] = 8
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, d)

    def test_changed_threshold_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            config["threshold"] = 0.95
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, d)

    def test_changed_case_set_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            config["cases"][1]["reference"] = "a completely different reference"
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, d)

    def test_changed_source_type_is_stale(self):
        # AC2: the artifact source descriptor (how the generated text under
        # test is obtained) is pinned too — swapping file->command after
        # freezing must refuse as stale, not silently score against a
        # different generator than the one approved.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            config["cases"][0]["source"] = {
                "type": "command", "run": ["python3", "-c", "print('swapped')"],
            }
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, d)

    def test_changed_source_path_is_stale(self):
        # Same source.type, but retargeting which file/command is used must
        # also refuse — the descriptor's *value*, not just its type, is
        # pinned.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
            config = json.loads((d / "config.json").read_text())
            config["cases"][0]["source"]["path"] = "generated/different.txt"
            with self.assertRaises(score.StaleError):
                score.validate_freeze(config, d)

    def test_changed_source_does_not_affect_artifact_hashes(self):
        # source is pinned into the definition hash (value-pinning), but must
        # NOT be treated as an on-disk file to hash the content of — it names
        # the moving target under test, not a frozen reference artifact.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            config = _base_config()
            hashes = score.artifact_hashes(config, d)
            self.assertNotIn("generated/welcome.txt", hashes)
            # only the rubric + reference file(s) are content-hashed
            self.assertEqual(set(hashes), {"rubric", "refs/welcome.txt"})

    def test_freeze_refuses_missing_reference_file(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            (d / "refs" / "welcome.txt").unlink()
            with self.assertRaises(FileNotFoundError):
                cf.freeze(tmp)

    def test_freeze_allows_inline_reference(self):
        # The "support" case's reference is inline prose, not a file path —
        # freeze must not treat it as a missing file.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _make_eval_dir(tmp)
            cf.freeze(tmp)  # no raise


class SingleGatherPerRunTests(unittest.TestCase):
    """AC3: the artifact under test is gathered exactly once per case per
    ``score()`` call, regardless of ``n`` — never re-gathered per sample."""

    def setUp(self):
        # score() gates the live path on a judge credential/binary even though
        # these tests monkeypatch score.judge itself to bypass any real call.
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_file_read_happens_once_per_case_regardless_of_n(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            config = _base_config()
            config["samples"]["n"] = 5  # n=5 judge calls, but ONE gather
            d = _make_eval_dir(tmp, config)
            cf.freeze(tmp)
            config = json.loads((d / "config.json").read_text())

            calls = {"welcome": 0, "support": 0}
            orig_gather = score.gather_text
            orig_judge = score.judge

            def counting_gather(base_dir, case):
                calls[case["id"]] += 1
                return orig_gather(base_dir, case)

            judge_calls = {"n": 0}

            def fake_judge(generated, reference, cfg):
                judge_calls["n"] += 1
                return 0.85

            score.gather_text = counting_gather
            score.judge = fake_judge
            try:
                composite = score.score(d)
            finally:
                score.gather_text = orig_gather
                score.judge = orig_judge

            self.assertEqual(calls["welcome"], 1)  # gathered exactly once
            self.assertEqual(calls["support"], 1)  # gathered exactly once (command case too)
            self.assertEqual(judge_calls["n"], 10)  # judged n=5 times per case x 2 cases
            self.assertGreater(composite, 0.0)

    def test_command_not_re_invoked_per_sample(self):
        # A command-backed case's generator must run exactly once even though
        # judge() is called n times against its single captured output.
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            config = _base_config()
            config["cases"] = [config["cases"][1]]  # command-only case
            config["samples"]["n"] = 6
            d = _make_eval_dir(tmp, config)
            cf.freeze(tmp)
            config = json.loads((d / "config.json").read_text())

            run_count = {"n": 0}
            orig_run = score.subprocess.run
            orig_judge = score.judge

            def counting_run(*args, **kwargs):
                run_count["n"] += 1
                return orig_run(*args, **kwargs)

            score.subprocess.run = counting_run
            score.judge = lambda generated, reference, cfg: 0.9
            try:
                score.score(d)
            finally:
                score.subprocess.run = orig_run
                score.judge = orig_judge

            self.assertEqual(run_count["n"], 1)  # generator invoked once, not 6x


class ScoreHonestyTests(unittest.TestCase):
    """AC4: stale / env_error → exit 2, never 0.0; a valid frozen run with
    fake scores → 0 + float. AC6: missing file / failing command → env_error."""

    def setUp(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop(score._FAKE_SCORES_ENV, None)

    def tearDown(self):
        os.environ.pop(score._FAKE_SCORES_ENV, None)

    def test_env_error_when_no_key_and_no_fake(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
            rc, out, err = _capture_main(d)
            self.assertEqual(rc, score.EXIT_ENV_ERROR)
            self.assertEqual(out.strip(), "")  # never a 0.0 on the env-error path
            self.assertIn("env_error", err)

    def test_stale_exits_2_not_zero(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)  # not frozen → stale
            os.environ[score._FAKE_SCORES_ENV] = json.dumps({"welcome": [0.9], "support": [0.9]})
            rc, out, err = _capture_main(d)
            self.assertEqual(rc, score.EXIT_ENV_ERROR)
            self.assertEqual(out.strip(), "")  # never prints a 0.0 on the stale path
            self.assertIn("stale", err)

    def test_fake_scores_happy_path_composite(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
            os.environ[score._FAKE_SCORES_ENV] = json.dumps(
                {"welcome": [0.80, 0.82, 0.78, 0.80], "support": [0.90, 0.90, 0.90, 0.90]})
            rc, out, _ = _capture_main(d)
            self.assertEqual(rc, score.EXIT_OK)
            composite = float(out.strip())
            self.assertGreater(composite, 0.7)
            self.assertLessEqual(composite, 1.0)
            # ledger written
            self.assertTrue((d / "ledger.jsonl").is_file())

    def test_missing_artifact_file_is_env_error_not_zero(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            cf.freeze(tmp)
            (d / "generated" / "welcome.txt").unlink()
            config = json.loads((d / "config.json").read_text())
            with self.assertRaises(score.EnvError):
                score.gather_text(d, config["cases"][0])

    def test_failing_command_is_env_error_not_zero(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            case = {"id": "x", "source": {"type": "command", "run": ["false"]}}
            with self.assertRaises(score.EnvError):
                score.gather_text(d, case)

    def test_nonexistent_command_binary_is_env_error(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            case = {"id": "x",
                     "source": {"type": "command", "run": ["definitely-not-a-binary-xyz"]}}
            with self.assertRaises(score.EnvError):
                score.gather_text(d, case)

    def test_unknown_source_type_is_env_error(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            d = _make_eval_dir(tmp)
            case = {"id": "x", "source": {"type": "carrier-pigeon"}}
            with self.assertRaises(score.EnvError):
                score.gather_text(d, case)


class TextJudgeRuntimeTests(unittest.TestCase):
    """AC5: text-only prompt (rubric + reference + generated text), no image
    content blocks, dispatched over the same api/cli transports as design-eval."""

    def setUp(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_prompt_has_no_image_content_blocks(self):
        prompt = score._prompt("generated text", "reference text", _base_config())
        self.assertIn("REFERENCE", prompt)
        self.assertIn("GENERATED TEXT UNDER TEST", prompt)
        self.assertIn("reference text", prompt)
        self.assertIn("generated text", prompt)

    def test_judge_api_sends_text_only_message_body(self):
        captured = {}

        def fake_post(req, timeout, attempts=3):
            captured["body"] = json.loads(req.data)
            return {"content": [{"type": "text", "text": '{"score": 0.77}'}]}

        orig = score._post_with_retry
        score._post_with_retry = fake_post
        try:
            val = score._judge_api("gen text", "ref text", _base_config())
        finally:
            score._post_with_retry = orig
        self.assertAlmostEqual(val, 0.77)
        content = captured["body"]["messages"][0]["content"]
        self.assertIsInstance(content, str)  # a plain string, never an image-block list
        self.assertIn("gen text", content)
        self.assertIn("ref text", content)

    def test_extract_json_from_noisy_reply(self):
        self.assertEqual(
            score._extract_json('Sure! {"score": 0.8, "reasoning": "x"} done'),
            '{"score": 0.8, "reasoning": "x"}')

    def test_unknown_transport_is_env_error(self):
        config = _base_config()
        config["judge"]["transport"] = "carrier-pigeon"
        with self.assertRaises(score.EnvError):
            score.judge("g", "r", config)


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
    unreachable judge → env_error, never a 0.0) — without a real API call."""

    def setUp(self):
        os.environ["ANTHROPIC_API_KEY"] = "test-key"

    def tearDown(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def _resp(self, text: str) -> _FakeResp:
        return _FakeResp(json.dumps({"content": [{"type": "text", "text": text}]}).encode())

    def test_api_unparseable_reply_is_env_error(self):
        with _patched_urlopen([self._resp("I cannot score this.")]):
            with self.assertRaises(score.EnvError):
                score._judge_api("gen", "ref", _base_config())

    def test_api_retries_transient_then_succeeds(self):
        transient = score.urllib.error.HTTPError("u", 503, "Service Unavailable", {}, None)
        with _patched_urlopen([transient, self._resp('{"score": 0.91}')]) as calls:
            val = score._judge_api("gen", "ref", _base_config())
        self.assertEqual(calls["n"], 2)  # one retry, then success
        self.assertAlmostEqual(val, 0.91)

    def test_api_does_not_retry_on_4xx(self):
        bad = score.urllib.error.HTTPError("u", 400, "Bad Request", {}, None)
        with _patched_urlopen([bad, bad]) as calls:
            with self.assertRaises(score.EnvError):
                score._judge_api("gen", "ref", _base_config())
        self.assertEqual(calls["n"], 1)  # 4xx is surfaced immediately, not retried

    def test_api_missing_key_is_env_error(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with self.assertRaises(score.EnvError):
            score._judge_api("gen", "ref", _base_config())


class InstallTests(unittest.TestCase):
    """AC1/AC8: ordinary score_<name> component, parameterized splice, same
    idempotency guarantees as design-eval's authoring CLI."""

    ORACLE = (
        "#!/usr/bin/env bash\nset -euo pipefail\nTHRESHOLD=\"${THRESHOLD:-0.5}\"\n"
        "COMPONENTS=(\n  \"vitest:1.0\"\n)\n\nweighted_sum=\"0\"\ntotal_weight=\"0\"\n"
    )

    def _target(self, tmp: Path):
        (tmp / ".servo").mkdir(parents=True, exist_ok=True)
        (tmp / "oracle.sh").write_text(self.ORACLE)
        (tmp / ".servo" / "install.json").write_text(json.dumps({"components": ["vitest"]}))
        # content-fidelity dir + config so install's init() has something to copy into
        _make_eval_dir(tmp)

    def test_install_splices_component_and_registers(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            cf.install(tmp, weight=2.0)
            text = (tmp / "oracle.sh").read_text()
            self.assertIn("# SEED:start content_fidelity", text)
            self.assertIn("score_content_fidelity()", text)
            self.assertIn('"content_fidelity:2.0"', text)
            self.assertIn('"vitest:1.0"', text)  # baseline untouched
            manifest = json.loads((tmp / ".servo" / "install.json").read_text())
            self.assertIn("content_fidelity", manifest["components"])

    def test_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            cf.install(tmp, weight=1.0)
            cf.install(tmp, weight=3.0)  # re-install refreshes weight, no dup
            text = (tmp / "oracle.sh").read_text()
            self.assertEqual(text.count("# SEED:start content_fidelity"), 1)
            self.assertIn('"content_fidelity:3.0"', text)
            self.assertNotIn('"content_fidelity:1.0"', text)

    def test_uninstall_removes_component(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            self._target(tmp)
            cf.install(tmp)
            cf.uninstall(tmp)
            text = (tmp / "oracle.sh").read_text()
            self.assertNotIn("content_fidelity", text)
            self.assertIn('"vitest:1.0"', text)
            # ...and the install manifest is deregistered symmetrically (no drift).
            manifest = json.loads((tmp / ".servo" / "install.json").read_text())
            self.assertNotIn("content_fidelity", manifest["components"])
            self.assertIn("vitest", manifest["components"])  # baseline untouched


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
    mod = _load("content_fidelity_score_run", str(eval_dir / "score.py"))
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = mod.main([])
    return rc, out.getvalue(), err.getvalue()


if __name__ == "__main__":
    unittest.main()
