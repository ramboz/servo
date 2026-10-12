---
status: IN_PROGRESS
skill: heartbeat
use_cases: []
---

# Spec 033: Heartbeat outcome handoff

## Overview

An operator should see why a dispatched servo run stopped, its actual final
oracle score, and any existing permission-fix hint without hunting through a
retained worktree. Preserve the existing driver summaries in heartbeat's sticky
outcome and display them in the human triage surfaces. Do not change continuation,
budgets, finding identity, lifecycle classification, or quarantine policy.

This serves Servo Run's evaluation reporting and convergence diagnostics in
[the product vision](../../product-vision.md#two-phases-servo-compile-and-servo-run).
The vision has no `## Use cases` section, so `use_cases: []` is intentional.

## Recovery chronology

The original implementation was committed as `ac06cec` and opened as
[ramboz/servo#38](https://github.com/ramboz/servo/pull/38) before a spec,
independent review evidence, or reconciliation existed. TDD and focused checks
were performed, but they did not satisfy the full jig ceremony the owner
expected. The owner requested recovery of that missing ceremony on 2026-10-12.

This spec is retrospective. Its actual transitions and reviews occur now:
they do not claim a spec-first implementation or backdated approval. Existing
implementation remains subject to fresh review and correction against these
criteria. Provisional spec/ADR identifiers were allocated with the documented
`--no-push` helpers on the existing PR branch; board/index and fresh-main checks
must detect a collision before the recovery is published.

That check found an existing sibling's spec 032 (`copilot-third-host`) and
ADR-0038. Our unpublished reservations were retired and freshly allocated as
033/0039 using the helpers. The provisional 0038 acceptance had only been
stamped locally; it was rescinded before any Accepted record was committed or
pushed. The final identifiers must receive their own frame verdicts and gates;
old provisional verdicts are not reused as their review evidence.

## Scope

Canonical implementation: `skills/heartbeat/heartbeat.py`, its tests and skill
surface; related live architecture prose and generated Claude/Codex packages.
Workflow recovery adds this spec, real review artifacts, a supplementary
[ADR-0039](../../decisions/adr-0039-heartbeat-handoff-contract.md), and the
minimal `scaffold.json` sentinel for the already-existing jig-shaped corpus.
No runtime machinery is vendored, and no old ADR or closed slice is amended.

## Assumptions

- Compatibility with unknown out-of-repository consumers that require an exact
  five-key outcome has not been established. The bounded guarantee is for
  inspected in-repository readers and old records, not every external reader.
  ADR-0039 records the versioning choice and the trigger for reconsidering it.

## Decomposition

One vertical **Data + Interface** slice connects both summary shapes to durable
outcomes and human reporting. Splitting normalization from display would leave
the operator's handoff incomplete. No spike or new execution subsystem is needed.

## Slices

- [033-01 — diagnostic handoff](slice-01-diagnostic-handoff.md)
