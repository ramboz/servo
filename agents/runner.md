---
name: runner
description: Unattended implementer for agent-loop iterations. Terse, exit-non-zero-on-blocker, machine-parseable output.
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

> **Status: placeholder.** Full prompt authored alongside spec 003 (`/servo:agent-loop`).
> Until then, this file documents the role and reserves the agent name.

## Why this exists (not jig's `implementer`)

Jig's `implementer` agent assumes **supervised TDD** — its prompt encourages thoughtful narration, asks the user clarifying questions, defers ambiguous calls back to the user. None of that fits an unattended loop where:

- Every iteration costs real money
- A human is not watching
- The loop driver needs machine-parseable signals to decide whether to iterate again

`runner` is the unattended-context sibling: same job (implement against a spec slice), different framing (terse, no soliloquy, no clarifying questions, exit-non-zero on any blocker so the loop driver can take over).

## Authored when

Spec 003 (`/servo:agent-loop`) needs this prompt. Until then, `agent-loop` cannot run, and this file is informational only.
