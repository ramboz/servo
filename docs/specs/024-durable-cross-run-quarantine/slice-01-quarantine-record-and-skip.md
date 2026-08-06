---
status: RECONCILED
dependencies: [adr-0030]
arch_review: true
last_verified: 2026-08-06
---

## Slice 024-01 — cross-run quarantine record, quarantined status, and evidence-gated re-admission

**Goal:** A finding that plateaus is durably quarantined across runs and stops
being re-dispatched, reopening only on new diagnostic evidence — with the
quarantine legible to a future jig reader for attest-only bug closure. Implements
the quarantine half of
[ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
as reframed by its 2026-08-06 frame-critique.

**DoR:**
- ✅ [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md) is the governing record (Accepted).
- ✅ Plateau persistence confirmed: `loop.py._check_plateau` (loop.py:541) sets
  `terminal_reason = "oracle_plateau"` (loop.py:2212); the loop **summary line**
  carries `terminal_reason` (`_summary_payload`, loop.py:1694). `loop.py` has no
  `finding_id` and, in dispatch, runs against the *worktree*, not the real target
  — so **`heartbeat.py` is the writer**.
- ✅ Dispatch seam confirmed: `heartbeat.run_dispatch` (heartbeat.py:1789) records
  each outcome via `_outcome_from_summary` (heartbeat.py:1638), which currently
  **drops `terminal_reason`** — the seam to extend. `_select_candidates`
  (heartbeat.py:1338) is `actionable AND status == open`; `_merge_findings`
  never resets a status to `open` (heartbeat.py:759). Reusable `_fingerprint`
  (heartbeat.py:305).
- ✅ Fingerprint/key decided: the file **key is the `finding_id`** (already stable,
  content-derived); `failure_signature` + `evidence_pointer` are stored fields.

**Acceptance Criteria:**

1. **Cross-run quarantine write, keyed by `finding_id`.** When a dispatched loop's
   summary carries `terminal_reason == oracle_plateau`, `heartbeat.py` writes
   `<target>/.servo/quarantine/<finding_id>.json` (schema_version, finding_id,
   source, failure_signature, evidence_pointer, evidence_location, run_id,
   quarantined_at) and sets the finding's inbox status to `quarantined`. `loop.py`
   is unchanged. Observable: a plateau-summary fixture produces the file; the file
   key (`finding_id`) is identical across two independent run-ids for the same
   finding.
2. **Quarantined findings are not re-dispatched.** A `quarantined` finding is not
   in the `open`-only candidate set, so a subsequent dispatch tick spawns no loop
   for it while other `open` findings still dispatch. `quarantine` is in
   `_NON_PROVISIONED_SERVO_DIRS` (never copied into a worktree); the quarantine
   state is read from the **real** target's `.servo/quarantine/`. Observable: a
   second tick over the same inbox witnesses no-redispatch for the quarantined
   finding; an `open` finding beside it dispatches.
3. **Evidence-gated re-admission (record presence + pointer change).** On a
   discover pass, a `quarantined` finding is re-admitted (`quarantined -> open`,
   record removed) when **either** its quarantine record is gone (the human
   release gesture / a torn record — the record *is* the quarantine) **or** its
   current `evidence_pointer` (hash of the `evidence` dict minus `url` / `*_url` /
   `*_at`) **differs** from the recorded one; an unchanged pointer with a live
   record keeps it `quarantined`. A failed record write falls back to `tried`
   (never park record-less). Observable: same stable evidence + live record → stays
   quarantined; a changed stable-evidence pointer → re-admitted; a deleted record →
   re-admitted; a `run_url`-only change → does **not** re-admit.
   **v1 disclosure:** for today's CI/issue sources the stable projection equals the
   finding_id inputs, so the *automatic* (pointer-change) path is a forward hook —
   the human quarantine queue (delete the record) is the real v1 release valve.
4. **Servo-owned attest legibility.** The quarantine record validates against a
   servo-owned schema fixture and exposes exactly the projection a future jig
   reader needs (the `finding_id <-> bug` mapping key + the evidence location) for
   jig ADR-0050's attest-only ingest. No scorer is invoked on any servo path that
   produces the record, and servo does not import or hard-depend on jig.
   Observable: a schema round-trip test passes against servo's fixture; the record
   carries `finding_id` + `evidence_location`; jig is never invoked to produce it.

**DoD:**
- [x] All ACs pass; test suite green (189 heartbeat tests, no regressions).
- [x] Each AC covered by ≥1 fixture; each new test shown capable of failing
      (8/11 original failed pre-impl; 3 new behaviours added post-review).
- [x] Reviewed (compliance ✅ + craft ✅ + arch ✅ — re-verified after fixes).
- [x] Host packages regenerated (`hosts/claude`, `hosts/codex`) + manifests valid.
- [x] Deviation log + reconciliation sweep recorded under this slice.

### Close-out (post-DONE)
- [x] `docs/specs/README.md` regenerated (status-board).

**Anti-horizontal-phasing check:** After this slice lands, a plateaued finding is
attempted once, then durably quarantined + legible across ticks, and can only
return to dispatch on genuinely new evidence — end-to-end anti-thrash for the
coordinator, independent of the priority work in spec 025.

### Deviation log (after reconciliation)

1. **Writer is `heartbeat.py`, not `loop.py`** (vs the *original* recorded spec;
   matches the reframed ADR-0030/spec). loop.py runs against an ephemeral worktree
   and has no `finding_id`; heartbeat owns both. `loop.py` is byte-unchanged.
2. **New `quarantined` inbox status value, no `SCHEMA_VERSION` bump.** A status
   *value* (not a structural field) is a tolerated vocabulary extension —
   `_status_counts`/renderers surface it via `.get`, `_select_candidates` stays
   open-only, `_STICKY_STATUSES` gained it. (Contrast 025-01's `priority` *field*,
   which does bump 2→3.)
3. **`bug_ref: null` reserved field** in the record beyond AC1's enumerated keys —
   the `finding_id ↔ bug` slot AC4 requires for a future jig reader; servo never
   derives a jig id, so it writes null (ADR-0011 boundary).
4. **Record-presence release + write-failure fallback** (arch-review response):
   AC3 re-admits on a *missing* record (human release gesture / self-heal), not
   only a changed pointer; a failed record write falls back to `tried` rather than
   parking record-less. AC3 wording updated to match; disclosure added that the
   automatic pointer path is a v1 forward hook (stable CI/issue evidence carries no
   diagnostic content today).
5. **Test-side `importlib` load of `heartbeat.py` / `loop.py`** — a new test
   pattern (the file is otherwise subprocess-driven), justified for unit-testing
   pure helpers and the loop↔heartbeat plateau-string contract test. Does not
   violate the dependency-free invariant (that guards *heartbeat* importing
   loop/gate — the reverse).

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `docs/decisions/adr-0030-...md` | `updated` | Reframed via frame-critique (writer, anti-thrash premise, ladder, release rule, jig contract, schema) + v1 disclosure. |
| `docs/decisions/reviews/adr-0030-frame-critique.md` | `added` | Frame-critique evidence (ADR-0020 OQ2 gate). |
| `docs/specs/024-.../{spec.md,slice-01}` | `updated` | DRAFT → reframed READY_FOR_IMPLEMENTATION → IN_PROGRESS; ACs rewritten to the buildable contract. |
| `docs/specs/025-.../{spec.md,slice-01}` | `updated` | Same ADR reframe (ladder narrowed, schema bump, fail-open jig); code lands in the stacked 025 PR. |
| `skills/heartbeat/heartbeat.py` + `test_heartbeat.py` | `updated` | Quarantine impl + 14 tests. |
| `hosts/{claude,codex}/.../heartbeat.py` | `updated` | Regenerated from source (dual-host parity). |
| `docs/specs/README.md` | `updated` | status-board regenerated. |
| `skills/agent-loop/loop.py` | `no-op` | Unchanged — heartbeat is the writer. |
| `docs/decisions/README.md` | `no-op` | ADR-0030 already indexed. |
