"""Bounded card acquisition and immutable delivery controls."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import card_bundle as bundle
import card_evidence as evidence


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "index.html").write_text("<!doctype html><p>candidate</p>")
        (self.source / "candidate.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "entry": "index.html",
                    "dependencies": [],
                    "assets": [],
                }
            )
        )

    def test_sealed_bytes_close_to_source_and_independent_delivery(self):
        sealed = self.root / "build"
        delivery = self.root / "current"
        record = bundle.build(self.source, sealed)
        delivery.mkdir()
        (delivery / "index.html").write_bytes((self.source / "index.html").read_bytes())
        bundle.verify(record, sealed, delivery)
        self.assertEqual(record["outputs"], bundle.inventory(delivery))
        self.assertEqual(record["inputs"], bundle.inventory(self.source))
        self.assertNotEqual(record["input_hash"], record["output_hash"])

    def test_same_head_source_build_and_delivery_edits_do_not_reuse_pass(self):
        for changed in ("source", "output", "delivery"):
            with self.subTest(changed=changed):
                base = self.root / ("control-" + changed)
                base.mkdir(exist_ok=True)
                sealed = base / "build"
                delivery = base / "current"
                record = bundle.build(self.source, sealed)
                delivery.mkdir()
                (delivery / "index.html").write_bytes((self.source / "index.html").read_bytes())
                path = {"source": self.source, "output": sealed / "output", "delivery": delivery}[
                    changed
                ] / "index.html"
                previous = path.read_bytes()
                path.write_bytes(previous + b"\n<!-- new bytes -->")
                with self.assertRaisesRegex(ValueError, "changed|mismatch"):
                    bundle.verify(record, sealed, delivery)
                path.write_bytes(previous)

    def test_inventory_refuses_unlisted_inputs_symlinks_and_external_resources(self):
        (self.source / "unlisted.css").write_text("p {color:red}")
        with self.assertRaisesRegex(ValueError, "input"):
            bundle.build(self.source, self.root / "extra")
        (self.source / "unlisted.css").unlink()
        (self.source / "index.html").unlink()
        (self.source / "index.html").symlink_to(self.source / "candidate.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            bundle.build(self.source, self.root / "link")
        (self.source / "index.html").unlink()
        (self.source / "index.html").write_text(
            '<script src="https://unapproved.invalid/x.js"></script>'
        )
        with self.assertRaisesRegex(ValueError, "resource"):
            bundle.build(self.source, self.root / "external")

    def test_output_directory_is_exclusive_and_manifest_is_not_self_hashed(self):
        sealed = self.root / "build"
        record = bundle.build(self.source, sealed)
        with self.assertRaises(FileExistsError):
            bundle.build(self.source, sealed)
        self.assertEqual([r["path"] for r in record["outputs"]], ["index.html"])
        self.assertEqual(bundle.load(sealed / "build.json"), record)
        with self.assertRaisesRegex(ValueError, "overlap"):
            bundle.build(self.source, self.source / "nested-build")

    def test_atomic_replacement_during_hashing_does_not_claim_old_bytes(self):
        from unittest.mock import patch

        path = self.source / "index.html"
        replacement = self.root / "replacement.html"
        replacement.write_text("<!doctype html><p>changed</p>")
        original = hashlib.sha256
        changed = []

        def replace_once():
            if not changed:
                replacement.replace(path)
                changed.append(True)

        def raced(data=b""):
            value = original(data)
            if data:
                replace_once()

            class Hasher:
                def update(self, chunk):
                    value.update(chunk)
                    replace_once()

                def hexdigest(self):
                    return value.hexdigest()

            return Hasher()

        with patch.object(bundle.hashlib, "sha256", raced):
            with self.assertRaisesRegex(ValueError, "changed|replacement"):
                bundle.file_hash(path)
        self.assertTrue(changed)

    def test_copy_build_cannot_bind_stale_input_manifest_to_new_output_bytes(self):
        from unittest.mock import patch

        before = bundle.source_inventory(self.source)
        (self.source / "index.html").write_text("<!doctype html><p>new bytes</p>")
        with patch.object(bundle, "source_inventory", return_value=before):
            with self.assertRaisesRegex(ValueError, "source|input"):
                bundle.build(self.source, self.root / "raced-build")

    def test_self_consistent_output_manifest_is_not_copy_recipe_proof(self):
        sealed, delivery = self.root / "forged-build", self.root / "forged-delivery"
        record = bundle.build(self.source, sealed)
        (sealed / "output/index.html").write_text("<p>different served bytes</p>")
        record["outputs"] = bundle.inventory(sealed / "output")
        record["output_hash"] = bundle.identity("servo-output-closure-v1", record["outputs"])
        (sealed / "build.json").write_bytes(bundle.canonical(record))
        import shutil

        shutil.copytree(sealed / "output", delivery)
        with self.assertRaisesRegex(ValueError, "copy|input|source"):
            bundle.verify(record, sealed, delivery)


class ComparisonTests(unittest.TestCase):
    def package(self):
        return {
            "view": {"state": "normal"},
            "required_inventory": {"required_ids": ["normal-band-width", "normal-title-text"]},
            "source_facts": [
                {"id": "normal-band-width", "value": "240"},
                {"id": "normal-title-text", "value": "Trailhead"},
            ],
            "policy": {
                "constraints": [
                    {
                        "id": "normal-band-width",
                        "binding_id": "band",
                        "required": True,
                        "comparison": "absolute-inclusive",
                        "normalizer": "dom-bounds-csspx-v0",
                        "units": "CSSpx",
                        "tolerance": "1",
                    },
                    {
                        "id": "normal-title-text",
                        "binding_id": "title",
                        "required": True,
                        "comparison": "exact",
                        "normalizer": "text-content-exact-v0",
                        "units": "text",
                        "tolerance": "0",
                    },
                ]
            },
        }

    def observed(self):
        return {
            "state": "normal",
            "acquisition_error": None,
            "state_error": None,
            "elements": {
                "band": {"count": 1, "visible": True},
                "title": {"count": 1, "visible": True},
            },
            "facts": [
                {"id": "normal-band-width", "value": "240", "raw": "240"},
                {"id": "normal-title-text", "value": "Trailhead", "raw": "Trailhead"},
            ],
        }

    def test_exact_arithmetic_never_rounds_more_than_28_digit_boundary(self):
        for width, expected in (
            ("239", "pass"),
            ("241", "pass"),
            ("238.99", "fail"),
            ("241.01", "fail"),
            ("241.0000000000000000000000000000000000001", "fail"),
        ):
            with self.subTest(width=width):
                observed = self.observed()
                observed["facts"][0]["value"] = width
                result = evidence.compare(self.package(), observed)
                self.assertEqual(result[0]["status"], expected)
                self.assertEqual(result[0]["actual"], width)

    def test_known_absence_and_hidden_title_fail_dependent_constraints(self):
        for title in ({"count": 0, "visible": False}, {"count": 1, "visible": False}):
            observed = self.observed()
            observed["elements"]["title"] = title
            observed["facts"] = observed["facts"][:1]
            result = evidence.compare(self.package(), observed)
            self.assertEqual(result[1]["status"], "fail")
            self.assertIsNone(result[1]["actual"])
            self.assertIn("absent", result[1]["reason"] if title["count"] == 0 else "absent")

    def test_missing_ambiguous_and_unavailable_evidence_stays_unknown(self):
        for mutation in ("missing", "ambiguous", "acquisition"):
            observed = self.observed()
            if mutation == "missing":
                observed["facts"].pop()
            elif mutation == "ambiguous":
                observed["elements"]["title"]["count"] = 2
            else:
                observed["acquisition_error"] = "browser unavailable"
            result = evidence.compare(self.package(), observed)
            self.assertEqual(result[1]["status"], "unknown")

    def test_inventory_duplicates_and_omitted_tolerance_refuse(self):
        for mutation in ("duplicate", "extra", "tolerance"):
            package, observed = self.package(), self.observed()
            if mutation == "duplicate":
                observed["facts"].append(observed["facts"][0])
            elif mutation == "extra":
                observed["facts"].append({"id": "normal-card-width", "value": "240"})
            else:
                del package["policy"]["constraints"][0]["tolerance"]
            with self.assertRaises(ValueError):
                evidence.compare(package, observed)


class AcquisitionOwnershipTests(unittest.TestCase):
    def test_relabelled_old_tree_without_gate_owned_receipt_is_not_current_acquisition(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            root = target / "runs" / "fresh-run" / "design"
            root.mkdir(parents=True)
            policy = {"target": str(target), "approval": {}}
            binding = {"build": {"unit": "build"}, "selection_hash": "unit-selection"}
            envelope = {
                "run_id": "fresh-run",
                "policy": {"hash": evidence.policy_hash(policy), "required_ids": []},
                "build": binding["build"],
                "current_delivery": {"selection_hash": binding["selection_hash"]},
                "artifacts": [],
                "constraints": [],
            }
            with self.assertRaisesRegex(ValueError, "acquisition|ownership|receipt"):
                evidence._verify_existing(envelope, root, policy, binding, "fresh-run")


class DriverSealTests(unittest.TestCase):
    def test_real_quality_wrapper_is_frozen_not_only_its_python_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            oracle = root / "oracle.sh"
            oracle.write_text(
                "# SEED:start design_fidelity\nscore_design_fidelity(){ python real.py; }\n"
                "# SEED:end design_fidelity\n"
            )
            checks = root / "spec/oracle/card/checks.json"
            checks.parent.mkdir(parents=True)
            plan = {
                "approval_status": "approved",
                "approved_required_binding": {
                    "evaluator_artifacts": [],
                },
            }
            checks.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "oracle|seal"):
                evidence.assert_driver_seal(root)
            plan["approved_required_binding"]["evaluator_artifacts"] = [
                {"path": "oracle.sh", "hash": bundle.file_hash(oracle)}
            ]
            checks.write_text(json.dumps(plan))
            evidence.assert_driver_seal(root)
            oracle.write_text(oracle.read_text().replace("python real.py", "echo 1.0"))
            with self.assertRaisesRegex(ValueError, "oracle|seal"):
                evidence.assert_driver_seal(root)

    def test_source_required_ids_cannot_be_optionalized_or_omitted_after_reapproval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "oracle.sh").write_text("approved driver bytes")
            path = root / "spec/oracle/card/checks.json"
            path.parent.mkdir(parents=True)
            plan = {
                "approval_status": "approved",
                "required_policy": {"enabled": True},
                "checks": [{"id": "normal-title-text", "required": False}],
                "approved_required_binding": {
                    "evaluator_artifacts": [
                        {"path": "oracle.sh", "hash": bundle.file_hash(root / "oracle.sh")}
                    ],
                    "required_ids": [],
                },
            }
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "inventory|optional"):
                evidence.assert_driver_seal(root, ["normal-title-text"])
            plan["checks"][0]["required"] = True
            plan["approved_required_binding"]["required_ids"] = ["normal-title-text"]
            path.write_text(json.dumps(plan))
            evidence.assert_driver_seal(root, ["normal-title-text"])
            plan["checks"] = []
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "inventory|omitted"):
                evidence.assert_driver_seal(root, ["normal-title-text"])


class RuntimeContextTests(unittest.TestCase):
    def test_playwright_node_runtime_and_module_overrides_refuse(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyvenv.cfg").write_text("include-system-site-packages = false\n")
            for key in ("PLAYWRIGHT_NODEJS_PATH", "NODE_OPTIONS", "NODE_PATH"):
                with (
                    self.subTest(key=key),
                    patch.object(evidence.site, "ENABLE_USER_SITE", False),
                    patch.dict("os.environ", {key: "/unit-unpinned-runtime"}),
                    self.assertRaisesRegex(ValueError, "Node|node|startup"),
                ):
                    evidence.check_startup_environment(root, [])

    def test_executable_virtualenv_startup_files_are_not_undeclared_inputs(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyvenv.cfg").write_text("include-system-site-packages = false\n")
            packages = root / "packages"
            packages.mkdir()
            with patch.object(evidence.site, "ENABLE_USER_SITE", False):
                evidence.check_startup_environment(root, [str(packages)])
                (packages / "unapproved.pth").write_text("import unapproved\n")
                with self.assertRaisesRegex(ValueError, "startup"):
                    evidence.check_startup_environment(root, [str(packages)])

    def policy(self, root):
        import platform
        import shutil

        manifest = root / "runtime.json"
        bundle.publish(manifest, [])
        policy = {
            "schema_version": 1,
            "kind": "card_evidence_policy",
            "target": str(root),
            "producer": "unit-only",
            "references": "unit-only",
            "selection": "unit-only",
            "output_root": "unit-only",
            "evaluator_files": [],
            "quality": {},
            "runtime": {
                "python": platform.python_version(),
                "executable": str(Path(sys.executable).resolve()),
                "prefix": str(Path(sys.prefix).resolve()),
                "module_origins": {},
                "bash": str(Path(shutil.which("bash")).resolve()),
                "dependencies": {},
                "os": platform.platform(),
                "browser_root": "/unit-browser",
                "manifest": {"path": str(manifest), "hash": bundle.file_hash(manifest)},
            },
        }
        return policy

    def approve_unit_policy(self, path, policy):
        policy["approval"] = {
            "decision": "approved",
            "author": "unit-author",
            "reviewer": "unit-reviewer",
            "policy_hash": evidence.policy_hash(policy),
        }
        path.write_text(json.dumps(policy))

    def test_same_interpreter_bytes_do_not_hide_wrong_virtual_environment(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = self.policy(root)
            policy["runtime"]["prefix"] = "/different-venv"
            path = root / "policy.json"
            self.approve_unit_policy(path, policy)
            with patch.dict("os.environ", {"PLAYWRIGHT_BROWSERS_PATH": "/unit-browser"}):
                with self.assertRaisesRegex(ValueError, "prefix|environment"):
                    evidence.validated_policy(path)

    def test_shadowed_module_origin_is_not_the_declared_dependency_closure(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = self.policy(root)
            policy["runtime"]["module_origins"] = {"json": "/unexpected/json.py"}
            policy["runtime"]["dependencies"] = {"json": "unit-only"}
            path = root / "policy.json"
            self.approve_unit_policy(path, policy)
            with patch.dict("os.environ", {"PLAYWRIGHT_BROWSERS_PATH": "/unit-browser"}):
                with self.assertRaisesRegex(ValueError, "module|origin"):
                    evidence.validated_policy(path)

    def test_native_library_alias_cannot_silently_select_different_bytes(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old, new = root / "old.dylib", root / "new.dylib"
            old.write_bytes(b"unit-old-library")
            new.write_bytes(b"unit-new-library")
            alias = root / "library.dylib"
            alias.symlink_to(new)
            policy = self.policy(root)
            policy["runtime"]["site_roots"] = sorted(
                str(Path(path).resolve()) for path in evidence.site.getsitepackages()
            )
            policy["runtime"]["native_resolutions"] = [
                {"path": str(alias), "resolved": str(old), "hash": bundle.file_hash(old)}
            ]
            path = root / "policy.json"
            self.approve_unit_policy(path, policy)
            with (
                patch.dict("os.environ", {"PLAYWRIGHT_BROWSERS_PATH": "/unit-browser"}),
                patch.object(evidence, "check_startup_environment"),
            ):
                with self.assertRaisesRegex(ValueError, "native dependency resolution"):
                    evidence.validated_policy(path)


if __name__ == "__main__":
    unittest.main()
