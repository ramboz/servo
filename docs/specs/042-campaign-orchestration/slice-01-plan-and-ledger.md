---
status: DONE
kind: feature
dependencies: [adr-0049, 038-03, 040-01]
last_verified: 2026-11-12
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

### Deviation log (after reconciliation)

The original ACs are preserved above. Review rounds:
- **Round 1:** compliance PASS, craft PASS; **arch needs-changes** (one blocker:
  `docs/architecture.md` did not document the new `.servo/campaigns/` runtime
  artifact / third dispatch surface); **frame-critique needs-changes** (two
  findings, below).
- **Round 2:** all re-reviews cleared — **arch PASS** (architecture.md bullet +
  all nits + OQ2), **frame-critique PASS** (both findings fixed, verified against
  source + a live repro), **compliance PASS** (AC1–AC4 re-verified, AC3
  additionally hardened). A subsequent one-line hardening (reject a negative
  `cost_usd`) closed the compliance-noted unreachable edge.

Load-bearing choices made during implementation:

1. **New module `skills/heartbeat/campaign.py`** with its own `main()`
   (`init`/`record`/`status`), rather than folding the campaign CLI into
   `heartbeat.py` (already ~155 KB). The surface is `campaign …`, distinct from
   `heartbeat.py …`.
2. **The 038 `models` validator is reached by a dynamic `spec_from_file_location`
   load of `../agent-loop/loop.py`**, not a static import and not a mirrored copy
   (the dependency-free skill invariant, bug 005; the probe `score.py` uses for
   `fidelity_eval.py`). This makes AC1's "same validator, same messages" literally
   true; mirroring would drift. The loop's message is preserved verbatim, prefixed
   with an `item '<id>': ` locator so a multi-item plan names the failing item.
3. **Ledger discipline: atomic write mirrored, lock made BLOCKING.** `_atomic_write`
   mirrors heartbeat.py (ADR-0004); `_ledger_lock` is a **blocking** `flock`
   `LOCK_EX`, diverging from the inbox's **non-blocking** `LOCK_EX|LOCK_NB` — a
   recorded outcome is unique data that must never be dropped, so a concurrent
   `record` waits. Mirror over import so the concurrent `record`/`status` paths
   never load heartbeat.py; `init` does load loop.py for the validator (the
   docstring states this precisely).
4. **Plan schema (`schema_version: 1`):** top-level keys exactly
   `{schema_version, items}`; per-item required `{id, title, prompt, oracle_ref,
   budget, models}`; budget exactly `{unit ∈ usd|credit, ceiling > 0}`; unknown
   top-level / item / budget keys rejected; `oracle_ref` a required non-empty
   string stored verbatim (not run). Lean A4-checkpoint shape; 042-02+ extend via
   the version.
5. **Cost-unit rule keys on the two reliable signals, not null-vs-numeric
   (frame-critique Round 1 PRIMARY).** loop.py's refusal/preflight helpers
   (`_refuse_preflight`/`_refuse_plan`/`_refuse_readiness`/`_refuse_goal`) hardcode
   `cumulative_cost_usd: 0.0` regardless of host, and `_unpriced_oracle_preflight`
   is host-agnostic — so a legitimate credit/Copilot run can emit numeric
   `cost_usd: 0.0`. The original rule ("credit ⇒ null") dropped such a real
   outcome. Fixed: a USD item rejects only a **null** cost; a credit item rejects
   only a **positive** cost; `0.0` is accepted either way. AC2's "wrong unit"
   refusal (rc=2, ledger unchanged) is preserved for the real mismatches.
6. **`campaign record --tier` accepts only `{servo, advisory}` (frame-critique
   SECONDARY + arch OQ2).** `wrapped` is a valid LEDGER tier (schema + enforced-spend
   accounting handle it, ready for 042-04) but is "verified, not declared"
   (ADR-0049): the CLI refuses `--tier wrapped` until 042-04's run-id/fingerprint
   verifier earns it, so no unverified wrapped spend is ever counted as enforced.
7. **Credit enforced-amount deferred to 042-04.** The 040 line carries no credit
   number (040-01 deviation log); a credit entry records `cost_usd: null` and is
   not counted in `enforced_cost_usd`. `campaign status` **marks** credit items
   ("spend tracked in AI credits, re-derived in 042-04") rather than implying `$0`
   (frame-critique A4 note).
8. **`self_reported` is derived from the tier** (advisory ⇒ true), never
   caller-supplied; `enforced_cost_usd` sums `cost_usd` over non-self_reported
   entries only — an advisory worker's cost can never be laundered into enforced
   spend.
9. **`OUTCOME_SCHEMA_VERSION` / `OUTCOME_RESULTS` mirrored from loop.py**, not
   dynamically loaded (small value constants; `record` is the hot path). A parity
   test (`test_outcome_constants_track_loop`) fails if loop.py's 040 contract
   drifts from the mirror (craft nit).
10. **`_validate_outcome`** requires `servo_outcome == 1`, `result` in-enum, and a
    present `cost_usd` (null or a **non-negative** number — a negative is rejected
    as impossible input, closing a compliance-noted edge where it would subtract
    from enforced spend). `rung`/`reason` are stored if present but not
    independently required (compliance MINOR) — kept lenient so over-strict gating
    can't reject valid future 040 lines.
11. **`status` fails closed on a corrupt ledger line:** a malformed line makes
    `_read_ledger` raise, which `cmd_status` catches (`json.JSONDecodeError` →
    rc=2 with a single reason, not a traceback; craft/compliance/arch nit, mirroring
    `cmd_init`/`cmd_record`'s JSONDecodeError→refusal mapping).
12. **`SERVO_CAMPAIGN_LOOP_PY` env override** on the loop.py path (arch nit;
    parity with heartbeat.py's `SERVO_HEARTBEAT_LOOP_PY`).
13. **`docs/architecture.md` updated** with the `.servo/campaigns/` runtime-artifact
    entry and the "third dispatch surface" (ADR-0049 Consequences) — the arch
    Round-1 blocker. The slice DoD did not list architecture.md; it is now in the
    reconciliation sweep.
14. **Campaign id:** `--id` optional (slug-validated), generated `cmp-<hex12>` and
    printed when omitted; `init` refuses an existing id dir (no clobber).
    `record`/`status` take `<id>` + `--target` (default cwd).
15. **`status` totals** also report `budget`/`error` counts, `self_reported_cost_usd`
    and `credit_items` beyond the AC-named passed/plateau/blocked; `open` = any
    item whose latest result ≠ `passed` (including never-recorded items).

Red evidence: the whole feature was witnessed red (no `campaign.py` → import-time
collection error, all tests fail). The frame-critique Round 1 witnessed the
cost-unit defect as a live end-to-end failure (a Copilot `unpriced_oracle_components`
0.0 outcome dropped from a credit ledger); Round 2 pins the fix with
`test_credit_item_accepts_zero_cost_refusal`.

Deferred to `docs/refinement-todo.md` (owner, 042 parity-release): promote the 038
`models` validator to a declared shared surface (e.g. `skills/_common/`) rather than
reaching into loop.py's private `_validate_models` (arch OQ1, test-guarded meanwhile);
the O(n) full-file ledger rewrite per append is a deliberate ADR-0004 crash-atomicity
trade-off (arch OQ3).

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | The front door lists no campaign CLI. |
| `docs/specs/README.md` (board) | `deferred` | Regenerated by `workflow.py status-board` at the close step, before DONE. |
| `docs/product-vision.md` | `no-op` | No scope or design-principle change. |
| `docs/architecture.md` | `updated` | New `.servo/campaigns/` runtime artifact + the "third dispatch surface" (ADR-0049). |
| `docs/decisions/adr-0049-…` | `no-op` | Accepted; 042-01 implements it. Implementation choices are in this deviation log + the arch review. |
| `docs/decisions/adr-0004 / adr-0010` | `no-op` | The mirrored atomic-write / flock discipline cites them; no contract change. |
| `docs/decisions/README.md` (ADR index) | `no-op` | No new ADR. |
| `skills/heartbeat/SKILL.md` + 3 host copies | `updated` | New Campaign section (corrected cost-unit rule, `--tier {servo&#124;advisory}`, credit marker); hosts regenerated + drift-checked (sync gate green). |
| `skills/heartbeat/campaign.py` + 3 host copies | `new` | The feature. |
| `skills/heartbeat/test_campaign.py` | `new` | TDD coverage (source-only; tests are not vendored to hosts). |
| `docs/specs/042-…/reviews/` | `new` | compliance / craft / arch / frame-critique / reconciliation verdicts. |
| `docs/refinement-todo.md` | `updated` | 038-validator shared-surface (owner); O(n) ledger-append trade-off. |
| `CLAUDE.md` / `AGENTS.md` primers | `no-op` | No active campaign primer section to compress. |
| `docs/inbox.md` / `docs/memory/**` | `no-op` | No new domain terms or rules beyond the spec + ADR. |
| `agents/*.md` | `no-op` | Unchanged. |
| `docs/specs/042-…/spec.md` | `updated` | `status: DRAFT → IN_PROGRESS` rollup (`workflow.py transition`). |
| `docs/specs/042-…/slice-01-…md` | `updated` | This slice doc — lifecycle transitions + hosts the deviation log + sweep. |
