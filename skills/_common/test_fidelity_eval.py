"""Tests for the shared frozen-eval harness (servo ADR-0024, spec 020 slice
020-01).

Covers AC1 (each exported function directly, with a case shape that is NOT
design-eval's — a differently-named cases key and file field, to prove the
generalization actually works for a second caller), AC2 (score.py's
two-candidate import probe, run as a real subprocess against each deployment
layout), AC3 (design_eval.py::init() copies fidelity_eval.py alongside the
existing runtime files), and AC5 (the oracle.sh splice helpers, reused with a
second, distinct component name).

Run:  python3 -m pytest skills/_common/test_fidelity_eval.py
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESIGN_EVAL_DIR = HERE.parent / "design-eval"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fe = _load("fidelity_eval", "fidelity_eval.py")

# A deliberately non-design-eval case shape: cases key "cases", file field
# "target" — proves definition_hash/artifact_hashes/validate_freeze are not
# secretly still hardcoded to "screens"/"reference"/"setup".
CASES_KEY = "cases"
FILE_FIELDS = ("target", "setup")


def _base_config(rubric="Score tone/register/reading-level fidelity 0..1."):
    return {
        "schema_version": 1,
        "approval_status": "draft",
        "judge": {"model": "claude-sonnet-4-6", "temperature": 0.0, "max_tokens": 1024},
        "samples": {"n": 4, "k": 1.0, "delta": 0.03},
        "threshold": 0.8,
        "rubric": rubric,
        "cases": [
            {"id": "landing-copy", "target": "targets/landing.txt", "weight": 1.0},
            {"id": "error-copy", "target": "targets/error.txt", "setup": "setups/error.json",
             "weight": 2.0},
        ],
    }


def _make_eval_dir(tmp: Path, config=None):
    d = tmp / ".servo" / "content-fidelity"
    (d / "targets").mkdir(parents=True, exist_ok=True)
    (d / "setups").mkdir(parents=True, exist_ok=True)
    (d / "targets" / "landing.txt").write_text("Welcome home.")
    (d / "targets" / "error.txt").write_text("Something went wrong.")
    (d / "setups" / "error.json").write_text(json.dumps({"code": 500}))
    cfg = config or _base_config()
    (d / "config.json").write_text(json.dumps(cfg, indent=2))
    return d


def _freeze(d: Path) -> dict:
    config = json.loads((d / "config.json").read_text())
    config["hashes"] = fe.artifact_hashes(config, d, CASES_KEY, FILE_FIELDS)
    config["approved_content_hash"] = fe.definition_hash(config, CASES_KEY, FILE_FIELDS)
    config["approval_status"] = "approved"
    (d / "config.json").write_text(json.dumps(config, indent=2))
    return config


class HashTests(unittest.TestCase):
    def test_sha256_text_is_stable_and_prefixed(self):
        h1 = fe.sha256_text("hello")
        h2 = fe.sha256_text("hello")
        self.assertEqual(h1, h2)
        self.assertTrue(h1.startswith("sha256:"))

    def test_sha256_file_matches_content(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "f.txt"
            p.write_text("hello")
            self.assertEqual(fe.sha256_file(p), fe.sha256_text("hello"))

    def test_definition_hash_generalizes_to_a_different_cases_key(self):
        config = _base_config()
        h = fe.definition_hash(config, CASES_KEY, FILE_FIELDS)
        self.assertTrue(h.startswith("sha256:"))
        # Changing an unrelated top-level field the hash doesn't track keeps
        # the hash stable (excludes bookkeeping / hash-bearing fields).
        config2 = dict(config)
        config2["approval_status"] = "approved"
        self.assertEqual(fe.definition_hash(config2, CASES_KEY, FILE_FIELDS), h)

    def test_definition_hash_changes_on_case_field_change(self):
        config = _base_config()
        h = fe.definition_hash(config, CASES_KEY, FILE_FIELDS)
        config["cases"][0]["target"] = "targets/other.txt"
        self.assertNotEqual(fe.definition_hash(config, CASES_KEY, FILE_FIELDS), h)

    def test_definition_hash_has_no_design_eval_specific_knowledge(self):
        """The shared module must carry zero design-eval-specific field names
        (e.g. "viewport") hardcoded into its logic — a config with no such
        key at all, and no extra_fields argument, must hash successfully
        with no special-casing, and adding an unrelated "viewport" value to
        the config must not affect the hash unless the caller explicitly
        asks for it via extra_fields."""
        config = _base_config()
        self.assertNotIn("viewport", config)
        h = fe.definition_hash(config, CASES_KEY, FILE_FIELDS)
        self.assertTrue(h.startswith("sha256:"))

        config_with_viewport = dict(config)
        config_with_viewport["viewport"] = {"width": 1, "height": 1}
        self.assertEqual(fe.definition_hash(config_with_viewport, CASES_KEY, FILE_FIELDS), h)

        # Confirm "viewport" is not referenced as logic (only documentation
        # prose, if at all) — the functions above are the load-bearing proof;
        # this is a belt-and-suspenders source scan for a hardcoded dict key.
        source = (HERE / "fidelity_eval.py").read_text()
        self.assertNotIn('"viewport"', source)

    def test_definition_hash_extra_fields_is_fully_generic(self):
        """A caller-supplied extra_fields tuple naming something other than
        "viewport" is pinned into the hash just like any other caller's field
        — proving extra_fields is a generic parameter, not a design-eval
        special case."""
        config = _base_config()
        config["reading_level"] = "grade-8"
        h_without = fe.definition_hash(config, CASES_KEY, FILE_FIELDS)
        h_with = fe.definition_hash(config, CASES_KEY, FILE_FIELDS, ("reading_level",))
        self.assertNotEqual(h_without, h_with)

        config["reading_level"] = "grade-10"
        h_with_changed = fe.definition_hash(config, CASES_KEY, FILE_FIELDS, ("reading_level",))
        self.assertNotEqual(h_with, h_with_changed)

    def test_artifact_hashes_covers_rubric_and_every_file_field(self):
        with tempfile.TemporaryDirectory() as t:
            d = _make_eval_dir(Path(t))
            config = json.loads((d / "config.json").read_text())
            hashes = fe.artifact_hashes(config, d, CASES_KEY, FILE_FIELDS)
            self.assertIn("rubric", hashes)
            self.assertIn("targets/landing.txt", hashes)
            self.assertIn("targets/error.txt", hashes)
            self.assertIn("setups/error.json", hashes)


class FreezeTests(unittest.TestCase):
    def test_freeze_then_validate_passes(self):
        with tempfile.TemporaryDirectory() as t:
            d = _make_eval_dir(Path(t))
            _freeze(d)
            config = json.loads((d / "config.json").read_text())
            fe.validate_freeze(config, d, CASES_KEY, FILE_FIELDS)  # no raise

    def test_unapproved_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            d = _make_eval_dir(Path(t))
            config = json.loads((d / "config.json").read_text())
            with self.assertRaises(fe.StaleError):
                fe.validate_freeze(config, d, CASES_KEY, FILE_FIELDS)

    def test_definition_change_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            d = _make_eval_dir(Path(t))
            config = _freeze(d)
            config["judge"]["model"] = "claude-haiku-4-5-20251001"
            with self.assertRaises(fe.StaleError):
                fe.validate_freeze(config, d, CASES_KEY, FILE_FIELDS)

    def test_rubric_change_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            d = _make_eval_dir(Path(t))
            config = _freeze(d)
            config["rubric"] = "different rubric"
            with self.assertRaises(fe.StaleError):
                fe.validate_freeze(config, d, CASES_KEY, FILE_FIELDS)

    def test_tampered_file_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            d = _make_eval_dir(Path(t))
            config = _freeze(d)
            (d / "targets" / "landing.txt").write_text("TAMPERED")
            with self.assertRaises(fe.StaleError):
                fe.validate_freeze(config, d, CASES_KEY, FILE_FIELDS)

    def test_missing_frozen_file_is_stale(self):
        with tempfile.TemporaryDirectory() as t:
            d = _make_eval_dir(Path(t))
            config = _freeze(d)
            (d / "targets" / "landing.txt").unlink()
            with self.assertRaises(fe.StaleError):
                fe.validate_freeze(config, d, CASES_KEY, FILE_FIELDS)

    def test_env_error_on_no_samples_to_aggregate(self):
        with self.assertRaises(fe.EnvError):
            fe.aggregate_lower_bound([], 1.0)


class AggregationTests(unittest.TestCase):
    def test_single_sample_has_no_stderr(self):
        self.assertAlmostEqual(fe.aggregate_lower_bound([0.83], 1.0), 0.83)

    def test_two_samples_lower_bound_below_mean_when_noisy(self):
        lb = fe.aggregate_lower_bound([0.9, 0.6], 1.0)
        self.assertLess(lb, 0.75)

    def test_n_samples_confident_stays_high(self):
        lb = fe.aggregate_lower_bound([0.9, 0.9, 0.9, 0.9], 1.0)
        self.assertAlmostEqual(lb, 0.9)

    def test_clamped_to_unit_interval(self):
        self.assertEqual(fe.aggregate_lower_bound([0.05, 0.0, 0.0], 5.0), 0.0)
        self.assertEqual(fe.aggregate_lower_bound([1.0, 1.0], 1.0), 1.0)


class JudgeReplyParseTests(unittest.TestCase):
    def test_extract_json_from_noisy_reply(self):
        self.assertEqual(
            fe._extract_json('Sure! {"score": 0.8} done'), '{"score": 0.8}')

    def test_extract_json_raises_without_object(self):
        with self.assertRaises(ValueError):
            fe._extract_json("no json object here")


class LedgerTests(unittest.TestCase):
    def test_write_ledger_appends_json_line(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            fe.write_ledger(d, {"a": 1})
            fe.write_ledger(d, {"a": 2})
            lines = (d / "ledger.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0]), {"a": 1})

    def test_write_ledger_is_best_effort_on_write_error(self):
        # A base_dir that doesn't exist can't be appended to; must not raise.
        with tempfile.TemporaryDirectory() as t:
            missing = Path(t) / "does" / "not" / "exist"
            fe.write_ledger(missing, {"a": 1})  # no raise


class SpliceHelperReuseTests(unittest.TestCase):
    """AC5: the splice helpers, invoked with a SECOND, distinct component
    name against a throwaway oracle.sh fixture, coexist with an existing
    component — mirroring test_design_eval.py's InstallTests but proving
    the logic isn't hardcoded to design-eval's COMPONENT constant."""

    ORACLE = (
        "#!/usr/bin/env bash\nset -euo pipefail\nTHRESHOLD=\"${THRESHOLD:-0.5}\"\n"
        "COMPONENTS=(\n  \"vitest:1.0\"\n)\n\nweighted_sum=\"0\"\ntotal_weight=\"0\"\n"
    )

    def _fragment(self, component: str) -> str:
        return (
            f"# SEED:start {component}\n"
            f"score_{component}() {{ echo 0.5; }}\n"
            f"# SEED:end {component}\n"
        )

    def test_two_distinct_components_coexist(self):
        component_a = "design_fidelity"
        component_b = "content_fidelity"
        text = self.ORACLE
        text = fe.splice_component(text, component_a, self._fragment(component_a))
        text = fe.splice_components_entry(text, component_a, 1.0)
        text = fe.splice_component(text, component_b, self._fragment(component_b))
        text = fe.splice_components_entry(text, component_b, 2.5)

        self.assertIn("# SEED:start design_fidelity", text)
        self.assertIn("# SEED:start content_fidelity", text)
        self.assertIn('"design_fidelity:1.0"', text)
        self.assertIn('"content_fidelity:2.5"', text)
        self.assertIn('"vitest:1.0"', text)  # baseline untouched

    def test_reinstall_second_component_is_idempotent(self):
        component_b = "content_fidelity"
        text = self.ORACLE
        text = fe.splice_component(text, component_b, self._fragment(component_b))
        text = fe.splice_components_entry(text, component_b, 1.0)
        text = fe.splice_component(text, component_b, self._fragment(component_b))
        text = fe.splice_components_entry(text, component_b, 3.0)

        self.assertEqual(text.count("# SEED:start content_fidelity"), 1)
        self.assertIn('"content_fidelity:3.0"', text)
        self.assertNotIn('"content_fidelity:1.0"', text)

    def test_uninstall_one_leaves_the_other_intact(self):
        component_a = "design_fidelity"
        component_b = "content_fidelity"
        text = self.ORACLE
        text = fe.splice_component(text, component_a, self._fragment(component_a))
        text = fe.splice_components_entry(text, component_a, 1.0)
        text = fe.splice_component(text, component_b, self._fragment(component_b))
        text = fe.splice_components_entry(text, component_b, 2.0)

        text = fe.unsplice_component(text, component_b)

        self.assertNotIn("content_fidelity", text)
        self.assertIn("# SEED:start design_fidelity", text)
        self.assertIn('"design_fidelity:1.0"', text)

    def test_manifest_register_and_deregister_two_components(self):
        with tempfile.TemporaryDirectory() as t:
            target = Path(t)
            (target / ".servo").mkdir()
            (target / ".servo" / "install.json").write_text(json.dumps({"components": ["vitest"]}))

            fe.register_manifest(target, "design_fidelity")
            fe.register_manifest(target, "content_fidelity")
            data = json.loads((target / ".servo" / "install.json").read_text())
            self.assertIn("design_fidelity", data["components"])
            self.assertIn("content_fidelity", data["components"])
            self.assertIn("vitest", data["components"])

            fe.deregister_manifest(target, "design_fidelity")
            data = json.loads((target / ".servo" / "install.json").read_text())
            self.assertNotIn("design_fidelity", data["components"])
            self.assertIn("content_fidelity", data["components"])


class ImportResolutionTests(unittest.TestCase):
    """AC2: score.py resolves fidelity_eval via a two-candidate probe. Each
    test runs score.py as a direct subprocess (mirroring oracle.sh's actual
    `python3 .servo/design-eval/score.py "$PWD"` invocation), never via
    importlib.spec_from_file_location, since that's the real oracle contract."""

    def _base_config(self):
        return {
            "schema_version": 1,
            "approval_status": "draft",
            "viewport": {"width": 392, "height": 812, "deviceScaleFactor": 2},
            "app_url": "http://localhost:4173/",
            "judge": {"model": "claude-sonnet-4-6", "temperature": 0.0, "max_tokens": 1024},
            "samples": {"n": 1, "k": 1.0, "delta": 0.03},
            "threshold": 0.8,
            "rubric": "Score fidelity 0..1.",
            "screens": [{"id": "home", "reference": "refs/home.png", "weight": 1.0}],
        }

    def _write_eval_dir(self, d: Path):
        (d / "refs").mkdir(parents=True, exist_ok=True)
        (d / "refs" / "home.png").write_bytes(b"\x89PNG-home")
        config = self._base_config()
        config["hashes"] = {
            "rubric": fe.sha256_text(config["rubric"]),
            "refs/home.png": fe.sha256_file(d / "refs" / "home.png"),
        }
        # Use design-eval's own definition_hash call shape via score.py's wrapper
        # is unnecessary here: freeze fields must just round-trip through
        # validate_freeze, so compute the hash the same way score.py will —
        # including design-eval's "viewport" extra_fields pin (score.py's
        # own _EXTRA_HASH_FIELDS constant).
        cases_key, file_fields = "screens", ("reference", "setup")
        config["approved_content_hash"] = fe.definition_hash(
            config, cases_key, file_fields, ("viewport",))
        config["approval_status"] = "approved"
        (d / "config.json").write_text(json.dumps(config, indent=2))

    def _run_score(self, score_path: Path) -> subprocess.CompletedProcess:
        env = {
            "PATH": "/usr/bin:/bin",
            "SERVO_DESIGN_EVAL_FAKE_SCORES": json.dumps({"home": [0.9]}),
        }
        return subprocess.run(
            [sys.executable, str(score_path), str(score_path.parent)],
            capture_output=True, text=True, timeout=30, env=env)

    def test_resolves_source_layout_sibling(self):
        # skills/design-eval/score.py next to skills/_common/fidelity_eval.py
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            design_eval_dir = root / "skills" / "design-eval"
            common_dir = root / "skills" / "_common"
            design_eval_dir.mkdir(parents=True)
            common_dir.mkdir(parents=True)
            shutil.copyfile(DESIGN_EVAL_DIR / "score.py", design_eval_dir / "score.py")
            shutil.copyfile(HERE / "fidelity_eval.py", common_dir / "fidelity_eval.py")
            self._write_eval_dir(design_eval_dir)

            proc = self._run_score(design_eval_dir / "score.py")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertAlmostEqual(float(proc.stdout.strip()), 0.9)

    def test_resolves_copied_flat_layout(self):
        # score.py and fidelity_eval.py copied flat side by side (the
        # .servo/design-eval/ deployment shape after install()).
        with tempfile.TemporaryDirectory() as t:
            target_dir = Path(t) / ".servo" / "design-eval"
            target_dir.mkdir(parents=True)
            shutil.copyfile(DESIGN_EVAL_DIR / "score.py", target_dir / "score.py")
            shutil.copyfile(HERE / "fidelity_eval.py", target_dir / "fidelity_eval.py")
            self._write_eval_dir(target_dir)

            proc = self._run_score(target_dir / "score.py")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertAlmostEqual(float(proc.stdout.strip()), 0.9)


class InitCopiesSharedModuleTests(unittest.TestCase):
    """AC3: design_eval.py::init() copies fidelity_eval.py alongside score.py
    and capture.mjs, sourced from skills/_common/."""

    def test_init_copies_fidelity_eval_byte_identical(self):
        de = _load("design_eval_cli_for_init_test", str(DESIGN_EVAL_DIR / "design_eval.py"))
        with tempfile.TemporaryDirectory() as t:
            target = Path(t)
            eval_dir = de.init(target)
            copied = eval_dir / "fidelity_eval.py"
            self.assertTrue(copied.is_file())
            self.assertEqual(copied.read_bytes(), (HERE / "fidelity_eval.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
