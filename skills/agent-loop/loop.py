"""
servo agent-loop — full spec 003 (slices 003-01 through 003-06)

Two drivers, selected by `--driver {loop|goal}` (default `loop`):

- **`loop`** (slices 003-01..05): the hand-rolled driver described below — a
  `for`-loop over N `claude -p` calls with every guardrail enforced servo-side.
  Retained as the portable / external-driver layer for hook-restricted and
  non-Claude-Code hosts (ADR-0008).
- **`goal`** (slice 003-06, ADR-0008 rebase): a single `claude -p` whose prompt
  carries a `/goal` completion condition that drives across-turn continuation.
  The loop body runs `servo:quality-gate` each turn and prints a
  machine-greppable `SERVO_ORACLE_VERDICT` sentinel; the `/goal` condition only
  *fact-checks* that sentinel; the hard caps ride the OUTER call (`--max-turns`
  + `--max-budget-usd`, both V2-verified to bind a `/goal` run); and a **final
  authoritative `gate.py --json` run is the verdict** — never the transcript
  judge (ADR-0008 hard constraint; ADR-0002 exit-code contract). See
  `run_goal_loop`.

Headless iteration driver. Subprocesses `claude -p --output-format json
--agent <runner|judge>` against a target N times under guardrails, and
uses `gate.py --json` (spec 002) as the truth-source after each iteration.
Halts on (a) oracle pass (composite ≥ threshold), (b) iteration cap
reached, (c) cumulative cost ceiling exceeded (slice 003-02), (d)
context-fill ratio at-or-above the gate threshold (slice 003-03),
(e) SIGINT/SIGTERM (slice 003-04), (f) oracle-score plateau over the last
M iterations (slice 003-05), (g) verdict-block schema mismatch
(slice 003-05, ADR-0003).

Subagent dispatch (slice 003-05, ADR-0003): each iteration alternates
between `runner` (odd iters; CHANGES_MADE/NO_CHANGES/BLOCKED verdicts)
and `judge` (even iters; PASS/FAIL/INCONCLUSIVE + score). Each agent
ends its output with a fenced ```` ```verdict ``` ```` block carrying
`schema_version: 1` as its first field; `loop.py` parses the block and
refuses the run on schema mismatch.

Per-iteration prompt assembly: seed prompt + last `gate.py --json` output
+ last verdict block, concatenated into a structured prompt sent to the
next agent.

Checkpoint/resume: per-iteration state is atomically written to
`<target>/.servo/runs/<run-id>/state.json` (slice 003-04, ADR-0004). A
capped or interrupted run can be resumed via `loop.py --resume <run-id>`.

Usage:
    python3 loop.py <target> --prompt "<text>"
    python3 loop.py <target> --prompt "<text>" --max-iterations 3
    python3 loop.py <target> --prompt "<text>" --cost-ceiling 1.50
    python3 loop.py <target> --prompt "<text>" --context-fill-threshold 0.50
    python3 loop.py <target> --prompt "<text>" --plateau-window 5
    python3 loop.py <target> --resume <run-id>
    python3 loop.py <target> --resume <run-id> --max-iterations 20

Per-iteration JSON: one line per completed iteration on stdout.
Summary line: one JSON line on stdout after the last iteration (or refusal).
"""

import argparse
import json
import os
import platform
import re
import secrets
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Schema version for every JSON line emitted on stdout. Mirrors gate.py's
# `schema_version` (ADR-0002) and ADR-0004's `state_schema_version`. Bump
# on any field rename, type change, or semantic shift; pure additive changes
# MAY keep version=1. Old consumers can refuse loudly on mismatch rather
# than silently mis-decoding fields they don't recognize.
SCHEMA_VERSION = 1

# Closed exit-code contract aligned with gate.py (ADR-0002):
#   0 — loop terminated normally (oracle pass or iteration cap)
#   2 — env error (preflight refusal, claude invocation failure)
# 003-01 never exits 1; below-threshold scoring drives more iterations, not
# a non-zero loop exit. 1 is reserved should a later slice find a use for it.
EXIT_OK = 0
EXIT_ENV_ERROR = 2

# Default iteration cap (per docs/architecture.md "Project vs servo-core split").
DEFAULT_MAX_ITERATIONS = 5

# Slice 003-02 cost-ceiling defaults (per docs/architecture.md "Project vs
# servo-core split" table: max-iterations=5, cost-ceiling=$2). The ceiling
# is cumulative across iterations and enforced by loop.py; `--max-budget-usd`
# is the per-invocation defense-in-depth (so one runaway agentic turn can't
# blow past the cumulative cap by more than its own burn rate).
DEFAULT_COST_CEILING_USD = 2.0

# Minimum `--max-budget-usd` value the loop will ever pass to claude. Below
# this, the loop halts pre-iteration rather than invoking claude with an
# effectively-zero budget. Set just above zero so we never invoke a
# free-tier-only run by accident.
MIN_BUDGET_FLOOR_USD = 0.01

# `--max-budget-usd` value used when the cumulative cost-ceiling is disabled
# (`--cost-ceiling 0`). Provides a per-invocation brake so a runaway agentic
# turn still has an upper bound, even when the caller is enforcing a budget
# out-of-band.
DEFAULT_PER_ITER_BUDGET_USD = 1.0

# Slice 003-03 context-fill-gate default (spike picked 0.75 as the midpoint
# of the 60–75% range observed across mixed long/short iterations).
# Flagged in `docs/refinement-todo.md` for tuning once real-world iteration
# data accumulates. Pass 0 on the CLI to disable the gate entirely; the
# iteration cap and cost ceiling still apply.
DEFAULT_CONTEXT_FILL_THRESHOLD = 0.75

# Slice 003-05 plateau-detection window. After M consecutive iterations
# with no improvement over the highest score seen earlier, halt with
# `terminal_reason=oracle_plateau`. "No improvement" = strict less-than-or-
# equal-to the prior max. M=3 is a heuristic — short enough to catch a
# clearly-stuck loop, long enough to tolerate a few non-improving iters
# while the agent gathers context. Flagged in `docs/refinement-todo.md`
# for tuning once real-world plateau data accumulates. Pass 0 to disable.
DEFAULT_PLATEAU_WINDOW = 3
# ADR-0005 clause 4 (δ): plateau treats composite gains smaller than this
# frozen noise floor as "flat", so a wobbling non-deterministic eval component
# can neither fake progress (dodging a real plateau halt) nor fake a plateau
# (halting early). 0.0 = legacy behaviour — any strict gain counts as progress.
DEFAULT_PLATEAU_NOISE_FLOOR = 0.0

# Slice 003-05 subagent dispatch (ADR-0003). The loop alternates
# runner → judge → runner → judge → ... starting with runner on iter 1.
# Each agent's prompt is in `agents/<name>.md`; Claude Code resolves
# `--agent <name>` against the plugin's `agents/` directory.
AGENT_RUNNER = "runner"
AGENT_JUDGE = "judge"

# Slice 003-05 verdict-block schema version (ADR-0003). Mirrors gate.py's
# `schema_version` mechanism: refuse loudly on mismatch rather than
# silently mis-decoding. Spec 005's variant-race will reuse the judge
# verdict shape via the same version gate.
VERDICT_SCHEMA_VERSION = 1

# Regex for extracting a fenced ```verdict ... ``` block from agent output.
# DOTALL so the body can span lines; non-greedy so multiple blocks in a
# single response don't merge. Slice 003-05 uses the LAST match (the agent
# should end with the verdict block per `runner.md` / `judge.md`).
_VERDICT_BLOCK_RE = re.compile(r"```verdict\s*\n(.*?)\n```", re.DOTALL)

# Default per-invocation wall-clock cap for `claude -p`. 30 minutes is a
# generous upper bound — long enough for substantial agentic turns with
# tool use, short enough that an unattended loop won't hang for days if
# claude wedges. Tunable via the SERVO_CLAUDE_TIMEOUT env var (0 disables).
# Flagged in `docs/refinement-todo.md` for tuning with real-world data.
DEFAULT_CLAUDE_TIMEOUT_SECONDS = 1800

# Env var override for the per-invocation claude timeout. `0` disables the
# bound; malformed values fall back to DEFAULT_CLAUDE_TIMEOUT_SECONDS with a
# stderr breadcrumb. Mirrors gate.py's SERVO_GATE_TIMEOUT pattern.
_CLAUDE_TIMEOUT_ENV_VAR = "SERVO_CLAUDE_TIMEOUT"

# Status taxonomy for the summary line's `final_oracle_status`. Mirrors the
# gate.py status strings so consumers can pivot on the same values across
# both per-iteration and summary lines.
STATUS_PASS = "pass"
STATUS_BELOW_THRESHOLD = "below_threshold"
STATUS_ENV_ERROR = "env_error"

# Terminal-reason taxonomy. Slice 003-05 closes the set with
# `oracle_plateau` and `verdict_schema_mismatch`. Keep the strings stable —
# they are part of the loop's structured-output contract.
REASON_ORACLE_PASSED = "oracle_passed"
REASON_MAX_ITERATIONS_REACHED = "max_iterations_reached"
REASON_COST_CEILING_REACHED = "cost_ceiling_reached"
REASON_CONTEXT_FULL = "context_full"
REASON_INTERRUPTED = "interrupted"
REASON_ORACLE_PLATEAU = "oracle_plateau"
REASON_VERDICT_SCHEMA_MISMATCH = "verdict_schema_mismatch"
REASON_CLAUDE_INVOCATION_FAILED = "claude_invocation_failed"
REASON_GATE_INVOCATION_FAILED = "gate_invocation_failed"
REASON_TARGET_MISSING = "target_missing"
REASON_TARGET_NOT_DIRECTORY = "target_not_directory"
REASON_MANIFEST_MISSING = "manifest_missing"
REASON_ORACLE_MISSING = "oracle_missing"
REASON_STATE_MISSING = "state_missing"
REASON_STATE_SCHEMA_MISMATCH = "state_schema_mismatch"
REASON_CLAUDE_VERSION_MISMATCH = "claude_version_mismatch"
REASON_RUN_ID_COLLISION = "run_id_collision"

# Slice 003-07 preflight refusal shared by both drivers (ADR-0008 V4): a
# scheduled / unattended run against a dirty working tree can score leftover
# uncommitted state as a spurious immediate pass. On by default; `--allow-dirty`
# opts out; a non-git target skips the check entirely.
REASON_DIRTY_TREE = "dirty_tree"

# Slice 016-02 execution-plan consumption (ADR-0016). `--plan <path>` reads a
# compiled `plan.json`'s `budget` + `driver` as run defaults; every read failure
# is a fail-closed rc=2 refusal with a structured stderr reason, mirroring the
# `state_missing` / `state_schema_mismatch` resume-refusal style. `loop.py`
# consumes `provenance: compiled` plans only — a `human_edited` plan could carry
# a loosened brake, so it is refused pending 016-03's clamp (ADR-0016 "clamp,
# never loosen"; A2 in the slice).
PLAN_SCHEMA_VERSION = 1
PROVENANCE_COMPILED = "compiled"
REASON_PLAN_MISSING = "plan_missing"
REASON_PLAN_MALFORMED = "plan_malformed"
REASON_PLAN_SCHEMA_MISMATCH = "plan_schema_mismatch"
REASON_PLAN_REQUIRES_CLAMP = "plan_requires_clamp"
# The four budget knobs a compiled plan can supply as run defaults, mapped to
# the `loop.py` CLI flag they default. Loop-only brakes (context-fill / plateau)
# are dropped under the goal driver exactly as explicit flags are (slice AC3).
_PLAN_BUDGET_KEYS = (
    "max_iterations",
    "cost_ceiling_usd",
    "context_fill_threshold",
    "plateau_window",
)

# Slice 003-04 state-file constants (per ADR-0004).
STATE_SCHEMA_VERSION = 1
STATE_FILE_NAME = "state.json"

# Slice 003-08: the detached `--background` child's stdout/stderr land here, a
# sibling of `state.json` in the run dir.
BACKGROUND_LOG_NAME = "background.log"
STATE_TMP_SUFFIX = ".tmp"  # written then os.replace'd for atomicity
RUN_ID_MAX_ATTEMPTS = 3  # initial + 2 retries before refusing

# Status for AC9's "signal arrived before scoring finished" case. Distinct
# from STATUS_ENV_ERROR so a forensic reader can tell "loop was interrupted
# mid-iteration" apart from "gate.py refused or oracle env-errored."
STATUS_UNKNOWN_INTERRUPTED = "unknown_interrupted"

# Per-invocation timeout for `claude --version` capture (AC2 schema field).
# Short bound — the command should return in <1s on a healthy install.
CLAUDE_VERSION_TIMEOUT_SECONDS = 10

# Standard Unix convention for "process was interrupted by SIGINT" — AC9.
EXIT_INTERRUPTED = 130

# gate.py lives at a sibling skill path. Resolve once at import time so a
# repeated `subprocess.run` cost stays trivial.
GATE_PATH = Path(__file__).resolve().parent.parent / "quality-gate" / "gate.py"

# This file's own path. Slice 003-08 re-execs it as the detached child of a
# `--background` launch: `sys.executable <_LOOP_PY> <target> --driver goal …`
# runs the goal loop in a new OS session (see `_build_detached_child_argv`).
_LOOP_PY = Path(__file__).resolve()

# Slice 003-07 (ADR-0008 V4): the clone-portable location for gate.py inside the
# target. Spec 004's `hook.py` already PREFERS this relative path when baking the
# meta-judge command (`$CLAUDE_PROJECT_DIR/.claude/skills/servo-quality-gate/
# gate.py`); this slice makes vendoring a guardrail-layer responsibility so the
# meta-judge + the goal/Routine driver resolve the oracle relative to the target
# after a clone instead of baking servo's absolute install path (which fails open
# in a clone). Kept in sync with hook.py's `_resolve_gate_py`.
VENDORED_GATE_REL = Path(".claude") / "skills" / "servo-quality-gate" / "gate.py"

# ===========================================================================
# Slice 003-06 goal-driver constants (ADR-0008 rebase)
# ===========================================================================

# The loop drivers. `loop` (slices 003-01..05) is the hand-rolled external-driver
# path — the portable layer for hook-restricted / non-Claude-Code hosts; `goal`
# (003-06) delegates continuation to Claude Code's `/goal` primitive while servo
# keeps the guardrail + oracle layer. `auto` (003-07, the default) picks the best
# available path for the host via a deterministic host-support probe.
DRIVER_LOOP = "loop"
DRIVER_GOAL = "goal"
DRIVER_AUTO = "auto"

# Slice 003-07 host-scope routing (ADR-0008 V3 / Assumption 7). `/goal` is a
# Claude Code primitive introduced in 2.1.139; a host whose `claude` predates
# that (or is absent / non-Claude) cannot run the goal driver. Probed
# deterministically off `claude --version` so `auto` can route without spending
# an API call, and so an explicit `--driver goal` on an unsupported host refuses
# upfront rather than burning a turn to discover it.
GOAL_MIN_VERSION = (2, 1, 139)
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

# The oracle-verdict sentinel (AC2). A SINGLE pinned shape used by BOTH the
# loop-body prompt instruction (what the agent is told to print each turn) AND
# the transcript-scan parser (what the driver greps for, and what the `/goal`
# condition fact-checks):
#   SERVO_ORACLE_VERDICT exit=<rc> status=<pass|fail> composite=<c> threshold=<t>
SENTINEL_PREFIX = "SERVO_ORACLE_VERDICT"

# Strict matcher: REQUIRES the composite=/threshold= tail. The bare substring
# `SERVO_ORACLE_VERDICT exit=0 status=pass` (which the `/goal` condition text
# itself carries) and the placeholder instruction line (`status=<status>`) both
# fail this — so neither is miscounted as a real oracle pass (AC2 bare-substring
# guard). Capturing groups: exit, status, composite, threshold.
_SENTINEL_RE = re.compile(
    r"SERVO_ORACLE_VERDICT\s+exit=(\S+)\s+status=(\S+)\s+"
    r"composite=(\S+)\s+threshold=(\S+)"
)

# The bare form the `/goal` completion condition fact-checks (AC1). Deliberately
# WITHOUT the composite=/threshold= tail so it reads as a cue, never a self-
# satisfying pass under `_SENTINEL_RE`.
SENTINEL_PASS_BARE = f"{SENTINEL_PREFIX} exit=0 status=pass"

# Claude result `subtype` values a `/goal` run emits — empirically re-confirmed
# at implementation on claude 2.1.175 (folds in the DoR's open string-capture
# item; matches ADR-0008 V2): success → `success` (terminal_reason=`completed`);
# turn cap → `error_max_turns` (terminal_reason=`max_turns`); budget cap →
# `error_max_budget_usd`. (`--max-turns` is functional though hidden from
# `claude --help` — never infer flag availability from `--help`.)
SUBTYPE_SUCCESS = "success"
SUBTYPE_ERROR_MAX_TURNS = "error_max_turns"
SUBTYPE_ERROR_MAX_BUDGET = "error_max_budget_usd"

# Goal-mode terminal reasons (AC4/AC5). Distinct from the loop-mode taxonomy:
# the goal driver runs a single `claude -p` + one final authoritative gate.py,
# so its halt reasons key on the `/goal` result subtype and the final gate.
# `cost_ceiling_reached` is shared with loop mode (REASON_COST_CEILING_REACHED).
REASON_ORACLE_PASS = "oracle_pass"
REASON_ORACLE_BELOW_THRESHOLD = "oracle_below_threshold"
REASON_ORACLE_DISAGREEMENT = "oracle_disagreement"
REASON_ITERATION_CAP_REACHED = "iteration_cap_reached"
REASON_GOAL_UNAVAILABLE = "goal_unavailable"
REASON_GOAL_RESUME_UNSUPPORTED = "goal_resume_unsupported"

# Slice 003-07: fail-closed when the clone-portable gate.py can't be vendored
# into the target (e.g. `.claude` is an unexpected non-directory, or perms block
# the write). Without a resolvable oracle the goal driver has no authority, so it
# refuses rather than running unguarded.
REASON_GATE_VENDOR_FAILED = "gate_vendor_failed"

# Slice 003-08 (ADR-0008 rebase, detach-and-schedule): `--background` launches
# the goal driver in a detached OS session so a long unattended run survives the
# terminal closing. `detached` is the PARENT's provisional terminal reason — the
# run continues in the child; the real outcome lands in `state.json` as the child
# progresses. `detach_failed` is the fail-closed reason when the child can't be
# spawned (e.g. the background log can't be opened).
REASON_DETACHED = "detached"
REASON_DETACH_FAILED = "detach_failed"

# `/goal` refusal under hook restrictions (AC6 / ADR-0008 V3). When
# `disableAllHooks` / `allowManagedHooksOnly` is set, `/goal` refuses verbatim
# ("/goal can't run while hooks are restricted ..."). Two detection signals
# (see `_detect_goal_unavailable`): the discriminating refusal SENTENCE (safe
# to match anywhere in the transcript), and the managed-settings KEYS — which
# only count when corroborated by a zero-turn run, since an agent's own
# *successful* work could legitimately surface those key names (e.g. a task
# that audits or edits a settings file), and must not be mis-flagged.
_GOAL_REFUSAL_RE = re.compile(r"can'?t run while hooks are restricted", re.IGNORECASE)
_GOAL_HOOK_KEYS_RE = re.compile(r"disableAllHooks|allowManagedHooksOnly")

# Signal-handler state: incremented on each delivery of SIGINT/SIGTERM.
# First delivery sets the flag and forwards the signal to the active
# subprocess (so claude / gate.py exit promptly rather than running to
# completion); the loop checks the flag at iteration boundaries and after
# each subprocess returns. Second delivery bypasses cleanup
# (`os._exit(130)`) — the escape hatch documented in AC9 for a hung trap.
_interrupt_count = 0
_interrupt_signo: Optional[int] = None
_active_subprocess: Optional[subprocess.Popen] = None


def _signal_handler(signum: int, frame) -> None:
    """SIGINT/SIGTERM handler — sets a flag and forwards to active subprocess.

    Single delivery: record the signal, forward it to any active subprocess
    so the loop's `proc.communicate()` returns promptly, then let the next
    iteration boundary do the cleanup (write state, emit summary, exit 130).
    Forwarding mirrors real-terminal Ctrl-C behavior: in a foreground
    process group, the shell sends SIGINT to every member of the group, so
    the child claude would naturally die alongside the parent loop. In
    tests (`proc.send_signal`), only the loop's PID gets the signal — the
    forward is what makes the test scenario equivalent to the real one.

    Double delivery (second Ctrl-C, or any second signal): bypass cleanup
    via `os._exit(130)` so a hung trap handler can never wedge a
    user-interrupt forever.

    The handler itself is allocation-light — Python's documentation warns
    that signal handlers should be small. State updates happen at the
    iteration boundary, not here.
    """
    global _interrupt_count, _interrupt_signo
    _interrupt_count += 1
    _interrupt_signo = signum
    if _active_subprocess is not None:
        try:
            _active_subprocess.send_signal(signum)
        except (ProcessLookupError, OSError):
            pass
    if _interrupt_count >= 2:
        os._exit(EXIT_INTERRUPTED)


def _install_signal_handlers() -> None:
    """Install SIGINT/SIGTERM handlers. Called from main(), not at import.

    Installing at module import would clobber signal handlers in any
    importer (the unit tests that import `_extract_context_fill_ratio`
    directly, future callers that embed the module). Tests that exercise
    signal handling spawn loop.py as a subprocess; the handlers install
    inside that subprocess only.
    """
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


def _was_interrupted() -> bool:
    return _interrupt_count > 0


def _agent_for_iteration(iteration: int) -> str:
    """Pick the agent for iteration N (1-indexed).

    Odd iters → runner; even iters → judge. Hardcoded alternation per
    slice 003-05 DoR; ADR-0003 commits to this two-agent roster. A future
    `--agent-pattern` flag could let callers override this, but today the
    alternation is the contract.
    """
    return AGENT_RUNNER if iteration % 2 == 1 else AGENT_JUDGE


def _parse_verdict_block(
    agent_text: str,
) -> tuple[Optional[dict], Optional[str]]:
    """Extract the last fenced ```verdict``` block and validate AC10.

    Returns `(fields, None)` on success, where `fields` is a dict of
    key→string-value pairs parsed from the block. Returns `(None, breadcrumb)`
    on AC10 refusal paths: (a) the block is present but `schema_version`
    field is absent (or not the first non-empty line); (b) `schema_version`
    is present but ≠ 1; (c) `schema_version` is present but is a quoted
    string (`schema_version: "1"`) or otherwise non-integer.

    A SEPARATE return shape — `(None, None)` — signals "no verdict block
    found in the output at all." Per the slice 003-05 design, that's
    informational, not a refusal: agents *should* emit a block, but the
    loop continues if they don't (the next iteration's prompt just won't
    include a "last verdict" section). AC10's three refusal paths assume
    a block exists; "no block" is a fourth, looser case.
    """
    matches = list(_VERDICT_BLOCK_RE.finditer(agent_text))
    if not matches:
        return None, None  # no block — informational, not a refusal
    block_body = matches[-1].group(1)
    lines = [line for line in block_body.splitlines() if line.strip()]
    if not lines:
        return None, "verdict block is empty"
    first_line = lines[0].strip()
    if not first_line.startswith("schema_version:"):
        return None, (
            f"verdict block first key is not schema_version "
            f"(got {first_line[:60]!r}); expected version 1"
        )
    raw_sv = first_line.split(":", 1)[1].strip()
    # Reject quoted-string values explicitly: AC10c case `schema_version: "1"`.
    if raw_sv.startswith(("\"", "'")):
        return None, (
            f"verdict block schema_version is a string ({raw_sv!r}); "
            f"expected unquoted integer {VERDICT_SCHEMA_VERSION}"
        )
    try:
        sv = int(raw_sv)
    except ValueError:
        return None, (
            f"verdict block schema_version is non-integer ({raw_sv!r}); "
            f"expected {VERDICT_SCHEMA_VERSION}"
        )
    if sv != VERDICT_SCHEMA_VERSION:
        return None, (
            f"verdict block schema_version is {sv}; "
            f"expected {VERDICT_SCHEMA_VERSION}"
        )

    fields: dict = {"schema_version": sv}
    for line in lines[1:]:
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fields[key.strip()] = val.strip()
    return fields, None


def _assemble_iteration_prompt(
    seed: str, last_oracle: Optional[dict], last_verdict: Optional[dict],
) -> str:
    """Build the per-iteration prompt block sent to claude (AC8).

    Iter 1 (no priors): the seed prompt verbatim.
    Iter 2+: seed + a clearly-delimited block carrying the last oracle JSON
    and the last verdict block, so the next agent (runner OR judge) can
    branch on what happened the previous turn.

    Format is documented in `agents/runner.md` and `agents/judge.md` so
    agents know how to read the prompt.
    """
    if last_oracle is None and last_verdict is None:
        return seed
    parts = [seed.rstrip(), "", "---", "Context from prior iteration:"]
    if last_oracle is not None:
        parts.extend([
            "",
            "Last oracle output (`gate.py --json`):",
            "```json",
            json.dumps(last_oracle, indent=2),
            "```",
        ])
    if last_verdict is not None:
        # Render the verdict back as a fenced block so the agent reads the
        # same shape it's expected to emit on its own turn.
        verdict_lines = ["```verdict"]
        # schema_version first (parser invariant), then everything else in
        # insertion order.
        verdict_lines.append(
            f"schema_version: {last_verdict.get('schema_version', VERDICT_SCHEMA_VERSION)}"
        )
        for key, val in last_verdict.items():
            if key == "schema_version":
                continue
            verdict_lines.append(f"{key}: {val}")
        verdict_lines.append("```")
        parts.extend([
            "",
            "Last agent verdict:",
            *verdict_lines,
        ])
    parts.append("---")
    return "\n".join(parts) + "\n"


def _check_plateau(
    history: list, window: int, noise_floor: float = 0.0,
) -> bool:
    """True iff the last `window` iterations are all non-improving.

    "Non-improving" = composite ≤ max(prior composites) + `noise_floor`. For
    window=M, requires at least M+1 entries in `history` (one baseline + M
    non-improving). Equivalent formulation: the global max of all composites
    does not exceed the max of composites excluding the last M iterations by
    more than the noise floor. AC3 pins the `≤` direction (equality counts as
    non-improving).

    `window <= 0` disables the gate (AC4). Entries missing a numeric
    `composite` are ignored (defensive — env-error iterations carry
    composite=None in the history; they don't contribute to the plateau
    judgement).

    `noise_floor` (ADR-0005 clause 4, δ): an improvement must exceed
    `earlier_max + noise_floor` to reset the plateau; sub-δ wobble reads as
    flat. Defaults to 0.0 (legacy strict-`≤` behaviour). This is the one
    additive change the frozen-eval contract requires of `loop.py`.
    """
    if window <= 0:
        return False
    composites = [
        e.get("composite") for e in history
        if isinstance(e.get("composite"), (int, float))
        and not isinstance(e.get("composite"), bool)
    ]
    if len(composites) < window + 1:
        return False
    earlier_max = max(composites[:-window])
    overall_max = max(composites)
    return overall_max <= earlier_max + noise_floor


# Test hook: when set, `_generate_run_id` returns comma-separated values
# from this env var in order (one per call). After exhaustion, falls back
# to normal generation. Lets `RunIdCollisionTests` deterministically seed
# the next-generated ids so collision retry can be exercised without
# racing the wall clock.
_TEST_RUN_IDS_ENV = "SERVO_TEST_RUN_IDS"
_test_run_id_idx = 0


def _generate_run_id() -> str:
    """Run-id per ADR-0004: timestamp prefix + short random suffix.

    Shape `YYYYMMDDTHHMMSS-XXXX` (15 + 1 + 4 = 20 chars). Human-readable,
    sortable across runs without parsing, collision-resistant under spec
    005's parallel-variant scenario. Slice 003-04 wires the bounded-retry
    collision policy on `mkdir(.../runs/<run-id>/, exist_ok=False)` in
    `_create_run_dir` below; this function is the per-attempt suffix
    regenerator.

    Test hook: `$SERVO_TEST_RUN_IDS` (comma-separated) overrides generation
    for the first N calls in this process; afterwards, normal random
    generation resumes. Used by `RunIdCollisionTests` to deterministically
    drive the retry path.
    """
    global _test_run_id_idx
    test_ids_env = os.environ.get(_TEST_RUN_IDS_ENV)
    if test_ids_env:
        ids = [s for s in test_ids_env.split(",") if s]
        if _test_run_id_idx < len(ids):
            run_id = ids[_test_run_id_idx]
            _test_run_id_idx += 1
            return run_id
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    suffix = secrets.token_hex(2)  # 4 hex chars ≈ 16 bits ≈ 65k entropy
    return f"{ts}-{suffix}"


def _generate_preflight_run_id() -> str:
    """Run-id for preflight-refusal summaries (informational only).

    Identical wire-shape to `_generate_run_id` but always uses the wall
    clock + `secrets.token_hex`, bypassing the `SERVO_TEST_RUN_IDS` test
    hook. This keeps `RunIdCollisionTests` honest: only ids consumed by
    `_create_run_dir`'s allocation attempts count against the seeded
    list. Without this split, the pre-allocation refusal slot would
    silently eat one test id and make a triple-collision seed only force
    two real collisions.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    suffix = secrets.token_hex(2)
    return f"{ts}-{suffix}"


def _runs_dir(target: Path) -> Path:
    return target / ".servo" / "runs"


def _state_path_for(target: Path, run_id: str) -> Path:
    return _runs_dir(target) / run_id / STATE_FILE_NAME


def _create_run_dir(target: Path) -> tuple[Optional[Path], Optional[str], list[str]]:
    """Create `<target>/.servo/runs/<run-id>/` with bounded collision retry.

    Per ADR-0004 (and slice 003-04 AC10): on `FileExistsError`, regenerate
    the random suffix (timestamp prefix preserved within a second) and
    retry — up to `RUN_ID_MAX_ATTEMPTS` total. After exhaustion, return
    `(None, None, attempted_run_ids)` so the caller can refuse with rc=2 /
    `reason=run_id_collision` and a stderr breadcrumb naming the
    colliding ids.

    Returns `(run_dir, run_id, attempted)` on success. `attempted` is the
    list of ids that failed before success (empty on first-try success).
    """
    runs_dir = _runs_dir(target)
    runs_dir.mkdir(parents=True, exist_ok=True)
    attempted: list[str] = []
    for _ in range(RUN_ID_MAX_ATTEMPTS):
        run_id = _generate_run_id()
        run_dir = runs_dir / run_id
        try:
            run_dir.mkdir(exist_ok=False)
        except FileExistsError:
            attempted.append(run_id)
            continue
        return run_dir, run_id, attempted
    return None, None, attempted


def _atomic_write_state(state: dict, state_path: Path) -> None:
    """Write the full state payload atomically (ADR-0004's atomic-write contract).

    Writes to `state.json.tmp`, then `os.replace`s onto `state.json`.
    `os.replace` is atomic on POSIX and on NTFS, so a Ctrl-C / SIGTERM /
    power loss mid-write can never leave a torn file. Stamps
    `last_updated_at` at write time so each on-disk snapshot has a fresh
    timestamp without callers having to remember.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = state_path.with_name(state_path.name + STATE_TMP_SUFFIX)
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, state_path)


def _load_state(state_path: Path) -> Optional[dict]:
    """Read a state.json from disk. None on absent/unparseable/non-dict.

    Caller distinguishes "file missing" from "file malformed" by checking
    `state_path.exists()` first; this helper collapses the two into None
    when called against a known-present path.
    """
    if not state_path.exists():
        return None
    try:
        data = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _get_claude_version() -> Optional[str]:
    """Capture `claude --version` for forensic persistence (AC2).

    Returns the stripped stdout on success, or None on any failure (binary
    absent, non-zero exit, timeout, OSError, empty output). None at write
    time means the field is null in the state file — distinguishable from a
    missing key. AC5's `claude_version_mismatch` refusal compares None to
    None as equal (same install state), so a fresh-run-without-claude /
    resume-without-claude pair won't trip the version-mismatch refusal
    spuriously.

    Uses Popen + `_active_subprocess` registration so a SIGINT during the
    version capture is forwarded to the child rather than waiting for the
    10s timeout (consistent with the rest of the slice 003-04 subprocess
    design).
    """
    global _active_subprocess
    try:
        proc = subprocess.Popen(
            ["claude", "--version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except (FileNotFoundError, OSError):
        return None
    _active_subprocess = proc
    try:
        try:
            stdout, _stderr = proc.communicate(
                timeout=CLAUDE_VERSION_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return None
    finally:
        _active_subprocess = None
    if proc.returncode != 0:
        return None
    out = stdout.strip()
    return out or None


# ===========================================================================
# Slice 003-07 host-scope routing (ADR-0008 V3 / Assumption 7)
#
# A single auditable decision — which driver runs, and the settings/version
# facts that forced it — productionized from `adr-0008-experiments/v3_audit_env.py`.
# ===========================================================================


def _parse_claude_version(version_str: Optional[str]) -> Optional[tuple[int, int, int]]:
    """Extract a (major, minor, patch) tuple from a `claude --version` string.

    Tolerant of trailing text (`2.1.175 (Claude Code)`) and pre-release suffixes
    (`1.0.0-mock`). Returns None when no `N.N.N` triple is present.
    """
    if not version_str:
        return None
    m = _VERSION_RE.search(version_str)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def _goal_primitive_available() -> tuple[bool, Optional[str], Optional[str]]:
    """Is the `/goal` primitive available on this host? (AC4 host-support probe.)

    Deterministic from `claude --version`: `/goal` shipped in GOAL_MIN_VERSION.
    Returns `(available, version_str, reason)` — `reason` is a breadcrumb only
    when unavailable (binary absent, version unparseable, or too old).
    """
    version_str = _get_claude_version()
    parsed = _parse_claude_version(version_str)
    if parsed is None:
        reason = (
            "claude binary not found on PATH" if version_str is None
            else f"claude --version {version_str!r} is unparseable"
        )
        return False, version_str, reason
    if parsed < GOAL_MIN_VERSION:
        need = ".".join(str(n) for n in GOAL_MIN_VERSION)
        return False, version_str, (
            f"claude {version_str} predates the /goal primitive (needs >= {need})"
        )
    return True, version_str, None


def _managed_settings_paths() -> list[Path]:
    """Platform-specific managed-settings.json locations (per Claude Code docs).

    `SERVO_MANAGED_SETTINGS_PATH` overrides the OS default: a path (possibly
    absent) for unusual installs, or empty string for "no managed layer." This
    is the seam that keeps subprocess-level routing tests hermetic on hosts that
    happen to ship a real managed-settings.json (e.g. MDM-managed CI). Otherwise
    production reads the real OS paths. Mirrors `adr-0008-experiments/v3_audit_env.py`.
    """
    override = os.environ.get("SERVO_MANAGED_SETTINGS_PATH")
    if override is not None:
        return [Path(override)] if override else []
    sysname = platform.system()
    if sysname == "Darwin":
        return [Path("/Library/Application Support/ClaudeCode/managed-settings.json")]
    if sysname == "Windows":
        return [Path(os.path.expandvars(r"%PROGRAMDATA%\ClaudeCode\managed-settings.json"))]
    return [Path("/etc/claude-code/managed-settings.json")]


def _load_settings_file(path: Path) -> Optional[dict]:
    """Parse a settings.json layer. None when absent; `{__parse_error__: ...}`
    on malformed JSON (so the audit can report it without crashing)."""
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except OSError as exc:
        return {"__parse_error__": str(exc)}
    except json.JSONDecodeError as exc:
        return {"__parse_error__": str(exc)}


def _audit_hook_settings(target: Path) -> dict:
    """Inspect the settings hierarchy for the switches that disable `/goal`.

    Productionized from `v3_audit_env.py`. `disableAllHooks` truthy at ANY layer,
    or `allowManagedHooksOnly` truthy in the MANAGED layer, disables BOTH `/goal`
    and servo's (project, non-managed) meta-judge (ADR-0008 V3 / settled
    grounding). Returns a structured, auditable result:

        {hooks_permitted: bool, forcing_layer: str|None, layers: [per-layer dict]}

    `forcing_layer` is the first layer+key that forced the restriction (e.g.
    `"project-local:disableAllHooks"`), so the routing decision names exactly
    what disabled it.
    """
    layers: list[tuple[str, Path, bool]] = [
        ("user", Path.home() / ".claude" / "settings.json", False),
        ("project", target / ".claude" / "settings.json", False),
        ("project-local", target / ".claude" / "settings.local.json", False),
    ] + [("managed", p, True) for p in _managed_settings_paths()]

    findings: list[dict] = []
    forcing_layer: Optional[str] = None
    for name, path, is_managed in layers:
        entry = {
            "layer": name, "path": str(path), "present": False,
            "disableAllHooks": False, "allowManagedHooksOnly": False,
            "parse_error": None, "forces": False,
        }
        data = _load_settings_file(path)
        if data is None:
            findings.append(entry)
            continue
        if isinstance(data, dict) and "__parse_error__" in data:
            entry["parse_error"] = data["__parse_error__"]
            findings.append(entry)
            continue
        entry["present"] = True
        dah = bool(data.get("disableAllHooks"))
        # allowManagedHooksOnly only binds in the managed tier (per the docs);
        # in a non-managed layer it is recorded but inert.
        amho = bool(data.get("allowManagedHooksOnly"))
        entry["disableAllHooks"] = dah
        entry["allowManagedHooksOnly"] = amho
        forces_here = dah or (amho and is_managed)
        if forces_here:
            entry["forces"] = True
            if forcing_layer is None:
                key = "disableAllHooks" if dah else "allowManagedHooksOnly"
                forcing_layer = f"{name}:{key}"
        findings.append(entry)

    return {
        "hooks_permitted": forcing_layer is None,
        "forcing_layer": forcing_layer,
        "layers": findings,
    }


def _decide_route(target: Path, requested_driver: str) -> dict:
    """Resolve which driver runs (AC4) and record why (AC5). Never raises.

    Eligibility for the goal driver = `/goal` available (version probe) AND hooks
    permitted (settings audit). Routing:
      - `loop`  → always the hand-rolled driver (the portable path).
      - `goal`  → the goal driver if eligible; otherwise `refused=True` (an
                  explicit force on an unsupported host refuses; per 003-06 AC6).
      - `auto`  → the goal driver when eligible, else a fail-safe downgrade to
                  the loop driver (the always-works path).
    """
    audit = _audit_hook_settings(target)
    goal_available, version_str, goal_reason = _goal_primitive_available()
    hooks_permitted = audit["hooks_permitted"]
    eligible = hooks_permitted and goal_available

    if not hooks_permitted:
        ineligible_reason = f"hooks restricted ({audit['forcing_layer']})"
    elif not goal_available:
        ineligible_reason = goal_reason
    else:
        ineligible_reason = None

    refused = False
    if requested_driver == DRIVER_LOOP:
        chosen = DRIVER_LOOP
    elif requested_driver == DRIVER_GOAL:
        chosen = DRIVER_GOAL
        refused = not eligible
    else:  # DRIVER_AUTO
        chosen = DRIVER_GOAL if eligible else DRIVER_LOOP

    return {
        "requested_driver": requested_driver,
        "chosen_driver": chosen,
        "goal_eligible": eligible,
        "refused": refused,
        "ineligible_reason": ineligible_reason,
        "hooks_permitted": hooks_permitted,
        "forcing_layer": audit["forcing_layer"],
        "goal_available": goal_available,
        "claude_version": version_str,
        "audit": audit,
    }


def _format_routing_explanation(verdict: dict, target: Path) -> str:
    """Render `--explain-routing` output: the verdict + the layer that forced it
    (AC5). Human-readable + greppable; the routing decision is auditable without
    running anything."""
    eligible = "YES" if verdict["goal_eligible"] else "NO"
    lines = [
        f"servo routing verdict for {target}:",
        f"  requested driver : {verdict['requested_driver']}",
        f"  chosen driver    : {verdict['chosen_driver']}",
        f"  /goal eligible   : {eligible}",
    ]
    if verdict["ineligible_reason"]:
        lines.append(f"  ineligible because: {verdict['ineligible_reason']}")
    if verdict["refused"]:
        lines.append("  NOTE: explicit --driver goal on an unsupported host "
                     "would refuse (rc=2); use --driver loop or auto.")
    lines.append(f"  claude version   : {verdict['claude_version'] or '(not found)'}")
    lines.append(f"  /goal available  : {'YES' if verdict['goal_available'] else 'NO'}")
    permitted = (
        "YES" if verdict["hooks_permitted"]
        else f"NO  (forced by {verdict['forcing_layer']})"
    )
    lines.append(f"  hooks permitted  : {permitted}")
    lines.append("  settings layers:")
    for entry in verdict["audit"]["layers"]:
        flags = []
        if entry["parse_error"]:
            state = f"⚠ PARSE ERROR: {entry['parse_error']}"
        elif not entry["present"]:
            state = "absent"
        else:
            if entry["disableAllHooks"]:
                flags.append("disableAllHooks=true")
            if entry["allowManagedHooksOnly"]:
                flags.append("allowManagedHooksOnly=true")
            state = "present  " + ("  ".join(flags) if flags else "(no relevant keys)")
        marker = "  ← forces" if entry["forces"] else ""
        lines.append(f"    {entry['layer']:14} {entry['path']}  — {state}{marker}")
    return "\n".join(lines) + "\n"


def _build_initial_state(
    *, run_id: str, target: Path, prompt: str,
    max_iterations: int, cost_ceiling: float,
    context_fill_threshold: float, plateau_window: int,
    plateau_noise_floor: float,
    claude_version: Optional[str],
) -> dict:
    """Construct the canonical fresh-run state dict (ADR-0004 schema).

    Additive fields beyond ADR-0004's canonical list:
    - `prompt` (slice 003-04): persists the seed prompt so `--resume` can
      replay it without forcing the user to remember it.
    - `plateau_window` (slice 003-05): persists the plateau-detection cap
      so `--resume` preserves the original brake.
    - `last_verdict` / `last_oracle_json` (slice 003-05): persist the
      prior iteration's verdict block + gate JSON for prompt assembly on
      resumed runs.

    All four are documented in the slice deviation logs. ADR-0004's
    "pure additive changes MAY keep version at 1" clause covers them.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "run_id": run_id,
        "started_at": now_iso,
        "last_updated_at": now_iso,
        "target_path": str(target),
        "prompt": prompt,
        "current_session_id": "",
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "cost_ceiling_usd": cost_ceiling,
        "cumulative_cost_usd": 0.0,
        "cumulative_input_tokens": 0,
        "cumulative_output_tokens": 0,
        "context_fill_threshold": context_fill_threshold,
        "last_context_fill_ratio": None,
        "plateau_window": plateau_window,
        "plateau_noise_floor": plateau_noise_floor,
        "oracle_score_history": [],
        "last_terminal_reason": None,
        "claude_version": claude_version,
        "last_verdict": None,
        "last_oracle_json": None,
    }


def _emit_json(payload: dict) -> None:
    """Emit a single JSON line on stdout, flushed immediately.

    Every emission is auto-prefixed with `schema_version` (matching gate.py's
    ADR-0002 contract and ADR-0004's state-file framing) so callers can't
    forget. Per-iteration consumers (and the spec 005 race driver) are
    line-oriented; flushing makes the loop's stdout safe to pipe through
    `tee` / `jq -c` / a watching shell loop without buffering surprises.
    """
    out = {"schema_version": SCHEMA_VERSION, **payload}
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


def _resolve_claude_timeout() -> Optional[float]:
    """Pick the effective `claude -p` timeout in seconds. None = unbounded.

    Precedence: SERVO_CLAUDE_TIMEOUT env var → DEFAULT_CLAUDE_TIMEOUT_SECONDS.
    `0` (env var) disables the bound entirely — useful for tests or callers
    enforcing a wall-clock budget out-of-band. Malformed env var falls back
    to the default with a stderr breadcrumb. Mirrors gate.py's
    `_resolve_timeout` pattern.
    """
    env_value = os.environ.get(_CLAUDE_TIMEOUT_ENV_VAR)
    if env_value is None:
        return float(DEFAULT_CLAUDE_TIMEOUT_SECONDS)
    try:
        parsed = float(env_value)
    except ValueError:
        sys.stderr.write(
            f"loop: ignoring malformed {_CLAUDE_TIMEOUT_ENV_VAR}={env_value!r}; "
            f"using default {DEFAULT_CLAUDE_TIMEOUT_SECONDS}s\n"
        )
        return float(DEFAULT_CLAUDE_TIMEOUT_SECONDS)
    return None if parsed == 0 else parsed


def _refuse_preflight(
    *, run_id: str, reason: str, message: str,
    cost_ceiling: float, context_fill_threshold: float,
) -> int:
    """Emit a stderr breadcrumb + a summary JSON line; return rc=2.

    No per-iteration line is emitted because preflight refusal happens
    before iteration 1 runs. The summary line still carries `run_id` so a
    caller can correlate the refusal with whatever orchestration context
    invoked the loop. `cost_ceiling_usd` and `context_fill_threshold` are
    included even on preflight so consumers see the configured bounds
    regardless of how the run ended. `context_fill_ratio` is null on
    preflight (no iteration ran, so no usage observed). Slice 003-04 reuses
    this helper for `state_missing` / `state_schema_mismatch` /
    `claude_version_mismatch` / `run_id_collision` resume refusals — the
    summary shape is identical, only the `terminal_reason` and stderr
    message differ.
    """
    sys.stderr.write(f"loop: {message}\n")
    _emit_json({
        "terminal_reason": reason,
        "iterations_completed": 0,
        "cumulative_cost_usd": 0.0,
        "cost_ceiling_usd": cost_ceiling,
        "context_fill_threshold": context_fill_threshold,
        "context_fill_ratio": None,
        "final_oracle_status": STATUS_ENV_ERROR,
        "run_id": run_id,
    })
    return EXIT_ENV_ERROR


def _refuse_plan(*, reason: str, message: str) -> int:
    """Fail-closed refusal for a plan-read error (slice 016-02, rc=2).

    Emitted before any run starts (before routing, run-dir creation, or a
    state.json write), so — unlike `_refuse_preflight` — there is no run-id yet
    and no configured budget to echo. The summary shape mirrors the preflight
    refusal (a single JSON line + a stderr breadcrumb) with the plan-read
    `terminal_reason`; the closed reasons are `plan_missing` / `plan_malformed`
    / `plan_schema_mismatch` / `plan_requires_clamp`.
    """
    sys.stderr.write(f"loop: {message}\n")
    _emit_json({
        "terminal_reason": reason,
        "iterations_completed": 0,
        "cumulative_cost_usd": 0.0,
        "final_oracle_status": STATUS_ENV_ERROR,
    })
    return EXIT_ENV_ERROR


def _load_plan(
    plan_path: Path,
) -> tuple[Optional[dict], Optional[tuple[str, str]]]:
    """Read + validate a compiled `plan.json` (slice 016-02, ADR-0016).

    Returns `(plan_dict, None)` on success, or `(None, (reason, message))` when
    the plan cannot be consumed — fail-closed, never a partial read. The caller
    turns the `(reason, message)` pair into an rc=2 `_refuse_plan`. Validation,
    in order:

    - **missing file** → `plan_missing`.
    - **unreadable / malformed JSON, or a non-object top level** →
      `plan_malformed` (mirrors `_load_state`'s absent/unparseable/non-dict
      collapse; a bare list is not a plan).
    - **`schema_version` != PLAN_SCHEMA_VERSION** (incl. missing) →
      `plan_schema_mismatch` (mirrors the resume `state_schema_mismatch` guard).
    - **`provenance` != "compiled"** → `plan_requires_clamp`: a `human_edited`
      (or any non-compiled) plan could carry a loosened brake, so it is refused
      pending 016-03's clamp (A2; ADR-0016 "clamp, never loosen").

    This slice consumes only the `budget` + `driver` fields; `prompt_ref`
    rendering is out of scope (016-05), so the plan's other fields are inert.
    """
    if not plan_path.exists():
        return None, (
            REASON_PLAN_MISSING,
            f"plan file not found at {plan_path}; check the --plan path",
        )
    try:
        data = json.loads(plan_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None, (
            REASON_PLAN_MALFORMED,
            f"plan file at {plan_path} is unreadable or not valid JSON",
        )
    if not isinstance(data, dict):
        return None, (
            REASON_PLAN_MALFORMED,
            f"plan file at {plan_path} is not a JSON object",
        )
    schema = data.get("schema_version")
    if schema != PLAN_SCHEMA_VERSION:
        return None, (
            REASON_PLAN_SCHEMA_MISMATCH,
            f"plan schema_version mismatch: file has {schema!r}, this loop.py "
            f"expects {PLAN_SCHEMA_VERSION}",
        )
    provenance = data.get("provenance")
    if provenance != PROVENANCE_COMPILED:
        return None, (
            REASON_PLAN_REQUIRES_CLAMP,
            f"plan provenance is {provenance!r}; loop.py consumes only "
            f"{PROVENANCE_COMPILED!r} plans. A non-compiled (e.g. human_edited) "
            f"plan may carry a loosened brake and needs clamping before Run — "
            f"deferred to slice 016-03",
        )
    return data, None


def _resolve_from_plan(
    cli_value: Optional[object],
    plan_budget: Optional[dict],
    key: str,
) -> Optional[object]:
    """Precedence resolver: explicit CLI flag > plan value > loop.py default.

    `cli_value` is the argparse value (`None` == flag not passed). When the
    caller passed the flag, that wins. Otherwise the plan's budget value (if
    present) is used. When neither supplies a value, `None` is returned so the
    downstream `run_loop` / `run_goal_loop` applies its built-in `DEFAULT_*`.

    Crucially, a plan value is returned as a fresh local — it is NOT written
    back into `args.*`. The goal-driver brake-drop (slice 003-06) warns iff
    `args.<brake> is not None`; keeping the plan value out of `args` is what
    lets a plan-sourced loop-only brake be dropped silently under the goal
    driver (slice AC3) instead of misattributed to the user.
    """
    if cli_value is not None:
        return cli_value
    if plan_budget is not None and key in plan_budget:
        return plan_budget[key]
    return None


def _target_preflight_error(target: Path) -> Optional[tuple[str, str]]:
    """Existence checks shared by both drivers (slice 003-06 extraction).

    Returns `(reason, message)` on the first failure, or None when
    target / manifest / oracle all exist. Reason strings mirror gate.py's
    taxonomy (`target_missing`, `target_not_directory`, `manifest_missing`,
    `oracle_missing`) per AC4: both drivers defer to gate.py's vocabulary so
    downstream consumers pivot on the same strings. Existence-only check —
    malformed manifest, non-executable oracle, etc., surface from gate.py at
    score time as `oracle_status=env_error`, not a driver-level refusal.
    """
    if not target.exists():
        return REASON_TARGET_MISSING, f"target does not exist: {target}"
    if not target.is_dir():
        return REASON_TARGET_NOT_DIRECTORY, f"target is not a directory: {target}"
    manifest_path = target / ".servo" / "install.json"
    if not manifest_path.exists():
        return REASON_MANIFEST_MISSING, (
            f".servo/install.json not found at {manifest_path}; "
            f"run /servo:scaffold-init first"
        )
    oracle_path = target / "oracle.sh"
    if not oracle_path.exists():
        return REASON_ORACLE_MISSING, (
            f"oracle.sh not found at {oracle_path}; run /servo:scaffold-init first"
        )
    return None


# Cap on how many dirty paths the refusal breadcrumb enumerates, so a wildly
# dirty tree can't spam the log; the count is always reported in full.
_DIRTY_PATHS_SHOWN = 20


def _is_git_work_tree(target: Path) -> bool:
    """True iff `target` is inside a git working tree (AC3 non-git skip)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except (FileNotFoundError, OSError):
        return False  # git not installed → treat as non-git (skip the check)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _dirty_tree_paths(target: Path) -> Optional[list[str]]:
    """Tracked-file dirty paths, or None when clean / not-a-git-repo (AC2/AC3).

    - Non-git target → None (AC3 skip; no false refusal).
    - Git repo → `git status --porcelain`; any tracked-file change (staged or
      unstaged; porcelain XY status other than `??`) makes the tree dirty.
      Untracked files (`??`) are NOT "changes to tracked files" per AC2's
      wording — and excluding them means servo's own run artifacts (`.servo/`,
      the vendored gate.py) never self-trip the brake on a later run.
    - Pathological case (valid work tree but `git status` itself errors) → None
      (skip) rather than a false refusal; the brake is best-effort over git.
    """
    if not _is_git_work_tree(target):
        return None
    proc = subprocess.run(
        ["git", "-C", str(target), "status", "--porcelain"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        return None
    dirty: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        xy = line[:2]
        if xy == "??":
            continue  # untracked — not a tracked-file change
        # porcelain v1: "XY <path>"; a rename shows "orig -> new" in the path.
        dirty.append(line[3:].strip())
    return dirty or None


def _dirty_tree_message(paths: list[str]) -> str:
    """Refusal breadcrumb naming the dirty paths (AC2), bounded in length."""
    shown = paths[:_DIRTY_PATHS_SHOWN]
    more = "" if len(paths) <= _DIRTY_PATHS_SHOWN else f" (+{len(paths) - _DIRTY_PATHS_SHOWN} more)"
    return (
        f"refusing to run against a dirty working tree: {len(paths)} uncommitted "
        f"change(s) to tracked file(s): {', '.join(shown)}{more}. Commit or stash "
        f"them, or pass --allow-dirty for an intentional dirty run."
    )


def _preflight(
    target: Path, run_id: str, *,
    cost_ceiling: float, context_fill_threshold: float,
) -> Optional[int]:
    """Validate target / manifest / oracle exist (loop mode). rc on refusal, None on pass.

    Thin wrapper over `_target_preflight_error` that renders a loop-shaped
    refusal summary via `_refuse_preflight`. The goal driver shares the same
    existence checks but renders a goal-shaped summary (`_refuse_goal`).
    """
    err = _target_preflight_error(target)
    if err is not None:
        reason, message = err
        return _refuse_preflight(
            run_id=run_id, reason=reason, message=message,
            cost_ceiling=cost_ceiling,
            context_fill_threshold=context_fill_threshold,
        )
    return None


def _compute_per_iter_budget(cost_ceiling: float, cumulative: float) -> float:
    """Per-iteration `--max-budget-usd` value to pass to `claude -p`.

    When cost_ceiling > 0: remaining = cost_ceiling - cumulative, floored at
    MIN_BUDGET_FLOOR_USD. The caller is expected to have already gated on
    `_budget_floor_hit` before reaching here, so the `max(..., floor)` clamp
    is belt-and-suspenders.

    When cost_ceiling <= 0 (disabled): DEFAULT_PER_ITER_BUDGET_USD so a
    runaway agentic turn still has a brake even when the caller is
    enforcing a budget out-of-band.
    """
    if cost_ceiling <= 0:
        return DEFAULT_PER_ITER_BUDGET_USD
    return max(cost_ceiling - cumulative, MIN_BUDGET_FLOOR_USD)


def _extract_context_fill_ratio(
    claude_data: dict,
) -> tuple[Optional[float], Optional[str]]:
    """Compute the context-fill ratio from claude's per-iteration JSON.

    Ratio = `(usage.input_tokens + usage.cache_read_input_tokens +
    usage.cache_creation_input_tokens) / modelUsage.<model>.contextWindow`,
    per the spike's empirical schema capture. Returns `(ratio, None)` on
    success or `(None, breadcrumb)` when any required field is missing or
    malformed (AC8 fail-open path: the gate refuses to enforce; the iteration
    cap and cost ceiling still apply). The breadcrumb is a single-line
    stderr-suitable message naming the specific cause.

    Multi-model invocations are unlikely under `claude -p` single-turn use
    (the spike captured one model per iteration); when more than one entry
    appears under `modelUsage`, the first dict with a positive integer
    `contextWindow` wins. This is deterministic given Python 3.7+ dict
    insertion order — adequate for the single-model expected case and
    documented as a known approximation for the multi-model hypothetical.
    """
    usage = claude_data.get("usage")
    if not isinstance(usage, dict):
        return None, "context-fill gate: claude JSON missing `usage` block"
    try:
        in_tokens = int(usage.get("input_tokens", 0) or 0)
        cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
        cache_create = int(usage.get("cache_creation_input_tokens", 0) or 0)
    except (TypeError, ValueError):
        return None, "context-fill gate: claude JSON `usage` tokens are non-numeric"
    input_total = in_tokens + cache_read + cache_create

    model_usage = claude_data.get("modelUsage")
    if not isinstance(model_usage, dict) or not model_usage:
        return None, "context-fill gate: claude JSON missing `modelUsage` block"

    context_window: Optional[int] = None
    for model_entry in model_usage.values():
        if not isinstance(model_entry, dict):
            continue
        cw = model_entry.get("contextWindow")
        if isinstance(cw, bool):
            continue  # bool is a subclass of int — exclude explicitly
        if isinstance(cw, (int, float)) and cw > 0:
            context_window = int(cw)
            break
    if context_window is None:
        return None, (
            "context-fill gate: claude JSON missing "
            "`modelUsage.<model>.contextWindow`"
        )

    return input_total / context_window, None


def _budget_floor_hit(cost_ceiling: float, cumulative: float) -> bool:
    """True iff cumulative is within MIN_BUDGET_FLOOR_USD of the ceiling.

    Used as a pre-iteration gate so the loop never invokes claude with an
    effectively-zero budget. Returns False when the ceiling is disabled
    (cost_ceiling <= 0).
    """
    if cost_ceiling <= 0:
        return False
    return (cost_ceiling - cumulative) < MIN_BUDGET_FLOOR_USD


def _settings_args(target: Path) -> list[str]:
    """`--settings <file>` for the target's own `.claude/settings.json`, else `[]`.

    Bug 002: a headless `claude -p` inherits the host's default (prompt-on-tool)
    permission mode, which denies Write/Edit/Bash unattended — so a target that
    pre-authorizes its tools in a committed `.claude/settings.json` still can't
    edit files. Forwarding that file lets such a target run unattended. Only the
    target's OWN committed settings are forwarded (never a synthesized bypass
    mode), so host-level managed policy still governs; when the target declares
    no settings the flag is omitted and the host default is preserved.
    """
    settings = target / ".claude" / "settings.json"
    if settings.is_file():
        return ["--settings", str(settings)]
    return []


def _invoke_claude(
    prompt: str, target: Path, *,
    max_budget_usd: float,
    timeout_seconds: Optional[float] = None,
    session_id: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> tuple[Optional[dict], Optional[str]]:
    """Invoke `claude -p --output-format json --max-budget-usd <budget> "<prompt>"`.

    `session_id` (slice 003-04): when non-empty, the invocation includes
    `--resume <session_id>` so the conversation continues across iterations
    and across resumed `loop.py` runs. Fresh-run iter 1 passes `None` and
    creates a new session; subsequent iterations and resumed-run iter N+1
    carry the prior session forward.

    Returns `(parsed_json, None)` on success or `(None, breadcrumb)` on
    failure (AC9). Success includes the budget-exceeded path: when claude
    honors `--max-budget-usd` it may exit non-zero with a parseable JSON
    body — that JSON is the iteration's result, not an invocation failure.
    Per AC9's literal wording ("exit non-zero WITHOUT parseable JSON output"
    = failure), the split is:

      - exit 0 + parseable JSON dict        → success
      - exit non-zero + parseable JSON dict → success (budget_exceeded path)
      - exit 0 + unparseable/non-dict       → failure ("JSON parse error")
      - exit non-zero + unparseable/non-dict → failure ("without JSON output")
      - timeout / FileNotFoundError / OSError → failure (specific breadcrumb)

    `timeout_seconds=None` means unbounded (used by tests that lower the
    bound to 1s via SERVO_CLAUDE_TIMEOUT to avoid 30-minute waits). On
    `subprocess.TimeoutExpired`, Python sends SIGKILL to claude.

    Implementation note (slice 003-04): uses `subprocess.Popen` +
    `communicate` instead of `subprocess.run` so the signal handler can
    forward SIGINT/SIGTERM to the live subprocess via `_active_subprocess`.
    Behavior is otherwise identical to `subprocess.run`.
    """
    global _active_subprocess
    cmd: list[str] = ["claude", "-p", "--output-format", "json"]
    cmd.extend(["--max-budget-usd", f"{max_budget_usd:.6f}"])
    cmd.extend(_settings_args(target))
    if agent_name:
        cmd.extend(["--agent", agent_name])
    if session_id:
        cmd.extend(["--resume", session_id])
    cmd.append(prompt)
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(target),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except FileNotFoundError:
        # Binary not on PATH — Python's execvp raises this before the child
        # process gets a chance to run.
        return None, "claude not on PATH"
    except OSError as exc:
        return None, f"OS error invoking claude: {exc}"

    _active_subprocess = proc
    try:
        try:
            stdout, _stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # AC9-adjacent: timeout is a kind of OS-level failure. Kill the
            # child and reap; reuse the uniform `claude_invocation_failed`
            # terminal_reason per AC9's uniformity rule.
            proc.kill()
            proc.communicate()
            return None, f"claude -p timed out after {timeout_seconds}s (killed)"
    finally:
        _active_subprocess = None

    parse_error: Optional[str] = None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        parse_error = f"claude JSON parse error: {exc.msg} (line {exc.lineno})"
        data = None
    else:
        if not isinstance(data, dict):
            parse_error = "claude JSON parse error: output is not a JSON object"
            data = None

    if data is not None:
        # Bug 001: a parseable envelope is not automatically a scored iteration.
        # A hard invocation failure (auth / API / rate-limit) also returns valid
        # JSON, but with `is_error: true` and no work done — scoring it masks the
        # real cause as an oracle plateau. The ONLY legitimate `is_error: true`
        # envelopes in loop mode are the `--max-budget-usd` / `--max-turns` halts
        # (they carry real partial work worth scoring), so exclude just those.
        if data.get("is_error") and str(data.get("subtype") or "") not in (
            SUBTYPE_ERROR_MAX_BUDGET, SUBTYPE_ERROR_MAX_TURNS,
        ):
            status = data.get("api_error_status")
            detail = f" (api_error_status={status})" if status else ""
            raw = str(data.get("result") or data.get("subtype") or "error").strip()
            first_line = raw.splitlines()[0] if raw else "error"
            return None, f"claude -p invocation failed{detail}: {first_line[:200]}"
        # Treat as success regardless of exit code — `--max-budget-usd` halt
        # can produce non-zero + parseable JSON, and that's the iteration's
        # result not an invocation failure.
        return data, None

    if proc.returncode != 0:
        # Non-zero exit + unparseable/non-dict body = real invocation failure.
        # Keep the AC9 wording stable for downstream consumers.
        return None, f"claude -p exited {proc.returncode} without JSON output"

    # Exit 0 with unparseable / non-dict output → AC9 "JSON parse error" path.
    return None, parse_error


def _vendored_gate_path(target: Path) -> Path:
    """Absolute path of the clone-portable gate.py copy inside `target`."""
    return target / VENDORED_GATE_REL


def _ensure_vendored_gate(target: Path) -> tuple[Optional[Path], Optional[str]]:
    """Ensure `<target>/.claude/skills/servo-quality-gate/gate.py` exists + is current (AC1).

    Idempotent: copies servo's own `gate.py` when the vendored copy is absent or
    byte-stale; a no-op (no rewrite) when it is already byte-identical, so the
    preflight is cheap on every run. Returns `(vendored_path, None)` on success
    or `(None, breadcrumb)` when servo's gate.py can't be read or the destination
    can't be written — the caller fails closed (a goal/Routine run has no oracle
    authority without a resolvable gate.py).

    Why vendor at all (ADR-0008 V4): the meta-judge resolves the oracle on a
    *relative* gate.py path after a clone; a non-vendored install bakes servo's
    absolute path and fails open in a clone. `hook.py:_resolve_gate_py` already
    prefers this path — this makes putting the file there a driver responsibility.
    """
    src = GATE_PATH
    dest = _vendored_gate_path(target)
    try:
        src_bytes = src.read_bytes()
    except OSError as exc:
        return None, f"cannot read servo's gate.py at {src}: {exc}"
    try:
        if dest.is_file() and dest.read_bytes() == src_bytes:
            return dest, None  # present and current → no rewrite
        dest.parent.mkdir(parents=True, exist_ok=True)
        # copy2 preserves gate.py's mode; the file is always invoked via
        # `sys.executable`, so the exec bit is not load-bearing.
        shutil.copy2(src, dest)
    except OSError as exc:
        return None, f"cannot vendor gate.py into target at {dest}: {exc}"
    return dest, None


def _invoke_gate(target: Path, gate_path: Path = GATE_PATH) -> Optional[dict]:
    """Invoke `gate.py <target> --json`. Return parsed JSON dict or None on parse failure.

    gate.py emits exactly one JSON line on stdout regardless of exit code
    (per ADR-0002). We don't pass through gate's exit code as the loop's
    exit code — the loop's exit code is governed by the iteration outcome,
    not by gate's pass/fail/env-error signal on any single iteration.

    `gate_path` (slice 003-07): which gate.py to run. Loop mode uses servo's own
    `GATE_PATH` (the external-driver path runs on servo's host); the goal driver
    passes the target's *vendored* copy so the authoritative final score resolves
    on the same clone-portable path the meta-judge uses.

    Slice 003-04: registers the Popen as `_active_subprocess` so the signal
    handler can forward SIGINT/SIGTERM to gate.py (so the loop's wait
    returns promptly under interrupt).
    """
    global _active_subprocess
    cmd = [sys.executable, str(gate_path), str(target), "--json"]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    _active_subprocess = proc
    try:
        stdout, stderr = proc.communicate()
    finally:
        _active_subprocess = None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        # Truncate the diagnostic dump — a misbehaving gate could otherwise
        # spam megabytes into our stderr. 500 chars each is enough to ID the
        # failure shape without flooding the log.
        sys.stderr.write(
            f"loop: gate.py emitted unparseable output (rc={proc.returncode}); "
            f"stdout[:500]={stdout[:500]!r} stderr[:500]={stderr[:500]!r}\n"
        )
        return None


def _summary_payload(state: dict, *, terminal_reason: str, final_oracle_status: str) -> dict:
    """Build the standard summary JSON payload from the state dict.

    Centralizes the shape so every halt path (normal, interrupted, refusal)
    emits the same fields. `terminal_reason` and `final_oracle_status` are
    callsite-specific; everything else is read from `state`.
    """
    return {
        "terminal_reason": terminal_reason,
        "iterations_completed": state["iteration_count"],
        "cumulative_cost_usd": state["cumulative_cost_usd"],
        "cost_ceiling_usd": state["cost_ceiling_usd"],
        "context_fill_threshold": state["context_fill_threshold"],
        "context_fill_ratio": state.get("last_context_fill_ratio"),
        "plateau_window": state.get("plateau_window", DEFAULT_PLATEAU_WINDOW),
        "plateau_noise_floor": state.get(
            "plateau_noise_floor", DEFAULT_PLATEAU_NOISE_FLOOR,
        ),
        "oracle_score_history": state.get("oracle_score_history", []),
        "final_oracle_status": final_oracle_status,
        "run_id": state["run_id"],
    }


def _finalize_state_and_summary(
    state: dict, state_path: Path, *,
    terminal_reason: str, final_oracle_status: str,
) -> None:
    """Stamp the state's last_terminal_reason, write atomically, emit summary.

    Used at every loop terminus (normal halt, interrupted, claude/gate
    invocation failure within an iteration). The atomic write is the
    foundation of AC9's signal-safety guarantee — even if SIGINT arrives
    mid-write, `os.replace` is atomic on POSIX/NTFS, so the on-disk file
    is either the prior content or the new content, never torn.
    """
    state["last_terminal_reason"] = terminal_reason
    _atomic_write_state(state, state_path)
    _emit_json(_summary_payload(
        state,
        terminal_reason=terminal_reason,
        final_oracle_status=final_oracle_status,
    ))


def run_loop(
    target: Path, *,
    prompt: Optional[str],
    max_iterations: Optional[int],
    cost_ceiling: Optional[float],
    context_fill_threshold: Optional[float],
    plateau_window: Optional[int] = None,
    plateau_noise_floor: Optional[float] = None,
    resume_run_id: Optional[str] = None,
    resume_anyway: bool = False,
    allow_dirty: bool = False,
) -> int:
    """Drive the iteration loop with state persistence + resume + signal handling.

    Two entry modes:
      - **Fresh run** (`resume_run_id is None`): preflight target/manifest/
        oracle; create `<target>/.servo/runs/<run-id>/` (with collision
        retry per AC10); build initial state with CLI flags applied over
        defaults; persist; iterate.
      - **Resume** (`resume_run_id` given): load state from
        `<target>/.servo/runs/<run-id>/state.json`; refuse on missing /
        schema-mismatch / claude-version-mismatch (escapable via
        `resume_anyway`); apply CLI overrides over persisted values;
        iterate from `iteration_count + 1`.

    State is atomically rewritten after every iteration (success or
    failure to score), so an interruption loses at most the in-flight
    iteration's work. Signal handlers (SIGINT/SIGTERM) forward to the
    active subprocess and set a flag the loop polls at iteration
    boundaries.
    """
    _install_signal_handlers()

    claude_timeout_seconds = _resolve_claude_timeout()

    # ---- Phase 1: resolve state (fresh init or resume load) -----------------
    if resume_run_id is not None:
        # Resume path. Validate the state file BEFORE any preflight against
        # the target — the user gave us a run-id, so the right failure mode
        # is `state_missing` not `manifest_missing`.
        state_path = _state_path_for(target, resume_run_id)
        # Use a synthesised refusal run_id (the same one the user passed)
        # so the summary's `run_id` matches what they invoked with.
        # For refusal summaries, cost_ceiling/threshold come from the CLI
        # overrides (or defaults) since we don't know the persisted values
        # yet.
        refusal_ceiling = (
            cost_ceiling if cost_ceiling is not None else DEFAULT_COST_CEILING_USD
        )
        refusal_threshold = (
            context_fill_threshold if context_fill_threshold is not None
            else DEFAULT_CONTEXT_FILL_THRESHOLD
        )
        if not state_path.exists():
            return _refuse_preflight(
                run_id=resume_run_id,
                reason=REASON_STATE_MISSING,
                message=(
                    f"state file not found at {state_path}; "
                    f"verify <run-id> against `<target>/.servo/runs/`"
                ),
                cost_ceiling=refusal_ceiling,
                context_fill_threshold=refusal_threshold,
            )
        state = _load_state(state_path)
        if state is None:
            return _refuse_preflight(
                run_id=resume_run_id,
                reason=REASON_STATE_MISSING,
                message=(
                    f"state file at {state_path} is missing or malformed; "
                    f"--resume-anyway does not bypass parse errors"
                ),
                cost_ceiling=refusal_ceiling,
                context_fill_threshold=refusal_threshold,
            )

        # Slice 003-06 AC7: a goal-driven run cannot be resumed (detachment is
        # 003-08). Such a state carries `driver: "goal"`; refuse with a clear
        # breadcrumb rather than replaying it as a hand-rolled loop.
        if state.get("driver") == DRIVER_GOAL:
            return _refuse_preflight(
                run_id=resume_run_id,
                reason=REASON_GOAL_RESUME_UNSUPPORTED,
                message=(
                    f"run-id {resume_run_id} was created by --driver goal; "
                    f"resuming a goal-driven run is out of scope (slice 003-08). "
                    f"Start a fresh run with --driver goal (no --resume)."
                ),
                cost_ceiling=refusal_ceiling,
                context_fill_threshold=refusal_threshold,
            )

        persisted_schema = state.get("state_schema_version")
        if persisted_schema != STATE_SCHEMA_VERSION and not resume_anyway:
            return _refuse_preflight(
                run_id=resume_run_id,
                reason=REASON_STATE_SCHEMA_MISMATCH,
                message=(
                    f"state_schema_version mismatch: file has "
                    f"{persisted_schema!r}, this loop.py expects "
                    f"{STATE_SCHEMA_VERSION}. Use --resume-anyway to bypass "
                    f"(risky: silent mis-decoding may corrupt the run)"
                ),
                cost_ceiling=refusal_ceiling,
                context_fill_threshold=refusal_threshold,
            )

        current_claude_version = _get_claude_version()
        persisted_version = state.get("claude_version")
        if persisted_version != current_claude_version and not resume_anyway:
            return _refuse_preflight(
                run_id=resume_run_id,
                reason=REASON_CLAUDE_VERSION_MISMATCH,
                message=(
                    f"claude_version mismatch: state file has "
                    f"{persisted_version!r}, current `claude --version` is "
                    f"{current_claude_version!r}. Use --resume-anyway to "
                    f"bypass (risky: session_id semantics or JSON shape "
                    f"may have changed between versions)"
                ),
                cost_ceiling=refusal_ceiling,
                context_fill_threshold=refusal_threshold,
            )

        # Apply CLI overrides on top of persisted values (AC4). `None` means
        # "user didn't pass the flag; keep persisted value." A CLI-supplied
        # value wins over persistence.
        if prompt is not None:
            state["prompt"] = prompt
        if max_iterations is not None:
            state["max_iterations"] = max_iterations
        if cost_ceiling is not None:
            state["cost_ceiling_usd"] = cost_ceiling
        if context_fill_threshold is not None:
            state["context_fill_threshold"] = context_fill_threshold
        if plateau_window is not None:
            state["plateau_window"] = plateau_window
        if plateau_noise_floor is not None:
            state["plateau_noise_floor"] = plateau_noise_floor
        # Backfill defaults for state files written before slice 003-05.
        # Same state_schema_version=1; additive fields per ADR-0004's
        # "pure additive changes MAY keep version at 1" clause.
        state.setdefault("plateau_window", DEFAULT_PLATEAU_WINDOW)
        state.setdefault("plateau_noise_floor", DEFAULT_PLATEAU_NOISE_FLOOR)
        state.setdefault("last_verdict", None)
        state.setdefault("last_oracle_json", None)

        run_id = state["run_id"]
        # Synchronise last_context_fill_ratio across the read so the
        # pre-iter gate sees the prior iteration's ratio without an extra
        # state read inside the loop.
        last_context_fill_ratio = state.get("last_context_fill_ratio")
    else:
        # Fresh run. Standard preflight + run-id dir creation + state init.
        # `_generate_preflight_run_id()` is used for any preflight-refusal
        # summary line; it deliberately bypasses the test hook so that
        # `RunIdCollisionTests` can count `_create_run_dir`'s attempts
        # without one being consumed pre-allocation.
        # Apply defaults for None values.
        if max_iterations is None:
            max_iterations = DEFAULT_MAX_ITERATIONS
        if cost_ceiling is None:
            cost_ceiling = DEFAULT_COST_CEILING_USD
        if context_fill_threshold is None:
            context_fill_threshold = DEFAULT_CONTEXT_FILL_THRESHOLD
        if plateau_window is None:
            plateau_window = DEFAULT_PLATEAU_WINDOW
        if plateau_noise_floor is None:
            plateau_noise_floor = DEFAULT_PLATEAU_NOISE_FLOOR
        rc = _preflight(
            target, _generate_preflight_run_id(),
            cost_ceiling=cost_ceiling,
            context_fill_threshold=context_fill_threshold,
        )
        if rc is not None:
            return rc

        # AC2/AC3: refuse a FRESH run against a dirty tree (a scheduled run could
        # otherwise score leftover state as a spurious pass). Resume deliberately
        # skips this — a resumed loop's tree is legitimately dirty from the prior
        # iterations' agent mutations. `--allow-dirty` opts out; non-git skips.
        if not allow_dirty:
            dirty = _dirty_tree_paths(target)
            if dirty:
                return _refuse_preflight(
                    run_id=_generate_preflight_run_id(),
                    reason=REASON_DIRTY_TREE,
                    message=_dirty_tree_message(dirty),
                    cost_ceiling=cost_ceiling,
                    context_fill_threshold=context_fill_threshold,
                )

        run_dir, run_id, attempted = _create_run_dir(target)
        if run_dir is None or run_id is None:
            attempt_list = ", ".join(attempted) if attempted else "(none)"
            # The first attempted id is the natural forensic stamp — it's
            # the run-id the user "would have gotten" if not for the
            # collision. Falls back to a synthesized id when `attempted` is
            # empty (shouldn't happen at RUN_ID_MAX_ATTEMPTS >= 1).
            refusal_run_id = (
                attempted[0] if attempted else _generate_preflight_run_id()
            )
            return _refuse_preflight(
                run_id=refusal_run_id,
                reason=REASON_RUN_ID_COLLISION,
                message=(
                    f"could not allocate a fresh run-id after "
                    f"{RUN_ID_MAX_ATTEMPTS} attempts; colliding ids: "
                    f"{attempt_list}"
                ),
                cost_ceiling=cost_ceiling,
                context_fill_threshold=context_fill_threshold,
            )

        # prompt is required for fresh runs (argparse enforced); narrow type.
        assert prompt is not None
        # Capture `claude --version` for forensics (AC2). Done here, not
        # before preflight, so refused-target invocations don't subprocess
        # out to claude unnecessarily.
        current_claude_version = _get_claude_version()
        state = _build_initial_state(
            run_id=run_id, target=target, prompt=prompt,
            max_iterations=max_iterations, cost_ceiling=cost_ceiling,
            context_fill_threshold=context_fill_threshold,
            plateau_window=plateau_window,
            plateau_noise_floor=plateau_noise_floor,
            claude_version=current_claude_version,
        )
        state_path = _state_path_for(target, run_id)
        _atomic_write_state(state, state_path)
        last_context_fill_ratio = None

    # ---- Phase 2: iteration loop --------------------------------------------
    final_oracle_status = STATUS_ENV_ERROR
    # Populate final_oracle_status from prior history (resume case): the
    # most recent oracle score's status is the "last known" status; an
    # empty history (fresh run) keeps the env_error default.
    history = state.get("oracle_score_history") or []
    if history:
        final_oracle_status = history[-1].get("status", STATUS_ENV_ERROR)
    starting_iteration = state["iteration_count"] + 1
    terminal_reason = REASON_MAX_ITERATIONS_REACHED
    halted_on_pass = False
    halted_on_cost = False
    halted_on_context = False
    halted_on_plateau = False
    for iteration in range(starting_iteration, state["max_iterations"] + 1):
        # Pre-iteration interrupt check (AC9). If the signal arrived between
        # iterations (or before iter 1), we never invoke claude / gate.
        # `final_oracle_status` is `unknown_interrupted` when no iteration
        # has yet been gate-scored (history empty / first iter); otherwise
        # it carries the last successfully-scored iteration's status, since
        # that scoring did complete before the interrupt arrived. The
        # spec's literal AC9 wording only pins the during-claude and
        # during-gate cases as `unknown_interrupted`; choosing
        # `unknown_interrupted` for pre-iter-1 too (rather than the
        # `env_error` default) is more accurate — the loop was interrupted,
        # not env-errored.
        if _was_interrupted():
            interrupted_status = (
                final_oracle_status if history else STATUS_UNKNOWN_INTERRUPTED
            )
            _finalize_state_and_summary(
                state, state_path,
                terminal_reason=REASON_INTERRUPTED,
                final_oracle_status=interrupted_status,
            )
            return EXIT_INTERRUPTED

        # Pre-iteration context-fill gate (slice 003-03 AC1/AC2/AC4/AC6).
        if (
            state["context_fill_threshold"] > 0
            and last_context_fill_ratio is not None
            and last_context_fill_ratio >= state["context_fill_threshold"]
        ):
            terminal_reason = REASON_CONTEXT_FULL
            halted_on_context = True
            break

        # Pre-iteration cost-ceiling floor check (slice 003-02 AC4).
        if _budget_floor_hit(state["cost_ceiling_usd"], state["cumulative_cost_usd"]):
            terminal_reason = REASON_COST_CEILING_REACHED
            halted_on_cost = True
            break

        per_iter_budget = _compute_per_iter_budget(
            state["cost_ceiling_usd"], state["cumulative_cost_usd"],
        )
        # Pass --resume <session_id> when we have one (slice 003-04). For
        # fresh-run iter 1 the session id is empty → no --resume.
        session_id_arg = state.get("current_session_id") or None
        # Slice 003-05: pick agent (runner/judge alternation) and assemble
        # the per-iteration prompt from the seed + last oracle JSON + last
        # verdict block. Iter 1 of a fresh run sends just the seed; iter 2+
        # / resumed runs send the structured assembly.
        agent_name = _agent_for_iteration(iteration)
        iteration_prompt = _assemble_iteration_prompt(
            state["prompt"],
            state.get("last_oracle_json"),
            state.get("last_verdict"),
        )
        claude_data, error = _invoke_claude(
            iteration_prompt, target,
            max_budget_usd=per_iter_budget,
            timeout_seconds=claude_timeout_seconds,
            session_id=session_id_arg,
            agent_name=agent_name,
        )

        # Interrupt-during-claude (AC9): the iteration is treated as
        # "completed for state-file purposes" with `unknown_interrupted`
        # final oracle status. Bump iteration_count, persist, emit summary.
        if _was_interrupted():
            state["iteration_count"] = iteration
            _finalize_state_and_summary(
                state, state_path,
                terminal_reason=REASON_INTERRUPTED,
                final_oracle_status=STATUS_UNKNOWN_INTERRUPTED,
            )
            return EXIT_INTERRUPTED

        if claude_data is None:
            sys.stderr.write(f"loop: {error}\n")
            _finalize_state_and_summary(
                state, state_path,
                terminal_reason=REASON_CLAUDE_INVOCATION_FAILED,
                final_oracle_status=final_oracle_status,
            )
            return EXIT_ENV_ERROR

        # Extract iteration data.
        session_id = str(claude_data.get("session_id", ""))
        try:
            cost_usd = float(claude_data.get("total_cost_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            cost_usd = 0.0
        claude_terminal_reason = str(claude_data.get("terminal_reason", ""))

        # Token tallies for AC2's cumulative_input_tokens / cumulative_output_tokens.
        usage = claude_data.get("usage") or {}
        if not isinstance(usage, dict):
            usage = {}
        try:
            iter_input_tokens = (
                int(usage.get("input_tokens", 0) or 0)
                + int(usage.get("cache_read_input_tokens", 0) or 0)
                + int(usage.get("cache_creation_input_tokens", 0) or 0)
            )
            iter_output_tokens = int(usage.get("output_tokens", 0) or 0)
        except (TypeError, ValueError):
            iter_input_tokens = 0
            iter_output_tokens = 0

        state["cumulative_cost_usd"] += cost_usd
        state["cumulative_input_tokens"] += iter_input_tokens
        state["cumulative_output_tokens"] += iter_output_tokens
        if session_id:
            state["current_session_id"] = session_id

        # Context-fill ratio (slice 003-03).
        context_fill_ratio, ratio_error = _extract_context_fill_ratio(claude_data)
        if context_fill_ratio is None and ratio_error is not None:
            sys.stderr.write(f"loop: {ratio_error}\n")
        state["last_context_fill_ratio"] = context_fill_ratio

        # Slice 003-05 AC10: parse the agent's verdict block. The agent's
        # textual output is in claude_data["result"]. The parser returns
        # (None, None) if no verdict block is present (informational — the
        # agent malfunctioned but the loop continues), (None, breadcrumb)
        # on AC10 refusal paths (block present but malformed), or
        # (fields, None) on success.
        agent_text = str(claude_data.get("result", "") or "")
        verdict_fields, verdict_error = _parse_verdict_block(agent_text)
        if verdict_error is not None:
            # AC10: refuse the run on a malformed verdict block.
            sys.stderr.write(f"loop: {verdict_error}\n")
            state["iteration_count"] = iteration
            _finalize_state_and_summary(
                state, state_path,
                terminal_reason=REASON_VERDICT_SCHEMA_MISMATCH,
                final_oracle_status=final_oracle_status,
            )
            return EXIT_ENV_ERROR
        # `verdict_fields` may be None (no block found); that's fine — the
        # next iteration's prompt assembly will just omit the verdict section.
        state["last_verdict"] = verdict_fields

        gate_data = _invoke_gate(target)

        # Interrupt-during-gate (AC9): same posture as interrupt-during-claude.
        # The iteration counted (claude data was extracted into state), but
        # no oracle status is recorded — `unknown_interrupted`.
        if _was_interrupted():
            state["iteration_count"] = iteration
            _finalize_state_and_summary(
                state, state_path,
                terminal_reason=REASON_INTERRUPTED,
                final_oracle_status=STATUS_UNKNOWN_INTERRUPTED,
            )
            return EXIT_INTERRUPTED

        if gate_data is None:
            # Defensive branch (ADR-0002 says gate.py always emits JSON).
            _finalize_state_and_summary(
                state, state_path,
                terminal_reason=REASON_GATE_INVOCATION_FAILED,
                final_oracle_status=STATUS_ENV_ERROR,
            )
            return EXIT_ENV_ERROR

        oracle_exit_code = int(gate_data.get("exit_code", 2))
        oracle_status = str(gate_data.get("status", STATUS_ENV_ERROR))
        oracle_composite = gate_data.get("composite")
        oracle_threshold = gate_data.get("threshold")

        # Update state with the scored iteration BEFORE emitting per-iter JSON.
        # If the user Ctrl-Cs between the gate call and the emit, the state
        # file already reflects this iteration's outcome.
        state["iteration_count"] = iteration
        state["oracle_score_history"].append({
            "iteration": iteration,
            "composite": oracle_composite,
            "threshold": oracle_threshold,
            "status": oracle_status,
        })
        state["last_terminal_reason"] = claude_terminal_reason
        state["last_oracle_json"] = gate_data
        _atomic_write_state(state, state_path)

        # Slice 003-05: per-iter JSON includes the active agent and the
        # parsed verdict fields (or null). Agents alternate runner → judge,
        # so a downstream consumer can group per-iter lines by role.
        _emit_json({
            "iteration": iteration,
            "agent": agent_name,
            "session_id": session_id,
            "cost_usd": cost_usd,
            "cumulative_cost_usd": state["cumulative_cost_usd"],
            "context_fill_ratio": context_fill_ratio,
            "verdict": verdict_fields,
            "terminal_reason": claude_terminal_reason,
            "oracle_exit_code": oracle_exit_code,
            "oracle_status": oracle_status,
            "oracle_composite": oracle_composite,
            "oracle_threshold": oracle_threshold,
            "run_id": state["run_id"],
        })

        final_oracle_status = oracle_status
        last_context_fill_ratio = context_fill_ratio

        if oracle_exit_code == 0:
            terminal_reason = REASON_ORACLE_PASSED
            halted_on_pass = True
            break

        # Post-iteration cost-ceiling check.
        if (
            state["cost_ceiling_usd"] > 0
            and state["cumulative_cost_usd"] > state["cost_ceiling_usd"]
        ):
            terminal_reason = REASON_COST_CEILING_REACHED
            halted_on_cost = True
            break

        # Slice 003-05 plateau check (AC1/AC2/AC3): after gate scoring, if
        # the last `plateau_window` iterations failed to improve over the
        # max-prior-composite, halt. AC4 disables when window==0.
        if _check_plateau(
            state["oracle_score_history"], state["plateau_window"],
            state.get("plateau_noise_floor", DEFAULT_PLATEAU_NOISE_FLOOR),
        ):
            terminal_reason = REASON_ORACLE_PLATEAU
            halted_on_plateau = True
            break

    if (
        not halted_on_pass and not halted_on_cost
        and not halted_on_context and not halted_on_plateau
    ):
        terminal_reason = REASON_MAX_ITERATIONS_REACHED

    _finalize_state_and_summary(
        state, state_path,
        terminal_reason=terminal_reason,
        final_oracle_status=final_oracle_status,
    )
    return EXIT_OK


# ===========================================================================
# Slice 003-06 — goal-driven loop (ADR-0008 rebase)
# ===========================================================================


def _compose_goal_prompt(
    seed: str, gate_path: Path = GATE_PATH, *, python: Optional[str] = None
) -> str:
    """Build the single `/goal`-driven prompt (AC1/AC2).

    `gate_path` (slice 003-07): the gate.py the in-transcript loop body is told
    to run. `run_goal_loop` passes the target's *vendored* copy so the agent's
    every-turn gate run and the driver's authoritative final run resolve the same
    clone-portable path.

    `python` (slice 003-08): the interpreter token in the gate command. Defaults
    to this host's `sys.executable` for a live `claude -p` run (so the agent's
    in-transcript gate run shares the interpreter of the authoritative
    `_invoke_gate`). The Routine emitter (`_emit_routine_prompt`) overrides it to
    a portable `python3` + a *relative* `gate_path`, because that prompt runs in a
    cloud clone where this host's absolute interpreter path is meaningless.

    Shape: a `/goal` completion condition that only FACT-CHECKS the printed
    pass sentinel, then the user's seed task, then a per-turn loop-body
    instruction to run servo:quality-gate (`gate.py --json`) and print the
    SERVO_ORACLE_VERDICT sentinel verbatim. The `/goal` evaluator confirms a
    deterministic fact (the oracle already printed a pass); it never re-judges
    — `oracle.sh` stays the authority (ADR-0008 hard constraint).

    The instruction uses placeholder tokens (`<exit_code>`, `<status>`, …), and
    the `/goal` line carries only the bare `SENTINEL_PASS_BARE` (no tail), so
    neither the prompt nor its echo can satisfy `_SENTINEL_RE`'s pass predicate.

    By default the gate command names the SAME interpreter the driver's
    authoritative `_invoke_gate` uses (`sys.executable`) so the agent's
    in-transcript gate run can't drift to a different `python3` than the final
    verdict's (the Routine emitter overrides this via `python=` — see above). The
    final `gate.py` remains the only authority regardless; this just keeps the two
    runs consistent.
    """
    python = python or sys.executable or "python3"
    return (
        f"/goal Continue working until the transcript contains a line "
        f"`{SENTINEL_PASS_BARE}` that was printed by the quality gate (step 3 "
        f"below) on a turn where the gate actually exited 0.\n"
        f"\n"
        f"{seed.rstrip()}\n"
        f"\n"
        f"On EVERY turn, after doing work toward the task above, surface the "
        f"servo quality gate's verdict so this loop can decide whether to "
        f"continue:\n"
        f"1. Run exactly: {python} {gate_path} . --json\n"
        f"2. Read the JSON it prints (fields: exit_code, status, composite, "
        f"threshold).\n"
        f"3. Print EXACTLY this one line (no code fence), substituting the real "
        f"values, where <status> is `pass` when exit_code is 0 and `fail` "
        f"otherwise:\n"
        f"   {SENTINEL_PREFIX} exit=<exit_code> status=<status> "
        f"composite=<composite> threshold=<threshold>\n"
        f"Never print the sentinel with `status=pass` unless that gate run "
        f"reported exit_code 0 this turn — the oracle, not your judgement, "
        f"decides what passes.\n"
    )


def _scan_pass_sentinel(text: str) -> bool:
    """True iff `text` carries a REAL oracle pass sentinel (AC2/AC4).

    A match counts as a pass only when the strict sentinel (with the
    composite=/threshold= tail) reports exit=0 AND status=pass. The bare
    `/goal`-condition substring (no tail) and the placeholder instruction line
    (`status=<status>`) both fail this predicate, so neither is miscounted as
    the oracle having actually passed.
    """
    for m in _SENTINEL_RE.finditer(text or ""):
        if m.group(1) == "0" and m.group(2) == "pass":
            return True
    return False


def _detect_goal_unavailable(raw_stdout: str, num_turns: int) -> bool:
    """True iff `/goal` refused to run under hook restrictions (AC6 / V3).

    Two signals, deliberately asymmetric to avoid false positives:
    - the verbatim refusal SENTENCE ("can't run while hooks are restricted")
      is specific to `/goal`'s refusal → safe to match anywhere; but
    - the managed-settings KEYS (`disableAllHooks` / `allowManagedHooksOnly`)
      could legitimately appear in an agent's own successful work, so they
      only count when corroborated by a zero-turn run (nothing actually ran —
      the V3-observed signature: `num_turns=0`, `$0`, zero hooks fired).
    """
    text = raw_stdout or ""
    if _GOAL_REFUSAL_RE.search(text):
        return True
    return num_turns == 0 and bool(_GOAL_HOOK_KEYS_RE.search(text))


def _invoke_claude_goal(
    prompt: str, target: Path, *,
    max_turns: int,
    max_budget_usd: Optional[float],
    timeout_seconds: Optional[float] = None,
) -> tuple[Optional[dict], str, Optional[str]]:
    """Invoke one `claude -p --output-format stream-json --verbose` `/goal` run.

    Hard caps ride the OUTER call (AC3): `--max-turns <max_turns>` always, and
    `--max-budget-usd <max_budget_usd>` when a positive ceiling is set — the two
    caps ADR-0008 V2 proved bind a `/goal` run. stream-json (which requires
    `--verbose` in print mode) lets the driver scan the whole transcript for the
    sentinel, not just the final message.

    Returns `(result_event, raw_stdout, breadcrumb)`. `breadcrumb` is non-None
    only on a hard invocation failure (binary missing / timeout / no parseable
    `type=result` event), mirroring `_invoke_claude`'s AC9 split. `raw_stdout`
    is always returned (even on failure) so the caller can scan it for the
    `/goal` hook-restriction refusal (AC6).
    """
    global _active_subprocess
    cmd: list[str] = [
        "claude", "-p", "--output-format", "stream-json", "--verbose",
        "--max-turns", str(max_turns),
    ]
    if max_budget_usd is not None and max_budget_usd > 0:
        cmd.extend(["--max-budget-usd", f"{max_budget_usd:.6f}"])
    # Bug 004 (parity with bug 002): forward the target's own committed
    # .claude/settings.json so a /goal run against a target that pre-authorizes
    # its tools runs unattended. Same conservative semantics as the loop driver.
    cmd.extend(_settings_args(target))
    cmd.append(prompt)
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(target),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
    except FileNotFoundError:
        return None, "", "claude not on PATH"
    except OSError as exc:
        return None, "", f"OS error invoking claude: {exc}"

    _active_subprocess = proc
    try:
        try:
            stdout, _stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return None, "", f"claude -p timed out after {timeout_seconds}s (killed)"
    finally:
        _active_subprocess = None

    result_event: Optional[dict] = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate non-JSON noise interleaved in the stream
        if isinstance(ev, dict) and ev.get("type") == "result":
            result_event = ev  # last result event wins

    if result_event is None:
        if proc.returncode != 0:
            return None, stdout, (
                f"claude -p exited {proc.returncode} without a result event"
            )
        return None, stdout, "claude -p emitted no parseable result event"
    return result_event, stdout, None


def _build_goal_state(
    *, run_id: str, target: Path, prompt: str,
    max_turns: int, cost_ceiling: float, claude_version: Optional[str],
) -> dict:
    """Goal-driver per-run state (ADR-0004 shape, goal-mode fields).

    Carries `driver: "goal"` so a later `--resume` of this run-id refuses
    (AC7). `state_schema_version` stays 1 — the goal fields are additive per
    ADR-0004's "pure additive changes MAY keep version at 1" clause.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "driver": DRIVER_GOAL,
        "run_id": run_id,
        "started_at": now_iso,
        "last_updated_at": now_iso,
        "target_path": str(target),
        "prompt": prompt,
        "max_turns": max_turns,
        "cost_ceiling_usd": cost_ceiling,
        "cumulative_cost_usd": 0.0,
        "num_turns": 0,
        "subtype": None,
        "claude_terminal_reason": None,
        "transcript_showed_pass": False,
        "final_oracle_status": None,
        "oracle_composite": None,
        "oracle_threshold": None,
        "terminal_reason": None,
        "claude_version": claude_version,
    }


def _goal_summary(
    *, run_id: str, terminal_reason: str, cumulative_cost_usd: float,
    cost_ceiling: float, max_turns: int, final_oracle_status: str,
    composite, threshold, subtype, claude_terminal_reason,
    num_turns: int, transcript_showed_pass: bool,
) -> dict:
    """Single source for the goal-mode summary line (every halt path uses it)."""
    return {
        "driver": DRIVER_GOAL,
        "terminal_reason": terminal_reason,
        "subtype": subtype,
        "claude_terminal_reason": claude_terminal_reason,
        "num_turns": num_turns,
        "cumulative_cost_usd": cumulative_cost_usd,
        "cost_ceiling_usd": cost_ceiling,
        "max_turns": max_turns,
        "final_oracle_status": final_oracle_status,
        "oracle_composite": composite,
        "oracle_threshold": threshold,
        "transcript_showed_pass": transcript_showed_pass,
        "run_id": run_id,
    }


def _refuse_goal(
    *, run_id: str, reason: str, message: str,
    cost_ceiling: float, max_turns: int,
) -> int:
    """Stderr breadcrumb + goal-shaped summary line; return rc=2 (no run dir)."""
    sys.stderr.write(f"loop: {message}\n")
    _emit_json(_goal_summary(
        run_id=run_id, terminal_reason=reason, cumulative_cost_usd=0.0,
        cost_ceiling=cost_ceiling, max_turns=max_turns,
        final_oracle_status=STATUS_ENV_ERROR, composite=None, threshold=None,
        subtype=None, claude_terminal_reason=None, num_turns=0,
        transcript_showed_pass=False,
    ))
    return EXIT_ENV_ERROR


def run_goal_loop(
    target: Path, *,
    prompt: Optional[str],
    max_iterations: Optional[int],
    cost_ceiling: Optional[float],
    resume_run_id: Optional[str] = None,
    allow_dirty: bool = False,
    run_id: Optional[str] = None,
    detached: bool = False,
) -> int:
    """Drive a single `/goal`-continuation run with servo's guardrails wired
    through the OUTER `claude -p` invocation (slice 003-06 / ADR-0008).

    The platform owns *"keep going"* (`/goal` + `--max-turns`); servo owns *"is
    it actually good, and is it safe to keep going"* — the hard caps on the
    outer call (AC3), a final authoritative `gate.py` run as the verdict (AC4),
    fail-closed handling when the transcript and the oracle disagree (AC4), and
    a refuse-don't-degrade posture when `/goal` can't run at all (AC6).
    """
    _install_signal_handlers()
    claude_timeout_seconds = _resolve_claude_timeout()

    max_turns = (
        max_iterations if max_iterations is not None else DEFAULT_MAX_ITERATIONS
    )
    ceiling = (
        cost_ceiling if cost_ceiling is not None else DEFAULT_COST_CEILING_USD
    )

    # AC7: resume of a goal-driven run is out of scope (detachment is 003-08).
    if resume_run_id is not None:
        return _refuse_goal(
            run_id=resume_run_id,
            reason=REASON_GOAL_RESUME_UNSUPPORTED,
            message=(
                "--resume is not supported with --driver goal (detachment is "
                "slice 003-08); re-run without --resume, or use --driver loop "
                "to resume a hand-rolled run"
            ),
            cost_ceiling=ceiling, max_turns=max_turns,
        )

    # Preflight (shared existence checks; goal-shaped refusal summary).
    err = _target_preflight_error(target)
    if err is not None:
        reason, message = err
        return _refuse_goal(
            run_id=_generate_preflight_run_id(), reason=reason, message=message,
            cost_ceiling=ceiling, max_turns=max_turns,
        )

    # AC2/AC3: refuse against a dirty tree before any side effects (vendoring,
    # run-dir, spend). `--allow-dirty` opts out; a non-git target skips.
    if not allow_dirty:
        dirty = _dirty_tree_paths(target)
        if dirty:
            return _refuse_goal(
                run_id=_generate_preflight_run_id(),
                reason=REASON_DIRTY_TREE, message=_dirty_tree_message(dirty),
                cost_ceiling=ceiling, max_turns=max_turns,
            )

    # AC1: vendor the clone-portable gate.py into the target. The goal driver's
    # in-transcript loop body AND its authoritative final score both resolve this
    # path, so the oracle survives a clone (ADR-0008 V4). Fail closed if it can't
    # be written — a goal run without a resolvable oracle has no authority.
    vendored_gate, vendor_err = _ensure_vendored_gate(target)
    if vendored_gate is None:
        return _refuse_goal(
            run_id=_generate_preflight_run_id(),
            reason=REASON_GATE_VENDOR_FAILED, message=str(vendor_err),
            cost_ceiling=ceiling, max_turns=max_turns,
        )

    # Allocate a run dir (same per-run-id isolation as loop mode; AC7). A detached
    # `--background` child (slice 003-08) is handed the parent's pre-allocated
    # run-id via `run_id=` so the run-id the user saw at launch is the one the
    # state file lives under — reuse that dir instead of allocating a second.
    if run_id is not None:
        run_dir = _runs_dir(target) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_dir, run_id, attempted = _create_run_dir(target)
        if run_dir is None or run_id is None:
            attempt_list = ", ".join(attempted) if attempted else "(none)"
            return _refuse_goal(
                run_id=(attempted[0] if attempted else _generate_preflight_run_id()),
                reason=REASON_RUN_ID_COLLISION,
                message=(
                    f"could not allocate a fresh run-id after {RUN_ID_MAX_ATTEMPTS} "
                    f"attempts; colliding ids: {attempt_list}"
                ),
                cost_ceiling=ceiling, max_turns=max_turns,
            )

    assert prompt is not None  # argparse enforces --prompt for goal fresh runs
    # Re-probes `claude --version` (auto/goal routing already read it via
    # `_goal_primitive_available`); a second sub-second call is cheaper than
    # threading the value across the main()→run boundary, and re-reads it at the
    # moment of state init.
    claude_version = _get_claude_version()
    state_path = _state_path_for(target, run_id)
    state = _build_goal_state(
        run_id=run_id, target=target, prompt=prompt,
        max_turns=max_turns, cost_ceiling=ceiling, claude_version=claude_version,
    )
    if detached:
        state["detached"] = True  # slice 003-08: a `--background` child run
    _atomic_write_state(state, state_path)

    def _finalize(terminal_reason, *, cumulative_cost_usd, final_oracle_status,
                  composite=None, threshold=None, subtype=None,
                  claude_terminal_reason=None, num_turns=0,
                  transcript_showed_pass=False, exit_code):
        """Persist final state + emit the goal summary; return exit_code."""
        state["terminal_reason"] = terminal_reason
        state["cumulative_cost_usd"] = cumulative_cost_usd
        state["final_oracle_status"] = final_oracle_status
        state["oracle_composite"] = composite
        state["oracle_threshold"] = threshold
        state["subtype"] = subtype
        state["claude_terminal_reason"] = claude_terminal_reason
        state["num_turns"] = num_turns
        state["transcript_showed_pass"] = transcript_showed_pass
        _atomic_write_state(state, state_path)
        _emit_json(_goal_summary(
            run_id=run_id, terminal_reason=terminal_reason,
            cumulative_cost_usd=cumulative_cost_usd, cost_ceiling=ceiling,
            max_turns=max_turns, final_oracle_status=final_oracle_status,
            composite=composite, threshold=threshold, subtype=subtype,
            claude_terminal_reason=claude_terminal_reason, num_turns=num_turns,
            transcript_showed_pass=transcript_showed_pass,
        ))
        return exit_code

    goal_prompt = _compose_goal_prompt(prompt, gate_path=vendored_gate)
    result_event, raw_stdout, error = _invoke_claude_goal(
        goal_prompt, target,
        max_turns=max_turns, max_budget_usd=ceiling,
        timeout_seconds=claude_timeout_seconds,
    )

    # Pull cost + turn count off the result event once, defensively — every
    # exit path (interrupt, goal_unavailable, the normal verdict) reports the
    # real spend, not a hardcoded $0, even when the run was cut short.
    _rev = result_event or {}
    try:
        result_cost = float(_rev.get("total_cost_usd", 0.0) or 0.0)
    except (TypeError, ValueError):
        result_cost = 0.0
    try:
        result_num_turns = int(_rev.get("num_turns", 0) or 0)
    except (TypeError, ValueError):
        result_num_turns = 0

    # Interrupt during the /goal run (Q9 posture): finalize and exit 130.
    if _was_interrupted():
        return _finalize(
            REASON_INTERRUPTED, cumulative_cost_usd=result_cost,
            final_oracle_status=STATUS_UNKNOWN_INTERRUPTED,
            subtype=_rev.get("subtype"), num_turns=result_num_turns,
            exit_code=EXIT_INTERRUPTED,
        )

    # AC6: /goal refused to run (hooks restricted) — refuse loudly, don't
    # silently degrade. The stderr names --driver loop as the portable
    # fallback. `_detect_goal_unavailable` corroborates the managed-settings
    # keys with a zero-turn run so an agent's own work mentioning those keys
    # can't spuriously flip a successful run to goal_unavailable.
    if _detect_goal_unavailable(raw_stdout, result_num_turns):
        sys.stderr.write(
            "loop: /goal did not engage — it refuses when hooks are restricted "
            "(disableAllHooks / allowManagedHooksOnly). Use --driver loop (the "
            "portable hand-rolled driver) for hook-restricted or non-Claude-Code "
            "hosts.\n"
        )
        return _finalize(
            REASON_GOAL_UNAVAILABLE, cumulative_cost_usd=result_cost,
            final_oracle_status=STATUS_ENV_ERROR,
            subtype=_rev.get("subtype"),
            claude_terminal_reason=_rev.get("terminal_reason"),
            num_turns=result_num_turns,
            exit_code=EXIT_ENV_ERROR,
        )

    # Hard invocation failure (binary missing / timeout / no result event).
    if error is not None or result_event is None:
        sys.stderr.write(f"loop: {error}\n")
        return _finalize(
            REASON_CLAUDE_INVOCATION_FAILED, cumulative_cost_usd=0.0,
            final_oracle_status=STATUS_ENV_ERROR, exit_code=EXIT_ENV_ERROR,
        )

    subtype = str(result_event.get("subtype", ""))
    claude_terminal_reason = str(result_event.get("terminal_reason", ""))
    cost_usd = result_cost
    num_turns = result_num_turns
    transcript_showed_pass = _scan_pass_sentinel(raw_stdout)

    # Bug 004 (parity with bug 001): a hard /goal invocation failure returns a
    # parseable result event with `is_error: true` (auth / API / rate-limit).
    # Surface it as claude_invocation_failed BEFORE running the final gate —
    # otherwise the gate reports the unchanged oracle state as
    # `oracle_below_threshold`, masking the real cause. The budget/turn caps are
    # `is_error: true` too but carry real work, so exclude them (handled below).
    if result_event.get("is_error") and subtype not in (
        SUBTYPE_ERROR_MAX_TURNS, SUBTYPE_ERROR_MAX_BUDGET,
    ):
        status = result_event.get("api_error_status")
        detail = f" (api_error_status={status})" if status else ""
        raw = str(result_event.get("result") or subtype or "error").strip()
        first_line = raw.splitlines()[0] if raw else "error"
        sys.stderr.write(
            f"loop: claude -p invocation failed{detail}: {first_line[:200]}\n")
        return _finalize(
            REASON_CLAUDE_INVOCATION_FAILED, cumulative_cost_usd=cost_usd,
            final_oracle_status=STATUS_ENV_ERROR, subtype=subtype,
            claude_terminal_reason=claude_terminal_reason, num_turns=num_turns,
            transcript_showed_pass=transcript_showed_pass,
            exit_code=EXIT_ENV_ERROR,
        )

    # AC4: the FINAL gate.py run is the authority — never the transcript judge.
    # Run it on every clean-return path (incl. the caps) to populate the
    # forensic `final_oracle_status`. Uses the vendored copy (003-07 AC1) so the
    # authority resolves on the same clone-portable path as the in-transcript run.
    gate_data = _invoke_gate(target, gate_path=vendored_gate)
    if gate_data is None:
        return _finalize(
            REASON_GATE_INVOCATION_FAILED, cumulative_cost_usd=cost_usd,
            final_oracle_status=STATUS_ENV_ERROR, subtype=subtype,
            claude_terminal_reason=claude_terminal_reason, num_turns=num_turns,
            transcript_showed_pass=transcript_showed_pass,
            exit_code=EXIT_ENV_ERROR,
        )
    gate_exit = int(gate_data.get("exit_code", 2))
    gate_status = str(gate_data.get("status", STATUS_ENV_ERROR))
    composite = gate_data.get("composite")
    threshold = gate_data.get("threshold")

    # AC5 terminal-reason map, subtype-first; AC4 fail-closed disagreement.
    #
    # Precedence: a hard cap (error_max_turns / error_max_budget_usd) wins over
    # the disagreement branch. Had a real pass sentinel been printed, /goal
    # would have stopped with subtype=success BEFORE the cap fired — so a cap
    # subtype means /goal never saw a pass, and the cap is the honest reason.
    # The oracle's authority is preserved regardless: the run is never reported
    # as a pass, and `final_oracle_status` carries the final gate's real verdict.
    if subtype == SUBTYPE_ERROR_MAX_TURNS:
        terminal_reason, exit_code = REASON_ITERATION_CAP_REACHED, EXIT_OK
    elif subtype == SUBTYPE_ERROR_MAX_BUDGET:
        terminal_reason, exit_code = REASON_COST_CEILING_REACHED, EXIT_OK
    elif transcript_showed_pass and gate_exit != 0:
        # The transcript printed a real pass sentinel, but the authoritative
        # final gate disagrees → fail-closed (AC4). Pins the ADR-0008 hard
        # constraint at the loop boundary: the oracle, not the transcript
        # judge, decides.
        terminal_reason, exit_code = REASON_ORACLE_DISAGREEMENT, EXIT_ENV_ERROR
    elif gate_exit == 0:
        terminal_reason, exit_code = REASON_ORACLE_PASS, EXIT_OK
    else:
        terminal_reason, exit_code = REASON_ORACLE_BELOW_THRESHOLD, EXIT_OK

    return _finalize(
        terminal_reason, cumulative_cost_usd=cost_usd,
        final_oracle_status=gate_status, composite=composite, threshold=threshold,
        subtype=subtype, claude_terminal_reason=claude_terminal_reason,
        num_turns=num_turns, transcript_showed_pass=transcript_showed_pass,
        exit_code=exit_code,
    )


# ===========================================================================
# Slice 003-08 — detach (`--background`) + Routine-ready target emit
# ===========================================================================


def _emit_routine_prompt(target: Path, seed: str) -> int:
    """Make `target` Routine-ready + print the paste-ready prompt (AC2).

    A Routine — a scheduled, unattended run on Anthropic-managed infra — is
    created from the web / desktop app, NOT the CLI (claude 2.1.175 exposes no
    `routine` / `schedule` subcommand — ADR-0008 V4 discovery). So servo can't
    *create* a Routine; what it does is make the target Routine-ready and hand the
    user the exact prompt to paste:

    1. Vendor a clone-portable `gate.py` (003-07) so the oracle resolves relative
       to `$CLAUDE_PROJECT_DIR` after the Routine clones the repo into the cloud.
    2. Emit the canonical `/goal` loop-body prompt — same shape the live goal
       driver composes — but with a PORTABLE gate command (`python3` + the
       relative vendored path), because it runs in the cloud clone, not on this
       host.

    Read-only w.r.t. the run loop: it vendors + prints, then exits 0. It does NOT
    gate on *this* host's `/goal` support — the Routine runs on a different host
    (the cloud), whose policy is captured at run time, not here.
    """
    err = _target_preflight_error(target)
    if err is not None:
        _reason, message = err
        sys.stderr.write(f"loop: {message}\n")
        return EXIT_ENV_ERROR
    vendored_gate, vendor_err = _ensure_vendored_gate(target)
    if vendored_gate is None:
        sys.stderr.write(f"loop: {vendor_err}\n")
        return EXIT_ENV_ERROR

    routine_prompt = _compose_goal_prompt(
        seed, gate_path=VENDORED_GATE_REL, python="python3"
    )
    sys.stdout.write(
        "# servo Routine-ready target\n"
        f"# Vendored clone-portable gate.py at {VENDORED_GATE_REL} (commit it).\n"
        "#\n"
        "# Create a Routine (claude.ai/code or desktop) pointed at this repo,\n"
        "# grant it Bash + Edit/Write, and paste the block below as the task.\n"
        "# The loop body runs servo:quality-gate every turn and prints the\n"
        "# SERVO_ORACLE_VERDICT sentinel; the /goal condition only fact-checks it.\n"
        "# In a Routine (one continuous invocation, no per-turn Stop hook) gate.py\n"
        "# is the authority — the meta-judge is moot (ADR-0008 V4). Start each\n"
        "# scheduled run from a clean committed baseline (fresh clone, or\n"
        "# `git reset --hard`) so leftover state can't score as a spurious pass.\n"
        "# ----- paste from here -----\n"
    )
    sys.stdout.write(routine_prompt)
    if not routine_prompt.endswith("\n"):
        sys.stdout.write("\n")
    return EXIT_OK


def _build_detached_child_argv(
    target: Path, run_id: str, *,
    prompt: str, max_iterations: Optional[int], cost_ceiling: Optional[float],
) -> list[str]:
    """argv for the detached goal-driver child of a `--background` launch (AC1).

    `--allow-dirty` is set unconditionally: the parent already ran the dirty-tree
    preflight (or the user passed `--allow-dirty`), so the child must not re-refuse
    on a tree the parent already accepted. `--_detached-run-id` hands the child the
    parent's pre-allocated run-id so both processes share one run directory.
    Resolved caps are forwarded only when explicitly set, so the child applies the
    same defaults the parent computed.
    """
    argv = [
        sys.executable, str(_LOOP_PY), str(target),
        "--driver", DRIVER_GOAL, "--prompt", prompt,
        "--allow-dirty", "--_detached-run-id", run_id,
    ]
    if max_iterations is not None:
        argv += ["--max-iterations", str(max_iterations)]
    if cost_ceiling is not None:
        argv += ["--cost-ceiling", str(cost_ceiling)]
    return argv


def _spawn_detached(
    argv: list[str], log_path: Path
) -> tuple[Optional[int], Optional[str]]:
    """Spawn `argv` detached in a new OS session; child output → `log_path` (AC1).

    `start_new_session=True` (POSIX setsid) detaches the child from the parent's
    controlling terminal and process group, so it survives the parent exiting or
    the terminal closing — the headless equivalent of the interactive `/background`
    agent-view action (there is no headless `--background` flag on `claude -p`;
    probed on 2.1.175). stdin is `/dev/null`; stdout + stderr are redirected to the
    run-dir log. Returns `(pid, None)`, or `(None, breadcrumb)` on failure — the
    caller fails closed.
    """
    try:
        log_f = open(log_path, "ab")
    except OSError as exc:
        return None, f"cannot open background log {log_path}: {exc}"
    try:
        proc = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=log_f,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
    except OSError as exc:
        return None, f"cannot spawn detached child: {exc}"
    finally:
        # The child has its own dup'd fd; closing the parent's copy is correct.
        log_f.close()
    return proc.pid, None


def _detach_summary(
    *, run_id: str, pid: int, state_path: Path, log_path: Path,
    cost_ceiling: float, max_turns: int,
) -> dict:
    """Parent's one-line summary for a `--background` launch (AC1).

    Distinct shape from `_goal_summary`: `detached: true` + the `pid` and the paths
    to inspect. `terminal_reason=detached` means the run was *launched*, not
    finished — its real outcome lands in `state.json` as the detached child runs.
    """
    return {
        "driver": DRIVER_GOAL,
        "detached": True,
        "terminal_reason": REASON_DETACHED,
        "run_id": run_id,
        "pid": pid,
        "state_path": str(state_path),
        "log_path": str(log_path),
        "cost_ceiling_usd": cost_ceiling,
        "max_turns": max_turns,
    }


def run_goal_loop_background(
    target: Path, *,
    prompt: str,
    max_iterations: Optional[int],
    cost_ceiling: Optional[float],
    allow_dirty: bool,
) -> int:
    """Launch the goal driver DETACHED so an unattended run survives terminal close (AC1).

    The detached run carries every guardrail unchanged — the hard caps ride the
    child's outer `claude -p`, the final `gate.py` is the authority (it's the same
    `run_goal_loop`, just re-exec'd in a new OS session). The run-id + `state.json`
    (003-04) are the inspect / reattach surface: this returns immediately after
    printing the run-id; the user watches `state.json` for the outcome.

    Preflight refusals (missing / unscaffolded target, dirty tree, un-vendorable
    gate, run-id collision) are checked HERE, synchronously, so they surface to the
    user instead of being buried in the detached child's log. AC4: the dirty-tree
    brake runs before any detach, so a scheduled rerun can't inherit a dirty tree.

    Precondition (caller's responsibility): `/goal` host-eligibility is verified by
    `main()`'s routing (`--background` routes as goal-required) *before* this runs;
    this function does not re-probe it. The detached child re-checks via its own
    `run_goal_loop` and logs `goal_unavailable` as defense-in-depth.
    """
    ceiling = cost_ceiling if cost_ceiling is not None else DEFAULT_COST_CEILING_USD
    max_turns = max_iterations if max_iterations is not None else DEFAULT_MAX_ITERATIONS

    err = _target_preflight_error(target)
    if err is not None:
        reason, message = err
        return _refuse_goal(
            run_id=_generate_preflight_run_id(), reason=reason, message=message,
            cost_ceiling=ceiling, max_turns=max_turns,
        )

    if not allow_dirty:
        dirty = _dirty_tree_paths(target)
        if dirty:
            return _refuse_goal(
                run_id=_generate_preflight_run_id(),
                reason=REASON_DIRTY_TREE, message=_dirty_tree_message(dirty),
                cost_ceiling=ceiling, max_turns=max_turns,
            )

    vendored_gate, vendor_err = _ensure_vendored_gate(target)
    if vendored_gate is None:
        return _refuse_goal(
            run_id=_generate_preflight_run_id(),
            reason=REASON_GATE_VENDOR_FAILED, message=str(vendor_err),
            cost_ceiling=ceiling, max_turns=max_turns,
        )

    run_dir, run_id, attempted = _create_run_dir(target)
    if run_dir is None or run_id is None:
        attempt_list = ", ".join(attempted) if attempted else "(none)"
        return _refuse_goal(
            run_id=(attempted[0] if attempted else _generate_preflight_run_id()),
            reason=REASON_RUN_ID_COLLISION,
            message=(
                f"could not allocate a fresh run-id after {RUN_ID_MAX_ATTEMPTS} "
                f"attempts; colliding ids: {attempt_list}"
            ),
            cost_ceiling=ceiling, max_turns=max_turns,
        )

    # Seed the state file so `state.json` exists the moment we hand back the
    # run-id; the detached child overwrites it with its evolving state.
    claude_version = _get_claude_version()
    state_path = _state_path_for(target, run_id)
    state = _build_goal_state(
        run_id=run_id, target=target, prompt=prompt,
        max_turns=max_turns, cost_ceiling=ceiling, claude_version=claude_version,
    )
    state["detached"] = True
    _atomic_write_state(state, state_path)

    log_path = run_dir / BACKGROUND_LOG_NAME
    argv = _build_detached_child_argv(
        target, run_id, prompt=prompt,
        max_iterations=max_iterations, cost_ceiling=cost_ceiling,
    )
    pid, spawn_err = _spawn_detached(argv, log_path)
    if pid is None:
        return _refuse_goal(
            run_id=run_id, reason=REASON_DETACH_FAILED, message=str(spawn_err),
            cost_ceiling=ceiling, max_turns=max_turns,
        )

    sys.stderr.write(
        f"loop: launched detached (pid {pid}, run-id {run_id}). "
        f"Inspect with `cat {state_path}`; child log at {log_path}.\n"
    )
    _emit_json(_detach_summary(
        run_id=run_id, pid=pid, state_path=state_path, log_path=log_path,
        cost_ceiling=ceiling, max_turns=max_turns,
    ))
    return EXIT_OK


def main(argv: Optional[list[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="loop.py",
        description=(
            "Headless iteration driver. Subprocesses `claude -p "
            "--output-format json --max-budget-usd <remaining>` against a "
            "target, scores via `gate.py --json` after each iteration, "
            "halts on oracle pass, iteration cap, cost ceiling, or "
            "context-fill threshold. State is checkpointed atomically to "
            "`<target>/.servo/runs/<run-id>/state.json`; resume via "
            "`--resume <run-id>`. Per-invocation claude timeout defaults "
            f"to {DEFAULT_CLAUDE_TIMEOUT_SECONDS}s; override via "
            f"${_CLAUDE_TIMEOUT_ENV_VAR} env var (0 disables)."
        ),
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Path to the servo-scaffolded target project.",
    )
    parser.add_argument(
        "--driver",
        choices=[DRIVER_AUTO, DRIVER_LOOP, DRIVER_GOAL],
        # Slice 016-02: default is `None` (not DRIVER_AUTO) so plan-precedence
        # can distinguish "user passed --driver" from "accept the default". The
        # effective driver is resolved below (`effective_arg_driver`) as
        # explicit flag > plan `driver` > DRIVER_AUTO, *above* the routing
        # probes, so a plan's driver reaches routing while an omitted --driver
        # with no plan still routes exactly as `auto` did.
        default=None,
        help=(
            "Continuation driver. `auto` (default) runs a deterministic "
            "host-support probe (is `/goal` available; are hooks permitted) and "
            "picks the best path — the goal driver where supported, else a "
            "fail-safe downgrade to the loop driver. `loop` is the hand-rolled "
            "003-01..05 driver — every guardrail enforced servo-side; the "
            "portable path for hook-restricted / non-Claude-Code hosts. `goal` "
            "issues a single `claude -p` whose `/goal` condition drives "
            "across-turn continuation, with the hard caps (`--max-turns` = "
            "`--max-iterations`, `--max-budget-usd` = `--cost-ceiling`) on the "
            "outer call and a final `gate.py` run as the authority (ADR-0008); "
            "an explicit `--driver goal` on an unsupported host refuses (rc=2). "
            "See `--explain-routing` for the verdict without running."
        ),
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help=(
            "Seed prompt passed to claude -p on each iteration. Required "
            "for fresh runs; optional with --resume (persisted prompt is "
            "used when omitted)."
        ),
    )
    # Defaults are None at the argparse layer so run_loop can distinguish
    # "user passed the flag" from "user accepted the default" — needed for
    # resume-time flag overrides (slice 003-04 AC4).
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help=(
            f"Iteration cap; loop halts when reached. "
            f"Default {DEFAULT_MAX_ITERATIONS} (fresh runs) or the "
            f"persisted value (resumed runs; override re-applies on resume)."
        ),
    )
    parser.add_argument(
        "--cost-ceiling",
        type=float,
        default=None,
        help=(
            f"Cumulative cost ceiling in USD; loop halts when "
            f"`sum(total_cost_usd)` exceeds this value. Default "
            f"${DEFAULT_COST_CEILING_USD:.2f}. Pass 0 to disable; the "
            f"per-iteration `--max-budget-usd` then defaults to "
            f"${DEFAULT_PER_ITER_BUDGET_USD:.2f} as a runaway brake."
        ),
    )
    parser.add_argument(
        "--context-fill-threshold",
        type=float,
        default=None,
        help=(
            f"Context-fill refusal threshold in [0.0, 1.0]; loop refuses "
            f"iter N+1 when the prior iteration's "
            f"`(usage.input_tokens + cache_*) / "
            f"modelUsage.<model>.contextWindow` ratio is at-or-above this "
            f"value. Default {DEFAULT_CONTEXT_FILL_THRESHOLD:.2f}. Pass 0 "
            f"to disable; the iteration cap and cost ceiling still apply."
        ),
    )
    parser.add_argument(
        "--plateau-window",
        type=int,
        default=None,
        help=(
            f"Halt the loop when the oracle composite has not improved "
            f"over the last M iterations (strict greater-than counts as "
            f"improvement; equality is non-improving). Requires at least "
            f"M+1 iterations of history before firing. Default "
            f"{DEFAULT_PLATEAU_WINDOW}. Pass 0 to disable plateau "
            f"detection entirely."
        ),
    )
    parser.add_argument(
        "--plateau-noise-floor",
        type=float,
        default=None,
        help=(
            f"Frozen noise floor δ (ADR-0005 clause 4): composite gains "
            f"smaller than this read as 'flat' for plateau detection, so a "
            f"wobbling non-deterministic eval component can neither fake "
            f"progress nor fake a plateau. Default "
            f"{DEFAULT_PLATEAU_NOISE_FLOOR}. Set to a frozen eval's δ when an "
            f"eval component contributes to the composite."
        ),
    )
    parser.add_argument(
        "--plan",
        dest="plan",
        type=Path,
        default=None,
        help=(
            "Path to a compiled execution `plan.json` (ADR-0016 / slice 016-02). "
            "A generic path — loop.py never derives a spec-id. Reads the plan's "
            "`budget` (max_iterations / cost_ceiling / context_fill_threshold / "
            "plateau_window) and `driver` as run defaults for any knob you did "
            "not pass on the command line (precedence: explicit flag > plan > "
            "built-in default). Consumes `provenance: compiled` plans only; a "
            "human_edited plan refuses pending the 016-03 clamp. With no --plan, "
            "behavior is byte-for-byte today's (CLI flags + defaults). Mutually "
            "exclusive with --resume (the persisted state.json is authoritative "
            "on resume). --prompt is still required (prompt_ref render = 016-05)."
        ),
    )
    parser.add_argument(
        "--resume",
        dest="resume",
        default=None,
        help=(
            "Resume a prior run by its run-id (the directory name under "
            "`<target>/.servo/runs/`). The state file is loaded; the loop "
            "continues from `iteration_count + 1` with cumulative counters "
            "preserved. Refuses with rc=2 on state_missing / "
            "state_schema_mismatch / claude_version_mismatch (escape via "
            "--resume-anyway)."
        ),
    )
    parser.add_argument(
        "--resume-anyway",
        dest="resume_anyway",
        action="store_true",
        help=(
            "When used with --resume: bypass the state-schema and "
            "claude-version mismatch refusals. Risky — silent mis-decoding "
            "may corrupt the run, or claude's session/JSON semantics may "
            "have changed between the recorded version and the current one."
        ),
    )
    parser.add_argument(
        "--allow-dirty",
        dest="allow_dirty",
        action="store_true",
        help=(
            "Bypass the refuse-on-dirty-tree preflight (slice 003-07). By "
            "default a fresh run against a git target with uncommitted changes "
            "to tracked files refuses (rc=2 / dirty_tree) — a scheduled or "
            "unattended run could otherwise score leftover state as a spurious "
            "pass. Pass this for an intentional dirty run. Non-git targets skip "
            "the check regardless."
        ),
    )
    parser.add_argument(
        "--explain-routing",
        dest="explain_routing",
        action="store_true",
        help=(
            "Print the host-scope routing verdict for <target> (the chosen "
            "driver, /goal eligibility, the settings layers inspected, and the "
            "layer that forced any restriction) and exit 0 without running. "
            "Reads the settings hierarchy + `claude --version`; mutates nothing."
        ),
    )
    parser.add_argument(
        "--background",
        dest="background",
        action="store_true",
        help=(
            "Launch the goal-driven run DETACHED, in a new OS session, so a long "
            "unattended run survives the terminal closing (slice 003-08). Prints "
            "the run-id + state/log paths and returns immediately; inspect or "
            "await the run via its `state.json` (003-04). Requires the goal driver "
            "(it delegates continuation to /goal); on a host that can't run /goal "
            "it refuses, like an explicit --driver goal would. The headless analog "
            "of the interactive `/background` agent-view action."
        ),
    )
    parser.add_argument(
        "--emit-routine-prompt",
        dest="emit_routine_prompt",
        action="store_true",
        help=(
            "Make <target> Routine-ready and print the paste-ready /goal prompt, "
            "then exit 0 (slice 003-08). Vendors a clone-portable gate.py (003-07) "
            "and emits the canonical loop-body prompt — with a portable `python3` + "
            "relative gate path — to paste into a scheduled Routine (created from "
            "the web/desktop app; there is no `routine` CLI subcommand). Requires "
            "--prompt (the task); runs no loop."
        ),
    )
    parser.add_argument(
        # Internal: the detached child of a `--background` launch runs the goal
        # loop into this parent-allocated run-id (so both share one run dir).
        "--_detached-run-id",
        dest="detached_run_id",
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    target = args.target.resolve()

    # --explain-routing (slice 003-07 AC5): print the verdict and exit 0,
    # read-only. Handled before flag-shape validation so it needs no --prompt.
    # Slice 016-02 migrated `--driver`'s default to None; resolve the omitted
    # case back to DRIVER_AUTO here so the read-only explanation is byte-for-byte
    # today's (plan-driven routing is resolved on the actual-run path below).
    if args.explain_routing:
        verdict = _decide_route(
            target, args.driver if args.driver is not None else DRIVER_AUTO
        )
        sys.stdout.write(_format_routing_explanation(verdict, target))
        return EXIT_OK

    # ---- Flag-shape validation ---------------------------------------------
    if args.resume_anyway and args.resume is None:
        parser.error("--resume-anyway requires --resume <run-id>")
    # Slice 016-02 AC8: on resume the persisted state.json is authoritative, so
    # a plan cannot also supply run defaults — passing both is a user error.
    if args.plan is not None and args.resume is not None:
        parser.error("--plan and --resume are mutually exclusive (on resume the "
                     "persisted state.json is authoritative; a fresh --plan run "
                     "takes no --resume)")
    if args.resume is None and args.prompt is None:
        parser.error("--prompt is required unless --resume <run-id> is given")
    if args.max_iterations is not None and args.max_iterations < 1:
        parser.error("--max-iterations must be >= 1")
    if args.cost_ceiling is not None and args.cost_ceiling < 0:
        parser.error("--cost-ceiling must be >= 0")
    if args.context_fill_threshold is not None and (
        args.context_fill_threshold < 0 or args.context_fill_threshold > 1
    ):
        parser.error("--context-fill-threshold must be in [0.0, 1.0]")
    if args.plateau_window is not None and args.plateau_window < 0:
        parser.error("--plateau-window must be >= 0")
    if args.plateau_noise_floor is not None and args.plateau_noise_floor < 0:
        parser.error("--plateau-noise-floor must be >= 0")
    # Slice 003-08 flag conflicts.
    if args.emit_routine_prompt and args.background:
        parser.error("--emit-routine-prompt and --background are mutually exclusive")
    if args.emit_routine_prompt and args.resume is not None:
        parser.error("--emit-routine-prompt emits a prompt and runs nothing; it "
                     "does not take --resume")
    if args.background and args.resume is not None:
        parser.error("--background does not support --resume (a detached run is a "
                     "fresh goal run; goal mode has no resume)")
    if args.background and args.driver == DRIVER_LOOP:
        parser.error("--background requires the goal driver (it delegates "
                     "continuation to /goal); --driver loop runs in the "
                     "foreground — detach it with your shell's nohup/&, or use "
                     "--resume for unattended continuation")

    # --emit-routine-prompt (slice 003-08 AC2): vendor a clone-portable gate.py
    # and print the paste-ready Routine prompt, then exit 0. Handled before
    # routing — the Routine runs on a different host (the cloud), so this host's
    # /goal support is irrelevant to producing the artifact.
    if args.emit_routine_prompt:
        return _emit_routine_prompt(target, args.prompt)

    # Detached child of a `--background` launch (slice 003-08 AC1): run the goal
    # loop into the parent-allocated run-id, bypassing routing (the parent
    # already verified host support before detaching).
    if args.detached_run_id is not None:
        return run_goal_loop(
            target,
            prompt=args.prompt,
            max_iterations=args.max_iterations,
            cost_ceiling=args.cost_ceiling,
            allow_dirty=args.allow_dirty,
            run_id=args.detached_run_id,
            detached=True,
        )

    # ---- Plan consumption (slice 016-02, ADR-0016) -------------------------
    # Read `budget` + `driver` from a compiled plan.json as run defaults for
    # knobs the caller did not pass. This is the ONLY path a plan is read on;
    # with no --plan, `plan_budget` / `plan_driver` stay None and every
    # resolution below collapses to today's args-or-default behavior (AC5).
    # Fail-closed: a missing / malformed / schema-mismatched / non-compiled plan
    # refuses rc=2 with a structured reason BEFORE any run starts (AC6/AC7).
    plan_budget = None
    plan_driver = None
    if args.plan is not None:
        plan, plan_err = _load_plan(args.plan.resolve())
        if plan_err is not None:
            return _refuse_plan(reason=plan_err[0], message=plan_err[1])
        plan_budget = plan.get("budget") or {}
        plan_driver = plan.get("driver")

    # Resolve the effective driver: explicit --driver > plan `driver` > auto
    # (slice 016-02 A1/AC2). Done ABOVE the routing probes so a plan's driver
    # reaches routing; an omitted --driver with no plan resolves to DRIVER_AUTO,
    # i.e. today's routing. Budget knobs resolve just above the run_loop /
    # run_goal_loop call (below) — the plan value is kept in a fresh local, NOT
    # written into args.*, so a plan-sourced loop-only brake is dropped silently
    # under the goal driver (AC3) instead of tripping the "stray brake" warning.
    if args.driver is not None:
        effective_arg_driver = args.driver
    elif plan_driver is not None:
        effective_arg_driver = plan_driver
    else:
        effective_arg_driver = DRIVER_AUTO

    # ---- Budget resolution (slice 016-02 AC1/AC2/AC3) ----------------------
    # Precedence per knob: explicit CLI flag > plan `budget` value > loop.py
    # default (`None` here ⇒ the driver applies its DEFAULT_*). Resolved ABOVE
    # both the `--background` detached-launch branch and the foreground dispatch
    # so a plan's budget reaches every launch path — including the detached goal
    # child (AC1: budget applies for each knob the caller did not pass, with no
    # background carve-out). Plan values are held in fresh locals — NEVER written
    # back into args.* — so the goal-driver brake-drop below (which warns iff
    # `args.<brake> is not None`) sees only EXPLICIT flags: a plan-sourced
    # loop-only brake is dropped silently under the goal driver, not
    # misattributed to the user (AC3 KEY). With no plan, `_resolve_from_plan`
    # returns `args.*` unchanged (None when unset) — byte-for-byte today (AC5).
    max_iterations = _resolve_from_plan(
        args.max_iterations, plan_budget, "max_iterations")
    cost_ceiling = _resolve_from_plan(
        args.cost_ceiling, plan_budget, "cost_ceiling_usd")
    context_fill_threshold = _resolve_from_plan(
        args.context_fill_threshold, plan_budget, "context_fill_threshold")
    plateau_window = _resolve_from_plan(
        args.plateau_window, plan_budget, "plateau_window")

    # ---- Host-scope routing (slice 003-07 AC4) -----------------------------
    # `loop` always runs (the portable path needs no probe). `goal` / `auto`
    # resolve via the deterministic host-support verdict: an explicit `goal` on
    # an unsupported host refuses (rc=2 / goal_unavailable), while `auto`
    # fail-safe-downgrades to `loop` and logs why. `--background` (003-08) needs
    # the goal driver (it delegates continuation to /goal), so it routes as if
    # `--driver goal` was requested — an unsupported host refuses rather than
    # silently downgrading to a non-detachable loop run.
    routing_driver = DRIVER_GOAL if args.background else effective_arg_driver
    if routing_driver == DRIVER_LOOP:
        effective_driver = DRIVER_LOOP
    else:
        verdict = _decide_route(target, routing_driver)
        if verdict["refused"]:
            ceiling = (args.cost_ceiling if args.cost_ceiling is not None
                       else DEFAULT_COST_CEILING_USD)
            max_turns = (args.max_iterations if args.max_iterations is not None
                         else DEFAULT_MAX_ITERATIONS)
            hint = ("--background needs the goal driver" if args.background
                    else "--driver goal is unsupported on this host")
            sys.stderr.write(
                f"loop: {hint} ({verdict['ineligible_reason']}). Use --driver loop "
                "(the portable hand-rolled driver) or --driver auto.\n"
            )
            return _refuse_goal(
                run_id=_generate_preflight_run_id(),
                reason=REASON_GOAL_UNAVAILABLE,
                message=f"goal driver unsupported: {verdict['ineligible_reason']}",
                cost_ceiling=ceiling, max_turns=max_turns,
            )
        effective_driver = verdict["chosen_driver"]
        if (effective_arg_driver == DRIVER_AUTO and not args.background
                and effective_driver == DRIVER_LOOP):
            sys.stderr.write(
                f"loop: auto-routing to --driver loop ({verdict['ineligible_reason']}); "
                "the goal driver is unavailable on this host.\n"
            )

    # ---- Detached launch (slice 003-08 AC1) --------------------------------
    # Routing above guaranteed effective_driver == goal (an ineligible host
    # already refused). Spawn the goal driver in a new OS session and return.
    # The plan-resolved budget locals (not args.*) carry the plan's budget into
    # the detached child (slice 016-02 AC1).
    if args.background:
        return run_goal_loop_background(
            target,
            prompt=args.prompt,
            max_iterations=max_iterations,
            cost_ceiling=cost_ceiling,
            allow_dirty=args.allow_dirty,
        )

    # ---- Dispatch ----------------------------------------------------------
    # `--context-fill-threshold` / `--plateau-window` / `--resume-anyway` are
    # loop-mode brakes; they're ignored when the effective driver is `goal` (the
    # /goal primitive owns continuation). `--max-iterations` / `--cost-ceiling`
    # carry over as the outer-call `--max-turns` / `--max-budget-usd` caps. The
    # warning keys on `args.*` (explicit flags only) so plan-sourced loop-only
    # brakes are dropped silently (AC3); the loop-only budget locals resolved
    # above are simply not forwarded to the goal driver.
    if effective_driver == DRIVER_GOAL:
        loop_only = [
            name for name, val in (
                ("--context-fill-threshold", args.context_fill_threshold),
                ("--plateau-window", args.plateau_window),
                ("--plateau-noise-floor", args.plateau_noise_floor),
                ("--resume-anyway", args.resume_anyway or None),
            ) if val is not None
        ]
        if loop_only:
            sys.stderr.write(
                f"loop: {', '.join(loop_only)} {'is' if len(loop_only) == 1 else 'are'} "
                f"a loop-mode brake and {'is' if len(loop_only) == 1 else 'are'} ignored "
                f"under --driver goal (the /goal primitive owns continuation).\n"
            )
        return run_goal_loop(
            target,
            prompt=args.prompt,
            max_iterations=max_iterations,
            cost_ceiling=cost_ceiling,
            resume_run_id=args.resume,
            allow_dirty=args.allow_dirty,
        )
    return run_loop(
        target,
        prompt=args.prompt,
        max_iterations=max_iterations,
        cost_ceiling=cost_ceiling,
        context_fill_threshold=context_fill_threshold,
        plateau_window=plateau_window,
        plateau_noise_floor=args.plateau_noise_floor,
        resume_run_id=args.resume,
        resume_anyway=args.resume_anyway,
        allow_dirty=args.allow_dirty,
    )


if __name__ == "__main__":
    sys.exit(main())
