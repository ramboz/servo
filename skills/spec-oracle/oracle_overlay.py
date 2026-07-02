"""
servo spec-oracle — slice 006-03 (oracle-overlay), colocated by slice 019-02
(ADR-0023: co-locate durable spec-oracle artifacts with the spec)

Compile a checked plan into an *installable oracle component*. The spec-oracle
becomes an ordinary servo `oracle.sh` component so the existing `gate.py` /
`loop.py` contract scores it with no special-casing (slice 006-03 AC5).

Three artifacts/operations:

  generate <target> <spec-dir> <spec-id> [--vendor-engine]
      Write `<spec-dir>/oracle/<id>/oracle.sh.fragment` (a
      `# SEED:start spec_oracle_<id>` / `# SEED:end spec_oracle_<id>` block
      wrapping a `score_spec_oracle_<id>` function). By default the fragment
      *references* the shared, plugin-sibling `checks.py` rather than copying
      it (ADR-0023 AC3); `--vendor-engine` still copies a private `checks.py`
      alongside the plan for the documented clone-portability case (a
      Routine/CI that clones the repo without the servo plugin installed).

  install <target> <spec-dir> <spec-id> [--weight W] [--vendor-engine]
      generate, then splice the component into `<target>/oracle.sh`: insert the
      SEED block before the driver loop and register `spec_oracle_<id>:W` in the
      COMPONENTS array, without disturbing existing baseline components (AC2).
      Idempotent — re-installing replaces the block and updates the weight.

  uninstall <target> <spec-id>
      Remove the SEED block and the COMPONENTS entry from `oracle.sh`, leaving
      the plan/check artifacts under the spec's own oracle dir intact (AC6).

The generated `score_spec_oracle_<id>` runs the engine in `--score-only` mode:
it prints the composite check score and returns 2 iff any check env-errored
(so `oracle.sh` marks the component missing → rc=2, AC3). Each run appends
evidence to `<spec-dir>/oracle/<id>/ledger.jsonl` (AC4).

**Artifact location (ADR-0023, slice 019-02).** The durable, spec-bound
artifacts (`plan.md`, `checks.json`, `oracle.sh.fragment`, and an opt-in
vendored `checks.py`) live under `<spec_dir>/oracle/<spec_id>/` — resolved
relative to the *spec's own directory* passed in as `spec_dir`, never the
target — so a spec and its oracle travel together in git/review. `.servo/`
under the target retains only run-scoped state (the install manifest, loop
runs, etc.) — unaffected by this slice. `oracle_dir_for_spec` is the one
shared path helper (`oracle_plan.py` imports it too, replacing its own former
independent path construction); it falls back to the legacy
`<target>/.servo/spec-oracles/<spec_id>/` location when the new spec-relative
location has no `checks.json` yet, so a pre-019-02 install is not broken
(AC5 — soft migration, no explicit `migrate` step required).

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
# .format) because the body is bash full of braces. `__ENGINE__` is the path
# to checks.py (either the shared plugin-sibling copy or a vendored local
# one); `__ORACLE_DIR__` is the spec-relative oracle dir (checks.json /
# ledger always live there, regardless of where the engine is resolved from).
_FRAGMENT_TEMPLATE = """# SEED:start __NAME__
__FN__() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "missing: python3 (spec-oracle __SPEC_ID__)" >&2
    return 2
  fi
  python3 "__ENGINE__" \\
    "__ORACLE_DIR__/checks.json" \\
    --base-dir . \\
    --ledger "__ORACLE_DIR__/ledger.jsonl" \\
    --enforce-freeze \\
    --score-only
}
# SEED:end __NAME__"""

# The shared check engine, resolved relative to this module (the plugin
# install), not the target — so a target need not vendor checks.py to score
# an overlay (ADR-0023 AC3).
_SHARED_ENGINE_PATH = Path(__file__).resolve().parent / "checks.py"


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


def render_fragment(spec_id: str, *, spec_oracle_dir: str,
                    vendor_engine: bool = False) -> str:
    """Return the `# SEED:start/end` block (the score function) for a spec id.

    ``spec_oracle_dir`` is the oracle dir's path *as written into the bash
    fragment* — relative to the target root, since the oracle runs with the
    target as cwd (the gate contract). ``checks.json`` / ``ledger.jsonl``
    always resolve under it. The check engine resolves to the vendored local
    copy (``<spec_oracle_dir>/checks.py``) when ``vendor_engine`` is set,
    else to the shared plugin-sibling ``checks.py`` (ADR-0023 AC3) at its
    absolute install path.
    """
    name = component_name(spec_id)
    engine = (f"{spec_oracle_dir}/checks.py" if vendor_engine
             else str(_SHARED_ENGINE_PATH))
    return (_FRAGMENT_TEMPLATE
            .replace("__NAME__", name)
            .replace("__FN__", "score_" + name)
            .replace("__SPEC_ID__", spec_id)
            .replace("__ENGINE__", engine)
            .replace("__ORACLE_DIR__", spec_oracle_dir))


def _legacy_oracle_dir(target: Path, spec_id: str) -> Path:
    """The pre-019-02 artifact location (``<target>/.servo/spec-oracles/<id>/``).

    Retained only as a read-fallback (AC5 migration) — nothing writes here
    anymore.
    """
    return target / ".servo" / "spec-oracles" / spec_id


def oracle_dir_for_spec(spec_dir: Path, spec_id: str, *,
                        target: Optional[Path] = None) -> Path:
    """The one shared path helper: where a spec-oracle's durable artifacts
    live (ADR-0023, slice 019-02).

    Resolves to ``<spec_dir>/oracle/<spec_id>/`` — relative to the spec's own
    directory, never the target. If that location has no ``checks.json`` yet
    *and* a ``target`` is supplied with a legacy
    ``<target>/.servo/spec-oracles/<spec_id>/checks.json`` present, falls back
    to the legacy location (AC5 — soft migration: a pre-019-02 install keeps
    working without an explicit migration step). The new location always wins
    once it has its own plan.

    Validates ``spec_id`` itself (rather than trusting each caller to have
    done so) — this is the one path-construction chokepoint every caller
    (this module's own `generate`/`install`/`approve`, and `oracle_plan.py`'s
    planner) funnels through, so a malformed or path-traversal-shaped
    ``spec_id`` (e.g. ``../../etc``) is rejected here regardless of which
    caller reaches it.
    """
    _validate_spec_id(spec_id)
    new_dir = spec_dir / "oracle" / spec_id
    if target is not None and not (new_dir / "checks.json").is_file():
        legacy_dir = _legacy_oracle_dir(target, spec_id)
        if (legacy_dir / "checks.json").is_file():
            return legacy_dir
    return new_dir


def generate(target: Path, spec_dir: Path, spec_id: str, *,
            vendor_engine: bool = False) -> dict:
    """Write the fragment (and, opt-in, a vendored copy of the check engine).

    Requires the plan (`checks.json`) to already exist under the spec's
    oracle directory (or its legacy `.servo/spec-oracles/<id>/` location, AC5);
    raises ``FileNotFoundError`` otherwise (nothing to compile). Returns the
    written paths.
    """
    _validate_spec_id(spec_id)
    oracle_dir = oracle_dir_for_spec(spec_dir, spec_id, target=target)
    checks_json = oracle_dir / "checks.json"
    if not checks_json.is_file():
        raise FileNotFoundError(
            f"no plan to compile: {checks_json} not found "
            f"(run the spec-oracle planner first)")

    # The fragment's paths are relative to the target root (oracle.sh runs
    # with the target as cwd); express the oracle dir that way regardless of
    # whether it resolved to the new or legacy location.
    try:
        rel_oracle_dir = oracle_dir.resolve().relative_to(target.resolve())
    except ValueError:
        # The spec dir lives outside the target root — fall back to the
        # absolute path so the fragment still resolves correctly at runtime.
        rel_oracle_dir = oracle_dir.resolve()

    fragment_path = oracle_dir / "oracle.sh.fragment"
    fragment_path.write_text(
        render_fragment(spec_id, spec_oracle_dir=str(rel_oracle_dir),
                        vendor_engine=vendor_engine) + "\n")

    result = {"fragment": fragment_path}
    if vendor_engine:
        # Vendor a private copy alongside the plan for the documented
        # clone-portability case (a Routine/CI that clones the repo without
        # the servo plugin installed) — the old default behavior, now opt-in.
        checks_py = oracle_dir / "checks.py"
        shutil.copyfile(_SHARED_ENGINE_PATH, checks_py)
        result["checks_py"] = checks_py

    return result


def install(target: Path, spec_dir: Path, spec_id: str,
           weight: float = DEFAULT_WEIGHT, *, vendor_engine: bool = False) -> None:
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

    generate(target, spec_dir, spec_id, vendor_engine=vendor_engine)

    oracle_dir = oracle_dir_for_spec(spec_dir, spec_id, target=target)
    try:
        rel_oracle_dir = oracle_dir.resolve().relative_to(target.resolve())
    except ValueError:
        rel_oracle_dir = oracle_dir.resolve()

    name = component_name(spec_id)
    fragment = render_fragment(spec_id, spec_oracle_dir=str(rel_oracle_dir),
                               vendor_engine=vendor_engine)
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

    Deletes the SEED block and the COMPONENTS entry only; the plan, any
    vendored `checks.py`, and the ledger under the spec's own oracle dir are
    preserved so the overlay can be re-installed or inspected (AC6). Never
    touches `.servo/` (AC4).
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
    spec = importlib.util.spec_from_file_location(
        "checks_engine", _SHARED_ENGINE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def approve(target: Path, spec_dir: Path, spec_id: str) -> dict:
    """Freeze the overlay: verify source fidelity, prove every negative control
    can fail, record artifact hashes, and set ``approval_status: approved``.

    Refuses (``ValueError``) if the source spec changed since planning (AC2 —
    re-plan, don't approve) or if any check's negative control does not actually
    fail (AC4 — the check is not falsifiable, so it could pass vacuously and let
    the loop self-grade). ``oracle.sh.fragment`` is always hashed into
    ``approved_artifacts`` (AC3); a vendored ``checks.py`` is hashed too, only
    when present (the `--vendor-engine` opt-in). The runtime freeze gate
    (`checks.py --enforce-freeze`) compares against these on every score.
    """
    _validate_spec_id(spec_id)
    oracle_dir = oracle_dir_for_spec(spec_dir, spec_id, target=target)
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

    # 3. Record approved-artifact hashes (AC3); generate/install must run
    #    first. `checks.py` is only hashed when vendored (opt-in) — the
    #    shared plugin-sibling copy is not a per-overlay artifact to pin.
    artifacts = {}
    fragment = oracle_dir / "oracle.sh.fragment"
    if not fragment.is_file():
        raise FileNotFoundError(
            "missing generated artifact oracle.sh.fragment; "
            "run install/generate first")
    artifacts["oracle.sh.fragment"] = _sha256_file(fragment)
    vendored_engine = oracle_dir / "checks.py"
    if vendored_engine.is_file():
        artifacts["checks.py"] = _sha256_file(vendored_engine)

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
    for cmd in ("generate", "install", "approve"):
        sp = sub.add_parser(cmd)
        sp.add_argument("target")
        sp.add_argument("spec_dir")
        sp.add_argument("spec_id")
        if cmd == "install":
            sp.add_argument("--weight", type=float, default=DEFAULT_WEIGHT)
        if cmd in ("generate", "install"):
            sp.add_argument("--vendor-engine", dest="vendor_engine",
                            action="store_true",
                            help="copy checks.py alongside the plan instead of "
                                 "referencing the shared plugin-sibling copy "
                                 "(clone-portability opt-in)")
    sp = sub.add_parser("uninstall")
    sp.add_argument("target")
    sp.add_argument("spec_id")
    args = parser.parse_args(argv)

    target = Path(args.target)
    try:
        if args.cmd == "generate":
            spec_dir = Path(args.spec_dir)
            paths = generate(target, spec_dir, args.spec_id,
                             vendor_engine=args.vendor_engine)
            print(f"servo: generated overlay for {args.spec_id} -> "
                  f"{paths['fragment'].parent}")
        elif args.cmd == "install":
            spec_dir = Path(args.spec_dir)
            install(target, spec_dir, args.spec_id, args.weight,
                   vendor_engine=args.vendor_engine)
            print(f"servo: installed component {component_name(args.spec_id)} "
                  f"into {target / 'oracle.sh'}")
        elif args.cmd == "uninstall":
            uninstall(target, args.spec_id)
            print(f"servo: removed component {component_name(args.spec_id)} "
                  f"from {target / 'oracle.sh'} (artifacts kept)")
        elif args.cmd == "approve":
            spec_dir = Path(args.spec_dir)
            approve(target, spec_dir, args.spec_id)
            print(f"servo: approved spec-oracle {args.spec_id} "
                  f"(frozen — re-plan to change)")
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
