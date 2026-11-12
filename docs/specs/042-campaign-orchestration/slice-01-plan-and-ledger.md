---
status: DRAFT
kind: feature
dependencies: [adr-0049, 038-03, 040-01]
last_verified:
arch_review: true
frame_review: true
---

## Slice 042-01 — plan and ledger

**Goal:** A campaign plan (a list of independent work items, each with its
oracle, budget and `models` block) and its append-only, lock-guarded ledger of
typed outcomes exist as servo-owned files, created and read by `campaign init`
/ `campaign record` / `campaign status`. No worker runs yet — this slice is the
file contract every later mode builds on, and the **A4 checkpoint** (if a
representative campaign's items cannot be oracle-gated, stop here and revisit).

**DoR:**
- ADR-0049 is Accepted (2026-11-11). ✓
- The typed outcome line exists: slice 040-01 is DONE (this slice depends on it,
  since the ledger stores that `servo_outcome` record).

**Acceptance Criteria:**

1. `campaign init <target> --plan <file>` validates a plan file and writes
   `.servo/campaigns/<id>/plan.json` and an empty `ledger.jsonl`.
   - The plan file has `schema_version: 1` and `items: [{id, title, prompt,
     oracle_ref, budget{...}, models{...}}]`.
   - The `models` block uses the spec 038 schema and validator (038-03), and is
     rejected with the same messages when malformed.
   - Item ids are unique and match `^[a-z0-9][a-z0-9-]*$`.
   - An unknown top-level key, a missing required field, a duplicate id, an
     empty `items` list, or a `schema_version` other than 1 fails closed with
     rc=2 and a single reason, and writes nothing (no partial `plan.json`, no
     `ledger.jsonl`).
   - `oracle_ref` is recorded as data; this slice does not run it (042-02/03
     do).
2. `campaign record <id> <item> --outcome <line>` appends one typed outcome.
   - The append is guarded by `flock` and written atomically — the same
     discipline as the heartbeat inbox (`_inbox_lock`, `_atomic_write` in
     `skills/heartbeat/heartbeat.py`).
   - The outcome is spec 040's line (`servo_outcome: 1`): `result`, `rung`,
     cost and `reason`.
   - The ledger entry adds `tier` (`servo` | `wrapped` | `advisory`) and
     `self_reported` (true for advisory; set by 042-03).
   - The aggregate ceiling counts cost only from `servo` and verified `wrapped`
     entries; `self_reported` cost is never counted as enforced spend.
   - An unknown item id, a malformed outcome line, or a cost in the wrong unit
     (USD where the plan is credit-denominated, or vice versa) is refused with
     rc=2 and the ledger is left unchanged.
3. `campaign status <id>` prints each item's latest outcome, the totals (cost,
   passed, plateau, blocked) and the items still open. It is read-only and
   writes nothing.
4. The campaign's state lives only under `.servo/campaigns/`. servo never reads
   jig files: a jig reframe manifest is converted into a servo plan file by jig
   or a human, never read by servo directly.

**DoD:** ACs pass with tests (TDD); compliance + craft + arch reviews (slice
declares `arch_review: true`); reconciliation sweep + deviation log.

**Anti-horizontal-phasing check:** a human or a host can declare a campaign's
work list and see one compact ledger of what each worker did and what it cost —
end to end, with no worker execution yet, which is the A4 go/no-go.

## Assumptions

- **A4 (oracle coverage):** a campaign's work items can be expressed as
  oracle-gated items, each with a `gate.py`-scorable `oracle_ref`. If most real
  items can't carry an oracle, the campaign layer doesn't serve its motivating
  case — this slice is the checkpoint where that is decided (ADR-0049 kill
  criterion A4).
