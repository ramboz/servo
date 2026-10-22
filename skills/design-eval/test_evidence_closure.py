"""Component-neutral extraction and distribution controls (no source approval claim)."""

import ast
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HELPERS = ("static_contract.py", "static_snapshot.py", "evidence_io.py", "evidence_runtime.py")
PRODUCER = {
    "confirmed_source.py", "capture_confirmed.py", "design_input.py",
    "redline_intake.py", "resolve_redline.py", "validate_redline.py",
}
IO_FUNCTIONS = {
    "require", "canonical", "raw", "identity", "_file_identity", "_regular_file",
    "read_bytes", "file_hash", "load", "publish", "safe", "inventory",
}
RUNTIME_FUNCTIONS = {"_native_dependencies", "check_startup_environment", "_run_id", "_summary"}


class NeutralClosureTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(HERE))
        self.addCleanup(sys.path.remove, str(HERE))

    def test_ac3_exact_primitive_extraction_without_component_implementation(self):
        for name, functions in (
            ("evidence_io.py", IO_FUNCTIONS), ("evidence_runtime.py", RUNTIME_FUNCTIONS),
        ):
            tree = ast.parse((HERE / name).read_text())
            self.assertEqual(
                {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}, functions,
            )
        app = importlib.import_module("static_contract")
        self.assertEqual(tuple(app.HELPERS), HELPERS)
        self.assertEqual(set(app.PRODUCER_PINS), PRODUCER)
        for name in HELPERS:
            text = (HERE / name).read_text()
            self.assertNotIn("card_", text)
        for name in ("required_runtime.py", "gate_consumer.py"):
            self.assertNotIn("card_", (ROOT / "skills/quality-gate" / name).read_text())
        self.assertNotIn("card_", (ROOT / "skills/spec-oracle/checks.py").read_text())

    def test_ac3_strict_io_refuses_duplicate_nonfinite_alias_and_extra_inventory(self):
        io = importlib.import_module("evidence_io")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "data.json"
            for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(ValueError):
                    io.load(path)
            path.write_text('{"x":1}')
            alias = root / "alias"
            alias.symlink_to(path)
            for operation in (io.load, io.read_bytes, io.file_hash):
                with self.subTest(operation=operation), self.assertRaises((ValueError, OSError)):
                    operation(alias)
            with self.assertRaises(ValueError):
                io.inventory(root)
            alias.unlink()
            rows = io.inventory(root)
            self.assertEqual(rows, [{"path": "data.json", "hash": io.raw(path.read_bytes())}])
            (root / "extra").write_text("added")
            self.assertNotEqual(io.inventory(root), rows)
            for name in ("../data.json", "/data.json", "./data.json", "a//b", "a\\b"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    io.safe(root, name)
            with self.assertRaises(FileExistsError):
                io.publish(path, {})

    def test_ac3_io_rejects_atomic_replacement_during_read(self):
        io = importlib.import_module("evidence_io")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input"
            path.write_bytes(b"original")
            with self.assertRaisesRegex(ValueError, "replacement"):
                with io._regular_file(path) as stream:
                    self.assertEqual(stream.read(), b"original")
                    replacement = path.with_name("replacement")
                    replacement.write_bytes(b"original")
                    replacement.replace(path)

    def test_ac3_runtime_summary_and_run_ownership_remain_generic(self):
        runtime = importlib.import_module("evidence_runtime")
        io = importlib.import_module("evidence_io")
        summary = runtime._summary([
            {"id": "indicator-width", "status": "fail"},
            {"id": "label-presence", "status": "unknown"},
        ])
        self.assertEqual(summary["required_status"], "unknown")
        self.assertEqual(summary["failed"], ["indicator-width"])
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            run = "a5dd7fe5-5f61-47b6-a1da-04926a390301"
            invocation = target / ".servo/gate-runs" / run
            invocation.mkdir(parents=True)
            io.publish(invocation / "invocation.json", {
                "schema_version": 1, "kind": "gate_invocation", "run_id": run,
            })
            with patch.dict(os.environ, {
                "SERVO_GATE_RUN_ID": run, "SERVO_GATE_RESULT_DIR": str(invocation),
            }):
                self.assertEqual(runtime._run_id(target), run)
                with patch.dict(os.environ, {"SERVO_GATE_RESULT_DIR": str(target)}):
                    with self.assertRaisesRegex(ValueError, "unbound"):
                        runtime._run_id(target)

    def test_ac4_unsealed_producer_refuses_before_creating_preparation(self):
        app = importlib.import_module("static_contract")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "oracle.sh").write_text("# ordinary scaffold prerequisite\n")
            # This guard control does not stand in for real source integration.
            with (
                patch.dict(app.PRODUCER_PINS, {"design_input.py": None}),
                self.assertRaisesRegex(ValueError, "producer.*sealed"),
            ):
                app.prepare(
                    root, root / "absent", root / "absent", root / "bindings", root / "browser",
                )
            self.assertFalse((root / "tools").exists())
            self.assertFalse((root / "spec").exists())

    def test_prepare_preserves_existing_destinations_before_any_write(self):
        app = importlib.import_module("static_contract")
        for name in ("spec/static.md", "tools/static", "design-input", "spec/oracle/static"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root / "oracle.sh").write_text("# scaffold prerequisite\n")
                occupied = root / name
                occupied.parent.mkdir(parents=True, exist_ok=True)
                if name.endswith(".md"):
                    occupied.write_bytes(b"project-owned specification\x00\n")
                else:
                    occupied.mkdir()
                    (occupied / "owned").write_bytes(b"project-owned content\n")
                before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
                with self.assertRaisesRegex(ValueError, "destination|prepared"):
                    app.prepare(root, root / "absent", root / "absent",
                                root / "bindings", root / "browser")
                self.assertEqual(
                    before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()},
                )

    def test_prepare_invalid_producer_leaves_no_partial_destinations(self):
        app = importlib.import_module("static_contract")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "oracle.sh").write_text("# scaffold prerequisite\n")
            producer = root / "producer-input"
            producer.mkdir()
            for name in app.PRODUCER_PINS:
                (producer / name).write_text("# invalid producer bytes\n")
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with self.assertRaisesRegex(ValueError, "producer changed"):
                app.prepare(root, root / "absent", producer, root / "bindings", root / "browser")
            self.assertEqual(
                before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()},
            )
            self.assertFalse((root / "spec").exists())
            self.assertFalse((root / "tools").exists())

    def test_ac6_host_and_project_copy_import_without_pilot_modules(self):
        roots = [
            HERE,
            ROOT / "hosts/claude/skills/design-eval",
            ROOT / "hosts/codex/plugins/servo/skills/design-eval",
            ROOT / "hosts/copilot/.github/skills/design-eval",
        ]
        for source in roots:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temp:
                self.assertEqual(list(source.rglob("card_*.py")), [])
                target = Path(temp)
                for name in HELPERS:
                    (target / name).write_bytes((source / name).read_bytes())
                code = (
                    "import sys; sys.path.insert(0,sys.argv[1]); "
                    "import static_contract,static_snapshot,evidence_io,evidence_runtime; "
                    "assert not any(n.startswith('card_') for n in sys.modules); "
                    "assert len(static_contract.HELPERS)==4"
                )
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", code, str(target)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual({p.name for p in target.iterdir()}, set(HELPERS))
                # Exercise the public snapshot CLI from the isolated project copy.
                source_root = target / "source"
                source_root.mkdir()
                (source_root / "index.html").write_text("<main>Neutral fixture</main>")
                (source_root / "candidate.json").write_text(json.dumps({
                    "schema_version": 1, "kind": "static_snapshot_candidate",
                    "entry": "/index.html", "metadata": [],
                    "resources": [{"url": "/index.html", "path": "index.html",
                                   "content_type": "text/html"}],
                }))
                result = subprocess.run([
                    sys.executable, "-I", "-B", str(target / "static_snapshot.py"),
                    "build", "--source", str(source_root), "--out", str(target / "build"),
                ], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_ac6_docs_route_to_reusable_flow_not_historical_proof(self):
        readme = (ROOT / "README.md").read_text()
        skill = (HERE / "SKILL.md").read_text()
        example = (HERE / "examples/static-source-contract.md").read_text()
        self.assertIn("static-source-contract.md", readme)
        self.assertIn("static-source-contract.md", skill)
        self.assertIn("adr-0046-component-agnostic-static-evidence.md", example)
        for name in PRODUCER:
            self.assertIn(name, example)
        for text in (readme, skill, example):
            for retired in ("bound-card.md", "card_install.py", "settled-closeout-receipt.md"):
                self.assertNotIn(retired, text)


if __name__ == "__main__":
    unittest.main()
