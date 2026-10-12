---
status: Accepted
dependencies: []
last_verified: 2026-10-12
frame_review: true
---

# ADR-0039: Heartbeat outcome diagnostics are optional, descriptive extensions

## Status

Accepted (2026-10-12)

## Context

Heartbeat needs to preserve the stop diagnosis already emitted by its drivers.
The portable loop and goal driver emit `terminal_reason` and an optional
`terminal_breadcrumb` (`skills/agent-loop/loop.py::_summary_payload`,
`_goal_summary`). Heartbeat's original outcome projection discarded those
fields and expected only portable score history, losing the goal driver's
direct composite (`skills/heartbeat/heartbeat.py::_outcome_from_summary`).

[ADR-0010](adr-0010-triage-inbox-schema.md) records the original five outcome
fields. This decision extends that outcome, without rewriting ADR-0010 or
altering its identity, cost, lifecycle, or retention rules. It is recorded
retrospectively with [spec 033](../specs/033-heartbeat-handoff-recovery/spec.md);
the implementation preceded this decision's formal review. It does not claim
the original PR had already completed jig's ceremony.

## Decision Options Considered

### Option A: Optional descriptive fields in the existing outcome
- **Pros:** The diagnosis stays beside the score/cost/run identity; existing
  in-repository readers consume named base fields; old records need no rewrite.
- **Cons:** Unknown external readers that demand an exact key set may reject
  new outcomes; that compatibility is not established.

### Option B: Bump the inbox version for these optional diagnostics
- **Pros:** Strict external readers refuse explicitly on the new version.
- **Cons:** Existing heartbeat readers reject a higher version, requiring a
  migration/version change despite unchanged required fields and controls.

### Option C: Keep the projection and send operators to per-run state
- **Pros:** No inbox-format extension.
- **Cons:** Loses the requested direct human handoff and requires navigating
  retained worktrees to recover data already present in each driver summary.

## Recommended Decision

Choose **Option A**, narrowly for these two diagnostic fields.

1. Preserve the five base outcome fields and their order/meaning. Append
   `terminal_reason` and `terminal_breadcrumb` only when emitted as nonempty
   strings. Missing diagnostics remain absent; they are not required to read
   an old record or to dispatch a finding.
2. Keep the current inbox schema version for this optional extension. This is
   not a general license for unversioned required-field or semantic changes.
   It follows the optional-addition distinction in
   [ADR-0004](adr-0004-session-state-file-format.md#decision), applied to the
   inspected heartbeat readers; external exact-key readers are an explicit risk.
3. Normalize the portable final history composite or goal driver's direct
   composite into the same existing `oracle_composite` field, retaining zero
   and null. This restores an existing field's intended score, not a new score.
4. Display these records in human status immediately and in `inbox.md` at its
   next discovery refresh. Keep the machine status summary's structure unchanged.
5. Diagnostics are descriptive. They do not decide status, retry, budgets,
   admission, or quarantine. A goal turn cap never manufactures plateau evidence.

## Consequences

**Becomes easier:**
- Operators can see a run's failure diagnosis and supplied fix hint next to its
  real score without reading child stderr or traversing run-state files.
- Both driver summary shapes produce a useful score in the same outcome field.

**Becomes harder:**
- Any known exact-key external reader needs an explicit compatibility decision;
  the bounded in-repository guarantee must not be advertised as universal.
- The generated discovery view is not immediate dispatch output; documentation
  must keep that timing distinct from the live read-only `status` command.

## Assumptions

- Unknown external consumers may depend on an exact old outcome key set.
  That set has not been enumerated. Compatibility claims are limited to the
  inspected in-repository readers and legacy records, with executable coverage.
- In-repository grounding: `_normalize_record` preserves the outcome object;
  `_outcome_cost_usd` reads the existing cost field; `_merge_one` retains
  sticky outcome data; `_select_candidates` reads status/actionability rather
  than diagnostic fields. Spec 033 requires regression coverage for these edges.

## Kill criteria

- A real supported consumer rejects the optional fields or misinterprets them:
  reconsider a version bump/explicit compatibility boundary before broadening
  the contract.
- Any diagnostic begins driving retry/admission or overwriting score/control
  evidence: stop that change and require a separate decision.

## Open questions

None within this bounded extension. Owner acceptance and the mandatory frame
review are still required while this record remains Proposed.
