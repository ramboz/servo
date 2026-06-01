"""
servo scaffold-init — slices 001-01..001-03

Probe a target project for tests / lint / CI / language signals and drop a
tailored `oracle.sh` + `.servo/install.json` into the target. Components are
composed from per-signal fragments under `${CLAUDE_PLUGIN_ROOT}/templates/
components/`.

Usage:
    python3 scaffold.py <target> [--force]      # install
    python3 scaffold.py detect <target>         # print detection JSON

Reads CLAUDE_PLUGIN_ROOT to locate the plugin root. Falls back to walking
parents of this script if the env var is absent (servo's own dogfood case).

Per ADR-0001, test-framework detection prefers jig's `tdd-loop/tdd.py` (via
subprocess) when present at `${CLAUDE_PLUGIN_ROOT}/jig/skills/tdd-loop/tdd.py`,
falling back to the built-in detector below.
"""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SERVO_VERSION = "0.1.0"

# Default composite-score gate. Matches the value baked into
# `templates/oracle.sh.template`. Surfaced as a Threshold decision in
# every scaffolded `<target>/.servo/refinement-todo.md` so the user is
# forced to confirm or tune it.
DEFAULT_THRESHOLD = 0.5

# Default weight per component. Test runners are weighted heavier than lint
# since they're a stronger correctness signal. These are servo's defaults;
# slice 001-04 surfaces them as a refinement-todo so the user can tune.
DEFAULT_WEIGHTS = {
    "pytest": 1.0,
    "vitest": 1.0,
    "jest": 1.0,
    "cargo": 1.0,
    "go": 1.0,
    "eslint": 0.5,
    "ruff": 0.5,
}

# Component classification for the manifest's `signals` summary.
TEST_COMPONENTS = {"pytest", "vitest", "jest", "cargo", "go"}
LINT_COMPONENTS = {"eslint", "ruff"}


def plugin_root() -> Path:
    env_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[2]


def _templates_root() -> Path:
    """Locate the templates directory in both plugin/source and scaffold modes.

    Scaffold mode (007-03/007-04): this file is vendored to
    `<target>/.claude/skills/servo-scaffold-init/scaffold.py`, and templates are
    vendored alongside it at `<target>/.claude/servo/templates` (the contract's
    `runtime_root/templates`). `parents[2]` is then `<target>/.claude`, so the
    vendored templates live at `parents[2]/servo/templates`.

    Plugin/source mode: that vendored directory does not exist, so we fall back
    to the historical `plugin_root()/templates` location. This keeps the
    bare-positional oracle-install behavior byte-for-byte unchanged in the
    source checkout (where CLAUDE_PLUGIN_ROOT may be set or fall back to
    `parents[2]`, the repo root).
    """
    vendored = Path(__file__).resolve().parents[2] / "servo" / "templates"
    if vendored.is_dir():
        return vendored
    return plugin_root() / "templates"


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Signal detection
# ---------------------------------------------------------------------------

def _detect_pytest(target: Path) -> bool:
    pyproject = target / "pyproject.toml"
    if pyproject.exists() and "[tool.pytest" in pyproject.read_text(errors="replace"):
        return True
    if (target / "pytest.ini").exists():
        return True
    if (target / "setup.cfg").exists() and "[tool:pytest]" in (target / "setup.cfg").read_text(errors="replace"):
        return True
    return False


def _detect_ruff(target: Path) -> bool:
    pyproject = target / "pyproject.toml"
    if pyproject.exists() and "[tool.ruff" in pyproject.read_text(errors="replace"):
        return True
    return (target / "ruff.toml").exists() or (target / ".ruff.toml").exists()


def _read_package_json(target: Path) -> dict | None:
    pkg = target / "package.json"
    if not pkg.exists():
        return None
    try:
        return json.loads(pkg.read_text(errors="replace"))
    except (json.JSONDecodeError, OSError):
        return None


def _pkg_has_dep(pkg: dict, name: str) -> bool:
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps = pkg.get(section) or {}
        if name in deps:
            return True
    return False


def _detect_vitest(target: Path) -> bool:
    pkg = _read_package_json(target)
    if pkg and _pkg_has_dep(pkg, "vitest"):
        return True
    return (target / "vitest.config.ts").exists() or (target / "vitest.config.js").exists()


def _detect_jest(target: Path) -> bool:
    pkg = _read_package_json(target)
    if pkg:
        if _pkg_has_dep(pkg, "jest"):
            return True
        if "jest" in pkg:
            return True
    return (target / "jest.config.js").exists() or (target / "jest.config.ts").exists()


def _detect_eslint(target: Path) -> bool:
    candidates = [
        ".eslintrc.json", ".eslintrc.js", ".eslintrc.cjs",
        ".eslintrc.yml", ".eslintrc.yaml", ".eslintrc",
        "eslint.config.js", "eslint.config.mjs",
    ]
    if any((target / name).exists() for name in candidates):
        return True
    pkg = _read_package_json(target)
    if pkg and "eslintConfig" in pkg:
        return True
    return False


def _detect_cargo(target: Path) -> bool:
    return (target / "Cargo.toml").exists()


def _detect_go(target: Path) -> bool:
    return (target / "go.mod").exists()


BUILTIN_DETECTORS = {
    "pytest": _detect_pytest,
    "vitest": _detect_vitest,
    "jest": _detect_jest,
    "cargo": _detect_cargo,
    "go": _detect_go,
    "eslint": _detect_eslint,
    "ruff": _detect_ruff,
}


def _jig_tdd_detect(target: Path) -> tuple[str | None, str]:
    """If jig is co-installed, ask its tdd.py for the test framework name.

    Returns `(framework_name, status)` where status is one of:
      - 'absent'   — jig's tdd.py is not on disk
      - 'success'  — jig returned a framework name in servo's vocabulary
      - 'failed'   — jig exists but call failed (timeout / non-zero exit /
                     malformed JSON / no framework key)
      - 'unknown'  — jig returned a framework outside servo's vocabulary

    The non-absent failure modes emit a stderr breadcrumb so a silent jig
    regression doesn't degrade installs invisibly. Per refinement-todo:
    file-existence is not the same as a usable call.
    """
    jig_tdd = plugin_root() / "jig" / "skills" / "tdd-loop" / "tdd.py"
    if not jig_tdd.exists():
        return None, "absent"
    try:
        result = subprocess.run(
            [sys.executable, str(jig_tdd), "detect", str(target)],
            capture_output=True, text=True, timeout=5,
        )
    except subprocess.TimeoutExpired:
        print("servo: jig detector timed out after 5s — using built-in",
              file=sys.stderr)
        return None, "failed"
    except OSError as exc:
        print(f"servo: jig detector OSError ({exc}) — using built-in",
              file=sys.stderr)
        return None, "failed"
    if result.returncode != 0:
        print(f"servo: jig detector exited rc={result.returncode} — using built-in",
              file=sys.stderr)
        return None, "failed"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("servo: jig detector returned malformed JSON — using built-in",
              file=sys.stderr)
        return None, "failed"
    # Tolerate jig schema drift: accept any of three plausible key shapes.
    name = data.get("framework") or data.get("runner") or data.get("name")
    if not isinstance(name, str):
        print("servo: jig detector returned no framework name — using built-in",
              file=sys.stderr)
        return None, "failed"
    normalized = name.lower().strip()
    if normalized in TEST_COMPONENTS:
        return normalized, "success"
    print(f"servo: jig detector returned unknown framework {name!r} — using built-in",
          file=sys.stderr)
    return None, "unknown"


def detect_signals(target: Path) -> dict:
    """Return the full detection payload for `detect_audit` / install.json.

    Calls `_jig_tdd_detect` exactly once; the returned status drives both
    component selection and the manifest's `detector` field (which reports
    the detector actually *used*, not merely "present on disk").

    Also exposes `ambiguous_tests` — the full list of test-framework configs
    found via built-in detection — so slice 001-04 can flag projects that
    have configs for more than one test runner.
    """
    # Enumerate built-in test-framework matches first so ambiguity stays
    # measurable independently of which detector ran.
    builtin_test_frameworks = [
        name for name in ("pytest", "vitest", "jest", "cargo", "go")
        if BUILTIN_DETECTORS[name](target)
    ]

    jig_framework, jig_status = _jig_tdd_detect(target)
    if jig_framework is not None:
        primary_test = jig_framework
    elif builtin_test_frameworks:
        primary_test = builtin_test_frameworks[0]
    else:
        primary_test = None

    components: list[str] = []
    if primary_test:
        components.append(primary_test)

    # Lint — multiple linters can coexist; never routed through jig.
    for name in ("eslint", "ruff"):
        if BUILTIN_DETECTORS[name](target):
            components.append(name)

    ambiguous_tests = builtin_test_frameworks if len(builtin_test_frameworks) > 1 else []

    return {
        "signals": {
            "tests": any(c in TEST_COMPONENTS for c in components),
            "lint": any(c in LINT_COMPONENTS for c in components),
            "ci": _detect_ci(target),
            "language": _detect_language(target),
        },
        "components": components,
        "weights": {name: DEFAULT_WEIGHTS.get(name, 1.0) for name in components},
        "detector": "jig" if jig_status == "success" else "built-in",
        "ambiguous_tests": ambiguous_tests,
    }


def detect_components(target: Path) -> list[str]:
    """Convenience wrapper — return only the components list."""
    return detect_signals(target)["components"]


def _detect_ci(target: Path) -> bool:
    if (target / ".github" / "workflows").is_dir():
        return True
    return (target / ".gitlab-ci.yml").exists() or (target / ".circleci" / "config.yml").exists()


def _detect_language(target: Path) -> str | None:
    """Coarse language hint from the highest-signal config file present."""
    if (target / "pyproject.toml").exists() or any(target.glob("*.py")):
        return "python"
    if (target / "package.json").exists() or any(target.glob("*.ts")) or any(target.glob("*.js")):
        return "javascript"
    if (target / "Cargo.toml").exists():
        return "rust"
    if (target / "go.mod").exists():
        return "go"
    return None


# ---------------------------------------------------------------------------
# Oracle assembly
# ---------------------------------------------------------------------------

def _load_template() -> str:
    return (_templates_root() / "oracle.sh.template").read_text()


def _load_fragment(component: str) -> str:
    path = _templates_root() / "components" / f"{component}.sh.fragment"
    if not path.exists():
        raise FileNotFoundError(f"missing fragment for component {component!r}: {path}")
    return path.read_text()


def _render_oracle(components: list[str]) -> str:
    template = _load_template()
    if components:
        components_list = "\n".join(
            f'  "{name}:{DEFAULT_WEIGHTS.get(name, 1.0)}"' for name in components
        )
        seed_blocks = "\n".join(_load_fragment(name).rstrip() for name in components)
        no_components_msg = "no components registered"
    else:
        components_list = "  # (no components — no signals detected)"
        seed_blocks = "# (no SEED blocks — populate manually using the conventions in README.md)"
        no_components_msg = "no signals detected — populate # SEED: blocks manually"
    return (template
            .replace("{{COMPONENTS_LIST}}", components_list)
            .replace("{{SEED_BLOCKS}}", seed_blocks)
            .replace("{{NO_COMPONENTS_MESSAGE}}", no_components_msg))


# ---------------------------------------------------------------------------
# Refinement-todo emission (slice 001-04)
# ---------------------------------------------------------------------------

def _render_refinement_todo(audit: dict) -> str:
    """Build the target-side `<target>/.servo/refinement-todo.md` content.

    Categories (only those that apply are emitted):
      - Threshold       — always (every install picks a default the user must confirm).
      - Weights         — when ≥2 components, since equal weights are a guess.
      - Ambiguous test runner — when ≥2 built-in test-framework configs were found.

    Format mirrors jig's refinement-todo convention: `## <name>` heading,
    `**Deferred:**` reason, `**Resolution trigger:**` line.
    """
    parts: list[str] = [
        "# Refinement TODO",
        "",
        "Open decisions servo couldn't infer from your project. Each has a "
        "resolution trigger — the moment in your workflow when you'll know "
        "enough to close it. Mirrors jig's refinement-todo format.",
        "",
        "---",
        "",
        "## Threshold",
        "",
        f"**Deferred:** default `THRESHOLD={DEFAULT_THRESHOLD}` chosen by servo "
        "without project-specific data.",
        "",
        "**Resolution trigger:** first time the oracle gate misfires — edit "
        "the `THRESHOLD` default at the top of `oracle.sh` to match observed quality.",
        "",
    ]

    components = audit.get("components", [])
    if len(components) >= 2:
        weights = audit.get("weights", {})
        weight_lines = "\n".join(
            f"- `{name}`: `{weights.get(name, 1.0)}`" for name in components
        )
        parts.extend([
            "## Weights",
            "",
            "**Deferred:** equal weights applied — tune to reflect project priorities.",
            "",
            "**Resolution trigger:** first time the composite score doesn't reflect "
            "your priority ordering. Edit the `COMPONENTS=(\"<name>:<weight>\")` "
            "entries in `oracle.sh`.",
            "",
            "Current weights:",
            "",
            weight_lines,
            "",
        ])

    ambiguous = audit.get("ambiguous_tests", [])
    if ambiguous:
        picked = components[0] if components else None
        amb_lines = "\n".join(
            f"- `{name}`{' (selected)' if name == picked else ''}" for name in ambiguous
        )
        parts.extend([
            "## Ambiguous test runner",
            "",
            f"**Deferred:** detected configs for multiple test runners: "
            f"{', '.join(ambiguous)}. Servo picked `{picked}`.",
            "",
            "**Resolution trigger:** confirm which runner is authoritative; "
            "remove the unused config or merge into a single runner.",
            "",
            amb_lines,
            "",
        ])

    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Install / detect commands
# ---------------------------------------------------------------------------

def install(target: Path, *, force: bool) -> None:
    if not target.exists():
        raise FileNotFoundError(f"target does not exist: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"target is not a directory: {target}")

    oracle_dst = target / "oracle.sh"
    manifest_dst = target / ".servo" / "install.json"

    if oracle_dst.exists() and not force:
        raise FileExistsError(
            f"oracle.sh already present at {oracle_dst}; re-run with --force to overwrite"
        )

    audit = detect_signals(target)
    oracle_text = _render_oracle(audit["components"])

    oracle_dst.write_text(oracle_text)
    mode = oracle_dst.stat().st_mode
    oracle_dst.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    manifest = {
        "servo_version": SERVO_VERSION,
        "timestamp": iso_now(),
        "installed_tier": "tier-0",
        "signals": audit["signals"],
        "components": audit["components"],
    }
    manifest_dst.parent.mkdir(parents=True, exist_ok=True)
    manifest_dst.write_text(json.dumps(manifest, indent=2) + "\n")

    # Slice 001-04: emit the refinement-todo alongside the manifest. Always
    # overwrites — `--force` re-scaffold yields a fresh file, no merge logic.
    refinement_dst = target / ".servo" / "refinement-todo.md"
    refinement_dst.write_text(_render_refinement_todo(audit))


def detect_audit(target: Path) -> dict:
    if not target.exists():
        raise FileNotFoundError(f"target does not exist: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"target is not a directory: {target}")
    return detect_signals(target)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _install_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="scaffold.py",
        description="Scaffold a servo Tier-0 install into a target project.",
    )
    parser.add_argument("target")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    try:
        install(target, force=args.force)
    except FileExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"servo: installed tier-0 at {target}")
    return 0


def _detect_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="scaffold.py detect",
        description="Probe a target for signals and print the audit JSON.",
    )
    parser.add_argument("target")
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    try:
        audit = detect_audit(target)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(audit, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    # Subcommand dispatch is intentionally hand-rolled instead of argparse
    # subparsers: the bare-positional install form `scaffold.py <target>`
    # was the 001-01 contract and breaking it for a `scaffold.py install
    # <target>` migration would be hostile. Tradeoff: a target literally
    # named `detect` would mis-route, but targets are filesystem paths and
    # such a name would fail both pathways anyway.
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "detect":
        return _detect_main(argv[1:])
    return _install_main(argv)


if __name__ == "__main__":
    sys.exit(main())
