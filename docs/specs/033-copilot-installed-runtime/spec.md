---
status: IN_PROGRESS
skill:
use_cases: []
---

# Spec 033: Copilot installed runtime and capability boundaries

## Overview

Complete supported delivery in existing PR #37, reusing closed spec 032.
An installed Copilot user can scaffold and score a project-owned deterministic
oracle without Claude or Jig. Native autonomy must refuse capabilities the
current CLI cannot guarantee. Native authoring and frozen judge transports
remain separate consumers, with their own evidence and approval boundaries.
This follow-up preserves historical records.

The October draft commit `230baa74` proposed delivery (032), guarded execution
(033) and evaluation transports (034) before the September implementation
was discovered. Numbers here are new provisional branch reservations.
Implements [ADR-0039](../../decisions/adr-0039-copilot-capability-boundaries.md).

## Assumptions

Supported packaging is grounded in existing builder tests and current
`copilot --plugin-dir hosts/copilot plugin list` (1.0.96-2 reports Servo 0.10.0).
Native authoring, model/image controls and per-turn stop continuation require
separate live evidence before their implementation can be called complete.

## Decomposition

Interface: 033-01 delivers the installed deterministic workflow.
Rules: 033-02 makes unsupported native execution fail without spending/mutation.
Paths: 033-04 delivers native assisted authoring; 033-05 delivers frozen text
scoring; 033-06 delivers frozen visual scoring, if actual image/model controls
can be proved. Native autonomy and stop continuation are separately deferred,
not counted as delivered by a refusal or by generated prose.

## Slices

- [033-01 — installed-oracle](slice-01-installed-oracle.md)
- [033-02 — capability-refusal](slice-02-capability-refusal.md)
- [033-03 — native-loop-and-consumers](slice-03-native-loop-and-consumers.md)
- [033-04 — native-authoring](slice-04-native-authoring.md)
- [033-05 — native-text-judges](slice-05-native-text-judges.md)
- [033-06 — native-visual-judge](slice-06-native-visual-judge.md)
- [033-07 — native-stop-continuation](slice-07-native-stop-continuation.md)
