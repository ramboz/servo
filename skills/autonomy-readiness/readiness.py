#!/usr/bin/env python3
"""
servo autonomy-readiness — slice 023-01 (readiness verdict + human approval).

The Compile-phase gate *upstream* of `edd-suitability`: before an unattended
long-horizon loop may start, review the goal's scope + initial prompt and emit a
closed three-state **readiness verdict** — `ready | needs_tightening |
unsafe_for_autonomy` — written atomically to
`<target>/.servo/readiness/<goal-id>.json`. Human-owned: the artifact starts
`approval_status: "proposed"` and is never auto-approved; a human reviews the
scorecard and flips it to `approved` (the `approve` verb). A `check` consumer
contract exposes the deterministic gate a launcher will consult (023-02 wires
`loop.py` to it).

Two check tiers (matching servo's deterministic-vs-model split) plus a
conditional identity posture compose the verdict:

- *Deterministic / offline:* oracle present + executable; ≥1 approved (non-draft)
  component; finite budget / iteration / max-candidates caps; clean tree +
  worktree isolation; an explicit mutation perimeter. All local, offline facts.
- *Model-judged:* the prompt itself is scored on Precision, Scope-boundedness,
  Stop/escalation conditions, Safety surface, and Internal contradiction — via
  `eval-authoring`'s expand-then-independent-review two-call pattern.
- *Identity posture (conditional, best-effort — networked):* only when the run
  **declares** an autonomous land/merge capability AND a host probe confirms the
  run principal can merge the base branch does identity collapse force
  `unsafe_for_autonomy`; otherwise it is an advisory scorecard note (amended
  ADR-0029), never a silent bless of collapse nor a false refusal.

Usage
-----
    readiness.py analyze <target> (--prompt <brief> | --brief-file <path>)
        [--cost-ceiling F] [--max-iterations N] [--max-candidates N]
        [--mutation-perimeter <path.json>] [--declares-autonomous-merge]
        [--json] [--explain]
    readiness.py approve <target> (--goal-id <id> | --prompt <brief>)
    readiness.py check <target> --prompt <brief>

Exit codes (ADR-0002 / ADR-0015 closed contract)
------------------------------------------------
    analyze : 0 verdict emitted (incl. a non-`ready` verdict) / 2 env error
              (no artifact written). NEVER exits 1.
    approve : 0 approved (or already-approved no-op) / 2 env error (missing
              artifact, or fail-closed refusal to approve an unsafe verdict).
    check   : 0 permit (artifact exists AND approved) / 1 refuse (missing or
              `proposed` — a normal reportable negative) / 2 env error.

No verb ever leaves a torn artifact (tmp + os.replace).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

APPROVAL_PROPOSED = "proposed"
APPROVAL_APPROVED = "approved"

# Closed three-state verdict, ordered worst-last so `_worse()` can rank.
VERDICT_READY = "ready"
VERDICT_NEEDS_TIGHTENING = "needs_tightening"
VERDICT_UNSAFE = "unsafe_for_autonomy"
_VERDICT_RANK = {VERDICT_READY: 0, VERDICT_NEEDS_TIGHTENING: 1, VERDICT_UNSAFE: 2}

# The five ADR-0029 model-judged dimensions scored against the prompt itself.
MODEL_DIMENSIONS = (
    "precision",
    "scope",
    "stop_conditions",
    "safety_surface",
    "contradiction",
)

# GitHub repo permissions that let the viewer merge to the base branch.
_MERGE_CAPABLE_PERMISSIONS = frozenset({"ADMIN", "WRITE", "MAINTAIN"})

# Subprocess seams. Both mirror eval-authoring's env-override idiom so a test (or
# an operator) can point them at a deterministic stand-in without PATH surgery,
# and NEVER calls a live binary in tests.
CLAUDE_BIN_ENV = "SERVO_AUTONOMY_READINESS_CLAUDE_BIN"
GH_BIN_ENV = "SERVO_AUTONOMY_READINESS_GH_BIN"

CLAUDE_PROMPT_TIMEOUT_SECONDS = 300
GH_PROBE_TIMEOUT_SECONDS = 60

# The built-in model-judge framing (used when jig's `clarify` is NOT co-installed).
_BUILT_IN_RUBRIC_PATH = Path(__file__).resolve().parent / "readiness-rubric.md"
_FRAMING_MAX_CHARS = 6000


class EnvError(Exception):
    """An environment error mapped to a closed `reason` + exit 2."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _goal_id(prompt: str) -> str:
    """Deterministic goal-id: sha256 of the whitespace-collapsed prompt, first
    16 hex chars. Standalone on purpose so the `check` verb below can expose it
    as a subprocess contract. **023-02's loop.py should consume the `check`
    contract (subprocess) rather than re-derive this hash** — that keeps a single
    source of truth for the artifact path. If 023-02 ever reads the artifact
    directly instead, it must add a cross-module hash-agreement test pinning its
    derivation to this one (arch-review note, 2026-08-06)."""
    normalized = " ".join(prompt.split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _worse(a: str, b: str) -> str:
    return a if _VERDICT_RANK[a] >= _VERDICT_RANK[b] else b


# ---------------------------------------------------------------------------
# Verdict composition — pure over the scored `checks` list
# ---------------------------------------------------------------------------

def compose_verdict(checks: list) -> dict:
    """Pure: fold the per-check scorecard into the closed three-state verdict.

    Start at `ready`; any `concern` downgrades to at least `needs_tightening`;
    any `unsafe` sets `unsafe_for_autonomy`. `pass` / `info` checks never
    downgrade. The final verdict is the worst tier — fail-closed. Every
    non-passing check's message is reflected into `reasons` so the human sees
    exactly WHY.
    """
    verdict = VERDICT_READY
    reasons: list = []
    for chk in checks:
        status = chk["status"]
        if status == "unsafe":
            verdict = _worse(verdict, VERDICT_UNSAFE)
            reasons.append({"code": chk["code"], "message": chk["message"]})
        elif status == "concern":
            verdict = _worse(verdict, VERDICT_NEEDS_TIGHTENING)
            reasons.append({"code": chk["code"], "message": chk["message"]})
    if not reasons:
        reasons.append({
            "code": "all_clear",
            "message": "every deterministic, model-judged, and identity check passed",
        })
    return {"verdict": verdict, "reasons": reasons}


# ---------------------------------------------------------------------------
# Deterministic / offline tier
# ---------------------------------------------------------------------------

def _check(code: str, tier: str, status: str, message: str) -> dict:
    return {"code": code, "tier": tier, "status": status, "message": message}


def _oracle_check(target: Path) -> dict:
    oracle = target / "oracle.sh"
    if not oracle.is_file():
        return _check(
            "oracle_missing", "deterministic", "concern",
            "no oracle.sh at the target — the loop has no deterministic gate to "
            "converge against; scaffold the oracle first",
        )
    if not os.access(oracle, os.X_OK):
        return _check(
            "oracle_not_executable", "deterministic", "concern",
            "oracle.sh is present but not executable — an unattended run cannot "
            "invoke it; `chmod +x oracle.sh`",
        )
    return _check("oracle_ready", "deterministic", "pass",
                  "oracle.sh is present and executable")


def _approved_component_check(target: Path) -> dict:
    """At least one approved (non-draft) oracle component exists. Scans
    `<target>/.servo/spec-oracles/*/plan.json` for a top-level
    `approval_status == "approved"` (mirrors eval-authoring's scalar approval)."""
    plans_root = target / ".servo" / "spec-oracles"
    approved = False
    if plans_root.is_dir():
        for plan in sorted(plans_root.glob("*/plan.json")):
            try:
                data = json.loads(plan.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(data, dict) and data.get("approval_status") == APPROVAL_APPROVED:
                approved = True
                break
    if approved:
        return _check("approved_component", "deterministic", "pass",
                      "at least one approved oracle component is present")
    return _check(
        "no_approved_component", "deterministic", "concern",
        "no approved (non-draft) oracle component found under "
        ".servo/spec-oracles/*/plan.json — a run would converge against an "
        "unapproved gate; approve at least one component first",
    )


def _cap_check(name: str, value, code: str) -> dict:
    if value is None:
        return _check(
            code, "deterministic", "concern",
            f"no {name} cap set (infinite) — an unattended long-horizon run "
            f"with no {name} ceiling can burn a day on a bad premise; pass a "
            f"finite {name}",
        )
    return _check(code, "deterministic", "pass", f"{name} cap is finite ({value})")


def _isolation_status(target: Path) -> tuple:
    """('clean'|'dirty'|'no_git', detail). Mirrors loop.py's dirty-tree
    preflight: untracked (`??`) files are not counted as changes to tracked
    files, so servo's own run artifacts never self-trip the check."""
    try:
        probe = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except (FileNotFoundError, OSError):
        return ("no_git", "git is not installed")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return ("no_git", "target is not inside a git work tree")
    status = subprocess.run(
        ["git", "-C", str(target), "status", "--porcelain"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if status.returncode != 0:
        return ("no_git", "git status failed")
    dirty = [
        ln for ln in status.stdout.splitlines()
        if ln.strip() and not ln.startswith("??")
    ]
    if dirty:
        return ("dirty", f"{len(dirty)} tracked path(s) with uncommitted changes")
    return ("clean", "clean tree")


def _isolation_check(target: Path) -> dict:
    state, detail = _isolation_status(target)
    if state == "clean":
        return _check("clean_isolated_tree", "deterministic", "pass",
                      "clean git work tree — worktree isolation is available")
    if state == "dirty":
        return _check(
            "dirty_tree", "deterministic", "concern",
            f"dirty work tree ({detail}) — an unattended run would build on "
            "uncommitted changes; commit or stash, or run from an isolated worktree",
        )
    return _check(
        "no_worktree_isolation", "deterministic", "concern",
        f"no git worktree isolation ({detail}) — an unattended run has no clean "
        "base to branch from; run from a git worktree",
    )


def _mutation_perimeter_check(perimeter_path) -> dict:
    if perimeter_path is None:
        return _check(
            "no_mutation_perimeter", "deterministic", "concern",
            "no explicit mutation perimeter (--mutation-perimeter) — an "
            "unattended run has no allowlist/denylist bounding what it may "
            "change; declare one",
        )
    path = Path(perimeter_path)
    if not path.is_file():
        return _check(
            "mutation_perimeter_missing", "deterministic", "concern",
            f"mutation perimeter file not found: {path}",
        )
    try:
        json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        return _check(
            "mutation_perimeter_malformed", "deterministic", "concern",
            f"mutation perimeter is not valid JSON: {exc}",
        )
    return _check("mutation_perimeter", "deterministic", "pass",
                  f"explicit mutation perimeter present ({path})")


def deterministic_checks(target: Path, *, cost_ceiling, max_iterations,
                         max_candidates, mutation_perimeter) -> list:
    """The offline, deterministic tier — one `{code, tier, status, message}`
    entry per precondition, in a stable order."""
    return [
        _oracle_check(target),
        _approved_component_check(target),
        _cap_check("cost-ceiling", cost_ceiling, "budget_cap"),
        _cap_check("max-iterations", max_iterations, "iteration_cap"),
        _cap_check("max-candidates", max_candidates, "candidate_cap"),
        _isolation_check(target),
        _mutation_perimeter_check(mutation_perimeter),
    ]


# ---------------------------------------------------------------------------
# Model-judged tier — expand-then-independent-review (reuse eval-authoring)
# ---------------------------------------------------------------------------

def _resolve_claude() -> "str | None":
    return os.environ.get(CLAUDE_BIN_ENV) or shutil.which("claude")


def _jig_clarify_skill_path() -> "Path | None":
    """Filesystem-hint probe (ADR-0001 / ADR-0029 reuse-seam): is jig's
    `clarify` skill installed at USER scope? Mirrors eval-authoring's
    `_jig_independent_review_skill_path` exactly — a user-scope
    `~/.claude/skills/clarify/SKILL.md`, honoring `$HOME` so it stays
    hermetically testable. Conservative on every error: the built-in rubric is
    always a safe fallback (servo does NOT hard-depend on jig — no import,
    subprocess + filesystem only)."""
    try:
        candidate = Path.home() / ".claude" / "skills" / "clarify" / "SKILL.md"
        if candidate.is_file():
            return candidate
    except (OSError, ValueError, RuntimeError):
        pass
    return None


def _review_framing_text(jig_skill_path) -> str:
    """The framing preamble for the prompt-scoring calls: jig's detected
    `clarify` skill content when co-installed, else the built-in
    `readiness-rubric.md`. Degrades to the built-in on any read failure of a
    detected jig file rather than crashing."""
    if jig_skill_path is not None:
        try:
            return jig_skill_path.read_text()[:_FRAMING_MAX_CHARS]
        except OSError:
            pass
    try:
        return _BUILT_IN_RUBRIC_PATH.read_text()[:_FRAMING_MAX_CHARS]
    except OSError as exc:
        # The rubric ships with the skill, so this is unlikely — but keep the
        # analyze route's "never exit 1" contract total by degrading to a
        # fail-closed EnvError (→ model_tier_unavailable concern) rather than
        # letting an OSError crash (craft-review nit, 2026-08-06).
        raise EnvError(
            "rubric_unreadable",
            f"built-in readiness rubric is unreadable: {exc}",
        ) from exc


def _invoke_claude_prompt(prompt: str) -> str:
    """One fresh, one-shot `claude -p --output-format json <prompt>` call —
    used for BOTH the expansion and the independent-review steps. Mirrors
    eval-authoring's `_invoke_claude_prompt`. Raises EnvError on any failure;
    never fabricates a reply."""
    claude = _resolve_claude()
    if not claude:
        raise EnvError(
            "claude_not_found",
            f"claude CLI not found — set {CLAUDE_BIN_ENV} or add it to PATH",
        )
    cmd = [claude, "-p", "--output-format", "json", prompt]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=CLAUDE_PROMPT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise EnvError("claude_not_found", f"claude CLI not found: {exc}") from exc
    except subprocess.TimeoutExpired:
        raise EnvError(
            "claude_timeout",
            f"claude -p timed out after {CLAUDE_PROMPT_TIMEOUT_SECONDS}s",
        ) from None
    if proc.returncode != 0:
        raise EnvError(
            "claude_invocation_failed",
            f"claude -p exited {proc.returncode}: {proc.stderr.strip()[:300]}",
        )
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise EnvError(
            "claude_malformed_envelope", f"claude -p output is not valid JSON: {exc}"
        ) from exc
    if not isinstance(envelope, dict):
        raise EnvError("claude_malformed_envelope", "claude -p output is not an object")
    if envelope.get("is_error"):
        raise EnvError(
            "claude_invocation_failed",
            f"claude -p reported an error: {str(envelope.get('result'))[:300]}",
        )
    return str(envelope.get("result", ""))


def _extract_json_object(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise EnvError("model_unparseable", "no JSON object found in the model reply")
    return text[start:end + 1]


_EXPANSION_TEMPLATE = """\
{framing}

You are scoring an INITIAL PROMPT that is about to be handed to an unattended, \
long-horizon agent loop. Score the prompt ITSELF (not any code) on each of the \
five readiness dimensions below. Reply "concern" for a dimension when the prompt \
is deficient on it, "ok" otherwise.

Dimensions: precision, scope, stop_conditions, safety_surface, contradiction.

INITIAL PROMPT:
{brief}

Reply with ONLY a JSON object, no other text, in this exact shape:
{{"scores": [{{"dimension": "precision|scope|stop_conditions|safety_surface|\
contradiction", "status": "ok|concern", "note": "<one line: why>"}}, ...]}}
"""

_REVIEW_TEMPLATE = """\
{framing}

You are an INDEPENDENT reviewer. You do NOT have access to the reasoning that \
produced the scores below — only the initial prompt text and the proposed \
per-dimension verdicts. Confirm or challenge them.

INITIAL PROMPT (verbatim):
{brief}

PROPOSED SCORES (dimension → verdict only, no reasoning):
{score_lines}

Reply with ONLY a JSON object, no other text, in this exact shape:
{{"flags": [{{"dimension": "precision|scope|stop_conditions|safety_surface|\
contradiction", "note": "<one or two sentences>"}}, ...]}}
If you agree with every proposed score, reply with {{"flags": []}}.
"""


def _render_expansion_prompt(brief: str, framing: str) -> str:
    return _EXPANSION_TEMPLATE.format(framing=framing, brief=brief)


def _render_review_prompt(brief: str, scores: list, framing: str) -> str:
    """The independent-review prompt carries ONLY the brief and the proposed
    per-dimension verdicts — never the expansion's `note`/reasoning — so the
    reviewer's independence is a fresh, separate call, not a continuation."""
    score_lines = "\n".join(
        f'- {s["dimension"]}: {s["status"]}' for s in scores
    )
    return _REVIEW_TEMPLATE.format(framing=framing, brief=brief,
                                   score_lines=score_lines)


def _load_model_json(text: str) -> dict:
    """Parse a model reply's JSON object, mapping ANY malformed payload to an
    `EnvError` so `model_checks` degrades to a fail-closed concern rather than
    crashing `analyze` (which must never exit 1). `_extract_json_object` already
    raises `EnvError` when no braces are present; this closes the
    braces-present-but-invalid case (truncated reply, trailing comma, single
    quotes — all things LLMs emit)."""
    raw = _extract_json_object(text)
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise EnvError(
            "model_unparseable", f"the model reply was not valid JSON ({exc})"
        ) from exc
    if not isinstance(obj, dict):
        raise EnvError("model_malformed", "the model reply was not a JSON object")
    return obj


def _parse_scores(text: str) -> list:
    obj = _load_model_json(text)
    scores = obj.get("scores")
    if not isinstance(scores, list) or not scores:
        raise EnvError("model_empty", "the model reply carried no dimension scores")
    parsed = []
    for i, entry in enumerate(scores):
        if not isinstance(entry, dict):
            raise EnvError("model_malformed", f"scores[{i}] is not an object")
        dim = entry.get("dimension")
        status = entry.get("status")
        if dim not in MODEL_DIMENSIONS:
            raise EnvError("model_malformed", f"scores[{i}].dimension {dim!r} unknown")
        if status not in ("ok", "concern"):
            raise EnvError("model_malformed", f"scores[{i}].status {status!r} invalid")
        parsed.append({
            "dimension": dim,
            "status": status,
            "note": str(entry.get("note", "")).strip(),
        })
    # Fail-closed on a partial reply: every dimension must be scored, else we
    # cannot confirm the premise and silently treating omitted dimensions as
    # `ok` would weaken the gate (craft-review nit, 2026-08-06).
    if {p["dimension"] for p in parsed} != set(MODEL_DIMENSIONS):
        raise EnvError(
            "model_incomplete",
            "the model reply did not score all five premise dimensions",
        )
    return parsed


def _parse_flags(text: str) -> list:
    obj = _load_model_json(text)
    flags = obj.get("flags")
    if not isinstance(flags, list):
        raise EnvError("model_malformed", "the review reply has no flags list")
    parsed = []
    for i, entry in enumerate(flags):
        if not isinstance(entry, dict):
            raise EnvError("model_malformed", f"flags[{i}] is not an object")
        dim = entry.get("dimension")
        if dim not in MODEL_DIMENSIONS:
            raise EnvError("model_malformed", f"flags[{i}].dimension {dim!r} unknown")
        parsed.append({"dimension": dim, "note": str(entry.get("note", "")).strip()})
    return parsed


def model_checks(brief: str) -> list:
    """The model-judged tier: expand-then-independent-review over the prompt.

    Fail-closed and best-effort: if `claude` cannot be resolved or the reply is
    unparseable, emit a single `model_tier_unavailable` CONCERN (never a silent
    `ready`) — we cannot confirm the premise is precise enough, so the verdict
    is at least `needs_tightening`.
    """
    jig_path = _jig_clarify_skill_path()
    try:
        framing = _review_framing_text(jig_path)
        scores = _parse_scores(
            _invoke_claude_prompt(_render_expansion_prompt(brief, framing))
        )
        flags = _parse_flags(
            _invoke_claude_prompt(_render_review_prompt(brief, scores, framing))
        )
    except EnvError as exc:
        return [_check(
            "model_tier_unavailable", "model", "concern",
            f"could not run the premise-quality review ({exc}); cannot confirm "
            "the brief is precise/bounded enough — tighten it manually or make "
            "claude available",
        )]

    checks: list = []
    concern_dims = set()
    for s in scores:
        if s["status"] == "concern":
            concern_dims.add(s["dimension"])
            checks.append(_check(
                f"model_{s['dimension']}", "model", "concern",
                s["note"] or f"the prompt is deficient on {s['dimension']}",
            ))
    for f in flags:
        if f["dimension"] not in concern_dims:
            concern_dims.add(f["dimension"])
            checks.append(_check(
                f"model_{f['dimension']}", "model", "concern",
                f["note"] or f"independent review flagged {f['dimension']}",
            ))
    if not checks:
        checks.append(_check(
            "model_tier_clear", "model", "pass",
            "the prompt scored ok on all five readiness dimensions "
            "(expansion + independent review agree)",
        ))
    return checks


# ---------------------------------------------------------------------------
# Identity posture — conditional, best-effort (networked, not offline)
# ---------------------------------------------------------------------------

def _resolve_gh() -> "str | None":
    return os.environ.get(GH_BIN_ENV) or shutil.which("gh")


def _probe_viewer_permission(target: Path) -> "str | None":
    """Best-effort host probe: the run principal's permission on the repo via
    `gh repo view --json viewerPermission`. Returns the permission string, or
    None when gh is unavailable / the probe fails (conservative — the caller
    treats None as "could not confirm", never as a bless of collapse)."""
    gh = _resolve_gh()
    if not gh:
        return None
    try:
        proc = subprocess.run(
            [gh, "repo", "view", "--json", "viewerPermission"],
            cwd=str(target), capture_output=True, text=True,
            timeout=GH_PROBE_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    perm = data.get("viewerPermission") if isinstance(data, dict) else None
    return perm if isinstance(perm, str) else None


def identity_checks(target: Path, *, declares_autonomous_merge: bool) -> list:
    """The conditional identity posture (amended ADR-0029).

    - Not declaring autonomous merge (servo's default human-lands-the-worktree
      model): an advisory `info` note only — never a downgrade.
    - Declaring autonomous merge + probe confirms the run principal CAN merge to
      base: `unsafe` (identity collapse — no independent approver).
    - Declaring autonomous merge + probe confirms the run principal CANNOT merge
      (a distinct identity must): `pass` (separation holds).
    - Declaring autonomous merge + probe cannot resolve authority: `concern`
      ("cannot confirm identity separation") — never a silent pass.
    """
    if not declares_autonomous_merge:
        return [_check(
            "identity_advisory", "identity", "info",
            "no autonomous land/merge declared — under servo's default "
            "human-lands-the-worktree model identity collapse is a latent, "
            "advisory concern only (a human is the second party on merge)",
        )]
    perm = _probe_viewer_permission(target)
    if perm is None:
        return [_check(
            "identity_unconfirmed", "identity", "concern",
            "--declares-autonomous-merge is set but the host probe could not "
            "resolve merge authority (no gh / probe failed); refusing to assume "
            "identity separation — cannot confirm identity separation",
        )]
    if perm.upper() in _MERGE_CAPABLE_PERMISSIONS:
        return [_check(
            "identity_collapse", "identity", "unsafe",
            f"identity collapse: the run principal can merge to the base branch "
            f"(viewerPermission={perm}) AND autonomous merge is declared — there "
            "is no independent approver; every downstream owner-approval gate is "
            "fictional",
        )]
    return [_check(
        "identity_separated", "identity", "pass",
        f"the run principal cannot merge to base (viewerPermission={perm}); a "
        "distinct identity must approve the merge — separation holds",
    )]


# ---------------------------------------------------------------------------
# Analysis + persistence
# ---------------------------------------------------------------------------

def _require_target(target: Path) -> None:
    if not target.is_dir():
        raise EnvError("target_missing", f"target directory not found: {target}")


def analyze(target: Path, brief: str, *, cost_ceiling, max_iterations,
            max_candidates, mutation_perimeter, declares_autonomous_merge) -> tuple:
    """Run all tiers and compose the verdict. Returns ``(goal_id, artifact)``.

    Raises EnvError (before any artifact is written) only on an env-level fault
    such as a missing target — a non-`ready` verdict is a *successful* analysis,
    not an error.
    """
    _require_target(target)
    checks: list = []
    checks.extend(deterministic_checks(
        target, cost_ceiling=cost_ceiling, max_iterations=max_iterations,
        max_candidates=max_candidates, mutation_perimeter=mutation_perimeter,
    ))
    checks.extend(model_checks(brief))
    checks.extend(identity_checks(
        target, declares_autonomous_merge=declares_autonomous_merge,
    ))

    decision = compose_verdict(checks)
    safety_surface = [
        c["message"] for c in checks
        if c["code"] == "model_safety_surface"
    ]
    goal_id = _goal_id(brief)
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "goal_id": goal_id,
        "verdict": decision["verdict"],
        "approval_status": APPROVAL_PROPOSED,
        "approved_at": None,
        "reasons": decision["reasons"],
        "checks": checks,
        "safety_surface": safety_surface,
        "analyzed_at": iso_now(),
        "inputs": {
            "cost_ceiling": cost_ceiling,
            "max_iterations": max_iterations,
            "max_candidates": max_candidates,
            "mutation_perimeter": (
                str(mutation_perimeter) if mutation_perimeter is not None else None
            ),
            "declares_autonomous_merge": declares_autonomous_merge,
        },
    }
    return goal_id, artifact


def _artifact_path(target: Path, goal_id: str) -> Path:
    return target / ".servo" / "readiness" / f"{goal_id}.json"


def write_artifact(target: Path, goal_id: str, artifact: dict) -> Path:
    out_dir = target / ".servo" / "readiness"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{goal_id}.json"
    tmp = out_dir / f".{goal_id}.json.tmp"
    tmp.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, out_path)
    return out_path


def load_artifact(target: Path, goal_id: str) -> dict:
    path = _artifact_path(target, goal_id)
    if not path.is_file():
        raise EnvError(
            "artifact_missing",
            f"no readiness artifact for goal {goal_id} at {path} — run "
            "`analyze` first",
        )
    try:
        artifact = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise EnvError("artifact_malformed",
                       f"readiness artifact is unreadable: {exc}") from exc
    # Forward-compat guard (arch-review nit, 2026-08-06): fail closed on an
    # artifact written by a newer, unknown schema rather than silently
    # mis-reading `approval_status` under a changed shape.
    version = artifact.get("schema_version") if isinstance(artifact, dict) else None
    if version != SCHEMA_VERSION:
        raise EnvError(
            "artifact_schema_mismatch",
            f"readiness artifact schema_version={version!r} != supported "
            f"{SCHEMA_VERSION} — re-run `analyze` with this servo version",
        )
    return artifact


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_VERDICT_HEADLINE = {
    VERDICT_READY: "READY — safe to hand to an unattended run (pending human approval)",
    VERDICT_NEEDS_TIGHTENING:
        "NEEDS_TIGHTENING — tighten the premise before an unattended run",
    VERDICT_UNSAFE:
        "UNSAFE_FOR_AUTONOMY — refuse: an unattended run on this premise is unsafe",
}


def render_human(artifact: dict, out_path: Path) -> str:
    verdict = artifact["verdict"]
    lines = [f"servo: {artifact['goal_id']} — {_VERDICT_HEADLINE.get(verdict, verdict)}"]
    for chk in artifact["checks"]:
        if chk["status"] in ("concern", "unsafe"):
            mark = "✗ unsafe" if chk["status"] == "unsafe" else "· concern"
            lines.append(f"  {mark} [{chk['tier']}/{chk['code']}] {chk['message']}")
    if verdict == VERDICT_READY:
        lines.append("  → review the scorecard, then `approve` to permit an "
                     "unattended start.")
    elif verdict == VERDICT_NEEDS_TIGHTENING:
        lines.append("  → address the concerns above, then re-run `analyze`.")
    else:
        lines.append("  → this premise cannot be approved; tighten the scope / "
                     "fix identity separation and re-run `analyze`.")
    lines.append(f"  artifact → {out_path}")
    return "\n".join(lines)


def render_trace(artifact: dict) -> str:
    lines = ["  readiness scorecard (ordered by tier):"]
    for chk in artifact["checks"]:
        lines.append(
            f"    [{chk['status']:>7}] {chk['tier']}/{chk['code']}: {chk['message']}"
        )
    lines.append(f"    => verdict: {artifact['verdict']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI verbs
# ---------------------------------------------------------------------------

def _resolve_brief(prompt, brief_file) -> str:
    if prompt is not None:
        return prompt
    path = Path(brief_file)
    if not path.is_file():
        raise EnvError("brief_missing", f"brief file not found: {path}")
    try:
        return path.read_text()
    except OSError as exc:
        raise EnvError("brief_missing", f"could not read brief file: {exc}") from exc


def _analyze_main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="readiness.py analyze")
    parser.add_argument("target")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt")
    src.add_argument("--brief-file")
    parser.add_argument("--cost-ceiling", type=float, default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--mutation-perimeter", default=None)
    parser.add_argument("--declares-autonomous-merge", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--explain", action="store_true")
    args = parser.parse_args(argv)

    try:
        brief = _resolve_brief(args.prompt, args.brief_file)
        target = Path(args.target).resolve()
        goal_id, artifact = analyze(
            target, brief,
            cost_ceiling=args.cost_ceiling,
            max_iterations=args.max_iterations,
            max_candidates=args.max_candidates,
            mutation_perimeter=args.mutation_perimeter,
            declares_autonomous_merge=args.declares_autonomous_merge,
        )
    except EnvError as exc:
        print(f"error: {exc.reason}: {exc}", file=sys.stderr)
        return 2

    out_path = write_artifact(target, goal_id, artifact)
    if args.json:
        print(json.dumps(artifact, indent=2, sort_keys=True))
    else:
        print(render_human(artifact, out_path))
    if args.explain:
        # stdout-only view; never persisted into the artifact.
        print(render_trace(artifact))
    return 0


def _approve_main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="readiness.py approve")
    parser.add_argument("target")
    ref = parser.add_mutually_exclusive_group(required=True)
    ref.add_argument("--goal-id")
    ref.add_argument("--prompt")
    args = parser.parse_args(argv)

    try:
        target = Path(args.target).resolve()
        _require_target(target)
        goal_id = args.goal_id if args.goal_id else _goal_id(args.prompt)
        artifact = load_artifact(target, goal_id)
        if artifact.get("verdict") == VERDICT_UNSAFE:
            raise EnvError(
                "unsafe_not_approvable",
                f"refusing to approve goal {goal_id}: the recorded verdict is "
                "unsafe_for_autonomy — a human cannot approve an unsafe premise "
                "(fail-closed); tighten the scope and re-run `analyze`",
            )
        if artifact.get("approval_status") == APPROVAL_APPROVED:
            print(f"servo: {goal_id} already approved (no-op)")
            return 0
        artifact["approval_status"] = APPROVAL_APPROVED
        artifact["approved_at"] = iso_now()
        write_artifact(target, goal_id, artifact)
    except EnvError as exc:
        print(f"error: {exc.reason}: {exc}", file=sys.stderr)
        return 2
    print(f"servo: {goal_id} approved — an unattended run may now start")
    return 0


def _check_main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="readiness.py check")
    parser.add_argument("target")
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args(argv)

    try:
        target = Path(args.target).resolve()
        _require_target(target)
        goal_id = _goal_id(args.prompt)
    except EnvError as exc:
        print(f"error: {exc.reason}: {exc}", file=sys.stderr)
        return 2

    path = _artifact_path(target, goal_id)
    if not path.is_file():
        print(f"servo: {goal_id}: no readiness artifact — refuse "
              "(run `analyze` then `approve`)")
        return 1
    try:
        artifact = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        print(f"servo: {goal_id}: readiness artifact unreadable — refuse")
        return 1
    if artifact.get("approval_status") == APPROVAL_APPROVED:
        print(f"servo: {goal_id}: approved — permit")
        return 0
    print(f"servo: {goal_id}: not approved (approval_status="
          f"{artifact.get('approval_status')}) — refuse")
    return 1


def main(argv: "list | None" = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "analyze":
        return _analyze_main(argv[1:])
    if argv and argv[0] == "approve":
        return _approve_main(argv[1:])
    if argv and argv[0] == "check":
        return _check_main(argv[1:])
    print("error: unknown or missing subcommand (expected: analyze, approve, check)",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
