"""
servo spec-oracle — slice 006-02 (check-library)

The deterministic, stdlib-only check *engine*. It reads a `checks.json` plan
(the artifact slice 006-01 produces, elaborated with per-family executable
fields) and runs each check through a family primitive, emitting one JSONL
evidence record per acceptance criterion plus a composite summary score.

Usage:
    python3 checks.py <checks.json> [--base-dir DIR] [--ledger PATH]

        Run every check in the plan against the target rooted at DIR (paths in
        the plan resolve relative to DIR). Without --base-dir the target root
        is derived from the canonical
        `<target>/.servo/spec-oracles/<id>/checks.json` location, else the cwd.

        Evidence is one JSON object per line. Without --ledger, evidence and a
        final summary object are written to stdout (distinguish them by the
        `kind` field: "evidence" vs "summary"). With --ledger, evidence rows
        are appended to that file and only the summary is printed to stdout.

        Exit code: 2 if any check env-errored, 1 if any check failed, else 0.
        This mirrors servo's existing "env error == exit 2" convention so the
        engine composes with `gate.py` / `loop.py` (wired up in slice 006-03).

Check families (slice 006-02 AC1)
---------------------------------
`command`, `file_presence`, `text_invariant`, `json_contract`,
`archive_inventory`, `markdown_links`, `generated_artifact_command`,
`runtime_reference_scan`. `residual_judgment` is always `not_applicable`
(it is explicitly non-deterministic in v1).

Status semantics
----------------
A primitive returns:
  - `pass`           — the asserted condition held;
  - `fail`           — the target exists/ran and the asserted condition was
                       violated (the message names the offending
                       path/command/key, AC4);
  - `env_error`      — the check could not be evaluated (target missing or
                       unreadable, malformed check spec, command not found,
                       timeout) — this is the signal that becomes exit 2;
  - `not_applicable` — residual-judgment ACs.

Existence is asserted *only* by `file_presence`; every other primitive
env-errors on a missing target rather than guessing. The one nuance:
`json_contract` treats an existing-but-unparseable file as `fail` (because
"is valid JSON" is itself an assertable contract), but a missing file as
`env_error`.

Score (AC3)
-----------
`D = passed + failed`. `score = passed / D` when `D > 0`; otherwise `0.0` if
anything env-errored (nothing could be established) and `1.0` if the only
records were `not_applicable` (nothing to prove deterministically, nothing
failed). `env_error` and `not_applicable` records never enter the
denominator — env errors are surfaced separately (and as exit 2), and
judgment ACs must not dilute the deterministic score. The policy for whether
unresolved residual judgment may *block* a perfect report is deferred to
slice 006-04 (freeze-and-controls).

Security / safety
-----------------
Commands run via argv lists, never `shell=True`; a string command is
`shlex.split` (no shell metacharacter expansion). Commands run in their own
process group under a bounded timeout (SIGTERM → grace → SIGKILL), mirroring
`gate.py` (slice 002-04). `checks.json` is a reviewed, frozen artifact (slice
006-04), so the engine trusts the commands it is told to run; it adds no
network access of its own.

Python stdlib only (AC5).
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

EVIDENCE_SCHEMA_VERSION = 1
RUNNER_VERSION = "0.1.0"

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_ENV_ERROR = "env_error"
STATUS_NA = "not_applicable"

# Bounded command execution (mirrors gate.py slice 002-04).
DEFAULT_TIMEOUT_SECONDS = 120.0
_TIMEOUT_ENV_VAR = "SERVO_CHECK_TIMEOUT"
_KILL_GRACE_SECONDS = 5.0

# The eight deterministic families (spec "Check families" table). Populated
# into DISPATCH at the bottom of the module once the handlers are defined.
FAMILIES = (
    "command",
    "file_presence",
    "text_invariant",
    "json_contract",
    "archive_inventory",
    "markdown_links",
    "generated_artifact_command",
    "runtime_reference_scan",
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def iso_now() -> str:
    """UTC timestamp for ledger rows (ISO 8601, Z-suffixed)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _listify(value) -> list:
    """Coerce a scalar/None/list field into a list of items."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _as_argv(command) -> Optional[list]:
    """Normalise a command field to an argv list, or None if unusable.

    A list is taken as argv verbatim; a string is `shlex.split` (NO shell, so
    no metacharacter expansion). Anything else is rejected.
    """
    if isinstance(command, (list, tuple)):
        return [str(part) for part in command]
    if isinstance(command, str):
        try:
            return shlex.split(command)
        except ValueError:
            return None
    return None


def _expected_exit_code(check: dict) -> int:
    """The expected exit code for a command-ish check.

    Accepts the canonical `{"expected": {"exit_code": N}}` shape, the
    convenience scalar `{"expected": N}`, and tolerates a malformed/missing
    value by defaulting to 0 (rather than raising on a non-dict `expected`).
    """
    exp = check.get("expected", {})
    if isinstance(exp, dict):
        exp = exp.get("exit_code", 0)
    try:
        return int(exp)
    except (TypeError, ValueError):
        return 0


def _resolve_timeout(check: dict) -> Optional[float]:
    """Per-check `timeout` overrides the env default; 0 disables the bound."""
    if "timeout" in check:
        try:
            value = float(check["timeout"])
        except (TypeError, ValueError):
            value = DEFAULT_TIMEOUT_SECONDS
    else:
        env = os.environ.get(_TIMEOUT_ENV_VAR)
        if env is not None:
            try:
                value = float(env)
            except ValueError:
                value = DEFAULT_TIMEOUT_SECONDS
        else:
            value = DEFAULT_TIMEOUT_SECONDS
    return None if value == 0 else value


class _CommandResult:
    """Outcome of a bounded subprocess run."""

    __slots__ = ("returncode", "stdout", "stderr", "timed_out", "not_found")

    def __init__(self, returncode, stdout, stderr, timed_out, not_found):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out
        self.not_found = not_found


def _run_bounded(argv: list, cwd: Path, timeout: Optional[float]) -> _CommandResult:
    """Run argv with cwd under an optional timeout, killing the whole process
    group on timeout (SIGTERM → grace → SIGKILL). Never raises for a missing
    executable — that surfaces as `not_found`."""
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # Own process group so killpg reaches any backgrounded children.
            start_new_session=True,
        )
    except FileNotFoundError:
        return _CommandResult(None, "", "", timed_out=False, not_found=True)
    except OSError as exc:
        return _CommandResult(None, "", str(exc), timed_out=False,
                              not_found=True)

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return _CommandResult(proc.returncode, stdout or "", stderr or "",
                              timed_out=False, not_found=False)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            stdout, stderr = proc.communicate(timeout=_KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            stdout, stderr = proc.communicate()
        return _CommandResult(proc.returncode, stdout or "", stderr or "",
                              timed_out=True, not_found=False)


def _stderr_tail(text: str, limit: int = 200) -> str:
    """A short, single-line tail of stderr for failure diagnostics."""
    text = (text or "").strip().replace("\n", " ")
    return text[-limit:]


# ---------------------------------------------------------------------------
# Primitive handlers. Each takes (check, base_dir) and returns a partial
# evidence dict with at least {"status", "message"} (plus optional extras).
# The dispatcher frames it with schema_version/check_id/ac_id/family/kind.
# ---------------------------------------------------------------------------

def _check_command(check: dict, base_dir: Path) -> dict:
    argv = _as_argv(check.get("command"))
    if not argv:
        return {"status": STATUS_ENV_ERROR,
                "message": "command check missing a usable 'command' field"}

    cwd = base_dir
    wd = check.get("working_directory")
    if wd:
        cwd = base_dir / wd
        if not cwd.is_dir():
            return {"status": STATUS_ENV_ERROR,
                    "message": f"working_directory not found: {wd}"}

    expected = _expected_exit_code(check)
    timeout = _resolve_timeout(check)
    result = _run_bounded(argv, cwd, timeout)

    if result.not_found:
        return {"status": STATUS_ENV_ERROR,
                "message": f"command not found: {argv[0]}",
                "command": argv}
    if result.timed_out:
        return {"status": STATUS_ENV_ERROR,
                "message": f"command exceeded timeout of {timeout}s: {argv}",
                "command": argv}
    if result.returncode == expected:
        return {"status": STATUS_PASS,
                "message": f"command exited {result.returncode} as expected",
                "command": argv, "exit_code": result.returncode}
    tail = _stderr_tail(result.stderr)
    msg = (f"command exited with code {result.returncode} "
           f"(expected {expected}): {argv}")
    if tail:
        msg += f" — stderr: {tail}"
    return {"status": STATUS_FAIL, "message": msg,
            "command": argv, "exit_code": result.returncode}


def _check_file_presence(check: dict, base_dir: Path) -> dict:
    rel = check.get("path")
    if not rel:
        return {"status": STATUS_ENV_ERROR,
                "message": "file_presence check missing required field 'path'"}
    path = base_dir / rel
    exists_expected = bool(check.get("exists", True))
    present = path.exists()

    if present != exists_expected:
        verb = "exist" if exists_expected else "be absent"
        return {"status": STATUS_FAIL,
                "message": f"expected path to {verb}: {rel}", "path": rel}

    if exists_expected and "executable" in check:
        want_exec = bool(check["executable"])
        try:
            is_exec = bool(path.stat().st_mode & 0o111)
        except OSError as exc:
            return {"status": STATUS_ENV_ERROR,
                    "message": f"cannot stat {rel}: {exc}", "path": rel}
        if is_exec != want_exec:
            state = "set" if want_exec else "unset"
            return {"status": STATUS_FAIL,
                    "message": f"expected executable bit {state} on: {rel}",
                    "path": rel}

    return {"status": STATUS_PASS,
            "message": f"path presence as expected: {rel}", "path": rel}


def _read_text(path: Path) -> Optional[str]:
    """Read a file as UTF-8 (replacing undecodable bytes), or None on error."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _check_text_invariant(check: dict, base_dir: Path) -> dict:
    rel = check.get("path")
    if not rel:
        return {"status": STATUS_ENV_ERROR,
                "message": "text_invariant check missing required field 'path'"}
    path = base_dir / rel
    if not path.is_file():
        return {"status": STATUS_ENV_ERROR,
                "message": f"cannot read text file: {rel} (not found)",
                "path": rel}
    text = _read_text(path)
    if text is None:
        return {"status": STATUS_ENV_ERROR,
                "message": f"cannot read text file: {rel}", "path": rel}

    asserted = False

    for needle in _listify(check.get("contains")):
        asserted = True
        if needle not in text:
            return {"status": STATUS_FAIL,
                    "message": f'{rel} does not contain expected text: "{needle}"',
                    "path": rel}

    for needle in _listify(check.get("not_contains")):
        asserted = True
        if needle in text:
            return {"status": STATUS_FAIL,
                    "message": f'{rel} contains forbidden text: "{needle}"',
                    "path": rel}

    for pattern in _listify(check.get("regex")):
        asserted = True
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return {"status": STATUS_ENV_ERROR,
                    "message": f"invalid regex {pattern!r}: {exc}", "path": rel}
        if not rx.search(text):
            return {"status": STATUS_FAIL,
                    "message": f"{rel} does not match regex: {pattern}",
                    "path": rel}

    for pattern in _listify(check.get("not_regex")):
        asserted = True
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return {"status": STATUS_ENV_ERROR,
                    "message": f"invalid regex {pattern!r}: {exc}", "path": rel}
        if rx.search(text):
            return {"status": STATUS_FAIL,
                    "message": f"{rel} matches forbidden regex: {pattern}",
                    "path": rel}

    if not asserted:
        return {"status": STATUS_ENV_ERROR,
                "message": (f"text_invariant check on {rel} has no assertion "
                            "(contains/not_contains/regex/not_regex)"),
                "path": rel}
    return {"status": STATUS_PASS,
            "message": f"text invariants hold for {rel}", "path": rel}


def _dig(obj, dotted: str):
    """Walk a dotted key path through nested dicts. Returns (found, value)."""
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return (False, None)
    return (True, cur)


def _check_json_contract(check: dict, base_dir: Path) -> dict:
    rel = check.get("path")
    if not rel:
        return {"status": STATUS_ENV_ERROR,
                "message": "json_contract check missing required field 'path'"}
    path = base_dir / rel
    if not path.is_file():
        return {"status": STATUS_ENV_ERROR,
                "message": f"JSON file not found: {rel}", "path": rel}
    text = _read_text(path)
    if text is None:
        return {"status": STATUS_ENV_ERROR,
                "message": f"cannot read JSON file: {rel}", "path": rel}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # "is valid JSON" is an assertable contract → fail, not env_error.
        return {"status": STATUS_FAIL,
                "message": f"{rel} is not valid JSON: {exc}", "path": rel}

    for key in _listify(check.get("required_keys")):
        found, _ = _dig(data, key)
        if not found:
            return {"status": STATUS_FAIL,
                    "message": f"{rel} missing required key: {key}",
                    "path": rel}

    for key, expected in (check.get("equals") or {}).items():
        found, value = _dig(data, key)
        if not found:
            return {"status": STATUS_FAIL,
                    "message": f"{rel} missing required key: {key}",
                    "path": rel}
        if value != expected:
            return {"status": STATUS_FAIL,
                    "message": (f"{rel} key {key} expected {expected!r}, "
                                f"got {value!r}"), "path": rel}

    return {"status": STATUS_PASS,
            "message": f"JSON contract holds for {rel}", "path": rel}


def _archive_names(path: Path) -> Optional[list]:
    """List entry names from a zip or tar archive, or None if not an archive."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            return zf.namelist()
    if tarfile.is_tarfile(path):
        with tarfile.open(path) as tf:
            return tf.getnames()
    return None


def _check_archive_inventory(check: dict, base_dir: Path) -> dict:
    rel = check.get("path")
    if not rel:
        return {"status": STATUS_ENV_ERROR,
                "message": "archive_inventory check missing required field 'path'"}
    path = base_dir / rel
    if not path.exists():
        return {"status": STATUS_ENV_ERROR,
                "message": f"archive not found: {rel}", "path": rel}

    contains = _listify(check.get("contains"))
    excludes = _listify(check.get("excludes"))
    if not contains and not excludes:
        return {"status": STATUS_ENV_ERROR,
                "message": (f"archive_inventory check on {rel} has no "
                            "'contains' or 'excludes' assertion"), "path": rel}

    try:
        names = _archive_names(path)
    except (zipfile.BadZipFile, tarfile.TarError, OSError) as exc:
        return {"status": STATUS_ENV_ERROR,
                "message": f"cannot read archive {rel}: {exc}", "path": rel}
    if names is None:
        return {"status": STATUS_ENV_ERROR,
                "message": f"not a zip or tar archive: {rel}", "path": rel}
    name_set = set(names)

    for entry in contains:
        if entry not in name_set:
            return {"status": STATUS_FAIL,
                    "message": f"archive {rel} missing required entry: {entry}",
                    "path": rel}
    for entry in excludes:
        if entry in name_set:
            return {"status": STATUS_FAIL,
                    "message": f"archive {rel} contains forbidden entry: {entry}",
                    "path": rel}

    return {"status": STATUS_PASS,
            "message": f"archive inventory as expected: {rel}", "path": rel}


# A Markdown inline link: `[text](target)`. Reference-style links are out of
# scope for v1 (logged as a known limitation in the deviation log).
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)[^)]*\)")
# A URL scheme prefix (http:, https:, mailto:, etc.) marks an external link.
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")


def _check_markdown_links(check: dict, base_dir: Path) -> dict:
    rel = check.get("path")
    root = check.get("root")
    md_files: list = []
    if rel:
        path = base_dir / rel
        if not path.is_file():
            return {"status": STATUS_ENV_ERROR,
                    "message": f"markdown file not found: {rel}", "path": rel}
        md_files = [path]
    elif root:
        root_path = base_dir / root
        if not root_path.is_dir():
            return {"status": STATUS_ENV_ERROR,
                    "message": f"markdown root not found: {root}"}
        md_files = sorted(root_path.rglob("*.md"))
    else:
        return {"status": STATUS_ENV_ERROR,
                "message": "markdown_links check needs 'path' or 'root'"}

    for md in md_files:
        text = _read_text(md)
        if text is None:
            return {"status": STATUS_ENV_ERROR,
                    "message": f"cannot read markdown file: {md}"}
        rel_md = os.path.relpath(md, base_dir)
        for target in _MD_LINK_RE.findall(text):
            target = target.strip()
            if not target or target.startswith("#"):
                continue  # in-page anchor
            if _SCHEME_RE.match(target) or target.startswith("//"):
                continue  # external link
            local = target.split("#", 1)[0]
            if not local:
                continue
            if not (md.parent / local).exists():
                return {"status": STATUS_FAIL,
                        "message": f"{rel_md} has broken local link: {target}",
                        "path": rel_md}

    label = rel if rel else root
    return {"status": STATUS_PASS,
            "message": f"local markdown links resolve: {label}"}


def _substitute(argv: list, mapping: dict) -> list:
    """Expand `{name}` placeholders in argv string parts (best-effort)."""
    out = []
    for part in argv:
        for key, value in mapping.items():
            part = part.replace("{" + key + "}", value)
        out.append(part)
    return out


def _check_generated_artifact_command(check: dict, base_dir: Path) -> dict:
    argv = _as_argv(check.get("command"))
    if not argv:
        return {"status": STATUS_ENV_ERROR,
                "message": ("generated_artifact_command check missing a usable "
                            "'command' field")}

    tmp = Path(tempfile.mkdtemp(prefix="servo-oracle-"))
    try:
        source = check.get("source")
        if source:
            src = base_dir / source
            if not src.is_dir():
                return {"status": STATUS_ENV_ERROR,
                        "message": f"source tree not found: {source}"}
            try:
                shutil.copytree(src, tmp, dirs_exist_ok=True)
            except (OSError, shutil.Error) as exc:
                return {"status": STATUS_ENV_ERROR,
                        "message": f"cannot copy source {source}: {exc}"}

        workdir = tmp
        sub = check.get("working_subdir")
        if sub:
            workdir = tmp / sub

        placeholders = {"tmp": str(tmp), "workdir": str(workdir)}
        timeout = _resolve_timeout(check)

        build = check.get("build_command")
        if build:
            build_argv = _as_argv(build)
            if not build_argv:
                return {"status": STATUS_ENV_ERROR,
                        "message": "unusable 'build_command' field"}
            build_argv = _substitute(build_argv, placeholders)
            b = _run_bounded(build_argv, tmp, timeout)
            if b.not_found:
                return {"status": STATUS_ENV_ERROR,
                        "message": f"build command not found: {build_argv[0]}"}
            if b.timed_out:
                return {"status": STATUS_ENV_ERROR,
                        "message": f"build command exceeded timeout of {timeout}s"}
            if b.returncode != 0:
                return {"status": STATUS_ENV_ERROR,
                        "message": (f"build command failed (exit {b.returncode}) "
                                    f"— could not produce artifact: {build_argv}")}

        if not workdir.is_dir():
            return {"status": STATUS_ENV_ERROR,
                    "message": f"generated working directory missing: {sub}"}

        expected = _expected_exit_code(check)
        run_argv = _substitute(argv, placeholders)
        r = _run_bounded(run_argv, workdir, timeout)
        if r.not_found:
            return {"status": STATUS_ENV_ERROR,
                    "message": f"command not found: {run_argv[0]}",
                    "command": run_argv}
        if r.timed_out:
            return {"status": STATUS_ENV_ERROR,
                    "message": f"command exceeded timeout of {timeout}s",
                    "command": run_argv}
        if r.returncode == expected:
            return {"status": STATUS_PASS,
                    "message": ("command succeeded from generated artifact "
                                f"(exit {r.returncode})"),
                    "command": run_argv, "exit_code": r.returncode}
        tail = _stderr_tail(r.stderr)
        msg = (f"command from generated artifact exited {r.returncode} "
               f"(expected {expected}): {run_argv}")
        if tail:
            msg += f" — stderr: {tail}"
        return {"status": STATUS_FAIL, "message": msg,
                "command": run_argv, "exit_code": r.returncode}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _check_runtime_reference_scan(check: dict, base_dir: Path) -> dict:
    needle = check.get("needle")
    pattern = check.get("regex")
    if not needle and not pattern:
        return {"status": STATUS_ENV_ERROR,
                "message": ("runtime_reference_scan check needs 'needle' or "
                            "'regex'")}
    matcher = None
    if pattern:
        try:
            matcher = re.compile(pattern)
        except re.error as exc:
            return {"status": STATUS_ENV_ERROR,
                    "message": f"invalid regex {pattern!r}: {exc}"}

    roots = _listify(check.get("roots")) or ["."]
    excludes = _listify(check.get("exclude"))

    def is_excluded(rel_posix: str) -> bool:
        return any(fnmatch.fnmatch(rel_posix, glob) for glob in excludes)

    def hit(line: str) -> bool:
        return bool(matcher.search(line)) if matcher else (needle in line)

    files: list = []
    for root in roots:
        rp = base_dir / root
        if not rp.exists():
            return {"status": STATUS_ENV_ERROR,
                    "message": f"scan root not found: {root}"}
        if rp.is_file():
            files.append(rp)
        else:
            for dirpath, _dirs, filenames in os.walk(rp):
                for name in filenames:
                    files.append(Path(dirpath) / name)

    label = pattern if pattern else needle
    for fp in files:
        rel_posix = Path(os.path.relpath(fp, base_dir)).as_posix()
        if is_excluded(rel_posix):
            continue
        text = _read_text(fp)
        if text is None:
            continue  # unreadable/binary — skip
        for lineno, line in enumerate(text.splitlines(), start=1):
            if hit(line):
                return {"status": STATUS_FAIL,
                        "message": (f"forbidden reference {label!r} found at "
                                    f"{rel_posix}:{lineno}"),
                        "path": rel_posix, "line": lineno}

    return {"status": STATUS_PASS,
            "message": f"no live references to {label!r} found"}


# ---------------------------------------------------------------------------
# Dispatch + framing
# ---------------------------------------------------------------------------

DISPATCH = {
    "command": _check_command,
    "file_presence": _check_file_presence,
    "text_invariant": _check_text_invariant,
    "json_contract": _check_json_contract,
    "archive_inventory": _check_archive_inventory,
    "markdown_links": _check_markdown_links,
    "generated_artifact_command": _check_generated_artifact_command,
    "runtime_reference_scan": _check_runtime_reference_scan,
}


def run_check(check: dict, base_dir: Path) -> dict:
    """Run one check and return a fully-framed evidence record.

    The record always carries the AC2 fields (`schema_version`, `check_id`,
    `ac_id`, `status`, `message`) plus `kind`, `family`, and any family-
    specific diagnostics. A handler that raises is contained as an
    `env_error` so one bad check never aborts the whole run.
    """
    check_id = check.get("id") or check.get("check_id") or "<unknown>"
    ac_id = check.get("ac_id") or check_id
    family = check.get("family")

    if family == "residual_judgment":
        reason = check.get("reason", "non-deterministic in v1")
        review = check.get("suggested_review", "human review")
        partial = {"status": STATUS_NA,
                   "message": f"residual judgment ({reason}); review: {review}"}
    elif family in DISPATCH:
        try:
            partial = DISPATCH[family](check, base_dir)
        except Exception as exc:  # defensive backstop — never crash the run
            partial = {"status": STATUS_ENV_ERROR,
                       "message": f"check raised {type(exc).__name__}: {exc}"}
    else:
        partial = {"status": STATUS_ENV_ERROR,
                   "message": f"unknown check family: {family!r}"}

    evidence = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "kind": "evidence",
        "check_id": check_id,
        "ac_id": ac_id,
        "family": family,
    }
    evidence.update(partial)
    return evidence


def score_summary(evidence: list) -> dict:
    """Tally evidence statuses into counts and a composite score (AC3)."""
    passed = sum(1 for e in evidence if e.get("status") == STATUS_PASS)
    failed = sum(1 for e in evidence if e.get("status") == STATUS_FAIL)
    env_errors = sum(1 for e in evidence if e.get("status") == STATUS_ENV_ERROR)
    na = sum(1 for e in evidence if e.get("status") == STATUS_NA)

    denominator = passed + failed
    if denominator > 0:
        score = passed / denominator
    elif env_errors > 0:
        score = 0.0
    else:
        score = 1.0

    return {
        "passed_checks": passed,
        "failed_checks": failed,
        "env_errors": env_errors,
        "not_applicable": na,
        "total": len(evidence),
        "score": score,
    }


def run_checks(plan: dict, base_dir: Path) -> dict:
    """Run every check in a plan and return evidence + a scored summary.

    Deterministic `checks[]` entries are executed; `residual_judgment[]`
    entries are emitted as `not_applicable` evidence so the ledger holds one
    record per acceptance criterion (AC2).
    """
    evidence = [run_check(c, base_dir) for c in plan.get("checks", [])]
    for residual in plan.get("residual_judgment", []):
        evidence.append(run_check({**residual, "family": "residual_judgment"},
                                  base_dir))

    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "kind": "run",
        "spec_id": plan.get("spec_id"),
        "runner_version": RUNNER_VERSION,
        "evidence": evidence,
        "summary": score_summary(evidence),
    }


def exit_code_for(summary: dict) -> int:
    """servo's exit convention: env error → 2, any failure → 1, else 0."""
    if summary.get("env_errors", 0) > 0:
        return 2
    if summary.get("failed_checks", 0) > 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Freeze controls (slice 006-04). Optional, enabled by --enforce-freeze — the
# generated oracle component runs with it on, so an unattended loop can only
# score an overlay that is approved, source-faithful, and unmodified.
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def plan_content_hash(plan: dict) -> str:
    """Hash the *evidence content* of a plan — its ``checks`` and
    ``residual_judgment`` — excluding the mutable approval/provenance fields.

    A tripwire: relaxing, weakening, or deleting a check after approval changes
    this hash, so the freeze gate refuses. It is NOT adversary-proof — a runner
    that deliberately rewrites both the checks and this recorded hash would not
    be caught (any in-file integrity value is forgeable by a writer of that
    file). The defenses against a deliberately self-rewriting runner are the
    runner.md constraint (AC5) and the human approval flow, per ADR-0001's
    filesystem-only trust model. This catches honest drift, like the other
    freeze hashes."""
    payload = json.dumps(
        {"checks": plan.get("checks", []),
         "residual_judgment": plan.get("residual_judgment", [])},
        sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def freeze_violation(plan: dict, checks_json_path: Path,
                     base_dir: Path) -> Optional[tuple]:
    """Return ``(reason, message)`` if the overlay must be refused, else None.

    Checks, in order: approval state (AC1), source-spec hash (AC2), then
    generated-artifact hashes (AC3). All violations map to env error (exit 2)
    — the loud "refuse to score" signal — with a distinct ``reason``.
    """
    status = plan.get("approval_status", "draft")
    if status == "stale":
        return ("spec_oracle_stale",
                "spec-oracle marked stale; re-plan and re-approve")
    if status != "approved":
        return ("spec_oracle_unapproved",
                f"spec-oracle not approved (status={status!r}); "
                f"approve it before unattended use")

    # AC2 — source spec must hash to what was recorded at plan time.
    source_path = plan.get("source_spec_path")
    source_hash = plan.get("source_hash")
    if source_path and source_hash:
        src = base_dir / source_path
        if not src.is_file():
            return ("spec_oracle_stale",
                    f"source spec missing: {source_path}; re-plan")
        if _sha256_file(src) != source_hash:
            return ("spec_oracle_stale",
                    f"source spec changed since approval ({source_path}); "
                    f"re-plan and re-approve")

    # AC3 — approved generated artifacts must be byte-identical.
    for name, expected in (plan.get("approved_artifacts") or {}).items():
        artifact = checks_json_path.parent / name
        if not artifact.is_file():
            return ("spec_oracle_artifact_modified",
                    f"approved artifact missing: {name}")
        if _sha256_file(artifact) != expected:
            return ("spec_oracle_artifact_modified",
                    f"approved artifact modified: {name}; re-approve after review")

    # The approved checks themselves are tripwire-pinned (slice 006-04 review):
    # relaxing/removing a check after approval changes the content hash.
    approved_content = plan.get("approved_content_hash")
    if approved_content and plan_content_hash(plan) != approved_content:
        return ("spec_oracle_plan_modified",
                "checks.json checks modified since approval; re-approve after review")

    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _derive_base_dir(checks_json: Path) -> Path:
    """Derive the target root from a canonical spec-oracle location.

    `<target>/.servo/spec-oracles/<id>/checks.json` → `<target>`. Falls back
    to the cwd when the path is not in that shape.
    """
    resolved = checks_json.resolve()
    parts = resolved.parts
    try:
        i = len(parts) - 1 - parts[::-1].index(".servo")
        # parts[i] == ".servo"; the target root is its parent.
        return Path(*parts[:i]) if i > 0 else Path.cwd()
    except ValueError:
        return Path.cwd()


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="checks.py",
        description="Run a spec-oracle checks.json and emit JSONL evidence.",
    )
    parser.add_argument("checks_json")
    parser.add_argument("--base-dir", dest="base_dir", default=None,
                        help="target root for resolving check paths "
                             "(default: derived from the .servo layout, else cwd)")
    parser.add_argument("--ledger", dest="ledger", default=None,
                        help="append evidence JSONL to this file instead of stdout")
    parser.add_argument("--score-only", dest="score_only", action="store_true",
                        help="print only the composite score (for an oracle.sh "
                             "component): exit 2 iff any check env-errored, else 0")
    parser.add_argument("--enforce-freeze", dest="enforce_freeze",
                        action="store_true",
                        help="refuse (exit 2) unless the overlay is approved, its "
                             "source spec is unchanged, and its generated "
                             "artifacts are unmodified (slice 006-04)")
    args = parser.parse_args(argv)

    checks_path = Path(args.checks_json)
    if not checks_path.is_file():
        print(f"error: checks.json not found: {args.checks_json}", file=sys.stderr)
        return 2
    try:
        plan = json.loads(checks_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read checks.json: {exc}", file=sys.stderr)
        return 2

    if args.base_dir:
        base_dir = Path(args.base_dir)
    else:
        base_dir = _derive_base_dir(checks_path)

    # Freeze gate (006-04): an unapproved / stale / tampered overlay is refused
    # before any check runs, so the loop can never satisfy a self-invented or
    # quietly-modified oracle.
    if args.enforce_freeze:
        violation = freeze_violation(plan, checks_path, base_dir)
        if violation is not None:
            reason, message = violation
            print(f"spec-oracle refused: {message} [{reason}]", file=sys.stderr)
            return 2

    result = run_checks(plan, base_dir)
    evidence = result["evidence"]
    summary_line = {"kind": "summary",
                    "schema_version": EVIDENCE_SCHEMA_VERSION,
                    "spec_id": result["spec_id"],
                    "runner_version": RUNNER_VERSION,
                    **result["summary"]}

    # Ledger rows carry a shared run timestamp so an append-only ledger can
    # tell separate runs apart (spec goal 6).
    if args.ledger:
        ts = iso_now()
        try:
            with open(args.ledger, "a", encoding="utf-8") as fh:
                for ev in evidence:
                    fh.write(json.dumps({**ev, "ts": ts}) + "\n")
        except OSError as exc:
            print(f"error: cannot write ledger: {exc}", file=sys.stderr)
            return 2

    # --score-only: the oracle.sh component contract. Print only the composite
    # score; exit 2 iff any check env-errored (so oracle.sh marks the component
    # missing → rc=2), else 0. Never exit 1 — the THRESHOLD gate, not the
    # component, decides pass/fail.
    if args.score_only:
        print(result["summary"]["score"])
        return 2 if result["summary"].get("env_errors", 0) > 0 else 0

    if not args.ledger:
        for ev in evidence:
            print(json.dumps(ev))
    print(json.dumps(summary_line))
    return exit_code_for(result["summary"])


if __name__ == "__main__":
    sys.exit(main())
