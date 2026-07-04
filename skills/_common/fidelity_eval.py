#!/usr/bin/env python3
"""Shared frozen-eval harness for servo's non-deterministic fidelity evals
(servo ADR-0024).

Modality-agnostic primitives extracted from `skills/design-eval/score.py` and
`design_eval.py` (spec 012) once a second consumer (content-fidelity, spec
020) needed the same freeze/hash/lower-bound/ledger/install-splice machinery.
Nothing here knows about images or text — the case shape (which array key
holds the cases, which per-case fields are files) is a parameter, not a
hardcoded assumption (ADR-0005's frozen-eval contract, generalized).

A flat module — no package `__init__.py` — so it copies as a single file
exactly like `capture.mjs` does today (see ADR-0024's "what moves" section
and 020-01's Assumption A1 on the two-deployment-layout import contract).

Python 3.9+ standard library only (servo constraint, ADR-0020).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class EnvError(RuntimeError):
    """Infrastructure failure — must surface as exit 2, never a 0.0 score."""


class StaleError(RuntimeError):
    """The frozen definition changed — refuse until re-frozen (exit 2)."""


# --------------------------------------------------------------------------- #
# Freeze (mirrors spec-oracle's 006-04 approval model for the eval case)
# --------------------------------------------------------------------------- #

def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def definition_hash(
    config: dict, cases_key: str, case_file_fields, extra_fields: tuple = ()) -> str:
    """Hash the *frozen definition* (ADR-0005 clause 2): judge model + decoding,
    sample count / aggregation / delta, threshold, and the case set. Excludes
    the hash-bearing/bookkeeping fields so it is stable and self-consistent —
    and excludes anything *environmental* (e.g. design-eval's ``app_url``,
    where the running app is reached), not part of the eval definition;
    pinning it would force a re-freeze + re-approval on an environment move.

    ``cases_key`` is the config key holding the case array (e.g. ``"screens"``
    for design-eval, ``"cases"`` for content-fidelity). ``case_file_fields``
    lists the per-case fields that name a file (e.g. ``("reference",
    "setup")``); every other per-case field this hash cares about (``id``,
    ``weight``) is fixed across callers. ``extra_fields`` lists additional
    top-level config keys a specific caller wants pinned as part of its
    definition (e.g. design-eval's screenshot viewport) — this module itself
    has no modality-specific fields, so a caller with nothing extra to pin
    (e.g. content-fidelity) simply omits the argument.
    """
    definition = {
        "judge": config.get("judge"),
        "samples": config.get("samples"),
        "threshold": config.get("threshold"),
        **{field: config.get(field) for field in extra_fields},
        cases_key: [
            {
                "id": c["id"],
                **{field: c.get(field) for field in case_file_fields},
                "weight": c.get("weight", 1.0),
            }
            for c in config.get(cases_key, [])
        ],
    }
    return sha256_text(json.dumps(definition, sort_keys=True))


def artifact_hashes(config: dict, base_dir: Path, cases_key: str, case_file_fields) -> dict:
    """The rubric (inline) plus every per-case file field, by relative path."""
    hashes = {"rubric": sha256_text(config.get("rubric", ""))}
    for c in config.get(cases_key, []):
        for field in case_file_fields:
            rel = c.get(field)
            if rel:
                f = base_dir / rel
                if f.is_file():
                    hashes[rel] = sha256_file(f)
    return hashes


def validate_freeze(
    config: dict, base_dir: Path, cases_key: str, case_file_fields,
    extra_fields: tuple = ()) -> None:
    """Refuse (StaleError) unless approved and every frozen part still matches."""
    if config.get("approval_status") != "approved":
        raise StaleError(
            "not approved (approval_status != 'approved') — run the authoring CLI's freeze")
    if definition_hash(
            config, cases_key, case_file_fields, extra_fields) != config.get(
                "approved_content_hash"):
        raise StaleError(
            "definition changed since freeze (model / n / delta / threshold / cases) — re-freeze")
    frozen = config.get("hashes", {})
    if not frozen:
        raise StaleError("no frozen artifact hashes — re-freeze")
    if frozen.get("rubric") != sha256_text(config.get("rubric", "")):
        raise StaleError("rubric changed since freeze — re-freeze")
    for rel, want in frozen.items():
        if rel == "rubric":
            continue
        f = base_dir / rel
        if not f.is_file():
            raise StaleError(f"frozen artifact missing: {rel} — re-freeze")
        if sha256_file(f) != want:
            raise StaleError(f"frozen artifact changed: {rel} — re-freeze")


# --------------------------------------------------------------------------- #
# Aggregation (ADR-0005 clause 3 — within-run anti-flap)
# --------------------------------------------------------------------------- #

def aggregate_lower_bound(samples, k: float) -> float:
    """Conservative lower bound of the sampled scores: ``mean - k*stderr``,
    clamped to ``[0,1]``. A single sample has stderr 0. This is what makes a
    wobbling judge contribute a high score only when it is *confident across
    samples* — scores within the band read as "not yet" rather than flapping.
    """
    vals = [float(s) for s in samples]
    if not vals:
        raise EnvError("no samples to aggregate")
    mean = statistics.fmean(vals)
    stderr = 0.0 if len(vals) < 2 else statistics.stdev(vals) / math.sqrt(len(vals))
    return max(0.0, min(1.0, mean - k * stderr))


# --------------------------------------------------------------------------- #
# Judge-reply parsing + HTTP retry (generic — no modality awareness)
# --------------------------------------------------------------------------- #

def _extract_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in judge reply")
    return text[start:end + 1]


def _post_with_retry(req, timeout: int, attempts: int = 3) -> dict:
    """POST ``req`` and return the parsed JSON body, with bounded exponential
    backoff on *transient* failures only: HTTP 429 / 5xx and network/timeout
    errors are retried; HTTP 4xx (bad request, auth) surfaces immediately because
    a retry cannot fix it. Exhausting the attempts raises ``EnvError`` (-> rc 2),
    never a silent score. Each of the ``n`` samples calls this, so a single
    transient blip on the last sample no longer discards the whole case."""
    import random  # local import: only the live HTTP path needs jitter

    delay = 1.0
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if not (e.code == 429 or 500 <= e.code < 600) or attempt == attempts:
                raise EnvError(f"judge request failed (HTTP {e.code}): {e}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt == attempts:
                raise EnvError(f"judge request failed: {e}") from e
        time.sleep(delay + random.uniform(0.0, 0.5))
        delay *= 2
    raise EnvError("judge request failed: retries exhausted")  # unreachable


# --------------------------------------------------------------------------- #
# Ledger (evidence trail — ADR-0005's "never a silent zero" honesty contract)
# --------------------------------------------------------------------------- #

def write_ledger(base_dir: Path, record: dict) -> None:
    """Append one JSON record to ``ledger.jsonl``. Best-effort — never fail the
    caller's score on a write error (a full disk shouldn't turn a real score
    into an env_error)."""
    try:
        with (base_dir / "ledger.jsonl").open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# oracle.sh install/uninstall splice (generalized from design_eval.py's
# COMPONENT-hardcoded splice — ADR-0024's second "what moves" item)
# --------------------------------------------------------------------------- #

_DRIVER_ANCHOR = 'weighted_sum="0"'


def splice_component(oracle_text: str, component: str, fragment: str) -> str:
    """Replace an existing ``# SEED:start <component>`` block in ``oracle_text``
    with ``fragment``, or insert ``fragment`` before the driver-loop anchor if
    no such block exists yet. Idempotent: a second call with a changed
    ``fragment`` replaces the old block in place rather than duplicating it."""
    block_re = re.compile(
        r"# SEED:start " + re.escape(component) + r"\n.*?# SEED:end " + re.escape(component)
        + r"\n", re.DOTALL)
    if block_re.search(oracle_text):
        return block_re.sub(lambda _m: fragment, oracle_text, count=1)
    text, n = re.subn(
        re.escape(_DRIVER_ANCHOR), lambda m: fragment + "\n" + m.group(0), oracle_text, count=1)
    if n == 0:
        raise ValueError(
            "could not find the driver-loop anchor in oracle.sh; is this a servo oracle?")
    return text


def splice_components_entry(oracle_text: str, component: str, weight: float) -> str:
    """Add or refresh ``"<component>:<weight>"`` in the ``COMPONENTS=(...)``
    array. Idempotent: re-registering the same component refreshes its weight
    in place instead of appending a duplicate entry."""
    entry = f'"{component}:{weight}"'
    entry_re = re.compile(r'"' + re.escape(component) + r':[^"]*"')
    if entry_re.search(oracle_text):
        return entry_re.sub(lambda _m: entry, oracle_text, count=1)
    text, n = re.subn(
        r"COMPONENTS=\(\s*\n", lambda _m: f'COMPONENTS=(\n  {entry}\n', oracle_text, count=1)
    if n == 0:
        raise ValueError("could not find COMPONENTS=( in oracle.sh")
    return text


def unsplice_component(oracle_text: str, component: str) -> str:
    """Remove ``component``'s SEED block and its ``COMPONENTS=(...)`` entry.
    Symmetric with ``splice_component``/``splice_components_entry``."""
    text = re.sub(
        r"# SEED:start " + re.escape(component) + r"\n.*?# SEED:end " + re.escape(component)
        + r"\n", "", oracle_text, flags=re.DOTALL)
    text = re.sub(r'[ \t]*"' + re.escape(component) + r':[^"]*"\n', "", text)
    return text


def register_manifest(target: Path, component: str) -> None:
    """Add ``component`` to ``<target>/.servo/install.json``'s ``components``
    list if the manifest exists. No-op if there is no manifest to update."""
    manifest = target / ".servo" / "install.json"
    if not manifest.is_file():
        return
    data = json.loads(manifest.read_text())
    components = data.setdefault("components", [])
    if component not in components:
        components.append(component)
        manifest.write_text(json.dumps(data, indent=2) + "\n")


def deregister_manifest(target: Path, component: str) -> None:
    """Remove ``component`` from ``<target>/.servo/install.json``'s
    ``components`` list if present. Symmetric with ``register_manifest``, so
    the manifest never lists a component no longer spliced into oracle.sh."""
    manifest = target / ".servo" / "install.json"
    if not manifest.is_file():
        return
    data = json.loads(manifest.read_text())
    components = data.get("components")
    if isinstance(components, list) and component in components:
        components.remove(component)
        manifest.write_text(json.dumps(data, indent=2) + "\n")


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
