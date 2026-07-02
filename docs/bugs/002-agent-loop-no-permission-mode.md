---
status: DONE
tier: standard
severity: high
claimed_by: main
regression_test: skills/agent-loop/test_loop.py::LoopForwardsTargetSettingsTests
main_repro_checked_at: 2026-07-02
main_repro_ref: origin/main@45d8dc0
main_repro_result: reproduces
red_confirmed_at: 2026-07-02
green_confirmed_at: 2026-07-02
fix_class: local_patch
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

- [x] **(leading)** `loop.py` builds `["claude","-p","--output-format","json",
  "--agent",<name>, …]` with no permission flag and no `--settings`, so the
  spawned runner inherits the host's default (prompt-on-tool) mode, which in a
  headless context = deny. *Confirm:* read `_invoke_claude`'s argv. *Falsify:*
  find a `--settings`/`--permission-mode` in the argv.
- [ ] It should pass/inherit the **target repo's** permission settings so a repo
  that pre-authorizes its tools (an allow-list in `.claude/settings.json`) runs
  unattended out of the box. *Confirm:* a control `claude -p --settings
  <allow-list>` allowed edits. *Falsify:* edits still denied with settings.

## Root cause

**Confirmed by code inspection** (`skills/agent-loop/loop.py:1276-1282`).
`_invoke_claude` constructs its `claude -p` argv as
`["claude","-p","--output-format","json","--max-budget-usd",…]` plus optional
`--agent`/`--resume`/prompt — **no `--settings` and no `--permission-mode`**.
The spawned runner therefore inherits the host's default (prompt-on-tool)
permission mode, which in a headless (no TTY) context denies `Write`/`Edit`/
`Bash`. A target repo that pre-authorizes its tools in a committed
`.claude/settings.json` gets no benefit, so the runner burns tokens without
editing files and the loop halts on `context_full`/`oracle_plateau`. (Scope:
the reported repro is `--driver loop`; the goal driver has a separate argv +
routing audit and is out of scope for this bug — see Fix.)

## Fix class

`local_patch` — argv construction in `_invoke_claude` (loop driver).

## Fix

New helper `_settings_args(target)` (`skills/agent-loop/loop.py`) returns
`["--settings", "<target>/.claude/settings.json"]` when that file exists, else
`[]`. `_invoke_claude` extends its `claude -p` argv with it, so a target that
pre-authorizes its tools in a committed `.claude/settings.json` runs unattended.

**Security boundary (addresses the record's caveat):** the fix forwards ONLY
the target's own committed settings file — it never synthesizes or injects a
bypass `--permission-mode`. Host-level managed policy still merges on top and
governs, so this cannot silently enable an unrestricted agent where the host
forbids it. When the target declares no settings, the flag is omitted and the
host default is preserved.

**Scope:** limited to the reported `--driver loop` path. The goal driver
(`_invoke_claude_goal`) has a separate argv plus the ADR-0008-V3 routing audit;
the broader "refuse-when-nested / can't-get-edit-perms" behavior is
[ADR-0021](../decisions/adr-0021-oracle-first-agent-loop-optional-consumer.md) /
[spec 019-04](../specs/019-compile-core-simplification/slice-04-oracle-as-a-service-docs.md)
work, deliberately not folded into this bug fix.

## Already tried

Control: `claude -p --settings <allow-list JSON>` allowed edits — proves the fix
direction works when the loop supplies settings.

## Regression test

`skills/agent-loop/test_loop.py::LoopForwardsTargetSettingsTests` — two tests:
`test_forwards_settings_when_target_declares_them` (target `.claude/settings.json`
→ argv carries `--settings <that resolved path>`) and
`test_no_settings_flag_when_target_has_none` (no settings → no `--settings`).

## Proof

Red→green witnessed by the teeth gate (`red_confirmed_at` / `green_confirmed_at`).
Existing loop tests unaffected (none declare a target `.claude/settings.json`, so
`_settings_args` returns `[]`); ruff clean.

## Learning

Related: Bug 001 (same run's earlier auth failure). Together they show servo's
headless loop cannot run **nested inside another (sandboxed) agent** — it is a
top-level / user-run tool. See the oracle-first scoping ADR.

## Main recheck

- 2026-07-02 - `origin/main@45d8dc0` -> reproduces: HEAD==origin/main==45d8dc0; _invoke_claude argv (loop.py:1276-1282) has no --settings/--permission-mode. New LoopForwardsTargetSettingsTests reproduces (RED).
