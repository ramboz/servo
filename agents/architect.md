---
name: architect
description: Evaluates architectural decisions for servo and produces ADR-style proposals. Invoked rarely — only for hard-to-reverse decisions.
tools:
  - Read
  - Glob
  - Grep
  - WebSearch
---

> **Status: placeholder.** Mostly a copy of jig's `architect`, reworded for servo's unattended-agent context. Full prompt authored when the first ADR-worthy decision lands (likely during spec 001 around weighted-composite heuristics, or spec 003 around loop guardrail defaults).

## Why a separate file (not jig's verbatim)

Jig's `architect` reasons about supervised spec-driven dev. Servo's surface raises different architectural questions:

- Cost-vs-convergence tradeoffs (loop iteration cap, cost ceiling)
- Reversibility of hooks (settings.json mutation, backup/rollback)
- Worktree race scoring policy (winner selection, loser cleanup)
- Filesystem-only coupling with jig

The prompt frames the agent for these tradeoffs rather than spec-driven ones. Mechanics (read the question, read the code, produce an ADR with alternatives) are identical to jig's.

## Authored when

First ADR-worthy decision arises during spec 001 (weighted-composite heuristic) or spec 003 (loop guardrail defaults).
