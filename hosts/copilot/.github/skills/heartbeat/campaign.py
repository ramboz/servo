#!/usr/bin/env python3
"""servo campaign plan + ledger CLI (spec 042-01, ADR-0049).

A **campaign** is heartbeat-style dispatch over a *planned* work list. This
module is the file contract every later campaign mode builds on, and the A4
oracle-coverage checkpoint: a human or a host can declare a work list
(`campaign init`) and read one compact ledger of what each worker did and what
it cost (`campaign record` / `campaign status`) — with no worker execution yet.

Three subcommands:
  * `init <target> --plan <file> [--id <id>]` — validate a plan file and write
    `<target>/.servo/campaigns/<id>/plan.json` + an empty `ledger.jsonl`.
    Fail-closed: any validation error exits rc=2 with a single reason and
    writes nothing (no partial files).
  * `record <id> <item> --outcome <line> [--tier ...] [--target <path>]` —
    append one typed outcome (spec 040's `servo_outcome` line) under a blocking
    `flock` + atomic write, with `tier` and `self_reported`.
  * `status <id> [--json] [--target <path>]` — read-only read-back of each
    item's latest outcome, the totals, and the open items.

State lives ONLY under `<target>/.servo/campaigns/`. servo never reads jig
files: a jig reframe manifest is converted into a servo plan by jig or a human
(ADR-0049), never read here.

Dependency-free skill invariant (bug 005): this module never statically imports
a sibling skill. loop.py's 038 models validator is loaded dynamically via
`importlib` (the same `spec_from_file_location` probe score.py uses), so the
`models` block is validated with the exact 038 schema and rejected with the
exact same messages (042-01 AC1). The ledger's lock + atomic-write discipline
(ADR-0010 / ADR-0004) is mirrored from heartbeat.py's inbox rather than imported,
so the concurrent `record` and `status` paths never load heartbeat.py. (`init`
does load loop.py — and thus loop.py's own gate-consumer import — to reach the
038 validator; the mirror keeps the hot ledger paths off the heavier heartbeat
module, and the ledger lock is deliberately blocking where the inbox lock is
not; see `_ledger_lock`.)
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# `fcntl` is POSIX-only stdlib. servo already assumes POSIX (the oracle is a
# shell script); on a non-POSIX host the atomic write still prevents torn files
# and only the lost-update race is unguarded (mirrors heartbeat.py's inbox).
try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

SCHEMA_VERSION = 1  # plan.json `schema_version`
PLAN_NAME = "plan.json"
LEDGER_NAME = "ledger.jsonl"
LEDGER_LOCK_NAME = ".ledger.lock"
TMP_SUFFIX = ".tmp"
CAMPAIGNS_SEGMENTS = (".servo", "campaigns")

PLAN_TOP_KEYS = ("schema_version", "items")
ITEM_REQUIRED = ("id", "title", "prompt", "oracle_ref", "budget", "models")
BUDGET_KEYS = ("unit", "ceiling")
BUDGET_UNITS = ("usd", "credit")

# The three campaign tiers (ADR-0049) — the LEDGER's tier vocabulary.
# `self_reported` is derived, never taken from the caller: only advisory outcomes
# are self-reported, and the aggregate ceiling never counts a self-reported cost
# as enforced spend (042-01 AC2).
TIERS = ("servo", "wrapped", "advisory")
_TIER_SELF_REPORTED = {"servo": False, "wrapped": False, "advisory": True}

# But `campaign record` accepts only servo + advisory in 042-01. `wrapped` is
# "verified, not declared" (ADR-0049): a wrapped entry is legitimate only once
# 042-04's run-id / content-fingerprint / base-sha verifier earns it (an
# unverified wrapped downgrades to advisory), and its cost counts as enforced
# spend — so letting a caller self-declare `--tier wrapped` here would count
# unverified spend as enforced. The schema and the accounting below still handle
# `wrapped` (ready for 042-04); the CLI gate is what waits.
CLI_TIERS = ("servo", "advisory")

# Spec 040's typed outcome line. These mirror loop.py's `OUTCOME_SCHEMA_VERSION`
# and `OUTCOME_RESULT_*` constants (the 040-01 contract loop.py emits). Unlike the
# `models` validator, they are small value constants, so they are mirrored rather
# than loaded on the hot `record` path; `test_outcome_constants_track_loop` fails
# if loop.py's 040 schema drifts from these.
OUTCOME_SCHEMA_VERSION = 1  # the line's `servo_outcome` field
OUTCOME_RESULTS = ("passed", "plateau", "budget", "blocked", "error")

# An item id (and a generated campaign id) is a lowercase slug.
ITEM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# loop.py carries the authoritative 038 models validator. Resolved relative to
# this file so it works in every host layout (source + the three vendored host
# packages all keep `agent-loop/` a sibling of `heartbeat/`). `SERVO_CAMPAIGN_LOOP_PY`
# overrides the path — the established `SERVO_*` test-hook idiom, cf. heartbeat.py's
# `SERVO_HEARTBEAT_LOOP_PY`.
_LOOP_PY_PATH = Path(
    os.environ.get("SERVO_CAMPAIGN_LOOP_PY")
    or Path(__file__).resolve().parent.parent / "agent-loop" / "loop.py")
_MODELS_VALIDATOR = None  # lazily loaded, then cached


def _load_models_validator():
    """Return loop.py's `_validate_models` (the 038 schema validator).

    Loaded dynamically the first time it is needed (never a static cross-skill
    import — the dependency-free invariant), then cached. Using loop.py's own
    function is what makes 042-01 AC1 true: the `models` block is validated with
    the exact 038 schema and rejected with the exact same messages.
    """
    global _MODELS_VALIDATOR
    if _MODELS_VALIDATOR is None:
        spec = importlib.util.spec_from_file_location(
            "campaign_models_consumer", _LOOP_PY_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODELS_VALIDATOR = module._validate_models
    return _MODELS_VALIDATOR


# --------------------------------------------------------------------------- #
# Ledger discipline — mirrored from heartbeat.py (ADR-0004 atomic write,
# ADR-0010 advisory flock). Kept self-contained so the campaign CLI does not
# transitively load heartbeat.py's gate-consumer machinery.
# --------------------------------------------------------------------------- #

def _atomic_write(path: Path, payload: str) -> None:
    """Write `payload` to `path` atomically: write a `.tmp` sibling, then
    `os.replace` it onto the final path. `os.replace` is atomic on POSIX and
    NTFS, so a Ctrl-C / SIGTERM / power loss mid-write never leaves a torn
    ledger for the next reader."""
    tmp = path.with_name(path.name + TMP_SUFFIX)
    tmp.write_text(payload)
    os.replace(tmp, path)


@contextlib.contextmanager
def _ledger_lock(campaign_dir: Path):
    """Advisory, BLOCKING `flock` around the ledger read-append-write.

    Yields `"locked"` (lock held) or `"unlocked"` (`fcntl` unavailable on a
    non-POSIX host — the atomic write still prevents torn files; only the
    lost-update race is unguarded). Unlike the heartbeat's non-blocking inbox
    lock, this one BLOCKS: a recorded outcome is unique data that must never be
    dropped on contention, so a concurrent `record` waits its turn rather than
    no-op'ing. The lock is taken on a separate, persistent `.ledger.lock` file —
    never on `ledger.jsonl`, whose inode `os.replace` swaps — and is never
    unlinked (the kernel releases it on process exit)."""
    if fcntl is None:  # pragma: no cover - non-POSIX fallback
        yield "unlocked"
        return
    lock_path = campaign_dir / LEDGER_LOCK_NAME
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)  # blocking — never drop a record
        try:
            yield "locked"
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _now_iso() -> str:
    """UTC timestamp, second resolution, `Z` suffix (mirrors heartbeat)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Plan validation (042-01 AC1)
# --------------------------------------------------------------------------- #

def _is_number(value: object) -> bool:
    """A real JSON number (int/float), never a bool (`True`/`False` are ints)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_budget(budget: object, item_id: str) -> Optional[str]:
    """`None` if the per-item budget is well-formed, else a single reason."""
    if not isinstance(budget, dict):
        return f"item {item_id!r}: budget must be an object"
    missing = [k for k in BUDGET_KEYS if k not in budget]
    if missing:
        return f"item {item_id!r}: budget missing required field(s): {missing}"
    extra = sorted(set(budget) - set(BUDGET_KEYS))
    if extra:
        return f"item {item_id!r}: budget has unknown field(s): {extra}"
    unit = budget["unit"]
    if unit not in BUDGET_UNITS:
        return (f"item {item_id!r}: budget unit must be one of "
                f"{list(BUDGET_UNITS)}, got {unit!r}")
    ceiling = budget["ceiling"]
    if not _is_number(ceiling):
        return f"item {item_id!r}: budget ceiling must be a number, got {ceiling!r}"
    if ceiling <= 0:
        return f"item {item_id!r}: budget ceiling must be > 0, got {ceiling!r}"
    return None


def _validate_item(item: object, idx: int, seen: set, validate_models) -> Optional[str]:
    """`None` if the item is well-formed (and registers its id), else a reason."""
    where = f"items[{idx}]"
    if not isinstance(item, dict):
        return f"{where} must be an object, got {item!r}"
    missing = [k for k in ITEM_REQUIRED if k not in item]
    if missing:
        return f"{where} missing required field(s): {missing}"
    extra = sorted(set(item) - set(ITEM_REQUIRED))
    if extra:
        return f"{where} has unknown field(s): {extra}"
    item_id = item["id"]
    if not isinstance(item_id, str) or not ITEM_ID_RE.match(item_id):
        return f"{where} id must match {ITEM_ID_RE.pattern!r}, got {item_id!r}"
    if item_id in seen:
        return f"duplicate item id {item_id!r}"
    seen.add(item_id)
    for field in ("title", "prompt", "oracle_ref"):
        value = item[field]
        if not isinstance(value, str) or not value.strip():
            return f"item {item_id!r}: {field} must be a non-empty string"
    budget_err = _validate_budget(item["budget"], item_id)
    if budget_err:
        return budget_err
    # The models block is validated with loop.py's 038 schema + validator, and
    # its message is preserved verbatim after a minimal item tag (AC1).
    _, models_err = validate_models(item["models"], allow_escalation=True)
    if models_err:
        return f"item {item_id!r}: {models_err}"
    return None


def _validate_plan(data: object) -> "tuple[Optional[dict], Optional[str]]":
    """`(plan, None)` if the plan is well-formed, else `(None, reason)`.

    Pure (writes nothing), so `init` can validate the whole plan before
    creating any file — the fail-closed, write-nothing guarantee (AC1)."""
    if not isinstance(data, dict):
        return None, "plan must be a JSON object"
    extra = sorted(set(data) - set(PLAN_TOP_KEYS))
    if extra:
        return None, f"plan has unknown top-level key(s): {extra}"
    if data.get("schema_version") != SCHEMA_VERSION:
        return None, (f"plan schema_version must be {SCHEMA_VERSION}, got "
                      f"{data.get('schema_version')!r}")
    items = data.get("items")
    if not isinstance(items, list):
        return None, "plan items must be a list"
    if not items:
        return None, "plan items must not be empty"
    validate_models = _load_models_validator()
    seen: set = set()
    for idx, item in enumerate(items):
        err = _validate_item(item, idx, seen, validate_models)
        if err:
            return None, err
    return data, None


# --------------------------------------------------------------------------- #
# Outcome validation + ledger entry (042-01 AC2)
# --------------------------------------------------------------------------- #

def _validate_outcome(obj: object) -> "tuple[Optional[dict], Optional[str]]":
    """`(outcome, None)` if `obj` is a spec 040 `servo_outcome` line, else
    `(None, reason)`."""
    if not isinstance(obj, dict):
        return None, "outcome line must be a JSON object"
    if obj.get("servo_outcome") != OUTCOME_SCHEMA_VERSION:
        return None, (f"outcome servo_outcome must be {OUTCOME_SCHEMA_VERSION}, "
                      f"got {obj.get('servo_outcome')!r}")
    result = obj.get("result")
    if result not in OUTCOME_RESULTS:
        return None, (f"outcome result must be one of {list(OUTCOME_RESULTS)}, "
                      f"got {result!r}")
    if "cost_usd" not in obj:
        return None, "outcome is missing cost_usd"
    cost = obj["cost_usd"]
    if cost is not None and not _is_number(cost):
        return None, f"outcome cost_usd must be a number or null, got {cost!r}"
    # A cost is a cumulative spend, never negative. Rejecting impossible input
    # keeps a tampered or malformed line from subtracting from enforced spend —
    # loop.py never emits a negative, so this can only catch a corrupt/hostile
    # line (which the host-driven advisory tier, 042-03, will forward untrusted).
    if _is_number(cost) and cost < 0:
        return None, f"outcome cost_usd must be >= 0, got {cost!r}"
    return obj, None


def _cost_unit_error(unit: str, cost_usd: object) -> Optional[str]:
    """`None` if the outcome's cost matches the item's budget denomination, else
    a reason (042-01 AC2).

    loop.py nulls `cumulative_cost_usd` ONLY under `--host copilot` (the main run
    state); every USD/Claude terminal reports a number, `0.0` included. But the
    refusal / preflight helpers (`_refuse_preflight`, `_refuse_plan`,
    `_refuse_readiness`, `_refuse_goal`) hardcode `0.0` regardless of host — so a
    legitimate credit/Copilot run that halts at one of those (e.g. an
    `unpriced_oracle_components` preflight) also emits `cost_usd: 0.0`. `0.0` is
    therefore ambiguous across hosts; only two signals are reliable, and the rule
    keys on them so no real outcome is dropped:
      * `cost_usd is None` ⇒ a credit/Copilot run — wrong unit on a USD item;
      * `cost_usd > 0`     ⇒ real USD spend — wrong unit on a credit item.
    A `0.0` is accepted on either (a no-spend USD refusal, or a Copilot refusal).
    A credit item's actual credit spend is not in the 040 line; it is re-derived
    from the loop's `state.json` by `run_id` in 042-04."""
    if unit == "usd":
        if cost_usd is None:
            return ("outcome cost_usd is null (a credit-denominated / Copilot "
                    "run) but the plan item is USD-denominated")
        return None
    if unit == "credit":
        if _is_number(cost_usd) and cost_usd > 0:
            return ("outcome reports positive USD spend but the plan item is "
                    "credit-denominated")
        return None
    return f"unknown budget unit {unit!r}"  # pragma: no cover - plan pre-validated


def _ledger_entry(item_id: str, tier: str, outcome: dict, now_iso: str) -> dict:
    """One ledger record: the typed outcome plus the campaign-layer fields.

    `self_reported` is DERIVED from the tier (true only for advisory), never
    taken from the caller — the accounting rule in `_status_summary` depends on
    it (042-01 AC2)."""
    return {
        "item": item_id,
        "tier": tier,
        "self_reported": _TIER_SELF_REPORTED[tier],
        "recorded_at": now_iso,
        "outcome": outcome,
    }


# --------------------------------------------------------------------------- #
# Status read-back (042-01 AC3)
# --------------------------------------------------------------------------- #

def _status_summary(plan: dict, entries: "list[dict]") -> dict:
    """Build the machine summary: each item's latest outcome, the totals, and
    the open items.

    Totals:
      * `enforced_cost_usd` — Σ `cost_usd` over entries whose `self_reported`
        is false (tier servo + wrapped). A self-reported (advisory) cost is
        never counted as enforced spend, and a credit `cost_usd: null` is not
        counted here (its credit spend is re-derived in 042-04). This is the
        aggregate-ceiling accounting rule (AC2).
      * `self_reported_cost_usd` — the advisory spend, shown but not enforced.
      * `passed` / `plateau` / `blocked` (and `budget` / `error`) — item counts
        by each item's LATEST outcome.
    An item is OPEN when its latest outcome is not `passed` (a never-recorded
    item is open)."""
    items = plan.get("items", [])
    credit_items = sum(
        1 for item in items
        if (item.get("budget") or {}).get("unit") == "credit")
    latest: "dict[str, dict]" = {}
    for entry in entries:
        latest[entry.get("item")] = entry  # last recorded wins

    enforced = 0.0
    self_reported = 0.0
    for entry in entries:
        cost = (entry.get("outcome") or {}).get("cost_usd")
        if _is_number(cost):
            if entry.get("self_reported"):
                self_reported += cost
            else:
                enforced += cost

    result_counts = {r: 0 for r in OUTCOME_RESULTS}
    item_views: "list[dict]" = []
    open_items: "list[str]" = []
    for item in items:
        item_id = item["id"]
        entry = latest.get(item_id)
        outcome = entry.get("outcome") if entry else None
        result = outcome.get("result") if outcome else None
        if result in result_counts:
            result_counts[result] += 1
        is_open = result != "passed"
        if is_open:
            open_items.append(item_id)
        item_views.append({
            "id": item_id,
            "title": item.get("title"),
            "latest": outcome,
            "latest_result": result,
            "latest_tier": entry.get("tier") if entry else None,
            "open": is_open,
        })

    totals = {
        "enforced_cost_usd": round(enforced, 6),
        "self_reported_cost_usd": round(self_reported, 6),
        "passed": result_counts["passed"],
        "plateau": result_counts["plateau"],
        "blocked": result_counts["blocked"],
        "budget": result_counts["budget"],
        "error": result_counts["error"],
        "credit_items": credit_items,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "items": item_views,
        "totals": totals,
        "open_items": open_items,
    }


def _render_status_human(summary: dict, campaign_id: str) -> str:
    """Render the human `status` read-back."""
    totals = summary["totals"]
    lines: "list[str]" = []
    lines.append(f"campaign {campaign_id}")
    lines.append(
        f"items: {len(summary['items'])}  open: {len(summary['open_items'])}")
    lines.append("")
    lines.append("items (latest outcome):")
    for view in summary["items"]:
        outcome = view["latest"]
        if outcome is None:
            lines.append(f"  - {view['id']}  [{view['title']}]  (no outcome — open)")
            continue
        cost = outcome.get("cost_usd")
        cost_str = "null" if cost is None else f"${cost}"
        lines.append(
            f"  - {view['id']}  [{view['title']}]  {view['latest_result']} "
            f"(tier={view['latest_tier']}, cost={cost_str}, "
            f"reason={outcome.get('reason')})")
    lines.append("")
    lines.append("totals:")
    lines.append(
        f"  enforced cost (servo + wrapped): ${totals['enforced_cost_usd']}")
    lines.append(
        f"  advisory self-reported (not counted): "
        f"${totals['self_reported_cost_usd']}")
    lines.append(
        f"  passed: {totals['passed']}  plateau: {totals['plateau']}  "
        f"blocked: {totals['blocked']}  budget: {totals['budget']}  "
        f"error: {totals['error']}")
    if totals.get("credit_items"):
        lines.append(
            f"  credit items: {totals['credit_items']} — spend tracked in AI "
            f"credits, re-derived in 042-04 (not in the USD totals above)")
    lines.append("")
    if summary["open_items"]:
        lines.append("open items: " + ", ".join(summary["open_items"]))
    else:
        lines.append("open items: none")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Filesystem helpers
# --------------------------------------------------------------------------- #

def _campaign_dir(target: Path, campaign_id: str) -> Path:
    return target.joinpath(*CAMPAIGNS_SEGMENTS, campaign_id)


def _load_plan_file(campaign_dir: Path) -> Optional[dict]:
    """Read a campaign's stored `plan.json`, or `None` when it is absent /
    unreadable / not a plan shape."""
    try:
        data = json.loads((campaign_dir / PLAN_NAME).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data
    return None


def _read_ledger(campaign_dir: Path) -> "list[dict]":
    """Read every ledger entry (one JSON object per line); `[]` when absent."""
    try:
        text = (campaign_dir / LEDGER_NAME).read_text()
    except OSError:
        return []
    entries: "list[dict]" = []
    for line in text.splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def _read_outcome_arg(value: str) -> Optional[str]:
    """Resolve `--outcome`: `-` reads stdin; inline JSON (starts with `{`/`[`)
    is returned verbatim; otherwise it is a path to read. `None` on a read
    error."""
    if value == "-":
        return sys.stdin.read()
    stripped = value.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return value
    try:
        return Path(value).read_text()
    except OSError:
        return None


def _generate_campaign_id() -> str:
    return "cmp-" + uuid.uuid4().hex[:12]


def _fail(message: str) -> int:
    """Fail closed: one reason on stderr, rc=2."""
    sys.stderr.write(f"campaign: {message}\n")
    return 2


# --------------------------------------------------------------------------- #
# Subcommands
# --------------------------------------------------------------------------- #

def cmd_init(args: argparse.Namespace) -> int:
    target: Path = args.target
    if not target.is_dir():
        return _fail(f"target {str(target)!r} is not a directory")
    try:
        raw = args.plan.read_text()
    except OSError as exc:
        return _fail(f"cannot read plan file {str(args.plan)!r}: {exc}")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _fail(f"plan file {str(args.plan)!r} is not valid JSON: {exc}")
    plan, err = _validate_plan(data)
    if err:
        return _fail(err)
    campaign_id = args.id if args.id is not None else _generate_campaign_id()
    if not ITEM_ID_RE.match(campaign_id):
        return _fail(
            f"campaign id must match {ITEM_ID_RE.pattern!r}, got {campaign_id!r}")
    cdir = _campaign_dir(target, campaign_id)
    if cdir.exists():
        return _fail(
            f"campaign {campaign_id!r} already exists at {cdir} (refusing to clobber)")
    # Everything validated: only NOW do we touch the filesystem, so any failure
    # above left nothing behind (AC1 write-nothing guarantee).
    cdir.mkdir(parents=True, exist_ok=False)
    _atomic_write(cdir / PLAN_NAME, json.dumps(plan, indent=2) + "\n")
    _atomic_write(cdir / LEDGER_NAME, "")
    sys.stdout.write(f"campaign {campaign_id} initialized\n")
    sys.stdout.write(f"  plan:   {cdir / PLAN_NAME}\n")
    sys.stdout.write(f"  ledger: {cdir / LEDGER_NAME}\n")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    cdir = _campaign_dir(args.target, args.id)
    plan = _load_plan_file(cdir)
    if plan is None:
        return _fail(
            f"campaign {args.id!r} not found under "
            f"{args.target.joinpath(*CAMPAIGNS_SEGMENTS)}")
    budget_unit = None
    for item in plan["items"]:
        if item.get("id") == args.item:
            budget_unit = (item.get("budget") or {}).get("unit")
            break
    if budget_unit is None:
        return _fail(f"unknown item id {args.item!r} (not in this campaign's plan)")
    raw = _read_outcome_arg(args.outcome)
    if raw is None:
        return _fail(f"cannot read --outcome {args.outcome!r}")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _fail(f"--outcome is not valid JSON: {exc}")
    outcome, err = _validate_outcome(obj)
    if err:
        return _fail(err)
    cost_err = _cost_unit_error(budget_unit, outcome["cost_usd"])
    if cost_err:
        return _fail(cost_err)
    entry = _ledger_entry(args.item, args.tier, outcome, _now_iso())
    # flock + atomic read-append-write — never drop or tear a record (AC2).
    with _ledger_lock(cdir):
        ledger_path = cdir / LEDGER_NAME
        try:
            existing = ledger_path.read_text()
        except OSError:
            existing = ""
        _atomic_write(ledger_path, existing + json.dumps(entry) + "\n")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cdir = _campaign_dir(args.target, args.id)
    plan = _load_plan_file(cdir)
    if plan is None:
        return _fail(
            f"campaign {args.id!r} not found under "
            f"{args.target.joinpath(*CAMPAIGNS_SEGMENTS)}")
    try:
        entries = _read_ledger(cdir)
    except json.JSONDecodeError as exc:
        return _fail(f"campaign {args.id!r} ledger has a malformed line: {exc}")
    summary = _status_summary(plan, entries)
    summary = {"campaign_id": args.id, **summary}
    if args.as_json:
        sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    else:
        sys.stdout.write(_render_status_human(summary, args.id))
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: Optional[list] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="campaign.py",
        description=(
            "servo campaign plan + ledger (spec 042-01). A planned, oracle-gated "
            "work list and its append-only, lock-guarded ledger of typed "
            "outcomes. No worker runs here — later modes dispatch."),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser(
        "init",
        help="Validate a plan file and create a campaign's plan.json + ledger.jsonl.",
        description=(
            "Validate <file> and write <target>/.servo/campaigns/<id>/plan.json "
            "and an empty ledger.jsonl. Fail-closed: any validation error exits "
            "rc=2 with a single reason and writes nothing."),
    )
    p_init.add_argument("target", type=Path, help="target project (holds .servo/).")
    p_init.add_argument("--plan", type=Path, required=True, help="path to the plan file.")
    p_init.add_argument(
        "--id", default=None,
        help="campaign id (lowercase slug). Generated when omitted.")

    p_record = sub.add_parser(
        "record",
        help="Append one typed outcome (spec 040 line) to a campaign's ledger.",
        description=(
            "Append one spec 040 servo_outcome line to the campaign's ledger "
            "under a blocking flock + atomic write, tagged with tier and the "
            "derived self_reported. An unknown item, a malformed line, or a cost "
            "in the wrong unit is refused rc=2 and the ledger is left unchanged."),
    )
    p_record.add_argument("id", help="campaign id.")
    p_record.add_argument("item", help="plan item id this outcome is for.")
    p_record.add_argument(
        "--outcome", required=True,
        help="the spec 040 outcome line: inline JSON, a file path, or '-' (stdin).")
    p_record.add_argument(
        "--tier", choices=CLI_TIERS, default="servo",
        help=("worker tier (default: servo). advisory sets self_reported=true. "
              "wrapped is earned by 042-04's verifier, not recordable here."))
    p_record.add_argument(
        "--target", type=Path, default=Path("."),
        help="target project holding .servo/ (default: current directory).")

    p_status = sub.add_parser(
        "status",
        help="Read-only read-back of each item's latest outcome and the totals.",
        description=(
            "Read-only: print each item's latest outcome, the totals (enforced "
            "cost, passed/plateau/blocked) and the open items. Writes nothing."),
    )
    p_status.add_argument("id", help="campaign id.")
    p_status.add_argument(
        "--json", dest="as_json", action="store_true",
        help="emit the machine summary as JSON (carrying schema_version).")
    p_status.add_argument(
        "--target", type=Path, default=Path("."),
        help="target project holding .servo/ (default: current directory).")

    args = parser.parse_args(argv)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "record":
        return cmd_record(args)
    if args.command == "status":
        return cmd_status(args)
    return 2  # pragma: no cover - argparse requires a subcommand


if __name__ == "__main__":
    sys.exit(main())
