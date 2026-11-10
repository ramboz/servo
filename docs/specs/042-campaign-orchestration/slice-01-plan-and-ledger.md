---
status: DRAFT
kind: feature
dependencies: [adr-0049, 038-03]
last_verified:
arch_review: true
frame_review: true
---

## Slice 042-01 — plan and ledger

**Goal:** A campaign plan (a list of independent work items, each with its
oracle, budget and `models` block) and its append-only, lock-guarded ledger
of typed outcomes exist as servo-owned files, readable by `campaign status`.

**DoR:**
- The owner has explicitly accepted ADR-0049.
- The outcome line exists, or this slice includes it (spec 040-01).

**Acceptance Criteria (sketch):**

1. `campaign init <target> --plan <file>` validates a plan file and writes
   `.servo/campaigns/<id>/plan.json` and an empty `ledger.jsonl`.
   - The plan file has `schema_version: 1` and `items: [{id, title, prompt,
     oracle_ref, budget{...}, models{...}}]`.
   - The `models` block uses the spec 038 schema and validator.
   - Item ids are unique and match `^[a-z0-9][a-z0-9-]*$`.
   - Validation fails closed with rc=2 and a reason, and writes nothing.
2. `campaign record <id> <item> --outcome <line>` appends one typed outcome.
   - The append is guarded by `flock` and written atomically, the same
     discipline as the heartbeat inbox.
   - The outcome is spec 040's line: result, rung, cost and reason.
   - The ledger entry adds `tier` (`servo` | `wrapped` | `advisory`) and
     `self_reported` (true for advisory).
   - The aggregate ceiling counts cost only from `servo` and verified
     `wrapped` entries.
   - A malformed outcome is refused.
3. `campaign status <id>` prints each item's latest outcome, the totals
   (cost, passed, plateau, blocked) and the items still open. It is read-only.
4. The campaign's state lives only under `.servo/campaigns/`. servo never
   reads jig files: a jig reframe manifest is converted into a servo plan file
   by jig or a human.

**Anti-horizontal-phasing check:** a human or a host can declare a campaign's
work list and see one compact ledger of what each worker did and what it
cost.
