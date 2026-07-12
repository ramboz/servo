"""
servo eval-authoring — slices 008-01 (residual-triage), 008-02
(rubric-shaping), and 008-03 (reference-set), the self-contained core of the
single servo-owned guided skill `/servo:eval-authoring` (ADR-0019 / ADR-0026).
Durable artifacts are co-located with the spec
(ADR-0023), mirroring `skills/spec-oracle/oracle_plan.py`'s convention.

Given a spec-006 evidence plan (`checks.json`, produced by
`oracle_plan.py`) — or a curated AC set that has already round-tripped
through 006's classify (a future 008-05), same shape — classify each
`residual_judgment` entry as **eval-able** (a rubric + dataset could score
it) or **human-residual** (taste / policy / ADR-shaped; stays waived exactly
as spec-006 already handles it), with a one-line rationale per AC. The
classification is a *proposal*: every entry starts `confirmed: false` for a
human to flip. The tool never silently promotes a taste/policy/ADR-shaped AC
into `eval-able` — when uncertain, it defaults to `human-residual` (AC2,
fail-closed, mirroring ADR-0015's spirit).

Usage:
    python3 eval_authoring.py triage <plan>
        Read a spec-006 `checks.json` evidence plan, classify its
        `residual_judgment` entries, and write `triage.json` (the machine
        contract 008-02+ reads) and `triage.md` (human-reviewable) under
        `<spec-dir>/eval/<spec-id>/` — resolved from the plan *file's own
        on-disk location* (a spec-006 `checks.json` always lives at
        `<spec-dir>/oracle/<spec-id>/checks.json`), never from the plan's
        `source_spec_path` field (a display path, CWD-dependent under
        `.resolve()`) or plugin/target state (ADR-0023).

    python3 eval_authoring.py rubric <plan> --ac <id> [--archetype ...]
        (Slice 008-02.) Resolve the same `<spec-dir>/eval/<spec-id>/`
        colocation dir `triage` wrote to, read its `triage.json`, and shape a
        rubric — named scoring criteria, an explicit scale, and a judge
        prompt — for one `eval-able` AC (`--ac`), from an editable starting
        archetype (`--archetype`: `single_dimension` | `multi_criteria` |
        `comparative`; default `single_dimension`). Writes `config.json` (the
        `fidelity_eval.py`-shaped eval definition — judge/samples/threshold/
        rubric/cases, `cases` empty until 008-03) and `rubric.md`
        (human-reviewable) under `<spec-dir>/eval/<spec-id>/<eval-name>/`,
        where `<eval-name>` is a slug of `--ac` (becomes `score_<name>` once
        008-04 emits + spec-006 compiles). The tool proposes; the human edits
        and approves before anything is frozen (008-04's job, not this one).

    python3 eval_authoring.py dataset <plan> --ac <id>
        (Slice 008-03.) Resolve the same colocation dir, and grow the
        statistical **reference set** for one already-rubric-shaped AC's
        `config.json`. On first run (`cases` still empty), scaffolds cases
        seeded verbatim from the spec's own `## Examples` / `## Edge cases`
        markdown sections (never inventing scenario/input text) — or, when
        neither section exists, a small labeled `EDIT ME` placeholder per
        taxonomy category for the human to fill in. On any later run
        (`cases` already non-empty), never overwrites — the dataset is a
        project-owned, human-grown artifact; the local `config.json` file is
        the source of truth (AC1). Every run validates the case list's shape
        (AC2) and prints a non-fatal advisory when it is under the
        provisional minimum-viable-size floor (AC3) — never autofilling
        toward it. Writes the updated `config.json` and a human-reviewable
        `dataset.md` under the same `<eval-name>/` directory `rubric` used.

Design decision — classification stays deterministic, never LLM-assisted
-------------------------------------------------------------------------
Like spec-006's own classifier, this triage is keyword/substring matching
over the AC statement text — no LLM, no network call — so a re-run over the
same plan is reproducible and diffs cleanly (AC5). Cross-skill data exchange
with spec-006 is the on-disk plan JSON only; servo's established idiom for
skill-to-skill data is subprocess/JSON, never a Python import across skill
directories (see `skills/edd-suitability/suitability.py`'s module docstring),
so the two `residual_judgment` `reason` strings are mirrored here as
literals rather than imported.

The rendered artifact is deliberately timestamp-free: unlike
`oracle_plan.py`'s `checks.json` (which records `generated_at`), a triage
re-run over an unchanged plan must be byte-identical (AC5), and a churning
timestamp would defeat that.

Python stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
TRIAGER_VERSION = "0.1.0"

# spec-006's public plan contract (`oracle_plan.py`'s `RESIDUAL_REASON_TASTE` /
# `RESIDUAL_REASON_UNMATCHED`) — the two values a `residual_judgment` entry's
# `reason` field can carry. Mirrored here as literals, not imported (see
# module docstring: cross-skill data is JSON, never a Python import).
RESIDUAL_REASON_TASTE = "tone / product positioning / subjective quality judgment"
RESIDUAL_REASON_UNMATCHED = "no deterministic check family matched the criterion text"

CLASSIFICATION_EVAL_ABLE = "eval-able"
CLASSIFICATION_HUMAN_RESIDUAL = "human-residual"


class EnvError(Exception):
    """An environment problem (bad/missing path, malformed JSON, malformed
    plan shape) — mapped to a clean exit(2), never a stack trace (mirrors
    `skills/edd-suitability/suitability.py`'s `EnvError`)."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


# ---------------------------------------------------------------------------
# Classification (AC1 / AC2)
# ---------------------------------------------------------------------------

# Conservative scan for taste/policy/ADR/subjective-quality language (AC2).
# Longer, multi-word-safe tokens are matched unanchored (plain substring):
# over-matching only ever pushes an AC toward the safe `human-residual` side;
# under-matching would risk promoting a taste call into `eval-able`, which
# AC2 forbids outright. Short/ambiguous tokens are matched word-anchored
# instead (see `_has_word` below) — unanchored, "tone" would false-hit inside
# "milestone" and "adr" inside e.g. "quadrant", which would over-trigger
# human-residual for reasons unrelated to taste and defeat AC1's proposal
# being a *useful* one.
_TASTE_KEYWORDS_SUBSTRING = (
    "taste", "elegant", "policy", "positioning", "appropriate", "good enough",
)
_TASTE_KEYWORDS_WORD = ("adr", "tone")


def _has_word(text: str, *words: str) -> bool:
    """Word-boundary match for short/ambiguous tokens (mirrors
    `oracle_plan.py::_has_word` — same rationale: plain substring matching is
    unsafe for short tokens like "tone" (substring of "milestone") or "adr"
    (substring of e.g. "quadrant")."""
    return any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words)


def _reads_as_taste(statement: str) -> bool:
    """True if the AC statement text itself reads as taste/policy/ADR-shaped."""
    t = statement.lower()
    return (any(kw in t for kw in _TASTE_KEYWORDS_SUBSTRING)
            or _has_word(t, *_TASTE_KEYWORDS_WORD))


def classify_entry(entry: dict) -> dict:
    """Classify one `residual_judgment` entry (AC1 / AC2).

    Fail-closed: only an UNMATCHED-reasoned entry whose statement text does
    *not* itself read as taste/policy/ADR-shaped becomes `eval-able`. A
    TASTE-reasoned entry, an unrecognized/missing reason, or taste-reading
    text on an otherwise-UNMATCHED entry, all default to `human-residual` —
    "when uncertain, human-residual" (AC2, mirroring ADR-0015's fail-closed
    spirit). The result is a *proposal*: `confirmed` starts `False` for a
    human to flip (AC1).
    """
    reason = entry.get("reason")
    statement = entry.get("statement", "")

    if reason == RESIDUAL_REASON_UNMATCHED and not _reads_as_taste(statement):
        classification = CLASSIFICATION_EVAL_ABLE
        rationale = (
            "no deterministic check family matched, and the statement does not "
            "read as taste/policy/ADR-shaped — a candidate for a scored rubric"
        )
    elif reason == RESIDUAL_REASON_TASTE:
        classification = CLASSIFICATION_HUMAN_RESIDUAL
        rationale = (
            "spec-oracle already classified this as tone/positioning/"
            "subjective-quality judgment"
        )
    elif reason == RESIDUAL_REASON_UNMATCHED:
        classification = CLASSIFICATION_HUMAN_RESIDUAL
        rationale = (
            "statement reads as taste/policy/ADR-shaped even though no "
            "deterministic check family matched — defaulting to human-residual"
        )
    else:
        classification = CLASSIFICATION_HUMAN_RESIDUAL
        rationale = (
            f"unrecognized or missing residual reason ({reason!r}) — "
            "defaulting to human-residual (fail-closed)"
        )

    return {
        "id": entry.get("id"),
        "statement": statement,
        "source_line": entry.get("source_line"),
        "classification": classification,
        "rationale": rationale,
        "confirmed": False,
    }


def _entry_sort_key(entry: dict):
    """Stable sort key: by source line, then AC id (AC5).

    Entries without a `source_line` (e.g. a future goal-expanded curated AC)
    sort after every line-numbered entry, so ordering never depends on input
    order — a re-run over the same plan (in any input order) diffs cleanly.
    """
    line = entry.get("source_line")
    return (line is None, line if line is not None else 0, entry.get("id") or "")


def build_triage(plan: dict) -> dict:
    """Pure classification over an already-loaded, validated plan. No I/O.

    Returns the `triage.json` payload: a stably-ordered `entries` list (AC5)
    plus an `eval_able` list of ids — the stable, machine-readable form the
    next slice (008-02) reads (AC3).
    """
    ordered = sorted(plan["residual_judgment"], key=_entry_sort_key)
    entries = [classify_entry(e) for e in ordered]
    eval_able = [e["id"] for e in entries if e["classification"] == CLASSIFICATION_EVAL_ABLE]

    return {
        "schema_version": SCHEMA_VERSION,
        "spec_id": plan["spec_id"],
        "source_spec_path": plan["source_spec_path"],
        "source_hash": plan.get("source_hash"),
        "triager_version": TRIAGER_VERSION,
        "entries": entries,
        "eval_able": eval_able,
    }


# ---------------------------------------------------------------------------
# Plan loading (AC1 / AC6)
# ---------------------------------------------------------------------------

def load_plan(plan_path: Path) -> dict:
    """Read + minimally validate a spec-006-shaped evidence plan (AC1).

    Accepts either a genuine spec-006 `checks.json` or a curated AC set that
    has already round-tripped through 006's classify (008-05, not yet built)
    — both share the same `residual_judgment` entry shape
    (`id`/`statement`/`source_line`/`reason`/`suggested_review`). Raises
    `EnvError` on any environment problem (missing/unreadable path, malformed
    JSON, missing required fields) so the CLI can exit 2 cleanly rather than
    with a stack trace (AC6).
    """
    if not plan_path.exists():
        raise EnvError("plan_missing", f"plan path does not exist: {plan_path}")
    if not plan_path.is_file():
        raise EnvError("plan_not_file", f"plan path is not a file: {plan_path}")

    try:
        plan = json.loads(plan_path.read_text())
    except json.JSONDecodeError as exc:
        raise EnvError(
            "plan_malformed_json", f"plan is not valid JSON: {plan_path} ({exc})"
        ) from exc

    if not isinstance(plan, dict):
        raise EnvError("plan_malformed", f"plan must be a JSON object: {plan_path}")
    if not isinstance(plan.get("residual_judgment"), list):
        raise EnvError(
            "plan_missing_residual_judgment",
            f"plan has no residual_judgment list: {plan_path}",
        )
    for key in ("spec_id", "source_spec_path"):
        if not plan.get(key):
            raise EnvError(
                "plan_missing_field",
                f"plan is missing required field {key!r}: {plan_path}",
            )
    for i, entry in enumerate(plan["residual_judgment"]):
        if not isinstance(entry, dict) or "id" not in entry or "statement" not in entry:
            raise EnvError(
                "plan_malformed_entry",
                f"residual_judgment[{i}] is missing required id/statement "
                f"fields: {plan_path}",
            )

    return plan


# ---------------------------------------------------------------------------
# Artifact location (AC4 — ADR-0023 colocation)
# ---------------------------------------------------------------------------

# A spec id is a directory slug; reject anything else so it can never inject
# into a path or escape the eval directory (mirrors
# `oracle_overlay.py::_validate_spec_id`).
_SPEC_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_spec_id(spec_id: str) -> None:
    if not _SPEC_ID_RE.match(spec_id or "") or not re.search(r"[A-Za-z0-9]", spec_id or ""):
        raise EnvError(
            "invalid_spec_id",
            f"invalid spec id {spec_id!r}: must match {_SPEC_ID_RE.pattern} "
            "and contain an alphanumeric character",
        )


def eval_dir_for_spec(spec_dir: Path, spec_id: str) -> Path:
    """Where eval-authoring's durable artifacts live for a spec (AC4).

    Mirrors spec-oracle's `oracle_dir_for_spec`: resolves to
    `<spec_dir>/eval/<spec_id>/`, relative to the spec's own directory —
    never plugin/target state. Later slices (008-02..04) write the rubric,
    dataset, and emitted eval definition alongside this triage, under the
    same directory, so the whole eval-authoring trail travels with the spec.
    """
    _validate_spec_id(spec_id)
    return spec_dir / "eval" / spec_id


# ---------------------------------------------------------------------------
# Rendering (AC1 / AC2 — the human is the gate)
# ---------------------------------------------------------------------------

def _render_triage_md(triage: dict) -> str:
    """Render the human-reviewable `triage.md` from a `triage.json` payload.

    Deliberately timestamp-free (like the JSON body) so a re-run over the
    same plan produces byte-identical output (AC5).
    """
    lines = [
        f"# Eval-authoring triage — {triage['spec_id']}",
        "",
        f"- **Source spec:** `{triage['source_spec_path']}`",
    ]
    if triage.get("source_hash"):
        lines.append(f"- **Source hash:** `{triage['source_hash']}`")
    lines += [
        f"- **Triager version:** {triage['triager_version']}",
        "",
        "> **This is a proposal, not a decision (AC1/AC2).** Every "
        "classification below is a starting point for a human to confirm — "
        "flip `confirmed` to `true` in `triage.json` only once you agree. "
        "The tool never auto-promotes a taste/policy/ADR-shaped AC into "
        "`eval-able`; a `human-residual` AC stays waived exactly as "
        "spec-006 already handles it (AC3), until you say otherwise.",
        "",
        "## Proposed classifications",
        "",
    ]

    if triage["entries"]:
        lines.append(
            "| Confirm | AC | Statement | Classification | Source line | Rationale |"
        )
        lines.append("|---|---|---|---|---|---|")
        for e in triage["entries"]:
            statement = e["statement"].replace("|", "\\|")
            rationale = e["rationale"].replace("|", "\\|")
            line_no = e["source_line"] if e["source_line"] is not None else "-"
            lines.append(
                f"| [ ] | {e['id']} | {statement} | `{e['classification']}` | "
                f"{line_no} | {rationale} |"
            )
    else:
        lines.append("_No residual-judgment ACs to triage._")

    lines += [
        "",
        "## Eval-able (queued for rubric shaping — 008-02)",
        "",
    ]
    if triage["eval_able"]:
        lines += [f"- {ac_id}" for ac_id in triage["eval_able"]]
    else:
        lines.append("_None — every residual AC reads as human-residual._")

    human_residual = [
        e for e in triage["entries"] if e["classification"] == CLASSIFICATION_HUMAN_RESIDUAL
    ]
    lines += [
        "",
        "## Human-residual (stays waived)",
        "",
    ]
    if human_residual:
        lines += [f"- {e['id']} — {e['rationale']}" for e in human_residual]
    else:
        lines.append("_None — every residual AC is eval-able._")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Write command (AC4)
# ---------------------------------------------------------------------------

def _spec_dir_from_plan_path(plan_path: Path, plan: dict) -> Path:
    """Derive the spec directory from the plan *file's own on-disk location*
    (AC4) — never from `plan["source_spec_path"]`.

    `source_spec_path` is a *display* path recorded verbatim by
    `oracle_plan.py` — typically repo-relative — so resolving it with
    `.resolve()` anchors it to the process's current working directory: run
    `triage` from anywhere but the repo root and the artifact would land
    under `<cwd>/eval/<spec_id>/` instead of beside the spec (breaks AC4
    colocation).

    A spec-006 evidence plan always lives at
    `<spec_dir>/oracle/<spec_id>/checks.json`, so the plan file's own
    (already on-disk, CWD-independent) location is the source of truth: the
    spec dir is its great-grandparent directory.
    """
    resolved = plan_path.resolve()
    try:
        spec_dir = resolved.parents[2]
    except IndexError:
        raise EnvError(
            "plan_path_layout_mismatch",
            f"plan path {resolved} is not nested deeply enough to be a "
            "spec-006 <spec_dir>/oracle/<spec_id>/checks.json evidence plan",
        ) from None

    # Guard: the resolved spec dir should contain the spec file the plan
    # itself names (by basename — source_spec_path is a display path, not
    # necessarily the on-disk one). If it doesn't, the plan isn't sitting at
    # the expected layout and deriving spec_dir this way would be wrong.
    expected_name = Path(plan["source_spec_path"]).name
    if expected_name and not (spec_dir / expected_name).is_file():
        raise EnvError(
            "plan_path_layout_mismatch",
            f"expected {spec_dir} (derived from the plan file's own location "
            f"{resolved}) to contain {expected_name!r} — the plan does not "
            "sit at the expected <spec_dir>/oracle/<spec_id>/checks.json "
            "layout",
        )
    return spec_dir


def triage_target(plan_path: Path):
    """Load the plan, classify its `residual_judgment` ACs, and write
    `triage.json` + `triage.md` beside the spec (ADR-0023).

    Returns `(triage_payload, out_dir)`.
    """
    plan = load_plan(plan_path)
    triage_payload = build_triage(plan)

    spec_dir = _spec_dir_from_plan_path(plan_path, plan)
    out_dir = eval_dir_for_spec(spec_dir, triage_payload["spec_id"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "triage.json").write_text(json.dumps(triage_payload, indent=2) + "\n")
    (out_dir / "triage.md").write_text(_render_triage_md(triage_payload))
    return triage_payload, out_dir


# ---------------------------------------------------------------------------
# Rubric shaping (slice 008-02 — AC1 / AC2 / AC3 / AC4 / AC5)
# ---------------------------------------------------------------------------

# Low-temperature judge defaults (AC2). Model/transport/max_tokens follow
# content-fidelity's `config.example.json` (the closest existing precedent for a
# text-judged rubric); temperature is pinned to 0.0 here — lower than
# content-fidelity's 0.6 — because AC2 calls for a low-temperature judge and the
# n-sample lower bound already absorbs the residual stochasticity.
DEFAULT_JUDGE = {
    "model": "claude-sonnet-4-6", "transport": "api", "temperature": 0.0, "max_tokens": 1024,
}
DEFAULT_SAMPLES = {"n": 4, "k": 1.0, "delta": 0.03}
DEFAULT_THRESHOLD = 0.8

_SCALE_TEXT = (
    "Scale: 1.0 = fully meets the criterion; 0.5 = partially meets it with a "
    "significant gap; 0.0 = does not meet it at all. Score anywhere between "
    "these anchors to reflect partial credit."
)


def _render_single_dimension(statement: str) -> str:
    """Archetype 1/3 (AC3): one holistic named criterion over the AC as a
    whole."""
    return (
        f'Score, in [0,1], how well the CANDIDATE UNDER TEST satisfies this '
        f'acceptance criterion: "{statement}"\n\n'
        "Named criterion: overall satisfaction of the acceptance criterion above.\n"
        f"{_SCALE_TEXT}\n\n"
        "EDIT ME: sharpen the criterion wording, add a concrete pass/fail "
        "example, and adjust the scale anchors to this AC's specifics before "
        "this rubric is used for real scoring."
    )


def _render_multi_criteria(statement: str) -> str:
    """Archetype 2/3 (AC3): several named, weighted sub-criteria combined
    into one overall score."""
    return (
        f'Score, in [0,1], how well the CANDIDATE UNDER TEST satisfies this '
        f'acceptance criterion: "{statement}"\n\n'
        "Named criteria (weighted; combine sub-scores into one overall [0,1] score):\n"
        "- Criterion A (weight 0.5): EDIT ME — name and describe the first "
        "sub-criterion this AC implies.\n"
        "- Criterion B (weight 0.3): EDIT ME — name and describe the second "
        "sub-criterion.\n"
        "- Criterion C (weight 0.2): EDIT ME — name and describe the third "
        "sub-criterion.\n\n"
        f"{_SCALE_TEXT} Weight each criterion's sub-score by the weights above.\n\n"
        "EDIT ME: replace the placeholder criteria and weights with the real "
        "sub-criteria this AC implies before this rubric is used for real "
        "scoring."
    )


def _render_comparative(statement: str) -> str:
    """Archetype 3/3 (AC3): proposed-vs-baseline comparison."""
    return (
        f'Compare a PROPOSED candidate against a BASELINE reference for this '
        f'acceptance criterion: "{statement}"\n\n'
        "Named criterion: does PROPOSED satisfy the acceptance criterion at "
        "least as well as BASELINE?\n"
        "Scale: 1.0 = PROPOSED clearly better than or equal to BASELINE on "
        "the criterion; 0.5 = roughly on par, a mixed picture; 0.0 = "
        "PROPOSED is clearly worse than BASELINE.\n\n"
        "EDIT ME: describe what 'better' means for this specific AC, and any "
        "dimension PROPOSED must not regress even while improving on others."
    )


ARCHETYPES = {
    "single_dimension": _render_single_dimension,
    "multi_criteria": _render_multi_criteria,
    "comparative": _render_comparative,
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    """AC4's `<eval-name>` derivation: lowercase, non-alnum runs collapsed to
    one underscore, leading/trailing underscores stripped — becomes the
    `score_<name>` component name once 008-04 emits + spec-006 compiles."""
    slug = _SLUG_RE.sub("_", (text or "").lower()).strip("_")
    return slug or "eval"


def build_rubric_config(ac_entry: dict, archetype: str) -> dict:
    """Pure construction of the `config.json` payload for one eval-able AC +
    archetype (AC1/AC3). No I/O.

    In the *exact* shape `skills/_common/fidelity_eval.py`'s
    `definition_hash`/`validate_freeze` consume (AC5): `judge` / `samples` /
    `threshold` / `rubric` / `cases`, unchanged — `cases` starts empty (008-03
    fills it) so 008-04 can freeze this and spec-006 can compile it with no
    reshaping.
    """
    if archetype not in ARCHETYPES:
        raise EnvError(
            "unknown_archetype",
            f"unknown archetype {archetype!r} (expected one of {sorted(ARCHETYPES)})",
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "approval_status": "draft",
        "archetype": archetype,
        "source_ac": {"id": ac_entry.get("id"), "statement": ac_entry.get("statement", "")},
        "judge": dict(DEFAULT_JUDGE),
        "samples": dict(DEFAULT_SAMPLES),
        "threshold": DEFAULT_THRESHOLD,
        "rubric": ARCHETYPES[archetype](ac_entry.get("statement", "")),
        "cases": [],
    }


def _render_rubric_md(config: dict, ac_entry: dict) -> str:
    """Render the human-reviewable `rubric.md` (AC4). Makes the human-gate
    explicit: the tool proposes this shape from a borrowed archetype; the
    human owns the wording, edits it, and approves — approval + freeze happen
    in 008-04, not here."""
    lines = [
        f"# Eval rubric — {ac_entry.get('id')}",
        "",
        f"- **Source AC:** {ac_entry.get('statement', '')}",
        f"- **Archetype:** `{config['archetype']}`",
        "",
        "> **This is a proposal, not a decision.** The skill scaffolds the "
        "shape — named criteria, an explicit scale, a judge prompt — from a "
        "borrowed archetype template; you own the wording. Edit the rubric "
        "prose below (keep `config.json`'s `rubric` field in sync — they "
        "must match) and approve it before it is used for real scoring; "
        "approval and freezing happen in 008-04, not here.",
        "",
        "## Rubric",
        "",
        "```",
        config["rubric"],
        "```",
        "",
        "## Judge defaults (edit in `config.json`, not here)",
        "",
        f"- Model: `{config['judge']['model']}`",
        f"- Transport: `{config['judge']['transport']}`",
        f"- Temperature: `{config['judge']['temperature']}`",
        f"- Samples (n): `{config['samples']['n']}`",
        f"- Threshold: `{config['threshold']}`",
        "",
    ]
    return "\n".join(lines)


def rubric_target(plan_path: Path, ac_id: str, archetype: str):
    """Load the plan, resolve the same `<spec-dir>/eval/<spec-id>/`
    colocation dir `triage_target` wrote to (AC4), read that dir's
    `triage.json`, pick the entry named `ac_id`, and shape a rubric for it
    under `<eval-dir>/<eval-name>/` (AC1/AC3/AC4).

    Refuses (`EnvError`) an unknown AC id or one that isn't classified
    `eval-able` — mirrors triage's own fail-closed spirit (AC2): only an
    eval-able AC gets a rubric shaped for it. (The per-AC human-approval gate
    is the freeze step in 008-04, not this `classification`-only check; triage's
    `confirmed` flag is not consulted here.)

    Returns `(config, out_dir)`.
    """
    plan = load_plan(plan_path)
    spec_dir = _spec_dir_from_plan_path(plan_path, plan)
    eval_dir = eval_dir_for_spec(spec_dir, plan["spec_id"])

    triage_path = eval_dir / "triage.json"
    if not triage_path.is_file():
        raise EnvError(
            "triage_missing",
            f"no triage.json at {triage_path} — run `triage` on this plan first",
        )
    try:
        triage = json.loads(triage_path.read_text())
    except json.JSONDecodeError as exc:
        raise EnvError(
            "triage_malformed_json", f"triage.json is not valid JSON: {triage_path} ({exc})"
        ) from exc

    entries_by_id = {e.get("id"): e for e in triage.get("entries", [])}
    entry = entries_by_id.get(ac_id)
    if entry is None:
        raise EnvError("ac_not_found", f"AC {ac_id!r} not found in {triage_path}'s entries")
    if entry.get("classification") != CLASSIFICATION_EVAL_ABLE:
        raise EnvError(
            "ac_not_eval_able",
            f"AC {ac_id!r} is classified {entry.get('classification')!r}, not "
            f"{CLASSIFICATION_EVAL_ABLE!r} — only eval-able ACs get a rubric shaped",
        )

    config = build_rubric_config(entry, archetype)
    out_dir = eval_dir / _slug(ac_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    (out_dir / "rubric.md").write_text(_render_rubric_md(config, entry))
    return config, out_dir


# ---------------------------------------------------------------------------
# Reference-set / dataset (slice 008-03 — AC1 / AC2 / AC3 / AC4 / AC5)
# ---------------------------------------------------------------------------

# AC2's borrowed taxonomy. `skip_case` never gets an `expected_output` (it is
# excluded from scoring entirely — that exclusion mechanics are 008-04's, not
# this slice's; here it is just a valid taxonomy member).
CASE_CATEGORIES = ("happy_path", "edge_case", "skip_case")

# Provisional minimum-viable-size floor (AC3) — a starting number, not a
# derived one; it is expected to be re-tuned once the first real eval is
# authored end-to-end. Never auto-filled toward: see `dataset_size_warning`.
MIN_DATASET_SIZE = 12

_EDIT_ME = "EDIT ME"

# --- string-constraint DSL (AC2): "<field> <op> <value>", op in {==, >=, <=} ---
_CONSTRAINT_OPS = ("==", ">=", "<=")
_CONSTRAINT_RE = re.compile(
    r"^\s*(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<op>==|>=|<=)\s*(?P<value>.+?)\s*$"
)


def parse_constraint(text: str) -> dict:
    """Parse one string-constraint DSL expression (AC2) — e.g. `"length >=
    100"` or `"version == 3.10"` — into `{"field": str, "op": "==" | ">=" |
    "<=", "value": float | str}`.

    `==`'s value is always kept as a bare **string** (surrounding quotes
    stripped if quoted), never float-coerced — `"version == 3.10"` must
    preserve `"3.10"` exactly rather than collapsing it to the float `3.1`,
    and `==` is just as often comparing non-numeric text (e.g. a tone
    label) as a numeric-looking one. `>=`/`<=` require a genuinely numeric
    value: it is parsed to a `float` right here, at parse/`validate_case`
    time, so an un-evaluable inequality (e.g. `"size >= large"`) fails at
    authoring time with a clear message, not silently or later at score
    time. Raises `EnvError` with a clear, specific message on a malformed
    expression: empty/non-string input, no recognized operator
    (`==`/`>=`/`<=`), a missing field/value, or a non-numeric `>=`/`<=`
    value.
    """
    if not isinstance(text, str) or not text.strip():
        raise EnvError(
            "malformed_constraint", f"empty or non-string constraint: {text!r}")
    m = _CONSTRAINT_RE.match(text)
    if not m:
        raise EnvError(
            "malformed_constraint",
            f"malformed constraint {text!r} — expected '<field> <op> <value>' "
            f"with <op> one of {_CONSTRAINT_OPS}",
        )
    field = m.group("field")
    op = m.group("op")
    raw_value = m.group("value").strip()
    if not raw_value:
        raise EnvError("malformed_constraint", f"malformed constraint {text!r} — missing a value")
    if op == "==":
        value = raw_value.strip("\"'")
    else:
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise EnvError(
                "malformed_constraint",
                f"malformed constraint {text!r} — {op!r} requires a numeric value, "
                f"got {raw_value!r}",
            ) from exc
    return {"field": field, "op": op, "value": value}


def evaluate_constraint(constraint: dict, actual_values: dict) -> bool:
    """Evaluate one `parse_constraint`-parsed constraint against
    `actual_values` — a dict of field name -> the value computed for one
    candidate (e.g. `{"length": 142, "tone": "warm"}`), which the eventual
    scorer (008-04's candidate-gather) is responsible for deriving from a
    candidate; this DSL only knows how to *compare*, not how to extract a
    named field's value from raw candidate text.

    `==` compares `str(actual)` against the parsed (already-string,
    never-float-coerced) `value` — so `"3.10"` never silently matches
    `"3.1"`. `>=`/`<=` already carry a numeric `value` (validated at
    `parse_constraint` time); only the *actual* value is coerced to `float`
    here, since it comes from live per-candidate data at evaluation time,
    not from the authored expression. Raises `EnvError` if the constraint's
    `field` has no entry in `actual_values`, or if a `>=`/`<=` comparison is
    attempted against a non-numeric actual value — cheap, deterministic, and
    fails clearly rather than silently passing/failing.
    """
    field, op, expected = constraint["field"], constraint["op"], constraint["value"]
    if field not in actual_values:
        raise EnvError(
            "constraint_field_missing",
            f"cannot evaluate constraint on field {field!r} — no actual value supplied",
        )
    actual = actual_values[field]
    if op == "==":
        return str(actual) == expected
    try:
        actual_num = float(actual)
    except (TypeError, ValueError) as exc:
        raise EnvError(
            "constraint_not_numeric",
            f"cannot compare field {field!r} with operator {op!r} against a non-numeric value",
        ) from exc
    return actual_num >= expected if op == ">=" else actual_num <= expected


# --- per-case shape validation (AC2 / AC5) ---

def validate_case(case, index: int) -> None:
    """Validate one case against AC2's exact shape:
    `{id, category, scenario, input, expected_output?: {description,
    constraints?: [<dsl>...]}, baseline?}`.

    `expected_output` is optional at the per-case level — its *presence*
    is what distinguishes a ground-truthed case (has a description, and
    optionally cheap deterministic `constraints`) from a rubric-only judged
    case (no hard label at all; the rubric alone scores it) — AC5's "both in
    one dataset." `baseline` is optional too: the per-case field the
    comparative archetype (PROPOSED-vs-BASELINE) needs; carried in the shape
    here so 008-04 can widen `judge()`/scoring to use it without a reshape.

    Raises `EnvError`, citing the case's position, on the first problem
    found.
    """
    where = f"cases[{index}]"
    if not isinstance(case, dict):
        raise EnvError("dataset_malformed_case", f"{where} is not an object")
    for field in ("id", "category", "scenario", "input"):
        value = case.get(field)
        if not isinstance(value, str) or not value.strip():
            raise EnvError(
                "dataset_malformed_case", f"{where} is missing a non-empty {field!r}")
    if case["category"] not in CASE_CATEGORIES:
        raise EnvError(
            "dataset_malformed_case",
            f"{where}.category {case['category']!r} must be one of {CASE_CATEGORIES}",
        )
    expected_output = case.get("expected_output")
    if expected_output is not None:
        description = expected_output.get("description") if isinstance(
            expected_output, dict) else None
        if not isinstance(description, str) or not description.strip():
            raise EnvError(
                "dataset_malformed_case",
                f"{where}.expected_output must be an object with a non-empty 'description'",
            )
        constraints = expected_output.get("constraints")
        if constraints is not None:
            if not isinstance(constraints, list):
                raise EnvError(
                    "dataset_malformed_case", f"{where}.expected_output.constraints must be a list")
            for c_index, raw_constraint in enumerate(constraints):
                try:
                    parse_constraint(raw_constraint)
                except EnvError as exc:
                    raise EnvError(
                        "dataset_malformed_case",
                        f"{where}.expected_output.constraints[{c_index}]: {exc}",
                    ) from exc
    baseline = case.get("baseline")
    if baseline is not None and not isinstance(baseline, str):
        raise EnvError("dataset_malformed_case", f"{where}.baseline must be a string when present")


def validate_dataset(cases) -> list:
    """Validate the whole case list (AC2): every case's shape, plus unique
    `id`s. Raises `EnvError` on the first problem found; returns `cases`
    unchanged on success (a pure check, no I/O)."""
    if not isinstance(cases, list):
        raise EnvError("dataset_malformed", "cases must be a list")
    seen_ids = set()
    for i, case in enumerate(cases):
        validate_case(case, i)
        if case["id"] in seen_ids:
            raise EnvError(
                "dataset_duplicate_id", f"duplicate case id {case['id']!r} at cases[{i}]")
        seen_ids.add(case["id"])
    return cases


def dataset_size_warning(cases: list):
    """AC3: a clear, non-fatal advisory when the dataset is under the
    provisional minimum-viable-size floor — never a reason to fail the
    command, and never a reason to invent cases to close the gap (spec 008
    non-goal: no fabricated ground truth). Returns `None` when the floor is
    met."""
    if len(cases) >= MIN_DATASET_SIZE:
        return None
    return (
        f"only {len(cases)} case(s) — below the provisional minimum-viable-size "
        f"floor of {MIN_DATASET_SIZE} (provisional, tuned against the first real "
        "eval). This is a non-fatal advisory: the tool never autofills cases or "
        "labels to reach the floor (spec 008 non-goal: no fabricated ground "
        "truth) — add real cases yourself."
    )


# --- scaffolding from the spec's own text (AC1) ---

_EXAMPLES_HEADING_RE = re.compile(r"^#{1,6}\s*examples?\b", re.IGNORECASE)
_EDGE_CASE_HEADING_RE = re.compile(r"^#{1,6}\s*edge[\s-]*cases?\b", re.IGNORECASE)
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")


def _extract_section_bullets(spec_text: str, heading_re: re.Pattern) -> list:
    """Bullet items (`- ...` / `* ...`) under the first heading matching
    `heading_re`, up to the next heading of any level (or end of text)."""
    bullets = []
    in_section = False
    for line in spec_text.splitlines():
        if heading_re.match(line):
            in_section = True
            continue
        if in_section and _ANY_HEADING_RE.match(line):
            break
        if in_section:
            m = _BULLET_RE.match(line)
            if m:
                bullets.append(m.group(1))
    return bullets


def _placeholder_case(index: int, category: str) -> dict:
    """A clearly-labeled, never-invented starting point (AC1/AC3): the
    scenario/input/expected-output text is an explicit `EDIT ME` instruction,
    not fabricated case content."""
    label = category.replace("_", " ")
    case = {
        "id": f"case-{index}",
        "category": category,
        "scenario": f"{_EDIT_ME} — describe a {label} scenario for this AC.",
        "input": f"{_EDIT_ME} — the input this scenario feeds to the candidate under test.",
    }
    if category != "skip_case":
        case["expected_output"] = {
            "description": f"{_EDIT_ME} — describe the expected behaviour/output.",
        }
    return case


def scaffold_cases(spec_text: str) -> list:
    """AC1: seed cases from the spec's own `## Examples` / `## Edge cases`
    markdown sections — bullet text copied **verbatim**, never invented, as
    `happy_path` / `edge_case` cases with no `expected_output` (rubric-only:
    inventing a hard label for spec prose the tool did not author would be
    fabricated ground truth).

    When neither section is present (or both are empty), scaffolds a small
    labeled `EDIT ME` placeholder per taxonomy category instead — a starting
    point for the human to fill in, never fabricated content (AC1/AC3).
    """
    cases = []
    idx = 1
    for bullet in _extract_section_bullets(spec_text, _EXAMPLES_HEADING_RE):
        cases.append({"id": f"case-{idx}", "category": "happy_path", "scenario": bullet,
                      "input": bullet})
        idx += 1
    for bullet in _extract_section_bullets(spec_text, _EDGE_CASE_HEADING_RE):
        cases.append({"id": f"case-{idx}", "category": "edge_case", "scenario": bullet,
                      "input": bullet})
        idx += 1
    if not cases:
        for category in CASE_CATEGORIES:
            cases.append(_placeholder_case(idx, category))
            idx += 1
    return cases


def _render_dataset_md(config: dict, ac_id: str, warning) -> str:
    """Render the human-reviewable `dataset.md` (mirrors `triage.md`/
    `rubric.md`'s idiom): makes the human-gate + honesty contract explicit —
    this is a project-owned, human-grown artifact; the tool never fabricates
    case content or ground truth."""
    cases = config.get("cases", [])
    lines = [
        f"# Eval dataset — {ac_id}",
        "",
        f"- **Cases:** {len(cases)} (provisional minimum-viable-size floor: "
        f"{MIN_DATASET_SIZE}, tuned against the first real eval)",
        "",
    ]
    if warning:
        lines += [f"> **Advisory:** {warning}", ""]
    lines += [
        "> **Local file = source of truth.** This dataset lives in the "
        "project's git, colocated with the spec (`config.json`'s `cases`) — "
        "you own and grow it directly; the tool never fabricates case "
        "content or ground-truth labels (spec 008 non-goal).",
        "",
        "## Cases",
        "",
    ]
    if cases:
        lines.append("| id | category | scenario | ground-truthed? |")
        lines.append("|---|---|---|---|")
        for c in cases:
            scenario = (c.get("scenario") or "").replace("|", "\\|")
            truthed = "yes" if c.get("expected_output") else "rubric-only"
            lines.append(f"| {c.get('id')} | {c.get('category')} | {scenario} | {truthed} |")
    else:
        lines.append("_No cases yet._")
    lines.append("")
    return "\n".join(lines)


def dataset_target(plan_path: Path, ac_id: str):
    """Load the plan, resolve the same `<spec-dir>/eval/<spec-id>/<eval-name>/`
    dir `rubric_target` wrote to (AC1/AC4), and scaffold/validate its
    `config.json`'s `cases`.

    Requires `rubric` to have already run for `ac_id` (its `config.json` is
    where this slice's cases live — AC5's harness shape, extended). On first
    run (`cases` still empty), seeds via `scaffold_cases`; on any later run,
    never overwrites already-present cases (a human may have edited them) —
    `dataset` only re-validates and re-reports in that case.

    Returns `(config, out_dir, warning, scaffolded)`.
    """
    plan = load_plan(plan_path)
    spec_dir = _spec_dir_from_plan_path(plan_path, plan)
    eval_dir = eval_dir_for_spec(spec_dir, plan["spec_id"])

    out_dir = eval_dir / _slug(ac_id)
    config_path = out_dir / "config.json"
    if not config_path.is_file():
        raise EnvError(
            "rubric_missing",
            f"no config.json at {config_path} — run `rubric` for {ac_id!r} first",
        )
    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise EnvError(
            "config_malformed_json", f"config.json is not valid JSON: {config_path} ({exc})"
        ) from exc

    existing_cases = config.get("cases") or []
    if existing_cases:
        cases = existing_cases
        scaffolded = False
    else:
        spec_path = spec_dir / Path(plan["source_spec_path"]).name
        spec_text = spec_path.read_text() if spec_path.is_file() else ""
        cases = scaffold_cases(spec_text)
        scaffolded = True

    validate_dataset(cases)
    config["cases"] = cases
    config_path.write_text(json.dumps(config, indent=2) + "\n")

    warning = dataset_size_warning(cases)
    (out_dir / "dataset.md").write_text(_render_dataset_md(config, ac_id, warning))
    return config, out_dir, warning, scaffolded


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _triage_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_authoring.py triage",
        description=(
            "Classify a spec-006 evidence plan's residual_judgment ACs into "
            "eval-able vs human-residual, with a rationale per AC."
        ),
    )
    parser.add_argument(
        "plan_path", metavar="plan",
        help="Path to a spec-006 checks.json evidence plan.",
    )
    args = parser.parse_args(argv)

    plan_path = Path(args.plan_path).resolve()
    try:
        triage_payload, out_dir = triage_target(plan_path)
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    n_eval = len(triage_payload["eval_able"])
    n_total = len(triage_payload["entries"])
    n_residual = n_total - n_eval
    print(
        f"servo: triaged {triage_payload['spec_id']} "
        f"({n_eval} eval-able, {n_residual} human-residual of {n_total}) -> {out_dir}"
    )
    return 0


def _rubric_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_authoring.py rubric",
        description=(
            "Shape a rubric (named criteria, an explicit scale, a judge "
            "prompt) for one eval-able AC from triage.json."
        ),
    )
    parser.add_argument(
        "plan_path", metavar="plan",
        help="Path to the same spec-006 checks.json plan passed to `triage`.",
    )
    parser.add_argument(
        "--ac", required=True,
        help="The eval-able AC id to shape a rubric for (from triage.json's eval_able list).",
    )
    parser.add_argument(
        "--archetype", choices=sorted(ARCHETYPES), default="single_dimension",
        help="Which rubric archetype template to start from (default: single_dimension).",
    )
    args = parser.parse_args(argv)

    plan_path = Path(args.plan_path).resolve()
    try:
        config, out_dir = rubric_target(plan_path, args.ac, args.archetype)
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"servo: shaped a {config['archetype']} rubric for {args.ac} -> {out_dir}")
    return 0


def _dataset_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_authoring.py dataset",
        description=(
            "Scaffold/grow the statistical reference set (cases) for one "
            "already-rubric-shaped AC's config.json."
        ),
    )
    parser.add_argument(
        "plan_path", metavar="plan",
        help="Path to the same spec-006 checks.json plan passed to `triage`/`rubric`.",
    )
    parser.add_argument(
        "--ac", required=True,
        help="The AC id to scaffold/grow a dataset for (must already have a rubric config.json).",
    )
    args = parser.parse_args(argv)

    plan_path = Path(args.plan_path).resolve()
    try:
        config, out_dir, warning, scaffolded = dataset_target(plan_path, args.ac)
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    verb = "scaffolded" if scaffolded else "left"
    print(f"servo: {verb} {len(config['cases'])} case(s) for {args.ac} -> {out_dir}")
    if warning:
        print(f"warning: {warning}")
    return 0


def main(argv: list | None = None) -> int:
    # Hand-rolled subcommand dispatch (mirrors `oracle_plan.py` / `gate.py`).
    # `triage` (008-01), `rubric` (008-02), and `dataset` (008-03) exist so
    # far; later slices add `from-goal`/`emit`/`audit` alongside them.
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "triage":
        return _triage_main(argv[1:])
    if argv and argv[0] == "rubric":
        return _rubric_main(argv[1:])
    if argv and argv[0] == "dataset":
        return _dataset_main(argv[1:])
    print(
        "error: unknown or missing subcommand (expected: triage, rubric, dataset)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
