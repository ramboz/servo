---
status: DONE
skill: design-eval
use_cases: []
---

# Spec 037: Reusable design evidence

## Overview

Deliver a component-agnostic required-evidence gate and static design observer,
without the unmerged card proof-of-concept runtime. Projects supply their own
approved source inventory, application bindings, resources, and environment.
Required failures cannot be averaged away by quality scores; unavailable
evidence cannot become success.

The owner authorized a clean product-only replacement of the initial effort
in Servo pull requests 40-47, retirement of its unmerged pilot interfaces, and
preservation of original pull requests, worktrees, and selected approval epochs.
This is prospective work on a default-main branch, not a claim that the old
experiments shipped or that their closed records have been rewritten.

### Grounded starting point

The inspected source cut is `f0041335ac42f0892874f275e61d4b135ff46205`.
Its generic required gate, declared-output closure, and consumers live in
`skills/quality-gate/{required_runtime,gate_consumer,gate}.py`,
`skills/spec-oracle/{checks,oracle_overlay}.py`, and their consuming skills.
`git diff --name-only dc56bd3 f0041335 -- skills templates agents` enumerates
that cut's canonical runtime changes; generated `hosts/` is rebuilt from
canonical source rather than transplanted.

At that cut, `static_contract.py` imports strict I/O from `card_bundle.py`,
startup/run-summary helpers from `card_evidence.py`, and native-link inventory
from `card_install.py` (imports and `HELPERS` at lines 24-26, 523-529,
643-645, 739-740, 962-963). `static_snapshot.py` imports the same I/O helpers
(lines 20-21). These call sites establish the extraction scope, not a license
to copy the rest of those pilot modules under new names.

The existing static observer's command interface, source/profile versions,
comparison and tolerance rules, snapshot resource contract, and envelope remain
bounded. Component-agnostic does not mean arbitrary producer or build-framework
support. The existing non-deterministic quality engine remains unchanged.

### Product boundary

- Retain the generic required gate, opaque command/refusal handling, immutable
  declared-output closure, and loop/checkpoint/hook/planner/heartbeat consumers.
- Extract only used strict I/O and runtime primitives into `evidence_io.py`
  and `evidence_runtime.py`; the static observer must neither ship nor depend
  on a pilot module.
- Consume the clean Vellum successor's actual six-file source helper closure:
  `confirmed_source.py`, `capture_confirmed.py`, `design_input.py`,
  `redline_intake.py`, `resolve_redline.py`, `validate_redline.py`.
  Preserve live original-source freshness and require new approvals for new
  source-tool bytes. No compatibility alias or old-approval rebinding.
- Retire card capture/install/evidence/quality interfaces, fixed role and
  geometry inventories, pilot application dependencies, and fixed
  model/attempt/threshold policy.
- Test actual public preparation, independent policy approval, ordinary
  installation, native gate execution, and pure readback on two structurally
  different non-card fixtures. Synthetic approvals are explicitly test-only,
  never application attestations.

### Non-goals

No provider registry, new protocol, language, state engine, sampler, quality
policy expansion, arbitrary build framework, model/vision judge, pilot rerun,
application archive, or historical proof export. No changes to old pull requests
or records, main pushes, merges, or automatic approval migration.

### Integration prerequisites

The clean source-producer cut is Vellum commit
`80f178ea1b25ebb0fff7b3e8c6651fcb4aa3e2b6`. On 2026-10-22, the actual six
helper files were individually SHA-256 compared against `git show` at that
commit; all six matched. The source's neutral primitives and live-freshness
contract are verified inputs, not an archive-only compatibility assumption.
The explicit frozen runtime is supplied separately for integration tests;
unsupported platform/runtime conditions must refuse. Fixture inputs are copied
to isolated live roots and receive new synthetic test-only approvals.

## Assumptions

None.

## Decomposition

One vertical **Rules** slice: projects can compile their approved component
inventory into required checks, observe an independently selected static
delivery, and consume the native result without a component-specific runtime.
The generic gate and observer are one delivered path; dividing extraction,
packaging, and consumer wiring into horizontal slices would not independently
provide that value. No spike is needed: the inspected implementation supplies
the bounded comparison and resource behavior.

## Slices

- [037-01 — reusable static evidence](slice-01-reusable-static-evidence.md)
