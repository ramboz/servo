#!/usr/bin/env python3
"""Generic judge-scorer core for a servo-authored eval component
(`/servo:eval-authoring`, slices 008-02/008-03/008-04).

Grows across 008-02 -> 008-04:
- **008-02** shipped the **judge path** — turn a rubric plus one candidate
  string into a judge call, and parse its reply into the richer structured
  output `{score, reasoning, strengths, weaknesses}` this generic surface
  targets (a broader schema than `content-fidelity/score.py`'s `{score,
  reasoning}` — AC2).
- **008-03** added the **dataset composite**, `score()`: iterate
  `config["cases"]` (excluding `skip_case`, which is out of the denominator
  entirely), aggregate each scored case's `n` judged samples to a
  conservative lower bound (`aggregate_lower_bound`, shared with
  `content-fidelity`), gate that lower bound by any per-case
  `expected_output.constraints` via the DSL (`evaluate_constraint` —
  AC2's "cheap deterministic sub-checks alongside the judged score"), and
  combine the per-case scores into one weighted composite in `[0,1]`.
  Composition rule: a **failed hard constraint zeroes that case's
  contribution** (multiplies its lower bound by `0.0`); a rubric-only case
  (no `expected_output`) has no constraints to gate on and is judged by the
  rubric alone.
- **008-04** (this slice) wires in the freeze enforcement 008-03 left open:
  `score()` now calls `validate_freeze` first, so a change to the rubric /
  dataset / model / n / delta / threshold since the last `eval_authoring.py
  emit` refuses as `StaleError` (exit 2), never a silent score (AC5).
  It also: guards the per-case `weight` parse (a hand-edited non-numeric
  weight now raises this module's own clean `EnvError`, not a bare
  `ValueError` — an 008-03 carry-forward); vendors the constraint DSL
  (`parse_constraint`/`evaluate_constraint`) as a local copy instead of
  importing `eval_authoring.py` (another 008-03 carry-forward — see the
  "Constraint DSL" section below for why); and adds `main()` so this file
  runs standalone as the `score_<name>` oracle.sh component
  `eval_authoring.py install_component` splices in (mirrors
  `content-fidelity/score.py::main()` exactly).

  Still a documented, deliberately-unbuilt seam (out of this slice's scope
  — see the spec's non-goals): the real candidate-gather (running the
  system under test on a case's `input` to produce the text `judge()`
  scores — see `_gather_candidate` below) and the real per-candidate
  `actual_values` extraction the constraint DSL compares against (see
  `_case_constraint_score` below). Both raise `EnvError` today rather than
  fabricating a candidate/actual, which is why a *live* (no-fake-scores)
  `score()` call always ends in `env_error`, never a placeholder score. The
  comparative archetype's PROPOSED-vs-BASELINE judging (the `baseline`
  per-case field 008-02/008-03 already carry in the case shape) is the same
  kind of seam: widening `judge()`'s signature to consume it is deferred
  until a real candidate-gather exists to feed it — half-wiring it now
  would add a signature nobody can drive yet.

Honesty (servo ADR-0005): a malformed/unparseable/unreachable judge reply,
a missing judged sample, a stale/unapproved definition, or a case with
constraints but no actual values to evaluate them against, all raise
`EnvError`/`StaleError` — **never a silent 0.0** (mirrors content-fidelity's
own contract exactly; see AC2/AC5/AC6 and this module's tests in
`test_eval_authoring.py`).

Reuses `skills/_common/fidelity_eval.py` (ADR-0024) for `_extract_json` /
`_post_with_retry` / `EnvError` / the freeze+hash primitives, so a rubric
authored here slots into the exact shape the harness already hashes/freezes
(AC5) — no reshaping when `eval_authoring.py`'s `emit` freezes it.

Python 3.9+ standard library only (servo constraint, ADR-0020).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time  # noqa: F401 — re-exposed as `score.time` for test monkeypatching (see _post_with_retry)
import urllib.error
import urllib.request
from pathlib import Path

EXIT_OK = 0
EXIT_ENV_ERROR = 2  # -> oracle.sh treats rc=2 as a missing component -> gate env_error

# Offline-test hooks for the composite scorer below (mirror content-fidelity's
# own `_FAKE_SCORES_ENV` idiom exactly): `_FAKE_SCORES_ENV` maps a case id to
# its list of `n` judged samples, bypassing the real judge call entirely;
# `_FAKE_ACTUALS_ENV` maps a case id to the `actual_values` dict the
# constraint DSL evaluates against, standing in for 008-04's real
# candidate-gather + actual-value extraction (see `_gather_candidate` /
# `_case_constraint_score`). 008-02's own tests monkeypatch `_post_with_retry`
# directly instead, since they exercise `judge()` in isolation, not the
# composite.
_FAKE_SCORES_ENV = "SERVO_EVAL_AUTHORING_FAKE_SCORES"
_FAKE_ACTUALS_ENV = "SERVO_EVAL_AUTHORING_FAKE_ACTUALS"

# The case shape (008-03, `eval_authoring.py::validate_case`):
# `{id, category, scenario, input, expected_output?: {description,
# constraints?}, baseline?}`. Every field the freeze cares about — including
# `scenario` — is pinned **by value** into the definition hash — a changed
# `input`, a re-worded `scenario` or `expected_output`, a flipped `category`,
# or a re-pointed `baseline` must all refuse as stale (ADR-0005 / AC4).
# Pinning `scenario` is intentional, not incidental: it is the human-facing
# description of what the case exercises, so editing it is a *definition*
# change (what this case means) rather than a cosmetic one — re-freeze, same
# as an `input`/`expected_output` edit. `id` and `weight` are already fixed
# across every `fidelity_eval.py` caller (see its `definition_hash`
# docstring), so they are not repeated here.
_CASES_KEY = "cases"
_CASE_PIN_FIELDS = ("category", "scenario", "input", "expected_output", "baseline")
# No per-case field is a referenced on-disk file in this slice — cases carry
# `input`/`expected_output`/`baseline` inline (AC2's shape has no file-path
# field). A large-input-as-referenced-file variant (mirroring
# content-fidelity's `reference`) is a future extension, not built here; when
# one exists, add its name to both `_REFERENCE_FILE_FIELDS` (content-hash) and
# `_CASE_PIN_FIELDS` (pin the path descriptor itself, exactly as
# content-fidelity's `reference` does — see that module's own comment).
_REFERENCE_FILE_FIELDS: tuple = ()
_EXTRA_HASH_FIELDS: tuple = ()


def _load_fidelity_eval():
    """Two-candidate probe (mirrors `content-fidelity/score.py`'s own): this
    file may eventually be copied into a target's `.servo/<eval>/` directory
    (a future install path) and must resolve its sibling shared module there,
    independent of CWD or how it was invoked.

    - source layout: `skills/eval-authoring/score.py` next to
      `skills/_common/fidelity_eval.py` (one directory up, then across);
    - copied-target layout: both files copied flat into the same directory.
    """
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "_common" / "fidelity_eval.py", here / "fidelity_eval.py"):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("fidelity_eval", candidate)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise ModuleNotFoundError(
        "fidelity_eval.py not found next to score.py nor at ../_common/fidelity_eval.py")


_fe = _load_fidelity_eval()

EnvError = _fe.EnvError
StaleError = _fe.StaleError
sha256_text = _fe.sha256_text
sha256_file = _fe.sha256_file


def definition_hash(config: dict) -> str:
    """AC5: the exact harness definition hash — judge/samples/threshold/
    cases, unchanged shape, so 008-04 can freeze this and spec-006 can
    compile it with no reshaping."""
    return _fe.definition_hash(config, _CASES_KEY, _CASE_PIN_FIELDS, _EXTRA_HASH_FIELDS)


def artifact_hashes(config: dict, base_dir: Path) -> dict:
    return _fe.artifact_hashes(config, base_dir, _CASES_KEY, _REFERENCE_FILE_FIELDS)


def validate_freeze(config: dict, base_dir: Path) -> None:
    _fe.validate_freeze(config, base_dir, _CASES_KEY, _CASE_PIN_FIELDS, _EXTRA_HASH_FIELDS)


def aggregate_lower_bound(samples, k: float) -> float:
    return _fe.aggregate_lower_bound(samples, k)


# --------------------------------------------------------------------------- #
# Constraint DSL (AC2) — a **vendored copy** of `eval_authoring.py`'s
# `parse_constraint` / `evaluate_constraint` (an 008-03 carry-forward this
# slice resolves: the two functions are duplicated here rather than
# imported).
#
# Why duplicate instead of import: `eval_authoring.py`'s `install_component`
# copies only this file + `fidelity_eval.py` into a target's
# `.servo/<component>/` — not the whole authoring CLI — so a standalone
# installed `score.py` has zero cross-file dependency beyond the shared
# harness (mirrors content-fidelity's own two-file install footprint
# exactly). `eval_authoring.py`'s copy remains canonical — it is what
# `validate_case` validates a constraint string against at authoring time;
# this copy only re-evaluates an already-validated string at score time, so
# a drift between the two could only ever affect *which side* (author-time
# validation vs score-time evaluation) catches a malformed expression first,
# never silently pass a bad one. `test_eval_authoring.py`'s
# `VendoredConstraintDSLDriftGuardTests` pins the two copies behaviourally
# equal (mirrors `eval_authoring.py`'s own `RESIDUAL_REASON_*` mirroring
# idiom).
# --------------------------------------------------------------------------- #
_CONSTRAINT_OPS = ("==", ">=", "<=")
_CONSTRAINT_RE = re.compile(
    r"^\s*(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<op>==|>=|<=)\s*(?P<value>.+?)\s*$"
)


def parse_constraint(text: str) -> dict:
    """Vendored copy of `eval_authoring.py::parse_constraint` — see this
    module's "Constraint DSL" section note above for why it is duplicated
    rather than imported. Identical parsing rules: `==`'s value stays a bare
    string (never float-coerced); `>=`/`<=` require a numeric value."""
    if not isinstance(text, str) or not text.strip():
        raise EnvError(f"empty or non-string constraint: {text!r}")
    m = _CONSTRAINT_RE.match(text)
    if not m:
        raise EnvError(
            f"malformed constraint {text!r} — expected '<field> <op> <value>' "
            f"with <op> one of {_CONSTRAINT_OPS}"
        )
    field = m.group("field")
    op = m.group("op")
    raw_value = m.group("value").strip()
    if not raw_value:
        raise EnvError(f"malformed constraint {text!r} — missing a value")
    if op == "==":
        value = raw_value.strip("\"'")
    else:
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise EnvError(
                f"malformed constraint {text!r} — {op!r} requires a numeric value, "
                f"got {raw_value!r}"
            ) from exc
    return {"field": field, "op": op, "value": value}


def evaluate_constraint(constraint: dict, actual_values: dict) -> bool:
    """Vendored copy of `eval_authoring.py::evaluate_constraint` — see this
    module's "Constraint DSL" section note above."""
    field, op, expected = constraint["field"], constraint["op"], constraint["value"]
    if field not in actual_values:
        raise EnvError(
            f"cannot evaluate constraint on field {field!r} — no actual value supplied")
    actual = actual_values[field]
    if op == "==":
        return str(actual) == expected
    try:
        actual_num = float(actual)
    except (TypeError, ValueError) as exc:
        raise EnvError(
            f"cannot compare field {field!r} with operator {op!r} against a non-numeric value"
        ) from exc
    return actual_num >= expected if op == ">=" else actual_num <= expected


# --------------------------------------------------------------------------- #
# Judge (AC2 — the structured-output contract; text-only. The composite below
# (008-03) drives this per scored case; the real candidate-gather that
# produces the `candidate` text `judge()` scores is still 008-04's job.)
# --------------------------------------------------------------------------- #

def judge(candidate: str, config: dict) -> dict:
    """One judge sample against `config["rubric"]`, dispatched on the frozen
    `judge.transport`: `"api"` (Messages API + ANTHROPIC_API_KEY) or `"cli"`
    (headless `claude -p`, subscription auth, no API key) — the same two
    transports `content-fidelity/score.py` supports.

    Returns the structured reply `{"score": float in [0,1], "reasoning": str,
    "strengths": [str], "weaknesses": [str]}` (AC2's richer schema). Never
    returns a silent `0.0` — a malformed/unreachable/unparseable reply raises
    `EnvError` instead (ADR-0005).
    """
    transport = (config.get("judge") or {}).get("transport", "api")
    if transport == "cli":
        return _judge_cli(candidate, config)
    if transport != "api":
        raise EnvError(f"unknown judge.transport: {transport!r} (expected 'api' or 'cli')")
    return _judge_api(candidate, config)


def _resolve_claude() -> str:
    """The `claude` CLI path: explicit `SERVO_EVAL_AUTHORING_CLAUDE_BIN`
    override, else PATH."""
    return os.environ.get("SERVO_EVAL_AUTHORING_CLAUDE_BIN") or shutil.which("claude")


def _prompt(candidate: str, config: dict) -> str:
    """The judge prompt: the authored rubric plus the candidate text under
    test, asking for AC2's four-field structured JSON reply."""
    return (
        config["rubric"].rstrip()
        + "\n\nCANDIDATE UNDER TEST:\n" + candidate.rstrip()
        + "\n\nReply with ONLY a JSON object, no other text: "
        '{"score": <number 0..1>, "reasoning": "<one or two sentences>", '
        '"strengths": ["<short phrase>", ...], "weaknesses": ["<short phrase>", ...]}.'
    )


def _parse_judge_reply(text: str) -> dict:
    """Parse a judge reply into AC2's structured shape. `score` is the one
    load-bearing field — required, and clamped to `[0,1]`; a missing or
    non-numeric `score` raises `EnvError`. `reasoning`/`strengths`/
    `weaknesses` are captured verbatim (defaulting to an empty value when the
    judge omits them). Any parse failure raises `EnvError` — never a silent
    `0.0` (ADR-0005 / AC2)."""
    try:
        obj = json.loads(_extract_json(text))
        clamped_score = max(0.0, min(1.0, float(obj["score"])))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        raise EnvError(f"unparseable judge response: {e}") from e
    return {
        "score": clamped_score,
        "reasoning": str(obj.get("reasoning", "")),
        "strengths": list(obj.get("strengths") or []),
        "weaknesses": list(obj.get("weaknesses") or []),
    }


def _judge_cli(candidate: str, config: dict) -> dict:
    """One judge sample via headless `claude -p` (subscription auth, no API
    key)."""
    claude = _resolve_claude()
    if not claude:
        raise EnvError(
            "`claude` CLI not found — set SERVO_EVAL_AUTHORING_CLAUDE_BIN or add it to PATH")
    prompt = _prompt(candidate, config)
    cmd = [claude, "-p", prompt, "--model", config["judge"]["model"], "--output-format", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError as e:
        raise EnvError(f"claude CLI not executable: {e}") from e
    except subprocess.TimeoutExpired:
        raise EnvError("claude judge timed out") from None
    if proc.returncode != 0:
        raise EnvError(f"claude judge failed (rc={proc.returncode}): {proc.stderr.strip()[:200]}")
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise EnvError(f"unparseable claude judge envelope: {e}") from e
    if envelope.get("is_error"):
        raise EnvError(f"claude judge error: {str(envelope.get('result'))[:200]}")
    return _parse_judge_reply(envelope.get("result", ""))


def _post_with_retry(req, timeout: int, attempts: int = 3) -> dict:
    """POST `req` via the shared HTTP-retry wrapper (module-level `urllib`/
    `time` stay imported here, not just in `_fe`, so tests can monkeypatch
    `score.urllib.request.urlopen`/`score.time.sleep` — both point at the
    same singleton stdlib modules `_fe` calls through, so the patch applies
    either way)."""
    return _fe._post_with_retry(req, timeout, attempts)


def _judge_api(candidate: str, config: dict) -> dict:
    """One judge sample via the Anthropic Messages API (x-api-key), sampled
    at low temperature (AC2)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvError("ANTHROPIC_API_KEY unset — cannot run the judge")
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    j = config["judge"]
    prompt = _prompt(candidate, config)

    body = {
        "model": j["model"],
        "max_tokens": int(j.get("max_tokens", 1024)),
        "temperature": float(j.get("temperature", 0.0)),
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        base + "/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    payload = _post_with_retry(req, timeout=180)
    text = "".join(
        b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
    return _parse_judge_reply(text)


def _extract_json(text: str) -> str:
    return _fe._extract_json(text)


# --------------------------------------------------------------------------- #
# Dataset composite (AC6 — 008-03's growth of this module): score every
# non-`skip_case` case in `config["cases"]`, gate each by its own hard
# constraints (if any), and combine into one weighted composite in [0,1].
# --------------------------------------------------------------------------- #

def _fake_scores():
    """Offline test hook: `{case_id: [sample, ...]}`, bypassing the real judge
    call entirely (mirrors content-fidelity's own `_FAKE_SCORES_ENV`)."""
    raw = os.environ.get(_FAKE_SCORES_ENV)
    return json.loads(raw) if raw else None


def _fake_actuals():
    """Offline test hook: `{case_id: {field: value, ...}}` — the
    `actual_values` map the constraint DSL (`evaluate_constraint`) evaluates
    a case's `expected_output.constraints` against. Stands in for 008-04's
    real per-candidate actual-value extraction (see `_case_constraint_score`
    below)."""
    raw = os.environ.get(_FAKE_ACTUALS_ENV)
    return json.loads(raw) if raw else None


def _gather_candidate(base_dir: Path, case: dict) -> str:
    """The candidate-gather seam: running the system under test on
    `case["input"]` to obtain the text this case's judged score is over
    (mirrors content-fidelity's `gather_text`, generalized past a
    file-or-command `source`). **Not yet implemented** — a documented,
    deliberately-unbuilt seam (out of every slice's scope so far — see the
    spec's non-goals: this skill authors, it does not run). A live
    (no-fake-scores) `score()` call raises `EnvError` here rather than
    silently judging a placeholder candidate — honest about the missing
    capability (ADR-0005) rather than fabricating one.
    """
    raise EnvError(
        f"case {case.get('id')!r}: candidate-gather is not yet implemented "
        f"— set {_FAKE_SCORES_ENV} for offline scoring until then"
    )


def _case_constraint_score(case: dict, fake_actuals) -> float:
    """The constraint-DSL gate for one case (AC2's "cheap deterministic
    sub-checks alongside the judged score"): `1.0` when every constraint
    passes (or the case has none — a rubric-only case is judged by the
    rubric alone), `0.0` the moment any constraint fails. This is the
    composition rule (documented, not derived): a **failed hard constraint
    zeroes that case's contribution** — multiplying its judged lower bound
    by this gate — rather than partially discounting it, so a case that
    fails a stated hard requirement can never still "mostly" pass on the
    strength of a good judged score.

    The real `actual_values` a live candidate produces are the same
    candidate-gather seam's job to extract (see `_gather_candidate`); the
    live path never reaches here (it raises first, in `_gather_candidate`),
    so only the `_FAKE_ACTUALS_ENV` offline test hook exercises this today.
    A case with constraints but no actuals supplied is an `EnvError` (never
    a silent pass or fail) — as is a malformed constraint or an
    evaluate-time DSL error (`parse_constraint`/`evaluate_constraint` above,
    this module's own vendored copy, so no cross-module exception type to
    reconcile).
    """
    constraints = ((case.get("expected_output") or {}).get("constraints")) or []
    if not constraints:
        return 1.0
    actual_values = (fake_actuals or {}).get(case["id"])
    if actual_values is None:
        raise EnvError(
            f"case {case['id']!r} has constraints but no actual values to evaluate them "
            f"against (set {_FAKE_ACTUALS_ENV} for offline scoring; live actual-value "
            "extraction from a candidate is the candidate-gather seam's job)"
        )
    for raw_constraint in constraints:
        constraint = parse_constraint(raw_constraint)
        if not evaluate_constraint(constraint, actual_values):
            return 0.0
    return 1.0


def _case_weight(case: dict) -> float:
    """Guarded per-case weight parse (AC5/an 008-03 carry-forward this
    slice resolves): `weight` is not part of AC2's case shape and is
    unvalidated at authoring time, so a hand-edited non-numeric value must
    raise this module's own clean `EnvError`, not a bare `ValueError`
    bubbling out of `score()`. The `total_w <= 0` guard below stays as its
    own explicit check (a numerically valid but degenerate all-zero-weight
    dataset is a distinct failure mode from a malformed weight)."""
    raw = case.get("weight", 1.0)
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise EnvError(f"case {case.get('id')!r}: weight must be numeric, got {raw!r}") from exc


def score(base_dir: Path) -> float:
    """The dataset composite (AC6): a weighted lower-bound-aggregated judged
    score across every scored case in `<base_dir>/config.json`.

    - `category == "skip_case"` cases are **excluded from the denominator
      entirely** — never judged, never weighted in (AC2's taxonomy: a
      skip case marks a scenario the eval deliberately does not score).
    - Every other case gets `n` judged samples (the real judge path via
      `judge()`, or — offline — the `_FAKE_SCORES_ENV` hook keyed by case
      id), aggregated to a conservative lower bound
      (`aggregate_lower_bound`), then gated by `_case_constraint_score`
      (a rubric-only case, with no `expected_output.constraints`, is judged
      by the rubric alone — the gate is a no-op `1.0`).
    - The per-case scores combine into one weighted mean (`weight` defaults
      to `1.0`, exactly as `content-fidelity/score.py`'s own composite),
      clamped to `[0,1]`.

    Enforces the freeze first (AC5, this slice's resolution of 008-03's
    carry-forward): `validate_freeze` runs before anything else, so a
    change to the rubric / dataset / model / n / delta / threshold since
    the last `eval_authoring.py emit` refuses as `StaleError` (exit 2) —
    mirrors `content-fidelity/score.py::score()`'s own first line exactly.

    Honesty (ADR-0005): a stale/unapproved definition, a missing judged
    sample, an unreachable/malformed judge reply, a non-numeric per-case
    `weight`, or a case with constraints but no actual values, all raise
    `EnvError`/`StaleError` — never a silent `0.0`.
    """
    config = json.loads((base_dir / "config.json").read_text())
    validate_freeze(config, base_dir)  # StaleError -> exit 2 (AC5)
    n = int(config["samples"]["n"])
    k = float(config["samples"].get("k", 1.0))
    fake_scores = _fake_scores()
    fake_actuals = _fake_actuals()

    per_case = []
    for case in config.get(_CASES_KEY, []):
        if case.get("category") == "skip_case":
            continue  # excluded from the denominator entirely (AC2/AC6)
        if fake_scores is not None:
            if case["id"] not in fake_scores:
                raise EnvError(f"fake scores missing case {case['id']!r}")
            samples = [float(x) for x in fake_scores[case["id"]]]
        else:
            # Gather is not yet implemented — see _gather_candidate.
            candidate = _gather_candidate(base_dir, case)
            samples = [judge(candidate, config)["score"] for _ in range(n)]
        lower_bound = aggregate_lower_bound(samples, k)
        case_score = lower_bound * _case_constraint_score(case, fake_actuals)
        per_case.append((case, samples, case_score))

    if not per_case:
        raise EnvError("no scored cases (every case is skip_case, or cases is empty)")
    total_w = sum(_case_weight(c) for c, _, _ in per_case)
    if total_w <= 0:
        raise EnvError("total case weight is zero")
    composite = sum(cs * _case_weight(c) for c, _, cs in per_case) / total_w
    _ledger(base_dir, config, per_case, composite)
    return max(0.0, min(1.0, composite))


def _ledger(base_dir: Path, config: dict, per_case, composite: float) -> None:
    record = {
        "at": _fe.iso_now(),
        "model": config["judge"]["model"],
        "transport": (config.get("judge") or {}).get("transport", "api"),
        "composite": round(composite, 4),
        "definition_hash": config.get("approved_content_hash"),
        "cases": [
            {"id": c["id"], "samples": [round(x, 4) for x in samp], "score": round(cs, 4)}
            for c, samp, cs in per_case
        ],
    }
    _fe.write_ledger(base_dir, record)


def main(argv=None) -> int:
    """The `score_<name>` oracle.sh component entrypoint (mirrors
    `content-fidelity/score.py::main()` exactly). The component invokes
    `score.py <target>`, but the frozen eval this copy scores lives beside
    this file (`eval_authoring.py install_component` copies it there), so
    the base dir is always this script's own directory — the arg is
    accepted for the oracle.sh contract and intentionally ignored. `argv`
    stays in the signature so tests can call `main([])` without touching
    `sys.argv`."""
    base_dir = Path(__file__).resolve().parent
    try:
        composite = score(base_dir)
    except StaleError as e:
        print(f"eval-authoring: stale — {e}", file=sys.stderr)
        return EXIT_ENV_ERROR
    except EnvError as e:
        print(f"eval-authoring: env_error — {e}", file=sys.stderr)
        return EXIT_ENV_ERROR
    print(f"{composite:.4f}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())


# --------------------------------------------------------------------------- #
# Remaining seam (deliberately unbuilt — see the module docstring): the real
# candidate-gather (`_gather_candidate`) and actual-value extraction
# (`_case_constraint_score`), plus widening `judge()` to carry a case's
# `baseline` for the comparative archetype. Both need a real "system under
# test" to drive them, which is out of scope for the authoring skill (spec
# 008's non-goal: this skill authors, it does not run).
# --------------------------------------------------------------------------- #
