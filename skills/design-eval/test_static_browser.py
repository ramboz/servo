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
    def test_effective_visibility_override_preserves_text_and_geometry(self):
        from playwright.sync_api import sync_playwright

        bindings = {
            "root": "#scene",
            "document_witnesses": ["#scene > section"],
            "elements": {"caption": ".caption", "marker": ".dot"},
        }
        constraints = [
            {"id": "caption-presence", "element": "caption", "property": "presence"},
            {"id": "caption-text", "element": "caption", "property": "text"},
            {"id": "marker-presence", "element": "marker", "property": "presence"},
        ]
        core = {
            "inventory": [row["id"] for row in constraints],
            "policy": [
                {**row, "comparison": "exact" if row["property"] == "text" else "present",
                 "tolerance": "0"}
                for row in constraints
            ],
            "facts": [
                {"id": row["id"], "value": "Visible heading" if row["property"] == "text" else True}
                for row in constraints
            ],
        }
        variants = (
            "override",
            "hidden-attribute-overridden",
            "hidden-attribute",
            "true-hidden",
            "opacity",
            "nonzero-opacity",
            "inline-opacity",
            "boxless-opacity",
            "boxless-nonzero-opacity",
            "boxless-opacity-with-independent-hidden",
            "hidden-text-leaf",
            "opaque-text-fill",
            "transparent-text-fill",
            "transparent-text-colour",
            "transparent-shadow",
            "transparent-stroke",
            "transparent-background-clip",
            "display",
            "content-hidden",
            "boxless-overflow",
            "inline-overflow",
            "boxless-content-hidden",
            "inline-content-hidden",
            "overflow-clipped-x",
            "overflow-clipped-y",
            "paint-contained",
            "partial-clip",
            "transform",
            "transformed-text-leaf",
            "zero-transformed-text-leaf",
            "opacity-hidden-text-with-transform",
            "known-hidden-fragment-before-unsupported",
            "known-hidden-fragment-after-unsupported",
            "hidden-with-transform",
            "opacity-with-transform",
            "content-hidden-with-transform",
            "unsupported-zero-geometry",
        )
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 800, "height": 600})
                for name in variants:
                    with self.subTest(variant=name):
                        page.set_content(
                            '<!doctype html><main id="scene" style="width:300px;height:180px">'
                            '<section style="visibility:hidden">'
                            '<h2 class="caption" style="visibility:visible">Visible '
                            '<span style="visibility:hidden"><b style="visibility:visible">'
                            'heading</b></span></h2><i class="dot" style="visibility:visible;'
                            'display:block;width:8px;height:8px;background:#f0b24e"></i>'
                            "</section></main>"
                        )
                        native = page.evaluate(
                            """name=>{
                            const wrapper=document.querySelector('section'),
                              caption=document.querySelector('.caption'),
                              leaf=document.querySelector('b'),marker=document.querySelector('.dot');
                            if(name==='hidden-attribute-overridden'){
                              wrapper.hidden=caption.hidden=leaf.hidden=marker.hidden=true;
                              wrapper.style.display=caption.style.display='block';
                              leaf.style.display='inline';
                            }else if(name==='hidden-attribute'){wrapper.hidden=true;}
                            else if(name==='true-hidden'){
                              caption.style.visibility=leaf.style.visibility=
                                marker.style.visibility='inherit';
                            }else if(name==='opacity'){
                              wrapper.style.opacity='0';
                              caption.style.opacity=leaf.style.opacity=marker.style.opacity='1';
                            }else if(name==='nonzero-opacity'){
                              wrapper.style.opacity='0.5';
                            }else if(name==='inline-opacity'){
                              wrapper.style.display='inline';wrapper.style.opacity='0';
                            }else if(name==='boxless-opacity'||name==='boxless-nonzero-opacity'||
                                     name==='boxless-opacity-with-independent-hidden'){
                              wrapper.style.display='contents';
                              wrapper.style.opacity=name==='boxless-nonzero-opacity'?'0.5':'0';
                              if(name==='boxless-opacity-with-independent-hidden'){
                                document.querySelector('#scene').style.opacity='0';
                              }
                            }else if(name==='hidden-text-leaf'){leaf.style.visibility='hidden';}
                            else if(name==='opaque-text-fill'){
                              caption.style.color='transparent';
                              caption.style.webkitTextFillColor='black';
                            }else if(name==='transparent-text-fill'){
                              caption.style.webkitTextFillColor='transparent';
                            }else if(name==='transparent-text-colour'){
                              caption.style.color='transparent';
                            }else if(name==='transparent-shadow'){
                              caption.style.color='transparent';
                              caption.style.textShadow='1px 1px 0 black';
                            }else if(name==='transparent-stroke'){
                              caption.style.webkitTextFillColor='transparent';
                              caption.style.webkitTextStroke='1px black';
                            }else if(name==='transparent-background-clip'){
                              caption.style.webkitTextFillColor='transparent';
                              caption.style.backgroundImage='linear-gradient(black,black)';
                              caption.style.backgroundClip='text';
                            }
                            else if(name==='display'){wrapper.style.display='none';}
                            else if(name==='content-hidden'){
                              wrapper.style.contentVisibility='hidden';
                            }else if(name==='boxless-overflow'){
                              wrapper.style.display='contents';wrapper.style.overflow='hidden';
                            }else if(name==='inline-overflow'){
                              wrapper.style.display='inline';wrapper.style.overflow='hidden';
                            }else if(name==='boxless-content-hidden'){
                              wrapper.style.display='contents';
                              wrapper.style.contentVisibility='hidden';
                            }else if(name==='inline-content-hidden'){
                              wrapper.style.display='inline';
                              wrapper.style.contentVisibility='hidden';
                            }else if(name==='overflow-clipped-x'){
                              wrapper.style.width='0';wrapper.style.overflow='hidden';
                            }else if(name==='overflow-clipped-y'){
                              wrapper.style.height='0';wrapper.style.overflow='hidden';
                            }else if(name==='paint-contained'){
                              wrapper.style.height='0';wrapper.style.contain='paint';
                            }else if(name==='partial-clip'){
                              wrapper.style.width='4px';wrapper.style.overflow='hidden';
                            }else if(name==='transform'){
                              wrapper.style.transform='translateX(1px)';
                            }else if(name==='transformed-text-leaf'){
                              leaf.style.display='inline-block';
                              leaf.style.transform='translateX(1px)';
                            }else if(name==='zero-transformed-text-leaf'){
                              leaf.style.display='inline-block';leaf.style.transform='scale(0)';
                            }else if(name==='opacity-hidden-text-with-transform'){
                              leaf.parentElement.style.opacity='0';
                              leaf.style.display='inline-block';
                              leaf.style.transform='translateX(1px)';
                            }else if(name==='known-hidden-fragment-before-unsupported'||
                                     name==='known-hidden-fragment-after-unsupported'){
                              const prefix=caption.firstChild,span=document.createElement('span');
                              caption.insertBefore(span,prefix);span.append(prefix);
                              if(name==='known-hidden-fragment-before-unsupported'){
                                span.style.opacity='0';leaf.style.display='inline-block';
                                leaf.style.transform='translateX(1px)';
                              }else{
                                span.style.display='inline-block';
                                span.style.transform='translateX(1px)';
                                leaf.parentElement.style.opacity='0';
                              }
                            }else if(name==='hidden-with-transform'){
                              wrapper.style.display='none';
                              wrapper.style.transform='translateX(1px)';
                            }else if(name==='opacity-with-transform'){
                              wrapper.style.opacity='0';
                              wrapper.style.transform='translateX(1px)';
                            }else if(name==='content-hidden-with-transform'){
                              wrapper.style.contentVisibility='hidden';
                              wrapper.style.transform='translateX(1px)';
                            }else if(name==='unsupported-zero-geometry'){
                              wrapper.style.transform='scale(0)';
                            }
                            const visible=el=>el.checkVisibility(
                              {checkOpacity:true,checkVisibilityCSS:true});
                            return {wrapper:getComputedStyle(wrapper).visibility,
                              caption:getComputedStyle(caption).visibility,
                              leaf:getComputedStyle(leaf).visibility,
                              wrapperDisplay:getComputedStyle(wrapper).display,
                              wrapperClientWidth:wrapper.clientWidth,
                              wrapperClientHeight:wrapper.clientHeight,
                              captionColour:getComputedStyle(caption).color,
                              captionFill:getComputedStyle(caption).webkitTextFillColor,
                              captionShadow:getComputedStyle(caption).textShadow,
                              captionStroke:getComputedStyle(caption).webkitTextStrokeWidth,
                              captionBackgroundClip:getComputedStyle(caption).backgroundClip,
                              wrapperHidden:wrapper.hidden,captionHidden:caption.hidden,
                              leafHidden:leaf.hidden,markerHidden:marker.hidden,
                              captionVisible:visible(caption),markerVisible:visible(marker)};
                            }""",
                            name,
                        )
                        elements = app.observe_roles(page, bindings, constraints)
                        rows = {
                            row["id"]: row["status"]
                            for row in app.compare(core, {"elements": elements}, None)
                        }
                        if name in (
                            "override", "hidden-attribute-overridden", "hidden-text-leaf",
                            "nonzero-opacity", "partial-clip",
                            "boxless-overflow", "inline-overflow", "opaque-text-fill",
                            "boxless-content-hidden", "inline-content-hidden",
                            "transparent-text-fill", "transparent-text-colour",
                            "opacity-hidden-text-with-transform",
                            "known-hidden-fragment-before-unsupported",
                            "known-hidden-fragment-after-unsupported",
                        ):
                            self.assertEqual(native["wrapper"], "hidden")
                            self.assertEqual(native["caption"], "visible")
                            self.assertTrue(native["captionVisible"])
                            self.assertTrue(native["markerVisible"])
                            if name == "hidden-attribute-overridden":
                                self.assertEqual(native["wrapperDisplay"], "block")
                                self.assertTrue(all(native[key] for key in (
                                    "wrapperHidden", "captionHidden", "leafHidden", "markerHidden",
                                )))
                            self.assertEqual(
                                rows,
                                {"caption-presence": "pass",
                                 "caption-text": "fail" if name in (
                                     "hidden-text-leaf", "transparent-text-fill",
                                     "transparent-text-colour",
                                     "opacity-hidden-text-with-transform",
                                     "known-hidden-fragment-before-unsupported",
                                     "known-hidden-fragment-after-unsupported",
                                 ) else "pass",
                                 "marker-presence": "pass"},
                                {"native": native, "observed": elements},
                            )
                        elif name in (
                            "transformed-text-leaf", "zero-transformed-text-leaf",
                            "transparent-shadow", "transparent-stroke",
                            "transparent-background-clip",
                        ):
                            self.assertEqual(
                                rows,
                                {"caption-presence": "unknown", "caption-text": "unknown",
                                 "marker-presence": "pass"},
                                elements,
                            )
                        else:
                            expected = (
                                "unknown"
                                if name in (
                                    "transform", "unsupported-zero-geometry", "boxless-opacity",
                                    "boxless-nonzero-opacity",
                                )
                                else "fail"
                            )
                            self.assertEqual(set(rows.values()), {expected}, elements)
            finally:
                browser.close()

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
                "invalid-binding",
                "absence-plus-instability",
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
                    elif variant in ("required-unstable", "absence-plus-instability"):
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
                    elements = {"caption": "[" if variant == "invalid-binding" else ".caption"}
                    constraints = [
                        {"id": "caption-text", "element": "caption", "property": "text"},
                        {"id": "caption-size", "element": "caption", "property": "font-size"},
                        {"id": "root-width", "element": "root", "property": "width"},
                    ]
                    if variant == "absence-plus-instability":
                        elements["missing"] = ".missing"
                        constraints.append(
                            {"id": "missing-presence", "element": "missing", "property": "presence"}
                        )
                    observed = app.acquire(
                        browser,
                        record,
                        root / "build",
                        {
                            "root": "#frame",
                            "document_witnesses": ["#toolbar"],
                            "elements": elements,
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
                        constraints=constraints,
                    )
                    if variant == "required-unstable":
                        self.assertIn("unstable", observed["error"])
                    elif variant == "absence-plus-instability":
                        self.assertIn("missing", observed["elements"])
                        self.assertEqual(observed["elements"]["missing"]["count"], 0)
                        self.assertIn("caption-size", observed["settlement"]["unstable_ids"])
                        self.assertNotIn("missing-presence", observed["settlement"]["unstable_ids"])
                        self.assertEqual(len(observed["settlement"]["samples"]), 60)
                        core = {
                            "policy": [
                                {
                                    "id": "missing-presence",
                                    "element": "missing",
                                    "property": "presence",
                                    "normalizer": "explicit-unit",
                                    "comparison": "present",
                                    "tolerance": "0",
                                    "units": "boolean",
                                }
                            ],
                            "inventory": ["missing-presence"],
                            "facts": [{"id": "missing-presence", "value": True}],
                        }
                        self.assertEqual(app.compare(core, observed, None)[0]["status"], "fail")
                        changing = {
                            "policy": [
                                {
                                    "id": "caption-size",
                                    "element": "caption",
                                    "property": "font-size",
                                    "normalizer": "css-scalar-v0",
                                    "comparison": "absolute-inclusive",
                                    "tolerance": "0",
                                    "units": "CSSpx",
                                }
                            ],
                            "inventory": ["caption-size"],
                            "facts": [{"id": "caption-size", "value": "18"}],
                        }
                        row = app.compare(changing, observed, None)[0]
                        self.assertEqual(row["status"], "unknown")
                        self.assertIn("did not settle", row["reason"])
                    elif variant == "invalid-binding":
                        core = {
                            "policy": [
                                {
                                    "id": "caption-text",
                                    "element": "caption",
                                    "property": "text",
                                    "normalizer": "explicit-unit",
                                    "comparison": "exact",
                                    "tolerance": "0",
                                    "units": "text",
                                }
                            ],
                            "inventory": ["caption-text"],
                            "facts": [{"id": "caption-text", "value": "Independent"}],
                        }
                        self.assertEqual(app.compare(core, observed, None)[0]["status"], "unknown")
                        self.assertIsNone(observed["elements"]["caption"]["count"])
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
