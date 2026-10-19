"""Opt-in real browser controls using the separately supplied frozen runtime."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import static_contract as app
import static_snapshot as snapshot


@unittest.skipUnless(
    os.environ.get("SERVO_STATIC_BROWSER_TESTS") == "1",
    "explicit frozen Playwright runtime required",
)
class BrowserTests(unittest.TestCase):
    def test_geometry_only_empty_role_does_not_request_text_paint(self):
        from playwright.sync_api import sync_playwright

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "scene.html").write_text(
                '<!doctype html><div id="context">Geometry unit control</div><main id="scene">'
                '<i class="dot" style="display:block;width:8px;height:8px;background:#f0b24e">'
                "</i></main>"
            )
            (source / "candidate.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "static_snapshot_candidate",
                        "entry": "/scene.html",
                        "metadata": [],
                        "resources": [
                            {
                                "url": "/scene.html",
                                "path": "scene.html",
                                "content_type": "text/html",
                            }
                        ],
                    }
                )
            )
            record = snapshot.build(source, root / "build")
            out = root / "observed"
            out.mkdir()
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                try:
                    with patch.object(
                        app, "_TEXT_PAINT", "()=>{throw Error('ghost text required')}"
                    ):
                        observed = app.acquire(
                            browser,
                            record,
                            root / "build",
                            {
                                "root": "#scene",
                                "document_witnesses": ["#context"],
                                "elements": {"marker": ".dot"},
                            },
                            {
                                "viewport": {"width": 800, "height": 600},
                                "device_scale": "1",
                                "color_scheme": "light",
                                "locale": "en-US",
                                "timezone": "UTC",
                                "reduced_motion": "reduce",
                            },
                            out,
                            constraints=[
                                {"id": prop, "element": "marker", "property": prop}
                                for prop in ("presence", "width", "height", "background-color")
                            ],
                        )
                finally:
                    browser.close()
            self.assertIsNone(observed["error"])
            marker = observed["elements"]["marker"]
            self.assertEqual(marker["count"], 1)
            self.assertTrue(marker["visible"])
            self.assertEqual(marker["raw"]["text"], "")
            self.assertEqual((marker["raw"]["width"], marker["raw"]["height"]), ("8", "8"))
            self.assertEqual(marker["raw"]["backgroundColor"], "rgb(240, 178, 78)")
            self.assertNotIn("textVisible", marker["raw"])

    def test_app_capture_preserves_mutations_and_closes_all_resources(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            for variant in (
                "baseline",
                "changed",
                "absent",
                "ambiguous",
                "hidden",
                "paint",
                "external",
                "paint-descendant",
                "indented",
                "nested",
                "partial",
                "transformed",
                "dynamic-residual",
                "required-unstable",
            ):
                with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    source = root / "source"
                    source.mkdir()
                    caption = '<h2 class="caption">Independent</h2>'
                    if variant == "changed":
                        caption = caption.replace("Independent", "Changed")
                    elif variant == "absent":
                        caption = ""
                    elif variant == "ambiguous":
                        caption += caption
                    elif variant == "hidden":
                        caption = caption.replace('class="caption"', 'class="caption" hidden')
                    elif variant == "paint":
                        caption = (
                            '<div style="contain:paint;height:0;overflow:visible">'
                            + caption
                            + "</div>"
                        )
                    elif variant == "paint-descendant":
                        caption = (
                            '<h2 class="caption" style="height:40px">'
                            '<span style="display:block;contain:paint;height:0;overflow:visible">'
                            "Independent</span></h2>"
                        )
                    elif variant == "indented":
                        caption = '<h2 class="caption">\n  Independent\n</h2>'
                    elif variant == "nested":
                        caption = '<h2 class="caption"><span>Indepen</span><b>dent</b></h2>'
                    elif variant == "partial":
                        caption = (
                            '<h2 class="caption" style="width:40px;overflow:hidden">'
                            "Independent</h2>"
                        )
                    elif variant == "transformed":
                        caption = (
                            '<h2 class="caption"><span style="display:inline-block;'
                            'transform:translateX(1px)">Independent</span></h2>'
                        )
                    (source / "panel.html").write_text(
                        '<!doctype html><div id="toolbar">Control</div><main id="frame">'
                        + caption
                        + '</main><script type="module" src="./view.mjs"></script>'
                    )
                    script = "await (await fetch('/data')).json();"
                    if variant == "dynamic-residual":
                        script += (
                            "const n=document.createElement('span');"
                            "document.querySelector('#frame').append(n);let i=0;"
                            "function tick(){n.textContent=String(++i);"
                            "document.querySelector('#frame').style.height=(100+i%2)+'px';"
                            "n.style.opacity=i%2?'0.5':'1';requestAnimationFrame(tick)}"
                            "requestAnimationFrame(tick);"
                        )
                    elif variant == "required-unstable":
                        script += (
                            "let i=0;function tick(){document.querySelector('.caption')"
                            ".style.fontSize="
                            "(20+(++i)/100)+'px';requestAnimationFrame(tick)}requestAnimationFrame(tick);"
                        )
                    (source / "view.mjs").write_text(
                        script
                        + (
                            "fetch('https://blocked.invalid/extra');"
                            if variant == "external"
                            else ""
                        )
                    )
                    (source / "data.json").write_text('{"real":"fixture-response"}')
                    (source / "candidate.json").write_text(
                        json.dumps(
                            {
                                "schema_version": 1,
                                "kind": "static_snapshot_candidate",
                                "entry": "/panel.html",
                                "metadata": [],
                                "resources": [
                                    {
                                        "url": "/data",
                                        "path": "data.json",
                                        "content_type": "application/json",
                                    },
                                    {
                                        "url": "/panel.html",
                                        "path": "panel.html",
                                        "content_type": "text/html",
                                    },
                                    {
                                        "url": "/view.mjs",
                                        "path": "view.mjs",
                                        "content_type": "text/javascript",
                                    },
                                ],
                            }
                        )
                    )
                    record = snapshot.build(source, root / "build")
                    out = root / "observed"
                    out.mkdir()
                    observed = app.acquire(
                        browser,
                        record,
                        root / "build",
                        {
                            "root": "#frame",
                            "document_witnesses": ["#toolbar"],
                            "elements": {"caption": ".caption"},
                        },
                        {
                            "viewport": {"width": 800, "height": 600},
                            "device_scale": "1",
                            "color_scheme": "light",
                            "locale": "en-US",
                            "timezone": "UTC",
                            "reduced_motion": "reduce",
                        },
                        out,
                        constraints=[
                            {"id": "caption-text", "element": "caption", "property": "text"},
                            {"id": "caption-size", "element": "caption", "property": "font-size"},
                            {"id": "root-width", "element": "root", "property": "width"},
                        ],
                    )
                    if variant == "required-unstable":
                        self.assertIn("unstable", observed["error"])
                    elif variant == "external":
                        self.assertIn("unapproved", observed["error"])
                    else:
                        self.assertIsNone(observed["error"])
                        self.assertEqual(len(observed["loaded_resources"]), 3)
                        node = observed["elements"]["caption"]
                        if variant == "transformed":
                            self.assertIn("unsupported APP text paint", node["error"])
                        elif variant in (
                            "baseline",
                            "changed",
                            "indented",
                            "nested",
                            "partial",
                            "dynamic-residual",
                        ):
                            self.assertEqual(
                                node["raw"]["text"],
                                "Changed"
                                if variant == "changed"
                                else "\n  Independent\n"
                                if variant == "indented"
                                else "Independent",
                            )
                            self.assertTrue(node["visible"])
                            self.assertTrue(node["raw"]["textVisible"])
                        elif variant == "absent":
                            self.assertEqual(node["count"], 0)
                        elif variant == "ambiguous":
                            self.assertEqual(node["count"], 2)
                        elif variant == "paint-descendant":
                            self.assertFalse(node["raw"]["textVisible"])
                        else:
                            self.assertFalse(node["visible"])
            browser.close()


if __name__ == "__main__":
    unittest.main()
