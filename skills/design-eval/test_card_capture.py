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
            result = card_capture.acquire(self.browser, entry, MAPPING, state, path / "shot.png")
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

    def test_unavailable_quality_does_not_overwrite_confirmed_required_facts(self):
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
            package = {
                "view": {"state": "normal"},
                "application_binding_intent": MAPPING,
                "target_revision": "unit-only",
                "approval": {"sha256": "unit-only"},
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
                    "browser_hash": card_bundle.file_hash(self.runtime.chromium.executable_path)
                },
                "quality": {"mode": "live", "config": "unit-only"},
                "evaluator_files": [],
            }
            with (
                patch.dict(
                    os.environ,
                    {"SERVO_GATE_RUN_ID": run_id, "SERVO_GATE_RESULT_DIR": str(invocation)},
                ),
                patch.object(card_evidence, "validated_policy", return_value=policy),
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
                patch("card_quality.run", side_effect=ValueError("judge unavailable")) as judge,
                patch("playwright.sync_api.sync_playwright") as runtime,
            ):
                runtime.return_value.__enter__.return_value = self.runtime
                result = card_evidence.evaluate(target / "unit-policy.json")
            self.assertEqual(judge.call_count, 1)
            self.assertEqual(result["summary"]["required_status"], "pass")
            self.assertEqual(result["constraints"][0]["status"], "pass")
            self.assertEqual(result["quality"]["mode"], "unavailable")
            self.assertIn("judge unavailable", result["quality"]["reason"])


if __name__ == "__main__":
    unittest.main()
