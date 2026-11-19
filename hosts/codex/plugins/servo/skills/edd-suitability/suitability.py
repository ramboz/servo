#!/usr/bin/env python3
"""
servo edd-suitability — slices 015-01 (verdict-contract) + 015-02
(missing-evidence) + 030-01 (eval-component-signal).

The first step of Servo Compile: decide whether an engineering spec is suitable
for Evaluation-Driven Development, emitting the ADR-0015 **suitability verdict** —
a closed three-state gate (`suitable` / `needs_evidence` / `unsuitable`), not a
score. For a `needs_evidence` verdict the artifact carries an actionable
`missing_evidence` checklist keyed to a closed `kind` taxonomy (015-02).

Usage
-----
    python3 suitability.py analyze <target> --spec <spec-path> [--json] [--explain]

Default output is a concise human summary (the verdict + each blocking
`missing_evidence` item); `--json` emits the full ADR-0015 verdict JSON; and
`--explain` shows the ordered rule trace — which rules were evaluated, which
fired, and the inputs they keyed on — so a verdict is debuggable without reading
the rule-table source. The persisted artifact is always the clean ADR-0015 shape;
`--explain` adds the trace as a stdout-only view, never to the file.

Reads the target's detected signals (`<target>/.servo/install.json`, from spec
001) and the spec's AC classification (via spec 006's `oracle_plan.py classify`,
subprocessed — the established servo idiom, never imported), runs a deterministic
ordered rule table, and writes the verdict to
`<target>/.servo/suitability/<spec-id>.json` (atomic).

Design — deterministic in v1
----------------------------
The verdict is a pure, ordered, first-match rule table over four inputs: the
target's deterministic test/CI signal, a *reviewed, frozen eval component*
signal (ADR-0036 — read from the same manifests servo already writes), and the
count of evaluable vs residual-judgment ACs. No clock / network / randomness
enters the decision, so the verdict is reproducible. ADR-0015's optional
model-assisted pass is a documented extension point (spec 015-04), not built
here.

The eval-signal leg (ADR-0036 / spec 030-01)
--------------------------------------------
`has_signal` is `deterministic_signal OR reviewed_frozen_eval`. The eval leg is
established purely from two manifests servo already writes — never by parsing
`oracle.sh`:

1. **Installed** — the component name is registered in `install.json`'s
   `components` list (written by `fidelity_eval.register_manifest`, removed
   symmetrically at uninstall).
2. **Approved + frozen, with reviewed provenance** — the component's frozen
   `<target>/.servo/<eval>/config.json` carries `approval_status: "approved"`,
   `approval_provenance: "reviewed"`, `approved_content_hash`, and a non-empty
   `hashes` map. A `self_approved` or provenance-less freeze, an unapproved or
   unfrozen config, an unregistered component, or an unreadable/malformed config
   contributes nothing (fail-closed — ADR-0036 guardrail 4).

When a reviewed frozen eval is the *only* signal (no tests, no CI), the verdict
is still `suitable`, but the artifact carries a standing **non-blocking**
advisory recommending at least one deterministic component (the ADR-0033
counterweight), and the decided rule names the eval-signal source so the
judged-only case is auditable via `reasons` / `--explain`.

Exit codes (ADR-0002 closed contract)
-------------------------------------
    0  verdict emitted (including a non-`suitable` verdict — that is a
       successful analysis, not an error)
    2  environment error (missing spec / missing-or-malformed manifest /
       unreadable classification); a structured reason is printed to stderr and
       no artifact is written.

Never exits 1; never leaves a torn artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

# Subprocess seam for spec 006's classifier. Defaults to the sibling skill path
# (mirrors heartbeat.py's GATE_PY_PATH idiom); the SERVO_* env override is the
# established test hook so a test injects a deterministic stand-in.
ORACLE_PLAN_ENV = "SERVO_SUITABILITY_ORACLE_PLAN"
DEFAULT_ORACLE_PLAN = (
    Path(__file__).resolve().parent.parent / "spec-oracle" / "oracle_plan.py"
)

# Only tests / CI count as a compilable *deterministic* oracle signal in v1.
# Lint alone is a weak code-quality signal — not sufficient on its own to call
# work EDD-evaluable (it surfaces as a missing_evidence item below). A reviewed,
# frozen eval component is a *separate* signal source (ADR-0036 / 030-01),
# computed from the manifests in `_eval_signal` and threaded in as `eval_signal`.
_SIGNAL_KEYS = ("tests", "ci")

# Closed dir↔component alias map (ADR-0036). The *reverse* of the eval
# producers' forward mapping: given an installed component name (from
# `install.json`'s `components`), which `.servo/<dir>/config.json` holds its
# frozen definition. The two blessed presets are fixed constants in their
# producers — `design_fidelity` → `.servo/design-eval/` (design_eval.py), and
# `content_fidelity` → `.servo/content-fidelity/` (content_fidelity.py) — and
# every eval-authoring component's directory equals its own name
# (eval_authoring.py). A future preset must extend this map (ADR-0036 kill
# criterion); `_eval_config_dir` falls back to dir-equals-name so an
# eval-authoring component resolves without a map entry.
_EVAL_COMPONENT_DIRS = {
    "design_fidelity": "design-eval",
    "content_fidelity": "content-fidelity",
}

# Closed `kind` taxonomy for missing_evidence items (slice 015-02), mirroring
# ADR-0002's closed-`reason` posture. An input that maps to no known kind is
# never emitted as an open string — the set is extended only by a deliberate
# schema bump. The tuple order is also the stable display order (ADR-0015
# re-runnability): items sort by (taxonomy index, detail).
MISSING_EVIDENCE_KINDS = ("tests", "lint", "ci", "oracle_signal", "reference_set")


class EnvError(Exception):
    """An environment error mapped to a closed `reason` + exit 2."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Decision — pure, deterministic, ordered first-match rule table
# ---------------------------------------------------------------------------

# Reused non-blocking advisory details (015-02). The same `tests` / `ci` kinds
# serve two situations: the no-signal gap (alongside the blocking oracle_signal)
# and the judged-only counterweight (ADR-0036 guardrail 5 — "reuses the existing
# non-blocking tests/ci kinds, whose details already frame the deterministic-gate
# remedy"). A dedicated kind would need a schema bump and is not warranted for a
# non-blocking nudge.
_TESTS_ADVISORY = (
    "no test signal detected; add a test command (e.g. a test runner target) "
    "so the oracle has a deterministic gate"
)
_CI_ADVISORY = (
    "no CI signal detected; add a CI workflow that runs the project's checks "
    "so the oracle has a reproducible gate"
)


def _missing_evidence(signals: dict, *, has_signal: bool, n_evaluable: int,
                      judged_only: bool = False) -> list:
    """Deterministic, actionable `missing_evidence` items (slice 015-02).

    Pure: no IO, no clock. Every item points at a *concrete absent input* (never
    a vague "needs more") and carries the closed `{kind, detail, blocking}`
    shape. ``blocking=True`` marks the gap that *caused* the `needs_evidence`
    verdict; ``blocking=False`` items are how-to / quality nudges. Items are
    returned in the stable order ADR-0015 requires (taxonomy index, then detail)
    so re-analysis over unchanged inputs is byte-stable.

    ``judged_only`` (ADR-0036 / 030-01) marks the judged-only **suitable** case
    — a reviewed, frozen eval is the *sole* signal (no tests, no CI) *and* the
    verdict is `suitable`, so the counterweight advisory applies. It emits the
    non-blocking ``tests`` / ``ci`` kinds (ADR-0036 guardrail 5), **without** the
    blocking ``oracle_signal`` item (the eval already satisfies the signal). The
    caller passes it True only for that case — a deterministic-signal `suitable`
    emits nothing (byte-identical to pre-030-01, AC3), and an eval-signal
    `needs_evidence` (eval present but no evaluable ACs) is treated like today's
    deterministic `signal_without_evaluable_acs` (no counterweight nudge; the
    real gap is the missing evaluable AC, surfaced by `reference_set`).
    """
    items: list = []
    if not has_signal:
        items.append({
            "kind": "oracle_signal",
            "detail": "no test, CI, or reviewed frozen eval signal detected in "
                      ".servo/install.json; add a test command, a CI workflow, "
                      "or a reviewed, frozen eval component so the oracle has a "
                      "gate to evaluate against",
            "blocking": True,
        })
        items.append({"kind": "tests", "detail": _TESTS_ADVISORY,
                      "blocking": False})
        items.append({"kind": "ci", "detail": _CI_ADVISORY, "blocking": False})
    elif judged_only:
        # Judged-only suitable (ADR-0036 guardrail 5): the eval satisfies the
        # signal, so NO blocking oracle_signal; recommend a deterministic
        # counterweight via the existing non-blocking tests/ci kinds.
        items.append({"kind": "tests", "detail": _TESTS_ADVISORY,
                      "blocking": False})
        items.append({"kind": "ci", "detail": _CI_ADVISORY, "blocking": False})
    if not bool(signals.get("lint")):
        items.append({
            "kind": "lint",
            "detail": "no lint signal detected; adding one strengthens the "
                      "oracle but is not required for suitability on its own",
            "blocking": False,
        })
    if n_evaluable == 0:
        items.append({
            "kind": "reference_set",
            "detail": "no evaluable acceptance criteria detected; add at least "
                      "one deterministically-checkable AC (or a reference set) "
                      "so the oracle has something to gate on",
            "blocking": True,
        })
    kind_rank = {k: i for i, k in enumerate(MISSING_EVIDENCE_KINDS)}
    items.sort(key=lambda it: (kind_rank[it["kind"]], it["detail"]))
    return items


def _facts(n_evaluable: int, n_residual: int, *, det_signal: bool,
           eval_signal: bool) -> str:
    if det_signal:
        signal_phrase = "a test/CI signal"
    elif eval_signal:
        signal_phrase = "a reviewed frozen eval signal"
    else:
        signal_phrase = "no test/CI signal"
    return (
        f"{n_evaluable} evaluable AC(s), {n_residual} residual AC(s), "
        f"{signal_phrase}"
    )


def _rule_table(n_evaluable: int, n_residual: int, *, det_signal: bool,
                eval_signal: bool) -> list:
    """The ordered, first-match suitability rule table (ADR-0015 / 015-01,
    widened by ADR-0036 / 030-01).

    Returns ``[(matched, verdict, code, message), ...]``. The final rule's
    predicate is ``True`` — the fail-closed catch-all. Shared by `decide()`
    (which takes the first match) and `build_trace()` (which renders every rule
    for `--explain`), so the table is defined exactly once.

    `has_signal` is ``det_signal OR eval_signal``. The single "signal present →
    suitable" rule names its *source* in the code/message: a deterministic
    signal keeps the pre-030-01 `evaluable_acs_with_signal` code (byte-identical
    artifacts, AC3); a judged-only signal (eval but no tests/CI) takes the
    distinct `evaluable_acs_with_eval_signal` code so `reasons` / `--explain`
    make the case auditable (AC1). The table stays five rules.
    """
    has_signal = det_signal or eval_signal
    eval_only = has_signal and not det_signal
    if eval_only:
        signal_code = "evaluable_acs_with_eval_signal"
        signal_message = (
            "EDD-shaped: evaluable ACs and a reviewed, frozen eval component "
            "are both present (the judged eval is the oracle signal; a "
            "deterministic counterweight is advised)"
        )
        # Rule 3 fires for n_evaluable == 0 WITH a signal; when that signal is
        # the eval (no tests/CI), the message must not claim "a test/CI signal"
        # — that contradicts the `_facts` suffix "a reviewed frozen eval signal".
        no_evaluable_message = (
            "a reviewed, frozen eval signal exists but no evaluable ACs to "
            "gate on"
        )
    else:
        signal_code = "evaluable_acs_with_signal"
        signal_message = (
            "EDD-shaped: evaluable ACs and a compilable test/CI signal are both "
            "present"
        )
        # The exact pre-030-01 string — rule 3's deterministic-signal case is in
        # the AC3 byte-identity golden, so this must not change.
        no_evaluable_message = (
            "a test/CI signal exists but no evaluable ACs to gate on"
        )
    return [
        (
            n_evaluable >= 1 and has_signal,
            "suitable",
            signal_code,
            signal_message,
        ),
        (
            n_evaluable >= 1 and not has_signal,
            "needs_evidence",
            "evaluable_acs_no_signal",
            "evaluable ACs exist but there is no test/CI signal to compile an "
            "oracle against",
        ),
        (
            n_evaluable == 0 and has_signal,
            "needs_evidence",
            "signal_without_evaluable_acs",
            no_evaluable_message,
        ),
        (
            n_evaluable == 0 and n_residual >= 1 and not has_signal,
            "unsuitable",
            "all_acs_residual_no_signal",
            "every AC is residual judgment and there is no signal: success is "
            "irreducibly human taste, not EDD-shaped",
        ),
        (
            True,
            "needs_evidence",
            "no_evidence_no_acs",
            "no evaluable ACs and no signal: write testable ACs and add a "
            "test/CI signal, then re-analyze",
        ),
    ]


def build_trace(signals: dict, *, n_evaluable: int, n_residual: int,
                eval_signal: bool = False) -> dict:
    """Ordered rule trace for `--explain` (slice 015-04 AC3).

    Renders every rule in table order with its boolean predicate and marks the
    single rule that `decide()` would act on (`decided: true` — the first match).
    Pure; carries the inputs the rules keyed on so a verdict is debuggable
    without reading the rule-table source. `eval_signal` (ADR-0036 / 030-01) is
    surfaced so `--explain` shows which signal source decided a judged-only case.
    """
    det_signal = any(bool(signals.get(k)) for k in _SIGNAL_KEYS)
    has_signal = det_signal or eval_signal
    rules = _rule_table(n_evaluable, n_residual, det_signal=det_signal,
                        eval_signal=eval_signal)
    rendered = []
    decided = False
    for matched, verdict, code, _message in rules:
        is_decision = bool(matched) and not decided
        if is_decision:
            decided = True
        rendered.append({
            "code": code,
            "verdict": verdict,
            "matched": bool(matched),
            "decided": is_decision,
        })
    return {
        "inputs": {
            "n_evaluable": n_evaluable,
            "n_residual": n_residual,
            "has_signal": has_signal,
            "eval_signal": eval_signal,
            "signals": {
                k: signals.get(k) for k in ("tests", "lint", "ci", "language")
            },
        },
        "rules": rendered,
    }


def decide(signals: dict, *, n_evaluable: int, n_residual: int,
           eval_signal: bool = False) -> dict:
    """Return ``{"verdict", "reasons": [...], "missing_evidence": [...]}``.

    Pure: no IO, no clock. A `suitable` verdict requires an evaluable AC and a
    signal — `has_signal = deterministic_signal OR eval_signal`, where
    `eval_signal` (ADR-0036 / 030-01) is a reviewed, frozen eval component
    computed upstream in `analyze`. Everything else is fail-closed. The table is
    ordered and first-match — exactly one rule fires and names itself (and its
    signal *source*) in `reasons`.

    The `missing_evidence` list is load-bearing for `needs_evidence` and for the
    judged-only `suitable` case (ADR-0036): a deterministic-signal `suitable`
    carries an empty list, but a `suitable` reached via a reviewed frozen eval
    alone carries the **non-blocking** deterministic-counterweight advisory
    (never a blocking item). `unsuitable` carries an empty list (an unsuitable
    spec is not fixable by acquiring evidence). For `needs_evidence`, every
    blocking item's `kind` is also reflected back into `reasons` so the verdict
    and the list can never disagree (slice 015-02 AC3).
    """
    det_signal = any(bool(signals.get(k)) for k in _SIGNAL_KEYS)
    has_signal = det_signal or eval_signal
    eval_only = has_signal and not det_signal
    facts = _facts(n_evaluable, n_residual, det_signal=det_signal,
                   eval_signal=eval_signal)
    rules = _rule_table(n_evaluable, n_residual, det_signal=det_signal,
                        eval_signal=eval_signal)

    for matched, verdict, code, message in rules:
        if matched:
            reasons = [{"code": code, "message": f"{message} ({facts})"}]
            is_judged_only_suitable = verdict == "suitable" and eval_only
            emit_missing = (
                verdict == "needs_evidence" or is_judged_only_suitable
            )
            missing = (
                _missing_evidence(
                    signals, has_signal=has_signal, n_evaluable=n_evaluable,
                    judged_only=is_judged_only_suitable,
                )
                if emit_missing
                else []
            )
            # Reflect each blocking gap's kind into `reasons` so a consumer
            # reading the top-level reasons sees the same gaps as the list. The
            # judged-only advisory is non-blocking, so it never manufactures a
            # reason — the `suitable` verdict's only reason is its decided rule.
            for item in missing:
                if item["blocking"]:
                    reasons.append({
                        "code": f"missing_{item['kind']}",
                        "message": item["detail"],
                    })
            return {
                "verdict": verdict,
                "reasons": reasons,
                "missing_evidence": missing,
            }
    # Unreachable: the last rule's predicate is True.
    raise AssertionError("rule table is not exhaustive")  # pragma: no cover


# ---------------------------------------------------------------------------
# Inputs — signals (001) + eval components (ADR-0036) + AC classification (006)
# ---------------------------------------------------------------------------

def _load_manifest(target: Path) -> dict:
    """Read + validate `<target>/.servo/install.json`; return the parsed dict.

    Raises EnvError(`manifest_missing`) / EnvError(`manifest_malformed`). The
    `signals` object must be present and a dict (015-01); `components` is read
    separately by `_eval_signal` (ADR-0036 / 030-01) and is optional.
    """
    manifest = target / ".servo" / "install.json"
    if not manifest.is_file():
        raise EnvError(
            "manifest_missing",
            f".servo/install.json not found at {target}; "
            "run /servo:scaffold-init first",
        )
    try:
        data = json.loads(manifest.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise EnvError(
            "manifest_malformed", f".servo/install.json is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("signals"), dict):
        raise EnvError(
            "manifest_malformed",
            ".servo/install.json has no 'signals' object",
        )
    return data


def _eval_config_dir(component: str) -> str:
    """Reverse the closed dir↔component alias map (ADR-0036): the `.servo/<dir>/`
    that holds `component`'s frozen config. Eval-authoring components are
    dir-equals-name, so an unmapped name resolves to itself (never an error)."""
    return _EVAL_COMPONENT_DIRS.get(component, component)


def _is_reviewed_frozen_eval(target: Path, component: str) -> bool:
    """True iff `component`'s `<target>/.servo/<dir>/config.json` is a reviewed,
    approved, frozen eval definition (ADR-0036 decision point 2 + guardrail 4).

    Reads the *recorded approval facts* only — never re-hashes the frozen
    artifacts (staleness stays score-time authority via `validate_freeze`).
    Fail-closed on every indeterminate branch: a missing / unreadable / malformed
    config, a non-"approved" status, a non-"reviewed" provenance (`self_approved`
    or absent), an empty/missing `hashes` map, or an absent `approved_content_hash`
    all contribute nothing — never an env-error, never an optimistic credit.
    """
    # Defense-in-depth (install.json is servo-authored, so this is
    # belt-and-suspenders): never let a component name escape `.servo/` via a
    # path separator or traversal — every valid name (the two presets + an
    # eval-authoring slug) is a single path segment.
    if ("/" in component or "\\" in component or "\x00" in component
            or component in (".", "..")):
        return False
    cfg_path = target / ".servo" / _eval_config_dir(component) / "config.json"
    if not cfg_path.is_file():
        return False
    try:
        cfg = json.loads(cfg_path.read_text())
    except (json.JSONDecodeError, OSError, ValueError):
        return False
    if not isinstance(cfg, dict):
        return False
    if cfg.get("approval_status") != "approved":
        return False
    if cfg.get("approval_provenance") != "reviewed":
        return False
    hashes = cfg.get("hashes")
    if not isinstance(hashes, dict) or not hashes:
        return False
    if not cfg.get("approved_content_hash"):
        return False
    return True


def _eval_signal(target: Path, components) -> bool:
    """True iff at least one *installed* component (named in `install.json`'s
    `components`) is a reviewed, frozen eval (ADR-0036 / 030-01).

    The `components` membership is the "installed in oracle.sh" proxy
    (register/deregister symmetry). A non-list `components`, or a non-string
    entry, is ignored (fail-closed)."""
    if not isinstance(components, list):
        return False
    for component in components:
        if isinstance(component, str) and _is_reviewed_frozen_eval(
            target, component
        ):
            return True
    return False


def _classify(spec_path: Path, oracle_plan_path: Path) -> dict:
    """Obtain the 006 AC classification for `spec_path` via subprocess.

    Returns the plan payload (with `checks` + `residual_judgment`). Raises
    EnvError(`spec_missing`) / EnvError(`plan_unreadable`).
    """
    if not spec_path.is_file():
        raise EnvError("spec_missing", f"spec not found: {spec_path}")
    try:
        proc = subprocess.run(
            [sys.executable, str(oracle_plan_path), "classify", str(spec_path)],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise EnvError(
            "plan_unreadable", f"could not run oracle_plan classify: {exc}"
        ) from exc
    if proc.returncode != 0:
        raise EnvError(
            "plan_unreadable",
            f"oracle_plan classify exited {proc.returncode}: "
            f"{proc.stderr.strip()}",
        )
    try:
        plan = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise EnvError(
            "plan_unreadable",
            f"oracle_plan classify emitted unparseable output: {exc}",
        ) from exc
    if not isinstance(plan, dict) or "checks" not in plan \
            or "residual_judgment" not in plan:
        raise EnvError(
            "plan_unreadable",
            "oracle_plan classify output missing checks / residual_judgment",
        )
    return plan


# ---------------------------------------------------------------------------
# Analysis + persistence
# ---------------------------------------------------------------------------

def analyze(target: Path, spec_path: Path, *, oracle_plan_path: Path) -> tuple:
    """Run the analysis. Returns ``(spec_id, artifact_dict, eval_signal)``.

    Raises EnvError before any artifact is written (the caller persists only on
    success, so a failed analysis never leaves a torn artifact). `eval_signal`
    is returned so the CLI can thread it into the `--explain` trace without
    re-reading the manifest; it is deliberately NOT persisted into the artifact
    (keeping tests/CI artifacts byte-identical to pre-030-01 — AC3).
    """
    manifest = _load_manifest(target)
    signals = manifest["signals"]
    eval_signal = _eval_signal(target, manifest.get("components"))
    plan = _classify(spec_path, oracle_plan_path)
    n_evaluable = len(plan.get("checks", []))
    n_residual = len(plan.get("residual_judgment", []))
    spec_id = plan.get("spec_id") or spec_path.parent.name

    decision = decide(
        signals, n_evaluable=n_evaluable, n_residual=n_residual,
        eval_signal=eval_signal,
    )

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "verdict": decision["verdict"],
        "reasons": decision["reasons"],
        # Load-bearing for `needs_evidence` and the judged-only `suitable` case
        # (ADR-0036); empty for a deterministic-signal `suitable` / `unsuitable`.
        "missing_evidence": decision["missing_evidence"],
        "spec_id": spec_id,
        "analyzed_at": iso_now(),
        # Echoed inputs for auditability / the 015-04 `--explain` view. The eval
        # signal is intentionally absent here — see AC3 (byte-identity).
        "inputs": {
            "signals": {
                k: signals.get(k) for k in ("tests", "lint", "ci", "language")
            },
            "ac_counts": {"evaluable": n_evaluable, "residual": n_residual},
        },
    }
    return spec_id, artifact, eval_signal


def write_artifact(target: Path, spec_id: str, artifact: dict) -> Path:
    """Atomically write the verdict artifact; return its path."""
    out_dir = target / ".servo" / "suitability"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{spec_id}.json"
    tmp = out_dir / f".{spec_id}.json.tmp"
    tmp.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, out_path)
    return out_path


# ---------------------------------------------------------------------------
# Rendering — human summary + `--explain` rule trace (slice 015-04)
# ---------------------------------------------------------------------------

_VERDICT_HEADLINE = {
    "suitable": "SUITABLE — EDD-shaped with compilable evidence; ready to compile",
    "needs_evidence": "NEEDS_EVIDENCE — EDD-shaped but missing blocking evidence",
    "unsuitable": "UNSUITABLE — not EDD-shaped (success is human-residual)",
}


def render_human(artifact: dict, out_path: Path) -> str:
    """A concise human summary: the verdict + one line per *blocking* gap.

    Non-blocking advisory items are summarized as a count (the actionable next
    step is the blocking set). A `needs_evidence` verdict ends with the re-run
    hint ADR-0015 names. A judged-only `suitable` verdict surfaces its standing
    non-blocking advisory (ADR-0036 / 030-01 AC5) — today's deterministic-signal
    `suitable` has no advisory and prints just the headline.
    """
    verdict = artifact["verdict"]
    lines = [
        f"servo: {artifact['spec_id']} — "
        f"{_VERDICT_HEADLINE.get(verdict, verdict)}"
    ]
    missing = artifact.get("missing_evidence", [])
    blocking = [it for it in missing if it.get("blocking")]
    advisory = [it for it in missing if not it.get("blocking")]
    # Key the judged-only block on the DECIDED reason code, not on
    # advisory-presence — so a future deterministic-signal `suitable` that gains
    # an advisory item can never print a false "sole signal" line.
    judged_only = any(
        r.get("code") == "evaluable_acs_with_eval_signal"
        for r in artifact.get("reasons", [])
    )
    if verdict == "needs_evidence":
        for it in blocking:
            lines.append(f"  ✗ blocking [{it['kind']}] {it['detail']}")
        if advisory:
            lines.append(
                f"  · plus {len(advisory)} advisory item"
                f"{'' if len(advisory) == 1 else 's'} (run --json to see them)"
            )
        lines.append(
            "  → acquire the blocking evidence above, then re-run "
            "`analyze` — the verdict flips to `suitable` once the gaps close."
        )
    elif verdict == "unsuitable":
        for reason in artifact.get("reasons", []):
            lines.append(f"  · {reason['message']}")
        lines.append("  → route to a human / jig; this is not EDD-shaped.")
    elif verdict == "suitable" and judged_only:
        # Judged-only: a reviewed, frozen eval is the sole signal — surface the
        # standing deterministic-counterweight advisory (ADR-0036 / 030-01).
        lines.append(
            "  ✓ suitable via a reviewed, frozen eval component (the sole "
            "signal)"
        )
        for it in advisory:
            lines.append(f"  · advisory [{it['kind']}] {it['detail']}")
        lines.append(
            "  → suitable now; adding a deterministic component (test / CI) is "
            "a recommended reward-hacking counterweight, not required."
        )
    lines.append(f"  artifact → {out_path}")
    return "\n".join(lines)


def render_trace(trace: dict) -> str:
    """Render the ordered rule trace (`--explain`) as a human-readable block."""
    inp = trace["inputs"]
    lines = [
        "  rule trace (ordered, first-match):",
        f"    inputs: evaluable={inp['n_evaluable']} residual={inp['n_residual']} "
        f"has_signal={inp['has_signal']} eval_signal={inp['eval_signal']} "
        f"(tests={inp['signals'].get('tests')} ci={inp['signals'].get('ci')} "
        f"lint={inp['signals'].get('lint')})",
    ]
    for r in trace["rules"]:
        mark = "✓ DECIDED" if r["decided"] else ("·  matched" if r["matched"]
                                                 else "   ——")
        lines.append(f"    [{mark}] {r['code']} → {r['verdict']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _run_analyze(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    spec_path = Path(args.spec).resolve()
    oracle_plan_path = Path(
        os.environ.get(ORACLE_PLAN_ENV) or DEFAULT_ORACLE_PLAN
    )

    try:
        spec_id, artifact, eval_signal = analyze(
            target, spec_path, oracle_plan_path=oracle_plan_path
        )
    except EnvError as exc:
        # Env errors stay on stderr + exit 2 regardless of --json (no artifact,
        # no torn output) — the closed ADR-0002 contract from 015-01.
        print(f"servo: {exc.reason}: {exc}", file=sys.stderr)
        return 2

    out_path = write_artifact(target, spec_id, artifact)

    trace = None
    if args.explain:
        inputs = artifact["inputs"]["ac_counts"]
        trace = build_trace(
            artifact["inputs"]["signals"],
            n_evaluable=inputs["evaluable"],
            n_residual=inputs["residual"],
            eval_signal=eval_signal,
        )

    if args.json:
        # The persisted artifact stays the clean ADR-0015 shape; --explain adds
        # the trace as a stdout-only view (a superset), never to the file.
        payload = dict(artifact)
        if trace is not None:
            payload["rule_trace"] = trace
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_human(artifact, out_path))
        if trace is not None:
            print(render_trace(trace))
    return 0


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="suitability.py",
        description="servo edd-suitability — the ADR-0015 suitability gate.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    analyze_p = sub.add_parser(
        "analyze", help="emit the ADR-0015 suitability verdict for a spec"
    )
    analyze_p.add_argument("target", help="target project directory")
    analyze_p.add_argument(
        "--spec", dest="spec", required=True, help="path to the spec.md to judge"
    )
    analyze_p.add_argument(
        "--json", action="store_true",
        help="emit the full ADR-0015 verdict JSON (default: a human summary)",
    )
    analyze_p.add_argument(
        "--explain", action="store_true",
        help="show the ordered rule trace (which rules fired and why)",
    )

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "analyze":
        return _run_analyze(args)
    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
