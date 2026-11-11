---
status: DRAFT
skill: agent-loop
use_cases: []
---

# Spec 040: servo-wrapped worker outcome line

> **Status: DRAFT, scope capture.** Follow-up to
> [spec 038](../038-per-node-model-tiering/spec.md).

## Overview

A host (Claude Code sessions, Copilot `create_session`, a Managed Agents
workflow) can orchestrate a campaign by spawning worker sessions and messaging
them. In a recorded two-day multi-session run without servo, two problems
showed up:

- workers ran without per-node discipline (one fixer: 1,383 calls, 59
  compactions, ~23 h);
- escalation traffic was chatty: 646 messages from the coordinator, and more
  than 100 round trips with a single child.

servo's loop already has the per-node discipline: oracle, budget, plateau,
context-fill, and after spec 038 the escalation ladder and accounting. What is
missing is a **compact, typed result** that a worker can send up in one
message instead of a conversation.

This spec defines that result: a single outcome line that `loop.py` can print
on request. A host-spawned worker runs its task under `loop.py` and forwards
the line verbatim:

```json
{"servo_outcome": 1, "result": "passed|plateau|blocked|budget|error",
 "rung": 1, "rungs": 2, "iterations": 7, "cost_usd": 0.84,
 "composite": 0.91, "threshold": 0.8, "run_id": "…", "reason": "oracle_passed"}
```

## Boundaries (non-negotiable)

- **No `/servo:crew`, ever (spec 003), and no fan-out (spec 005).** servo does
  not spawn, message or track workers. The host owns the tree, and the outcome
  line is just output.
- **The loop stays trigger-agnostic.** The line is a rendering of the existing
  summary (spec 038 fields included). A host orchestrator is just another
  trigger, like the heartbeat.
- **servo never merges and never depends on jig.** jig may *consume* the line
  (for example a campaign ledger), but servo neither reads nor writes jig
  artifacts.

## Consumer: spec 042 campaigns

Spec 042 / ADR-0049 (Proposed) is this line's first consumer. A campaign
ledger never trusts the line's own field values for a wrapped worker:
- `campaign record` uses the line only to locate the run (`run_id`);
- it re-renders result, rung and cost from that run's `state.json`, after
  verifying the worktree's content fingerprint against the loop's halt state.

So the line must carry `run_id`, and `loop.py` must record the content
fingerprint (HEAD plus diff plus untracked contents) and its start HEAD at
halt. Those two state additions belong with 040-01 or 042-03, whichever lands
first.

## Assumptions

- **A1:** hosts can capture a worker's last stdout line, or a file, and forward
  it. True for Claude Code (`claude -p` JSON result) and plausible for Copilot
  sessions. Verify per host at activation.
- **A2:** the five-way `result` mapping from `terminal_reason` is total. To be
  enumerated against loop.py's closed terminal-reason taxonomy at activation.

## Activation trigger

A host-orchestrated campaign (jig reframe or similar) is about to run its
workers under `loop.py`.

## Slices

- [040-01 — outcome line](slice-01-outcome-line.md) (DRAFT sketch)
