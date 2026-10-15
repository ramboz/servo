---
slice: 035-01 - installed-required-gate
pass: spec-readiness
verdict: pass
reviewer: jig:reviewer / required-gate-readiness-resolution (fresh context)
reviewed_at: 2026-10-15
---

# Independent specification readiness

This is the actual judgment review of the DoR, encoding and implementation
plan, separate from `check-reviews --stage READY_FOR_REVIEW`, which validates
framing evidence only. No implementation proof or live project policy approval
is claimed.

## First review: needs-changes

The fresh `required-gate-readiness` reviewer passed the frame but blocked
readiness on three concrete gaps:

1. Disabled/reapproved JSON and removal/re-scaffold/inconsistent-marker
   transitions were incomplete. Existing forced scaffolding overwrites the
   oracle and manifest (`skills/scaffold-init/scaffold.py:556-568`).
2. Source/runtime pins were absent from the complete installed binding;
   source provenance must not be confused with current living-document bytes
   under Accepted ADR-0022.
3. Hashing argv and checks.py alone did not freeze an invoked assertion script
   or its helper artifacts (`skills/spec-oracle/checks.py:255-270`).

The plan now explicitly defines all three without revising Accepted ADRs:
disabled flags and reapproval, persistent v2 empty-policy behavior, refuse
forced re-scaffold, full binding identity including source/runtime provenance,
and reviewed executable/artifact closure distinct from mutable subjects.

## Resolution review: pass

Actual fresh-context reviewer verdict:

> VERDICT: pass
>
> REASONING:
> For 035-01 readiness, `plan.md:27–83` explicitly defines disabled/reapproved
> JSON, install/removal transitions, persistent v2 opt-in, and refusal for
> re-scaffold or inconsistent markers. Its full installed binding and bounded
> executable closure (`plan.md:35–108`) distinguish approved source provenance
> from current living-document bytes, consistent with ADR-0022, and freeze
> assertion executables/scripts/helpers without freezing mutable subject
> inputs. DoR dispositions: ADR acceptance/alignment/frame critique—satisfied;
> independent encoding/version/refusal/migration/identity review and existing
> command fixtures—satisfied; no upstream runtime-completion prerequisite—
> satisfied. The complete AC1–6 and DoD introduce no tightly coupled
> contradiction: installed veto, concurrency, publication and compatibility
> proofs remain implementation obligations, while 035-02/036 remain outside
> this readiness decision.
>
> RECONCILIATION NOTES:
> No readiness deviations identified. This verdict does not establish
> implementation compliance, approve a live installed policy, or itself
> advance lifecycle state.

Line references above identify the reviewed snapshot, not permanent anchors.
Existing readiness fixtures were separately rerun from this source:
`uvx pytest -q skills/spec-oracle/test_checks.py -k
'CommandPrimitiveTests or GeneratedArtifactCommandTests'`:
**17 passed, 117 deselected**. The first `python3 -m pytest` attempt found no
pytest in the shell's Python; the repository's available uvx launcher succeeded.

The first attempted `scripts/run_tests.py --help` unexpectedly launched the
full suite because that wrapper does not forward arguments. It was stopped;
it is not claimed as validation. No shared service or watcher was launched.
