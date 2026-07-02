---
status: REPORTED
tier:
severity:
claimed_by: main
regression_test:
main_repro_checked_at:
main_repro_ref:
main_repro_result:
red_confirmed_at:
green_confirmed_at:
fix_class:
security_surface: false
escalated_to:
---

# Bug 002: agent-loop-no-permission-mode

> Reported from an external dogfood run (cwv-workbench spec 015, 2026-07-01).

## Symptom

The loop driver's `claude -p` invocation passes **no `--permission-mode`** and
does not pass the target repo's `.claude/settings.json`. On a host that does not
default to bypass, the spawned runner can read/reason but its `Write`/`Edit`/`Bash`
tool calls are **denied**, so it makes no file changes while burning tokens — the
oracle never moves and the loop halts on `context_full`/`oracle_plateau`.

## Repro

On a host with default (non-bypass) permissions, `loop.py <target> --driver loop
--prompt "<edit task>"`. Runner iterations show `cost_usd > 0` but **zero file
edits**; oracle stays red; halts on context/plateau.

## Evidence

Run `20260701T234313-d3c3` (auth already fixed): iter 1 `cost_usd $1.10`, iter 3
`context_fill_ratio 1.4` → `context_full`; the judge iteration's verdict was
"None of the four deliverables exist yet (…unchanged, absent, no … added)". A
standalone control — `claude -p --settings <permissive-allow-list>` — **did**
allow the same Write/Bash, confirming permissions (not agent logic) were the
blocker.

## Hypotheses

1. **(leading)** `loop.py` builds `["claude","-p","--output-format","json",
   "--agent",<name>, …]` with no permission flag and no `--settings`, so the
   spawned runner inherits the host's default (prompt-on-tool) mode, which in a
   headless context = deny.
2. It should pass/inherit the **target repo's** permission settings so a repo
   that pre-authorizes its tools (an allow-list in `.claude/settings.json`) runs
   unattended out of the box.

## Root cause

_Not yet diagnosed (REPORTED). See hypotheses._

## Fix class

_TBD (likely `local_patch` in loop.py's `claude -p` argv construction)._

## Fix

**Direction (not yet implemented):** resolve the target repo's
`.claude/settings.json` and pass `--settings <that>` (or an explicit
`--permission-mode` sourced from config) to the spawned `claude -p`, so a target
that pre-authorizes its tools runs unattended. **Caveat:** this must NOT silently
enable an unrestricted agent when the host policy forbids it — pair with the
"refuse-when-nested / can't-get-edit-perms" behavior proposed in the
oracle-first scoping ADR. Passing permissive settings via shell indirection from
another auto-mode agent is exactly what a host safety classifier will (correctly)
block.

## Already tried

Control: `claude -p --settings <allow-list JSON>` allowed edits — proves the fix
direction works when the loop supplies settings.

## Regression test

_TBD — assert the loop's `claude -p` argv includes the resolved `--settings`
(or `--permission-mode`) when the target declares one._

## Proof

_TBD._

## Learning

Related: Bug 001 (same run's earlier auth failure). Together they show servo's
headless loop cannot run **nested inside another (sandboxed) agent** — it is a
top-level / user-run tool. See the oracle-first scoping ADR.
