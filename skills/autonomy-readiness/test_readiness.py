"""
Behavior tests for `/servo:autonomy-readiness` — slice 023-01.

One class per acceptance-criterion area (AC1..AC6). All subprocess seams
(`claude`, `gh`) are served from bash shadow scripts selected by env-var
override — never a live binary. Run via unittest or pytest:

    python3 skills/autonomy-readiness/test_readiness.py
    python3 -m pytest skills/autonomy-readiness/test_readiness.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
READINESS = REPO_ROOT / "skills" / "autonomy-readiness" / "readiness.py"
EXAMPLES = REPO_ROOT / "skills" / "autonomy-readiness" / "examples"

CLAUDE_BIN_ENV = "SERVO_AUTONOMY_READINESS_CLAUDE_BIN"
GH_BIN_ENV = "SERVO_AUTONOMY_READINESS_GH_BIN"


def _load_readiness():
    spec = importlib.util.spec_from_file_location("readiness", READINESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Mock subprocess seams
# ---------------------------------------------------------------------------

def _claude_envelope(result_text: str) -> str:
    return json.dumps({"type": "result", "is_error": False, "result": result_text})


def _all_ok_scores() -> str:
    return _claude_envelope(json.dumps({"scores": [
        {"dimension": d, "status": "ok", "note": "fine"}
        for d in ("precision", "scope", "stop_conditions",
                  "safety_surface", "contradiction")
    ]}))


def _no_flags() -> str:
    return _claude_envelope(json.dumps({"flags": []}))


def _make_mock_claude(bindir: Path, replies: list) -> Path:
    """A `claude` shadow that emits `replies[n-1]` (a full envelope, already
    JSON-encoded) on its n-th call, and records the prompt it received (the
    final argv) to `prompt-$n.txt` so a test can assert what each call saw."""
    bindir.mkdir(parents=True, exist_ok=True)
    for i, reply in enumerate(replies, start=1):
        (bindir / f"reply-{i}.json").write_text(reply)
    counter = bindir / "counter.txt"
    body = textwrap.dedent(f"""\
        #!/usr/bin/env bash
        counter='{counter}'
        if [ -f "$counter" ]; then n=$(cat "$counter"); else n=0; fi
        n=$((n + 1))
        echo "$n" > "$counter"
        # The prompt is the final argument.
        printf '%s' "${{@: -1}}" > '{bindir}/prompt-'"$n"'.txt'
        cat '{bindir}/reply-'"$n"'.json'
    """)
    claude = bindir / "claude"
    claude.write_text(body)
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return claude


def _make_mock_gh(bindir: Path, viewer_permission: str, *, fail: bool = False) -> Path:
    bindir.mkdir(parents=True, exist_ok=True)
    if fail:
        body = "#!/usr/bin/env bash\nexit 1\n"
    else:
        payload = json.dumps({"viewerPermission": viewer_permission})
        body = f"#!/usr/bin/env bash\ncat <<'EOF'\n{payload}\nEOF\n"
    gh = bindir / "gh"
    gh.write_text(body)
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return gh


# ---------------------------------------------------------------------------
# Target fixtures
# ---------------------------------------------------------------------------

def _git_init(target: Path) -> None:
    for args in (["init", "-q"], ["config", "user.email", "t@e.st"],
                 ["config", "user.name", "t"], ["add", "-A"],
                 ["commit", "-q", "-m", "init"]):
        subprocess.run(["git", "-C", str(target), *args],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _make_perimeter(root: Path) -> Path:
    p = root / "perimeter.json"
    p.write_text(json.dumps({"allow": ["src/**"], "protected": [".git/**"]}))
    return p


def _good_target(root: Path) -> Path:
    """A fully-ready target: executable oracle, an approved component, a clean
    git tree. Callers add the finite caps + perimeter via CLI args and break a
    single precondition to test each toggle."""
    target = root / "target"
    (target / ".servo" / "spec-oracles" / "demo").mkdir(parents=True)
    (target / ".servo" / "spec-oracles" / "demo" / "plan.json").write_text(
        json.dumps({"approval_status": "approved"}))
    oracle = target / "oracle.sh"
    oracle.write_text("#!/usr/bin/env bash\nexit 0\n")
    oracle.chmod(oracle.stat().st_mode | stat.S_IXUSR)
    _git_init(target)
    return target


def _run_cli(*args, claude_bin=None, gh_bin=None, home=None, extra_env=None):
    env = dict(os.environ)
    env.pop(CLAUDE_BIN_ENV, None)
    env.pop(GH_BIN_ENV, None)
    if claude_bin is not None:
        env[CLAUDE_BIN_ENV] = str(claude_bin)
    if gh_bin is not None:
        env[GH_BIN_ENV] = str(gh_bin)
    if home is not None:
        env["HOME"] = str(home)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(READINESS), *args],
        capture_output=True, text=True, env=env,
    )


def _ready_args(target: Path, perimeter: Path, brief: str) -> list:
    return [
        "analyze", str(target), "--prompt", brief,
        "--cost-ceiling", "5.0", "--max-iterations", "20",
        "--max-candidates", "3", "--mutation-perimeter", str(perimeter),
        "--json",
    ]


READY_BRIEF = "Add a bounded --timeout flag to loop.py with a passing test; out "\
    "of scope: heartbeat; stop when the test is green; touches no secrets."


# ---------------------------------------------------------------------------
# AC1 — three-state verdict + atomic artifact + exit codes + --json
# ---------------------------------------------------------------------------

class VerdictAndArtifactTests(unittest.TestCase):
    def _analyze_json(self, target, perimeter, brief, *, replies, home,
                      gh_bin=None, extra=()):
        with tempfile.TemporaryDirectory() as bd:
            claude = _make_mock_claude(Path(bd), replies)
            res = _run_cli(*_ready_args(target, perimeter, brief), *extra,
                           claude_bin=claude, gh_bin=gh_bin, home=home)
        return res

    def test_ready_verdict_reachable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = _good_target(root)
            perimeter = _make_perimeter(root)
            res = self._analyze_json(
                target, perimeter, READY_BRIEF,
                replies=[_all_ok_scores(), _no_flags()], home=home)
            self.assertEqual(res.returncode, 0, res.stderr)
            obj = json.loads(res.stdout)
            self.assertEqual(obj["verdict"], "ready")
            self.assertEqual(obj["approval_status"], "proposed")
            # Artifact written atomically at the goal-id path.
            art = target / ".servo" / "readiness" / f"{obj['goal_id']}.json"
            self.assertTrue(art.is_file())
            self.assertEqual(json.loads(art.read_text())["verdict"], "ready")

    def test_needs_tightening_reachable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = _good_target(root)
            perimeter = _make_perimeter(root)
            # Model tier flags precision → needs_tightening.
            expansion = _claude_envelope(json.dumps({"scores": [
                {"dimension": "precision", "status": "concern", "note": "vague"},
                {"dimension": "scope", "status": "ok", "note": ""},
                {"dimension": "stop_conditions", "status": "ok", "note": ""},
                {"dimension": "safety_surface", "status": "ok", "note": ""},
                {"dimension": "contradiction", "status": "ok", "note": ""},
            ]}))
            res = self._analyze_json(
                target, perimeter, READY_BRIEF,
                replies=[expansion, _no_flags()], home=home)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(json.loads(res.stdout)["verdict"], "needs_tightening")

    def test_unsafe_verdict_reachable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = _good_target(root)
            perimeter = _make_perimeter(root)
            gh = _make_mock_gh(root / "ghbin", "ADMIN")
            res = self._analyze_json(
                target, perimeter, READY_BRIEF,
                replies=[_all_ok_scores(), _no_flags()], home=home,
                gh_bin=gh, extra=("--declares-autonomous-merge",))
            self.assertEqual(res.returncode, 0, res.stderr)
            obj = json.loads(res.stdout)
            self.assertEqual(obj["verdict"], "unsafe_for_autonomy")

    def test_missing_target_exits_2_not_1(self):
        # An env error (missing target) → 2, never 1. The broader "never 1"
        # invariant on the model path is covered by
        # ModelTierTests.test_malformed_model_reply_is_concern_not_crash.
        res = _run_cli("analyze", "/no/such/target", "--prompt", "x")
        self.assertEqual(res.returncode, 2)


# ---------------------------------------------------------------------------
# AC2 — deterministic tier: each precondition toggles the verdict
# ---------------------------------------------------------------------------

class DeterministicTierTests(unittest.TestCase):
    """Baseline is fully ready; breaking exactly one precondition must flip the
    verdict off `ready` deterministically (the model tier is pinned all-ok)."""

    def _analyze(self, root, target, perimeter, *, home, extra=(), args=None):
        with tempfile.TemporaryDirectory() as bd:
            claude = _make_mock_claude(Path(bd), [_all_ok_scores(), _no_flags()])
            base = args if args is not None else _ready_args(
                target, perimeter, READY_BRIEF)
            res = _run_cli(*base, *extra, claude_bin=claude, home=home)
        return json.loads(res.stdout), res

    def _codes(self, obj):
        return {c["code"] for c in obj["checks"] if c["status"] in ("concern", "unsafe")}

    def test_baseline_is_ready(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            obj, res = self._analyze(root, _good_target(root),
                                     _make_perimeter(root), home=home)
            self.assertEqual(obj["verdict"], "ready", res.stdout)

    def test_missing_or_unexecutable_oracle_downgrades(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = _good_target(root)
            (target / "oracle.sh").chmod(0o644)  # strip the executable bit
            obj, _ = self._analyze(root, target, _make_perimeter(root), home=home)
            self.assertNotEqual(obj["verdict"], "ready")
            self.assertIn("oracle_not_executable", self._codes(obj))

    def test_no_approved_component_downgrades(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = _good_target(root)
            (target / ".servo" / "spec-oracles" / "demo" / "plan.json").write_text(
                json.dumps({"approval_status": "draft"}))
            obj, _ = self._analyze(root, target, _make_perimeter(root), home=home)
            self.assertNotEqual(obj["verdict"], "ready")
            self.assertIn("no_approved_component", self._codes(obj))

    def test_unset_cap_downgrades(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = _good_target(root)
            perimeter = _make_perimeter(root)
            # Omit --cost-ceiling (infinite budget).
            args = ["analyze", str(target), "--prompt", READY_BRIEF,
                    "--max-iterations", "20", "--max-candidates", "3",
                    "--mutation-perimeter", str(perimeter), "--json"]
            obj, _ = self._analyze(root, target, perimeter, home=home, args=args)
            self.assertNotEqual(obj["verdict"], "ready")
            self.assertIn("budget_cap", self._codes(obj))

    def test_dirty_tree_downgrades(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = _good_target(root)
            # Modify a tracked file → dirty tree.
            (target / "oracle.sh").write_text("#!/usr/bin/env bash\nexit 1\n")
            (target / "oracle.sh").chmod(
                (target / "oracle.sh").stat().st_mode | stat.S_IXUSR)
            obj, _ = self._analyze(root, target, _make_perimeter(root), home=home)
            self.assertNotEqual(obj["verdict"], "ready")
            self.assertIn("dirty_tree", self._codes(obj))

    def test_absent_mutation_perimeter_downgrades(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = _good_target(root)
            args = ["analyze", str(target), "--prompt", READY_BRIEF,
                    "--cost-ceiling", "5.0", "--max-iterations", "20",
                    "--max-candidates", "3", "--json"]  # no --mutation-perimeter
            obj, _ = self._analyze(root, target, _make_perimeter(root),
                                   home=home, args=args)
            self.assertNotEqual(obj["verdict"], "ready")
            self.assertIn("no_mutation_perimeter", self._codes(obj))


# ---------------------------------------------------------------------------
# AC3 — identity posture (conditional, best-effort)
# ---------------------------------------------------------------------------

class IdentityPostureTests(unittest.TestCase):
    def _analyze(self, root, target, perimeter, *, home, gh_bin=None, extra=()):
        with tempfile.TemporaryDirectory() as bd:
            claude = _make_mock_claude(Path(bd), [_all_ok_scores(), _no_flags()])
            res = _run_cli(*_ready_args(target, perimeter, READY_BRIEF), *extra,
                           claude_bin=claude, gh_bin=gh_bin, home=home)
        return json.loads(res.stdout)

    def test_single_identity_plus_autonomous_merge_is_unsafe(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            gh = _make_mock_gh(root / "ghbin", "ADMIN")  # can merge
            obj = self._analyze(root, _good_target(root), _make_perimeter(root),
                                home=home, gh_bin=gh,
                                extra=("--declares-autonomous-merge",))
            self.assertEqual(obj["verdict"], "unsafe_for_autonomy")
            collapse = next(c for c in obj["checks"] if c["code"] == "identity_collapse")
            self.assertIn("identity collapse", collapse["message"])

    def test_two_identity_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            gh = _make_mock_gh(root / "ghbin", "READ")  # cannot merge → separated
            obj = self._analyze(root, _good_target(root), _make_perimeter(root),
                                home=home, gh_bin=gh,
                                extra=("--declares-autonomous-merge",))
            self.assertEqual(obj["verdict"], "ready")
            self.assertTrue(any(c["code"] == "identity_separated"
                                for c in obj["checks"]))

    def test_single_identity_without_declaration_is_advisory_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            gh = _make_mock_gh(root / "ghbin", "ADMIN")
            obj = self._analyze(root, _good_target(root), _make_perimeter(root),
                                home=home, gh_bin=gh)  # no --declares flag
            self.assertEqual(obj["verdict"], "ready")
            advisory = next(c for c in obj["checks"] if c["tier"] == "identity")
            self.assertEqual(advisory["status"], "info")

    def test_declared_but_probe_unavailable_is_needs_tightening(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            gh = _make_mock_gh(root / "ghbin", "ADMIN", fail=True)
            obj = self._analyze(root, _good_target(root), _make_perimeter(root),
                                home=home, gh_bin=gh,
                                extra=("--declares-autonomous-merge",))
            self.assertEqual(obj["verdict"], "needs_tightening")
            self.assertTrue(any(c["code"] == "identity_unconfirmed"
                                for c in obj["checks"]))


# ---------------------------------------------------------------------------
# AC4 — model-judged tier (two-call, independence)
# ---------------------------------------------------------------------------

class ModelTierTests(unittest.TestCase):
    def _analyze(self, root, target, perimeter, brief, *, replies, home):
        bd = root / "bd"
        claude = _make_mock_claude(bd, replies)
        res = _run_cli(*_ready_args(target, perimeter, brief),
                       claude_bin=claude, home=home)
        return json.loads(res.stdout), bd

    def test_open_ended_brief_needs_tightening(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            expansion = _claude_envelope(json.dumps({"scores": [
                {"dimension": "precision", "status": "concern", "note": "make it better is vague"},
                {"dimension": "scope", "status": "concern", "note": "no out-of-scope"},
                {"dimension": "stop_conditions", "status": "concern", "note": "no stop"},
                {"dimension": "safety_surface", "status": "ok", "note": ""},
                {"dimension": "contradiction", "status": "ok", "note": ""},
            ]}))
            obj, _ = self._analyze(
                root, _good_target(root), _make_perimeter(root),
                "Make the codebase better.",
                replies=[expansion, _no_flags()], home=home)
            self.assertEqual(obj["verdict"], "needs_tightening")

    def test_secrets_brief_names_safety_surface(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            expansion = _claude_envelope(json.dumps({"scores": [
                {"dimension": "precision", "status": "ok", "note": ""},
                {"dimension": "scope", "status": "ok", "note": ""},
                {"dimension": "stop_conditions", "status": "ok", "note": ""},
                {"dimension": "safety_surface", "status": "concern",
                 "note": "rotates production secrets and deploys — needs a human checkpoint"},
                {"dimension": "contradiction", "status": "ok", "note": ""},
            ]}))
            obj, _ = self._analyze(
                root, _good_target(root), _make_perimeter(root),
                "Rotate production DB credentials and deploy.",
                replies=[expansion, _no_flags()], home=home)
            self.assertIn(obj["verdict"],
                          ("needs_tightening", "unsafe_for_autonomy"))
            self.assertTrue(obj["safety_surface"])
            self.assertIn("secret", " ".join(obj["safety_surface"]).lower())

    def test_malformed_model_reply_is_concern_not_crash(self):
        # A braces-present-but-INVALID model reply (truncated / trailing commas —
        # what LLMs actually emit) must NOT crash analyze with exit 1; it degrades
        # to a fail-closed `model_tier_unavailable` concern → at least
        # needs_tightening. Regression for the 2026-08-06 craft-review blocker.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            # Balanced braces (so _extract_json_object accepts it) but invalid
            # JSON inside (trailing comma) — the exact case the blocker was about.
            malformed = _claude_envelope('{"scores": [1, 2,]}')
            res = _run_cli(
                *_ready_args(_good_target(root), _make_perimeter(root),
                             "A well-scoped, bounded brief."),
                claude_bin=_make_mock_claude(root / "bd", [malformed, _no_flags()]),
                home=home)
            self.assertEqual(res.returncode, 0)  # {0,2} only — NEVER 1
            obj = json.loads(res.stdout)
            self.assertEqual(obj["verdict"], "needs_tightening")
            self.assertIn("model_tier_unavailable",
                          [c["code"] for c in obj["checks"]])

    def test_partial_model_reply_is_concern(self):
        # A reply scoring only some dimensions must fail closed (not silently
        # treat the omitted ones as ok). Craft-review nit, 2026-08-06.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            partial = _claude_envelope(json.dumps({"scores": [
                {"dimension": "precision", "status": "ok", "note": ""},
            ]}))
            res = _run_cli(
                *_ready_args(_good_target(root), _make_perimeter(root),
                             "A well-scoped, bounded brief."),
                claude_bin=_make_mock_claude(root / "bd", [partial, _no_flags()]),
                home=home)
            self.assertEqual(res.returncode, 0)
            obj = json.loads(res.stdout)
            self.assertIn("model_tier_unavailable",
                          [c["code"] for c in obj["checks"]])

    def test_two_calls_and_review_is_independent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            secret_reasoning = "SUPER_SECRET_EXPANSION_REASONING_TOKEN"
            expansion = _claude_envelope(json.dumps({"scores": [
                {"dimension": d2, "status": "ok", "note": secret_reasoning}
                for d2 in ("precision", "scope", "stop_conditions",
                           "safety_surface", "contradiction")
            ]}))
            obj, bd = self._analyze(
                root, _good_target(root), _make_perimeter(root), READY_BRIEF,
                replies=[expansion, _no_flags()], home=home)
            # Exactly two claude calls happened.
            self.assertEqual((bd / "counter.txt").read_text().strip(), "2")
            review_prompt = (bd / "prompt-2.txt").read_text()
            # The review call carries the brief but NOT the expansion's reasoning.
            self.assertIn("Add a bounded --timeout flag", review_prompt)
            self.assertNotIn(secret_reasoning, review_prompt)


# ---------------------------------------------------------------------------
# AC5 — approval + check consumer contract
# ---------------------------------------------------------------------------

class ApprovalAndCheckTests(unittest.TestCase):
    def _analyze_ready(self, root, home, brief=READY_BRIEF, gh_bin=None, extra=(),
                       replies=None):
        target = _good_target(root)
        perimeter = _make_perimeter(root)
        bd = root / f"bd-{len(list(root.iterdir()))}"
        claude = _make_mock_claude(bd, replies or [_all_ok_scores(), _no_flags()])
        res = _run_cli(*_ready_args(target, perimeter, brief), *extra,
                       claude_bin=claude, gh_bin=gh_bin, home=home)
        self.assertEqual(res.returncode, 0, res.stderr)
        return target

    def test_check_refuses_while_proposed_and_permits_after_approve(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = self._analyze_ready(root, home)
            # Proposed → check refuses (exit 1).
            r1 = _run_cli("check", str(target), "--prompt", READY_BRIEF)
            self.assertEqual(r1.returncode, 1, r1.stdout)
            # Approve.
            ra = _run_cli("approve", str(target), "--prompt", READY_BRIEF)
            self.assertEqual(ra.returncode, 0, ra.stderr)
            # Approved → check permits (exit 0).
            r2 = _run_cli("check", str(target), "--prompt", READY_BRIEF)
            self.assertEqual(r2.returncode, 0, r2.stdout)

    def test_check_refuses_when_artifact_missing(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "target"
            target.mkdir()
            r = _run_cli("check", str(target), "--prompt", "never analyzed")
            self.assertEqual(r.returncode, 1)

    def test_artifact_starts_proposed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = self._analyze_ready(root, home)
            gid = _load_readiness()._goal_id(READY_BRIEF)
            art = json.loads(
                (target / ".servo" / "readiness" / f"{gid}.json").read_text())
            self.assertEqual(art["approval_status"], "proposed")
            self.assertIsNone(art["approved_at"])

    def test_approve_stamps_approved_at(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = self._analyze_ready(root, home)
            _run_cli("approve", str(target), "--prompt", READY_BRIEF)
            gid = _load_readiness()._goal_id(READY_BRIEF)
            art = json.loads(
                (target / ".servo" / "readiness" / f"{gid}.json").read_text())
            self.assertEqual(art["approval_status"], "approved")
            self.assertTrue(art["approved_at"])

    def test_approve_refuses_unsafe_verdict(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            gh = _make_mock_gh(root / "ghbin", "ADMIN")
            target = self._analyze_ready(
                root, home, gh_bin=gh, extra=("--declares-autonomous-merge",))
            r = _run_cli("approve", str(target), "--prompt", READY_BRIEF)
            self.assertEqual(r.returncode, 2, r.stdout)
            self.assertIn("unsafe_not_approvable", r.stderr)
            # And check still refuses (never permitted).
            self.assertEqual(
                _run_cli("check", str(target), "--prompt", READY_BRIEF).returncode, 1)

    def test_approve_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            target = self._analyze_ready(root, home)
            _run_cli("approve", str(target), "--prompt", READY_BRIEF)
            r2 = _run_cli("approve", str(target), "--prompt", READY_BRIEF)
            self.assertEqual(r2.returncode, 0, r2.stderr)


# ---------------------------------------------------------------------------
# AC6 — boundary integrity (jig co-install vs built-in rubric, no import)
# ---------------------------------------------------------------------------

class BoundaryIntegrityTests(unittest.TestCase):
    def _seed_jig_clarify(self, home: Path) -> Path:
        skill = home / ".claude" / "skills" / "clarify"
        skill.mkdir(parents=True)
        marker = "JIG_CLARIFY_FRAMING_MARKER"
        (skill / "SKILL.md").write_text(f"---\nname: clarify\n---\n{marker}\n")
        return skill / "SKILL.md"

    def test_co_installed_path_uses_jig_framing(self):
        mod = _load_readiness()
        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / "home"
            self._seed_jig_clarify(home)
            old = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            try:
                path = mod._jig_clarify_skill_path()
                self.assertIsNotNone(path)
                framing = mod._review_framing_text(path)
                self.assertIn("JIG_CLARIFY_FRAMING_MARKER", framing)
            finally:
                if old is not None:
                    os.environ["HOME"] = old

    def test_standalone_path_uses_builtin_rubric_and_does_not_error(self):
        mod = _load_readiness()
        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / "home"
            home.mkdir()
            old = os.environ.get("HOME")
            os.environ["HOME"] = str(home)
            try:
                self.assertIsNone(mod._jig_clarify_skill_path())
                framing = mod._review_framing_text(None)
                self.assertIn("Autonomy-readiness rubric", framing)
            finally:
                if old is not None:
                    os.environ["HOME"] = old

    def test_end_to_end_standalone_runs_without_jig(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()  # no jig skill under it
            target = _good_target(root)
            perimeter = _make_perimeter(root)
            bd = root / "bd"
            claude = _make_mock_claude(bd, [_all_ok_scores(), _no_flags()])
            res = _run_cli(*_ready_args(target, perimeter, READY_BRIEF),
                           claude_bin=claude, home=home)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(json.loads(res.stdout)["verdict"], "ready")

    def test_no_servo_to_jig_python_import(self):
        source = READINESS.read_text()
        lowered = source.lower()
        # No import-level coupling to jig at all.
        self.assertNotIn("import jig", lowered)
        self.assertNotIn("from jig", lowered)


if __name__ == "__main__":
    unittest.main()
