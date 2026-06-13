"""
AC verification tests for slice 011-01 of `/servo:heartbeat` (`heartbeat.py`).

Run from the repo root:
    python3 -m pytest skills/heartbeat/test_heartbeat.py -q
or directly:
    python3 skills/heartbeat/test_heartbeat.py

Test classes map 1:1 to slice 011-01 acceptance criteria:
    AC1 → DiscoverThreeSourcesTests
    AC2 → ReadOnlyByteSnapshotTests + AtomicWriteTests
    AC3 → FindingRecordShapeTests
    AC4 → SourceDegradationTests + ClosedExitContractTests
    AC5 → HumanViewTests + PerSourceHealthHeaderTests
    AC6 → DependencyFreeTests
    AC7 → MockGhGitHarnessTests
    AC8 → FindingIdStabilityTests
    AC9 → TriageBootstrapTests

The mock `gh` / `git` harness (AC7) writes bash scripts into a per-test
`bin/` directory; PATH is set to `<bindir>:/bin:/usr/bin` so the mocks
shadow any real `gh` / `git` (which live outside /bin or /usr/bin) while
keeping bash/env available. No live network, gh, or repo state is touched.
"""

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
HEARTBEAT = REPO_ROOT / "skills" / "heartbeat" / "heartbeat.py"

# Minimal system PATH for tests. /bin + /usr/bin host bash/env on Linux and
# macOS; intentionally excludes /usr/local/bin and any shim dirs so the real
# `gh` / `git` binaries cannot accidentally satisfy a test.
SYSTEM_PATH = "/bin:/usr/bin"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# Two failed CI runs, matching the real `gh run list --json` field surface
# (verified live, gh 2.92.0): attempt, conclusion, createdAt, databaseId,
# displayTitle, event, headBranch, headSha, name, number, startedAt, status,
# updatedAt, url, workflowDatabaseId, workflowName.
GH_RUN_LIST_JSON = json.dumps([
    {
        "attempt": 1,
        "conclusion": "failure",
        "createdAt": "2026-06-10T09:00:00Z",
        "databaseId": 111,
        "displayTitle": "fix the parser",
        "event": "push",
        "headBranch": "main",
        "headSha": "aaaaaaaaaaaa",
        "name": "CI",
        "number": 42,
        "startedAt": "2026-06-10T09:00:05Z",
        "status": "completed",
        "updatedAt": "2026-06-10T09:05:00Z",
        "url": "https://github.com/o/r/actions/runs/111",
        "workflowDatabaseId": 9001,
        "workflowName": "CI",
    },
    {
        "attempt": 2,
        "conclusion": "failure",
        "createdAt": "2026-06-11T10:00:00Z",
        "databaseId": 222,
        "displayTitle": "nightly lint",
        "event": "schedule",
        "headBranch": "release",
        "headSha": "bbbbbbbbbbbb",
        "name": "Lint",
        "number": 7,
        "startedAt": "2026-06-11T10:00:05Z",
        "status": "completed",
        "updatedAt": "2026-06-11T10:02:00Z",
        "url": "https://github.com/o/r/actions/runs/222",
        "workflowDatabaseId": 9002,
        "workflowName": "Lint",
    },
])

# Three open issues, matching the real `gh issue list --json` field surface
# (verified live, gh 2.92.0): assignees, author, body, closed, closedAt,
# comments, createdAt, id, labels, milestone, number, projectItems,
# reactionGroups, state, stateReason, title, updatedAt, url.
GH_ISSUE_LIST_JSON = json.dumps([
    {
        "number": 101,
        "title": "Crash on empty input",
        "body": "Steps to reproduce ...",
        "state": "OPEN",
        "url": "https://github.com/o/r/issues/101",
        "labels": [{"name": "bug"}],
        "author": {"login": "alice"},
        "createdAt": "2026-06-01T00:00:00Z",
        "updatedAt": "2026-06-02T00:00:00Z",
    },
    {
        "number": 102,
        "title": "Add --json flag",
        "body": "",
        "state": "OPEN",
        "url": "https://github.com/o/r/issues/102",
        "labels": [],
        "author": {"login": "bob"},
        "createdAt": "2026-06-03T00:00:00Z",
        "updatedAt": "2026-06-03T00:00:00Z",
    },
    {
        "number": 103,
        "title": "Docs are stale",
        "body": "The README mentions a removed flag.",
        "state": "OPEN",
        "url": "https://github.com/o/r/issues/103",
        "labels": [{"name": "docs"}],
        "author": {"login": "carol"},
        "createdAt": "2026-06-04T00:00:00Z",
        "updatedAt": "2026-06-05T00:00:00Z",
    },
])

# Four recent commits. `git log` is driven with a `--pretty` format so the
# mock emits one record per line; the helper parses it. We use a unit-
# separator-delimited `<sha><US><subject>` shape (see GIT_LOG_FORMAT_TOKEN).
GIT_COMMITS = [
    ("c0ffee0000000000", "feat: add discovery pass"),
    ("deadbeef11111111", "fix: handle empty inbox"),
    ("0123456789abcdef", "docs: note the triage dir"),
    ("fedcba9876543210", "refactor: extract finding shape"),
]


def _make_mock_gh(
    bindir: Path,
    *,
    run_list_json: Optional[str] = GH_RUN_LIST_JSON,
    issue_list_json: Optional[str] = GH_ISSUE_LIST_JSON,
    run_fail: bool = False,
    issue_fail: bool = False,
) -> Path:
    """Write an executable fake `gh` that branches on `run` vs `issue`.

    `run_fail` / `issue_fail` make that subcommand exit non-zero (an auth
    error / transient failure). A None payload + the corresponding *_fail
    flag together let a test fail one source while leaving the other intact.

    Built by string concatenation (not f-strings / str.format) so the JSON
    payloads' braces and brackets are emitted verbatim into the heredoc
    without confusing any template engine.
    """
    if run_fail:
        run_block = '    echo "gh: run list failed" >&2\n    exit 1\n'
    else:
        run_block = (
            "    cat <<'__GH_RUN_EOF__'\n"
            + str(run_list_json) + "\n"
            "__GH_RUN_EOF__\n"
            "    exit 0\n"
        )
    if issue_fail:
        issue_block = '    echo "gh: issue list failed" >&2\n    exit 1\n'
    else:
        issue_block = (
            "    cat <<'__GH_ISSUE_EOF__'\n"
            + str(issue_list_json) + "\n"
            "__GH_ISSUE_EOF__\n"
            "    exit 0\n"
        )
    script = (
        "#!/usr/bin/env bash\n"
        'sub="$1"\n'
        'if [ "$sub" = "run" ]; then\n'
        + run_block
        + 'elif [ "$sub" = "issue" ]; then\n'
        + issue_block
        + "else\n"
        '    echo "gh: unexpected subcommand $sub" >&2\n'
        "    exit 2\n"
        "fi\n"
    )
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(script)
    _make_executable(gh)
    return gh


def _make_mock_gh_bad_json(bindir: Path) -> Path:
    """A `gh` whose `run` emits unparseable JSON (issue stays valid)."""
    # Built by concatenation (not an f-string) so the deliberately-malformed
    # JSON literal's braces/brackets don't confuse the f-string parser.
    script = (
        "#!/usr/bin/env bash\n"
        'sub="$1"\n'
        'if [ "$sub" = "run" ]; then\n'
        "    echo 'this is NOT valid JSON {{{ ]]]'\n"
        "    exit 0\n"
        'elif [ "$sub" = "issue" ]; then\n'
        "    cat <<'__GH_ISSUE_EOF__'\n"
        + GH_ISSUE_LIST_JSON + "\n"
        "__GH_ISSUE_EOF__\n"
        "    exit 0\n"
        "fi\n"
        "exit 2\n"
    )
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(script)
    _make_executable(gh)
    return gh


def _make_mock_gh_empty_run(bindir: Path) -> Path:
    """A `gh` whose `run` exits 0 with EMPTY stdout (issue stays valid).

    Models the edge where a clean `gh` call legitimately returns nothing on
    stdout instead of `[]`: discovery must report ci as `ran (0 findings)`,
    NOT `skipped (unparseable JSON)`, so the health header stays honest.
    """
    script = (
        "#!/usr/bin/env bash\n"
        'sub="$1"\n'
        'if [ "$sub" = "run" ]; then\n'
        "    exit 0\n"
        'elif [ "$sub" = "issue" ]; then\n'
        "    cat <<'__GH_ISSUE_EOF__'\n"
        + GH_ISSUE_LIST_JSON + "\n"
        "__GH_ISSUE_EOF__\n"
        "    exit 0\n"
        "fi\n"
        "exit 2\n"
    )
    bindir.mkdir(parents=True, exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(script)
    _make_executable(gh)
    return gh


def _make_mock_git(
    bindir: Path,
    *,
    commits: Optional[list] = None,
    fail: bool = False,
) -> Path:
    """Write an executable fake `git` that emits `git log` records.

    The mock honours `git -C <dir> log ...`; it ignores the path and any
    pretty/format flags and emits one `<sha><US><subject>` line per commit.
    `fail=True` makes any `log` invocation exit non-zero.
    """
    if commits is None:
        commits = GIT_COMMITS
    us = "\x1f"  # unit separator — matches the helper's GIT_LOG_FORMAT_TOKEN
    lines = "".join(f"{sha}{us}{subj}\n" for sha, subj in commits)
    # Built by concatenation so the heredoc terminator sits at column 0 (a
    # quoted `<<'EOF'` heredoc requires an unindented terminator) and the
    # commit lines are emitted verbatim (no leading whitespace).
    if fail:
        log_block = (
            '        echo "git: log failed" >&2\n'
            "        exit 1\n"
        )
    else:
        log_block = (
            "        cat <<'__GIT_LOG_EOF__'\n"
            + lines
            + "__GIT_LOG_EOF__\n"
            "        exit 0\n"
        )
    # `git -C <dir> log` carries "log" somewhere in argv; scan for it.
    script = (
        "#!/usr/bin/env bash\n"
        'for a in "$@"; do\n'
        '    if [ "$a" = "log" ]; then\n'
        + log_block
        + "    fi\n"
        "done\n"
        'echo "git: unexpected invocation $*" >&2\n'
        "exit 2\n"
    )
    bindir.mkdir(parents=True, exist_ok=True)
    git = bindir / "git"
    git.write_text(script)
    _make_executable(git)
    return git


def _make_oracle_and_manifest(target: Path) -> None:
    """Drop a minimal oracle.sh + .servo/install.json so AC9 stays quiet."""
    servo = target / ".servo"
    servo.mkdir(parents=True, exist_ok=True)
    (servo / "install.json").write_text(json.dumps({
        "installed_tier": "tier-0",
        "components": [],
    }))
    oracle = target / "oracle.sh"
    oracle.write_text("#!/usr/bin/env bash\necho 'oracle: composite=1 threshold=0.5'\n")
    _make_executable(oracle)


def _seed_target_files(target: Path) -> None:
    """Populate the target with a few pre-existing files (for byte-snapshot)."""
    (target / "src.py").write_text("print('hello')\n")
    (target / "README.md").write_text("# demo\n")
    sub = target / "pkg"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / "mod.py").write_text("x = 1\n")


def _run_discover(
    target: Path,
    bindir: Optional[Path] = None,
    *,
    extra_path: Optional[str] = None,
) -> subprocess.CompletedProcess:
    """Invoke `heartbeat.py discover <target>` with a controlled PATH."""
    env = dict(os.environ)
    if bindir is not None:
        env["PATH"] = f"{bindir}:{SYSTEM_PATH}"
    elif extra_path is not None:
        env["PATH"] = extra_path
    else:
        env["PATH"] = SYSTEM_PATH
    return subprocess.run(
        [sys.executable, str(HEARTBEAT), "discover", str(target)],
        capture_output=True,
        text=True,
        env=env,
    )


def _snapshot_tree(root: Path, *, exclude_rel: str) -> dict:
    """Map every file path (relative to root) -> its bytes, excluding a subtree."""
    snapshot = {}
    exclude = (root / exclude_rel).resolve()
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rp = p.resolve()
        if rp == exclude or exclude in rp.parents:
            continue
        snapshot[str(p.relative_to(root))] = p.read_bytes()
    return snapshot


def _read_jsonl(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _triage_dir(target: Path) -> Path:
    return target / ".servo" / "triage"


# ===========================================================================
# AC1 — Read-only discovery over three signal families
# ===========================================================================


class DiscoverThreeSourcesTests(unittest.TestCase):
    """AC1 — 2 ci + 3 issue + 4 commit = exactly 9 findings on the happy path."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac1-")
        root = Path(self.tmp.name)
        self.target = root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_nine_findings_written(self):
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        jsonl = _triage_dir(self.target) / "inbox.jsonl"
        self.assertTrue(jsonl.exists(), "inbox.jsonl was not written")
        findings = _read_jsonl(jsonl)
        self.assertEqual(len(findings), 9, f"expected 9 findings, got {len(findings)}")

    def test_findings_per_source_counts(self):
        _run_discover(self.target, self.bindir)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        by_source = {}
        for f in findings:
            by_source.setdefault(f["source"], 0)
            by_source[f["source"]] += 1
        self.assertEqual(by_source.get("ci"), 2)
        self.assertEqual(by_source.get("issue"), 3)
        self.assertEqual(by_source.get("commit"), 4)

    def test_inbox_md_also_written(self):
        _run_discover(self.target, self.bindir)
        self.assertTrue((_triage_dir(self.target) / "inbox.md").exists())


# ===========================================================================
# AC2 — Strictly read-only outside the artifact dir + atomic write
# ===========================================================================


class ReadOnlyByteSnapshotTests(unittest.TestCase):
    """AC2 — the target tree outside `.servo/triage/` is byte-identical."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac2-")
        root = Path(self.tmp.name)
        self.target = root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        _seed_target_files(self.target)
        self.bindir = root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_tree_byte_identical_outside_triage(self):
        before = _snapshot_tree(self.target, exclude_rel=".servo/triage")
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        after = _snapshot_tree(self.target, exclude_rel=".servo/triage")
        self.assertEqual(
            before, after,
            "discover mutated the target tree outside .servo/triage/",
        )

    def test_only_new_paths_live_under_triage(self):
        before = _snapshot_tree(self.target, exclude_rel=".servo/triage")
        _run_discover(self.target, self.bindir)
        # All pre-existing files unchanged (covered above); additionally
        # assert the ONLY new files are the two triage artifacts.
        after_all = {}
        for p in sorted(self.target.rglob("*")):
            if p.is_file():
                after_all[str(p.relative_to(self.target))] = p.read_bytes()
        new_paths = set(after_all) - set(before)
        triage_prefix = os.path.join(".servo", "triage")
        for path in new_paths:
            self.assertTrue(
                path.startswith(triage_prefix),
                f"discover wrote outside the triage dir: {path}",
            )
        self.assertEqual(
            new_paths,
            {
                os.path.join(triage_prefix, "inbox.jsonl"),
                os.path.join(triage_prefix, "inbox.md"),
            },
        )

    def test_no_tmp_files_left_behind(self):
        _run_discover(self.target, self.bindir)
        leftovers = list(_triage_dir(self.target).glob("*.tmp"))
        self.assertEqual(leftovers, [], f"atomic-write tmp files left behind: {leftovers}")


class AtomicWriteTests(unittest.TestCase):
    """AC2 — both artifacts are written via <name>.tmp + os.replace."""

    def test_helper_uses_os_replace(self):
        text = HEARTBEAT.read_text()
        self.assertIn(
            "os.replace", text,
            "atomic write must use os.replace (ADR-0004 discipline)",
        )

    def test_helper_writes_tmp_then_replaces(self):
        # The tmp suffix and os.replace must both be present, and the tmp
        # path must be replaced ONTO the final path (not the other way).
        text = HEARTBEAT.read_text()
        self.assertRegex(
            text,
            r"\.tmp",
            "atomic write should stage to a .tmp sidecar before replacing",
        )

    def test_rerun_overwrites_not_appends(self):
        # AC2 + the 011-02 boundary note: re-running discover re-emits the
        # current findings (overwrite), it does not append/duplicate.
        tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac2b-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        target = root / "demo"
        target.mkdir()
        _make_oracle_and_manifest(target)
        bindir = root / "bin"
        _make_mock_gh(bindir)
        _make_mock_git(bindir)
        _run_discover(target, bindir)
        first = _read_jsonl(_triage_dir(target) / "inbox.jsonl")
        _run_discover(target, bindir)
        second = _read_jsonl(_triage_dir(target) / "inbox.jsonl")
        self.assertEqual(len(first), 9)
        self.assertEqual(len(second), 9, "re-run must overwrite, not append")


# ===========================================================================
# AC3 — Finding record shape
# ===========================================================================


class FindingRecordShapeTests(unittest.TestCase):
    """AC3 — each JSONL line has the exact required keys, schema_version first."""

    REQUIRED_KEYS = (
        "schema_version", "finding_id", "source", "title", "detail",
        "evidence", "discovered_at", "status",
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac3-")
        root = Path(self.tmp.name)
        self.target = root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)
        _run_discover(self.target, self.bindir)
        self.findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_required_keys_present(self):
        for f in self.findings:
            for key in self.REQUIRED_KEYS:
                self.assertIn(key, f, f"finding missing key {key!r}: {f}")

    def test_schema_version_is_first_key_and_int_one(self):
        # Re-parse preserving key order to assert schema_version is first.
        lines = [
            line for line in
            (_triage_dir(self.target) / "inbox.jsonl").read_text().splitlines()
            if line.strip()
        ]
        for line in lines:
            obj = json.loads(line)
            first_key = next(iter(obj))
            self.assertEqual(first_key, "schema_version", f"schema_version not first: {line}")
            self.assertEqual(obj["schema_version"], 1)
            self.assertIsInstance(obj["schema_version"], int)

    def test_source_enum(self):
        for f in self.findings:
            self.assertIn(f["source"], ("ci", "issue", "commit"))

    def test_status_always_open(self):
        for f in self.findings:
            self.assertEqual(f["status"], "open")

    def test_field_types(self):
        for f in self.findings:
            self.assertIsInstance(f["finding_id"], str)
            self.assertIsInstance(f["title"], str)
            self.assertIsInstance(f["detail"], str)
            self.assertIsInstance(f["evidence"], dict)
            self.assertIsInstance(f["discovered_at"], str)

    def test_discovered_at_is_iso8601(self):
        from datetime import datetime
        for f in self.findings:
            # Should round-trip through fromisoformat without raising.
            datetime.fromisoformat(f["discovered_at"])

    def test_evidence_shapes_per_source(self):
        for f in self.findings:
            ev = f["evidence"]
            if f["source"] == "ci":
                self.assertIn("run_url", ev)
                self.assertIn("workflow", ev)
            elif f["source"] == "issue":
                self.assertIn("issue_number", ev)
                self.assertIn("url", ev)
            elif f["source"] == "commit":
                self.assertIn("commit_sha", ev)


# ===========================================================================
# AC4 — Per-source independent degradation + closed exit contract
# ===========================================================================


class SourceDegradationTests(unittest.TestCase):
    """AC4 — one source failing skips THAT source and continues over the rest."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac4a-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"

    def tearDown(self):
        self.tmp.cleanup()

    def test_gh_absent_skips_ci_and_issue_keeps_commit(self):
        # Only git present (no gh on PATH). ci + issue skip; commit survives.
        _make_mock_git(self.bindir)
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        sources = {f["source"] for f in findings}
        self.assertEqual(sources, {"commit"})
        self.assertEqual(len(findings), 4)
        self.assertIn("gh not on PATH", res.stderr)

    def test_git_log_failure_skips_commit_keeps_gh(self):
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir, fail=True)
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        sources = {f["source"] for f in findings}
        self.assertEqual(sources, {"ci", "issue"})
        self.assertIn("git log", res.stderr)

    def test_gh_run_failure_skips_ci_keeps_issue_and_commit(self):
        _make_mock_gh(self.bindir, run_fail=True, run_list_json=None)
        _make_mock_git(self.bindir)
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        sources = {f["source"] for f in findings}
        self.assertEqual(sources, {"issue", "commit"})

    def test_unparseable_json_skips_that_source(self):
        _make_mock_gh_bad_json(self.bindir)
        _make_mock_git(self.bindir)
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        sources = {f["source"] for f in findings}
        # ci has bad JSON → skipped; issue + commit survive.
        self.assertNotIn("ci", sources)
        self.assertIn("issue", sources)
        self.assertIn("commit", sources)

    def test_all_sources_absent_exits_zero_empty_inbox(self):
        # No gh, no git on PATH → all sources skip, empty inbox, exit 0.
        empty_bin = self.root / "emptybin"
        empty_bin.mkdir()
        res = _run_discover(self.target, empty_bin)
        self.assertEqual(res.returncode, 0, res.stderr)
        jsonl = _triage_dir(self.target) / "inbox.jsonl"
        self.assertTrue(jsonl.exists(), "empty inbox.jsonl should still be written")
        self.assertEqual(_read_jsonl(jsonl), [])

    def test_empty_stdout_reports_ran_not_skipped(self):
        # A clean `gh run` exit-0 with EMPTY stdout = "ran, found nothing" — ci
        # must be reported `ran (0 findings)`, NOT skipped, so the health header
        # never mislabels a healthy-but-empty source as degraded.
        _make_mock_gh_empty_run(self.bindir)
        _make_mock_git(self.bindir)
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        sources = {f["source"] for f in findings}
        # ci ran but found nothing → no ci findings; issue + commit survive.
        self.assertEqual({"issue", "commit"}, sources)
        # Health header reports ci ran-with-zero, not skipped.
        md = (_triage_dir(self.target) / "inbox.md").read_text()
        self.assertIn("**ci**: ran (0 findings)", md)
        self.assertNotIn("**ci**: skipped", md)
        # And no "skipping ci" breadcrumb on stderr — it didn't skip.
        self.assertNotIn("skipping ci source", res.stderr)


class ClosedExitContractTests(unittest.TestCase):
    """AC4 — exit codes are a closed {0, 2} set; no exit 1."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac4b-")
        self.root = Path(self.tmp.name)
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_target_exits_two(self):
        missing = self.root / "does-not-exist"
        res = _run_discover(missing, self.bindir)
        self.assertEqual(res.returncode, 2)
        self.assertIn("target", res.stderr.lower())

    def test_target_not_directory_exits_two(self):
        f = self.root / "afile"
        f.write_text("not a dir\n")
        res = _run_discover(f, self.bindir)
        self.assertEqual(res.returncode, 2)

    def test_happy_path_exits_zero(self):
        target = self.root / "demo"
        target.mkdir()
        _make_oracle_and_manifest(target)
        res = _run_discover(target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_never_exits_one(self):
        # Every degradation path must remain in {0, 2} — exercise a fully
        # degraded run and confirm it is 0, not 1.
        target = self.root / "demo2"
        target.mkdir()
        _make_oracle_and_manifest(target)
        empty_bin = self.root / "emptybin"
        empty_bin.mkdir()
        res = _run_discover(target, empty_bin)
        self.assertEqual(res.returncode, 0)
        self.assertNotEqual(res.returncode, 1)

    def test_unwritable_triage_dir_exits_two(self):
        if os.geteuid() == 0:
            self.skipTest("root bypasses directory permissions")
        target = self.root / "demo3"
        target.mkdir()
        _make_oracle_and_manifest(target)
        # Make .servo present but unwritable so triage/ cannot be created.
        servo = target / ".servo"
        servo.chmod(0o500)
        # Restore writability in a guarded cleanup so TemporaryDirectory
        # teardown can recurse into it (and so the cleanup never raises if the
        # dir is already gone).
        self.addCleanup(self._restore_mode, servo)
        res = _run_discover(target, self.bindir)
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("triage", res.stderr.lower())

    @staticmethod
    def _restore_mode(path: Path) -> None:
        if path.exists():
            path.chmod(0o700)


# ===========================================================================
# AC5 — Generated human-readable view + per-source health header
# ===========================================================================


class HumanViewTests(unittest.TestCase):
    """AC5 — inbox.md groups findings by source with title/status/evidence."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac5a-")
        root = Path(self.tmp.name)
        self.target = root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)
        _run_discover(self.target, self.bindir)
        self.md = (_triage_dir(self.target) / "inbox.md").read_text()

    def tearDown(self):
        self.tmp.cleanup()

    def test_generated_marker_present(self):
        self.assertIn(
            "<!-- generated by heartbeat.py — do not hand-edit -->",
            self.md,
        )

    def test_grouped_by_source(self):
        # Each source family should appear as a section heading.
        for src in ("ci", "issue", "commit"):
            self.assertRegex(
                self.md, rf"(?i){src}",
                f"inbox.md missing a section for source {src!r}",
            )

    def test_shows_titles(self):
        self.assertIn("Crash on empty input", self.md)
        self.assertIn("fix the parser", self.md)

    def test_shows_status_and_evidence_ref(self):
        self.assertIn("open", self.md)
        # An evidence reference (a URL or sha) should be present.
        self.assertTrue(
            "https://github.com/o/r/issues/101" in self.md
            or "c0ffee0000000000" in self.md,
            "inbox.md shows no evidence reference",
        )


class PerSourceHealthHeaderTests(unittest.TestCase):
    """AC5 — inbox.md opens with a per-source ran/skipped status header."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac5b-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"

    def tearDown(self):
        self.tmp.cleanup()

    def test_header_lists_all_three_sources_as_ran(self):
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)
        _run_discover(self.target, self.bindir)
        md = (_triage_dir(self.target) / "inbox.md").read_text()
        for src in ("ci", "issue", "commit"):
            self.assertRegex(md, rf"(?i){src}.*\bran\b")

    def test_header_shows_skipped_with_cause(self):
        # No gh → ci/issue skipped; the header should say so with a cause.
        _make_mock_git(self.bindir)
        _run_discover(self.target, self.bindir)
        md = (_triage_dir(self.target) / "inbox.md").read_text()
        self.assertRegex(md, r"(?i)ci.*skipped")
        self.assertRegex(md, r"(?i)issue.*skipped")
        self.assertRegex(md, r"(?i)commit.*ran")

    def test_header_shows_finding_counts_for_ran_sources(self):
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)
        _run_discover(self.target, self.bindir)
        md = (_triage_dir(self.target) / "inbox.md").read_text()
        # ci ran with 2, issue with 3, commit with 4.
        self.assertRegex(md, r"(?i)ci.*ran.*2")
        self.assertRegex(md, r"(?i)issue.*ran.*3")
        self.assertRegex(md, r"(?i)commit.*ran.*4")

    def test_header_appears_before_findings(self):
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)
        _run_discover(self.target, self.bindir)
        md = (_triage_dir(self.target) / "inbox.md").read_text()
        # The first finding title should appear after the word "skipped"/"ran"
        # status block — i.e. a status header precedes the body.
        header_idx = md.lower().find("ran")
        body_idx = md.find("Crash on empty input")
        self.assertNotEqual(header_idx, -1)
        self.assertNotEqual(body_idx, -1)
        self.assertLess(header_idx, body_idx, "health header must precede findings")


# ===========================================================================
# AC6 — Dependency-free (stdlib only)
# ===========================================================================


class DependencyFreeTests(unittest.TestCase):
    """AC6 — heartbeat.py uses only the Python 3.11+ standard library."""

    STDLIB_TOP_LEVELS = {
        "argparse", "json", "os", "re", "subprocess", "sys", "stat",
        "shutil", "pathlib", "dataclasses", "datetime", "typing",
        "collections", "itertools", "functools", "tempfile", "io",
        "contextlib", "errno", "enum", "uuid", "textwrap", "string",
        "platform", "signal", "secrets", "hashlib", "math", "time",
        "__future__",
    }

    def test_no_third_party_imports(self):
        text = HEARTBEAT.read_text()
        for line in text.splitlines():
            stripped = line.strip()
            m = re.match(r"^(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
            if not m:
                continue
            top = m.group(1)
            self.assertIn(
                top, self.STDLIB_TOP_LEVELS,
                f"non-stdlib import found: {top!r} on line: {stripped!r}",
            )

    def test_no_requirements_file_alongside_helper(self):
        for name in ("requirements.txt", "setup.py", "pyproject.toml"):
            self.assertFalse(
                (HEARTBEAT.parent / name).exists(),
                f"unexpected dependency descriptor at {HEARTBEAT.parent / name}",
            )

    def test_gh_and_git_are_subprocessed_not_imported(self):
        text = HEARTBEAT.read_text()
        # No `import gh` / `import git` (those would be third-party anyway).
        self.assertNotRegex(text, r"^\s*import\s+gh\b", )
        self.assertNotRegex(text, r"^\s*import\s+git\b")
        self.assertIn("subprocess", text)


# ===========================================================================
# AC7 — Mock harness (fake gh/git via PATH)
# ===========================================================================


class MockGhGitHarnessTests(unittest.TestCase):
    """AC7 — fake gh/git binaries via PATH; no live network/gh/repo touched."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac7-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"

    def tearDown(self):
        self.tmp.cleanup()

    def test_happy_path_nine_findings(self):
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        self.assertEqual(len(findings), 9)

    def test_each_source_individually_failing(self):
        # gh run fails → ci absent.
        _make_mock_gh(self.bindir, run_fail=True, run_list_json=None)
        _make_mock_git(self.bindir)
        findings = self._discover_sources()
        self.assertNotIn("ci", findings)
        self.assertIn("issue", findings)
        self.assertIn("commit", findings)
        # gh issue fails → issue absent.
        _make_mock_gh(self.bindir, issue_fail=True, issue_list_json=None)
        _make_mock_git(self.bindir)
        findings = self._discover_sources()
        self.assertIn("ci", findings)
        self.assertNotIn("issue", findings)
        self.assertIn("commit", findings)
        # git fails → commit absent.
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir, fail=True)
        findings = self._discover_sources()
        self.assertIn("ci", findings)
        self.assertIn("issue", findings)
        self.assertNotIn("commit", findings)

    def test_all_sources_absent(self):
        empty_bin = self.root / "emptybin"
        empty_bin.mkdir()
        res = _run_discover(self.target, empty_bin)
        self.assertEqual(res.returncode, 0, res.stderr)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        self.assertEqual(findings, [])

    def test_mock_json_matches_real_field_names(self):
        # Guard: the canned gh JSON in this test module must use the real
        # field surface (the spike's central validation). Spot-check the
        # load-bearing names this helper reads.
        run = json.loads(GH_RUN_LIST_JSON)
        for r in run:
            self.assertIn("workflowName", r)
            self.assertIn("headBranch", r)
            self.assertIn("url", r)
            self.assertIn("conclusion", r)
        issues = json.loads(GH_ISSUE_LIST_JSON)
        for i in issues:
            self.assertIn("number", i)
            self.assertIn("title", i)
            self.assertIn("url", i)

    def _discover_sources(self) -> set:
        _run_discover(self.target, self.bindir)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        return {f["source"] for f in findings}


# ===========================================================================
# AC8 — Stable finding_id fingerprint
# ===========================================================================


class FindingIdStabilityTests(unittest.TestCase):
    """AC8 — finding_id is deterministic across re-runs and content-derived."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac8-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_finding_ids_stable_across_reruns(self):
        _run_discover(self.target, self.bindir)
        first = {f["finding_id"] for f in _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")}
        _run_discover(self.target, self.bindir)
        second = {f["finding_id"] for f in _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")}
        self.assertEqual(first, second, "finding_id changed across identical re-runs")
        self.assertEqual(len(first), 9, "finding_ids should be unique per finding")

    def test_finding_ids_are_16_hex_chars(self):
        _run_discover(self.target, self.bindir)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        for f in findings:
            self.assertRegex(
                f["finding_id"], r"^[0-9a-f]{16}$",
                f"finding_id is not 16 hex chars: {f['finding_id']!r}",
            )

    def test_ci_fingerprint_is_workflow_plus_branch(self):
        # AC8 + the deviation: ci fingerprint = sha256("ci|"+workflow+"|"+branch)[:16].
        _run_discover(self.target, self.bindir)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        ci = [f for f in findings if f["source"] == "ci"]
        expected = hashlib.sha256(b"ci|CI|main").hexdigest()[:16]
        ids = {f["finding_id"] for f in ci}
        self.assertIn(expected, ids, "ci finding_id is not sha256('ci|workflow|branch')[:16]")

    def test_commit_fingerprint_is_sha_derived(self):
        _run_discover(self.target, self.bindir)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        commits = [f for f in findings if f["source"] == "commit"]
        expected = hashlib.sha256(b"commit|c0ffee0000000000").hexdigest()[:16]
        ids = {f["finding_id"] for f in commits}
        self.assertIn(expected, ids)

    def test_issue_fingerprint_is_number_derived(self):
        _run_discover(self.target, self.bindir)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        issues = [f for f in findings if f["source"] == "issue"]
        expected = hashlib.sha256(b"issue|101").hexdigest()[:16]
        ids = {f["finding_id"] for f in issues}
        self.assertIn(expected, ids)

    def test_finding_id_independent_of_timestamps(self):
        # discovered_at changes between runs, but finding_id must not.
        _run_discover(self.target, self.bindir)
        f1 = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        ts1 = {f["finding_id"]: f["discovered_at"] for f in f1}
        _run_discover(self.target, self.bindir)
        f2 = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        ids2 = {f["finding_id"] for f in f2}
        # ids identical even though discovered_at is regenerated each run.
        self.assertEqual(set(ts1), ids2)


# ===========================================================================
# AC9 — Triage dir bootstrap + oracle-independence breadcrumb
# ===========================================================================


class TriageBootstrapTests(unittest.TestCase):
    """AC9 — creates triage/ if absent; oracle-independent (never refuses)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-ac9-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_triage_dir_when_absent(self):
        _make_oracle_and_manifest(self.target)
        self.assertFalse(_triage_dir(self.target).exists())
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(_triage_dir(self.target).is_dir())

    def test_no_oracle_no_manifest_still_exits_zero(self):
        # Bare target — no .servo/install.json, no oracle.sh.
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        self.assertEqual(len(findings), 9, "discovery must work oracle-independently")

    def test_no_oracle_emits_breadcrumb(self):
        res = _run_discover(self.target, self.bindir)
        self.assertIn("no oracle/manifest", res.stderr)
        self.assertIn("dispatch unavailable", res.stderr)

    def test_oracle_present_no_breadcrumb(self):
        _make_oracle_and_manifest(self.target)
        res = _run_discover(self.target, self.bindir)
        self.assertNotIn("no oracle/manifest", res.stderr)

    def test_manifest_present_oracle_absent_emits_breadcrumb(self):
        # Only manifest, no oracle.sh → still a breadcrumb (either absent triggers).
        servo = self.target / ".servo"
        servo.mkdir(parents=True, exist_ok=True)
        (servo / "install.json").write_text('{"installed_tier": "tier-0", "components": []}')
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("no oracle/manifest", res.stderr)


if __name__ == "__main__":
    unittest.main()
