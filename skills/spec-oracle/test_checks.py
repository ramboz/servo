"""
AC verification tests for slice 006-02 (check-library) of `/servo:spec-oracle`.

Run from the repo root:
    python3 -m unittest skills.spec-oracle.test_checks
or via pytest:
    uvx pytest skills/spec-oracle/test_checks.py -q

`checks.py` is the deterministic, stdlib-only check *engine*: it reads a
`checks.json` plan (the artifact slice 006-01 produces, elaborated with
per-family executable fields) and runs each check through a family primitive,
emitting one JSONL evidence record per AC plus a composite summary score.

Test idiom mirrors `skills/spec-oracle/test_oracle_plan.py`:
  - `unittest.TestCase` classes (collected by pytest),
  - `REPO_ROOT = Path(__file__).resolve().parents[2]`,
  - fixtures written into a `tempfile.TemporaryDirectory()`,
  - the engine imported by path (the dir name `spec-oracle` is not a valid
    Python identifier) for fast unit assertions, and driven as a subprocess
    for the end-to-end CLI path.

No check primitive requires the network (006-02 DoR); the engine is stdlib
only (AC5).
"""

import hashlib
import importlib.util
import io
import json
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKS_PY = REPO_ROOT / "skills" / "spec-oracle" / "checks.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("checks", CHECKS_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ck = _load_module()


# The eight deterministic families plus residual_judgment (slice 006-02 AC1).
DETERMINISTIC_FAMILIES = (
    "command",
    "file_presence",
    "text_invariant",
    "json_contract",
    "archive_inventory",
    "markdown_links",
    "generated_artifact_command",
    "runtime_reference_scan",
)

VALID_STATUSES = {"pass", "fail", "env_error", "not_applicable"}


def _py(code: str) -> list:
    """A portable argv that runs `code` under the current interpreter."""
    return [sys.executable, "-c", code]


class _TmpBase(unittest.TestCase):
    """Mixin giving each test a fresh base_dir under a TemporaryDirectory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel: str, content: str) -> Path:
        p = self.base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def run_check(self, check: dict) -> dict:
        return ck.run_check(check, self.base)


# ===========================================================================
# AC1 — Primitive coverage (a handler for each of the eight families)
# ===========================================================================


class PrimitiveCoverageTests(unittest.TestCase):
    """AC1 — checks.py supports all eight deterministic families."""

    def test_all_families_dispatchable(self):
        for family in DETERMINISTIC_FAMILIES:
            self.assertIn(
                family, ck.DISPATCH,
                f"no primitive handler registered for family {family!r}",
            )

    def test_residual_judgment_is_not_applicable(self):
        ev = ck.run_check(
            {"id": "AC-X", "family": "residual_judgment",
             "reason": "tone", "suggested_review": "human"},
            Path("."),
        )
        self.assertEqual(ev["status"], "not_applicable")

    def test_unknown_family_is_env_error(self):
        ev = ck.run_check({"id": "AC-X", "family": "no_such_family"}, Path("."))
        self.assertEqual(ev["status"], "env_error")
        self.assertIn("family", ev["message"].lower())


# ===========================================================================
# AC2 — Structured output (one evidence record per AC with the named fields)
# ===========================================================================


class EvidenceStructureTests(_TmpBase):
    """AC2 — every evidence record carries the required fields."""

    REQUIRED = ("schema_version", "check_id", "ac_id", "status", "message")

    def test_required_fields_present(self):
        self.write("foo.txt", "x")
        ev = self.run_check(
            {"id": "AC-1", "family": "file_presence", "path": "foo.txt"})
        for key in self.REQUIRED:
            self.assertIn(key, ev, f"evidence missing {key!r}")

    def test_schema_version_is_one(self):
        self.write("foo.txt", "x")
        ev = self.run_check(
            {"id": "AC-1", "family": "file_presence", "path": "foo.txt"})
        self.assertEqual(ev["schema_version"], 1)

    def test_status_is_in_closed_set(self):
        self.write("foo.txt", "x")
        ev = self.run_check(
            {"id": "AC-1", "family": "file_presence", "path": "foo.txt"})
        self.assertIn(ev["status"], VALID_STATUSES)

    def test_message_is_nonempty_string(self):
        ev = self.run_check(
            {"id": "AC-1", "family": "file_presence", "path": "gone.txt"})
        self.assertIsInstance(ev["message"], str)
        self.assertTrue(ev["message"])

    def test_check_id_echoed(self):
        self.write("foo.txt", "x")
        ev = self.run_check(
            {"id": "AC-42", "family": "file_presence", "path": "foo.txt"})
        self.assertEqual(ev["check_id"], "AC-42")

    def test_ac_id_defaults_to_check_id(self):
        # When a check carries no explicit ac_id, it falls back to its own id
        # (006-01 plans set id == AC id).
        self.write("foo.txt", "x")
        ev = self.run_check(
            {"id": "AC-7", "family": "file_presence", "path": "foo.txt"})
        self.assertEqual(ev["ac_id"], "AC-7")

    def test_ac_id_explicit_when_provided(self):
        self.write("foo.txt", "x")
        ev = self.run_check(
            {"id": "CHK-7", "ac_id": "AC-9", "family": "file_presence",
             "path": "foo.txt"})
        self.assertEqual(ev["ac_id"], "AC-9")
        self.assertEqual(ev["check_id"], "CHK-7")


# ===========================================================================
# AC1/AC4 — command primitive
# ===========================================================================


class CommandPrimitiveTests(_TmpBase):
    def test_pass_on_expected_exit(self):
        ev = self.run_check(
            {"id": "C", "family": "command", "command": _py("import sys; sys.exit(0)")})
        self.assertEqual(ev["status"], "pass")

    def test_fail_on_wrong_exit(self):
        ev = self.run_check(
            {"id": "C", "family": "command", "command": _py("import sys; sys.exit(3)")})
        self.assertEqual(ev["status"], "fail")
        # Diagnostics name the observed exit code (AC4).
        self.assertIn("3", ev["message"])

    def test_expected_nonzero_exit_passes(self):
        ev = self.run_check(
            {"id": "C", "family": "command",
             "command": _py("import sys; sys.exit(2)"),
             "expected": {"exit_code": 2}})
        self.assertEqual(ev["status"], "pass")

    def test_expected_bare_int_convenience(self):
        # `expected: N` is accepted as shorthand for `{"exit_code": N}`, and a
        # malformed `expected` never raises (defaults to 0).
        ev = self.run_check(
            {"id": "C", "family": "command",
             "command": _py("import sys; sys.exit(2)"), "expected": 2})
        self.assertEqual(ev["status"], "pass")

    def test_string_command_is_split_without_shell(self):
        # A string command is shlex-split (no shell), so this is argv, not a
        # shell pipeline.
        ev = self.run_check(
            {"id": "C", "family": "command",
             "command": f'"{sys.executable}" -c "import sys; sys.exit(0)"'})
        self.assertEqual(ev["status"], "pass")

    def test_missing_binary_is_env_error(self):
        ev = self.run_check(
            {"id": "C", "family": "command",
             "command": ["this-binary-does-not-exist-12345"]})
        self.assertEqual(ev["status"], "env_error")

    def test_missing_command_field_is_env_error(self):
        ev = self.run_check({"id": "C", "family": "command"})
        self.assertEqual(ev["status"], "env_error")

    def test_timeout_is_env_error(self):
        ev = self.run_check(
            {"id": "C", "family": "command",
             "command": _py("import time; time.sleep(30)"),
             "timeout": 1})
        self.assertEqual(ev["status"], "env_error")
        self.assertIn("timeout", ev["message"].lower())

    def test_working_directory_resolved_under_base(self):
        (self.base / "sub").mkdir()
        ev = self.run_check(
            {"id": "C", "family": "command", "working_directory": "sub",
             "command": _py(
                 "import os,sys; sys.exit(0 if os.path.basename(os.getcwd())=='sub' else 1)")})
        self.assertEqual(ev["status"], "pass")


# ===========================================================================
# AC1/AC4 — file_presence primitive
# ===========================================================================


class FilePresenceTests(_TmpBase):
    def test_present_pass(self):
        self.write("a.txt", "hi")
        ev = self.run_check({"id": "F", "family": "file_presence", "path": "a.txt"})
        self.assertEqual(ev["status"], "pass")

    def test_missing_when_expected_fail_names_path(self):
        ev = self.run_check(
            {"id": "F", "family": "file_presence", "path": "nope.txt"})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("nope.txt", ev["message"])

    def test_absent_expected_pass(self):
        ev = self.run_check(
            {"id": "F", "family": "file_presence", "path": "ghost.txt",
             "exists": False})
        self.assertEqual(ev["status"], "pass")

    def test_present_when_expected_absent_fail(self):
        self.write("here.txt", "x")
        ev = self.run_check(
            {"id": "F", "family": "file_presence", "path": "here.txt",
             "exists": False})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("here.txt", ev["message"])

    def test_executable_bit_required_pass(self):
        p = self.write("run.sh", "#!/bin/sh\n")
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
        ev = self.run_check(
            {"id": "F", "family": "file_presence", "path": "run.sh",
             "executable": True})
        self.assertEqual(ev["status"], "pass")

    def test_executable_bit_required_fail(self):
        self.write("plain.txt", "data")
        ev = self.run_check(
            {"id": "F", "family": "file_presence", "path": "plain.txt",
             "executable": True})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("executable", ev["message"].lower())


# ===========================================================================
# AC1/AC4 — text_invariant primitive
# ===========================================================================


class TextInvariantTests(_TmpBase):
    def test_contains_pass(self):
        self.write("README.md", "powered by servo\n")
        ev = self.run_check(
            {"id": "T", "family": "text_invariant", "path": "README.md",
             "contains": "servo"})
        self.assertEqual(ev["status"], "pass")

    def test_contains_fail_names_needle_and_path(self):
        self.write("README.md", "nothing here\n")
        ev = self.run_check(
            {"id": "T", "family": "text_invariant", "path": "README.md",
             "contains": "servo"})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("servo", ev["message"])
        self.assertIn("README.md", ev["message"])

    def test_not_contains_pass(self):
        self.write("clean.txt", "all good\n")
        ev = self.run_check(
            {"id": "T", "family": "text_invariant", "path": "clean.txt",
             "not_contains": "FIXME"})
        self.assertEqual(ev["status"], "pass")

    def test_not_contains_fail(self):
        self.write("dirty.txt", "TODO: FIXME later\n")
        ev = self.run_check(
            {"id": "T", "family": "text_invariant", "path": "dirty.txt",
             "not_contains": "FIXME"})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("FIXME", ev["message"])

    def test_regex_pass(self):
        self.write("v.txt", "version = 0.1.0\n")
        ev = self.run_check(
            {"id": "T", "family": "text_invariant", "path": "v.txt",
             "regex": r"version\s*=\s*\d+\.\d+\.\d+"})
        self.assertEqual(ev["status"], "pass")

    def test_regex_fail(self):
        self.write("v.txt", "no version here\n")
        ev = self.run_check(
            {"id": "T", "family": "text_invariant", "path": "v.txt",
             "regex": r"version\s*=\s*\d+\.\d+\.\d+"})
        self.assertEqual(ev["status"], "fail")

    def test_bad_regex_is_env_error(self):
        self.write("v.txt", "x")
        ev = self.run_check(
            {"id": "T", "family": "text_invariant", "path": "v.txt",
             "regex": r"([unterminated"})
        self.assertEqual(ev["status"], "env_error")

    def test_missing_file_is_env_error(self):
        ev = self.run_check(
            {"id": "T", "family": "text_invariant", "path": "gone.txt",
             "contains": "x"})
        self.assertEqual(ev["status"], "env_error")

    def test_no_assertion_field_is_env_error(self):
        self.write("a.txt", "x")
        ev = self.run_check(
            {"id": "T", "family": "text_invariant", "path": "a.txt"})
        self.assertEqual(ev["status"], "env_error")


# ===========================================================================
# AC1/AC4 — json_contract primitive
# ===========================================================================


class JsonContractTests(_TmpBase):
    def test_required_key_pass(self):
        self.write("install.json", json.dumps({"servo_version": "0.1.0"}))
        ev = self.run_check(
            {"id": "J", "family": "json_contract", "path": "install.json",
             "required_keys": ["servo_version"]})
        self.assertEqual(ev["status"], "pass")

    def test_missing_key_fail_names_key(self):
        self.write("install.json", json.dumps({"other": 1}))
        ev = self.run_check(
            {"id": "J", "family": "json_contract", "path": "install.json",
             "required_keys": ["servo_version"]})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("servo_version", ev["message"])

    def test_nested_dotted_key_pass(self):
        self.write("c.json", json.dumps({"a": {"b": {"c": 1}}}))
        ev = self.run_check(
            {"id": "J", "family": "json_contract", "path": "c.json",
             "required_keys": ["a.b.c"]})
        self.assertEqual(ev["status"], "pass")

    def test_equals_pass(self):
        self.write("c.json", json.dumps({"schema_version": 1}))
        ev = self.run_check(
            {"id": "J", "family": "json_contract", "path": "c.json",
             "equals": {"schema_version": 1}})
        self.assertEqual(ev["status"], "pass")

    def test_equals_mismatch_fail(self):
        self.write("c.json", json.dumps({"schema_version": 2}))
        ev = self.run_check(
            {"id": "J", "family": "json_contract", "path": "c.json",
             "equals": {"schema_version": 1}})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("schema_version", ev["message"])

    def test_invalid_json_is_fail(self):
        # "is valid JSON" is itself an assertable contract: an existing but
        # unparseable file fails the contract rather than env-erroring.
        self.write("bad.json", "{not json,,,}")
        ev = self.run_check(
            {"id": "J", "family": "json_contract", "path": "bad.json",
             "required_keys": ["x"]})
        self.assertEqual(ev["status"], "fail")

    def test_missing_file_is_env_error(self):
        ev = self.run_check(
            {"id": "J", "family": "json_contract", "path": "gone.json",
             "required_keys": ["x"]})
        self.assertEqual(ev["status"], "env_error")


# ===========================================================================
# AC1/AC4 — archive_inventory primitive
# ===========================================================================


class ArchiveInventoryTests(_TmpBase):
    def _make_zip(self, rel: str, names) -> Path:
        p = self.base / rel
        with zipfile.ZipFile(p, "w") as zf:
            for n in names:
                zf.writestr(n, "x")
        return p

    def _make_tar(self, rel: str, names) -> Path:
        p = self.base / rel
        with tarfile.open(p, "w:gz") as tf:
            for n in names:
                data = b"x"
                info = tarfile.TarInfo(name=n)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
        return p

    def test_zip_contains_pass(self):
        self._make_zip("rel.zip", ["a/b.txt", "c.txt"])
        ev = self.run_check(
            {"id": "A", "family": "archive_inventory", "path": "rel.zip",
             "contains": ["a/b.txt"]})
        self.assertEqual(ev["status"], "pass")

    def test_zip_missing_entry_fail_names_entry(self):
        self._make_zip("rel.zip", ["c.txt"])
        ev = self.run_check(
            {"id": "A", "family": "archive_inventory", "path": "rel.zip",
             "contains": ["a/b.txt"]})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("a/b.txt", ev["message"])

    def test_zip_forbidden_entry_fail(self):
        self._make_zip("rel.zip", ["c.txt", "secret.key"])
        ev = self.run_check(
            {"id": "A", "family": "archive_inventory", "path": "rel.zip",
             "excludes": ["secret.key"]})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("secret.key", ev["message"])

    def test_tar_contains_pass(self):
        self._make_tar("rel.tar.gz", ["x/y.txt"])
        ev = self.run_check(
            {"id": "A", "family": "archive_inventory", "path": "rel.tar.gz",
             "contains": ["x/y.txt"]})
        self.assertEqual(ev["status"], "pass")

    def test_missing_archive_is_env_error(self):
        ev = self.run_check(
            {"id": "A", "family": "archive_inventory", "path": "gone.zip",
             "contains": ["a"]})
        self.assertEqual(ev["status"], "env_error")

    def test_not_an_archive_is_env_error(self):
        self.write("plain.txt", "not an archive")
        ev = self.run_check(
            {"id": "A", "family": "archive_inventory", "path": "plain.txt",
             "contains": ["a"]})
        self.assertEqual(ev["status"], "env_error")


# ===========================================================================
# AC1/AC4 — markdown_links primitive
# ===========================================================================


class MarkdownLinksTests(_TmpBase):
    def test_local_links_resolve_pass(self):
        self.write("docs/target.md", "# target\n")
        self.write("docs/index.md", "See [target](target.md).\n")
        ev = self.run_check(
            {"id": "M", "family": "markdown_links", "path": "docs/index.md"})
        self.assertEqual(ev["status"], "pass")

    def test_broken_link_fail_names_target(self):
        self.write("docs/index.md", "See [gone](missing.md).\n")
        ev = self.run_check(
            {"id": "M", "family": "markdown_links", "path": "docs/index.md"})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("missing.md", ev["message"])

    def test_external_links_skipped(self):
        self.write("docs/index.md",
                   "[ext](https://example.com) and [mail](mailto:a@b.c)\n")
        ev = self.run_check(
            {"id": "M", "family": "markdown_links", "path": "docs/index.md"})
        self.assertEqual(ev["status"], "pass")

    def test_anchor_fragment_stripped(self):
        self.write("docs/target.md", "# H\n")
        self.write("docs/index.md", "[sec](target.md#heading)\n")
        ev = self.run_check(
            {"id": "M", "family": "markdown_links", "path": "docs/index.md"})
        self.assertEqual(ev["status"], "pass")

    def test_missing_markdown_file_is_env_error(self):
        ev = self.run_check(
            {"id": "M", "family": "markdown_links", "path": "docs/gone.md"})
        self.assertEqual(ev["status"], "env_error")

    def test_root_mode_pass(self):
        # `root` walks every *.md under a directory.
        self.write("docs/a.md", "# a\n")
        self.write("docs/b.md", "see [a](a.md)\n")
        ev = self.run_check(
            {"id": "M", "family": "markdown_links", "root": "docs"})
        self.assertEqual(ev["status"], "pass")

    def test_root_mode_broken_fail(self):
        self.write("docs/a.md", "# a\n")
        self.write("docs/b.md", "see [gone](missing.md)\n")
        ev = self.run_check(
            {"id": "M", "family": "markdown_links", "root": "docs"})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("missing.md", ev["message"])

    def test_missing_root_is_env_error(self):
        ev = self.run_check(
            {"id": "M", "family": "markdown_links", "root": "no-such-dir"})
        self.assertEqual(ev["status"], "env_error")


# ===========================================================================
# AC1/AC4 — generated_artifact_command primitive
# ===========================================================================


class GeneratedArtifactCommandTests(_TmpBase):
    def test_copy_source_then_run_pass(self):
        # A source tree is copied into a fresh tempdir, then a command runs
        # rooted in that generated tree.
        self.write("src/marker.txt", "ok")
        ev = self.run_check(
            {"id": "G", "family": "generated_artifact_command",
             "source": "src",
             "command": _py(
                 "import os,sys; sys.exit(0 if os.path.exists('marker.txt') else 1)")})
        self.assertEqual(ev["status"], "pass")

    def test_command_failure_is_fail(self):
        self.write("src/marker.txt", "ok")
        ev = self.run_check(
            {"id": "G", "family": "generated_artifact_command",
             "source": "src",
             "command": _py("import sys; sys.exit(1)")})
        self.assertEqual(ev["status"], "fail")
        # Diagnostics name the offending command (AC4).
        self.assertIn(sys.executable, ev["message"])

    def test_working_subdir_pass(self):
        # The command runs rooted at <tmp>/<working_subdir>.
        self.write("src/sub/marker.txt", "ok")
        ev = self.run_check(
            {"id": "G", "family": "generated_artifact_command",
             "source": "src", "working_subdir": "sub",
             "command": _py(
                 "import os,sys; sys.exit(0 if os.path.exists('marker.txt') else 1)")})
        self.assertEqual(ev["status"], "pass")

    def test_missing_working_subdir_is_env_error(self):
        self.write("src/marker.txt", "ok")
        ev = self.run_check(
            {"id": "G", "family": "generated_artifact_command",
             "source": "src", "working_subdir": "nope",
             "command": _py("import sys; sys.exit(0)")})
        self.assertEqual(ev["status"], "env_error")

    def test_build_command_runs_before_command(self):
        ev = self.run_check(
            {"id": "G", "family": "generated_artifact_command",
             "build_command": _py("open('built.txt','w').write('x')"),
             "command": _py(
                 "import os,sys; sys.exit(0 if os.path.exists('built.txt') else 1)")})
        self.assertEqual(ev["status"], "pass")

    def test_build_command_failure_is_env_error(self):
        # A failing build step means the artifact could not be produced — that
        # is an environment failure, distinct from "built but the assertion
        # command failed" (which is a plain fail).
        ev = self.run_check(
            {"id": "G", "family": "generated_artifact_command",
             "build_command": _py("import sys; sys.exit(1)"),
             "command": _py("import sys; sys.exit(0)")})
        self.assertEqual(ev["status"], "env_error")

    def test_missing_command_is_env_error(self):
        ev = self.run_check(
            {"id": "G", "family": "generated_artifact_command", "source": "src"})
        self.assertEqual(ev["status"], "env_error")

    def test_does_not_mutate_source(self):
        # The command runs in a throwaway tempdir, never the real source.
        marker = self.write("src/marker.txt", "original")
        self.run_check(
            {"id": "G", "family": "generated_artifact_command",
             "source": "src",
             "command": _py("open('marker.txt','w').write('mutated')")})
        self.assertEqual(marker.read_text(), "original")


# ===========================================================================
# AC1/AC4 — runtime_reference_scan primitive
# ===========================================================================


class RuntimeReferenceScanTests(_TmpBase):
    def test_no_references_pass(self):
        self.write("src/a.py", "import os\n")
        ev = self.run_check(
            {"id": "R", "family": "runtime_reference_scan",
             "needle": "dead_module", "roots": ["src"]})
        self.assertEqual(ev["status"], "pass")

    def test_reference_present_fail_names_location(self):
        self.write("src/a.py", "x = 1\nimport dead_module\n")
        ev = self.run_check(
            {"id": "R", "family": "runtime_reference_scan",
             "needle": "dead_module", "roots": ["src"]})
        self.assertEqual(ev["status"], "fail")
        self.assertIn("a.py", ev["message"])
        self.assertIn("2", ev["message"])  # line number of the hit

    def test_excluded_path_not_scanned(self):
        # Historical docs are excluded, so a reference there does not fail.
        self.write("docs/history.md", "we removed dead_module\n")
        ev = self.run_check(
            {"id": "R", "family": "runtime_reference_scan",
             "needle": "dead_module", "roots": ["docs"],
             "exclude": ["docs/history.md"]})
        self.assertEqual(ev["status"], "pass")

    def test_regex_needle(self):
        self.write("src/a.py", "call_old_api()\n")
        ev = self.run_check(
            {"id": "R", "family": "runtime_reference_scan",
             "regex": r"old_\w+", "roots": ["src"]})
        self.assertEqual(ev["status"], "fail")

    def test_missing_root_is_env_error(self):
        ev = self.run_check(
            {"id": "R", "family": "runtime_reference_scan",
             "needle": "x", "roots": ["does-not-exist"]})
        self.assertEqual(ev["status"], "env_error")

    def test_no_pattern_is_env_error(self):
        self.write("src/a.py", "x\n")
        ev = self.run_check(
            {"id": "R", "family": "runtime_reference_scan", "roots": ["src"]})
        self.assertEqual(ev["status"], "env_error")


# ===========================================================================
# AC3 — Composite score + summary counts
# ===========================================================================


class CompositeScoreTests(unittest.TestCase):
    """AC3 — the summary reports counts and a score in [0.0, 1.0]."""

    def _summary(self, statuses):
        evidence = [{"status": s} for s in statuses]
        return ck.score_summary(evidence)

    def test_summary_has_required_fields(self):
        s = self._summary(["pass", "fail"])
        for key in ("passed_checks", "failed_checks", "env_errors",
                    "not_applicable", "score"):
            self.assertIn(key, s)

    def test_counts(self):
        s = self._summary(["pass", "pass", "fail", "env_error",
                           "not_applicable"])
        self.assertEqual(s["passed_checks"], 2)
        self.assertEqual(s["failed_checks"], 1)
        self.assertEqual(s["env_errors"], 1)
        self.assertEqual(s["not_applicable"], 1)

    def test_all_pass_score_is_one(self):
        self.assertEqual(self._summary(["pass", "pass"])["score"], 1.0)

    def test_half_pass_score(self):
        self.assertEqual(self._summary(["pass", "fail"])["score"], 0.5)

    def test_all_fail_score_is_zero(self):
        self.assertEqual(self._summary(["fail", "fail"])["score"], 0.0)

    def test_env_errors_excluded_from_denominator(self):
        # 1 pass, 1 fail, 2 env_error -> score over pass/fail only = 0.5.
        self.assertEqual(
            self._summary(["pass", "fail", "env_error", "env_error"])["score"],
            0.5)

    def test_not_applicable_excluded_from_denominator(self):
        # 1 pass, 3 N/A -> score = 1.0 (judgment ACs do not dilute the score).
        self.assertEqual(
            self._summary(["pass", "not_applicable", "not_applicable",
                           "not_applicable"])["score"],
            1.0)

    def test_only_not_applicable_score_is_one(self):
        # Nothing to prove deterministically and nothing failed.
        self.assertEqual(self._summary(["not_applicable"])["score"], 1.0)

    def test_only_env_errors_score_is_zero(self):
        # Nothing could be established and checks errored.
        self.assertEqual(self._summary(["env_error", "env_error"])["score"], 0.0)

    def test_score_within_unit_interval(self):
        for combo in (["pass"], ["fail"], ["pass", "fail", "fail"],
                      ["env_error"], ["not_applicable"], []):
            score = self._summary(combo)["score"]
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)


# ===========================================================================
# AC2/AC3 — run_checks over a whole plan
# ===========================================================================


class RunPlanTests(_TmpBase):
    def _plan(self, checks, residual=None):
        return {
            "schema_version": 1,
            "spec_id": "099-demo",
            "checks": checks,
            "residual_judgment": residual or [],
        }

    def test_one_evidence_record_per_ac(self):
        self.write("a.txt", "x")
        plan = self._plan(
            checks=[{"id": "AC-1", "family": "file_presence", "path": "a.txt"}],
            residual=[{"id": "AC-2", "reason": "tone",
                       "suggested_review": "human"}],
        )
        result = ck.run_checks(plan, self.base)
        ids = {e["check_id"] for e in result["evidence"]}
        self.assertEqual(ids, {"AC-1", "AC-2"})

    def test_residual_emitted_as_not_applicable(self):
        plan = self._plan(
            checks=[],
            residual=[{"id": "AC-2", "reason": "tone",
                       "suggested_review": "human"}],
        )
        result = ck.run_checks(plan, self.base)
        ev = result["evidence"][0]
        self.assertEqual(ev["status"], "not_applicable")

    def test_summary_present_and_scored(self):
        self.write("a.txt", "x")
        plan = self._plan(
            checks=[{"id": "AC-1", "family": "file_presence", "path": "a.txt"}])
        result = ck.run_checks(plan, self.base)
        self.assertIn("summary", result)
        self.assertEqual(result["summary"]["score"], 1.0)

    def test_unelaborated_planned_check_is_env_error(self):
        # A 006-01 plan entry carries family but no executable fields; the
        # runner must not silently pass it.
        plan = self._plan(
            checks=[{"id": "AC-1", "family": "file_presence",
                     "status": "planned"}])
        result = ck.run_checks(plan, self.base)
        self.assertEqual(result["evidence"][0]["status"], "env_error")


# ===========================================================================
# AC2/AC3 — CLI end-to-end (JSONL evidence + summary + exit code)
# ===========================================================================


class CliTests(_TmpBase):
    def _write_plan(self, plan: dict) -> Path:
        out = self.base / ".servo" / "spec-oracles" / "099-demo"
        out.mkdir(parents=True, exist_ok=True)
        p = out / "checks.json"
        p.write_text(json.dumps(plan))
        return p

    def _run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CHECKS_PY), *[str(a) for a in args]],
            capture_output=True, text=True)

    def test_jsonl_evidence_and_summary_on_stdout(self):
        (self.base / "a.txt").write_text("x")
        plan_path = self._write_plan({
            "schema_version": 1, "spec_id": "099-demo",
            "checks": [{"id": "AC-1", "family": "file_presence", "path": "a.txt"}],
            "residual_judgment": [],
        })
        res = self._run(plan_path, "--base-dir", self.base)
        self.assertEqual(res.returncode, 0, res.stderr)
        lines = [json.loads(ln) for ln in res.stdout.splitlines() if ln.strip()]
        # Required AC2 fields on every evidence record.
        evidence = [ln for ln in lines if ln.get("kind") == "evidence"]
        summaries = [ln for ln in lines if ln.get("kind") == "summary"]
        self.assertEqual(len(evidence), 1)
        for key in ("schema_version", "check_id", "ac_id", "status", "message"):
            self.assertIn(key, evidence[0])
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["score"], 1.0)

    def test_exit_code_one_on_failure(self):
        plan_path = self._write_plan({
            "schema_version": 1, "spec_id": "099-demo",
            "checks": [{"id": "AC-1", "family": "file_presence",
                        "path": "absent.txt"}],
            "residual_judgment": [],
        })
        res = self._run(plan_path, "--base-dir", self.base)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)

    def test_exit_code_two_on_env_error(self):
        plan_path = self._write_plan({
            "schema_version": 1, "spec_id": "099-demo",
            "checks": [{"id": "AC-1", "family": "command"}],  # missing command
            "residual_judgment": [],
        })
        res = self._run(plan_path, "--base-dir", self.base)
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)

    def test_ledger_receives_evidence_when_requested(self):
        (self.base / "a.txt").write_text("x")
        plan_path = self._write_plan({
            "schema_version": 1, "spec_id": "099-demo",
            "checks": [{"id": "AC-1", "family": "file_presence", "path": "a.txt"}],
            "residual_judgment": [],
        })
        ledger = self.base / "ledger.jsonl"
        res = self._run(plan_path, "--base-dir", self.base, "--ledger", ledger)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(ledger.exists())
        rows = [json.loads(ln) for ln in ledger.read_text().splitlines() if ln.strip()]
        self.assertTrue(any(r.get("check_id") == "AC-1" for r in rows))

    def test_missing_checks_json_is_env_error_exit(self):
        res = self._run(self.base / "nope.json", "--base-dir", self.base)
        self.assertEqual(res.returncode, 2)

    def test_base_dir_derived_from_servo_layout(self):
        # Without --base-dir, the engine derives the target root from the
        # canonical .servo/spec-oracles/<id>/checks.json location.
        (self.base / "a.txt").write_text("x")
        plan_path = self._write_plan({
            "schema_version": 1, "spec_id": "099-demo",
            "checks": [{"id": "AC-1", "family": "file_presence", "path": "a.txt"}],
            "residual_judgment": [],
        })
        res = self._run(plan_path)
        self.assertEqual(res.returncode, 0, res.stderr)


# ===========================================================================
# AC5 — Dependency-free (stdlib only)
# ===========================================================================


class DependencyFreeTests(unittest.TestCase):
    """AC5 — the generated runner uses only the Python standard library."""

    def test_only_stdlib_imports(self):
        if not hasattr(sys, "stdlib_module_names"):
            self.skipTest("needs Python 3.10+ for sys.stdlib_module_names")
        stdlib = set(sys.stdlib_module_names)
        source = CHECKS_PY.read_text()
        offenders = []
        for line in source.splitlines():
            m = re.match(r"\s*import\s+([\w.]+)", line)
            if not m:
                m = re.match(r"\s*from\s+([\w.]+)\s+import\s", line)
            if not m:
                continue
            top = m.group(1).split(".")[0]
            if top == "checks":
                continue
            if top not in stdlib:
                offenders.append(top)
        self.assertEqual(offenders, [], f"non-stdlib imports: {offenders}")


# ===========================================================================
# --score-only mode (slice 006-03 — oracle component contract)
# ===========================================================================


class ScoreOnlyModeTests(_TmpBase):
    """The generated oracle component invokes `checks.py --score-only`, which
    must print just the composite score and obey the score_<name> contract:
    exit 0 (score on stdout) on pass/fail, exit 2 only on env error — never 1
    (a rc=1 from a component makes oracle.sh env-error)."""

    def _write_plan(self, checks) -> Path:
        out = self.base / ".servo" / "spec-oracles" / "demo"
        out.mkdir(parents=True, exist_ok=True)
        p = out / "checks.json"
        p.write_text(json.dumps(
            {"schema_version": 1, "spec_id": "demo", "checks": checks,
             "residual_judgment": []}))
        return p

    def _run(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CHECKS_PY), *[str(a) for a in args]],
            capture_output=True, text=True)

    def test_all_pass_prints_score_exits_zero(self):
        (self.base / "a.txt").write_text("x")
        plan = self._write_plan(
            [{"id": "AC-1", "family": "file_presence", "path": "a.txt"}])
        res = self._run(plan, "--base-dir", self.base, "--score-only")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "1.0")

    def test_failure_prints_score_and_exits_zero_not_one(self):
        # A failing check yields score 0.0 but still exit 0 — the THRESHOLD
        # gate in oracle.sh decides pass/fail, NOT the component.
        plan = self._write_plan(
            [{"id": "AC-1", "family": "file_presence", "path": "gone.txt"}])
        res = self._run(plan, "--base-dir", self.base, "--score-only")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "0.0")

    def test_mixed_prints_fractional_score(self):
        (self.base / "a.txt").write_text("x")
        plan = self._write_plan([
            {"id": "AC-1", "family": "file_presence", "path": "a.txt"},
            {"id": "AC-2", "family": "file_presence", "path": "gone.txt"},
        ])
        res = self._run(plan, "--base-dir", self.base, "--score-only")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "0.5")

    def test_env_error_exits_two(self):
        plan = self._write_plan(
            [{"id": "AC-1", "family": "command"}])  # missing command field
        res = self._run(plan, "--base-dir", self.base, "--score-only")
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)

    def test_score_only_suppresses_jsonl(self):
        (self.base / "a.txt").write_text("x")
        plan = self._write_plan(
            [{"id": "AC-1", "family": "file_presence", "path": "a.txt"}])
        res = self._run(plan, "--base-dir", self.base, "--score-only")
        self.assertNotIn("evidence", res.stdout)
        self.assertNotIn("{", res.stdout)  # no JSON, just the float


class LedgerTimestampTests(_TmpBase):
    """Ledger rows carry a run timestamp so an append-only ledger can tell
    runs apart (spec goal 6)."""

    def test_ledger_rows_have_ts(self):
        (self.base / "a.txt").write_text("x")
        out = self.base / ".servo" / "spec-oracles" / "demo"
        out.mkdir(parents=True, exist_ok=True)
        plan = out / "checks.json"
        plan.write_text(json.dumps(
            {"schema_version": 1, "spec_id": "demo",
             "checks": [{"id": "AC-1", "family": "file_presence", "path": "a.txt"}],
             "residual_judgment": []}))
        ledger = out / "ledger.jsonl"
        subprocess.run(
            [sys.executable, str(CHECKS_PY), str(plan), "--base-dir",
             str(self.base), "--ledger", str(ledger)],
            capture_output=True, text=True, check=True)
        rows = [json.loads(ln) for ln in ledger.read_text().splitlines() if ln.strip()]
        self.assertTrue(rows)
        for r in rows:
            self.assertIn("ts", r)
            self.assertTrue(r["ts"])


# ===========================================================================
# --enforce-freeze (slice 006-04 — freeze + approval controls)
# ===========================================================================


class FreezeEnforcementTests(_TmpBase):
    """`--enforce-freeze` refuses (exit 2) unless the overlay is approved, its
    source spec is unchanged, and its generated artifacts are unmodified. The
    default (no flag) path is unaffected — backward compatible with 006-02/03."""

    def _sha(self, p: Path) -> str:
        return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()

    def _setup_overlay(self, *, approval="approved", with_source=True) -> Path:
        d = self.base / ".servo" / "spec-oracles" / "demo"
        d.mkdir(parents=True, exist_ok=True)
        (self.base / "present.txt").write_text("x")
        checks_py = d / "checks.py"
        checks_py.write_text("# generated engine copy\n")
        frag = d / "oracle.sh.fragment"
        frag.write_text("# SEED:start spec_oracle_demo\n# SEED:end spec_oracle_demo\n")
        plan = {
            "schema_version": 1, "spec_id": "demo",
            "checks": [{"id": "AC-1", "family": "file_presence",
                        "path": "present.txt"}],
            "residual_judgment": [],
            "approval_status": approval,
            "approved_artifacts": {"checks.py": self._sha(checks_py),
                                   "oracle.sh.fragment": self._sha(frag)},
        }
        if with_source:
            src = self.base / "spec.md"
            src.write_text("# spec\n")
            plan["source_spec_path"] = "spec.md"
            plan["source_hash"] = self._sha(src)
        plan["approved_content_hash"] = ck.plan_content_hash(plan)
        cj = d / "checks.json"
        cj.write_text(json.dumps(plan))
        return cj

    def _run(self, cj: Path, *extra) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CHECKS_PY), str(cj), "--base-dir",
             str(self.base), "--enforce-freeze", *extra],
            capture_output=True, text=True)

    def test_approved_unchanged_scores(self):
        cj = self._setup_overlay(approval="approved")
        res = self._run(cj, "--score-only")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "1.0")

    def test_draft_refused(self):
        cj = self._setup_overlay(approval="draft")
        res = self._run(cj, "--score-only")
        self.assertEqual(res.returncode, 2)

    def test_missing_approval_defaults_draft_refused(self):
        d = self.base / ".servo" / "spec-oracles" / "demo"
        d.mkdir(parents=True, exist_ok=True)
        (self.base / "present.txt").write_text("x")
        cj = d / "checks.json"
        cj.write_text(json.dumps(
            {"schema_version": 1, "spec_id": "demo",
             "checks": [{"id": "AC-1", "family": "file_presence",
                         "path": "present.txt"}],
             "residual_judgment": []}))
        res = self._run(cj, "--score-only")
        self.assertEqual(res.returncode, 2)

    def test_source_changed_is_stale(self):
        cj = self._setup_overlay(approval="approved", with_source=True)
        (self.base / "spec.md").write_text("# spec CHANGED\n")
        res = self._run(cj, "--score-only")
        self.assertEqual(res.returncode, 2)
        self.assertIn("stale", (res.stderr + res.stdout).lower())

    def test_artifact_modified_refused(self):
        cj = self._setup_overlay(approval="approved")
        (self.base / ".servo" / "spec-oracles" / "demo" / "checks.py").write_text(
            "# tampered to always pass\n")
        res = self._run(cj, "--score-only")
        self.assertEqual(res.returncode, 2)
        self.assertIn("checks.py", res.stderr + res.stdout)

    def test_relaxed_checks_refused(self):
        # Tripwire: relaxing a check after approval (without updating the
        # recorded content hash) is refused, even if the altered check passes.
        cj = self._setup_overlay(approval="approved")
        (self.base / "other.txt").write_text("x")
        plan = json.loads(cj.read_text())
        plan["checks"][0]["path"] = "other.txt"  # altered → content hash stale
        cj.write_text(json.dumps(plan))
        res = self._run(cj, "--score-only")
        self.assertEqual(res.returncode, 2)
        self.assertIn("modified", (res.stderr + res.stdout).lower())

    def test_no_enforce_flag_ignores_approval(self):
        # Backward compatibility: without --enforce-freeze a draft plan still
        # scores normally (006-02/03 behaviour unchanged).
        cj = self._setup_overlay(approval="draft")
        res = subprocess.run(
            [sys.executable, str(CHECKS_PY), str(cj), "--base-dir",
             str(self.base), "--score-only"],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "1.0")


if __name__ == "__main__":
    unittest.main()
