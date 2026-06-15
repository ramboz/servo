"""
AC verification tests for `/servo:heartbeat` (`heartbeat.py`), slices 011-01 + 011-02.

Run from the repo root:
    python3 -m pytest skills/heartbeat/test_heartbeat.py -q
or directly:
    python3 skills/heartbeat/test_heartbeat.py

Slice 011-01 (discover-and-inbox) acceptance criteria:
    AC1 → DiscoverThreeSourcesTests
    AC2 → ReadOnlyByteSnapshotTests + AtomicWriteTests
    AC3 → FindingRecordShapeTests
    AC4 → SourceDegradationTests + ClosedExitContractTests
    AC5 → HumanViewTests + PerSourceHealthHeaderTests
    AC6 → DependencyFreeTests
    AC7 → MockGhGitHarnessTests
    AC8 → FindingIdStabilityTests
    AC9 → TriageBootstrapTests

Slice 011-02 (triage-state-spine) acceptance criteria:
    AC1  → SchemaV2RecordShapeTests
    AC2  → FindingIdStabilityTests (extended)
    AC3  → MergeDedupeTests
    AC4  → ResumeTests
    AC5  → RetentionTests
    AC6  → ActionabilityClassificationTests
    AC7  → ProvenanceMarkerTests
    AC8  → ConcurrencyLockTests
    AC9  → StatusSubcommandTests
    AC10 → SchemaMigrationTests
    AC11 → the 011-01 classes above, extended (ReadOnlyByteSnapshotTests /
           AtomicWriteTests / SourceDegradationTests / ClosedExitContractTests /
           HumanViewTests / DependencyFreeTests)

The mock `gh` / `git` harness (011-01 AC7) writes bash scripts into a per-test
`bin/` directory; PATH is set to `<bindir>:/bin:/usr/bin` so the mocks
shadow a real `git` (and a real `gh` where it lives outside /bin:/usr/bin)
while keeping bash/env available. (Ubuntu CI ships /usr/bin/gh, which leaks
through — see SYSTEM_PATH.) No live network, gh, or repo state is touched.
The 011-02 mock `gh` additionally answers `repo view --json defaultBranchRef`
(CI actionability) and the mock `git` answers `symbolic-ref` (default-branch
fallback); both default to a clean resolution so the 011-01 tests are unaffected.
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
# macOS; intentionally excludes /usr/local/bin and any shim dirs so a real
# `git` cannot accidentally satisfy a test. NOTE: GitHub's Ubuntu runners ship
# `gh` at /usr/bin/gh, so gh *does* leak through here — gh-absent scenarios must
# assert graceful degradation (absent OR non-zero exit), never the exact "not on
# PATH" wording (which only holds where gh lives outside /bin:/usr/bin).
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
    default_branch: Optional[str] = "main",
    repo_view_fail: bool = False,
) -> Path:
    """Write an executable fake `gh` that branches on `run` / `issue` / `repo`.

    `run_fail` / `issue_fail` make that subcommand exit non-zero (an auth
    error / transient failure). A None payload + the corresponding *_fail
    flag together let a test fail one source while leaving the other intact.

    `default_branch` is the branch name returned by `gh repo view --json
    defaultBranchRef` (011-02's authoritative default-branch resolution for CI
    actionability); set `repo_view_fail=True` to make that call exit non-zero so
    discovery falls back to `git symbolic-ref` / heuristic. `default_branch`
    defaults to "main" so the realistic happy path resolves without a fallback.

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
    if repo_view_fail or default_branch is None:
        repo_block = '    echo "gh: repo view failed" >&2\n    exit 1\n'
    else:
        repo_view_json = json.dumps({"defaultBranchRef": {"name": default_branch}})
        repo_block = (
            "    cat <<'__GH_REPO_EOF__'\n"
            + repo_view_json + "\n"
            "__GH_REPO_EOF__\n"
            "    exit 0\n"
        )
    script = (
        "#!/usr/bin/env bash\n"
        'sub="$1"\n'
        'if [ "$sub" = "run" ]; then\n'
        + run_block
        + 'elif [ "$sub" = "issue" ]; then\n'
        + issue_block
        + 'elif [ "$sub" = "repo" ]; then\n'
        + repo_block
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
    repo_view_json = json.dumps({"defaultBranchRef": {"name": "main"}})
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
        'elif [ "$sub" = "repo" ]; then\n'
        "    cat <<'__GH_REPO_EOF__'\n"
        + repo_view_json + "\n"
        "__GH_REPO_EOF__\n"
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
    repo_view_json = json.dumps({"defaultBranchRef": {"name": "main"}})
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
        'elif [ "$sub" = "repo" ]; then\n'
        "    cat <<'__GH_REPO_EOF__'\n"
        + repo_view_json + "\n"
        "__GH_REPO_EOF__\n"
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
    symbolic_ref_branch: Optional[str] = None,
) -> Path:
    """Write an executable fake `git` that emits `git log` records.

    The mock honours `git -C <dir> log ...`; it ignores the path and any
    pretty/format flags and emits one `<sha><US><subject>` line per commit.
    `fail=True` makes any `log` invocation exit non-zero.

    `symbolic_ref_branch` controls the second-tier default-branch fallback
    (`git symbolic-ref --short refs/remotes/origin/HEAD`): None (the default)
    makes that call exit non-zero — modelling the very common unset-`origin/HEAD`
    clone, so the heuristic/unknown tiers are exercised — while a branch name
    makes it print `origin/<branch>` on a clean exit, as a real clone with a set
    `origin/HEAD` would.
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
    if symbolic_ref_branch is None:
        symref_block = (
            '        echo "git: no upstream configured for origin/HEAD" >&2\n'
            "        exit 1\n"
        )
    else:
        symref_block = (
            '        echo "origin/' + symbolic_ref_branch + '"\n'
            "        exit 0\n"
        )
    # `git -C <dir> log` and `git symbolic-ref ...` each carry their verb
    # somewhere in argv; scan for each. `symbolic-ref` is checked first so it
    # wins even though both loops scan the same argv.
    script = (
        "#!/usr/bin/env bash\n"
        'for a in "$@"; do\n'
        '    if [ "$a" = "symbolic-ref" ]; then\n'
        + symref_block
        + "    fi\n"
        "done\n"
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


def _run_status(
    target: Path,
    bindir: Optional[Path] = None,
    *,
    as_json: bool = False,
) -> subprocess.CompletedProcess:
    """Invoke `heartbeat.py status <target>` (optionally `--json`).

    `status` is read-only and reads no live `gh`/`git`, so a bindir is rarely
    needed; it is accepted for symmetry with `_run_discover` and so a test can
    confirm `status` does not shell out.
    """
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{SYSTEM_PATH}" if bindir is not None else SYSTEM_PATH
    argv = [sys.executable, str(HEARTBEAT), "status", str(target)]
    if as_json:
        argv.append("--json")
    return subprocess.run(argv, capture_output=True, text=True, env=env)


def _write_inbox(target: Path, records: list) -> Path:
    """Hand-write `<target>/.servo/triage/inbox.jsonl` from `records` (one/line).

    Used to seed cross-run state (a `tried`/`passed` finding, a stale `open`
    finding, a `schema_version: 1` legacy record) without driving a full
    discover first — the merge/resume/retention/migration ACs need a pre-existing
    inbox under the implementation's control.
    """
    triage = _triage_dir(target)
    triage.mkdir(parents=True, exist_ok=True)
    jsonl = triage / "inbox.jsonl"
    jsonl.write_text("".join(json.dumps(r) + "\n" for r in records))
    return jsonl


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
        # assert the ONLY new files live under the triage dir: the two artifacts
        # plus the persistent advisory-lock target (011-02, AC8).
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
                os.path.join(triage_prefix, ".inbox.lock"),
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

    def test_rerun_does_not_duplicate(self):
        # 011-01 overwrote the JSONL; 011-02 MERGES by finding_id. Either way,
        # re-running discover on identical signals must not append/duplicate —
        # the nine findings keep their stable ids and are refreshed in place.
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
        self.assertEqual(len(second), 9, "re-run must merge in place, not append")


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

    def test_schema_version_is_first_key_and_int_two(self):
        # Re-parse preserving key order to assert schema_version is first.
        # Bumped 1 → 2 at slice 011-02 (the state-spine record shape; ADR-0010).
        lines = [
            line for line in
            (_triage_dir(self.target) / "inbox.jsonl").read_text().splitlines()
            if line.strip()
        ]
        for line in lines:
            obj = json.loads(line)
            first_key = next(iter(obj))
            self.assertEqual(first_key, "schema_version", f"schema_version not first: {line}")
            self.assertEqual(obj["schema_version"], 2)
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
        # Only a mock git is on PATH, so the real gh is unusable — either absent
        # (dev machines keep gh outside /bin:/usr/bin) or present-but-failing
        # (GitHub's Ubuntu runners ship /usr/bin/gh, which leaks through
        # SYSTEM_PATH and exits non-zero). Either way the gh-backed ci + issue
        # sources skip independently and commit survives.
        _make_mock_git(self.bindir)
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        sources = {f["source"] for f in findings}
        self.assertEqual(sources, {"commit"})
        self.assertEqual(len(findings), 4)
        # Assert the degradation was logged for both gh-backed sources, tolerant
        # of the cause (not-on-PATH vs non-zero exit) so it holds on any runner.
        self.assertRegex(res.stderr, r"gh (not on PATH|exited \d+).*skipping ci source")
        self.assertRegex(res.stderr, r"gh (not on PATH|exited \d+).*skipping issue source")

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
        # `fcntl` is POSIX-only stdlib — added at slice 011-02 for the
        # double-fire advisory flock (it is imported under a try/except so a
        # non-POSIX host degrades to unlocked; ADR-0010).
        "fcntl",
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

    def test_finding_id_is_the_dedupe_key_across_status_change(self):
        # 011-02 extension: the SAME finding_id is what the merge dedupes on —
        # a status mutation (e.g. dispatch-set tried) does not change the id, so
        # the next discover matches and resumes it rather than minting a new one.
        _run_discover(self.target, self.bindir)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        # Hand-flip one finding to `tried` (simulating an 011-03 dispatch / human).
        findings[0]["status"] = "tried"
        findings[0]["attempts"] = 1
        target_id = findings[0]["finding_id"]
        (_triage_dir(self.target) / "inbox.jsonl").write_text(
            "".join(json.dumps(f) + "\n" for f in findings)
        )
        _run_discover(self.target, self.bindir)
        after = {f["finding_id"]: f
                 for f in _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")}
        # Same id present (not duplicated), and it resumed as tried.
        self.assertIn(target_id, after)
        self.assertEqual(after[target_id]["status"], "tried")
        self.assertEqual(len(after), 9, "id-keyed merge must not duplicate")


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


# ###########################################################################
# Slice 011-02 — triage-state-spine
# ###########################################################################


# A reusable v2 record builder for hand-seeding cross-run state. Mirrors the
# implementation's key set + ADR-0010 order; tests override only what they care
# about. Volatile fields default to a plausible CI shape.
def _v2_record(**overrides) -> dict:
    rec = {
        "schema_version": 2,
        "finding_id": "deadbeefdeadbeef",
        "source": "ci",
        "provenance": "first_party",
        "discovered_at": "2026-06-01T00:00:00+00:00",
        "status": "open",
        "attempts": 0,
        "outcome": None,
        "title": "seeded finding",
        "detail": "",
        "evidence": {},
        "last_seen_at": "2026-06-01T00:00:00+00:00",
        "actionable": True,
        "actionable_reason": "ci_default_branch",
    }
    rec.update(overrides)
    return rec


# ===========================================================================
# 011-02 AC1 — Schema v2 record shape (fields, order, all-identical version)
# ===========================================================================


class SchemaV2RecordShapeTests(unittest.TestCase):
    """011-02 AC1 — v2 records carry the full field set in ADR-0010 order."""

    # The complete v2 field set, in the canonical ADR-0010 insertion order:
    # schema_version, then immutable, then sticky, then volatile.
    EXPECTED_ORDER = (
        "schema_version",
        "finding_id", "source", "provenance", "discovered_at",
        "status", "attempts", "outcome",
        "title", "detail", "evidence", "last_seen_at",
        "actionable", "actionable_reason",
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-v2-ac1-")
        root = Path(self.tmp.name)
        self.target = root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)
        _run_discover(self.target, self.bindir)
        self.jsonl = _triage_dir(self.target) / "inbox.jsonl"
        self.findings = _read_jsonl(self.jsonl)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_v2_fields_present(self):
        for f in self.findings:
            for key in self.EXPECTED_ORDER:
                self.assertIn(key, f, f"finding missing v2 key {key!r}: {f}")

    def test_key_order_exact(self):
        # Insertion order is load-bearing (ADR-0010): assert the exact key
        # sequence, not just membership.
        for line in self.jsonl.read_text().splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            self.assertEqual(
                tuple(obj.keys()), self.EXPECTED_ORDER,
                f"v2 key order wrong: {tuple(obj.keys())}",
            )

    def test_schema_version_first_and_two(self):
        for f in self.findings:
            self.assertEqual(next(iter(f)), "schema_version")
            self.assertEqual(f["schema_version"], 2)

    def test_sticky_defaults_on_fresh_discovery(self):
        # A freshly-discovered finding has the dispatch defaults reserved for
        # 011-03 (attempts: 0, outcome: null) and status open.
        for f in self.findings:
            self.assertEqual(f["status"], "open")
            self.assertEqual(f["attempts"], 0)
            self.assertIsNone(f["outcome"])

    def test_field_types(self):
        for f in self.findings:
            self.assertIsInstance(f["finding_id"], str)
            self.assertIn(f["source"], ("ci", "issue", "commit"))
            self.assertIn(f["provenance"], ("first_party", "contributor"))
            self.assertIsInstance(f["discovered_at"], str)
            self.assertIn(f["status"], ("open", "tried", "passed", "skipped"))
            self.assertIsInstance(f["attempts"], int)
            self.assertTrue(f["outcome"] is None or isinstance(f["outcome"], dict))
            self.assertIsInstance(f["title"], str)
            self.assertIsInstance(f["detail"], str)
            self.assertIsInstance(f["evidence"], dict)
            self.assertIsInstance(f["last_seen_at"], str)
            self.assertIsInstance(f["actionable"], bool)
            self.assertIsInstance(f["actionable_reason"], str)

    def test_discovered_and_last_seen_iso8601(self):
        from datetime import datetime
        for f in self.findings:
            datetime.fromisoformat(f["discovered_at"])
            datetime.fromisoformat(f["last_seen_at"])

    def test_all_records_same_schema_version(self):
        versions = {f["schema_version"] for f in self.findings}
        self.assertEqual(versions, {2})

    def test_mixed_version_file_rejected_by_status(self):
        # A file with two different schema_versions is corruption; the reader
        # (status) refuses rc=2. (discover's migration discards <2 and rebuilds,
        # so the mixed-version *rejection* contract is observed on the read path.)
        _write_inbox(self.target, [
            _v2_record(finding_id="a" * 16),
            _v2_record(finding_id="b" * 16, schema_version=3),
        ])
        res = _run_status(self.target)
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("schema_version", res.stderr.lower())


# ===========================================================================
# 011-02 AC3 — Uniform merge across runs (no more overwrite)
# ===========================================================================


class MergeDedupeTests(unittest.TestCase):
    """011-02 AC3 — merge by finding_id: preserve immutable+sticky, refresh volatile."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-v2-ac3-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def _by_id(self, findings):
        return {f["finding_id"]: f for f in findings}

    def test_existing_finding_preserves_discovered_at(self):
        _run_discover(self.target, self.bindir)
        first = self._by_id(_read_jsonl(_triage_dir(self.target) / "inbox.jsonl"))
        _run_discover(self.target, self.bindir)
        second = self._by_id(_read_jsonl(_triage_dir(self.target) / "inbox.jsonl"))
        self.assertEqual(set(first), set(second))
        for fid, rec in second.items():
            # discovered_at (first-seen) is immutable across the merge.
            self.assertEqual(
                rec["discovered_at"], first[fid]["discovered_at"],
                "merge must preserve first-seen discovered_at",
            )

    def test_last_seen_refreshes_on_reobservation(self):
        _run_discover(self.target, self.bindir)
        first = self._by_id(_read_jsonl(_triage_dir(self.target) / "inbox.jsonl"))
        _run_discover(self.target, self.bindir)
        second = self._by_id(_read_jsonl(_triage_dir(self.target) / "inbox.jsonl"))
        # last_seen_at is volatile — it must be >= the first pass's value for
        # every re-observed finding (monotonic refresh).
        for fid, rec in second.items():
            self.assertGreaterEqual(
                rec["last_seen_at"], first[fid]["last_seen_at"],
                "merge must refresh last_seen_at on re-observation",
            )

    def test_new_finding_appended_with_open_defaults(self):
        # Seed one pre-existing finding, then discover (which mints nine ids).
        # The seeded id (not produced by discovery) is retained only if it has a
        # lifecycle status; an extra OPEN seed that is not re-observed is evicted
        # (covered in RetentionTests). Here we assert NEWLY-seen discovery ids get
        # the open defaults.
        _run_discover(self.target, self.bindir)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        for f in findings:
            self.assertEqual(f["status"], "open")
            self.assertEqual(f["attempts"], 0)
            self.assertIsNone(f["outcome"])
            self.assertEqual(f["discovered_at"], f["last_seen_at"])

    def test_volatile_fields_refresh_from_new_signal(self):
        # Seed a CI finding whose id matches a discovered run (CI on main), with
        # stale volatile content; after discover the volatile fields reflect the
        # fresh signal while the sticky/immutable fields are preserved.
        ci_id = hashlib.sha256(b"ci|CI|main").hexdigest()[:16]
        seeded_seen = "2020-01-01T00:00:00+00:00"
        _write_inbox(self.target, [_v2_record(
            finding_id=ci_id, source="ci", status="tried", attempts=1,
            title="STALE TITLE", detail="stale detail",
            last_seen_at=seeded_seen, actionable=False,
            actionable_reason="ci_non_default_branch",
            discovered_at="2020-01-01T00:00:00+00:00",
        )])
        _run_discover(self.target, self.bindir)
        rec = self._by_id(_read_jsonl(_triage_dir(self.target) / "inbox.jsonl"))[ci_id]
        # Sticky preserved:
        self.assertEqual(rec["status"], "tried")
        self.assertEqual(rec["attempts"], 1)
        self.assertEqual(rec["discovered_at"], "2020-01-01T00:00:00+00:00")
        # Volatile refreshed from the live signal:
        self.assertNotEqual(rec["last_seen_at"], seeded_seen)
        self.assertIn("CI", rec["title"])
        self.assertTrue(rec["actionable"])  # CI on main, event push → actionable
        self.assertEqual(rec["actionable_reason"], "ci_default_branch")


# ===========================================================================
# 011-02 AC4 — Resume (sticky lifecycle survives re-discovery)
# ===========================================================================


class ResumeTests(unittest.TestCase):
    """011-02 AC4 — a tried/passed/skipped finding is never reset to open."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-v2-ac4-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def _seed_commit_with_status(self, status):
        # Seed a commit finding whose id matches the first GIT_COMMITS sha, so it
        # is re-observed every discover pass.
        sha = GIT_COMMITS[0][0]
        cid = hashlib.sha256(("commit|" + sha).encode()).hexdigest()[:16]
        _write_inbox(self.target, [_v2_record(
            finding_id=cid, source="commit", provenance="contributor",
            status=status, attempts=1 if status != "open" else 0,
            title="seeded commit", detail="commit " + sha[:12],
            evidence={"commit_sha": sha},
            discovered_at="2025-01-01T00:00:00+00:00",
            last_seen_at="2025-01-01T00:00:00+00:00",
            actionable=False, actionable_reason="commit_context_only",
        )])
        return cid

    def _find(self, fid):
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        return {f["finding_id"]: f for f in findings}.get(fid)

    def test_tried_survives_rediscovery(self):
        cid = self._seed_commit_with_status("tried")
        _run_discover(self.target, self.bindir)
        rec = self._find(cid)
        self.assertIsNotNone(rec, "re-observed tried finding was dropped")
        self.assertEqual(rec["status"], "tried", "tried was reset to open")

    def test_passed_survives_rediscovery(self):
        cid = self._seed_commit_with_status("passed")
        _run_discover(self.target, self.bindir)
        self.assertEqual(self._find(cid)["status"], "passed")

    def test_skipped_survives_rediscovery(self):
        cid = self._seed_commit_with_status("skipped")
        _run_discover(self.target, self.bindir)
        self.assertEqual(self._find(cid)["status"], "skipped")

    def test_discovered_at_preserved_last_seen_refreshes_on_resume(self):
        cid = self._seed_commit_with_status("tried")
        _run_discover(self.target, self.bindir)
        rec = self._find(cid)
        self.assertEqual(rec["discovered_at"], "2025-01-01T00:00:00+00:00")
        self.assertNotEqual(rec["last_seen_at"], "2025-01-01T00:00:00+00:00")

    def test_tried_not_auto_redispatched(self):
        # 011-02 never transitions tried→anything and never increments attempts;
        # a recurring tried finding stays tried with its attempts unchanged.
        cid = self._seed_commit_with_status("tried")
        _run_discover(self.target, self.bindir)
        _run_discover(self.target, self.bindir)
        rec = self._find(cid)
        self.assertEqual(rec["status"], "tried")
        self.assertEqual(rec["attempts"], 1, "011-02 must not increment attempts")


# ===========================================================================
# 011-02 AC5 — Retention bound (uniform, all sources)
# ===========================================================================


class RetentionTests(unittest.TestCase):
    """011-02 AC5 — open-unseen evicted; lifecycle-bearing retained forever."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-v2-ac5-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def _ids(self):
        return {f["finding_id"]
                for f in _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")}

    def test_open_unseen_is_evicted(self):
        # Seed an OPEN finding whose id will NOT be produced by discovery, then
        # run discover: it is unseen this pass and must be evicted.
        ghost = "ffffffffffffffff"
        _write_inbox(self.target, [_v2_record(
            finding_id=ghost, source="commit", status="open",
            evidence={"commit_sha": "ff" * 8},
        )])
        _run_discover(self.target, self.bindir)
        self.assertNotIn(ghost, self._ids(), "stale open finding was not evicted")

    def test_lifecycle_finding_retained_when_signal_gone(self):
        # A tried/passed/skipped finding whose signal has disappeared is kept as
        # an audit trail — even though it is unseen this pass.
        for status in ("tried", "passed", "skipped"):
            ghost = ("a" if status == "tried" else
                     "b" if status == "passed" else "c") * 16
            _write_inbox(self.target, [_v2_record(
                finding_id=ghost, source="commit", status=status, attempts=1,
                evidence={"commit_sha": "dd" * 8},
            )])
            _run_discover(self.target, self.bindir)
            self.assertIn(ghost, self._ids(),
                          f"{status} finding must be retained when signal gone")

    def test_open_reobserved_is_kept(self):
        # An OPEN finding that IS re-observed this pass stays (the routine case).
        sha = GIT_COMMITS[0][0]
        cid = hashlib.sha256(("commit|" + sha).encode()).hexdigest()[:16]
        _write_inbox(self.target, [_v2_record(
            finding_id=cid, source="commit", status="open",
            evidence={"commit_sha": sha},
        )])
        _run_discover(self.target, self.bindir)
        self.assertIn(cid, self._ids())

    def test_uniform_rule_across_sources(self):
        # A stale OPEN finding from each source is evicted by the same rule.
        _write_inbox(self.target, [
            _v2_record(finding_id="c1" * 8, source="ci", status="open"),
            _v2_record(finding_id="15" * 8, source="issue", status="open",
                       provenance="contributor"),
            _v2_record(finding_id="c0" * 8, source="commit", status="open",
                       provenance="contributor"),
        ])
        _run_discover(self.target, self.bindir)
        ids = self._ids()
        for ghost in ("c1" * 8, "15" * 8, "c0" * 8):
            self.assertNotIn(ghost, ids)


# ===========================================================================
# 011-02 AC6 — Actionability classification (deterministic, recomputed)
# ===========================================================================


class ActionabilityClassificationTests(unittest.TestCase):
    """011-02 AC6 — per-source actionable + actionable_reason heuristic."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-v2-ac6-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"

    def tearDown(self):
        self.tmp.cleanup()

    def _discover_findings(self):
        _run_discover(self.target, self.bindir)
        return _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")

    def test_ci_default_branch_push_is_actionable(self):
        # GH_RUN_LIST_JSON run #1: workflow CI, branch main, event push.
        # default branch resolves to main via gh repo view → actionable.
        _make_mock_gh(self.bindir, default_branch="main")
        _make_mock_git(self.bindir)
        ci = [f for f in self._discover_findings() if f["source"] == "ci"]
        on_main = [f for f in ci if f["evidence"].get("branch") == "main"]
        self.assertTrue(on_main, "expected a CI finding on main")
        for f in on_main:
            self.assertTrue(f["actionable"])
            self.assertEqual(f["actionable_reason"], "ci_default_branch")

    def test_ci_non_default_branch_not_actionable(self):
        # run #2: branch release, event schedule → not actionable (wrong branch).
        _make_mock_gh(self.bindir, default_branch="main")
        _make_mock_git(self.bindir)
        ci = [f for f in self._discover_findings() if f["source"] == "ci"]
        on_release = [f for f in ci if f["evidence"].get("branch") == "release"]
        self.assertTrue(on_release)
        for f in on_release:
            self.assertFalse(f["actionable"])
            self.assertEqual(f["actionable_reason"], "ci_non_default_branch")

    def test_ci_pull_request_event_not_actionable(self):
        # A pull_request run on the default branch is still NOT actionable
        # (someone's in-progress PR). The disqualifier is the EVENT, not the
        # branch — the reason must name the event, even though headBranch==main.
        pr_run = json.dumps([{
            "workflowName": "CI", "headBranch": "main", "conclusion": "failure",
            "url": "https://github.com/o/r/actions/runs/900",
            "displayTitle": "pr build", "event": "pull_request",
            "createdAt": "2026-06-10T09:00:00Z",
        }])
        _make_mock_gh(self.bindir, run_list_json=pr_run, default_branch="main")
        _make_mock_git(self.bindir)
        ci = [f for f in self._discover_findings() if f["source"] == "ci"]
        self.assertTrue(ci)
        for f in ci:
            self.assertFalse(f["actionable"], "pull_request run must not be actionable")
            self.assertEqual(f["actionable_reason"], "ci_non_actionable_event")

    def test_ci_non_actionable_event_takes_precedence_over_branch(self):
        # Both gates fail: a pull_request event AND a non-default branch. The
        # event gate is checked first, so the reason names the event — not the
        # branch — because a PR run is non-actionable regardless of its branch.
        pr_run = json.dumps([{
            "workflowName": "CI", "headBranch": "feature-x", "conclusion": "failure",
            "url": "https://github.com/o/r/actions/runs/903",
            "displayTitle": "pr build", "event": "pull_request",
            "createdAt": "2026-06-10T09:00:00Z",
        }])
        _make_mock_gh(self.bindir, run_list_json=pr_run, default_branch="main")
        _make_mock_git(self.bindir)
        ci = [f for f in self._discover_findings() if f["source"] == "ci"]
        self.assertTrue(ci)
        for f in ci:
            self.assertFalse(f["actionable"])
            self.assertEqual(f["actionable_reason"], "ci_non_actionable_event")

    def test_ci_default_branch_unknown_not_actionable(self):
        # gh repo view fails AND git symbolic-ref fails AND the branch is neither
        # main nor master → unknown ⇒ not actionable (fail toward not spending).
        odd_run = json.dumps([{
            "workflowName": "CI", "headBranch": "weird-branch",
            "conclusion": "failure", "url": "https://github.com/o/r/actions/runs/901",
            "displayTitle": "x", "event": "push", "createdAt": "2026-06-10T09:00:00Z",
        }])
        _make_mock_gh(self.bindir, run_list_json=odd_run, repo_view_fail=True)
        _make_mock_git(self.bindir, symbolic_ref_branch=None)
        ci = [f for f in self._discover_findings() if f["source"] == "ci"]
        self.assertTrue(ci)
        for f in ci:
            self.assertFalse(f["actionable"])
            self.assertEqual(f["actionable_reason"], "ci_default_branch_unknown")

    def test_ci_default_branch_via_symbolic_ref_fallback(self):
        # gh repo view fails, but git symbolic-ref resolves origin/main → the run
        # on main is actionable through the second-tier fallback.
        _make_mock_gh(self.bindir, repo_view_fail=True)
        _make_mock_git(self.bindir, symbolic_ref_branch="main")
        ci = [f for f in self._discover_findings() if f["source"] == "ci"]
        on_main = [f for f in ci if f["evidence"].get("branch") == "main"]
        self.assertTrue(on_main)
        for f in on_main:
            self.assertTrue(f["actionable"])
            self.assertEqual(f["actionable_reason"], "ci_default_branch")

    def test_ci_default_branch_via_master_heuristic(self):
        # gh + symbolic-ref both fail; branch is "master" → the main/master
        # heuristic resolves it as the default branch.
        master_run = json.dumps([{
            "workflowName": "CI", "headBranch": "master", "conclusion": "failure",
            "url": "https://github.com/o/r/actions/runs/902", "displayTitle": "x",
            "event": "push", "createdAt": "2026-06-10T09:00:00Z",
        }])
        _make_mock_gh(self.bindir, run_list_json=master_run, repo_view_fail=True)
        _make_mock_git(self.bindir, symbolic_ref_branch=None)
        ci = [f for f in self._discover_findings() if f["source"] == "ci"]
        self.assertTrue(ci)
        for f in ci:
            self.assertTrue(f["actionable"])
            self.assertEqual(f["actionable_reason"], "ci_default_branch")

    def test_issue_open_is_actionable(self):
        _make_mock_gh(self.bindir)  # default GH_ISSUE_LIST_JSON: bug/none/docs
        _make_mock_git(self.bindir)
        issues = [f for f in self._discover_findings() if f["source"] == "issue"]
        self.assertTrue(issues)
        for f in issues:
            self.assertTrue(f["actionable"])
            self.assertEqual(f["actionable_reason"], "issue_open")

    def test_issue_non_actionable_label(self):
        labeled = json.dumps([
            {"number": 201, "title": "won't do", "body": "",
             "state": "OPEN", "url": "https://github.com/o/r/issues/201",
             "labels": [{"name": "wontfix"}]},
            {"number": 202, "title": "dup", "body": "",
             "state": "OPEN", "url": "https://github.com/o/r/issues/202",
             "labels": [{"name": "Duplicate"}]},  # case-insensitive match
        ])
        _make_mock_gh(self.bindir, issue_list_json=labeled)
        _make_mock_git(self.bindir)
        issues = {f["evidence"]["issue_number"]: f
                  for f in self._discover_findings() if f["source"] == "issue"}
        self.assertFalse(issues[201]["actionable"])
        self.assertEqual(issues[201]["actionable_reason"], "issue_label_wontfix")
        self.assertFalse(issues[202]["actionable"])
        self.assertEqual(issues[202]["actionable_reason"], "issue_label_duplicate")

    def test_commit_always_context_only(self):
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)
        commits = [f for f in self._discover_findings() if f["source"] == "commit"]
        self.assertTrue(commits)
        for f in commits:
            self.assertFalse(f["actionable"])
            self.assertEqual(f["actionable_reason"], "commit_context_only")

    def test_actionability_recomputed_each_pass(self):
        # A finding seeded non-actionable on a wrong-branch CI id flips to
        # actionable once discovery sees it on the default branch — actionable is
        # recomputed, not sticky.
        ci_id = hashlib.sha256(b"ci|CI|main").hexdigest()[:16]
        _write_inbox(self.target, [_v2_record(
            finding_id=ci_id, source="ci", status="open",
            actionable=False, actionable_reason="ci_non_default_branch",
            evidence={"branch": "main", "workflow": "CI"},
        )])
        _make_mock_gh(self.bindir, default_branch="main")
        _make_mock_git(self.bindir)
        rec = {f["finding_id"]: f
               for f in self._discover_findings()}[ci_id]
        self.assertTrue(rec["actionable"], "actionable must be recomputed each pass")
        self.assertEqual(rec["actionable_reason"], "ci_default_branch")


# ===========================================================================
# 011-02 AC7 — Immutable provenance marker (Guardrail #4)
# ===========================================================================


class ProvenanceMarkerTests(unittest.TestCase):
    """011-02 AC7 — provenance is first_party for ci, contributor for issue/commit."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-v2-ac7-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_provenance_per_source(self):
        _run_discover(self.target, self.bindir)
        for f in _read_jsonl(_triage_dir(self.target) / "inbox.jsonl"):
            if f["source"] == "ci":
                self.assertEqual(f["provenance"], "first_party")
            else:
                self.assertEqual(f["provenance"], "contributor")

    def test_provenance_immutable_across_merge(self):
        # Even a (corruptly) mis-seeded provenance is restored to the source-
        # derived fact on the next discover — provenance is a function of source,
        # not a stored mutable value that drifts.
        ci_id = hashlib.sha256(b"ci|CI|main").hexdigest()[:16]
        _write_inbox(self.target, [_v2_record(
            finding_id=ci_id, source="ci", provenance="contributor",
            status="tried", attempts=1, evidence={"branch": "main", "workflow": "CI"},
        )])
        _run_discover(self.target, self.bindir)
        rec = {f["finding_id"]: f
               for f in _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")}[ci_id]
        self.assertEqual(rec["provenance"], "first_party",
                         "provenance must be re-derived from source, immutable")
        # And the sticky status was still preserved through the same merge.
        self.assertEqual(rec["status"], "tried")


# ===========================================================================
# 011-02 AC8 — Double-fire concurrency safety (advisory flock)
# ===========================================================================


class ConcurrencyLockTests(unittest.TestCase):
    """011-02 AC8 — flock on a persistent .inbox.lock; contention → exit 0."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-v2-ac8-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def _lock_path(self):
        return _triage_dir(self.target) / ".inbox.lock"

    def test_lock_file_created_and_persists(self):
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        # The lock file is a persistent target — present after a successful run,
        # never unlinked.
        self.assertTrue(self._lock_path().exists(),
                        ".inbox.lock must be created and persist")

    def test_lock_file_not_unlinked_across_runs(self):
        _run_discover(self.target, self.bindir)
        lock = self._lock_path()
        self.assertTrue(lock.exists())
        ino_first = lock.stat().st_ino
        _run_discover(self.target, self.bindir)
        self.assertTrue(lock.exists(), ".inbox.lock was unlinked between runs")
        # Same inode — the lock target was reused, not recreated (recreating it
        # would race the flock per ADR-0010).
        self.assertEqual(lock.stat().st_ino, ino_first,
                         ".inbox.lock inode changed — it was recreated, racing flock")

    def test_contention_exits_zero_with_breadcrumb(self):
        # Hold the advisory lock from the test process, then run discover: it
        # must observe contention (LOCK_NB), emit a `lock_contended` breadcrumb,
        # and exit 0 (the other run is maintaining the inbox).
        import fcntl
        # Pre-create the triage dir + lock file so we can grab the lock first.
        triage = _triage_dir(self.target)
        triage.mkdir(parents=True, exist_ok=True)
        lock = self._lock_path()
        fd = os.open(str(lock), os.O_CREAT | os.O_RDWR, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            res = _run_discover(self.target, self.bindir)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("lock_contended", res.stderr)

    def test_contention_does_not_overwrite_inbox(self):
        # Seed an inbox, hold the lock, run discover → it refuses (exit 0) and
        # leaves the existing inbox untouched (the held run owns it).
        import fcntl
        seeded = [_v2_record(finding_id="seed000000000000", status="tried",
                             evidence={"commit_sha": "ab" * 8})]
        _write_inbox(self.target, seeded)
        before = (_triage_dir(self.target) / "inbox.jsonl").read_bytes()
        lock = self._lock_path()
        fd = os.open(str(lock), os.O_CREAT | os.O_RDWR, 0o600)
        self.addCleanup(os.close, fd)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            res = _run_discover(self.target, self.bindir)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
        self.assertEqual(res.returncode, 0)
        after = (_triage_dir(self.target) / "inbox.jsonl").read_bytes()
        self.assertEqual(before, after, "contended run must not touch the inbox")

    def test_no_tmp_left_behind_on_success(self):
        _run_discover(self.target, self.bindir)
        leftovers = list(_triage_dir(self.target).glob("*.tmp"))
        self.assertEqual(leftovers, [], f"orphaned .tmp staging files: {leftovers}")

    def test_uses_flock_and_separate_lock_file(self):
        text = HEARTBEAT.read_text()
        self.assertIn("flock", text, "must use fcntl.flock for double-fire safety")
        self.assertIn("LOCK_EX", text)
        self.assertIn("LOCK_NB", text)
        self.assertIn(".inbox.lock", text, "must lock a separate .inbox.lock file")
        # Must NEVER unlink the lock file (unlinking races the flock).
        self.assertNotRegex(
            text, r"\.inbox\.lock['\"]?\s*\)?\.unlink",
            "the .inbox.lock file must never be unlinked",
        )


# ===========================================================================
# 011-02 AC9 — `heartbeat.py status` subcommand (read-only read-back)
# ===========================================================================


class StatusSubcommandTests(unittest.TestCase):
    """011-02 AC9 — status reads the inbox; human default + --json; closed {0,2}."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-v2-ac9-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_status_human_summary_after_discover(self):
        _run_discover(self.target, self.bindir)
        res = _run_status(self.target)
        self.assertEqual(res.returncode, 0, res.stderr)
        out = res.stdout
        # Counts by status, source, actionability are all surfaced.
        self.assertRegex(out, r"(?i)open")
        for src in ("ci", "issue", "commit"):
            self.assertRegex(out, rf"(?i){src}")
        self.assertRegex(out, r"(?i)actionable")

    def test_status_lists_open_actionable_candidates_with_last_seen(self):
        _run_discover(self.target, self.bindir)
        res = _run_status(self.target)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        # At least one open-actionable candidate (CI on main) exists; its
        # last_seen_at should appear in the candidate listing.
        candidates = [f for f in findings if f["status"] == "open" and f["actionable"]]
        self.assertTrue(candidates)
        # The candidate's last_seen_at timestamp shows up in the human output.
        self.assertTrue(
            any(c["last_seen_at"] in res.stdout for c in candidates),
            "open-actionable candidate's last_seen_at not shown",
        )

    def test_status_json_carries_schema_version(self):
        _run_discover(self.target, self.bindir)
        res = _run_status(self.target, as_json=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        payload = json.loads(res.stdout)
        self.assertEqual(payload["schema_version"], 2)
        # Machine summary carries the by-status / by-source / actionable counts.
        self.assertIn("counts", payload)

    def test_status_empty_inbox_exits_zero(self):
        # An empty (but present) inbox reads OK.
        _write_inbox(self.target, [])
        res = _run_status(self.target)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_status_absent_inbox_exits_zero(self):
        # No discover has run; the inbox is absent → still read OK (rc 0).
        res = _run_status(self.target)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_status_missing_target_exits_two(self):
        res = _run_status(self.root / "nope")
        self.assertEqual(res.returncode, 2)

    def test_status_never_exits_one(self):
        _run_discover(self.target, self.bindir)
        for as_json in (False, True):
            res = _run_status(self.target, as_json=as_json)
            self.assertNotEqual(res.returncode, 1)
            self.assertIn(res.returncode, (0, 2))

    def test_status_is_read_only(self):
        _run_discover(self.target, self.bindir)
        before = _snapshot_tree(self.target, exclude_rel="__none__")
        _run_status(self.target)
        _run_status(self.target, as_json=True)
        after = _snapshot_tree(self.target, exclude_rel="__none__")
        self.assertEqual(before, after, "status must not mutate anything")

    def test_status_does_not_shell_out(self):
        # status reads only the inbox file; with NO gh/git on PATH it must still
        # succeed (it never invokes a subprocess).
        _run_discover(self.target, self.bindir)
        empty_bin = self.root / "emptybin"
        empty_bin.mkdir()
        res = _run_status(self.target, empty_bin)
        self.assertEqual(res.returncode, 0, res.stderr)


# ===========================================================================
# 011-02 AC10 — Schema migration (two rules: discover discards <2, status warns/refuses)
# ===========================================================================


class SchemaMigrationTests(unittest.TestCase):
    """011-02 AC10 — discover drops <v2 + rebuilds; status warns-lower/refuses-higher."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-v2-ac10-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_discover_drops_v1_and_rebuilds(self):
        # Seed a legacy v1 record (the 011-01 shape: no sticky lifecycle) with a
        # finding_id that discovery will NOT reproduce. discover discards it and
        # rebuilds from live signals → the v1 id is gone, v2 ids present.
        v1 = {
            "schema_version": 1, "finding_id": "1111111111111111",
            "source": "commit", "title": "old", "detail": "",
            "evidence": {"commit_sha": "11" * 8},
            "discovered_at": "2025-01-01T00:00:00+00:00", "status": "open",
        }
        _write_inbox(self.target, [v1])
        res = _run_discover(self.target, self.bindir)
        self.assertEqual(res.returncode, 0, res.stderr)
        findings = _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")
        ids = {f["finding_id"] for f in findings}
        self.assertNotIn("1111111111111111", ids, "v1 record was not discarded")
        # All surviving records are v2.
        self.assertEqual({f["schema_version"] for f in findings}, {2})

    def test_discover_writes_v2_over_v1_inbox(self):
        # Even when a v1 finding_id WOULD collide with a discovered one, the
        # rewrite is clean v2 — a v1 record contributes no sticky state to merge
        # (lossless discard, per ADR-0010). Seed a v1 commit matching GIT_COMMITS.
        sha = GIT_COMMITS[0][0]
        cid = hashlib.sha256(("commit|" + sha).encode()).hexdigest()[:16]
        v1 = {
            "schema_version": 1, "finding_id": cid, "source": "commit",
            "title": "old", "detail": "", "evidence": {"commit_sha": sha},
            "discovered_at": "2025-01-01T00:00:00+00:00", "status": "open",
        }
        _write_inbox(self.target, [v1])
        _run_discover(self.target, self.bindir)
        rec = {f["finding_id"]: f
               for f in _read_jsonl(_triage_dir(self.target) / "inbox.jsonl")}[cid]
        self.assertEqual(rec["schema_version"], 2)
        # discovered_at is re-derived (a v1 record's first-seen is not trusted as
        # v2 sticky state), so it is the fresh pass time, not 2025.
        self.assertNotEqual(rec["discovered_at"], "2025-01-01T00:00:00+00:00")

    def test_status_warns_and_displays_lower_version(self):
        v1 = {
            "schema_version": 1, "finding_id": "2222222222222222",
            "source": "issue", "title": "legacy issue", "detail": "",
            "evidence": {"issue_number": 9, "url": "u"},
            "discovered_at": "2025-01-01T00:00:00+00:00", "status": "open",
        }
        _write_inbox(self.target, [v1])
        res = _run_status(self.target)
        # Best-effort display of a lower known version: exit 0 + a warning.
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertRegex(res.stderr, r"(?i)schema_version|version")

    def test_status_refuses_higher_version(self):
        future = _v2_record(finding_id="3333333333333333", schema_version=99)
        _write_inbox(self.target, [future])
        res = _run_status(self.target)
        self.assertEqual(res.returncode, 2)
        self.assertIn("schema_version_unsupported", res.stderr)

    def test_status_json_also_refuses_higher_version(self):
        future = _v2_record(finding_id="4444444444444444", schema_version=99)
        _write_inbox(self.target, [future])
        res = _run_status(self.target, as_json=True)
        self.assertEqual(res.returncode, 2)


# ===========================================================================
# 011-02 AC11 — view extended (status + actionable/reason + lifecycle summary)
# ===========================================================================


GENERATED_MARKER_TEXT = "<!-- generated by heartbeat.py — do not hand-edit -->"


class HumanViewV2Tests(unittest.TestCase):
    """011-02 AC11 — inbox.md surfaces status, actionable/reason, lifecycle summary.

    (Extends the 011-01 HumanViewTests; the generated-marker + per-source health
    header regressions stay asserted there.)
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="servo-hb-v2-ac11-")
        self.root = Path(self.tmp.name)
        self.target = self.root / "demo"
        self.target.mkdir()
        _make_oracle_and_manifest(self.target)
        self.bindir = self.root / "bin"
        _make_mock_gh(self.bindir)
        _make_mock_git(self.bindir)
        _run_discover(self.target, self.bindir)
        self.md = (_triage_dir(self.target) / "inbox.md").read_text()

    def tearDown(self):
        self.tmp.cleanup()

    def test_marker_still_present(self):
        self.assertIn(GENERATED_MARKER_TEXT, self.md)

    def test_shows_actionable_reason(self):
        # A machine reason code should be surfaced for review.
        self.assertTrue(
            "ci_default_branch" in self.md
            or "commit_context_only" in self.md
            or "issue_open" in self.md,
            "inbox.md surfaces no actionable_reason",
        )

    def test_lifecycle_summary_counts_by_status(self):
        # A lifecycle summary (counts by status) appears in the view.
        self.assertRegex(self.md, r"(?i)open")
        # Nine fresh findings → an open count of 9 is shown somewhere.
        self.assertRegex(self.md, r"9")

    def test_each_finding_shows_actionable_flag(self):
        # The actionable verdict is visible per finding (true/false/yes/no).
        self.assertRegex(self.md, r"(?i)actionable")


if __name__ == "__main__":
    unittest.main()
