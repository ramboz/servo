"""Opt-in real runtime-closure control; never installs into the supplied runtime."""

import os
import platform
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import static_contract as app


@unittest.skipUnless(
    os.environ.get("SERVO_STATIC_RUNTIME_TESTS") == "1",
    "explicit isolated macOS Playwright runtime required",
)
class RuntimeClosureTests(unittest.TestCase):
    def test_exact_runtime_inventory_roundtrip_and_changed_manifest_refusal(self):
        # -I -B is required at process startup; never write any runtime cache.
        self.assertTrue(sys.flags.isolated and sys.dont_write_bytecode)
        sys.pycache_prefix = os.path.join(
            tempfile.gettempdir(), "servo-static-runtime-test-" + str(uuid.uuid4()),
        )
        self.assertFalse(Path(sys.pycache_prefix).exists())
        runtime = app.runtime_inventory(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
        self.assertEqual(set(runtime["module_origins"]), {
            "playwright", "greenlet", "pyee", "typing_extensions",
        })
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files, members = root / "runtime-files.json", root / "browser-membership.json"
            app.bundle.publish(files, runtime.pop("files"))
            app.bundle.publish(members, runtime.pop("browser_members"))
            runtime["manifest"] = {"path": str(files), "hash": app.bundle.file_hash(files)}
            runtime["browser_membership"] = {
                "path": str(members), "hash": app.bundle.file_hash(members),
            }
            app._runtime(runtime)
            platform.invalidate_caches()
            allowed = {
                ("uname", "-p"),
                ("file", "-b", platform._follow_symlinks(sys.executable)),
            }
            commands = []
            run, popen = subprocess.run, subprocess.Popen

            def guard(command, options):
                self.assertFalse(options.get("shell", False))
                self.assertIn(tuple(command), allowed)
                commands.append(tuple(command))

            def metadata_run(command, *args, **kwargs):
                guard(command, kwargs)
                return run(command, *args, **kwargs)

            def metadata_popen(command, *args, **kwargs):
                guard(command, kwargs)
                return popen(command, *args, **kwargs)

            with (
                patch("subprocess.run", side_effect=metadata_run),
                patch("subprocess.Popen", side_effect=metadata_popen),
            ):
                app._runtime(runtime)
                with self.assertRaises(AssertionError):
                    metadata_run(["uname", "-a"])
            self.assertEqual(set(commands), allowed)
            files.write_text("[]\n")
            with self.assertRaisesRegex(ValueError, "runtime manifest changed"):
                app._runtime(runtime)
        self.assertFalse(Path(sys.pycache_prefix).exists())


if __name__ == "__main__":
    unittest.main()
