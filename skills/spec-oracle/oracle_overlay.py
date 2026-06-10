"""
servo spec-oracle — slice 006-03 (oracle-overlay)

Compile a checked plan into an *installable oracle component*. The spec-oracle
becomes an ordinary servo `oracle.sh` component so the existing `gate.py` /
`loop.py` contract scores it with no special-casing (slice 006-03 AC5).

Three artifacts/operations:

  generate <target> <spec-id>
      Write `<target>/.servo/spec-oracles/<id>/oracle.sh.fragment` (a
      `# SEED:start spec_oracle_<id>` / `# SEED:end spec_oracle_<id>` block
      wrapping a `score_spec_oracle_<id>` function) and copy the stdlib check
      engine `checks.py` alongside the plan, so the overlay is self-contained
      and project-owned (it does not depend on servo staying installed).

  install <target> <spec-id> [--weight W]
      generate, then splice the component into `<target>/oracle.sh`: insert the
      SEED block before the driver loop and register `spec_oracle_<id>:W` in the
      COMPONENTS array, without disturbing existing baseline components (AC2).
      Idempotent — re-installing replaces the block and updates the weight.

  uninstall <target> <spec-id>
      Remove the SEED block and the COMPONENTS entry from `oracle.sh`, leaving
      the plan/check artifacts under `.servo/spec-oracles/<id>/` intact (AC6).

The generated `score_spec_oracle_<id>` runs the copied engine in `--score-only`
mode: it prints the composite check score and returns 2 iff any check
env-errored (so `oracle.sh` marks the component missing → rc=2, AC3). Each run
appends evidence to `.servo/spec-oracles/<id>/ledger.jsonl` (AC4).

The `# SEED:` convention and the COMPONENTS array shape are spec 001's
(`templates/oracle.sh.template`); this module mirrors them rather than vendoring
scaffold-init code, keeping the overlay self-contained. Python stdlib only.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


COMPONENT_PREFIX = "spec_oracle_"
DEFAULT_WEIGHT = 1.0

# A spec id is a directory slug; reject anything else so it can never inject
# into the generated bash fragment or escape the spec-oracle directory.
_SPEC_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# Driver-loop anchor in the rendered oracle.sh (templates/oracle.sh.template):
# the SEED block is spliced in just before this line.
_DRIVER_ANCHOR = r'(?m)^weighted_sum="0"'

# The generated score function. Placeholders are substituted (not f-string /
# .format) because the body is bash full of braces.
_FRAGMENT_TEMPLATE = """# SEED:start __NAME__
__FN__() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "missing: python3 (spec-oracle __SPEC_ID__)" >&2
    return 2
  fi
  python3 ".servo/spec-oracles/__SPEC_ID__/checks.py" \\
    ".servo/spec-oracles/__SPEC_ID__/checks.json" \\
    --base-dir . \\
    --ledger ".servo/spec-oracles/__SPEC_ID__/ledger.jsonl" \\
    --enforce-freeze \\
    --score-only
}
# SEED:end __NAME__"""


def _validate_spec_id(spec_id: str) -> None:
    if not _SPEC_ID_RE.match(spec_id or ""):
        raise ValueError(
            f"invalid spec id {spec_id!r}: must match {_SPEC_ID_RE.pattern}")
    # Reject ".", "..", "---" and other all-punctuation ids: they have no
    # shell-safe component name and `..` would escape the spec-oracle dir.
    if not re.search(r"[A-Za-z0-9]", spec_id):
        raise ValueError(
            f"invalid spec id {spec_id!r}: must contain an alphanumeric character")


def component_name(spec_id: str) -> str:
    """The oracle component name for a spec id — a shell-safe identifier.

    Hyphens and other non-alphanumerics are collapsed to underscores so the
    name is valid as a shell function suffix (`score_<name>`) and a COMPONENTS
    entry. E.g. ``006-spec-oracle`` → ``spec_oracle_006_spec_oracle``.
    """
    _validate_spec_id(spec_id)
    slug = re.sub(r"[^0-9A-Za-z]+", "_", spec_id).strip("_")
    return COMPONENT_PREFIX + slug


def render_fragment(spec_id: str) -> str:
    """Return the `# SEED:start/end` block (the score function) for a spec id.

    Pure: paths are relative to the target root (the oracle runs with the
    target as cwd, per the gate contract); the directory uses the original
    spec id, the function/marker name uses the shell-safe component name.
    """
    name = component_name(spec_id)
    return (_FRAGMENT_TEMPLATE
            .replace("__NAME__", name)
            .replace("__FN__", "score_" + name)
            .replace("__SPEC_ID__", spec_id))


def _oracle_dir(target: Path, spec_id: str) -> Path:
    return target / ".servo" / "spec-oracles" / spec_id


def generate(target: Path, spec_id: str) -> dict:
    """Write the fragment + a self-contained copy of the check engine.

    Requires the plan (`checks.json`) to already exist under the spec-oracle
    directory; raises ``FileNotFoundError`` otherwise (nothing to compile).
    Returns the written paths.
    """
    _validate_spec_id(spec_id)
    oracle_dir = _oracle_dir(target, spec_id)
    checks_json = oracle_dir / "checks.json"
    if not checks_json.is_file():
        raise FileNotFoundError(
            f"no plan to compile: {checks_json} not found "
            f"(run the spec-oracle planner first)")

    fragment_path = oracle_dir / "oracle.sh.fragment"
    fragment_path.write_text(render_fragment(spec_id) + "\n")

    # Copy the engine alongside the plan so the overlay does not depend on the
    # servo plugin staying installed (project-owned artifact; frozen + hashed
    # in slice 006-04).
    engine_src = Path(__file__).resolve().parent / "checks.py"
    checks_py = oracle_dir / "checks.py"
    shutil.copyfile(engine_src, checks_py)

    return {"fragment": fragment_path, "checks_py": checks_py}


def install(target: Path, spec_id: str, weight: float = DEFAULT_WEIGHT) -> None:
    """Splice the overlay component into ``<target>/oracle.sh``.

    Idempotent: an existing SEED block is replaced and its COMPONENTS weight
    updated, so re-installing never duplicates the component. Baseline
    components are left untouched (AC2).
    """
    _validate_spec_id(spec_id)
    oracle = target / "oracle.sh"
    if not oracle.is_file():
        raise FileNotFoundError(
            f"oracle.sh not found: {oracle} (scaffold the target first)")

    generate(target, spec_id)  # fragment + engine copy

    name = component_name(spec_id)
    fragment = render_fragment(spec_id)
    text = oracle.read_text()

    # 1. SEED block — replace if already present, else insert before the loop.
    block_re = re.compile(
        r"# SEED:start " + re.escape(name) + r"\n.*?# SEED:end "
        + re.escape(name) + r"\n", re.DOTALL)
    if block_re.search(text):
        text = block_re.sub(lambda _m: fragment.rstrip() + "\n", text, count=1)
    else:
        text, n = re.subn(
            _DRIVER_ANCHOR,
            lambda m: fragment.rstrip() + "\n\n" + m.group(0),
            text, count=1)
        if n == 0:
            raise ValueError(
                "could not find the driver-loop anchor in oracle.sh; "
                "is this a servo-scaffolded oracle?")

    # 2. COMPONENTS entry — add if missing, else refresh the weight.
    entry = f'"{name}:{weight}"'
    entry_re = re.compile(r'"' + re.escape(name) + r':[^"]*"')
    if entry_re.search(text):
        text = entry_re.sub(lambda _m: entry, text, count=1)
    else:
        # Insert as the first array entry; `\s*` backtracks to match only
        # `COMPONENTS=(\n`, so any "# (no components …)" comment line stays
        # below the new entry.
        text, n = re.subn(r"COMPONENTS=\(\s*\n",
                          lambda _m: f'COMPONENTS=(\n  {entry}\n', text, count=1)
        if n == 0:
            raise ValueError("could not find COMPONENTS=( in oracle.sh")

    oracle.write_text(text)


def uninstall(target: Path, spec_id: str) -> None:
    """Remove the overlay component from ``oracle.sh``, keeping the artifacts.

    Deletes the SEED block and the COMPONENTS entry only; the plan, generated
    `checks.py`, and ledger under `.servo/spec-oracles/<id>/` are preserved so
    the overlay can be re-installed or inspected (AC6).
    """
    _validate_spec_id(spec_id)
    oracle = target / "oracle.sh"
    if not oracle.is_file():
        raise FileNotFoundError(f"oracle.sh not found: {oracle}")

    name = component_name(spec_id)
    text = oracle.read_text()
    block_re = re.compile(
        r"# SEED:start " + re.escape(name) + r"\n.*?# SEED:end "
        + re.escape(name) + r"\n", re.DOTALL)
    text = block_re.sub("", text)
    text = re.sub(r'[ \t]*"' + re.escape(name) + r':[^"]*"\n', "", text)
    oracle.write_text(text)


# ---------------------------------------------------------------------------
# Approval / freeze (slice 006-04)
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_engine():
    """Import the sibling check engine for the negative-control runner."""
    import importlib.util
    path = Path(__file__).resolve().parent / "checks.py"
    spec = importlib.util.spec_from_file_location("checks_engine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def approve(target: Path, spec_id: str) -> dict:
    """Freeze the overlay: verify source fidelity, prove every negative control
    can fail, record artifact hashes, and set ``approval_status: approved``.

    Refuses (``ValueError``) if the source spec changed since planning (AC2 —
    re-plan, don't approve) or if any check's negative control does not actually
    fail (AC4 — the check is not falsifiable, so it could pass vacuously and let
    the loop self-grade). The generated `checks.py` / `oracle.sh.fragment` are
    hashed into ``approved_artifacts`` (AC3); the runtime freeze gate
    (`checks.py --enforce-freeze`) compares against these on every score.
    """
    _validate_spec_id(spec_id)
    oracle_dir = _oracle_dir(target, spec_id)
    checks_json = oracle_dir / "checks.json"
    if not checks_json.is_file():
        raise FileNotFoundError(f"no plan to approve: {checks_json}")
    plan = json.loads(checks_json.read_text())

    # 1. Source spec must still hash to what the planner recorded (AC2).
    source_path = plan.get("source_spec_path")
    source_hash = plan.get("source_hash")
    if source_path and source_hash:
        src = target / source_path
        if not src.is_file():
            raise ValueError(f"source spec missing: {source_path}; re-plan first")
        if _sha256_file(src) != source_hash:
            raise ValueError(
                f"source spec changed since planning ({source_path}); "
                f"re-plan before approving")

    # 2. Every negative control must flip its check to failing (AC4). The
    #    control is a spec-override applied in isolation — non-destructive.
    engine = _load_engine()
    for check in plan.get("checks", []):
        control = check.get("negative_control")
        if isinstance(control, dict):
            mutated = {**check, **control}
            mutated.pop("negative_control", None)
            evidence = engine.run_check(mutated, target)
            if evidence.get("status") != "fail":
                raise ValueError(
                    f"negative control for {check.get('id')!r} did not fail "
                    f"(status={evidence.get('status')!r}); the check is not "
                    f"falsifiable — fix the control before approving")

    # 3. Record approved-artifact hashes (AC3); generate/install must run first.
    artifacts = {}
    for name in ("checks.py", "oracle.sh.fragment"):
        artifact = oracle_dir / name
        if not artifact.is_file():
            raise FileNotFoundError(
                f"missing generated artifact {name}; run install/generate first")
        artifacts[name] = _sha256_file(artifact)

    plan["approved_artifacts"] = artifacts
    # Tripwire-pin the approved checks themselves (review hardening): the freeze
    # gate refuses if checks.json's checks are relaxed after approval.
    plan["approved_content_hash"] = engine.plan_content_hash(plan)
    plan["approval_status"] = "approved"
    plan["approved_at"] = _iso_now()
    checks_json.write_text(json.dumps(plan, indent=2) + "\n")
    return plan


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="oracle_overlay.py",
        description="Install a spec-oracle as an oracle.sh component.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ("generate", "install", "uninstall", "approve"):
        sp = sub.add_parser(cmd)
        sp.add_argument("target")
        sp.add_argument("spec_id")
        if cmd == "install":
            sp.add_argument("--weight", type=float, default=DEFAULT_WEIGHT)
    args = parser.parse_args(argv)

    target = Path(args.target)
    try:
        if args.cmd == "generate":
            paths = generate(target, args.spec_id)
            print(f"servo: generated overlay for {args.spec_id} -> "
                  f"{paths['fragment'].parent}")
        elif args.cmd == "install":
            install(target, args.spec_id, args.weight)
            print(f"servo: installed component {component_name(args.spec_id)} "
                  f"into {target / 'oracle.sh'}")
        elif args.cmd == "uninstall":
            uninstall(target, args.spec_id)
            print(f"servo: removed component {component_name(args.spec_id)} "
                  f"from {target / 'oracle.sh'} (artifacts kept)")
        elif args.cmd == "approve":
            approve(target, args.spec_id)
            print(f"servo: approved spec-oracle {args.spec_id} "
                  f"(frozen — re-plan to change)")
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
