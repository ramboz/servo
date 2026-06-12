#!/usr/bin/env python3
"""ADR-0008 experiment analyzer — summarize a V1/V2 run directory.

Usage:  analyze.py {v1|v2} <run_dir>

Reads each arm subdir's stream.jsonl + mj-firings.jsonl + exit_code/final_phase
and prints a per-arm metrics block plus the raw signals that bear on the gate's
verdict. It does NOT declare PASS/FAIL on its own — it prints interpretation
guidance and lets a human apply it to the observed signals (the whole point of
an empirical gate is that the numbers, not the script, decide).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Match only a REAL oracle verdict line — the full form with the composite=/
# threshold= tail. The /goal condition text echoes the bare
# `SERVO_ORACLE_VERDICT exit=0 status=pass` substring, which lacks that tail and
# so must NOT count as the oracle having actually passed.
_SENTINEL_RE = re.compile(
    r"SERVO_ORACLE_VERDICT\s+exit=\S+\s+status=(\S+)\s+composite=\S+\s+threshold=\S+"
)


def load_jsonl(p: Path) -> list:
    recs: list = []
    if not p.is_file():
        return recs
    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            recs.append(json.loads(line))
        except Exception:
            recs.append({"_unparsed": line})
    return recs


def read_text(p: Path) -> str:
    return p.read_text(errors="replace").strip() if p.is_file() else "?"


def deep_find_sentinels(recs: list) -> list[tuple[str, str]]:
    """Return (full_line, status) for every REAL oracle verdict in the stream.

    Uses the strict regex so the /goal condition's echoed bare-substring is not
    miscounted as an actual oracle pass."""
    found: list[tuple[str, str]] = []

    def walk(o):
        if isinstance(o, str):
            for m in _SENTINEL_RE.finditer(o):
                found.append((m.group(0).strip(), m.group(1)))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for r in recs:
        walk(r)
    return found


def hook_started_counts(recs: list) -> dict:
    """Count hook firings by event from the stream's system/hook_started shape
    ({"type":"system","subtype":"hook_started","hook_event":"Stop",...}). The
    Stop count is the key collision signal: it doubles in arm C (both hooks fire
    per stop) vs the single-hook arms."""
    counts: dict = {}
    for r in recs:
        if isinstance(r, dict) and r.get("subtype") == "hook_started":
            ev = str(r.get("hook_event"))
            counts[ev] = counts.get(ev, 0) + 1
    return counts


def stop_hook_responses(recs: list) -> list[str]:
    """Non-empty Stop hook_response outputs (e.g. the meta-judge's block JSON)."""
    outs = []
    for r in recs:
        if (isinstance(r, dict) and r.get("subtype") == "hook_response"
                and r.get("hook_event") == "Stop"):
            o = (r.get("output") or "").strip()
            if o:
                outs.append(o.replace("\n", " ")[:160])
    return outs


def result_event(recs: list) -> dict:
    for r in reversed(recs):
        if isinstance(r, dict) and r.get("type") == "result":
            return r
    return {}


def is_block(rec: dict) -> bool:
    s = rec.get("stdout") if isinstance(rec, dict) else None
    return isinstance(s, str) and "decision" in s and "block" in s


def summarize(arm: Path) -> dict:
    stream = load_jsonl(arm / "stream.jsonl")
    mj = load_jsonl(arm / "mj-firings.jsonl")
    res = result_event(stream)
    sents = deep_find_sentinels(stream)
    return {
        "exit_code": read_text(arm / "exit_code"),
        "result_subtype": res.get("subtype"),
        "is_error": res.get("is_error"),
        "num_turns_reported": res.get("num_turns"),
        "assistant_msgs_in_stream": sum(
            1 for r in stream if isinstance(r, dict) and r.get("type") == "assistant"
        ),
        "total_cost_usd": res.get("total_cost_usd"),
        "oracle_verdicts_in_transcript": len(sents),
        "reached_status_pass": any(status == "pass" for _line, status in sents),
        "final_phase": read_text(arm / "final_phase"),
        "final_progress": read_text(arm / "final_progress"),
        "mj_firings": len(mj),
        "mj_blocks": sum(1 for r in mj if is_block(r)),
        "mj_stop_hook_active_seen": [
            r.get("stop_hook_active") for r in mj if isinstance(r, dict)
        ],
        "stream_stop_hook_firings": hook_started_counts(stream).get("Stop", 0),
        "stream_hook_started_by_event": hook_started_counts(stream),
        "stream_stop_responses_nonempty": stop_hook_responses(stream),
    }


V1_GUIDE = """\
INTERPRETATION — V1 (Stop-hook collision):
  • Arm A (meta-judge only) MUST show mj_firings>=1 with a block on the first
    firing (stop_hook_active=false) — if not, project hooks aren't firing in -p
    mode and NO arm is trustworthy (fix the harness before reading B/C).
  • Compare C (both) against A and B:
      - C.mj_firings>0 AND first firing sees stop_hook_active=false, blocks like A
        → the two Stop hooks STACK (meta-judge survives the rebase, runs alongside
          /goal's managed hook).
      - C.mj_firings==0, or its first firing already sees stop_hook_active=true
        (i.e. /goal's managed hook ran first and consumed the sequence)
        → /goal's hook PREEMPTS the meta-judge (meta-judge is redundant/shadowed
          → ADR-0006 must be amended; meta-judge can't gate a /goal run).
      - C errors / never stops / final_phase still 'fail' while B reached pass
        → destructive COLLISION → Kill-criterion 1 → fall back to hand-rolled loop.
  • stream_hook_event_types may directly reveal /goal's managed Stop hook if
    --include-hook-events surfaces it."""

V2_GUIDE = """\
INTERPRETATION — V2 (headless /goal + cap binding):
  • Arm a (engage): if num_turns / assistant_msgs > 1 AND reached_status_pass is
    true with final_phase=pass → /goal ENGAGED headlessly and correctly
    fact-checked the oracle sentinel (the proposed composition works in -p).
    If it ran exactly 1 turn (same as the plain control c) and did NOT loop
    → /goal does NOT engage in -p mode (it is interactive-only here) → the rebase
    must drive /goal via /background or stream-json, not plain `claude -p`.
  • Arm b (budget_cap): pass_after=99 means the goal is effectively unreachable.
    If result_subtype indicates a budget/limit stop and total_cost_usd ≈ the cap
    with final_phase still 'fail' → --max-budget-usd HARD-BINDS a /goal run
    (servo can enforce its retained cost ceiling through the outer flag).
    If it ran away well past the cap → caps ESCAPE the loop → Kill-criterion 2.
  • Compare a vs c (plain control) to confirm the extra turns are /goal's doing."""

V3_GUIDE = """\
INTERPRETATION — V3 (availability under hook restrictions):
  • baseline arm MUST show stream_stop_hook_firings>0, mj_firings>0 (a block) and
    final_phase=pass — both /goal and the meta-judge active (sanity; if not, fix
    the harness before reading the other arm).
  • disableAllHooks arm: expect stream_stop_hook_firings==0 AND mj_firings==0 (no
    hook fires) AND no /goal continuation (final_progress small / like the plain
    control, reached_status_pass false, final_phase=fail). That is the
    Kill-criterion-4 mechanism — ONE switch disables BOTH /goal (managed hook) and
    the meta-judge (project hook); only loop.py (no hooks) survives.
  • allowManagedHooksOnly (managed-tier only; not injectable via --settings) has
    the same expected effect. Use v3_audit_env.py to measure how common either
    switch is across real target environments."""


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("v1", "v2", "v3"):
        sys.stderr.write("usage: analyze.py {v1|v2|v3} <run_dir>\n")
        return 2
    mode, run_dir = argv[0], Path(argv[1])
    if not run_dir.is_dir():
        sys.stderr.write(f"run dir not found: {run_dir}\n")
        return 2

    arms = sorted(d for d in run_dir.iterdir() if d.is_dir())
    print(f"\n=== ADR-0008 {mode.upper()} analysis — {run_dir} ===\n")
    for arm in arms:
        s = summarize(arm)
        print(f"── arm: {arm.name}")
        for k, v in s.items():
            print(f"     {k:28} {v}")
        print()
    print({"v1": V1_GUIDE, "v2": V2_GUIDE, "v3": V3_GUIDE}[mode])
    print()
    # Emit machine-readable rollup beside the run for later diffing.
    rollup = {arm.name: summarize(arm) for arm in arms}
    (run_dir / "analysis.json").write_text(json.dumps(rollup, indent=2) + "\n")
    print(f"(machine-readable rollup → {run_dir / 'analysis.json'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
