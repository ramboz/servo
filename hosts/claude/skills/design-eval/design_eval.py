#!/usr/bin/env python3
"""Authoring CLI for a design-fidelity eval component (servo design-eval).

Scaffolds, freezes, and installs a project-authored ``score_design_fidelity``
oracle component. The *project* owns the policy (screens, rubric, model, n, δ,
threshold); servo owns the mechanism (capture + judge + freeze + the runtime
``score.py``). Mirrors spec-oracle's overlay install/approve so a design-eval
component drops into the same oracle.sh + 0/1/2 contract unchanged.

Subcommands:
  init <target>          scaffold .servo/design-eval/ (runtime + config skeleton)
  capture-refs <target>  render the mockup references via capture.mjs --refs
  freeze <target>        pin + hash the definition; approval_status=approved
  install <target>       splice score_design_fidelity into oracle.sh + manifest
  uninstall <target>     remove it (keeps the frozen artifacts)
  advisory <target>      subagent advisory read (029-02) — a loud, non-frozen
                         fidelity read; NOT the oracle path, NOT a gating score

Python 3.9+ standard library only (ADR-0020).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# 028-02: a human-owner's deliberateness bypass for the freeze-exclusion ack
# (a JIG_*-style signal, ADR-0011). Acknowledging via env is recorded as
# self_approved — never silently upgraded to `reviewed`.
_ACK_EXCLUSIONS_ENV = "SERVO_DESIGN_EVAL_ACK_EXCLUSIONS"

SKILL_DIR = Path(__file__).resolve().parent
COMMON_DIR = SKILL_DIR.parent / "_common"
# Mirrors score.py's EXIT_ENV_ERROR: oracle.sh treats rc=2 as a missing
# component → gate env_error, never a silent 0.0 (ADR-0005).
ENV_ERROR_RC = 2

COMPONENT = "design_fidelity"
DEFAULT_WEIGHT = 1.0

_FRAGMENT = """# SEED:start design_fidelity
score_design_fidelity() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "missing: python3 (design-eval)" >&2
    return 2
  fi
  python3 .servo/design-eval/score.py "$PWD"
}
# SEED:end design_fidelity
"""


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_score():
    """Single source of truth for the freeze hashing — reuse score.py's helpers."""
    return _load_module("design_eval_score", SKILL_DIR / "score.py")


_score = _load_score()
# Reuse the fidelity_eval module _score already loaded via its own two-candidate
# probe (`score.py::_load_fidelity_eval()`), rather than loading the same
# stateless file a second time under a second module object.
_fe = _score._fe


def _eval_dir(target: Path) -> Path:
    return target / ".servo" / "design-eval"


def init(target: Path) -> Path:
    """Scaffold ``.servo/design-eval/`` with the runtime + a config skeleton.

    Copies ``fidelity_eval.py`` from ``skills/_common/`` alongside the
    existing ``score.py``/``capture.mjs``/``capture_lib.mjs`` copies — ``score.py``'s two-candidate
    import probe (ADR-0024) resolves it from this same-directory copy once
    installed in an arbitrary target."""
    d = _eval_dir(target)
    for sub in ("", "refs", "setups", "shots"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    for runtime, src_dir in (
        ("score.py", SKILL_DIR), ("capture.mjs", SKILL_DIR),
        ("capture_lib.mjs", SKILL_DIR), ("fidelity_eval.py", COMMON_DIR),
        ("pngcrop.py", SKILL_DIR),  # 027-04: sibling stdlib PNG cropper for native providers
    ):
        src = src_dir / runtime
        if src.is_file():
            shutil.copyfile(src, d / runtime)
    cfg = d / "config.json"
    example = SKILL_DIR / "templates" / "config.example.json"
    if not cfg.is_file() and example.is_file():
        shutil.copyfile(example, cfg)
    return d


def capture_refs(target: Path) -> int:
    """Render the mockup references via ``capture.mjs --refs`` (Playwright).

    A missing ``node`` returns the env-error rc rather than escaping as an
    uncaught ``FileNotFoundError`` traceback — mirroring ``score.capture_app``,
    which already converts the same failure into an ``EnvError``. servo ships no
    browser, so "node absent" is an ordinary environment outcome, not a crash.
    """
    d = _eval_dir(target)
    try:
        proc = subprocess.run(["node", str(d / "capture.mjs"), "--refs"], cwd=str(d))
    except FileNotFoundError as e:
        print(f"capture-refs: node unavailable: {e}", file=sys.stderr)
        return ENV_ERROR_RC
    return proc.returncode


def freeze(target: Path, *, acknowledge: bool = False, reviewer: str = None) -> dict:
    """Pin + hash the definition (model/n/δ/threshold/screens) plus the structured
    policy (dimensions + ignore) + reference + setup files; set
    ``approval_status: approved`` (ADR-0005 clause 2). Refuses a legacy v1
    free-text-`rubric` config with a re-author message (028-01 / ADR-0033).

    028-02: surfaces the exclusion list and refuses unless the exclusions are
    acknowledged — by a distinct ``reviewer`` (→ ``approval_provenance: reviewed``,
    the prevention path) or a human owner via ``acknowledge`` /
    ``SERVO_DESIGN_EVAL_ACK_EXCLUSIONS`` (→ ``self_approved``, auditability-only)."""
    d = _eval_dir(target)
    cfg_path = d / "config.json"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"no config to freeze: {cfg_path}")
    config = json.loads(cfg_path.read_text())
    _score._require_schema_v2(config)   # 028-01: no v1 rubric freezes
    _score._validate_policy(config)     # 028-01: dimensions/ignore well-formed
    # 028-02 (ADR-0033 §4): SURFACE the exclusion list to an approver, and refuse to
    # stamp `approved` unless a distinct reviewer signed off (→ prevention) or a human
    # owner acknowledged it (→ self_approved / auditability-only). A self-ack is never
    # silently upgraded to `reviewed`.
    print(_score._exclusion_summary(config), file=sys.stderr)
    env_ack = os.environ.get(_ACK_EXCLUSIONS_ENV, "").lower() in ("1", "true", "yes", "on")
    if reviewer:
        provenance, approved_by = "reviewed", reviewer
    elif acknowledge or env_ack:
        provenance, approved_by = "self_approved", "self"
    else:
        raise _score.EnvError(
            "freeze refused: the exclusion list above was not acknowledged. Re-run "
            "with --reviewer <id> (a party distinct from the author who has reviewed "
            "the exclusions — the prevention path, ADR-0033) OR "
            "--acknowledge-exclusions / SERVO_DESIGN_EVAL_ACK_EXCLUSIONS=1 (a human "
            "owner accepting them; recorded as self_approved / auditability-only).")
    for s in config.get("screens", []):
        for rel in (s.get("reference"), s.get("setup")):
            if rel and not (d / rel).is_file():
                raise FileNotFoundError(
                    f"screen {s['id']!r}: missing {rel} — "
                    "capture references / write the setup first")
    config["hashes"] = _score.artifact_hashes(config, d)
    config["approved_content_hash"] = _score.definition_hash(config)
    config["approval_status"] = "approved"
    config["approval_provenance"] = provenance
    config["approved_by"] = approved_by
    config["approved_at"] = _fe.iso_now()
    cfg_path.write_text(json.dumps(config, indent=2) + "\n")
    return config


def install(target: Path, weight: float = DEFAULT_WEIGHT) -> None:
    """Splice ``score_design_fidelity`` into ``oracle.sh`` + register it.

    Idempotent (mirrors oracle_overlay.install): an existing SEED block is
    replaced and the COMPONENTS weight refreshed; baseline components untouched.
    Delegates the splice/registration mechanics to the shared module
    (ADR-0024) so a second caller (content-fidelity) can reuse the same
    regex logic under its own component name.
    """
    oracle = target / "oracle.sh"
    if not oracle.is_file():
        raise FileNotFoundError(f"oracle.sh not found: {oracle} (scaffold the target first)")
    init(target)  # ensure runtime is present (won't clobber an existing config.json)

    text = oracle.read_text()
    text = _fe.splice_component(text, COMPONENT, _FRAGMENT)
    text = _fe.splice_components_entry(text, COMPONENT, weight)
    oracle.write_text(text)
    _fe.register_manifest(target, COMPONENT)


def uninstall(target: Path) -> None:
    """Remove the SEED block + COMPONENTS entry and deregister from the install
    manifest; keep the frozen artifacts. Symmetric with ``install`` (which both
    splices and registers), so ``.servo/install.json`` never lists a component
    that is no longer in ``oracle.sh``."""
    oracle = target / "oracle.sh"
    if not oracle.is_file():
        raise FileNotFoundError(f"oracle.sh not found: {oracle}")
    text = oracle.read_text()
    text = _fe.unsplice_component(text, COMPONENT)
    oracle.write_text(text)
    _fe.deregister_manifest(target, COMPONENT)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="design_eval.py", description="Author a design-fidelity eval component.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("init", "capture-refs", "freeze", "install", "uninstall", "advisory"):
        sp = sub.add_parser(name)
        sp.add_argument("target", type=Path)
        if name == "install":
            sp.add_argument("--weight", type=float, default=DEFAULT_WEIGHT)
        if name == "freeze":
            # 028-02: acknowledge / review the surfaced exclusion list.
            sp.add_argument("--acknowledge-exclusions", action="store_true",
                            help="human owner accepts the exclusions (→ self_approved)")
            sp.add_argument("--reviewer", default=None,
                            help="id of a distinct reviewer who vetted the exclusions "
                                 "(→ reviewed / the prevention path)")
    args = parser.parse_args(argv)
    target = args.target.resolve()

    if args.cmd == "init":
        init(target)
        print(f"scaffolded {_eval_dir(target)}")
    elif args.cmd == "capture-refs":
        return capture_refs(target)
    elif args.cmd == "freeze":
        # 028-02: a refusal (unacknowledged exclusions) or a missing reference is an
        # expected, guided outcome — surface it as a clean line + rc 2, not a
        # traceback (mirrors the `advisory` branch below).
        try:
            cfg = freeze(target, acknowledge=args.acknowledge_exclusions,
                         reviewer=args.reviewer)
        except (_score.StaleError, _score.EnvError, FileNotFoundError) as e:
            print(f"design-eval: freeze refused — {e}", file=sys.stderr)
            return ENV_ERROR_RC
        print(f"frozen (approval_status=approved, "
              f"approval_provenance={cfg.get('approval_provenance')})")
    elif args.cmd == "install":
        install(target, args.weight)
        print(f"installed {COMPONENT} (weight {args.weight})")
    elif args.cmd == "uninstall":
        uninstall(target)
        print(f"uninstalled {COMPONENT}")
    elif args.cmd == "advisory":
        # 029-02 (ADR-0034): the ONLY entrypoint that runs the subagent judge — a
        # loud, non-frozen advisory read, structurally separate from the oracle
        # `score.py` path (which refuses `subagent` transport). Never prints a bare
        # float: the output is labelled ADVISORY so it cannot be mistaken for, or
        # piped as, a gating score.
        try:
            composite, model = _score.advisory_read(_eval_dir(target))
        except (_score.StaleError, _score.EnvError) as e:
            print(f"design-eval: advisory unavailable — {e}", file=sys.stderr)
            return ENV_ERROR_RC
        print(f"ADVISORY (subagent, non-frozen): composite={composite:.4f} — "
              f"self-reported model {model!r}; NOT a gating score.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
