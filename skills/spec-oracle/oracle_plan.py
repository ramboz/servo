"""
servo spec-oracle — slice 006-01 (evidence-plan)

Read a spec or slice Markdown file and write a *reviewable evidence plan*
under `<target>/.servo/spec-oracles/<spec-id>/`: a `plan.md` for humans and
a `checks.json` machine contract that maps each acceptance criterion to a
check family. This is the planning step only — no checks are executed, no
oracle is installed, and nothing in the target is mutated outside the
spec-oracle directory (slice 006-01 ACs 3 and 5).

Usage:
    python3 oracle_plan.py <target> <spec-path> [--spec-id ID]
        Write plan.md + checks.json under
        <target>/.servo/spec-oracles/<spec-id>/. Prints a short summary.

    python3 oracle_plan.py classify <spec-path> [--spec-id ID]
        Print the classification as JSON to stdout and write nothing — a dry
        path for inspecting how ACs would be classified.

Design decision — classification is deterministic in v1
-------------------------------------------------------
AC family classification uses keyword/regex matching on the AC statement
text only. It MUST NOT depend on an LLM or any network call: the spec's
principle is "deterministic checks remain the source of truth," and the
dogfood fixture tests (slice 006-01 AC6) rely on stable, offline behaviour.
The spec mentions a *future* model-assisted classification step; that is
explicitly deferred to a later slice and logged to refinement-todo.

Heuristics are an intentionally boring starting point (spec "Check families"
section). They are an ordered set of rules — the first matching family wins,
most-specific first — so that, e.g., "command works from the scaffold
target" is `generated_artifact_command` rather than the broader `command`,
and "no live runtime references" is `runtime_reference_scan` rather than the
broader `text_invariant`. Anything that matches no deterministic rule, or
that reads as taste/positioning, falls through to `residual_judgment` with a
reason and a suggested human review path (AC4).

Python stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SERVO_VERSION = "0.1.0"
PLANNER_VERSION = "0.1.0"
SCHEMA_VERSION = 1

# The nine first-version check families (spec "Check families" table).
FAMILIES = (
    "command",
    "file_presence",
    "text_invariant",
    "json_contract",
    "archive_inventory",
    "markdown_links",
    "generated_artifact_command",
    "runtime_reference_scan",
    "residual_judgment",
)

RESIDUAL_REASON_TASTE = "tone / product positioning / subjective quality judgment"
RESIDUAL_REASON_UNMATCHED = (
    "no deterministic check family matched the criterion text"
)
RESIDUAL_REVIEW = "human or craft-review pass"


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# AC extraction (AC1)
# ---------------------------------------------------------------------------

# A numbered AC list item: "1. body" or "12. body", with optional indent.
_AC_ITEM_RE = re.compile(r"^\s*(\d+)\.\s+(.*\S)\s*$")
# An "Acceptance Criteria" *section opener*: a `#` heading or a bold label
# whose text is essentially just "Acceptance Criteria" (with optional colon /
# trailing words). Deliberately strict — a prose sentence that merely mentions
# "acceptance criteria" (in Goals, Why-this-spec, etc.) must NOT open a
# section, or unrelated numbered lists get mis-extracted.
_AC_OPENER_RE = re.compile(
    r"^\s*(?:#{1,6}\s+|\*\*\s*)acceptance\s+criteria\b", re.IGNORECASE)
# A slice heading: "## Slice 006-01 — evidence-plan" (any dash style).
_SLICE_HEADING_RE = re.compile(
    r"^#{1,6}\s+Slice\s+([0-9A-Za-z][0-9A-Za-z._-]*)\b", re.IGNORECASE)
# Any Markdown heading line, or a bold label used as a pseudo-heading
# ("**DoD:**", "**DoR:**", "**Goal:**"). Either form closes an open AC section
# so sibling labelled lists (DoD checklists, etc.) are not swept in.
_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
_BOLD_LABEL_RE = re.compile(r"^\s*\*\*[^*]+\*\*")


def _slice_id_for_line(lines: list, ac_line_idx: int) -> str | None:
    """Return the nearest preceding `## Slice <id>` id, or None.

    Scans upward from the AC's line; the closest slice heading above the AC
    wins (a spec.md can contain many slice sections).
    """
    for i in range(ac_line_idx, -1, -1):
        m = _SLICE_HEADING_RE.match(lines[i])
        if m:
            return m.group(1)
    return None


def extract_acs(source_text: str, spec_id: str | None = None) -> list:
    """Extract numbered acceptance criteria from spec/slice Markdown.

    Returns a list of dicts: ``{"id", "statement", "source_line"}`` where
    ``source_line`` is 1-based (the line of the numbered item). IDs are
    ``AC-<slice-id>-<n>`` when the AC lives under a ``## Slice <id>`` heading,
    else ``AC-<spec_id>-<n>``.

    Only items inside an "Acceptance Criteria" section are extracted: a
    section opens on an "Acceptance Criteria" heading/label and runs until the
    next heading or bold pseudo-heading label. This keeps unrelated numbered
    lists (Goals, DoR, DoD, slice index) and prose mentions out of the plan.

    **Multi-line ACs are captured whole.** Real specs wrap each criterion
    across several indented lines; the statement is the numbered item's body
    joined with every following continuation line (whitespace collapsed) up to
    the next numbered item, heading, or bold pseudo-heading. Capturing only
    the first physical line would truncate statements mid-sentence and — worse
    — strip the keywords that make a criterion classifiable, collapsing
    deterministic ACs into ``residual_judgment``.
    """
    lines = source_text.splitlines()
    acs = []

    in_ac_section = False
    # Per-(scope) counter so numbering restarts for each slice's AC block and
    # is independent of the literal numbers in the source (which may repeat).
    counters: dict = {}
    # The AC currently being accumulated across its continuation lines.
    pending: dict | None = None

    def flush() -> None:
        nonlocal pending
        if pending is None:
            return
        acs.append({
            "id": f"AC-{pending['scope']}-{pending['n']}",
            "statement": _statement_text(" ".join(pending["parts"])),
            "source_line": pending["source_line"],
        })
        pending = None

    for idx, line in enumerate(lines):
        if _AC_OPENER_RE.match(line):
            # An "Acceptance Criteria" heading or bold label opens a section.
            flush()
            in_ac_section = True
            continue

        if _HEADING_RE.match(line) or _BOLD_LABEL_RE.match(line):
            # Any other heading or bold pseudo-heading label closes the
            # section. The opener above is checked first, so it is unaffected.
            flush()
            in_ac_section = False
            continue

        if not in_ac_section:
            continue

        m = _AC_ITEM_RE.match(line)
        if m:
            # A new numbered item finalizes the previous AC and starts a new.
            flush()
            slice_id = _slice_id_for_line(lines, idx)
            scope = slice_id if slice_id is not None else (spec_id or "SPEC")
            counters[scope] = counters.get(scope, 0) + 1
            pending = {
                "scope": scope,
                "n": counters[scope],
                "source_line": idx + 1,
                "parts": [m.group(2)],
            }
            continue

        # A continuation line of the pending AC. Blank lines are skipped (they
        # do not end the criterion — the next item or terminator does), but
        # non-blank prose is appended so the full statement is preserved.
        if pending is not None:
            stripped = line.strip()
            if stripped:
                pending["parts"].append(stripped)

    flush()  # finalize the last AC at end of input
    return acs


def _statement_text(raw: str) -> str:
    """Normalise an AC body: strip a leading ``**Bold label.**`` prefix and
    surrounding emphasis so the stored statement reads as a sentence."""
    text = raw.strip()
    # Drop a leading "**Label.**" or "**Label**" prefix if present.
    m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", text)
    if m:
        label, rest = m.group(1), m.group(2)
        text = (rest.strip() if rest.strip()
                else label.strip())
    return text


# ---------------------------------------------------------------------------
# Family classification (AC2 / AC4)
# ---------------------------------------------------------------------------

def _has(text: str, *needles: str) -> bool:
    return any(n in text for n in needles)


def _has_word(text: str, *words: str) -> bool:
    """Word-boundary match for short/ambiguous tokens.

    Plain substring matching is unsafe for short tokens — e.g. ``tar`` is a
    substring of ``target`` and ``start``, ``zip`` of ``zipped`` — so the
    archive/command families use this for their riskiest tokens to avoid
    false positives like classifying "asks for target path" as an archive.
    """
    return any(
        re.search(r"\b" + re.escape(w) + r"\b", text) for w in words
    )


def _classify_family(statement: str) -> str:
    """Return the check family for an AC statement (deterministic).

    Ordered rules: the first match wins, most-specific first. See module
    docstring for the precedence rationale.
    """
    t = statement.lower()

    # 1. generated_artifact_command — a command run from a built/scaffolded
    #    tree. Must precede the generic `command` family.
    if (_has(t, "scaffold target", "scaffold tree", "generated tree",
             "generated into", "from the scaffold", "into a tempdir",
             "into a temp dir", "temp scaffold", "scaffolded target")
            or (_has(t, "scaffold") and _has(t, "command", "runs", "run "))):
        return "generated_artifact_command"

    # 2. runtime_reference_scan — "no live/stale runtime references". Must
    #    precede text_invariant (references) and file_presence (remain).
    if (_has(t, "runtime reference", "runtime references", "live reference",
             "live references", "stale reference", "stale references")
            or (_has(t, "no live", "no stale") and _has(t, "reference"))):
        return "runtime_reference_scan"

    # 3. markdown_links — local links resolve / no broken links. Must precede
    #    text_invariant (a link "resolves" can read like a string check).
    if (_has(t, "link resolve", "links resolve", "local link", "local links",
             "broken link", "broken links", "markdown link", "markdown links")
            or (_has(t, "link", "links") and _has(t, "resolve", "resolves"))):
        return "markdown_links"

    # 4. json_contract — JSON/schema parses or has a required key. Must
    #    precede text_invariant and file_presence on overlap. The bare noun
    #    "manifest" is deliberately NOT a sole trigger: "the manifest contains
    #    the version string" is a text-presence check, not a key/validity
    #    check, so "manifest" only counts alongside a JSON/key/valid signal.
    if (_has(t, "valid json", "json file", "schema")
            or _has(t, "required key", "key exists", "valid key")
            or (_has(t, "json", "manifest")
                and _has(t, "key", "parse", "parses", "valid"))):
        return "json_contract"

    # 5. archive_inventory — zip/tar/archive/package entries. Short tokens
    #    (tar/zip) use word boundaries so "target"/"start"/"zipped" don't
    #    false-trigger.
    if (_has(t, "archive", "tarball")
            or _has_word(t, "zip", "tar")
            or (_has(t, "package") and _has(t, "entries", "entry",
                                            "contains", "include",
                                            "includes", "excludes"))):
        return "archive_inventory"

    # 6. file_presence — exists/present/absent/removed/deleted/executable bit.
    if _has(t, "executable bit", "is present", "is absent", "is removed",
            "is deleted", "exists", "present and", "removed and",
            "absent from", "file is present", "no longer exists",
            "does not exist"):
        return "file_presence"

    # 7. command — runs a test/lint/build command and asserts exit code.
    #    Broad; placed after the more-specific command-ish families above.
    #    The bare "0"/"zero" success tokens use word boundaries so a version
    #    string like "0.1.0" doesn't read as an exit code.
    if (_has(t, "test suite", "exit code", "exits 0", "exit 0", "exits zero",
             "build passes", "lint passes", "tests pass", "test passes",
             "command runs", "command exits")
            or (_has(t, "command", "verifier", "runs", "build", "lint")
                and (_has(t, "exit", "exits", "pass", "passes", "run", "runs")
                     or _has_word(t, "0", "zero")))):
        return "command"

    # 8. text_invariant — text contains / does not contain a string. Placed
    #    near the end so the structural families above win on overlap.
    #    ("containing" is matched as well as "contains" — "a fragment
    #    containing a valid block" is a text-presence check.)
    if _has(t, "contains", "containing", "does not contain", "doesn't contain",
            "mentions", "documents", "references", "the string",
            "version string"):
        return "text_invariant"

    # 9. residual_judgment — taste/positioning, or anything unmatched.
    return "residual_judgment"


def classify_one(ac: dict) -> dict:
    """Classify a single extracted AC into a check entry.

    Taste/quality language is forced to `residual_judgment` even if it would
    otherwise brush a deterministic keyword, because such ACs are explicitly
    not deterministic in v1 (spec non-goals + Guardrails). Residual entries
    carry a ``reason`` and ``suggested_review`` (AC4).
    """
    statement = ac["statement"]
    t = statement.lower()

    taste = _has(
        t, "tone", "positioning", "good enough", "appropriate",
        "appropriately", "readable", "reads well", "quality", "taste",
        "elegant", "polished", "feels ",
    )

    if taste:
        family = "residual_judgment"
        reason = RESIDUAL_REASON_TASTE
    else:
        family = _classify_family(statement)
        reason = RESIDUAL_REASON_UNMATCHED if family == "residual_judgment" else None

    entry = {
        "id": ac["id"],
        "statement": statement,
        "family": family,
        "source_line": ac["source_line"],
    }
    if family == "residual_judgment":
        entry["reason"] = reason
        entry["suggested_review"] = RESIDUAL_REVIEW
    return entry


def classify_acs(acs: list) -> list:
    """Classify a list of extracted ACs."""
    return [classify_one(ac) for ac in acs]


# ---------------------------------------------------------------------------
# Plan assembly (AC3 / AC4)
# ---------------------------------------------------------------------------

def _spec_id_from_path(spec_path: Path) -> str:
    """spec_id = the spec file's parent directory name."""
    return spec_path.parent.name


def build_plan(source_text: str, *, spec_id: str, source_spec_path: str,
               source_hash: str) -> dict:
    """Build the full checks.json payload from spec source text.

    Deterministic-family ACs go in ``checks``; ``residual_judgment`` ACs are
    surfaced separately so uncovered judgment stays visible (AC4).
    """
    classified = classify_acs(extract_acs(source_text, spec_id=spec_id))

    checks = []
    residual = []
    for entry in classified:
        if entry["family"] == "residual_judgment":
            residual.append({
                "id": entry["id"],
                "statement": entry["statement"],
                "source_line": entry["source_line"],
                "reason": entry["reason"],
                "suggested_review": entry["suggested_review"],
            })
        else:
            checks.append({
                "id": entry["id"],
                "statement": entry["statement"],
                "family": entry["family"],
                "source_line": entry["source_line"],
                "status": "planned",
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "spec_id": spec_id,
        "source_spec_path": source_spec_path,
        "source_hash": source_hash,
        "planner_version": PLANNER_VERSION,
        "generated_at": iso_now(),
        "checks": checks,
        "residual_judgment": residual,
    }


def _render_plan_md(plan: dict) -> str:
    """Render the human-reviewable plan.md from a checks.json payload."""
    lines = [
        f"# Spec-oracle plan — {plan['spec_id']}",
        "",
        f"- **Source spec:** `{plan['source_spec_path']}`",
        f"- **Source hash:** `{plan['source_hash']}`",
        f"- **Planner version:** {plan['planner_version']}",
        f"- **Generated:** {plan['generated_at']}",
        "",
        "> Read-only plan (slice 006-01). No checks are executed and the "
        "target oracle is not modified. A re-plan is required when the "
        "source spec hash changes.",
        "",
        "## Deterministic checks",
        "",
    ]

    if plan["checks"]:
        lines.append("| AC | Family | Source line | Statement |")
        lines.append("|---|---|---|---|")
        for c in plan["checks"]:
            stmt = c["statement"].replace("|", "\\|")
            lines.append(
                f"| {c['id']} | `{c['family']}` | {c['source_line']} | {stmt} |")
    else:
        lines.append("_No deterministic checks planned._")

    lines += [
        "",
        "## Residual judgment (not deterministic in v1)",
        "",
    ]

    if plan["residual_judgment"]:
        lines.append("| AC | Source line | Reason | Suggested review |")
        lines.append("|---|---|---|---|")
        for r in plan["residual_judgment"]:
            reason = r["reason"].replace("|", "\\|")
            review = r["suggested_review"].replace("|", "\\|")
            lines.append(
                f"| {r['id']} | {r['source_line']} | {reason} | {review} |")
    else:
        lines.append("_No residual-judgment ACs — every criterion is "
                     "deterministically coverable._")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Write / classify commands
# ---------------------------------------------------------------------------

def plan_target(target: Path, spec_path: Path, spec_id: str | None,
                *, source_spec_path: str | None = None) -> dict:
    """Read the spec and write plan.md + checks.json under the target.

    Returns the checks.json payload. Touches nothing outside
    ``<target>/.servo/spec-oracles/<spec-id>/`` (AC5).

    ``source_spec_path`` is the *display* path recorded verbatim in
    checks.json; the CLI passes the path as the user gave it (typically
    repo-relative, matching the spec's schema example) so the committed
    artifact does not leak the author's absolute filesystem layout. The read
    and the spec-id derivation still use the (possibly resolved) ``spec_path``.
    """
    if not target.exists():
        raise FileNotFoundError(f"target does not exist: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"target is not a directory: {target}")
    if not spec_path.exists():
        raise FileNotFoundError(f"spec path does not exist: {spec_path}")
    if not spec_path.is_file():
        raise IsADirectoryError(f"spec path is not a file: {spec_path}")

    source_bytes = spec_path.read_bytes()
    source_text = source_bytes.decode("utf-8", errors="replace")
    source_hash = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    resolved_id = spec_id or _spec_id_from_path(spec_path)

    plan = build_plan(
        source_text,
        spec_id=resolved_id,
        source_spec_path=source_spec_path or str(spec_path),
        source_hash=source_hash,
    )

    out_dir = target / ".servo" / "spec-oracles" / resolved_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "checks.json").write_text(json.dumps(plan, indent=2) + "\n")
    (out_dir / "plan.md").write_text(_render_plan_md(plan))
    return plan


def classify_only(spec_path: Path, spec_id: str | None,
                  *, source_spec_path: str | None = None) -> dict:
    """Dry classification: return the plan payload without writing anything."""
    if not spec_path.exists():
        raise FileNotFoundError(f"spec path does not exist: {spec_path}")
    if not spec_path.is_file():
        raise IsADirectoryError(f"spec path is not a file: {spec_path}")

    source_bytes = spec_path.read_bytes()
    source_text = source_bytes.decode("utf-8", errors="replace")
    source_hash = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    resolved_id = spec_id or _spec_id_from_path(spec_path)
    return build_plan(
        source_text,
        spec_id=resolved_id,
        source_spec_path=source_spec_path or str(spec_path),
        source_hash=source_hash,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _plan_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="oracle_plan.py",
        description="Plan a spec-oracle: map a spec's ACs to check families.",
    )
    parser.add_argument("target")
    parser.add_argument("spec_path")
    parser.add_argument("--spec-id", dest="spec_id", default=None)
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    spec_path = Path(args.spec_path).resolve()
    try:
        plan = plan_target(target, spec_path, args.spec_id,
                           source_spec_path=args.spec_path)
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_dir = target / ".servo" / "spec-oracles" / plan["spec_id"]
    n_checks = len(plan["checks"])
    n_residual = len(plan["residual_judgment"])
    print(
        f"servo: planned spec-oracle for {plan['spec_id']} "
        f"({n_checks} deterministic, {n_residual} residual) -> {out_dir}"
    )
    return 0


def _classify_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="oracle_plan.py classify",
        description="Print AC classification JSON to stdout; write nothing.",
    )
    parser.add_argument("spec_path")
    parser.add_argument("--spec-id", dest="spec_id", default=None)
    args = parser.parse_args(argv)

    spec_path = Path(args.spec_path).resolve()
    try:
        plan = classify_only(spec_path, args.spec_id,
                             source_spec_path=args.spec_path)
    except (FileNotFoundError, IsADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(plan, indent=2))
    return 0


def main(argv: list | None = None) -> int:
    # Hand-rolled subcommand dispatch matching scaffold.py's idiom: the bare
    # positional form `oracle_plan.py <target> <spec-path>` is the write path;
    # a leading `classify` selects the dry path. A target literally named
    # `classify` would mis-route, but targets are filesystem paths and that
    # name is implausible (and would fail anyway).
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "classify":
        return _classify_main(argv[1:])
    return _plan_main(argv)


if __name__ == "__main__":
    sys.exit(main())
