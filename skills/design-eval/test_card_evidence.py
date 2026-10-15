"""Bounded card acquisition and immutable delivery controls."""

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


if __name__ == "__main__":
    unittest.main()
