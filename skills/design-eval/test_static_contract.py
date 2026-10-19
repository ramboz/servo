"""Finite APP observation policy, not a CSS parser or visual-quality evaluator."""

import importlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


class FamilyTests(unittest.TestCase):
    def test_explicit_app_family_grammar_and_unchanged_c0_representation(self):
        app = importlib.import_module("static_contract")
        self.assertEqual(
            app.family(" SYSTEM-UI , sans-serif "),
            [{"kind": "generic", "value": "system-ui"}, {"kind": "generic", "value": "sans-serif"}],
        )
        self.assertEqual(app.family('"Inter", sans-serif'), app.family("'Inter', sans-serif"))
        self.assertEqual(app.family('"A  B", monospace')[0]["value"], "A  B")
        self.assertEqual(app.family("A \t B, monospace")[0]["value"], "A B")
        self.assertNotEqual(app.family("system-ui"), app.family('"system-ui"'))
        self.assertNotEqual(app.family("Menlo, Consolas"), app.family("Consolas, Menlo"))
        self.assertNotEqual(app.family("Menlo"), app.family("menlo"))
        self.assertEqual(
            app.family('ui-monospace, SFMono-Regular, -apple-system, "system-ui"'),
            [
                {"kind": "generic", "value": "ui-monospace"},
                {"kind": "named", "value": "SFMono-Regular"},
                {"kind": "named", "value": "-apple-system"},
                {"kind": "named", "value": "system-ui"},
            ],
        )
        for name in app.GENERICS:
            self.assertEqual(app.family(name), [{"kind": "generic", "value": name}])
        for value in (
            "",
            "system-ui,",
            '"A,B"',
            '"A\\B"',
            '"É"',
            "Inter/*x*/",
            "generic(fangsong)",
            "inherit",
            "INITIAL",
            "unset",
            "revert",
            "revert-layer",
            "default",
            "emoji",
            "A inherit",
            "--variable",
            "-1font",
            "A\nB",
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "family"):
                app.family(value)
        for value in ("inherit", "default", "emoji"):
            self.assertEqual(app.family('"' + value + '"'), [{"kind": "named", "value": value}])


class SnapshotTests(unittest.TestCase):
    def test_selected_source_refuses_lexical_traversal_and_symlink_alias(self):
        app = importlib.import_module("static_contract")
        snapshot = importlib.import_module("static_snapshot")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target"
            source = target / "candidate"
            source.mkdir(parents=True)
            (source / "panel.html").write_text("<p>Separate source-authority control</p>")
            (source / "candidate.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "static_snapshot_candidate",
                        "entry": "/panel.html",
                        "metadata": [],
                        "resources": [
                            {
                                "url": "/panel.html",
                                "path": "panel.html",
                                "content_type": "text/html",
                            }
                        ],
                    }
                )
            )
            record = snapshot.build(source, target / "build")
            shutil.copytree(target / "build/output", target / "delivery")
            app.bundle.publish(
                target / "selection.json", {"build": "build", "delivery": "delivery"}
            )
            policy = {"target": str(target), "selection": "selection.json"}
            app.current_binding(policy)
            shutil.copytree(source, root / "outside")
            alias = target / "alias"
            alias.symlink_to(source, target_is_directory=True)
            traversal = target / "../outside"
            self.assertTrue(
                traversal.is_relative_to(target)
            )  # The old lexical guard's counterexample.
            for name in (str(traversal), str(alias)):
                changed = {**record, "source": name}
                (target / "build/build.json").write_text(json.dumps(changed))
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "source escapes"):
                    app.current_binding(policy)
            (target / "build/build.json").write_text(json.dumps(record))
            app.current_binding(policy)

    def test_closed_multiresource_snapshot_and_independent_delivery(self):
        snapshot = importlib.import_module("static_snapshot")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "panel.html").write_text('<script src="./view.mjs" type="module"></script>')
            (source / "view.mjs").write_text("document.title='independent';")
            (source / "acquisition.json").write_text('{"scope":"snapshot-only"}')
            config = {
                "schema_version": 1,
                "kind": "static_snapshot_candidate",
                "entry": "/panel.html",
                "metadata": ["acquisition.json"],
                "resources": [
                    {"url": "/panel.html", "path": "panel.html", "content_type": "text/html"},
                    {"url": "/view.mjs", "path": "view.mjs", "content_type": "text/javascript"},
                ],
            }
            (source / "candidate.json").write_text(json.dumps(config))
            build = root / "build"
            record = snapshot.build(source, build)
            delivery = root / "delivery"
            shutil.copytree(build / "output", delivery)
            self.assertEqual(snapshot.verify(record, build, delivery), record)
            for path in (source / "view.mjs", build / "output/view.mjs", delivery / "view.mjs"):
                old = path.read_bytes()
                path.write_bytes(old + b"/* changed */")
                with self.assertRaisesRegex(ValueError, "changed|mismatch"):
                    snapshot.verify(record, build, delivery)
                path.write_bytes(old)
            (source / "extra").write_text("unlisted")
            with self.assertRaisesRegex(ValueError, "closure"):
                snapshot.verify(record, build, delivery)
            (source / "extra").unlink()
            (delivery / "extra").write_text("unlisted")
            with self.assertRaisesRegex(ValueError, "closure|mismatch"):
                snapshot.verify(record, build, delivery)
            (delivery / "extra").unlink()
            (delivery / "view.mjs").unlink()
            (delivery / "view.mjs").symlink_to(source / "view.mjs")
            with self.assertRaisesRegex(ValueError, "symlink"):
                snapshot.verify(record, build, delivery)


class ComparisonTests(unittest.TestCase):
    def test_missing_observation_flags_are_unknown_not_success_or_absence(self):
        app = importlib.import_module("static_contract")
        for prop, expected, raw in (
            ("presence", True, {}),
            ("text", "Stable", {"text": "Stable"}),
        ):
            core = {
                "policy": [
                    {
                        "id": "one",
                        "element": "element",
                        "property": prop,
                        "normalizer": "explicit-unit-test",
                        "comparison": "exact",
                        "units": "boolean" if prop == "presence" else "text",
                        "tolerance": "0",
                    }
                ],
                "inventory": ["one"],
                "facts": [{"id": "one", "value": expected}],
            }
            node = {"count": 1, "raw": raw}
            if prop == "text":
                node["visible"] = True
            observed = {"elements": {"element": node}, "error": None}
            with self.subTest(prop=prop):
                self.assertEqual(app.compare(core, observed, None)[0]["status"], "unknown")

    def test_exact_empty_text_on_visible_box_does_not_require_ghost_ink(self):
        app = importlib.import_module("static_contract")
        core = {
            "policy": [
                {
                    "id": "empty-text",
                    "element": "marker",
                    "property": "text",
                    "normalizer": "text-content-exact-v0",
                    "comparison": "exact",
                    "units": "text",
                    "tolerance": "0",
                }
            ],
            "inventory": ["empty-text"],
            "facts": [{"id": "empty-text", "value": ""}],
        }
        observation = {
            "error": None,
            "elements": {
                "marker": {
                    "count": 1,
                    "visible": True,
                    "raw": {"text": "", "textVisible": False},
                }
            },
        }
        result = app.compare(core, observation, None)
        self.assertEqual(result[0]["status"], "pass")
        self.assertEqual(result[0]["actual"], "")
        observation["elements"]["marker"]["visible"] = False
        self.assertEqual(app.compare(core, observation, None)[0]["status"], "fail")

    def test_finite_inventory_visible_failures_and_unknowns_without_same_value_guard(self):
        app = importlib.import_module("static_contract")
        rows = [
            {
                "id": "caption-presence",
                "element": "caption",
                "property": "presence",
                "normalizer": "unique-scoped-presence-v0",
                "comparison": "present",
                "units": "boolean",
                "tolerance": "0",
            },
            {
                "id": "caption-text",
                "element": "caption",
                "property": "text",
                "normalizer": "text-content-exact-v0",
                "comparison": "exact",
                "units": "text",
                "tolerance": "0",
            },
        ]
        core = {
            "policy": rows,
            "inventory": [r["id"] for r in rows],
            "facts": [
                {"id": "caption-presence", "value": True},
                {"id": "caption-text", "value": "Independent"},
            ],
        }
        raw = {
            "elements": {
                "caption": {
                    "count": 1,
                    "visible": True,
                    "raw": {"text": "Changed", "textVisible": True},
                }
            },
            "error": None,
        }
        result = app.compare(core, raw, None)
        self.assertEqual([r["status"] for r in result], ["pass", "fail"])
        self.assertEqual(result[1]["actual"], "Changed")
        raw["elements"]["caption"]["visible"] = False
        self.assertTrue(all(r["status"] == "fail" for r in app.compare(core, raw, None)))
        raw["elements"]["caption"]["count"] = 0
        self.assertTrue(all(r["status"] == "fail" for r in app.compare(core, raw, None)))
        raw["elements"]["caption"]["count"] = 2
        self.assertTrue(all(r["status"] == "unknown" for r in app.compare(core, raw, None)))
        raw["elements"]["caption"].update(count=1, visible=True)
        raw["error"] = "unlisted resource"
        self.assertEqual([r["status"] for r in app.compare(core, raw, None)], ["unknown", "fail"])
        core["inventory"].append("unobserved")
        with self.assertRaisesRegex(ValueError, "inventory"):
            app.compare(core, raw, None)


class PolicyTests(unittest.TestCase):
    def test_browser_membership_refuses_added_file_without_launching_browser(self):
        app = importlib.import_module("static_contract")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            browser = root / "isolated-browser-root"
            browser.mkdir()
            (browser / "binary").write_bytes(b"isolated test bytes, not a browser")
            expected = app.browser_membership(browser)
            manifest = root / "browser-membership.json"
            manifest.write_text(json.dumps(expected))
            runtime = {
                "browser_root": str(browser),
                "browser_membership": {
                    "path": str(manifest),
                    "hash": app.bundle.file_hash(manifest),
                },
            }
            app.validate_browser_membership(runtime)
            extra = browser / "new-unlisted-runtime-file"
            extra.write_bytes(b"unlisted")
            with self.assertRaisesRegex(ValueError, "browser runtime membership"):
                app.validate_browser_membership(runtime)
            extra.unlink()
            app.validate_browser_membership(runtime)
            (browser / "escape").symlink_to(root)
            with self.assertRaisesRegex(ValueError, "browser.*symlink"):
                app.browser_membership(browser)

    def test_draft_refuses_before_source_or_browser_access(self):
        app = importlib.import_module("static_contract")
        policy = {
            key: None
            for key in (
                "target",
                "producer",
                "source",
                "bindings",
                "normalizers",
                "constraints",
                "environment",
                "selection",
                "output_root",
                "runtime",
                "evaluator_files",
                "residuals",
            )
        }
        policy.update(
            schema_version=1,
            kind="static_source_contract_app_policy",
            version=app.VERSION,
            approval={"decision": "pending"},
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "policy.json"
            path.write_text(json.dumps(policy))
            with patch.object(app, "source_at", side_effect=AssertionError("source accessed")):
                with self.assertRaisesRegex(ValueError, "approval"):
                    app.validated_policy(path)

    def test_independent_structural_bindings_do_not_require_expected_values(self):
        app = importlib.import_module("static_contract")
        core = {"policy": [{"element": "label"}]}
        bindings = {
            "root": "#report",
            "document_witnesses": ["#toolbar"],
            "elements": {"label": ".label"},
        }
        app._bindings(bindings, core)
        for changed in (
            {**bindings, "elements": {}},
            {**bindings, "expected_text": "not an acquisition guard"},
            {**bindings, "elements": {"label": "text=Expected"}},
            {**bindings, "elements": {"label": ".label >> text=Expected"}},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                app._bindings(changed, core)

    def test_pure_readback_plumbing_never_acquires_or_compares(self):
        import uuid

        app = importlib.import_module("static_contract")
        with tempfile.TemporaryDirectory() as temp:
            run = str(uuid.uuid4())
            root = Path(temp)
            envelope = root / "runs" / run / "evidence.json"
            envelope.parent.mkdir(parents=True)
            envelope.write_text(json.dumps({"run_id": run}))
            policy = {"target": str(root), "output_root": "runs/{run_id}"}
            doc = {"core": {"inventory": ["one"]}}
            preserved = {"summary": {"status": "fail", "required_status": "fail"}}
            with (
                patch.object(app, "validated_policy", return_value=(policy, doc, None)),
                patch.object(app, "driver_seal"),
                patch.object(app, "current_binding", return_value={"immutable": "unit-fixture"}),
                patch.object(app, "_existing", return_value=preserved),
                patch.object(app, "compare", side_effect=AssertionError("rescore")),
                patch.object(app, "acquire", side_effect=AssertionError("recapture")),
            ):
                self.assertIs(app.validate_current(root / "policy.json", envelope), preserved)


if __name__ == "__main__":
    unittest.main()
