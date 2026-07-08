#!/usr/bin/env python3
"""
servo execution-planner — slice 016-01 (plan-emit) + slice 016-03 (clamp-and-review)
+ slice 016-04 (skill-surface: the `--json` outcome envelope).

The last step of Servo Compile: assemble the
[ADR-0016](../../docs/decisions/adr-0016-execution-plan-artifact.md) **execution
plan** and write it to `<target>/.servo/plans/<spec-id>/plan.json`. The plan is
the durable Compile→Run handoff artifact — the reciprocal of the per-run
`state.json` (ADR-0004): a *plan*, not an *outcome*.

Usage
-----
    python3 execution_plan.py compile <target> --spec <spec-path> [--force] [--json]

The plan **references** (never copies) the other Compile artifacts:
  - the suitability verdict (`.servo/suitability/<spec-id>.json`, spec 015) via a
    relative `suitability_ref` path — not the inlined verdict string, so it cannot
    go stale relative to a re-analysis;
  - the oracle (`oracle.sh`, spec 001) by path, with its component list (from
    `.servo/install.json`) and threshold (parsed from `oracle.sh`);
  - the spec-oracle overlay (spec 006) by id + AC counts, when one is installed
    (`null` for a baseline-oracle-only target).

The `budget` block records `loop.py`'s public defaults — the planned, safe budget.
Clamping a hand-edited disable-sentinel value is `loop.py`'s job at Run time
(slice 016-03 AC1). This module's own slice 016-03 responsibility (AC4) is
**recompile-preserve**: `compile` refuses to silently clobber a plan whose
`budget`/`driver` content was hand-edited since it was last compiled (detected
by `budget_hash`, not a self-reported `provenance` label — see `write_plan`),
unless `--force` is passed.

The `suitable`-only precondition
--------------------------------
Per ADR-0016 a `plan.json` exists **only** for a `suitable` suitability verdict, so
`compile` refuses (exit 2) when the verdict is missing or is
`needs_evidence`/`unsuitable`. This refusal *is* the Servo Compile precondition
that spec 015-03 (re-scoped, deferred pending 016) describes — enforced here at the
one boundary where a real spec + verdict exist.

Exit codes (ADR-0002 closed contract)
-------------------------------------
    0  plan emitted
    2  environment error (missing spec / missing-or-malformed manifest / missing
       oracle / missing suitability artifact / non-`suitable` verdict); a
       structured reason is printed to stderr and no plan is written.

Never exits 1; never leaves a torn artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

# loop.py public budget defaults (003 / ADR-0008) — the plan's source of truth.
# Duplicated as constants (never imported — the dependency-free skill invariant,
# cf. heartbeat.py's DEFAULT_HEARTBEAT_COST_CEILING_USD mirroring loop.py). The
# plan records the *planned* safe budget; no value exceeds the guardrail bound.
# Clamping a hand-edited over-ceiling value is slice 016-03.
BUDGET_MAX_ITERATIONS = 5
BUDGET_COST_CEILING_USD = 2.0
BUDGET_CONTEXT_FILL_THRESHOLD = 0.75
BUDGET_PLATEAU_WINDOW = 3

# loop.py's default driver (003-07 flipped the default to `auto`).
DEFAULT_DRIVER = "auto"

# oracle.sh threshold fallback when the `THRESHOLD=` default cannot be parsed —
# scaffold-init's `DEFAULT_THRESHOLD` (001).
DEFAULT_ORACLE_THRESHOLD = 0.5
# Matches the scaffolded `THRESHOLD="${THRESHOLD:-0.5}"` line (001 oracle template).
_THRESHOLD_RE = re.compile(r"THRESHOLD:-\s*([0-9]*\.?[0-9]+)")

# Atomic-write staging suffix (mirrors suitability.py / loop.py).
TMP_PREFIX = "."
TMP_SUFFIX = ".tmp"


class EnvError(Exception):
    """An environment error mapped to a closed `reason` + exit 2."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _spec_id_from_path(spec_path: Path) -> str:
    """spec_id = the spec file's parent directory name (006/015 convention)."""
    return spec_path.parent.name


# ---------------------------------------------------------------------------
# Inputs — suitability verdict (015), oracle + manifest (001), overlay (006)
# ---------------------------------------------------------------------------

def _require_suitable(target: Path, spec_id: str) -> str:
    """Enforce the `suitable`-only precondition; return the relative ref path.

    Raises EnvError(`suitability_missing` / `suitability_malformed` /
    `suitability_not_suitable`). This is the 015-03 Servo Compile gate: Compile
    proceeds only on `suitable`; every other case (missing / unparseable /
    `needs_evidence` / `unsuitable`) is fail-closed (an unavailable verdict is
    treated as non-`suitable`, 015-03 AC2). On a non-`suitable` verdict the refusal
    **surfaces the verdict's `reasons` + `missing_evidence`** as the actionable next
    step (015-03 AC1) rather than a bare code.
    """
    rel = f".servo/suitability/{spec_id}.json"
    path = target / ".servo" / "suitability" / f"{spec_id}.json"
    if not path.is_file():
        raise EnvError(
            "suitability_missing",
            f"no suitability verdict at {path}; run /servo:edd-suitability "
            f"analyze {target} --spec <spec> first",
        )
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise EnvError(
            "suitability_malformed",
            f"suitability verdict is not readable JSON: {exc}",
        ) from exc
    verdict = data.get("verdict") if isinstance(data, dict) else None
    if verdict != "suitable":
        raise EnvError(
            "suitability_not_suitable",
            _format_refusal(data if isinstance(data, dict) else {}, verdict),
        )
    return rel


def _format_refusal(data: dict, verdict) -> str:
    """Build the Compile-refusal message surfacing `reasons` + `missing_evidence`.

    The actionable next step for a non-`suitable` verdict (015-03 AC1): list every
    `reasons` entry and every `missing_evidence` item (with its blocking flag) from
    the 015 verdict artifact, then the re-analyze instruction — so a caller sees
    *why* Compile refused and *what to acquire*, not just a code.
    """
    lines = [
        f"suitability verdict is {verdict!r}, not 'suitable'; Servo Compile does "
        f"not proceed."
    ]
    reasons = data.get("reasons") or []
    if reasons:
        lines.append("reasons:")
        for r in reasons:
            if isinstance(r, dict):
                lines.append(f"  - [{r.get('code', '')}] {r.get('message', '')}")
    missing = data.get("missing_evidence") or []
    if missing:
        lines.append("missing_evidence:")
        for m in missing:
            if isinstance(m, dict):
                flag = " (blocking)" if m.get("blocking") else ""
                lines.append(f"  - [{m.get('kind', '')}] {m.get('detail', '')}{flag}")
    lines.append(
        "Acquire the missing evidence and re-run `/servo:edd-suitability analyze`, "
        "then re-compile."
    )
    return "\n".join(lines)


def _load_oracle(target: Path) -> dict:
    """Build the plan's `oracle` block from `install.json` + `oracle.sh`.

    Raises EnvError(`manifest_missing` / `manifest_malformed` / `oracle_missing`).
    References the oracle by path; reads components from the manifest and the
    threshold from `oracle.sh` (fallback `DEFAULT_ORACLE_THRESHOLD`).
    """
    manifest = target / ".servo" / "install.json"
    if not manifest.is_file():
        raise EnvError(
            "manifest_missing",
            f".servo/install.json not found at {target}; run "
            f"/servo:scaffold-init first",
        )
    try:
        data = json.loads(manifest.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise EnvError(
            "manifest_malformed", f".servo/install.json is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        raise EnvError(
            "manifest_malformed",
            ".servo/install.json has no 'components' list",
        )
    oracle_sh = target / "oracle.sh"
    if not oracle_sh.is_file():
        raise EnvError(
            "oracle_missing",
            f"oracle.sh not found at {target}; run /servo:scaffold-init first",
        )
    return {
        "path": "oracle.sh",
        "components": list(data["components"]),
        "threshold": _parse_threshold(oracle_sh),
    }


def _parse_threshold(oracle_sh: Path) -> float:
    """Parse the `THRESHOLD=` default from `oracle.sh`; fallback to the default."""
    try:
        text = oracle_sh.read_text()
    except OSError:
        return DEFAULT_ORACLE_THRESHOLD
    match = _THRESHOLD_RE.search(text)
    if not match:
        return DEFAULT_ORACLE_THRESHOLD
    try:
        return float(match.group(1))
    except ValueError:  # pragma: no cover - regex already constrains the shape
        return DEFAULT_ORACLE_THRESHOLD


def _load_evaluation_model(target: Path, spec_id: str):
    """Build the `evaluation_model` block from the 006 overlay, or `None`.

    References the overlay by `spec_oracle_id` + AC counts (never the check
    bodies). A baseline-oracle-only target (no overlay) yields `None` — ADR-0016:
    a plan exists even without a spec-oracle.
    """
    checks_json = target / ".servo" / "spec-oracles" / spec_id / "checks.json"
    if not checks_json.is_file():
        return None
    try:
        plan = json.loads(checks_json.read_text())
    except (json.JSONDecodeError, OSError):
        # A present-but-unreadable overlay is treated as absent rather than
        # failing the whole compile — the overlay is an optional enrichment.
        return None
    if not isinstance(plan, dict):
        return None
    return {
        "spec_oracle_id": plan.get("spec_id") or spec_id,
        "ac_count": len(plan.get("checks", []) or []),
        "residual": len(plan.get("residual_judgment", []) or []),
    }


# ---------------------------------------------------------------------------
# Compile + persistence
# ---------------------------------------------------------------------------

def _budget_hash(budget: dict, driver: str) -> str:
    """sha256 hex digest of the canonical-JSON `{budget, driver}` (016-03 A5).

    Only these two fields — the ones this slice's ACs and `loop.py` actually
    consume — are hashed; the other referenced-not-copied plan fields (per
    ADR-0016) are producer identity, not human-editable surface. `sort_keys`
    makes the digest independent of key insertion order, so an edit that
    reorders keys without changing values does not spuriously read as drift.
    """
    canonical = json.dumps({"budget": budget, "driver": driver}, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compile_plan(target: Path, spec_path: Path) -> tuple:
    """Assemble the execution plan. Returns ``(spec_id, plan_dict)``.

    Raises EnvError before any artifact is written (the caller persists only on
    success, so a failed compile never leaves a torn plan).
    """
    if not spec_path.is_file():
        raise EnvError("spec_missing", f"spec not found: {spec_path}")

    spec_id = _spec_id_from_path(spec_path)

    # The suitable-only precondition (015-03 gate) comes first.
    suitability_ref = _require_suitable(target, spec_id)
    oracle = _load_oracle(target)
    evaluation_model = _load_evaluation_model(target, spec_id)

    budget = {
        "max_iterations": BUDGET_MAX_ITERATIONS,
        "cost_ceiling_usd": BUDGET_COST_CEILING_USD,
        "context_fill_threshold": BUDGET_CONTEXT_FILL_THRESHOLD,
        "plateau_window": BUDGET_PLATEAU_WINDOW,
    }
    driver = DEFAULT_DRIVER

    # Key insertion order is load-bearing (ADR-0016 schema order): schema_version
    # first (mirrors every servo artifact), then identity, then the referenced
    # models, then the planning knobs, then provenance. `budget_hash` (016-03
    # AC4/A5) is stamped over the VALUES BEING WRITTEN for this compile, so a
    # subsequent compile can tell whether a human edited `budget`/`driver`
    # in between (recompile-preserve, `write_plan`).
    plan = {
        "schema_version": SCHEMA_VERSION,
        "spec_id": spec_id,
        "compiled_at": iso_now(),
        "suitability_ref": suitability_ref,
        "oracle": oracle,
        "evaluation_model": evaluation_model,
        "budget": budget,
        "driver": driver,
        "prompt_ref": str(spec_path),
        "provenance": "compiled",
        "budget_hash": _budget_hash(budget, driver),
    }
    return spec_id, plan


def write_plan(target: Path, spec_id: str, plan: dict, *, force: bool = False) -> Path:
    """Atomically write the plan; return its path.

    Written under the git-ignored `.servo/plans/<spec-id>/` (covered by the
    existing `.servo/` ignore rule). Insertion order preserved (no `sort_keys`).

    Slice 016-03 AC4/A5 (recompile-preserve): before overwriting an EXISTING
    plan at this path, recompute what its `budget_hash` should be from its own
    current on-disk `budget`/`driver` and compare to its own recorded
    `budget_hash`. A mismatch means the content drifted since it was last
    (re)compiled — regardless of what its `provenance` field claims — so this
    raises `EnvError("plan_edit_detected", ...)` and does NOT overwrite,
    unless `force=True` bypasses the check unconditionally. No existing plan,
    or one whose content still matches its own hash, is unaffected —
    unconditional overwrite, exactly as before this slice.

    Two deliberate fail-OPEN edge cases (there is no coherent edit to protect
    in either, so refusing would only add friction, not safety):
    - **Unreadable/malformed existing `plan.json`** (`existing = None` below):
      overwritten unconditionally, same as if no plan existed. A corrupt file
      is not a human's edit worth preserving.
    - **Existing plan with no `budget_hash` field at all** (`recorded_hash is
      None` below) — e.g. a plan compiled by 016-01, before this slice
      existed: there is no recorded baseline to detect drift against, so the
      overwrite proceeds exactly as it did before 016-03. The very next
      compile stamps a `budget_hash`, so drift detection is live from then on.
    """
    out_dir = target / ".servo" / "plans" / spec_id
    out_path = out_dir / "plan.json"
    if not force and out_path.is_file():
        try:
            existing = json.loads(out_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = None
        if isinstance(existing, dict):
            recorded_hash = existing.get("budget_hash")
            current_hash = _budget_hash(
                existing.get("budget") or {}, existing.get("driver")
            )
            if recorded_hash is not None and recorded_hash != current_hash:
                raise EnvError(
                    "plan_edit_detected",
                    f"plan at {out_path} was edited since it was last "
                    f"compiled (budget/driver content no longer matches its "
                    f"recorded budget_hash); refusing to overwrite the edit. "
                    f"Pass --force to recompile and discard it.",
                )
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / f"{TMP_PREFIX}plan.json{TMP_SUFFIX}"
    tmp.write_text(json.dumps(plan, indent=2) + "\n")
    os.replace(tmp, out_path)
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _run_compile(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    spec_path = Path(args.spec).resolve()
    try:
        spec_id, plan = compile_plan(target, spec_path)
        out_path = write_plan(target, spec_id, plan, force=args.force)
    except EnvError as exc:
        # Env errors are unchanged in every mode (015-04's "env errors
        # unchanged under --json"): structured stderr reason, exit 2, no
        # JSON envelope, no torn artifact.
        print(f"servo: {exc.reason}: {exc}", file=sys.stderr)
        return 2
    if args.json:
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "spec_id": spec_id,
            "status": "compiled",
            "plan_path": str(out_path),
            "provenance": plan["provenance"],
            "driver": plan["driver"],
            "budget": plan["budget"],
        }
        print(json.dumps(envelope, indent=2))
    else:
        print(f"servo: execution plan for {spec_id} compiled -> {out_path}")
    return 0


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="execution_plan.py",
        description="servo execution-planner — the ADR-0016 Compile→Run handoff.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    compile_p = sub.add_parser(
        "compile", help="compile the ADR-0016 execution plan for a spec"
    )
    compile_p.add_argument("target", help="target project directory")
    compile_p.add_argument(
        "--spec", dest="spec", required=True, help="path to the spec.md to plan"
    )
    compile_p.add_argument(
        "--force", action="store_true",
        help=(
            "bypass the recompile-preserve refusal (016-03 AC4) and "
            "overwrite an existing plan.json even if its budget/driver "
            "content was hand-edited since it was last compiled"
        ),
    )
    compile_p.add_argument(
        "--json", action="store_true",
        help=(
            "on success, print a structured JSON outcome envelope "
            "(schema_version/spec_id/status/plan_path/provenance/driver/"
            "budget) instead of the human confirmation line; env-error "
            "refusals are unchanged in every mode (016-04 AC3)"
        ),
    )

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "compile":
        return _run_compile(args)
    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
