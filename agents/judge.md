---
name: judge
description: Unattended reviewer for agent-loop and variant-race output. Read-only, machine-parseable verdict.
tools:
  - Read
  - Glob
  - Grep
---

> **Status: placeholder.** Full prompt authored alongside spec 003 (`/servo:agent-loop`) and reused by spec 005 (`/servo:variant-race`).

## Why this exists (not jig's `reviewer`)

Jig's `reviewer` produces narrative findings for a human reader. In an unattended loop or race, the loop/race driver needs:

- A single machine-parseable verdict (`PASS` / `FAIL` / `INCONCLUSIVE`)
- A score (if the loop weights review against the oracle)
- A short structured failure reason (so the next iteration's prompt can include it)

`judge` is the unattended-context sibling: same job (independent review of work against a spec), different output shape (structured, not narrative).

## Authored when

Spec 003 (`/servo:agent-loop`) needs this prompt for between-iteration evaluation. Spec 005 (`/servo:variant-race`) reuses it for per-variant scoring.
