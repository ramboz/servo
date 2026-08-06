---
status: RECONCILED
dependencies: [adr-0030, 024-01]
arch_review: true
last_verified: 2026-08-06
---

## Slice 025-01 — priority ranking and lifecycle-aware normalization

**Goal:** The heartbeat coordinator spends each tick on the highest-value work,
ranked by a ladder computed from today's signals, and dispatches normalized
records rather than raw text — skipping quarantined and claimed items. Implements
the coordinator half of
[ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
as reframed by its 2026-08-06 frame-critique.

**DoR:**
- ✅ [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md) is the governing record (Accepted).
- ✅ Inbox schema confirmed ([ADR-0010](../../decisions/adr-0010-triage-inbox-schema.md)):
  `SCHEMA_VERSION = 2` (heartbeat.py:131), canonical key order in
  `_normalize_record` (heartbeat.py:809), reader refuse-higher / warn-lower in
  `_read_inbox_for_status` (heartbeat.py:1149). Ranking signals: `_classify_ci`
  (heartbeat.py:410) yields the default-branch CI verdict; `_classify_issue`
  (heartbeat.py:447) inspects issue labels. **No signal exists** for
  resume-interrupted or active-work (deferred).
- ✅ jig board path confirmed: `docs/bugs/*.md` with frontmatter `status` +
  `claimed_by`; jig's `VALID_BUG_STATUSES` has **no `QUARANTINED`** today
  (unlanded jig ADR-0050) — servo reads a configurable skip-status set and
  fail-opens when the board is absent/unreadable.
- ✅ Depends on 024-01 (the `quarantined` status + skip).

**Acceptance Criteria:**

1. **Priority field + ladder ranking (computable rungs).** The inbox schema carries
   a `priority` field; `SCHEMA_VERSION` bumps 2 -> 3 with the ADR-0010 migration
   (discover rebuilds a `< 3` inbox on write; a v2 reader refuses a v3 inbox rc=2;
   `status` warns on a lower version). Dispatch selects by the ladder
   **security/data-loss > failing-CI > new work > idle** (tie-break: existing
   `discovered_at`, `finding_id`), where `security/data-loss` is a new
   `_classify_issue` severity gate over a configurable critical-label set.
   Observable: given a mixed inbox, a security-labelled issue is selected before a
   plain new-work finding, and a default-branch CI failure before new work; a v2
   inbox is transparently rebuilt to v3 on the next discover; a v2 reader refuses a
   v3 inbox rc=2.
2. **Lifecycle-aware normalization.** A new defect is dispatched as a structured
   record (acceptance-criteria section + security notes), never raw free text:
   **jig-bug-record-shaped** when a `docs/bugs/` board is co-installed (detected
   over the filesystem), a servo built-in structured block otherwise — never a hard
   failure. Per ADR-0011 servo **shapes** the record itself and never imports or
   subprocesses jig's `bug-fix` entry (the "via jig's bug-fix entry" intent is
   realized as filesystem-only detection + jig-shaped output). Observable: the
   dispatched prompt carries an acceptance-criteria section in both the co-installed
   and jig-absent fixtures; the finding's untrusted text stays inside the delimited
   untrusted block.
3. **Skip quarantined + claimed (fail-open).** The coordinator does not dispatch a
   `quarantined` finding (spec 024) and, **when a readable jig board is present**,
   does not dispatch a finding whose mapped jig bug is claimed or in the
   servo-configured skip-status set; when the board is absent or unreadable, it
   dispatches normally. Observable: a quarantined finding and a claimed-bug finding
   are skipped against a servo board fixture; with no board present, the same
   finding dispatches (fail-open).
4. **Boundedness preserved.** Ranking changes order only; eligibility remains gated
   by oracle / quarantine / readiness, and the whole-pass cost ceiling (ADR-0012) +
   `max-candidates` still bound the pass. Observable: enabling ranking does not
   increase the number of dispatches beyond `max-candidates`, and the same
   candidate set (reordered) is eligible.

**DoD:**
- [x] All ACs pass; test suite green (210 heartbeat tests, no regressions).
- [x] Each AC covered by ≥1 fixture; each new test shown capable of failing
      (ranking tests seed reverse-FIFO order; the uniformity + must-fix tests
      were shown red pre-fix).
- [x] Reviewed (compliance ✅ + craft ✅ + arch ✅ — craft + arch re-verified
      after fixes; the sole arch blocker was the deferred host regen, now done).
- [x] Host packages regenerated (`hosts/claude`, `hosts/codex`) + `--check` in
      sync + manifests valid.
- [x] Deviation log + reconciliation sweep recorded under this slice.

### Close-out (post-DONE)
- [x] `docs/specs/README.md` regenerated (status-board).

**Anti-horizontal-phasing check:** After this slice lands, an unattended heartbeat
run works the most important findings first and hands its edit-drivers normalized
records — end-to-end coordinator quality, building on the quarantine skip from
spec 024.

### Deviation log (after reconciliation)

1. **Normalization is jig-record-*shaped*, not jig-*invoked*.** Per ADR-0011 servo
   never imports/subprocesses jig's `bug-fix` entry; `_jig_present` is a
   filesystem `docs/bugs/` check and `_normalize_finding` emits the jig-shaped block
   itself. AC2 prose updated to match ("via jig's bug-fix entry" → filesystem-only
   detection + jig-shaped output).
2. **`_JIG_SKIP_STATUSES` is a hard-coded `frozenset({"QUARANTINED"})`**, not an
   env-configurable set (unlike the critical-label set). Scoped down deliberately —
   forward-compatible with jig ADR-0050; a real operator knob is deferred until a
   consumer needs it.
3. **`priority` is a materialized-derived VOLATILE field** (computed at discover,
   refreshed on re-observation, backfilled on migration) rather than computed at
   selection time — labels are only available at discover, so the rung is stored.
4. **`SCHEMA_VERSION` 2→3 migration is upgrade-in-place** (not the v1→v2
   drop-and-rederive), because v2 carries sticky lifecycle (incl. `quarantined`)
   that a drop would lose. `run_dispatch` normalizes the whole locked set on read
   so a partial dispatch of a v2 inbox can't leave a mixed-version file
   (orchestrator-review find + fix; `DispatchVersionUniformityTests` guards it).
5. **Byte-preservation invariant re-scoped to current-version records.** The
   pre-existing `test_other_findings_preserved_byte_for_byte` was updated to seed
   v3 records; migration legitimately rewrites a stale-version untouched record.
6. **Review-driven hardening** (post-review, in the impl): non-UTF-8 jig-board
   files read with `errors="replace"` (fail-open, not crash); `source` clamped to
   `_KNOWN_SOURCES` before the trusted-position label.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `skills/heartbeat/heartbeat.py` + `test_heartbeat.py` | `updated` | Priority ladder, 2→3 migration, normalization, claim-skip + 24 tests. |
| `hosts/{claude,codex}/.../heartbeat.py` | `updated` | Regenerated from source (`--check` in sync; dual-host parity). |
| `docs/specs/025-.../{spec.md,slice-01}` | `updated` | ACs reframed (ADR-0030); AC2 prose corrected to ADR-0011 posture. |
| `docs/specs/025-.../reviews/*` | `added` | compliance/craft/arch/reconciliation verdicts (ADR-0014). |
| `docs/specs/README.md` | `updated` | status-board regenerated. |
| `docs/decisions/adr-0030-...md` | `no-op` | Reframed + accepted in the 024 PR (#25); 025 consumes it unchanged. |
| `docs/decisions/README.md` | `no-op` | ADR-0030 already indexed. |
