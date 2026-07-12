#!/usr/bin/env python3
"""Authoring CLI for a content-fidelity eval component (servo content-fidelity).

Scaffolds, freezes, and installs a project-authored ``score_content_fidelity``
oracle component. The *project* owns the policy (cases, rubric, model, n, δ,
threshold); servo owns the mechanism (gather + judge + freeze + the runtime
``score.py``). Mirrors design-eval's authoring CLI (and, one level further
back, spec-oracle's overlay install/approve) so a content-fidelity component
drops into the same oracle.sh + 0/1/2 contract unchanged.

Subcommands:
  init <target>       scaffold .servo/content-fidelity/ (runtime + config skeleton)
  freeze <target>     pin + hash the definition; approval_status=approved
  install <target>    splice score_content_fidelity into oracle.sh + manifest
  uninstall <target>  remove it (keeps the frozen artifacts)

No ``capture-refs`` equivalent: unlike design-eval's mockup-to-PNG render
step, a content-fidelity case's reference is either inline rubric/spec text
already in ``config.json`` or a plain text file the project already has —
there is nothing to *render* (AC6 / Assumption A1).

Python 3.9+ standard library only (ADR-0020).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
COMMON_DIR = SKILL_DIR.parent / "_common"
COMPONENT = "content_fidelity"
DEFAULT_WEIGHT = 1.0

_FRAGMENT = """# SEED:start content_fidelity
score_content_fidelity() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "missing: python3 (content-fidelity)" >&2
    return 2
  fi
  python3 .servo/content-fidelity/score.py "$PWD"
}
# SEED:end content_fidelity
"""


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_score():
    """Single source of truth for the freeze hashing — reuse score.py's helpers."""
    return _load_module("content_fidelity_score", SKILL_DIR / "score.py")


_score = _load_score()
# Reuse the fidelity_eval module _score already loaded via its own two-candidate
# probe (`score.py::_load_fidelity_eval()`), rather than loading the same
# stateless file a second time under a second module object.
_fe = _score._fe


def _eval_dir(target: Path) -> Path:
    return target / ".servo" / "content-fidelity"


def init(target: Path) -> Path:
    """Scaffold ``.servo/content-fidelity/`` with the runtime + a config skeleton.

    Copies ``fidelity_eval.py`` from ``skills/_common/`` alongside the
    existing ``score.py`` copy — ``score.py``'s two-candidate import probe
    (ADR-0024) resolves it from this same-directory copy once installed in an
    arbitrary target."""
    d = _eval_dir(target)
    d.mkdir(parents=True, exist_ok=True)
    for runtime, src_dir in (
        ("score.py", SKILL_DIR), ("fidelity_eval.py", COMMON_DIR),
    ):
        src = src_dir / runtime
        if src.is_file():
            shutil.copyfile(src, d / runtime)
    cfg = d / "config.json"
    example = SKILL_DIR / "templates" / "config.example.json"
    if not cfg.is_file() and example.is_file():
        shutil.copyfile(example, cfg)
    return d


def freeze(target: Path) -> dict:
    """Pin + hash the definition (model/n/δ/threshold/cases) plus the rubric +
    reference files; set ``approval_status: approved`` (ADR-0005 clause 2)."""
    d = _eval_dir(target)
    cfg_path = d / "config.json"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"no config to freeze: {cfg_path}")
    config = json.loads(cfg_path.read_text())
    for c in config.get("cases", []):
        rel = c.get("reference")
        # A reference may be inline text or a path to a file; only refuse
        # when it looks like a file reference (relative path) that is
        # actually missing — inline prose has no file to find.
        if rel and not (d / rel).is_file() and _looks_like_path(rel):
            raise FileNotFoundError(
                f"case {c['id']!r}: reference file missing: {rel} — write it first")
    config["hashes"] = _score.artifact_hashes(config, d)
    config["approved_content_hash"] = _score.definition_hash(config)
    config["approval_status"] = "approved"
    config["approved_at"] = _fe.iso_now()
    cfg_path.write_text(json.dumps(config, indent=2) + "\n")
    return config


def _looks_like_path(value: str) -> bool:
    """Heuristic: a reference that looks like a relative file path (no
    whitespace, has a path separator or a file extension) vs. inline rubric
    prose (contains spaces/newlines). Used only to decide whether a *missing*
    reference should refuse ``freeze`` — inline text is never "missing"."""
    return bool(value) and " " not in value and "\n" not in value and (
        "/" in value or "." in value)


def install(target: Path, weight: float = DEFAULT_WEIGHT) -> None:
    """Splice ``score_content_fidelity`` into ``oracle.sh`` + register it.

    Idempotent (mirrors oracle_overlay.install): an existing SEED block is
    replaced and the COMPONENTS weight refreshed; baseline components
    untouched. Delegates the splice/registration mechanics to the shared
    module (ADR-0024) rather than re-implementing them.
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
        prog="content_fidelity.py", description="Author a content-fidelity eval component.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("init", "freeze", "install", "uninstall"):
        sp = sub.add_parser(name)
        sp.add_argument("target", type=Path)
        if name == "install":
            sp.add_argument("--weight", type=float, default=DEFAULT_WEIGHT)
    args = parser.parse_args(argv)
    target = args.target.resolve()

    if args.cmd == "init":
        init(target)
        print(f"scaffolded {_eval_dir(target)}")
    elif args.cmd == "freeze":
        freeze(target)
        print("frozen (approval_status=approved)")
    elif args.cmd == "install":
        install(target, args.weight)
        print(f"installed {COMPONENT} (weight {args.weight})")
    elif args.cmd == "uninstall":
        uninstall(target)
        print(f"uninstalled {COMPONENT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
