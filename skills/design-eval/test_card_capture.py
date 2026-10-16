"""Opt-in live controls; run with the declared project-local Playwright runtime."""

import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_bundle
import card_capture
import card_evidence

APP = """<!doctype html><style>
body{margin:0;font-family:system-ui,sans-serif}
article{width:240px}
header{width:240px;height:44px;background:#1e2329;box-sizing:border-box}
.title{font-size:20px;font-weight:600;color:#eef1f4}
.subtitle{font-size:12px;font-weight:400;color:#8a929c}
</style><main><article><header>
<div class="title">Trailhead</div><div class="subtitle">hiking route planner</div>
</header></article><button>Open</button></main>
<script>document.querySelector('button').onclick=()=>{
document.querySelector('.subtitle').textContent='opened'}</script>"""
MAPPING = {
    "root": "article",
    "elements": {
        "band": "header",
        "title": ".title",
        "subtitle": ".subtitle",
    },
    "driver": {"scope": "main", "selector": "button"},
}


@unittest.skipUnless(
    os.environ.get("SERVO_CARD_BROWSER_TESTS") == "1",
    "explicit project-local browser runtime required",
)
class LiveCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def observe(self, html=APP, state="normal"):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            entry = path / "index.html"
            entry.write_text(html)
            result = card_capture.acquire(
                self.browser,
                entry,
                MAPPING,
                state,
                path / "shot.png",
                expected_hash=card_bundle.raw(html.encode()),
            )
            self.assertTrue((path / "shot.png").is_file())
            return result

    def test_real_response_bytes_crop_and_open_action(self):
        normal, opened = self.observe(), self.observe(state="open")
        self.assertEqual(normal["elements"]["band"]["raw"]["width"], "240")
        self.assertEqual(normal["root"]["bounds"]["height"], "44")
        self.assertEqual(opened["elements"]["subtitle"]["raw"]["text"], "opened")
        self.assertIsNone(opened["acquisition_error"])
        self.assertTrue(opened["driver"]["outside_crop"])
        self.assertEqual(len(opened["loaded_resources"]), 1)

    def test_known_missing_title_and_noop_are_not_capture_unavailability(self):
        missing = self.observe(APP.replace('<div class="title">Trailhead</div>', ""))
        self.assertEqual(missing["elements"]["title"]["count"], 0)
        self.assertIsNone(missing["acquisition_error"])
        noop = self.observe(
            APP.replace("textContent='opened'", "textContent='hiking route planner'"), state="open"
        )
        self.assertIsNone(noop["acquisition_error"])
        self.assertIn("completed", noop["state_error"])

    def test_hidden_descendant_text_is_not_a_visible_required_title(self):
        html = APP.replace(
            ">Trailhead</div>", '><span style="visibility:hidden">Trailhead</span></div>'
        )
        result = self.observe(html)
        self.assertFalse(result["elements"]["title"]["visible"])
        self.assertIsNone(result["acquisition_error"])

    def test_fully_overflow_clipped_title_is_a_named_required_failure(self):
        for state in ("normal", "open"):
            for axis, dimension in (("x", "width"), ("y", "height")):
                for overflow in ("hidden", "clip", "scroll", "auto"):
                    with self.subTest(state=state, axis=axis, overflow=overflow):
                        html = APP.replace(
                            '<div class="title">Trailhead</div>',
                            f'<div style="{dimension}:0;overflow-{axis}:{overflow}">'
                            '<div class="title" style="width:240px">Trailhead</div></div>',
                        )
                        observed = self.observe(html, state=state)
                        identity = state + "-title-text"
                        package = {
                            "view": {"state": state},
                            "required_inventory": {"required_ids": [identity]},
                            "source_facts": [{"id": identity, "value": "Trailhead"}],
                            "policy": {
                                "constraints": [{
                                    "id": identity,
                                    "binding_id": "title",
                                    "required": True,
                                    "comparison": "exact",
                                    "normalizer": "text-content-exact-v0",
                                    "units": "text",
                                    "tolerance": "0",
                                }],
                            },
                        }
                        actual = observed["elements"]["title"]["raw"]["text"]
                        rows = card_evidence.compare(
                            package,
                            {**observed, "facts": [{"id": identity, "value": actual}]},
                        )
                        self.assertIsNone(observed["acquisition_error"])
                        self.assertFalse(observed["elements"]["title"]["visible"])
                        self.assertFalse(observed["elements"]["title"]["raw"]["textVisible"])
                        self.assertEqual(rows[0]["id"], identity)
                        self.assertEqual(rows[0]["status"], "fail")
                        self.assertEqual(rows[0]["actual"], "Trailhead")
                        self.assertIn("not visible", rows[0]["reason"])

    def test_unclipped_and_partially_clipped_wrappers_keep_visible_text(self):
        for state in ("normal", "open"):
            for style in (
                "",
                "display:contents",
                "height:0;overflow:visible",
                "width:0;overflow:visible",
                "height:30px;overflow:hidden",
                "height:10px;overflow:hidden",
                "width:20px;overflow:hidden",
            ):
                with self.subTest(state=state, style=style):
                    html = APP.replace(
                        '<div class="title">Trailhead</div>',
                        f'<div style="{style}">'
                        '<div class="title" style="width:240px">Trailhead</div></div>',
                    )
                    observed = self.observe(html, state=state)
                    self.assertIsNone(observed["acquisition_error"])
                    self.assertIsNone(observed["state_error"])
                    self.assertTrue(observed["elements"]["title"]["visible"])
                    self.assertTrue(observed["elements"]["title"]["raw"]["textVisible"])
                    expected = "opened" if state == "open" else "hiking route planner"
                    self.assertEqual(observed["elements"]["subtitle"]["raw"]["text"], expected)

    def test_modern_transparent_descendant_is_hidden_but_contents_wrapper_is_visible(self):
        for style, visible in (
            ("color:color(srgb 0 0 0 / 0)", False),
            ("display:contents", True),
        ):
            with self.subTest(style=style):
                html = APP.replace(
                    ">Trailhead</div>", f'><span style="{style}">Trailhead</span></div>'
                )
                result = self.observe(html)
                self.assertEqual(result["elements"]["title"]["visible"], visible)
                self.assertIsNone(result["acquisition_error"])

    def test_required_text_outside_crop_is_not_visible_and_driver_provenance_is_geometric(self):
        moved = self.observe(APP.replace(".title{", ".title{transform:translateX(500px);"))
        self.assertFalse(moved["elements"]["title"]["visible"])
        overlay = self.observe(APP + "<style>button{position:absolute;top:0;left:0}</style>")
        self.assertFalse(overlay["driver"]["outside_crop"])
        self.assertIn("crop", overlay["acquisition_error"])

    def test_actual_unrounded_geometry_controls(self):
        for value, beyond in (("239", False), ("241", False), ("238.98", True), ("241.02", True)):
            actual = self.observe(APP.replace("header{width:240px", "header{width:" + value + "px"))
            delta = abs(float(actual["elements"]["band"]["raw"]["width"]) - 240)
            self.assertEqual(delta > 1, beyond)
            self.assertEqual(actual["root"]["bounds"]["width"], "240")

    def test_external_resource_is_explicit_refusal(self):
        html = APP + "<script>fetch('https://unapproved.invalid/x')</script>"
        result = self.observe(html)
        self.assertIn("unapproved", result["acquisition_error"])

    def test_loaded_document_must_match_declared_output_not_a_self_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "index.html"
            entry.write_text(APP.replace("Trailhead", "Substituted"))
            result = card_capture.acquire(
                self.browser,
                entry,
                MAPPING,
                "normal",
                root / "shot.png",
                expected_hash=card_bundle.raw(APP.encode()),
            )
            self.assertIn("declared", result["acquisition_error"])

    def test_unavailable_quality_does_not_overwrite_confirmed_required_facts(self):
        def unavailable(*args, **kwargs):
            raise ValueError("judge unavailable")

        result = self._evaluate_quality(unavailable)
        self.assertEqual(result["summary"]["required_status"], "pass")
        self.assertEqual(result["constraints"][0]["status"], "pass")
        self.assertEqual(result["quality"]["mode"], "unavailable")
        self.assertIn("judge unavailable", result["quality"]["reason"])

    def test_original_acquisition_files_cannot_be_reblessed_during_quality(self):
        for suffix in (".png", ".observations.json"):
            with self.subTest(suffix=suffix):
                def mutate(config, shots, *args, suffix=suffix, **kwargs):
                    path = shots["normal"].with_suffix(suffix)
                    original = path.read_bytes()
                    path.write_bytes(b"changed-during-quality")
                    path.write_bytes(original)
                    return {"mode": "live", "composite": 0.99}

                result = self._evaluate_quality(mutate)
                self.assertEqual(result["summary"]["required_status"], "unknown")
                self.assertIn("acquisition artifact changed", result["constraints"][0]["reason"])

    def _evaluate_quality(self, quality_action):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            source = target / "source"
            source.mkdir()
            (source / "index.html").write_text(APP)
            card_bundle.publish(
                source / "candidate.json",
                {
                    "schema_version": 1,
                    "entry": "index.html",
                    "dependencies": [],
                    "assets": [],
                },
            )
            card_bundle.build(source, target / "build")
            shutil.copytree(target / "build/output", target / "delivery")
            card_bundle.publish(
                target / "selection.json", {"build": "build", "delivery": "delivery"}
            )
            run_id = str(uuid.uuid4())
            invocation = target / ".servo/gate-runs" / run_id
            invocation.mkdir(parents=True)
            card_bundle.publish(
                invocation / "invocation.json",
                {
                    "schema_version": 1,
                    "kind": "gate_invocation",
                    "run_id": run_id,
                },
            )
            (target / "normal.json").write_text("{}")
            (target / "refs").mkdir()
            (target / "refs/normal.png").write_bytes(b"unit-reference-only")
            package = {
                "view": {"state": "normal"},
                "application_binding_intent": MAPPING,
                "target_revision": "unit-only",
                "approval": {"sha256": "unit-only"},
                "reference": {"sha256": card_bundle.raw(b"unit-reference-only")[7:]},
                "required_inventory": {"required_ids": ["normal-title-text"]},
                "source_facts": [
                    {
                        "id": "normal-title-text",
                        "element": "title",
                        "observation": "text",
                        "value": "Trailhead",
                    }
                ],
                "policy": {
                    "constraints": [
                        {
                            "id": "normal-title-text",
                            "required": True,
                            "binding_id": "title",
                            "comparison": "exact",
                            "normalizer": "text-content-exact-v0",
                            "tolerance": "0",
                            "units": "text",
                        }
                    ]
                },
            }
            policy = {
                "target": str(target),
                "producer": "unit-only",
                "references": str(target),
                "selection": "selection.json",
                "output_root": "runs/{run_id}/design",
                "runtime": {
                    "browser_hash": card_bundle.file_hash(self.runtime.chromium.executable_path),
                    "executable": str(Path(sys.executable).resolve()),
                },
                "quality": {"mode": "live", "config": str(target / "unit-quality.json")},
                "evaluator_files": [],
            }
            with (
                patch.dict(
                    os.environ,
                    {
                        "SERVO_GATE_RUN_ID": run_id,
                        "SERVO_GATE_RESULT_DIR": str(invocation),
                        "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
                    },
                ),
                patch.object(card_evidence, "validated_policy", return_value=policy),
                patch.object(card_evidence, "assert_driver_seal"),
                patch.object(
                    sys,
                    "pycache_prefix",
                    str(target / ".servo/gate-runs" / run_id / "python-source-only"),
                ),
                patch.object(
                    card_evidence,
                    "producer_at",
                    return_value=SimpleNamespace(
                        VERSION="unit-only",
                        decimal=str,
                        colour=str,
                        family=str,
                        size=str,
                        weight=int,
                        Refusal=ValueError,
                    ),
                ),
                patch.object(card_evidence, "packages_at", return_value={"normal": package}),
                patch("card_quality.run", side_effect=quality_action) as judge,
                patch("playwright.sync_api.sync_playwright") as runtime,
            ):
                runtime.return_value.__enter__.return_value = self.runtime
                result = card_evidence.evaluate(target / "unit-policy.json")
            self.assertEqual(judge.call_count, 1)
            return result


if __name__ == "__main__":
    unittest.main()
