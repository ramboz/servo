"""
servo heartbeat — slices 011-01 (discover-and-inbox) + 011-02 (triage-state-spine)

The scheduled front-end of the servo loop. A Routine (cron / scheduled agent
/ CI `schedule:`) wakes servo on an interval; this helper's `discover`
subcommand does a **strictly read-only** pass over the target's own signals —
CI failures (`gh`), open issues (`gh`), recent commits (`git`) — and writes
the findings to `<target>/.servo/triage/inbox.jsonl` (one JSON record per
finding) plus a generated, human-readable `<target>/.servo/triage/inbox.md`
view. The pass mutates nothing outside `.servo/triage/`.

Slice 011-02 turns the inbox into a **resuming state spine** (ADR-0010): a
stable `finding_id` dedupes across runs, so `discover` now **merges** by
identity instead of overwriting — preserving each finding's immutable
(`finding_id`/`source`/`provenance`/`discovered_at`) and sticky
(`status`/`attempts`/`outcome`) fields while refreshing its volatile fields
(`title`/`detail`/`evidence`/`last_seen_at`/`actionable`/`actionable_reason`).
A retention rule bounds growth uniformly across sources (an `open` finding not
re-observed this pass is evicted; a `tried`/`passed`/`skipped` finding is kept
as an audit trail). Each finding carries an immutable `provenance` trust fact
(Guardrail #4) and a recomputed `actionable` verdict. The read-modify-write is
guarded by an advisory `fcntl.flock` on a separate `.inbox.lock` so a
double-fired Routine can't corrupt the inbox. A new read-only `status`
subcommand reads the spine back (human summary or `--json`).

Each source degrades independently: a missing `gh`, an auth error, or one
source emitting unparseable JSON skips *that source* with a stderr breadcrumb
and continues over the rest — discovery never hard-fails because one signal is
unavailable. External tools (`gh`, `git`) are invoked via subprocess with
list-form argv (never `shell=True`, never imported), so target-controlled
content (issue titles, commit messages) can never be shell-interpreted; all
subprocess output is treated as untrusted DATA.

Subcommands mirror the house pattern (`gate.py invoke/audit`,
`loop.py`/`hook.py` verbs). `discover` (011-01) and `status` (011-02) ship;
`dispatch` (011-03) and `run` (011-04) are later slices and are not
implemented here. 011-02 records the `provenance` marker and the `actionable`
verdict; 011-03 *acts on* them (the `open → tried`/`passed` transitions, the
`attempts` increment, and the `outcome` object are written by 011-03 — their
shape is reserved by ADR-0010, and 011-02 writes only their defaults).

Usage:
    python3 heartbeat.py discover <target>
    python3 heartbeat.py status <target> [--json]

Both artifacts are written atomically — full payload to `<name>.tmp`, then
`os.replace` onto the final path (ADR-0004's house discipline for `.servo/`
state files) — so a SIGTERM/crash mid-write can never leave a torn artifact.
Closed `{0, 2}` exit contract for BOTH verbs: 0 = completed OK (for `discover`,
zero or more findings incl. all-sources-skipped and the lock-contended no-op;
for `status`, read OK incl. an empty/absent inbox); 2 = environment error that
prevents the operation (`target_missing` / `target_not_directory` /
`triage_dir_unwritable`, a `flock` `OSError`, or — `status` only — a
`schema_version_unsupported` record from a higher unknown version). There is
**no exit 1** — neither verb gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

# `fcntl` is POSIX-only stdlib. servo already assumes POSIX (the oracle is
# bash), but the double-fire lock degrades gracefully on a non-POSIX host: if
# the import fails, discovery proceeds UNLOCKED with a one-time breadcrumb (the
# atomic write still prevents torn files; only the lost-update race is
# unguarded). Guarded here, not at the call site, so the degradation is a single
# module-level fact (AC8, ADR-0010).
try:
    import fcntl
except ImportError:  # pragma: no cover - exercised only on non-POSIX hosts
    fcntl = None  # type: ignore[assignment]

# JSON record schema version for every line of `inbox.jsonl`. Mirrors
# gate.py's `schema_version` (ADR-0002) and loop.py's state framing. Bumped
# 1 → 2 at slice 011-02: the record gained required fields (provenance,
# attempts, outcome, last_seen_at, actionable, actionable_reason), the meaning
# of `discovered_at` changed (now first-seen, preserved across merge), and the
# write discipline changed from overwrite to merge (ADR-0010). All records in a
# file MUST carry the same version; a mixed-version file is corruption (a
# reader refuses with rc=2). Always emitted as the FIRST key of each record.
SCHEMA_VERSION = 2

# Closed exit-code contract (AC11), aligned with gate.py / loop.py but with a
# narrower set — neither verb gates, so there is no "below threshold":
#   0 — completed OK (discover: zero or more findings, incl. all-skipped and the
#       lock-contended no-op; status: read OK, incl. an empty/absent inbox)
#   2 — env error preventing the operation (target_missing /
#       target_not_directory / triage_dir_unwritable / a flock OSError /
#       — status only — schema_version_unsupported)
# 1 is intentionally unused.
EXIT_OK = 0
EXIT_ENV_ERROR = 2

# Source identifiers (the closed v1 signal set; the dispatch table below is
# the documented extension point for more sources later).
SOURCE_CI = "ci"
SOURCE_ISSUE = "issue"
SOURCE_COMMIT = "commit"

# Finding status lifecycle (ADR-0010). 011-02 mints findings `open` and the
# retention rule below keys off the sticky (non-open) set; the open → tried /
# passed transitions and the human-only skipped transition are 011-03 / manual.
STATUS_OPEN = "open"
STATUS_TRIED = "tried"
STATUS_PASSED = "passed"
STATUS_SKIPPED = "skipped"
# Sticky (lifecycle-bearing) statuses: retained indefinitely as an audit trail
# even after their signal disappears. Everything NOT in this set (i.e. `open`)
# is evicted when not re-observed in a pass (the uniform retention bound, AC5).
_STICKY_STATUSES = frozenset({STATUS_TRIED, STATUS_PASSED, STATUS_SKIPPED})

# Provenance — an immutable trust *fact* about who produced a finding's text
# (Guardrail #4, ADR-0010). A pure function of `source` (which is part of the
# fingerprint), so it can never change for a stable finding_id. 011-02 only
# RECORDS it; 011-03 derives the dispatch treatment (frame `contributor`
# title/detail/evidence as untrusted DATA, never instructions).
PROVENANCE_FIRST_PARTY = "first_party"   # source == ci (the project's own pipeline)
PROVENANCE_CONTRIBUTOR = "contributor"   # source ∈ {issue, commit} (outside text)

# CI is actionable only for these trigger events — a `pull_request` run is
# someone's in-progress PR and is never auto-actionable (ADR-0010 v1 heuristic).
_CI_ACTIONABLE_EVENTS = frozenset({"push", "schedule"})

# Issue labels (case-insensitive NAME match) that mark an open issue NOT
# auto-actionable. Deliberately conservative + tunable (ADR-0010); mis-triage is
# cheap to correct because the inbox is reviewable.
_NON_ACTIONABLE_ISSUE_LABELS = frozenset({
    "wontfix", "won't fix", "duplicate", "invalid", "question", "discussion",
})

# actionable_reason machine codes (ADR-0010). Stored alongside `actionable` so a
# reviewer / 011-03 can see WHY a verdict was reached without re-deriving it.
REASON_CI_DEFAULT_BRANCH = "ci_default_branch"
REASON_CI_NON_DEFAULT_BRANCH = "ci_non_default_branch"
REASON_CI_DEFAULT_BRANCH_UNKNOWN = "ci_default_branch_unknown"
REASON_CI_NON_ACTIONABLE_EVENT = "ci_non_actionable_event"
REASON_ISSUE_OPEN = "issue_open"
REASON_ISSUE_LABEL_PREFIX = "issue_label_"   # + the matched label name
REASON_COMMIT_CONTEXT_ONLY = "commit_context_only"

# Reserved triage artifact dir + filenames, beside `runs/` and `races/`.
TRIAGE_DIRNAME = "triage"
INBOX_JSONL_NAME = "inbox.jsonl"
INBOX_MD_NAME = "inbox.md"

# Persistent advisory-lock target for the read-merge-write (AC8, ADR-0010). A
# SEPARATE file from inbox.jsonl — `os.replace` swaps the inbox inode, so a lock
# held on the inbox fd would protect nothing. NEVER unlinked: unlinking races the
# flock (a run arriving in the unlink→close window would create a fresh inode and
# proceed concurrently); the kernel releases the LOCK on process exit, so no
# stale lock ever persists — the property a pidfile lacks.
INBOX_LOCK_NAME = ".inbox.lock"

# Atomic-write staging suffix (mirrors loop.py's STATE_TMP_SUFFIX): write the
# full payload here, then os.replace onto the final path.
TMP_SUFFIX = ".tmp"

# Generated-view marker (the `status-board` generated-view convention).
GENERATED_MARKER = "<!-- generated by heartbeat.py — do not hand-edit -->"

# Unit separator delimiting `<sha><US><subject>` in the `git log --pretty`
# format. ASCII 0x1f never appears in a commit sha or (practically) a subject
# line, so it is a safe, parse-stable field delimiter — and avoids any risk of
# a commit message containing the delimiter we'd otherwise pick.
GIT_LOG_FORMAT_TOKEN = "%H%x1f%s"

# How many recent commits / failed runs / issues to enumerate. Bounded so an
# unattended discovery pass over a busy repo stays cheap and the inbox stays
# reviewable. (Limit-tuning was flagged for revisit alongside actionability;
# the 011-01 values held up against the real surface, so they are kept.)
COMMIT_LIMIT = 20
CI_RUN_LIMIT = 20
ISSUE_LIMIT = 50

# Bound every subprocess so a wedged `gh` / `git` can never hang an unattended
# heartbeat forever (mirrors gate.py / loop.py's bounded-subprocess
# discipline). 60s is generous for a single network-backed `gh` list call.
SUBPROCESS_TIMEOUT_SECONDS = 60

# `gh run list --json` field surface (verified live, gh 2.92.0). `event` is now
# read (011-02 actionability — a pull_request run is never auto-actionable).
_GH_RUN_FIELDS = "workflowName,headBranch,conclusion,url,displayTitle,event,createdAt"

# `gh issue list --json` field surface (verified live, gh 2.92.0). `labels` is
# now read (011-02 actionability — a non-actionable label suppresses dispatch).
_GH_ISSUE_FIELDS = "number,title,body,url,state,labels,author,createdAt,updatedAt"

# `gh repo view --json` field surface for authoritative default-branch
# resolution (011-02 CI actionability). `gh repo view` is primary precisely
# because `origin/HEAD` is unset on many real clones (ADR-0010).
_GH_REPO_FIELDS = "defaultBranchRef"


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string (matches loop.py's stamps)."""
    return datetime.now(timezone.utc).isoformat()


def _fingerprint(*parts: str) -> str:
    """Stable 16-hex-char fingerprint over content-identifying parts (AC2).

    `sha256("<part0>|<part1>|...")[:16]`. Derived ONLY from stable,
    content-identifying fields — never timestamps, run ordinals, or attempt
    numbers — so re-running `discover` on identical signals yields identical
    ids. This is the identity 011-02 dedupes the merge on; the 011-01 scheme is
    ratified unchanged as the v2 contract (ADR-0010).
    """
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _run_subprocess(
    argv: list[str], *, cwd: Optional[Path] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Run `argv` (list-form, no shell) bounded by a timeout.

    Returns `(stdout, None)` on a clean exit-0, or `(None, breadcrumb)` on any
    failure: binary absent (FileNotFoundError), non-zero exit, timeout, or
    OSError. The breadcrumb is a single-line, stderr-suitable cause string.

    List-form argv with no `shell=True` means target-controlled content (issue
    titles, commit messages, branch names) is never shell-interpreted — it is
    inert data on the argv, and the *output* is likewise treated as data by the
    callers. The bounded timeout mirrors gate.py / loop.py so a wedged tool
    can't hang an unattended pass.
    """
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        # Binary not on PATH — execvp raises this before the child runs.
        return None, f"{argv[0]} not on PATH"
    except subprocess.TimeoutExpired:
        return None, f"{argv[0]} timed out after {SUBPROCESS_TIMEOUT_SECONDS}s"
    except OSError as exc:
        return None, f"OS error invoking {argv[0]}: {exc}"
    if proc.returncode != 0:
        return None, f"{argv[0]} exited {proc.returncode}"
    return proc.stdout, None


def _provenance_for(source: str) -> str:
    """Map a `source` to its immutable provenance trust fact (AC7, Guardrail #4).

    `first_party` for CI (the project's own pipeline result); `contributor` for
    issue/commit (free-form text that is attacker-influenceable on any repo
    accepting outside contributions). A pure function of `source` — which is in
    the fingerprint — so it cannot change for a stable finding_id.
    """
    return PROVENANCE_FIRST_PARTY if source == SOURCE_CI else PROVENANCE_CONTRIBUTOR


def _resolve_default_branch(target: Path) -> Optional[str]:
    """Resolve the target repo's default branch ONCE per pass (AC6, ADR-0010).

    Resolution order, most authoritative first:
      1. `gh repo view --json defaultBranchRef` — authoritative; primary
         precisely because `origin/HEAD` is unset on many real clones, so
         relying on (2) alone would silently disable CI dispatch on healthy
         repos.
      2. `git symbolic-ref --short refs/remotes/origin/HEAD` (strip `origin/`).
      3. a `main` / `master` heuristic is applied by the CALLER against the
         finding's own branch (we cannot guess a repo's default from nothing
         here); this function returns None when (1) and (2) both fail.

    Returns the branch name, or None when it cannot be authoritatively resolved
    (the caller then applies the heuristic, and failing that classifies the
    finding `ci_default_branch_unknown` — fail toward NOT auto-spending).
    """
    stdout, err = _run_subprocess(
        ["gh", "repo", "view", "--json", _GH_REPO_FIELDS], cwd=target,
    )
    if err is None and stdout and stdout.strip():
        try:
            data = json.loads(stdout)
            ref = (data or {}).get("defaultBranchRef") or {}
            name = ref.get("name")
            if name:
                return str(name)
        except json.JSONDecodeError:
            pass  # fall through to the git fallback

    stdout, err = _run_subprocess(
        ["git", "-C", str(target), "symbolic-ref", "--short",
         "refs/remotes/origin/HEAD"],
    )
    if err is None and stdout and stdout.strip():
        ref = stdout.strip().splitlines()[0].strip()
        # `--short` yields e.g. `origin/main`; strip the remote prefix.
        if ref.startswith("origin/"):
            ref = ref[len("origin/"):]
        if ref:
            return ref

    return None


def _classify_ci(branch: str, event: str, default_branch: Optional[str]) -> tuple[bool, str]:
    """Actionability verdict + reason for a CI finding (AC6).

    Actionable iff the run's trigger `event ∈ {push, schedule}` AND its
    `headBranch` is the repo's default branch. The two gates are reported with
    distinct reasons so 011-03 / a human sees the actual disqualifier without
    re-deriving it:

    - `ci_non_actionable_event` — wrong trigger event (a `pull_request` run is
      someone's in-progress PR, never auto-actionable regardless of branch).
      Checked first: the event disqualifies independently of branch resolution.
    - `ci_default_branch_unknown` — actionable event, but the default branch
      could not be authoritatively resolved (`_resolve_default_branch`) and the
      run's own branch is neither `main` nor `master` (the last-resort
      heuristic); NOT actionable — fail toward not auto-spending.
    - `ci_non_default_branch` — actionable event, default branch resolved, but
      the run is on some other branch.
    - `ci_default_branch` — actionable event on the resolved default branch.
    """
    if event not in _CI_ACTIONABLE_EVENTS:
        # The disqualifier is the event, not the branch — say so precisely, even
        # when headBranch happens to be the default branch.
        return False, REASON_CI_NON_ACTIONABLE_EVENT
    resolved = default_branch
    if resolved is None:
        # Last-resort heuristic: a branch literally named main/master is taken to
        # be the default. This never up-classifies a feature branch (only the two
        # conventional default names match), so it stays fail-safe.
        if branch in ("main", "master"):
            resolved = branch
        else:
            return False, REASON_CI_DEFAULT_BRANCH_UNKNOWN
    if branch == resolved:
        return True, REASON_CI_DEFAULT_BRANCH
    return False, REASON_CI_NON_DEFAULT_BRANCH


def _classify_issue(labels: list) -> tuple[bool, str]:
    """Actionability verdict + reason for an issue finding (AC6).

    Actionable unless a label NAME (case-insensitive) is in the conservative
    non-actionable set. The reason for a suppressed issue names the matched label
    (`issue_label_<name>`) so a reviewer sees why; an actionable issue is
    `issue_open`.
    """
    for label in labels or []:
        if not isinstance(label, dict):
            continue
        name = str(label.get("name", "") or "")
        if name.lower() in _NON_ACTIONABLE_ISSUE_LABELS:
            return False, REASON_ISSUE_LABEL_PREFIX + name.lower()
    return True, REASON_ISSUE_OPEN


def _discover_ci(target: Path) -> tuple[Optional[list[dict]], Optional[str]]:
    """Enumerate recent failed CI runs via `gh run list` (AC1a).

    Returns `(findings, None)` on success or `(None, breadcrumb)` when `gh`
    is absent / errors / emits unparseable JSON (AC4 — caller skips just this
    source). One `gh` call per source (no second `gh run view` for jobs — see
    the slice deviation log: `gh run list` has no `job` field, so ci is
    fingerprinted on workflowName + headBranch; job-granularity is deferred to
    011-02 if wanted).
    """
    argv = [
        "gh", "run", "list",
        "--status", "failure",
        "--limit", str(CI_RUN_LIMIT),
        "--json", _GH_RUN_FIELDS,
    ]
    stdout, err = _run_subprocess(argv, cwd=target)
    if err is not None:
        return None, err
    # A clean exit-0 with empty/whitespace stdout means "ran, found nothing" —
    # treat it as an empty list, NOT a parse failure, so the per-source health
    # header reports `ran (0 findings)` rather than mislabeling a healthy
    # source `skipped (unparseable JSON)`. Real `gh --json` emits `[]`, but
    # guarding the empty-stdout edge keeps the AC5 health signal honest.
    raw = (stdout or "").strip()
    if not raw:
        runs = []
    else:
        try:
            runs = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, f"gh run list emitted unparseable JSON: {exc.msg}"
    if not isinstance(runs, list):
        return None, "gh run list JSON is not a list"

    # Resolve the default branch ONCE per pass (AC6), and only when there is at
    # least one run to classify — so a healthy-but-empty ci source costs no
    # extra `gh repo view` call and the AC4 degradation paths are unchanged.
    default_branch: Optional[str] = None
    if runs:
        default_branch = _resolve_default_branch(target)

    findings: list[dict] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        workflow = str(run.get("workflowName", "") or "")
        branch = str(run.get("headBranch", "") or "")
        url = str(run.get("url", "") or "")
        display = str(run.get("displayTitle", "") or "")
        conclusion = str(run.get("conclusion", "") or "")
        event = str(run.get("event", "") or "")
        title = f"CI failure: {workflow} on {branch}" if workflow else "CI failure"
        detail_parts = []
        if display:
            detail_parts.append(display)
        if conclusion:
            detail_parts.append(f"conclusion={conclusion}")
        actionable, reason = _classify_ci(branch, event, default_branch)
        findings.append(_build_finding(
            source=SOURCE_CI,
            finding_id=_fingerprint(SOURCE_CI, workflow, branch),
            title=title,
            detail=" — ".join(detail_parts),
            evidence={
                "run_url": url,
                "workflow": workflow,
                "branch": branch,
                "event": event,
            },
            actionable=actionable,
            actionable_reason=reason,
        ))
    return findings, None


def _discover_issues(target: Path) -> tuple[Optional[list[dict]], Optional[str]]:
    """Enumerate open issues via `gh issue list` (AC1b).

    Returns `(findings, None)` or `(None, breadcrumb)` on absence / error /
    unparseable JSON. Fingerprinted on the issue `number` (AC8).
    """
    argv = [
        "gh", "issue", "list",
        "--state", "open",
        "--limit", str(ISSUE_LIMIT),
        "--json", _GH_ISSUE_FIELDS,
    ]
    stdout, err = _run_subprocess(argv, cwd=target)
    if err is not None:
        return None, err
    # Empty/whitespace stdout on a clean exit-0 = "ran, found nothing" → empty
    # list, not a parse failure (mirrors _discover_ci; keeps the AC5 health
    # header from mislabeling a healthy-but-empty source `skipped`).
    raw = (stdout or "").strip()
    if not raw:
        issues = []
    else:
        try:
            issues = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, f"gh issue list emitted unparseable JSON: {exc.msg}"
    if not isinstance(issues, list):
        return None, "gh issue list JSON is not a list"

    findings: list[dict] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        number = issue.get("number")
        if number is None:
            continue
        title = str(issue.get("title", "") or "")
        url = str(issue.get("url", "") or "")
        body = str(issue.get("body", "") or "")
        labels = issue.get("labels") if isinstance(issue.get("labels"), list) else []
        # Trim the body for the detail field — the inbox is reviewable, not an
        # issue mirror; the full issue lives behind the url. (The body is also
        # untrusted attacker-influenceable text per guardrail #4 — marked
        # `contributor` provenance below; inert here in 011-02, but kept short
        # regardless.)
        detail = body.strip().splitlines()[0][:200] if body.strip() else ""
        actionable, reason = _classify_issue(labels)
        findings.append(_build_finding(
            source=SOURCE_ISSUE,
            finding_id=_fingerprint(SOURCE_ISSUE, str(number)),
            title=title,
            detail=detail,
            evidence={
                "issue_number": number,
                "url": url,
            },
            actionable=actionable,
            actionable_reason=reason,
        ))
    return findings, None


def _discover_commits(target: Path) -> tuple[Optional[list[dict]], Optional[str]]:
    """Enumerate recent commits via `git log` (AC1c).

    Returns `(findings, None)` or `(None, breadcrumb)` on absence / error.
    Uses a unit-separator-delimited `--pretty` format so each line parses into
    `<sha><US><subject>` deterministically. Fingerprinted on the commit sha
    (AC2). A commit is history/context for the human reviewer, never a dispatch
    candidate, so every commit finding is `actionable: false`
    (`commit_context_only`) per ADR-0010; the actionable-commit signal (a
    revert, a `FIXME`) is a deferred, additive future detector.
    """
    argv = [
        "git", "-C", str(target), "log",
        f"--max-count={COMMIT_LIMIT}",
        f"--pretty=format:{GIT_LOG_FORMAT_TOKEN}",
    ]
    stdout, err = _run_subprocess(argv)
    if err is not None:
        # Distinct breadcrumb wording so a reader can tell git-log-failed apart
        # from gh-absent (AC4).
        return None, f"git log failed ({err})"

    findings: list[dict] = []
    for line in (stdout or "").splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\x1f")
        sha = sha.strip()
        if not sha:
            continue
        findings.append(_build_finding(
            source=SOURCE_COMMIT,
            finding_id=_fingerprint(SOURCE_COMMIT, sha),
            title=subject.strip() or sha,
            detail=f"commit {sha[:12]}",
            evidence={"commit_sha": sha},
            actionable=False,
            actionable_reason=REASON_COMMIT_CONTEXT_ONLY,
        ))
    return findings, None


def _build_finding(
    *,
    source: str,
    finding_id: str,
    title: str,
    detail: str,
    evidence: dict,
    actionable: bool,
    actionable_reason: str,
) -> dict:
    """Construct one FRESHLY-seen v2 finding record (AC1).

    Key insertion order is load-bearing (ADR-0010): `schema_version` first
    (mirrors gate.py / loop.py / ADR-0004), then the IMMUTABLE identity fields
    (`finding_id`/`source`/`provenance`/`discovered_at`), then the STICKY
    lifecycle fields at their first-seen defaults (`status: open`/`attempts:
    0`/`outcome: null`), then the VOLATILE fields refreshed every pass
    (`title`/`detail`/`evidence`/`last_seen_at`/`actionable`/
    `actionable_reason`). `discovered_at == last_seen_at == now` at first sight.

    This builds a NEW finding; the merge (`_merge_findings`) preserves the
    immutable + sticky fields of an EXISTING finding and overwrites only the
    volatile ones from a record built here.
    """
    now = _now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        # immutable
        "finding_id": finding_id,
        "source": source,
        "provenance": _provenance_for(source),
        "discovered_at": now,
        # sticky (first-seen defaults; mutated only by dispatch/human later)
        "status": STATUS_OPEN,
        "attempts": 0,
        "outcome": None,
        # volatile (refreshed every pass the finding is re-observed)
        "title": title,
        "detail": detail,
        "evidence": evidence,
        "last_seen_at": now,
        "actionable": actionable,
        "actionable_reason": actionable_reason,
    }


# Discovery dispatch table (the documented extension point for more sources,
# same shape as the oracle component registry). Each entry maps a source id to
# its enumerator; `discover` walks the table in order so the inbox grouping is
# deterministic.
_DISCOVERY_SOURCES = (
    (SOURCE_CI, _discover_ci),
    (SOURCE_ISSUE, _discover_issues),
    (SOURCE_COMMIT, _discover_commits),
)

# Volatile fields refreshed from a freshly-discovered record onto an existing
# one during merge (AC3). Everything else on an existing record (the immutable
# identity fields + the sticky lifecycle fields) is PRESERVED. `provenance` is
# pointedly NOT here: it is immutable, re-derived from `source` on the fresh
# record, and identical for a stable finding_id — so refreshing it is a no-op,
# and it stays classified as immutable.
_VOLATILE_FIELDS = (
    "title", "detail", "evidence", "last_seen_at",
    "actionable", "actionable_reason",
)


def _read_inbox_for_discover(jsonl_path: Path) -> dict[str, dict]:
    """Load the existing inbox keyed by finding_id, for the discover merge (AC3/AC10).

    Migration (write path, ADR-0010): a record whose `schema_version` is not the
    current version is DROPPED — it is re-derived from live signals this pass.
    This is lossless for the v1→v2 step (a v1 record carried no sticky lifecycle;
    011-01 wrote `status: open` always) and friendlier than a hard refuse for a
    fully re-derivable artifact. A missing / torn / unreadable inbox is treated
    as empty (rebuild from scratch) — the atomic-write discipline means a torn
    file is not expected, but discovery must never hard-fail on a bad read.
    """
    if not jsonl_path.exists():
        return {}
    try:
        text = jsonl_path.read_text()
    except OSError:
        return {}
    existing: dict[str, dict] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # skip a torn line; the rest of the inbox still loads
        if not isinstance(rec, dict):
            continue
        # Drop any non-current-version record — it is re-derived this pass.
        if rec.get("schema_version") != SCHEMA_VERSION:
            continue
        fid = rec.get("finding_id")
        if isinstance(fid, str):
            existing[fid] = rec
    return existing


def _merge_findings(
    existing: dict[str, dict], fresh: list[dict],
) -> list[dict]:
    """Merge freshly-discovered findings into the existing inbox (AC3/AC4/AC5).

    The uniform rule (ADR-0010), applied across all sources:

    - **Existing finding_id re-observed this pass** — preserve its immutable
      (`finding_id`/`source`/`provenance`/`discovered_at`) and sticky
      (`status`/`attempts`/`outcome`) fields; refresh its volatile fields from
      the fresh record. This is RESUME: a `tried`/`passed`/`skipped` finding is
      never reset to `open` (AC4).
    - **Newly-seen finding_id** — append it as-built (`status: open`,
      `discovered_at == last_seen_at == now`, `attempts: 0`, `outcome: null`).
    - **Retention (AC5):** an EXISTING finding NOT re-observed this pass is
      EVICTED if its status is `open`, and RETAINED if its status is sticky
      (`tried`/`passed`/`skipped`) — an audit trail. One rule bounds growth
      across ci / issue / commit, because the unbounded keyspace (commit SHAs,
      CI `headBranch`) is what grows the inbox, not the source label.

    Order: re-observed-or-new findings first (in discovery order, so the inbox
    groups deterministically by source), then retained-but-unseen lifecycle
    findings appended after — keeping the live set at the top for a reviewer.
    """
    seen_ids = {f["finding_id"] for f in fresh}
    merged: list[dict] = []
    for f in fresh:
        prior = existing.get(f["finding_id"])
        if prior is None:
            merged.append(f)
            continue
        # Re-observed: start from the prior (immutable + sticky preserved) and
        # overwrite only the volatile fields with the fresh observation. Rebuild
        # so the key ORDER matches a fresh record (ADR-0010) even if the prior
        # was hand-edited with keys out of order.
        merged.append(_merge_one(prior, f))
    # Retention: keep unseen lifecycle-bearing findings as an audit trail.
    for fid, rec in existing.items():
        if fid in seen_ids:
            continue
        if rec.get("status") in _STICKY_STATUSES:
            merged.append(_normalize_record(rec))
    return merged


def _merge_one(prior: dict, fresh: dict) -> dict:
    """Refresh `prior`'s volatile fields from `fresh`; preserve immutable+sticky.

    Returns a record in canonical v2 key order (the same order `_build_finding`
    emits), so the on-disk inbox is order-stable regardless of how `prior` was
    serialized (e.g. a hand-edit).
    """
    merged = dict(prior)
    for key in _VOLATILE_FIELDS:
        merged[key] = fresh[key]
    # `provenance` is immutable — re-derive from source to heal any drift from a
    # hand-edited inbox (it cannot legitimately differ for a stable finding_id).
    merged["provenance"] = _provenance_for(merged.get("source", fresh["source"]))
    return _normalize_record(merged)


def _normalize_record(rec: dict) -> dict:
    """Return `rec` re-emitted in the canonical v2 key order (ADR-0010).

    Used for both merged and retained records so the inbox is byte-stable under
    re-serialization. Missing sticky defaults are backfilled defensively (a
    well-formed v2 record already has them).
    """
    source = rec.get("source", "")
    return {
        "schema_version": SCHEMA_VERSION,
        "finding_id": rec.get("finding_id", ""),
        "source": source,
        "provenance": rec.get("provenance") or _provenance_for(source),
        "discovered_at": rec.get("discovered_at", ""),
        "status": rec.get("status", STATUS_OPEN),
        "attempts": rec.get("attempts", 0),
        "outcome": rec.get("outcome", None),
        "title": rec.get("title", ""),
        "detail": rec.get("detail", ""),
        "evidence": rec.get("evidence", {}),
        "last_seen_at": rec.get("last_seen_at", rec.get("discovered_at", "")),
        "actionable": bool(rec.get("actionable", False)),
        "actionable_reason": rec.get("actionable_reason", ""),
    }


@contextmanager
def _inbox_lock(triage_dir: Path) -> Iterator[str]:
    """Advisory, non-blocking `flock` around the read-merge-write (AC8, ADR-0010).

    Yields a status string the caller switches on:
      - `"locked"`     — the lock is held; proceed with the merge.
      - `"contended"`  — another run holds the lock; the caller does the
                         lock-contended no-op (breadcrumb + exit 0).
      - `"unlocked"`   — `fcntl` is unavailable (non-POSIX); proceed UNLOCKED
                         (atomic write still prevents torn files; only the
                         lost-update race is unguarded).

    The lock is taken on a SEPARATE, persistent `.inbox.lock` file — never on
    `inbox.jsonl`, whose inode `os.replace` swaps. The file is NEVER unlinked:
    unlinking races the flock, and the kernel releases the lock on process exit
    anyway, so no stale lock can persist. A `flock` `OSError` (a broken
    environment) propagates to the caller, which maps it to rc=2.
    """
    if fcntl is None:
        # Non-POSIX host: no flock available. Proceed unlocked (the caller emits
        # the one-time breadcrumb); the atomic write still prevents torn files.
        yield "unlocked"
        return
    lock_path = triage_dir / INBOX_LOCK_NAME
    # Open (creating if needed) the persistent lock file. We deliberately do NOT
    # unlink it on exit; closing the fd releases our reference, and the kernel
    # releases the advisory lock when this process exits.
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Another discover holds the lock — refuse, don't wait (a double-fire
            # has nothing unique to add). The caller exits 0 with a breadcrumb.
            yield "contended"
            return
        try:
            yield "locked"
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _atomic_write(path: Path, payload: str) -> None:
    """Write `payload` to `path` atomically (ADR-0004's atomic-write contract).

    Writes the full payload to `<name>.tmp`, then `os.replace`s onto the final
    path. `os.replace` is atomic on POSIX and NTFS, so a Ctrl-C / SIGTERM /
    power loss mid-write can never leave a torn artifact for the next reader or
    the next heartbeat. Concurrent double-fire safety (the lost-update race the
    merge introduces) is provided separately by `_inbox_lock` (AC8); this helper
    is the single-writer torn-write guard it composes with.
    """
    tmp = path.with_name(path.name + TMP_SUFFIX)
    tmp.write_text(payload)
    os.replace(tmp, path)


def _render_jsonl(findings: list[dict]) -> str:
    """Serialize findings to JSONL — one JSON object per line."""
    if not findings:
        return ""
    return "\n".join(json.dumps(f) for f in findings) + "\n"


def _status_counts(findings: list[dict]) -> dict[str, int]:
    """Count findings by lifecycle status, over the full lifecycle vocabulary."""
    counts = {STATUS_OPEN: 0, STATUS_TRIED: 0, STATUS_PASSED: 0, STATUS_SKIPPED: 0}
    for f in findings:
        st = f.get("status", STATUS_OPEN)
        counts[st] = counts.get(st, 0) + 1
    return counts


def _render_markdown(
    findings: list[dict], source_status: dict[str, dict], target: Path,
) -> str:
    """Render the human-reviewable `inbox.md` view (AC5 + 011-02 AC11).

    Opens with the generated-view marker and a per-source status header (each
    source `ran` + finding count, or `skipped` + cause), then a **lifecycle
    summary** (counts by status — the state-spine read-back a reviewer scans),
    THEN the findings grouped by source. Each finding now shows its lifecycle
    `status`, its `actionable` verdict + machine reason, and an evidence ref.
    The header makes a silently-degraded unattended run (e.g. a missing `gh`
    auth surfacing an empty-looking inbox) visible in the artifact a human
    reviews — not only in the stderr breadcrumb.
    """
    lines: list[str] = []
    lines.append(GENERATED_MARKER)
    lines.append("")
    lines.append(f"# servo triage inbox — {target.name}")
    lines.append("")
    lines.append(f"_Discovered at {_now_iso()}._")
    lines.append("")
    lines.append("## Source status")
    lines.append("")
    for source, _enum in _DISCOVERY_SOURCES:
        info = source_status.get(source, {})
        if info.get("ran"):
            count = info.get("count", 0)
            lines.append(f"- **{source}**: ran ({count} finding"
                         f"{'' if count == 1 else 's'})")
        else:
            cause = info.get("cause", "unknown")
            lines.append(f"- **{source}**: skipped ({cause})")
    lines.append("")

    # Lifecycle summary (011-02 AC11) — counts by status across the whole inbox,
    # plus the open-actionable candidate count a dispatch pass (011-03) would act
    # on. This is the state-spine read-back surfaced in the human view.
    counts = _status_counts(findings)
    actionable_open = sum(
        1 for f in findings
        if f.get("status") == STATUS_OPEN and f.get("actionable")
    )
    lines.append("## Lifecycle")
    lines.append("")
    lines.append(
        f"- open: {counts[STATUS_OPEN]} "
        f"(actionable: {actionable_open}) · tried: {counts[STATUS_TRIED]} · "
        f"passed: {counts[STATUS_PASSED]} · skipped: {counts[STATUS_SKIPPED]}"
    )
    lines.append("")

    total = len(findings)
    lines.append(f"## Findings ({total})")
    lines.append("")
    if total == 0:
        lines.append("_No findings this pass._")
        lines.append("")
        return "\n".join(lines) + "\n"

    for source, _enum in _DISCOVERY_SOURCES:
        group = [f for f in findings if f["source"] == source]
        if not group:
            continue
        lines.append(f"### {source} ({len(group)})")
        lines.append("")
        for f in group:
            ref = _evidence_ref(f)
            title = f.get("title", "") or "(untitled)"
            verdict = "actionable" if f.get("actionable") else "not-actionable"
            lines.append(f"- [{f['status']}] {title}" + (f" — {ref}" if ref else ""))
            # Render the actionable verdict + machine reason on an indented line
            # so a reviewer sees WHY a finding is (not) a dispatch candidate
            # without re-deriving it. The reason is the stored machine code.
            reason = f.get("actionable_reason", "") or ""
            lines.append(f"  - {verdict}"
                         + (f" ({reason})" if reason else ""))
            # Render the detail beneath the title when present — for a CI
            # finding this surfaces the run's displayTitle/conclusion, which is
            # what a reviewer scans to triage "is this worth a loop?". Kept on
            # its own indented line so the title line stays a clean one-liner.
            detail = (f.get("detail", "") or "").strip()
            if detail:
                lines.append(f"  - {detail}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _evidence_ref(finding: dict) -> str:
    """Pick a single human-facing evidence reference (URL or sha) for a finding."""
    ev = finding.get("evidence", {})
    if not isinstance(ev, dict):
        return ""
    for key in ("url", "run_url"):
        val = ev.get(key)
        if val:
            return str(val)
    sha = ev.get("commit_sha")
    if sha:
        return str(sha)
    number = ev.get("issue_number")
    if number is not None:
        return f"#{number}"
    return ""


def _emit_breadcrumb(message: str) -> None:
    """Write a single-line `heartbeat: ...` breadcrumb to stderr."""
    sys.stderr.write(f"heartbeat: {message}\n")


def run_discover(target: Path) -> int:
    """Read-only discovery pass + lock-guarded merge into the state spine (AC1/AC3).

    Validates the target, bootstraps `<target>/.servo/triage/` (AC9), walks the
    discovery dispatch table degrading each source independently (AC4), then —
    under an advisory `flock` on `.inbox.lock` (AC8) — reads the existing inbox,
    MERGES the fresh findings by `finding_id` (preserving immutable + sticky
    fields, refreshing volatile fields, applying the retention bound; AC3/AC4/
    AC5), and atomically writes `inbox.jsonl` + `inbox.md` (AC11). Returns the
    closed `{0, 2}` exit code: 2 only on an env error that prevents writing at
    all (incl. a `flock` `OSError`); 0 in every other case, including
    all-sources-skipped AND a lock-contended double-fire (the other run is
    maintaining the inbox — nothing failed).
    """
    # ---- Env preconditions (the only paths that exit 2) --------------------
    if not target.exists():
        _emit_breadcrumb(f"target does not exist: {target} (target_missing)")
        return EXIT_ENV_ERROR
    if not target.is_dir():
        _emit_breadcrumb(
            f"target is not a directory: {target} (target_not_directory)"
        )
        return EXIT_ENV_ERROR

    # ---- Triage dir bootstrap (AC9) ----------------------------------------
    triage_dir = target / ".servo" / TRIAGE_DIRNAME
    try:
        triage_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _emit_breadcrumb(
            f"cannot create triage dir {triage_dir}: {exc} (triage_dir_unwritable)"
        )
        return EXIT_ENV_ERROR

    # ---- Oracle-independence breadcrumb (AC9) ------------------------------
    # Discovery is oracle-INDEPENDENT: it never refuses on a missing oracle.
    # It records a breadcrumb noting dispatch will be unavailable until the
    # target is scaffolded (the oracle gate lives at dispatch, 011-03).
    manifest = target / ".servo" / "install.json"
    oracle = target / "oracle.sh"
    if not manifest.exists() or not oracle.exists():
        _emit_breadcrumb(
            f"no oracle/manifest at {target} — discovery only; "
            f"dispatch unavailable until /servo:scaffold-init"
        )

    # ---- Walk the discovery dispatch table (AC1/AC4) -----------------------
    # All subprocess calls (the read-only `gh`/`git` enumeration) happen here,
    # BEFORE the lock — we hold the advisory lock only around the fast
    # read-merge-write, not across network-backed discovery, so a contended
    # double-fire is detected promptly.
    fresh: list[dict] = []
    source_status: dict[str, dict] = {}
    skipped_sources: list[str] = []
    for source, enumerator in _DISCOVERY_SOURCES:
        source_findings, err = enumerator(target)
        if err is not None or source_findings is None:
            cause = err or "unknown error"
            source_status[source] = {"ran": False, "cause": cause}
            skipped_sources.append(source)
            # Distinct, source-naming stderr breadcrumb (AC4).
            _emit_breadcrumb(f"{cause} — skipping {source} source")
            continue
        source_status[source] = {"ran": True, "count": len(source_findings)}
        fresh.extend(source_findings)

    jsonl_path = triage_dir / INBOX_JSONL_NAME
    md_path = triage_dir / INBOX_MD_NAME

    # ---- Lock-guarded read-merge-write (AC3/AC5/AC8) -----------------------
    try:
        with _inbox_lock(triage_dir) as lock_state:
            if lock_state == "contended":
                # Another discover holds the lock — refuse, don't wait. Exit 0:
                # the inbox is being maintained by the other run (AC8); the
                # structured reason keeps the no-op observable without a new code.
                _emit_breadcrumb(
                    f"another discover is maintaining {jsonl_path}; "
                    f"skipping this pass (lock_contended)"
                )
                return EXIT_OK
            if lock_state == "unlocked":
                # Non-POSIX host: proceeding without the lost-update guard.
                _emit_breadcrumb(
                    "fcntl unavailable (non-POSIX); proceeding without the "
                    "double-fire lock (atomic write still prevents torn files)"
                )
            # Merge the fresh findings into the existing inbox, then write both
            # artifacts atomically. Reading inside the lock so a concurrent
            # writer can't slip an update between our read and write.
            existing = _read_inbox_for_discover(jsonl_path)
            findings = _merge_findings(existing, fresh)
            try:
                _atomic_write(jsonl_path, _render_jsonl(findings))
                _atomic_write(
                    md_path, _render_markdown(findings, source_status, target)
                )
            except OSError as exc:
                _emit_breadcrumb(
                    f"cannot write triage artifacts under {triage_dir}: {exc} "
                    f"(triage_dir_unwritable)"
                )
                return EXIT_ENV_ERROR
    except OSError as exc:
        # A `flock` OSError (broken environment) — distinct from the
        # BlockingIOError contention path, which the lock CM handles internally.
        _emit_breadcrumb(
            f"cannot acquire inbox lock under {triage_dir}: {exc} "
            f"(triage_dir_unwritable)"
        )
        return EXIT_ENV_ERROR

    # ---- Summary breadcrumb (AC4 — visible even on the all-skipped path) ---
    ran = [s for s, info in source_status.items() if info.get("ran")]
    if not ran:
        _emit_breadcrumb(
            f"all sources skipped ({', '.join(skipped_sources)}); "
            f"wrote inbox to {jsonl_path}"
        )
    else:
        _emit_breadcrumb(
            f"merged {len(fresh)} discovered finding"
            f"{'' if len(fresh) == 1 else 's'} from {len(ran)} source"
            f"{'' if len(ran) == 1 else 's'}; inbox now holds {len(findings)} "
            f"→ {jsonl_path}"
        )
    return EXIT_OK


def _read_inbox_for_status(jsonl_path: Path) -> tuple[Optional[list[dict]], Optional[str]]:
    """Read the inbox for the read-only `status` verb (AC9/AC10/AC1).

    Returns `(records, None)` on a readable inbox (an empty list for a missing /
    empty inbox), or `(None, cause)` to refuse with rc=2. The version rules
    (ADR-0010, a deliberate divergence from ADR-0004's hard-refuse, justified by
    the inbox being re-derivable):

      - **higher unknown version** (`> SCHEMA_VERSION`, forward-incompatible) →
        refuse, cause `schema_version_unsupported`.
      - **mixed versions** in one file (corruption; AC1's "all records carry the
        same version") → refuse, cause `schema_version_mixed`.
      - **lower known version** (all records one version `< SCHEMA_VERSION`) →
        do NOT refuse; the caller WARNS and best-effort displays (v1 is a
        readable subset). Returned as records with a side-channel warning the
        caller emits (we signal "lower" by returning records whose min version
        is below current; the caller compares and warns).

    `status` never rebuilds (it is read-only) — unlike `discover`'s write path.
    """
    if not jsonl_path.exists():
        return [], None
    try:
        text = jsonl_path.read_text()
    except OSError as exc:
        return None, f"cannot read inbox: {exc} (inbox_unreadable)"
    records: list[dict] = []
    versions: set = set()
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            # A torn line on the read path is best-effort skipped (status never
            # mutates and never gates); the version checks below still apply to
            # the records that did parse.
            continue
        if not isinstance(rec, dict):
            continue
        versions.add(rec.get("schema_version"))
        records.append(rec)
    if not records:
        return [], None
    if any(isinstance(v, int) and v > SCHEMA_VERSION for v in versions):
        return None, "schema_version_unsupported"
    if len(versions) > 1:
        return None, "schema_version_mixed (records disagree on schema_version)"
    return records, None


def run_status(target: Path, *, as_json: bool = False) -> int:
    """Read-only read-back of the triage state spine (AC9).

    Reads `<target>/.servo/triage/inbox.jsonl` and prints either a human summary
    (default — counts by status, by source, by actionability, plus the
    open-actionable candidate list with each candidate's `last_seen_at`) or a
    machine summary under `--json` (carrying `schema_version`). Closed `{0, 2}`
    exit: 0 = read OK (incl. an empty/absent inbox); 2 = env error (target
    missing / not a directory / inbox unreadable) or `schema_version_unsupported`
    (a higher unknown version). NEVER mutates and NEVER gates (no exit 1).
    """
    # ---- Env preconditions (the only paths that exit 2) --------------------
    if not target.exists():
        _emit_breadcrumb(f"target does not exist: {target} (target_missing)")
        return EXIT_ENV_ERROR
    if not target.is_dir():
        _emit_breadcrumb(
            f"target is not a directory: {target} (target_not_directory)"
        )
        return EXIT_ENV_ERROR

    jsonl_path = target / ".servo" / TRIAGE_DIRNAME / INBOX_JSONL_NAME
    records, cause = _read_inbox_for_status(jsonl_path)
    if cause is not None:
        _emit_breadcrumb(f"cannot read triage inbox: {cause}")
        return EXIT_ENV_ERROR

    # A lower-known-version inbox (all v<current) is displayed best-effort with a
    # warning (AC10) — the read path is friendly, only the write path rebuilds.
    present_versions = {
        r.get("schema_version") for r in records
        if isinstance(r.get("schema_version"), int)
    }
    if present_versions and max(present_versions) < SCHEMA_VERSION:
        _emit_breadcrumb(
            f"inbox schema_version {max(present_versions)} < {SCHEMA_VERSION}; "
            f"displaying best-effort (run `discover` to rebuild at current schema)"
        )

    summary = _summarize_inbox(records)
    if as_json:
        sys.stdout.write(json.dumps(summary) + "\n")
    else:
        sys.stdout.write(_render_status_human(summary, target))
    return EXIT_OK


def _summarize_inbox(records: list[dict]) -> dict:
    """Build the machine summary for `status --json` (AC9).

    Carries `schema_version` (first key, like every artifact), the total, counts
    by status / source / actionability, and the open-actionable candidate list
    (each with finding_id, source, title, last_seen_at) — the dispatch candidate
    set 011-03 will consume, surfaced read-only here.
    """
    by_status: dict[str, int] = {}
    by_source: dict[str, int] = {}
    actionable_count = 0
    candidates: list[dict] = []
    for r in records:
        st = str(r.get("status", STATUS_OPEN))
        by_status[st] = by_status.get(st, 0) + 1
        src = str(r.get("source", ""))
        by_source[src] = by_source.get(src, 0) + 1
        if r.get("actionable"):
            actionable_count += 1
        if st == STATUS_OPEN and r.get("actionable"):
            candidates.append({
                "finding_id": r.get("finding_id", ""),
                "source": src,
                "title": r.get("title", ""),
                "last_seen_at": r.get("last_seen_at", ""),
                "actionable_reason": r.get("actionable_reason", ""),
            })
    return {
        "schema_version": SCHEMA_VERSION,
        "total": len(records),
        "counts": {
            "by_status": by_status,
            "by_source": by_source,
            "actionable": actionable_count,
            "open_actionable": len(candidates),
        },
        "open_actionable_candidates": candidates,
    }


def _render_status_human(summary: dict, target: Path) -> str:
    """Render the human `status` summary (AC9).

    Counts by status, by source, by actionability, then the open-actionable
    candidate list with each candidate's `last_seen_at` — the read-back a human
    scans to see what the next dispatch pass would act on.
    """
    counts = summary["counts"]
    by_status = counts["by_status"]
    by_source = counts["by_source"]
    lines: list[str] = []
    lines.append(f"servo triage inbox — {target.name}")
    lines.append(f"total findings: {summary['total']}")
    lines.append("")
    lines.append("by status:")
    for st in (STATUS_OPEN, STATUS_TRIED, STATUS_PASSED, STATUS_SKIPPED):
        lines.append(f"  {st}: {by_status.get(st, 0)}")
    # Any non-standard status (e.g. a hand-edit) is surfaced rather than hidden.
    for st in sorted(s for s in by_status
                     if s not in (STATUS_OPEN, STATUS_TRIED,
                                  STATUS_PASSED, STATUS_SKIPPED)):
        lines.append(f"  {st}: {by_status[st]}")
    lines.append("")
    lines.append("by source:")
    for src in sorted(by_source):
        lines.append(f"  {src}: {by_source[src]}")
    lines.append("")
    lines.append(
        f"actionable: {counts['actionable']} "
        f"(open-actionable candidates: {counts['open_actionable']})"
    )
    lines.append("")
    candidates = summary["open_actionable_candidates"]
    if candidates:
        lines.append("open-actionable candidates:")
        for c in candidates:
            lines.append(
                f"  - [{c['source']}] {c['title'] or '(untitled)'} "
                f"(last_seen_at={c['last_seen_at']})"
            )
    else:
        lines.append("open-actionable candidates: none")
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="heartbeat.py",
        description=(
            "The scheduled front-end of the servo loop. Subcommands mirror "
            "the house pattern; `discover` (read-only signal discovery → triage "
            "inbox state spine) and `status` (read-only read-back) ship. "
            "`dispatch` / `run` are later slices."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser(
        "discover",
        help=(
            "Read-only pass over CI failures (gh), open issues (gh), and "
            "recent commits (git); write findings to "
            "<target>/.servo/triage/inbox.jsonl + a generated inbox.md."
        ),
        description=(
            "Strictly read-only discovery: writes ONLY under "
            "<target>/.servo/triage/. Each source degrades independently — a "
            "missing gh / an auth error / one source failing skips that source "
            "with a stderr breadcrumb and continues. Closed {0,2} exit "
            "contract: 0 = completed (zero or more findings); 2 = env error "
            "preventing any write."
        ),
    )
    discover_parser.add_argument(
        "target",
        type=Path,
        help="Path to the target project (discovery is oracle-independent).",
    )

    status_parser = subparsers.add_parser(
        "status",
        help=(
            "Read-only read-back of the triage state spine: counts by status / "
            "source / actionability + the open-actionable candidate list."
        ),
        description=(
            "Strictly read-only: reads <target>/.servo/triage/inbox.jsonl and "
            "prints a human summary (default) or a machine summary (--json, "
            "carrying schema_version). Never mutates, never gates. Closed {0,2} "
            "exit: 0 = read OK (incl. an empty/absent inbox); 2 = env error or a "
            "higher unknown schema_version (schema_version_unsupported)."
        ),
    )
    status_parser.add_argument(
        "target",
        type=Path,
        help="Path to the target project whose inbox is read back.",
    )
    status_parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit the machine summary as JSON (carrying schema_version).",
    )

    args = parser.parse_args(argv)

    if args.command == "discover":
        return run_discover(args.target.resolve())
    if args.command == "status":
        return run_status(args.target.resolve(), as_json=args.as_json)

    # argparse `required=True` guarantees a known subcommand; this is a
    # defensive fallback only.
    parser.error(f"unknown command: {args.command}")
    return EXIT_ENV_ERROR  # unreachable — parser.error exits


if __name__ == "__main__":
    sys.exit(main())
