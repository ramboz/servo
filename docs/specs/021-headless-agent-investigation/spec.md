---
status: DONE
dependencies: [003-05, adr-0003]
last_verified: 2026-07-12
---

# Spec 021 - headless agent investigation & assumption discipline

> Harden servo's `runner`/`judge` agents for headless loops: (1) diff-anchored,
> narrow-first investigation guidance, and (2) surface-and-verify load-bearing
> assumptions in place of the clarifying questions a headless loop can't ask.
> Stays in the agent (consumer) layer per [ADR-0021](../../decisions/adr-0021-oracle-first-agent-loop-optional-consumer.md);
> the oracle/`gate.py` boundary is unchanged. Slice 02 is decided by
> [ADR-0025](../../decisions/adr-0025-runner-records-judge-verifies-assumptions.md).

## Overview

Both work items sharpen the reliability of the unattended agent-loop by editing
only the agent prompts (`agents/runner.md`, `agents/judge.md`) and their surface
tests — the same reviewable surface slice 003-05 used to ship the real runner/
judge prompts. Neither item touches `oracle.sh`, `gate.py`, or `loop.py`'s
score/guardrail logic; the deterministic authority stays where ADR-0021 /
ADR-0011 / ADR-0005 put it.

**Motivation.** GitHub reported that generic tool instructions gave a code-review
agent the wrong instincts (browse broad → read whole files → accumulate), and
that rewriting them to be reviewer-shaped (anchor to the diff, grep/glob to
locate before reading, batch discovery, read focused ranges, retry a failed
search with a simpler query) cut review cost ~20% at equal quality
([source](https://github.blog/ai-and-ml/github-copilot/better-tools-made-copilot-code-review-worse-heres-how-we-actually-improved-it/)).
servo's runner and judge are exactly such agents; slice 01 gives them that
discipline. Separately, servo's loop is **headless** — `agents/runner.md`
mandates "no clarifying questions" — so an ambiguous prompt is silently
interpreted, which can drive the loop toward a confidently-wrong target. Slice 02
replaces silent interpretation with surface-the-assumption-in-the-verdict-block,
which the judge then verifies. This is the servo-side counterpart to jig's
clarify/assumptions discipline, adapted for an unattended loop.

The ~20% figure is external and unmeasured for servo — the ACs promise the
guidance is present and the contract stays parseable, not a measured cost delta.

## Assumptions
- The guidance and the assumption record/verify are advisory prompt-shaping in
  the consumer layer; `gate.py`/`oracle.sh` remain the deterministic authority
  (ADR-0021, ADR-0011, ADR-0005). This spec does not move any signal into the
  oracle.
- The verdict block is strictly parsed by `loop.py` at `schema_version: 1`
  (ADR-0003): `schema_version` must be the first field and the unquoted integer
  `1`, or the run terminates with `verdict_schema_mismatch`. Slice 02 must
  reconcile any new `assumptions:` field with this parser — decided in ADR-0025.

## Decomposition

SPIDR — primarily **Rules** (021-01: add investigation-discipline rules to the
agent prompts) plus **Interface** (021-02: a new verdict-block field + the
judge's verification behavior). Two vertical slices; no spike — the current
prompt/parser behavior is known by reading `agents/runner.md`, `agents/judge.md`,
and `skills/agent-loop/loop.py`.

## Slices

- [021-01 - diff-anchored, narrow-first investigation](slice-01-diff-anchored-investigation.md)
- [021-02 - record and verify load-bearing assumptions](slice-02-assumption-record-verify.md)
