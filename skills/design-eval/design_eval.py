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

Python 3.10+ standard library only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
COMPONENT = "design_fidelity"
DEFAULT_WEIGHT = 1.0
_DRIVER_ANCHOR = 'weighted_sum="0"'

_FRAGMENT = """# SEED:start design_fidelity
score_design_fidelity() {
  python3 .servo/design-eval/score.py "$PWD"
}
# SEED:end design_fidelity
"""


def _load_score():
    """Single source of truth for the freeze hashing — reuse score.py's helpers."""
    spec = importlib.util.spec_from_file_location("design_eval_score", SKILL_DIR / "score.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_score = _load_score()


def _eval_dir(target: Path) -> Path:
    return target / ".servo" / "design-eval"


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init(target: Path) -> Path:
    """Scaffold ``.servo/design-eval/`` with the runtime + a config skeleton."""
    d = _eval_dir(target)
    for sub in ("", "refs", "setups", "shots"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    for runtime in ("score.py", "capture.mjs"):
        src = SKILL_DIR / runtime
        if src.is_file():
            shutil.copyfile(src, d / runtime)
    cfg = d / "config.json"
    example = SKILL_DIR / "templates" / "config.example.json"
    if not cfg.is_file() and example.is_file():
        shutil.copyfile(example, cfg)
    return d


def capture_refs(target: Path) -> int:
    """Render the mockup references via ``capture.mjs --refs`` (Playwright)."""
    d = _eval_dir(target)
    proc = subprocess.run(["node", str(d / "capture.mjs"), "--refs"], cwd=str(d))
    return proc.returncode


def freeze(target: Path) -> dict:
    """Pin + hash the definition (model/n/δ/threshold/screens) plus the rubric +
    reference + setup files; set ``approval_status: approved`` (ADR-0005 clause 2)."""
    d = _eval_dir(target)
    cfg_path = d / "config.json"
    if not cfg_path.is_file():
        raise FileNotFoundError(f"no config to freeze: {cfg_path}")
    config = json.loads(cfg_path.read_text())
    for s in config.get("screens", []):
        for rel in (s.get("reference"), s.get("setup")):
            if rel and not (d / rel).is_file():
                raise FileNotFoundError(
                    f"screen {s['id']!r}: missing {rel} — capture references / write the setup first")
    config["hashes"] = _score.artifact_hashes(config, d)
    config["approved_content_hash"] = _score.definition_hash(config)
    config["approval_status"] = "approved"
    config["approved_at"] = _iso_now()
    cfg_path.write_text(json.dumps(config, indent=2) + "\n")
    return config


def install(target: Path, weight: float = DEFAULT_WEIGHT) -> None:
    """Splice ``score_design_fidelity`` into ``oracle.sh`` + register it.

    Idempotent (mirrors oracle_overlay.install): an existing SEED block is
    replaced and the COMPONENTS weight refreshed; baseline components untouched.
    """
    oracle = target / "oracle.sh"
    if not oracle.is_file():
        raise FileNotFoundError(f"oracle.sh not found: {oracle} (scaffold the target first)")
    init(target)  # ensure runtime is present (won't clobber an existing config.json)

    text = oracle.read_text()
    block_re = re.compile(
        r"# SEED:start " + COMPONENT + r"\n.*?# SEED:end " + COMPONENT + r"\n", re.DOTALL)
    if block_re.search(text):
        text = block_re.sub(lambda _m: _FRAGMENT, text, count=1)
    else:
        text, n = re.subn(
            re.escape(_DRIVER_ANCHOR), lambda m: _FRAGMENT + "\n" + m.group(0), text, count=1)
        if n == 0:
            raise ValueError(
                "could not find the driver-loop anchor in oracle.sh; is this a servo oracle?")

    entry = f'"{COMPONENT}:{weight}"'
    entry_re = re.compile(r'"' + COMPONENT + r':[^"]*"')
    if entry_re.search(text):
        text = entry_re.sub(lambda _m: entry, text, count=1)
    else:
        text, n = re.subn(
            r"COMPONENTS=\(\s*\n", lambda _m: f'COMPONENTS=(\n  {entry}\n', text, count=1)
        if n == 0:
            raise ValueError("could not find COMPONENTS=( in oracle.sh")

    oracle.write_text(text)
    _register_manifest(target)


def _register_manifest(target: Path) -> None:
    manifest = target / ".servo" / "install.json"
    if not manifest.is_file():
        return
    data = json.loads(manifest.read_text())
    components = data.setdefault("components", [])
    if COMPONENT not in components:
        components.append(COMPONENT)
        manifest.write_text(json.dumps(data, indent=2) + "\n")


def uninstall(target: Path) -> None:
    """Remove the SEED block + COMPONENTS entry; keep the frozen artifacts."""
    oracle = target / "oracle.sh"
    if not oracle.is_file():
        raise FileNotFoundError(f"oracle.sh not found: {oracle}")
    text = oracle.read_text()
    text = re.sub(
        r"# SEED:start " + COMPONENT + r"\n.*?# SEED:end " + COMPONENT + r"\n",
        "", text, flags=re.DOTALL)
    text = re.sub(r'[ \t]*"' + COMPONENT + r':[^"]*"\n', "", text)
    oracle.write_text(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="design_eval.py", description="Author a design-fidelity eval component.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("init", "capture-refs", "freeze", "install", "uninstall"):
        sp = sub.add_parser(name)
        sp.add_argument("target", type=Path)
        if name == "install":
            sp.add_argument("--weight", type=float, default=DEFAULT_WEIGHT)
    args = parser.parse_args(argv)
    target = args.target.resolve()

    if args.cmd == "init":
        init(target)
        print(f"scaffolded {_eval_dir(target)}")
    elif args.cmd == "capture-refs":
        return capture_refs(target)
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
