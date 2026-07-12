"""
servo eval-authoring — slices 008-01 (residual-triage), 008-02
(rubric-shaping), 008-03 (reference-set), 008-04 (frozen-params-and-emit),
008-05 (goal-to-criteria), and 008-06 (judge-audit), the self-contained core
of the single servo-owned guided skill `/servo:eval-authoring` (ADR-0019 / ADR-0026).
Durable artifacts are co-located with the spec (ADR-0023), mirroring
`skills/spec-oracle/oracle_plan.py`'s convention.

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

    python3 eval_authoring.py params <plan> --ac <id> [--n N] [--delta D]
                                     [--threshold T] [--model M]
                                     [--temperature X] [--max-tokens N]
                                     [--transport api|cli]
        (Slice 008-04.) Set/confirm the frozen `n` / `δ` (samples.delta) /
        threshold / judge model+params for one already-rubric-shaped AC's
        `config.json` (AC1). Every flag left unset keeps the value `rubric`
        already seeded from the shipped fidelity presets' defaults — so
        accepting every default is just running this with no flags at all.
        Prints a one-line plain-language trade-off note per knob (the
        ADR-0005 knobs: too-wide δ never passes, too-narrow flaps; more
        samples cost more but stabilize; threshold trades false-pass vs
        false-fail) before writing the confirmed values back.

    python3 eval_authoring.py emit <plan> --ac <id> [--target <dir>] [--weight W]
        (Slice 008-04.) Freeze the AC's `config.json` — the human-approval
        gate (AC4): validates the dataset's shape, pins
        `hashes`/`approved_content_hash`, and flips `approval_status` to
        `approved`. With no `--target`, this is the stopping point: "an
        approved, compilable definition" (AC4) and nothing more. With
        `--target <dir>`, additionally installs the resulting
        `score_<name>` component into `<dir>` — splicing it into
        `<dir>/oracle.sh` and copying the runtime (`score.py` +
        `fidelity_eval.py`) plus the frozen `config.json` into
        `<dir>/.servo/<name>/` (AC2/AC3) — but never *runs* it (AC4);
        running is `gate.py`'s job once installed. Idempotent: a re-`emit`
        with the same `--target` refreshes the SEED block + weight in place
        rather than duplicating either.

    python3 eval_authoring.py uninstall <plan> --ac <id> --target <dir>
        (Slice 008-04.) Symmetric with `emit --target`: removes the
        `score_<name>` SEED block + COMPONENTS entry from `<dir>/oracle.sh`
        and deregisters it from the install manifest, keeping the frozen
        artifacts under `<dir>/.servo/<name>/` untouched.

    python3 eval_authoring.py from-goal "<goal text>" [--spec-dir <dir>] [--force]
        (Slice 008-05, ADR-0027.) Expand a free-form goal into a *proposed*,
        tagged (`deterministic|judged|human-only`) acceptance-criteria set via
        a fresh one-shot `claude -p` call, run a SECOND fresh `claude -p`
        independent-reviewer pass (no access to the expansion's reasoning —
        only the goal text and the proposal) for advisory structural flags,
        and write the curated-pending proposal under
        `<spec-dir>/<goal-slug>/` as `criteria.json` (machine contract) and
        `criteria.md` (the human-editable, spec-shaped artifact: frontmatter +
        a plain `## Acceptance criteria` list that `spec-oracle classify`
        (006) parses unchanged). This is an authoring ASSIST, never an
        autonomous step: every AC starts `approval_status: "proposed"` —
        nothing is frozen without a human recording approval (ADR-0027
        Decision #3) — and the human may edit/accept/reject/**add** any AC by
        editing `criteria.md`'s plain numbered list directly, the same way
        they would edit a hand-written spec's AC section. Refuses
        (`EnvError`) to re-run over an already-curated goal directory —
        `criteria.md`/`criteria.json` may already carry human edits and
        recorded approvals, and a fresh non-deterministic LLM expansion must
        never silently clobber those (mirrors `dataset_target`'s own
        never-overwrite posture for its human-grown cases). Pass `--force` to
        regenerate deliberately.

    python3 eval_authoring.py criteria-check <criteria.md>
        (Slice 008-05, ADR-0027 Decision #5.) The explicit, human-invokable
        form of AC3's human-curation gate: reads the sibling `criteria.json`
        a `from-goal` run wrote beside `<criteria.md>`, prints each AC's
        `approval_status`, and exits non-zero until every AC is
        `"approved"`. The no-freeze-without-approval guarantee itself is
        enforced procedurally, not by any oracle/gate machinery (ADR-0027
        Decision #5) — this command is how a human (or a future promotion
        step) actually invokes that check before treating a goal-derived AC
        set as curated.

    python3 eval_authoring.py criteria-split <criteria.md>
        (Slice 008-05, ADR-0027 Decision #4.) Run ONLY `edd-suitability`
        (015)'s criteria-classification half — the evaluable-vs-human-residual
        split — over a `from-goal`-emitted (or any spec-shaped) AC artifact,
        via the same `oracle_plan.py classify` subprocess `suitability.py`
        itself uses internally. Deliberately NOT the full `suitable |
        needs_evidence | unsuitable` verdict: at goal-expansion time there is
        no target signal or reference set yet, so a full verdict would be
        `needs_evidence` across the board (ADR-0018) — this surfaces only the
        half goal→eval can legitimately claim.

    python3 eval_authoring.py audit <eval> [--labels <file>] [--scores <file>]
                                    [--sample-size N]
        (Slice 008-06.) A light, ADVISORY judge-trust audit over an eval
        directory (`<eval>`, holding `config.json` and, once scored,
        `ledger.jsonl`): samples a mixed pass/fail set of the eval's judged
        cases for human spot-checking, records the `--labels` file's human
        verdicts alongside the judge scores, and computes fail-precision /
        pass-miss-rate / (above a provisional ≥20-labeled-case floor)
        score-vs-human drift, recommending `auto` (trust the judge) or
        `confirmed-only` — advisory output only, never enforced. Never
        alters the composite, the frozen `config.json`, or `oracle.sh`/
        `gate.py`; auto-demoting an untrusted judge is deferred (see
        `docs/refinement-todo.md`). Appends the audit record to
        `ledger.jsonl` (a `"kind": "judge_audit"` record, distinguishable
        from `score.py`'s own scoring records).

Architecture note — no spec-006 compile step (this slice's correction)
------------------------------------------------------------------------
Spec 008's prose describes `/servo:spec-oracle`'s "eval-family compile step"
freezing the authored definition into `score_<name>`. That step does not
exist: `skills/spec-oracle/oracle_overlay.py` only freezes deterministic
overlays. The real mechanism — already used by both shipped presets
(`content-fidelity`, `design-eval`) — is that the authoring skill itself
freezes + installs its `score_<name>` component via the shared
`fidelity_eval.py` splice machinery (ADR-0024): `freeze_dataset_config` +
`install_component` below mirror `content_fidelity.py`'s own
`freeze`/`install` almost line for line. `emit` is this slice's single
guided verb over both.

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
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
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
# Same-skill-dir load of score.py (slice 008-04). Not a cross-skill import
# (see the "classification stays deterministic" note above) — score.py is
# the other half of this same skill directory. Reused for its
# `definition_hash`/`artifact_hashes` wrappers (so `freeze_dataset_config`
# hashes the *exact* shape `score.py`'s own `validate_freeze` will later
# check) and its already-loaded `_fe` (the shared `fidelity_eval.py`
# splice/manifest primitives) — mirrors `content_fidelity.py::_load_score()`.
# ---------------------------------------------------------------------------

def _load_score():
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("eval_authoring_score", here / "score.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Frozen params (slice 008-04 — AC1)
# ---------------------------------------------------------------------------

# One-line plain-language trade-off note per frozen knob (AC1, the ADR-0005
# knobs), paired with a getter over the *confirmed* (current) value so the
# guidance always reflects what is actually about to be written, not a
# static example.
_PARAM_TRADEOFFS = (
    ("samples.n", lambda c: c["samples"]["n"],
     "more judge samples cost more (n x judge calls per case) but stabilize the "
     "lower-bound score against a noisy judge"),
    ("samples.delta (δ)", lambda c: c["samples"].get("delta"),
     "the noise-floor plateau: too wide and the eval can plateau below threshold and "
     "never pass; too narrow and a noisy judge flaps pass/fail run to run"),
    ("threshold", lambda c: c["threshold"],
     "the pass/fail cutoff: a higher threshold trades more false-fails for fewer "
     "false-passes, and vice versa"),
    ("judge.model", lambda c: c["judge"]["model"],
     "a stronger judge model reads subtler failures but costs more per sample"),
    ("judge.temperature", lambda c: c["judge"].get("temperature"),
     "low (near 0) keeps repeated judgments consistent, which the n-sample lower "
     "bound assumes"),
)


def apply_params(
    config: dict, *, n=None, delta=None, threshold=None, model=None,
    temperature=None, max_tokens=None, transport=None,
) -> dict:
    """AC1: set/confirm the frozen knobs. Every argument left `None` keeps
    whatever `rubric` already seeded from `DEFAULT_JUDGE`/`DEFAULT_SAMPLES`/
    `DEFAULT_THRESHOLD` — so accepting every default is just calling this
    with no overrides at all. Mutates and returns `config`."""
    if n is not None:
        config["samples"]["n"] = n
    if delta is not None:
        config["samples"]["delta"] = delta
    if threshold is not None:
        config["threshold"] = threshold
    if model is not None:
        config["judge"]["model"] = model
    if temperature is not None:
        config["judge"]["temperature"] = temperature
    if max_tokens is not None:
        config["judge"]["max_tokens"] = max_tokens
    if transport is not None:
        config["judge"]["transport"] = transport
    return config


def render_params_guidance(config: dict) -> list:
    """AC1's one-line plain-language trade-off note per knob, over the
    *confirmed* value of each — printed by the CLI so a human sees the
    rationale before accepting/overriding."""
    return [f"- {label} = {getter(config)} — {note}" for label, getter, note in
            _PARAM_TRADEOFFS]


def params_target(plan_path: Path, ac_id: str, **overrides):
    """Load the plan, resolve the same rubric `config.json` `rubric_target`
    wrote, and set/confirm its frozen knobs (AC1). Returns `(config,
    out_dir)`."""
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

    apply_params(config, **overrides)
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    return config, out_dir


# ---------------------------------------------------------------------------
# Freeze + install (slice 008-04 — AC2 / AC3 / AC4). See the module
# docstring's architecture note: there is no spec-006 compile step — this
# skill self-freezes + self-installs via the shared fidelity_eval.py splice
# machinery, exactly like the two shipped presets.
# ---------------------------------------------------------------------------

def component_name(spec_id: str, ac_id: str) -> str:
    """Disambiguates the installed `score_<name>` component across specs (an
    008-03 carry-forward): two different specs' AC ids can slug to the same
    string (e.g. both simply "AC-1"), which would collide if both were
    installed into the same target's `oracle.sh` side by side. Namespacing
    by the spec id too keeps the component name — and its
    `.servo/<component>/` directory — unique across every spec authored
    against the same target, while staying a shell-safe suffix for the
    `score_<component>` bash function name (never starts with a digit once
    the fixed `score_` prefix is prepended)."""
    return f"{_slug(spec_id)}_{_slug(ac_id)}"


def freeze_dataset_config(config: dict, out_dir: Path, score_mod) -> dict:
    """The human-approval gate (AC4): validate the dataset's shape, pin the
    frozen artifact hashes + definition hash, and flip `approval_status` to
    `approved`. Mutates and returns `config`; the caller persists it.

    Refuses (`EnvError`) an empty dataset — freezing zero cases would
    produce a component `score()` can never actually score (its own "no
    scored cases" guard would always fire) — but does *not* block on the
    provisional minimum-viable-size floor (AC3's floor is an advisory
    warning, not a freeze precondition; a human who has already seen it may
    still choose to freeze deliberately).
    """
    cases = config.get("cases") or []
    validate_dataset(cases)
    if not cases:
        raise EnvError(
            "dataset_empty",
            "cannot freeze an eval with no cases — run `dataset` to grow the reference "
            "set first",
        )
    config["hashes"] = score_mod.artifact_hashes(config, out_dir)
    config["approved_content_hash"] = score_mod.definition_hash(config)
    config["approval_status"] = "approved"
    config["approved_at"] = score_mod._fe.iso_now()
    return config


def _install_fragment(component: str) -> str:
    """The `score_<component>` shell function spliced into the target's
    `oracle.sh` (mirrors `content_fidelity.py`'s own `_FRAGMENT`,
    parameterized by the disambiguated component name — AC2/AC3)."""
    return (
        f"# SEED:start {component}\n"
        f"score_{component}() {{\n"
        "  if ! command -v python3 >/dev/null 2>&1; then\n"
        f'    echo "missing: python3 ({component})" >&2\n'
        "    return 2\n"
        "  fi\n"
        f'  python3 .servo/{component}/score.py "$PWD"\n'
        "}\n"
        f"# SEED:end {component}\n"
    )


def install_component(
    config: dict, component: str, target: Path, weight: float, score_mod,
) -> None:
    """Splice `score_<component>` into `<target>/oracle.sh` and copy the
    runtime (AC2/AC3): `score.py` + `fidelity_eval.py`, plus the frozen
    `config.json` itself, into `<target>/.servo/<component>/` — mirrors
    `content_fidelity.py::install()`'s splice/copy mechanics exactly (no
    parallel harness). Idempotent: a re-install refreshes the SEED block +
    weight in place rather than duplicating either. Refuses (`EnvError`) an
    unapproved config — `emit` (freeze) must run first (AC4: nothing is
    installed without the human-approval gate having already fired) — and a
    missing target `oracle.sh` (scaffold the target first).
    """
    if config.get("approval_status") != "approved":
        raise EnvError(
            "not_approved",
            "cannot install an unapproved eval definition — run `emit` (without --target) "
            "to freeze it first",
        )
    oracle = target / "oracle.sh"
    if not oracle.is_file():
        raise EnvError(
            "oracle_missing", f"oracle.sh not found: {oracle} (scaffold the target first)")

    comp_dir = target / ".servo" / component
    comp_dir.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    shutil.copyfile(here / "score.py", comp_dir / "score.py")
    shutil.copyfile(here.parent / "_common" / "fidelity_eval.py", comp_dir / "fidelity_eval.py")
    (comp_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")

    text = oracle.read_text()
    text = score_mod._fe.splice_component(text, component, _install_fragment(component))
    text = score_mod._fe.splice_components_entry(text, component, weight)
    oracle.write_text(text)
    score_mod._fe.register_manifest(target, component)


def uninstall_component(target: Path, component: str, score_mod) -> None:
    """Symmetric with `install_component`: removes the SEED block +
    COMPONENTS entry and deregisters the manifest; keeps the frozen
    artifacts under `<target>/.servo/<component>/` (mirrors
    `content_fidelity.py::uninstall`)."""
    oracle = target / "oracle.sh"
    if not oracle.is_file():
        raise EnvError("oracle_missing", f"oracle.sh not found: {oracle}")
    text = oracle.read_text()
    text = score_mod._fe.unsplice_component(text, component)
    oracle.write_text(text)
    score_mod._fe.deregister_manifest(target, component)


def emit_target(plan_path: Path, ac_id: str, target=None, weight: float = 1.0):
    """AC2/AC3/AC4: freeze `<eval-dir>/<name>/config.json` (the
    human-approval gate) and — when `target` is given — install the
    resulting `score_<name>` component into it (AC2's "a frozen
    score_<name>"). No `target` freezes only, leaving "an approved,
    compilable definition" (AC4) for a later call; this collapses
    `content_fidelity.py`'s separate `freeze`/`install` steps into one
    guided CLI verb, since the shipped fidelity presets self-install via the
    same `fidelity_eval.py` splice machinery rather than any spec-006
    compile step (see the module docstring's architecture note).

    Never runs the eval (AC4's "does not run") — that is `gate.py`'s job
    once installed.

    Returns `(config, out_dir, component, installed)`.
    """
    plan = load_plan(plan_path)
    spec_dir = _spec_dir_from_plan_path(plan_path, plan)
    eval_dir = eval_dir_for_spec(spec_dir, plan["spec_id"])
    out_dir = eval_dir / _slug(ac_id)
    config_path = out_dir / "config.json"
    if not config_path.is_file():
        raise EnvError(
            "config_missing",
            f"no config.json at {config_path} — run `rubric` (then `dataset`) for "
            f"{ac_id!r} first",
        )
    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise EnvError(
            "config_malformed_json", f"config.json is not valid JSON: {config_path} ({exc})"
        ) from exc

    score_mod = _load_score()
    freeze_dataset_config(config, out_dir, score_mod)
    config_path.write_text(json.dumps(config, indent=2) + "\n")

    component = component_name(plan["spec_id"], ac_id)
    installed = False
    if target is not None:
        install_component(config, component, Path(target), weight, score_mod)
        installed = True
    return config, out_dir, component, installed


def uninstall_target(plan_path: Path, ac_id: str, target) -> str:
    """Resolve the same disambiguated component name `emit_target` installed
    under, and remove it from `target` (AC6's round-trip)."""
    plan = load_plan(plan_path)
    _validate_spec_id(plan["spec_id"])
    component = component_name(plan["spec_id"], ac_id)
    score_mod = _load_score()
    uninstall_component(Path(target), component, score_mod)
    return component


# ---------------------------------------------------------------------------
# Judge-audit (slice 008-06) — a light, ADVISORY judge-trust audit. Samples an
# eval's already-judged cases for human spot-checking, computes agreement
# metrics against the human labels, and recommends `auto` (trust the judge)
# vs `confirmed-only` (require human confirmation). Reports and recommends
# only: it never alters the composite, the frozen `config.json` definition,
# or `oracle.sh`/`gate.py` (AC4). Auto-demoting an untrusted judge in the
# composite is explicitly deferred — see
# `docs/refinement-todo.md` ("Judge-audit -> composite gating") and spec 008's
# Open questions — pending a future ADR + slice.
# ---------------------------------------------------------------------------

AUDIT_SCHEMA_VERSION = 1

# Provisional (AC2/AC3, borrowed from the surveyed prior art's judge-
# monitoring) — starting numbers, not derived ones, exactly like
# `MIN_DATASET_SIZE` above; expected to be re-tuned once a real judge audit
# has run end-to-end.
AUDIT_DRIFT_MIN_SAMPLE = 20
AUDIT_FAIL_PRECISION_MIN = 0.70
AUDIT_PASS_MISS_RATE_MAX = 0.20

RECOMMENDATION_AUTO = "auto"
RECOMMENDATION_CONFIRMED_ONLY = "confirmed-only"


def _judge_verdict(score_value: float, threshold: float) -> str:
    """A case's judge verdict (AC1): `pass` iff its judged score >= the
    eval's threshold, else `fail`."""
    return "pass" if score_value >= threshold else "fail"


def load_judged_scores(eval_dir: Path, scores_path: Path | None = None) -> dict:
    """The judged case scores to audit (AC1): `{case_id: score}`.

    From an explicit `--scores` override file when given (a JSON object
    mapping `case_id -> score`), else the most recent *scoring* run recorded
    in `<eval_dir>/ledger.jsonl` — the last record with no `"kind"` marker
    (score.py's own `_ledger` writer never sets one; only this module's own
    audit records do, via `"kind": "judge_audit"` below — so a re-audit never
    mistakes a prior audit record for a fresh scoring run to audit against).

    Raises `EnvError` when neither is available or either is malformed —
    never fabricates a score to audit (mirrors ADR-0005's honesty posture,
    extended to authoring-time).
    """
    if scores_path is not None:
        if not scores_path.is_file():
            raise EnvError("scores_missing", f"--scores file not found: {scores_path}")
        try:
            payload = json.loads(scores_path.read_text())
        except json.JSONDecodeError as exc:
            raise EnvError(
                "scores_malformed_json", f"--scores file is not valid JSON: {scores_path} ({exc})"
            ) from exc
        if not isinstance(payload, dict) or not payload:
            raise EnvError(
                "scores_malformed",
                "--scores file must be a non-empty JSON object of case_id -> score",
            )
        try:
            return {str(k): float(v) for k, v in payload.items()}
        except (TypeError, ValueError) as exc:
            raise EnvError(
                "scores_malformed", f"--scores file has a non-numeric score: {exc}"
            ) from exc

    ledger_path = eval_dir / "ledger.jsonl"
    if not ledger_path.is_file():
        raise EnvError(
            "ledger_missing",
            f"no ledger.jsonl at {ledger_path} — run the eval at least once (or pass "
            "--scores) before auditing",
        )
    latest = None
    for line in ledger_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (isinstance(record, dict) and record.get("kind") is None
                and isinstance(record.get("cases"), list)):
            latest = record
    if latest is None:
        raise EnvError(
            "no_score_run",
            f"no scoring run found in {ledger_path} — run the eval at least once before "
            "auditing",
        )
    scores = {}
    for case in latest["cases"]:
        if isinstance(case, dict) and case.get("id") is not None and case.get("score") is not None:
            scores[str(case["id"])] = float(case["score"])
    if not scores:
        raise EnvError(
            "no_score_run", f"the most recent scoring run in {ledger_path} scored no cases")
    return scores


def select_audit_sample(judged_scores: dict, threshold: float, sample_size=None) -> list:
    """AC1: a mixed pass/fail selection of judged case ids for human spot-
    checking, stably ordered so a re-run over the same scores is
    deterministic. With no `sample_size`, every judged case is eligible
    (the provisional reference-set floor, `MIN_DATASET_SIZE` above, is small
    enough that capping is unnecessary by default); with one given, splits it
    evenly across the pass/fail groups so the sample stays mixed rather than
    exhausting one group first."""
    passes = sorted(
        cid for cid, s in judged_scores.items() if _judge_verdict(s, threshold) == "pass")
    fails = sorted(
        cid for cid, s in judged_scores.items() if _judge_verdict(s, threshold) == "fail")
    if sample_size is None:
        return sorted(passes + fails)
    half = max(1, sample_size // 2)
    return sorted(passes[:half] + fails[:half])


def parse_labels(payload: dict) -> dict:
    """AC1: parse a `--labels` file's payload into `{case_id: {"verdict":
    "pass"|"fail", "score": float|None}}`.

    Each entry is either a bare `"pass"`/`"fail"` string (verdict only, no
    drift input) or an object `{"verdict": ..., "score": <optional numeric
    human score, for AC2's drift metric>}`. Raises `EnvError` on an invalid
    verdict or a non-numeric score — never silently drops or guesses a
    label."""
    labels = {}
    for case_id, raw in payload.items():
        if isinstance(raw, str):
            verdict, human_score = raw, None
        elif isinstance(raw, dict):
            verdict, human_score = raw.get("verdict"), raw.get("score")
        else:
            raise EnvError(
                "label_malformed",
                f"label for {case_id!r} must be a 'pass'/'fail' string or an object",
            )
        if verdict not in ("pass", "fail"):
            raise EnvError(
                "label_malformed",
                f"label for {case_id!r} has verdict {verdict!r} — must be 'pass' or 'fail'",
            )
        if human_score is not None:
            try:
                human_score = float(human_score)
            except (TypeError, ValueError) as exc:
                raise EnvError(
                    "label_malformed", f"label for {case_id!r} has a non-numeric score: {exc}"
                ) from exc
        labels[str(case_id)] = {"verdict": verdict, "score": human_score}
    return labels


def compute_audit_metrics(
    judged_scores: dict, threshold: float, labels: dict, sample_ids: list,
) -> dict:
    """AC2: fail-precision, pass-miss-rate, and (only above the provisional
    floor) score-vs-human drift, over the **labeled** sample — the sampled
    ids that actually carry a human label (an author may sample more cases
    than they have gotten around to labeling yet).

    - **fail-precision** = |judge-fail ∩ human-fail| / |judge-fail|.
    - **pass-miss-rate** = |human-fail ∩ judge-pass| / |human-fail|.
    - **drift** = mean |judge score − human score| over labeled cases that
      carry a numeric human score, computed ONLY when that count clears
      `AUDIT_DRIFT_MIN_SAMPLE` — below it, suppressed with a stated caveat
      rather than reporting a spurious number (AC2).

    Both ratios handle an empty denominator cleanly: a stated "n/a" note,
    never a `ZeroDivisionError`. Every `*_note` field is `None` exactly when
    its paired metric is itself not `None`.
    """
    labeled_ids = [cid for cid in sample_ids if cid in labels]
    judge_fail = {
        cid for cid in labeled_ids if _judge_verdict(judged_scores[cid], threshold) == "fail"}
    judge_pass = {
        cid for cid in labeled_ids if _judge_verdict(judged_scores[cid], threshold) == "pass"}
    human_fail = {cid for cid in labeled_ids if labels[cid]["verdict"] == "fail"}

    if judge_fail:
        fail_precision = len(judge_fail & human_fail) / len(judge_fail)
        fail_precision_note = None
    else:
        fail_precision = None
        fail_precision_note = "n/a — no judge-fail cases in the labeled sample"

    if human_fail:
        pass_miss_rate = len(human_fail & judge_pass) / len(human_fail)
        pass_miss_note = None
    else:
        pass_miss_rate = None
        pass_miss_note = "n/a — no human-fail cases in the labeled sample"

    drift_inputs = [
        abs(judged_scores[cid] - labels[cid]["score"])
        for cid in labeled_ids if labels[cid]["score"] is not None
    ]
    if len(drift_inputs) >= AUDIT_DRIFT_MIN_SAMPLE:
        drift = sum(drift_inputs) / len(drift_inputs)
        drift_note = None
    else:
        drift = None
        drift_note = (
            f"suppressed — only {len(drift_inputs)} labeled case(s) carry a numeric human "
            f"score, below the provisional minimum floor of {AUDIT_DRIFT_MIN_SAMPLE}; a "
            "score-vs-human drift estimate below this floor would be spurious"
        )

    return {
        "n_labeled": len(labeled_ids),
        "fail_precision": fail_precision,
        "fail_precision_note": fail_precision_note,
        "pass_miss_rate": pass_miss_rate,
        "pass_miss_note": pass_miss_note,
        "drift": drift,
        "drift_n": len(drift_inputs),
        "drift_note": drift_note,
    }


def recommend_judge_trust(metrics: dict) -> str:
    """AC3: `auto` (trust the judge) when both fail-precision and pass-miss-
    rate clear the provisional thresholds; `confirmed-only` otherwise —
    including when either metric is undefined (`n/a`), fail-closed exactly
    like `classify_entry`'s own "when uncertain, the safer side" posture
    above. Advisory only — the caller prints/returns this, never enforces
    it (AC3/AC4)."""
    fp, pmr = metrics["fail_precision"], metrics["pass_miss_rate"]
    if (fp is not None and pmr is not None
            and fp >= AUDIT_FAIL_PRECISION_MIN and pmr <= AUDIT_PASS_MISS_RATE_MAX):
        return RECOMMENDATION_AUTO
    return RECOMMENDATION_CONFIRMED_ONLY


def audit_target(
    eval_dir: Path, *, labels_path: Path | None = None, scores_path: Path | None = None,
    sample_size=None,
) -> dict:
    """AC1/AC2/AC3/AC5: run one advisory judge-trust audit over
    `<eval_dir>/config.json` + its judged scores, append the result to
    `<eval_dir>/ledger.jsonl`, and return the audit record.

    Reads ONLY `config.json` (for `threshold`) and `ledger.jsonl` (for the
    judged scores, or `scores_path`'s override) — never writes to either, and
    never touches `oracle.sh` (AC4: the composite / frozen definition / gate
    machinery are unaffected by an audit run; auto-demotion is deferred, see
    this section's module comment above).
    """
    config_path = eval_dir / "config.json"
    if not config_path.is_file():
        raise EnvError(
            "config_missing",
            f"no config.json at {config_path} — not an eval-authoring eval directory",
        )
    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise EnvError(
            "config_malformed_json", f"config.json is not valid JSON: {config_path} ({exc})"
        ) from exc
    threshold = config.get("threshold")
    if threshold is None:
        raise EnvError("config_missing_threshold", f"{config_path} has no 'threshold'")

    judged_scores = load_judged_scores(eval_dir, scores_path)
    sample_ids = select_audit_sample(judged_scores, threshold, sample_size)

    labels = {}
    if labels_path is not None:
        if not labels_path.is_file():
            raise EnvError("labels_missing", f"--labels file not found: {labels_path}")
        try:
            raw_labels = json.loads(labels_path.read_text())
        except json.JSONDecodeError as exc:
            raise EnvError(
                "labels_malformed_json", f"--labels file is not valid JSON: {labels_path} ({exc})"
            ) from exc
        if not isinstance(raw_labels, dict):
            raise EnvError(
                "labels_malformed",
                "--labels file must be a JSON object mapping case_id -> label",
            )
        labels = parse_labels(raw_labels)

    metrics = compute_audit_metrics(judged_scores, threshold, labels, sample_ids)
    recommendation = recommend_judge_trust(metrics)

    record = {
        "kind": "judge_audit",
        "schema_version": AUDIT_SCHEMA_VERSION,
        "at": _iso_now(),
        "threshold": threshold,
        "sample": [
            {
                "id": cid,
                "judge_score": judged_scores[cid],
                "judge_verdict": _judge_verdict(judged_scores[cid], threshold),
                "human_label": labels.get(cid),
            }
            for cid in sample_ids
        ],
        "metrics": metrics,
        "recommendation": recommendation,
        "recommendation_thresholds": {
            "fail_precision_min": AUDIT_FAIL_PRECISION_MIN,
            "pass_miss_rate_max": AUDIT_PASS_MISS_RATE_MAX,
        },
        "drift_min_sample": AUDIT_DRIFT_MIN_SAMPLE,
    }

    score_mod = _load_score()
    score_mod._fe.write_ledger(eval_dir, record)  # AC5 — append-only, never a composite change
    return record


# ---------------------------------------------------------------------------
# Goal-to-criteria (slice 008-05, ADR-0027) — an authoring ASSIST, never an
# autonomous step (Decision #1). Expands a free-form goal into a *proposed*
# tagged AC set via a fresh one-shot `claude -p` call, runs a SECOND fresh
# `claude -p` independent-reviewer pass (no access to the expansion's own
# reasoning — Decision #2) for advisory STRUCTURAL flags only, and writes the
# result as a spec-shaped Markdown artifact the existing pipeline (015 -> 006
# -> 008-01 triage) consumes unchanged (Decision #4). Neither step is a new
# entry in servo's runner/judge agent roster (ADR-0003 untouched) — both are
# fresh one-shot subprocess calls, mirroring the architect -> jig:architect
# delegation posture, and `score.py::_judge_cli`'s own `claude -p` subprocess
# idiom. Nothing here is frozen without a recorded human per-AC approval
# (Decision #3) and nothing here ever imports/subprocesses `gate.py` or
# `oracle.sh` (Decision #5 / ADR-0021 / ADR-0011 / ADR-0005 boundary).
# ---------------------------------------------------------------------------

GOAL_TO_CRITERIA_SCHEMA_VERSION = 1

TAG_DETERMINISTIC = "deterministic"
TAG_JUDGED = "judged"
TAG_HUMAN_ONLY = "human-only"
VALID_TAGS = (TAG_DETERMINISTIC, TAG_JUDGED, TAG_HUMAN_ONLY)

APPROVAL_PROPOSED = "proposed"

REVIEWER_SOURCE_JIG = "jig"
REVIEWER_SOURCE_BUILT_IN = "built-in"

# Fixed per-invocation wall-clock cap for the two one-shot `claude -p` calls
# (expansion + review) — mirrors `score.py::_judge_cli`'s fixed 300s bound.
# Attended authoring (a human is waiting on the result either way), so no
# separate env-var override knob is offered here (unlike loop.py's unattended
# `SERVO_CLAUDE_TIMEOUT`); a mock claude in tests returns near-instantly.
CLAUDE_PROMPT_TIMEOUT_SECONDS = 300

# The built-in reviewer prompt shipped alongside this skill (AC2's "no hard
# jig dependency" fallback).
_BUILT_IN_REVIEW_PROMPT_PATH = Path(__file__).resolve().parent / "eval-frame-review.md"

# Bound on how much of a detected jig/built-in framing file is spliced into
# the reviewer prompt — generous for a short prompt file, cheap insurance
# against an unexpectedly huge file ballooning the prompt.
_REVIEW_FRAMING_MAX_CHARS = 4000


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_json_object(text: str) -> str:
    """Extract the first `{...}` span from noisy model output (mirrors
    `skills/_common/fidelity_eval.py::_extract_json` — a local copy, not an
    import, per this module's own "cross-skill data is JSON, never a Python
    import" convention, extended here to "cross-*call*", not just
    cross-skill)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise EnvError("claude_unparseable_reply", "no JSON object found in claude's reply")
    return text[start:end + 1]


def _resolve_claude() -> "str | None":
    """The `claude` CLI path: explicit `SERVO_EVAL_AUTHORING_CLAUDE_BIN`
    override, else PATH (mirrors `score.py::_resolve_claude` exactly — same
    env var name, so a test — or an operator — can point both halves of this
    one skill at the same mock/alternate binary without PATH surgery)."""
    return os.environ.get("SERVO_EVAL_AUTHORING_CLAUDE_BIN") or shutil.which("claude")


def _invoke_claude_prompt(prompt: str) -> str:
    """One fresh, one-shot `claude -p --output-format json <prompt>` call —
    used for BOTH the expansion step (AC1) and the independent-reviewer step
    (AC2). Deliberately NOT `--agent <name>`: ADR-0027 Decision #2 is explicit
    that goal->eval's reviewer is a fresh one-shot subprocess call, not a new
    entry in servo's runner/judge agent roster (ADR-0003's loop roster stays
    untouched) — mirrors the architect -> jig:architect delegation posture,
    and mirrors `score.py::_judge_cli`'s own subprocess idiom almost exactly.

    Returns the envelope's `result` text on success. Raises `EnvError` on any
    failure: claude not resolvable (PATH or `SERVO_EVAL_AUTHORING_CLAUDE_BIN`),
    a timeout, a non-zero exit, an unparseable envelope, or `is_error: true` in
    the envelope — never a silent or fabricated reply (ADR-0005's honesty
    posture, extended to authoring-time).
    """
    claude = _resolve_claude()
    if not claude:
        raise EnvError(
            "claude_not_found",
            "claude CLI not found — set SERVO_EVAL_AUTHORING_CLAUDE_BIN or add it to PATH",
        )
    cmd = [claude, "-p", "--output-format", "json", prompt]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=CLAUDE_PROMPT_TIMEOUT_SECONDS)
    except FileNotFoundError as exc:
        raise EnvError("claude_not_found", f"claude CLI not found on PATH: {exc}") from exc
    except subprocess.TimeoutExpired:
        raise EnvError(
            "claude_timeout",
            f"claude -p timed out after {CLAUDE_PROMPT_TIMEOUT_SECONDS}s",
        ) from None
    if proc.returncode != 0:
        raise EnvError(
            "claude_invocation_failed",
            f"claude -p exited {proc.returncode}: {proc.stderr.strip()[:300]}",
        )
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise EnvError(
            "claude_malformed_envelope", f"claude -p output is not valid JSON: {exc}"
        ) from exc
    if not isinstance(envelope, dict):
        raise EnvError("claude_malformed_envelope", "claude -p output is not a JSON object")
    if envelope.get("is_error"):
        raise EnvError(
            "claude_invocation_failed",
            f"claude -p reported an error: {str(envelope.get('result'))[:300]}",
        )
    return str(envelope.get("result", ""))


# --- expansion (AC1) --------------------------------------------------------

_EXPANSION_PROMPT_TEMPLATE = """\
You are expanding a free-form goal into a PROPOSED set of acceptance criteria \
for evaluation-driven development. This is a proposal only — a human will \
edit, accept, reject, and add to it; you are not authoring a frozen contract.

GOAL:
{goal}

For each acceptance criterion you propose, tag it with EXACTLY ONE of:
- "deterministic" — a cheap, mechanical, code-checkable predicate (e.g. a \
byte count, a regex match, a schema check).
- "judged" — needs an LLM/human judge against a rubric (a quality/\
faithfulness call that is not cheaply mechanical, but IS still \
operationalizable into a scored rubric).
- "human-only" — an irreducibly human taste/policy/sign-off call (e.g. \
"requires a senior editor's approval") that no rubric can score.

Be honest about the tag: do NOT tag a taste/policy call as "deterministic" \
or "judged" just because it sounds important — a criterion whose own \
wording is a subjective/taste/policy call belongs in "human-only" \
regardless of how it is phrased.

Reply with ONLY a JSON object, no other text, in this exact shape:
{{"acs": [{{"statement": "<one clear, operational criterion>", \
"tag": "deterministic|judged|human-only", \
"rationale": "<one line: why this tag>"}}, ...]}}
"""


def _render_expansion_prompt(goal: str) -> str:
    return _EXPANSION_PROMPT_TEMPLATE.format(goal=goal)


def _parse_expansion_reply(text: str) -> list:
    """Parse the expansion model's reply into a list of proposed AC dicts:
    `{"statement": str, "tag": deterministic|judged|human-only, "rationale":
    str}`. Raises `EnvError` on any malformed shape — never fabricates a
    criterion from unparseable model output (AC1)."""
    try:
        obj = json.loads(_extract_json_object(text))
    except (json.JSONDecodeError, EnvError) as exc:
        raise EnvError(
            "expansion_unparseable", f"could not parse the expansion reply: {exc}"
        ) from exc
    acs = obj.get("acs") if isinstance(obj, dict) else None
    if not isinstance(acs, list) or not acs:
        raise EnvError("expansion_empty", "the expansion reply carried no acceptance criteria")
    parsed = []
    for i, entry in enumerate(acs):
        if not isinstance(entry, dict):
            raise EnvError("expansion_malformed_entry", f"acs[{i}] is not an object")
        statement = entry.get("statement")
        tag = entry.get("tag")
        if not isinstance(statement, str) or not statement.strip():
            raise EnvError(
                "expansion_malformed_entry", f"acs[{i}] is missing a non-empty statement")
        if tag not in VALID_TAGS:
            raise EnvError(
                "expansion_malformed_entry",
                f"acs[{i}].tag {tag!r} is not one of {VALID_TAGS}",
            )
        parsed.append({
            "statement": statement.strip(),
            "tag": tag,
            "rationale": str(entry.get("rationale", "")).strip(),
        })
    return parsed


# --- independent review (AC2) -----------------------------------------------

def _jig_independent_review_skill_path() -> "Path | None":
    """Filesystem-hint probe (ADR-0001 / ADR-0027 Decision #2): is jig's
    `independent-review` skill installed at USER scope? Mirrors jig's own
    `review.py::detect_richer_skill` convention exactly — a user-scope
    `~/.claude/skills/independent-review/SKILL.md` — so the same
    `Path.home()` call (which honors `$HOME`) keeps this hermetically
    testable without a real jig install. Returns the `SKILL.md` path when
    present, else `None`. Conservative on every error (OSError/ValueError/
    RuntimeError -> None): the built-in prompt is always a safe fallback,
    never a hard failure — servo does not hard-depend on jig.
    """
    try:
        candidate = Path.home() / ".claude" / "skills" / "independent-review" / "SKILL.md"
        if candidate.is_file():
            return candidate
    except (OSError, ValueError, RuntimeError):
        pass
    return None


def _review_framing_text(jig_skill_path) -> str:
    """The reviewer prompt's framing preamble: jig's detected skill file's
    own content when co-installed, else the built-in `eval-frame-review.md`
    shipped with this skill (AC2). Falls back to the built-in text on any
    read failure of a *detected* jig file (belt-and-braces — detection
    already checked `is_file()`, but a race/permissions error should still
    degrade to the always-available built-in, never crash the review step).
    """
    if jig_skill_path is not None:
        try:
            return jig_skill_path.read_text()[:_REVIEW_FRAMING_MAX_CHARS]
        except OSError:
            pass
    return _BUILT_IN_REVIEW_PROMPT_PATH.read_text()[:_REVIEW_FRAMING_MAX_CHARS]


def _render_review_prompt(goal: str, acs: list, *, jig_skill_path) -> str:
    """AC2: the independent-reviewer prompt. Carries ONLY the goal text and
    the proposed AC list — never the expansion call's own reasoning/
    chain-of-thought — so the reviewer's independence is a fresh, separate
    subprocess call, not a continuation of the expansion's context."""
    ac_lines = "\n".join(
        f'{i}. [{ac["tag"]}] {ac["statement"]}' for i, ac in enumerate(acs, start=1)
    )
    framing = _review_framing_text(jig_skill_path)
    return f"""{framing}

GOAL (verbatim, as given to the expansion step):
{goal}

PROPOSED ACCEPTANCE CRITERIA (you do NOT have access to the reasoning that \
produced these — only the goal text and this list):
{ac_lines}

Reply with ONLY a JSON object, no other text, in this exact shape:
{{"flags": [{{"ac_index": <1-based index into the list above, or null if \
not tied to one AC>, "kind": "mis_tagged|unmeasurable|goal_restatement|\
coverage_gap", "note": "<one or two sentences>"}}, ...]}}
If you find nothing to flag, reply with {{"flags": []}}.
"""


def _parse_review_reply(text: str) -> list:
    """Parse the reviewer's reply into a list of flag dicts: `{"ac_index":
    int|None, "kind": str, "note": str}`. Raises `EnvError` on a malformed
    shape (AC2: advisory flags, never a silently-dropped or fabricated
    review)."""
    try:
        obj = json.loads(_extract_json_object(text))
    except (json.JSONDecodeError, EnvError) as exc:
        raise EnvError(
            "review_unparseable", f"could not parse the reviewer reply: {exc}"
        ) from exc
    flags = obj.get("flags") if isinstance(obj, dict) else None
    if not isinstance(flags, list):
        raise EnvError("review_malformed", "reviewer reply carried no 'flags' list")
    parsed = []
    for i, entry in enumerate(flags):
        if not isinstance(entry, dict):
            raise EnvError("review_malformed_entry", f"flags[{i}] is not an object")
        parsed.append({
            "ac_index": entry.get("ac_index"),
            "kind": entry.get("kind"),
            "note": str(entry.get("note", "")),
        })
    return parsed


# --- curated artifact (AC3 / AC4) -------------------------------------------

def build_criteria_payload(goal: str, acs: list, flags: list, *, reviewer_source: str) -> dict:
    """Assemble the `criteria.json` payload (AC3/AC4): one entry per proposed
    AC, each carrying its tag/rationale/reviewer flags and an
    `approval_status` that ALWAYS starts `"proposed"` — this function never
    writes `"approved"` (mirrors triage's own `confirmed: False` default;
    AC3's "nothing is frozen without recorded human approval"). A flag whose
    `ac_index` is missing/out-of-range/non-integer is not dropped — it is
    kept as an `unassigned_reviewer_flags` entry (schema-drift-tolerant, AC2:
    an advisory flag the reviewer couldn't or didn't tie to one AC is still
    surfaced to the human, never silently discarded).
    """
    entries = []
    for i, ac in enumerate(acs, start=1):
        entries.append({
            "id": f"AC-{i}",
            "statement": ac["statement"],
            "tag": ac["tag"],
            "rationale": ac["rationale"],
            "reviewer_flags": [],
            "approval_status": APPROVAL_PROPOSED,
        })
    unassigned = []
    for f in flags:
        idx = f.get("ac_index")
        if isinstance(idx, int) and not isinstance(idx, bool) and 1 <= idx <= len(entries):
            entries[idx - 1]["reviewer_flags"].append(
                {"kind": f.get("kind"), "note": f.get("note", "")})
        else:
            unassigned.append({"kind": f.get("kind"), "note": f.get("note", "")})
    return {
        "schema_version": GOAL_TO_CRITERIA_SCHEMA_VERSION,
        "goal": goal,
        "generated_at": _iso_now(),
        "reviewer_source": reviewer_source,
        "acs": entries,
        "unassigned_reviewer_flags": unassigned,
    }


def require_all_approved(payload: dict) -> None:
    """The human-curation gate (AC3/AC7), made callable/testable directly:
    raises `EnvError` unless every AC in `payload["acs"]` carries
    `approval_status == "approved"`. `from-goal` itself never calls this —
    it only ever emits `"proposed"` entries — so this exists as the explicit,
    assertable gate a human (or a future promotion step) must clear before an
    un-curated, goal-derived AC set could be treated as curated. Mirrors
    008-04's `freeze_dataset_config` refusing an unapproved rubric config,
    one stage earlier in the pipeline.

    The no-freeze-without-approval guarantee is deliberately **procedural**,
    not enforced by any oracle/gate machinery (ADR-0027 Decision #5: "its
    teeth are procedural — no freeze without human approval"). This function
    — and the `criteria-check` CLI subcommand that wraps it (below) — is the
    explicit, human-invokable point where that procedure is actually
    checked; nothing calls it automatically on `from-goal`'s own path.
    """
    unapproved = [e["id"] for e in payload.get("acs", []) if e.get("approval_status") != "approved"]
    if unapproved:
        raise EnvError(
            "criteria_not_approved",
            f"{len(unapproved)} acceptance criterion/criteria not yet approved "
            f"({', '.join(unapproved)}) — curate (edit/accept/reject/add) and record "
            "per-AC approval before treating this proposal as curated",
        )


def criteria_check(criteria_md_path: Path) -> dict:
    """The `criteria-check` command's logic: the explicit, human-invokable
    checkpoint for `require_all_approved` (AC3/ADR-0027 Decision #5) — wires
    that gate into a CLI a human actually runs, rather than leaving it a
    library function nothing on any path calls.

    Reads the sibling `criteria.json` a `from-goal` run wrote beside
    `criteria_md_path` (same directory — `from_goal_target` always writes
    both files together), and reports each AC's `id` + `approval_status`
    alongside whether `require_all_approved` would pass. Raises `EnvError` on
    a missing `criteria_md_path`, a missing sibling `criteria.json`, or
    malformed JSON — never on "not yet approved", which is a normal,
    reportable outcome (the CLI maps it to a non-zero exit, not a crash).

    Returns `{"all_approved": bool, "acs": [{"id": str, "approval_status":
    str}, ...]}`.
    """
    if not criteria_md_path.is_file():
        raise EnvError(
            "criteria_missing", f"criteria artifact not found: {criteria_md_path}")
    criteria_json_path = criteria_md_path.parent / "criteria.json"
    if not criteria_json_path.is_file():
        raise EnvError(
            "criteria_json_missing",
            f"no sibling criteria.json at {criteria_json_path} — run `from-goal` first",
        )
    try:
        payload = json.loads(criteria_json_path.read_text())
    except json.JSONDecodeError as exc:
        raise EnvError(
            "criteria_json_malformed",
            f"criteria.json is not valid JSON: {criteria_json_path} ({exc})",
        ) from exc

    statuses = [
        {"id": e.get("id"), "approval_status": e.get("approval_status")}
        for e in payload.get("acs", [])
    ]
    try:
        require_all_approved(payload)
        all_approved = True
    except EnvError:
        all_approved = False
    return {"all_approved": all_approved, "acs": statuses}


def _render_criteria_md(payload: dict) -> str:
    """Render `criteria.md` (AC4): frontmatter + a human-curation surface +
    a plain `## Acceptance criteria` numbered list that `spec-oracle
    classify` (006) — and, via it, `edd-suitability` (015) — parses
    unchanged, exactly like a hand-written spec's AC section. The tag /
    rationale / reviewer-flags / approval-status metadata lives in a
    SEPARATE table above that section (never mixed into a numbered item's
    text), so `oracle_plan.extract_acs`'s statement text is the clean
    criterion only (AC4's round-trip)."""
    acs = payload["acs"]
    lines = [
        "---",
        f"goal: {payload['goal']!r}",
        f"generated_at: {payload['generated_at']}",
        f"reviewer_source: {payload['reviewer_source']}",
        "---",
        "",
        "# Goal-to-criteria proposal",
        "",
        "## Goal",
        "",
        payload["goal"],
        "",
        "> **This is a proposal, not a decision (ADR-0027).** Every "
        "acceptance criterion below — including its "
        "`deterministic|judged|human-only` tag — is a starting point from an "
        "LLM expansion, checked by a fresh independent-reviewer subagent for "
        "STRUCTURAL issues only (mis-tagging by wording, unmeasurable "
        "predicates, goal-restatement, surface-literal coverage gaps). The "
        "reviewer's flags are advisory, not a verdict — it does NOT reliably "
        "catch a plausible-but-unfaithful criterion or an *implicit* "
        "coverage gap (a requirement the goal only implies). That is YOUR "
        "job: edit / accept / reject / **add** each criterion below. You may "
        "add a criterion the expansion omitted entirely — there is no row to "
        "reject for something that was never proposed, so adding is how you "
        "backstop coverage of intent. **Nothing is frozen until you record a "
        "per-AC approval** (flip `approval_status` to `\"approved\"` in "
        "`criteria.json` once you agree) — the `## Acceptance criteria` "
        "section below feeds `spec-oracle classify` (006) and "
        "`edd-suitability` (015) exactly like a hand-written spec's AC "
        "section. **Once every AC above is approved, run** "
        "`eval_authoring.py criteria-check criteria.md` **before proceeding** "
        "— it reports each AC's approval status and exits non-zero until "
        "every one reads `approved`.",
        "",
        "## Proposed classification & reviewer flags",
        "",
    ]
    if acs:
        lines.append("| Approve | # | Tag | Statement | Rationale | Reviewer flags |")
        lines.append("|---|---|---|---|---|---|")
        for e in acs:
            statement = e["statement"].replace("|", "&#124;")
            rationale = e["rationale"].replace("|", "&#124;")
            flags_text = "; ".join(
                f'{f.get("kind")}: {f.get("note", "")}' for f in e["reviewer_flags"]
            ).replace("|", "&#124;") or "-"
            lines.append(
                f'| [ ] | {e["id"]} | `{e["tag"]}` | {statement} | {rationale} | {flags_text} |'
            )
    else:
        lines.append("_No acceptance criteria proposed._")
    if payload["unassigned_reviewer_flags"]:
        lines += ["", "## Reviewer flags not tied to a single AC", ""]
        for f in payload["unassigned_reviewer_flags"]:
            note = str(f.get("note", "")).replace("|", "&#124;")
            lines.append(f'- {f.get("kind")}: {note}')
    lines += [
        "",
        "## Acceptance criteria",
        "",
    ]
    if acs:
        for i, e in enumerate(acs, start=1):
            lines.append(f'{i}. {e["statement"]}')
    else:
        lines.append("_No acceptance criteria proposed._")
    lines.append("")
    return "\n".join(lines)


def _goal_slug(goal: str) -> str:
    """The `<goal-slug>` directory name (AC4): `_slug`'s lowercase/underscore
    collapse, truncated so a long free-form goal doesn't produce an
    unreasonably long directory name."""
    return _slug(goal)[:60].rstrip("_") or "goal"


def criteria_dir_for_goal(spec_dir: Path, goal_slug: str) -> Path:
    """Where `from-goal`'s artifacts live (AC4, ADR-0023 colocation):
    `<spec_dir>/<goal_slug>/`. This directory plays the role a hand-written
    spec's own directory plays for `spec.md` — `criteria.md` sits directly
    inside it, so a later `oracle_plan.py classify <criteria.md>` /
    `eval_dir_for_spec(this_dir, goal_slug)` call resolves with zero special
    casing (AC6's opt-in boundary: the curated artifact re-enters the SAME
    pipeline a hand-written spec.md would, at 008-01 triage)."""
    _validate_spec_id(goal_slug)
    return spec_dir / goal_slug


def from_goal_target(goal: str, spec_dir: Path, *, force: bool = False) -> tuple:
    """AC1-AC4: expand the goal -> run the independent-reviewer pass -> emit
    the curated-pending proposal under `<spec_dir>/<goal-slug>/`. Never
    imports or subprocesses `gate.py`/`oracle.sh` (AC6/Decision #5) — the two
    `claude -p` calls and a Markdown/JSON write are the entire side effect.

    Refuses (`EnvError`) when `criteria.md` or `criteria.json` already exist
    for this goal — a re-run's fresh, non-deterministic LLM output must never
    silently clobber an already-curated artifact (a human may have edited
    `criteria.md`'s AC text, or recorded per-AC approvals in
    `criteria.json` — exactly the human curation AC3 exists to protect).
    Mirrors `dataset_target`'s own never-overwrite posture for its
    human-grown `cases` (008-03), applied one step earlier in the pipeline.
    The check runs BEFORE either `claude -p` call, so a refused re-run costs
    nothing. Pass `force=True` to regenerate deliberately, discarding
    whatever curation was already recorded.

    Returns `(payload, out_dir)`.
    """
    out_dir = criteria_dir_for_goal(spec_dir, _goal_slug(goal))
    if not force:
        for existing in (out_dir / "criteria.md", out_dir / "criteria.json"):
            if existing.is_file():
                raise EnvError(
                    "criteria_exists",
                    f"{existing} already exists — from-goal refuses to overwrite a "
                    "possibly human-curated artifact (edits recorded in criteria.md, "
                    "approvals recorded in criteria.json); pass --force to regenerate "
                    "deliberately",
                )

    expansion_text = _invoke_claude_prompt(_render_expansion_prompt(goal))
    acs = _parse_expansion_reply(expansion_text)

    jig_skill_path = _jig_independent_review_skill_path()
    review_prompt = _render_review_prompt(goal, acs, jig_skill_path=jig_skill_path)
    review_text = _invoke_claude_prompt(review_prompt)
    flags = _parse_review_reply(review_text)

    reviewer_source = (
        REVIEWER_SOURCE_JIG if jig_skill_path is not None else REVIEWER_SOURCE_BUILT_IN)
    payload = build_criteria_payload(goal, acs, flags, reviewer_source=reviewer_source)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "criteria.json").write_text(json.dumps(payload, indent=2) + "\n")
    (out_dir / "criteria.md").write_text(_render_criteria_md(payload))
    return payload, out_dir


# --- criteria split (AC5) ----------------------------------------------------

# spec-006's classifier lives at this fixed sibling-skill path (mirrors
# `skills/edd-suitability/suitability.py`'s own `DEFAULT_ORACLE_PLAN`).
ORACLE_PLAN_PATH = Path(__file__).resolve().parent.parent / "spec-oracle" / "oracle_plan.py"


def criteria_split(criteria_md_path: Path) -> dict:
    """AC5: run ONLY 015's criteria-classification half over an emitted
    artifact — the evaluable-vs-human-residual split — NOT edd-suitability's
    full `suitable | needs_evidence | unsuitable` verdict (ADR-0027 Decision
    #4 / ADR-0018): at goal-expansion time there is no target signal or
    reference set yet, so a full verdict would resolve `needs_evidence`
    across the board, uselessly. Subprocesses `oracle_plan.py classify`
    exactly as `suitability.py::_classify` does internally — the SAME half
    015 itself consumes, not a second, diverging classifier — and never
    calls `suitability.py`'s `decide`/`analyze` (no verdict is produced, and
    no `.servo/suitability/*.json` artifact is written).
    """
    if not criteria_md_path.is_file():
        raise EnvError(
            "criteria_missing", f"criteria artifact not found: {criteria_md_path}")
    cmd = [sys.executable, str(ORACLE_PLAN_PATH), "classify", str(criteria_md_path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as exc:
        raise EnvError(
            "oracle_plan_unreadable", f"could not run oracle_plan classify: {exc}"
        ) from exc
    if proc.returncode != 0:
        raise EnvError(
            "oracle_plan_unreadable",
            f"oracle_plan classify exited {proc.returncode}: {proc.stderr.strip()}",
        )
    try:
        plan = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise EnvError(
            "oracle_plan_unreadable",
            f"oracle_plan classify emitted unparseable output: {exc}",
        ) from exc
    if not isinstance(plan, dict) or "checks" not in plan or "residual_judgment" not in plan:
        raise EnvError(
            "oracle_plan_unreadable",
            "oracle_plan classify output missing checks / residual_judgment",
        )
    checks = plan.get("checks") or []
    residual = plan.get("residual_judgment") or []
    return {
        "spec_id": plan.get("spec_id"),
        "n_evaluable": len(checks),
        "n_human_residual": len(residual),
        "evaluable_ac_ids": [c.get("id") for c in checks],
        "human_residual_ac_ids": [r.get("id") for r in residual],
    }


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


def _params_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_authoring.py params",
        description=(
            "Set/confirm the frozen n/delta/threshold/judge params for one "
            "AC's config.json, with a one-line trade-off note per knob."
        ),
    )
    parser.add_argument(
        "plan_path", metavar="plan",
        help="Path to the same spec-006 checks.json plan passed to `rubric`.",
    )
    parser.add_argument("--ac", required=True, help="The AC id to set params for.")
    parser.add_argument("--n", type=int, default=None, help="Judge samples per case.")
    parser.add_argument("--delta", type=float, default=None, help="Noise-floor delta.")
    parser.add_argument("--threshold", type=float, default=None, help="Pass/fail threshold.")
    parser.add_argument("--model", default=None, help="Judge model.")
    parser.add_argument("--temperature", type=float, default=None, help="Judge temperature.")
    parser.add_argument(
        "--max-tokens", type=int, default=None, dest="max_tokens", help="Judge max_tokens.")
    parser.add_argument(
        "--transport", choices=("api", "cli"), default=None, help="Judge transport.")
    args = parser.parse_args(argv)

    plan_path = Path(args.plan_path).resolve()
    try:
        config, out_dir = params_target(
            plan_path, args.ac, n=args.n, delta=args.delta, threshold=args.threshold,
            model=args.model, temperature=args.temperature, max_tokens=args.max_tokens,
            transport=args.transport,
        )
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"servo: params set for {args.ac} -> {out_dir}")
    for line in render_params_guidance(config):
        print(line)
    return 0


def _emit_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_authoring.py emit",
        description=(
            "Freeze the AC's config.json (the human-approval gate) and, when "
            "--target is given, install the resulting score_<name> component."
        ),
    )
    parser.add_argument(
        "plan_path", metavar="plan",
        help="Path to the same spec-006 checks.json plan passed to `rubric`/`dataset`.",
    )
    parser.add_argument("--ac", required=True, help="The AC id to emit.")
    parser.add_argument(
        "--target", default=None,
        help="Optional project root to install the component into.",
    )
    parser.add_argument(
        "--weight", type=float, default=1.0,
        help="Weight for the installed component's oracle.sh entry.",
    )
    args = parser.parse_args(argv)

    plan_path = Path(args.plan_path).resolve()
    target = Path(args.target).resolve() if args.target else None
    try:
        _config, out_dir, component, installed = emit_target(
            plan_path, args.ac, target=target, weight=args.weight)
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"servo: emitted {args.ac} as score_{component} (approved) -> {out_dir}")
    if installed:
        print(f"servo: installed score_{component} into {target}")
    return 0


def _uninstall_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_authoring.py uninstall",
        description="Remove a previously-installed score_<name> component from a target.",
    )
    parser.add_argument(
        "plan_path", metavar="plan",
        help="Path to the same spec-006 checks.json plan passed to `emit`.",
    )
    parser.add_argument("--ac", required=True, help="The AC id whose component to remove.")
    parser.add_argument("--target", required=True, help="Project root to remove it from.")
    args = parser.parse_args(argv)

    plan_path = Path(args.plan_path).resolve()
    target = Path(args.target).resolve()
    try:
        component = uninstall_target(plan_path, args.ac, target)
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"servo: uninstalled score_{component} from {target}")
    return 0


def _from_goal_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_authoring.py from-goal",
        description=(
            "Expand a free-form goal into a PROPOSED, tagged acceptance-criteria "
            "set (ADR-0027) -- an authoring assist, never a frozen artifact."
        ),
    )
    parser.add_argument("goal", help="The free-form goal to expand.")
    parser.add_argument(
        "--spec-dir", default=".",
        help=(
            "Directory under which the goal's own <goal-slug>/ artifact "
            "directory is created (default: cwd)."
        ),
    )
    parser.add_argument(
        "--force", action="store_true",
        help=(
            "Regenerate even if criteria.md/criteria.json already exist for this "
            "goal, discarding any human curation already recorded (default: refuse)."
        ),
    )
    args = parser.parse_args(argv)

    spec_dir = Path(args.spec_dir).resolve()
    try:
        payload, out_dir = from_goal_target(args.goal, spec_dir, force=args.force)
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    n_acs = len(payload["acs"])
    n_flags = (
        sum(len(e["reviewer_flags"]) for e in payload["acs"])
        + len(payload["unassigned_reviewer_flags"])
    )
    print(
        f"servo: proposed {n_acs} acceptance criterion(s) from a goal "
        f"({n_flags} reviewer flag(s), reviewer={payload['reviewer_source']}) -> {out_dir}"
    )
    print(
        "servo: PROPOSAL ONLY -- edit/accept/reject/add each AC in criteria.md and "
        "record per-AC approval in criteria.json before treating this as curated"
    )
    return 0


def _criteria_check_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_authoring.py criteria-check",
        description=(
            "Report per-AC approval status for a from-goal criteria.md, and check "
            "whether every AC has recorded human approval (the AC3 human-curation gate, "
            "ADR-0027 Decision #5)."
        ),
    )
    parser.add_argument("criteria_md", help="Path to a from-goal criteria.md.")
    args = parser.parse_args(argv)

    criteria_md_path = Path(args.criteria_md).resolve()
    try:
        report = criteria_check(criteria_md_path)
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for entry in report["acs"]:
        marker = "approved" if entry["approval_status"] == "approved" else "NOT approved"
        print(f"servo: {entry['id']}: {marker}")
    if report["all_approved"]:
        print("servo: every AC approved -- safe to treat this proposal as curated")
        return 0
    print(
        "error: not every AC is approved yet -- curate criteria.md and record per-AC "
        "approval in criteria.json before treating this proposal as curated",
        file=sys.stderr,
    )
    return 1


def _criteria_split_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_authoring.py criteria-split",
        description=(
            "Run only edd-suitability's criteria-classification half (evaluable vs "
            "human-residual) over a spec-shaped AC artifact -- not a full verdict."
        ),
    )
    parser.add_argument(
        "criteria_md", help="Path to a from-goal criteria.md (or any spec-shaped AC artifact).")
    args = parser.parse_args(argv)

    criteria_md_path = Path(args.criteria_md).resolve()
    try:
        split = criteria_split(criteria_md_path)
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    total = split["n_evaluable"] + split["n_human_residual"]
    print(
        f"servo: {split['n_evaluable']} evaluable, {split['n_human_residual']} "
        f"human-residual of {total} acceptance criteria (criteria split only -- "
        "NOT a full suitability verdict; see ADR-0027/ADR-0018)"
    )
    return 0


def _audit_main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_authoring.py audit",
        description=(
            "Advisory judge-trust audit: sample judged cases for human spot-checking, "
            "compute agreement metrics, and recommend auto vs confirmed-only. Reports and "
            "recommends only -- never alters the composite, config.json, or oracle.sh/gate.py."
        ),
    )
    parser.add_argument(
        "eval_dir", metavar="eval",
        help="Path to the eval directory (holds config.json and, once scored, ledger.jsonl).",
    )
    parser.add_argument(
        "--labels", default=None,
        help=(
            "Path to a JSON file mapping case_id -> human verdict ('pass'/'fail', or an "
            "object {'verdict':..., 'score':...} carrying an optional numeric human score "
            "for drift)."
        ),
    )
    parser.add_argument(
        "--scores", default=None,
        help=(
            "Optional override: a JSON file mapping case_id -> judged score, in place of "
            "reading the most recent ledger.jsonl scoring run."
        ),
    )
    parser.add_argument(
        "--sample-size", type=int, default=None, dest="sample_size",
        help="Cap the mixed pass/fail sample size (default: every judged case is eligible).",
    )
    args = parser.parse_args(argv)

    eval_dir = Path(args.eval_dir).resolve()
    labels_path = Path(args.labels).resolve() if args.labels else None
    scores_path = Path(args.scores).resolve() if args.scores else None
    try:
        record = audit_target(
            eval_dir, labels_path=labels_path, scores_path=scores_path,
            sample_size=args.sample_size,
        )
    except EnvError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    metrics = record["metrics"]
    print(
        f"servo: judge audit over {len(record['sample'])} sampled case(s), "
        f"{metrics['n_labeled']} labeled -> {eval_dir / 'ledger.jsonl'}"
    )
    fp_text = (
        f"{metrics['fail_precision']:.2f}" if metrics["fail_precision"] is not None
        else metrics["fail_precision_note"]
    )
    pmr_text = (
        f"{metrics['pass_miss_rate']:.2f}" if metrics["pass_miss_rate"] is not None
        else metrics["pass_miss_note"]
    )
    print(f"servo: fail-precision = {fp_text} (provisional threshold: >= "
          f"{AUDIT_FAIL_PRECISION_MIN})")
    print(f"servo: pass-miss-rate = {pmr_text} (provisional threshold: <= "
          f"{AUDIT_PASS_MISS_RATE_MAX})")
    if metrics["drift"] is not None:
        print(f"servo: score-vs-human drift = {metrics['drift']:.4f} (n={metrics['drift_n']})")
    else:
        print(f"servo: score-vs-human drift = {metrics['drift_note']}")
    print(
        f"servo: recommendation = {record['recommendation']} (advisory only -- does not gate "
        "the composite; see docs/refinement-todo.md 'Judge-audit -> composite gating')"
    )
    return 0


def main(argv: list | None = None) -> int:
    # Hand-rolled subcommand dispatch (mirrors `oracle_plan.py` / `gate.py`).
    # `triage` (008-01), `rubric` (008-02), `dataset` (008-03),
    # `params`/`emit`/`uninstall` (008-04),
    # `from-goal`/`criteria-check`/`criteria-split` (008-05), and `audit`
    # (008-06) make up the full guided-skill surface.
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "triage":
        return _triage_main(argv[1:])
    if argv and argv[0] == "rubric":
        return _rubric_main(argv[1:])
    if argv and argv[0] == "dataset":
        return _dataset_main(argv[1:])
    if argv and argv[0] == "params":
        return _params_main(argv[1:])
    if argv and argv[0] == "emit":
        return _emit_main(argv[1:])
    if argv and argv[0] == "uninstall":
        return _uninstall_main(argv[1:])
    if argv and argv[0] == "from-goal":
        return _from_goal_main(argv[1:])
    if argv and argv[0] == "criteria-check":
        return _criteria_check_main(argv[1:])
    if argv and argv[0] == "criteria-split":
        return _criteria_split_main(argv[1:])
    if argv and argv[0] == "audit":
        return _audit_main(argv[1:])
    print(
        "error: unknown or missing subcommand (expected: triage, rubric, dataset, params, "
        "emit, uninstall, from-goal, criteria-check, criteria-split, audit)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
