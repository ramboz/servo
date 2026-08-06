---
status: DONE
dependencies: [adr-0030, adr-0011, adr-0012]
last_verified: 2026-08-06
---

# Spec 024 — durable-cross-run-quarantine

> Implements the quarantine half of
> [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
> (Accepted; reframed by its 2026-08-06 frame-critique). This is the **servo half**
> of the durable failure-quarantine piece; the jig half is jig spec 105 (jig
> ADR-0050), which is **not landed** — servo's contract is self-contained and
> fail-open per ADR-0011, and the live jig round-trip is a deferred integration
> slice.

## Why this spec

A finding dispatched by the heartbeat that **plateaus** (`oracle_plateau`) is
parked as an ordinary sticky-`tried` failure: ADR-0010's lifecycle attempts it
once and never re-selects it. Two gaps follow (ADR-0030 Context §1): the park is
**not legible** — a reviewer or a future jig reader cannot see *that* it plateaued
or *where* its evidence lives — and there is **no principled, evidence-gated
re-admission** path, so the finding can never be retried even when new diagnostic
evidence appears (and any future re-dispatch capability would have no thrash
guard). [ADR-0030](../../decisions/adr-0030-durable-quarantine-and-lifecycle-coordinator.md)
decides a durable, cross-run quarantine record (written by `heartbeat.py`, keyed
by `finding_id`), a distinct `quarantined` inbox status, and evidence-gated
re-admission — the servo mirror of jig ADR-0050's release rule.

## Goals

1. On a dispatched loop whose summary carries `terminal_reason == oracle_plateau`,
   **`heartbeat.py`** (which owns the `finding_id` and the real target) writes a
   cross-run `<target>/.servo/quarantine/<finding_id>.json` record and sets the
   finding's inbox status to a new terminal value `quarantined`. `loop.py` is
   unchanged (it runs against an ephemeral worktree and has no `finding_id`).
2. `_select_candidates` stays `open`-only, so a `quarantined` finding is never
   re-dispatched — the anti-thrash property (witnessed no-redispatch across ticks).
   `quarantine/` is added to `_NON_PROVISIONED_SERVO_DIRS` so it is never copied
   into a dispatch worktree; the skip reads the **real** target's quarantine dir.
3. A `quarantined` finding is **re-admitted** (`quarantined -> open`, record
   removed) when its record is gone (the human release gesture / a torn record)
   **or** its `evidence_pointer` — a hash over the finding's *stable* evidence
   projection (the `evidence` dict minus `url` and any `*_url` / `*_at` key, so a
   mechanical CI re-run does not change it) — differs from the recorded one. A
   failed record write falls back to `tried` (never parked record-less). For
   today's CI/issue sources the stable projection equals the finding_id inputs, so
   the automatic path is a forward hook — the human quarantine queue (delete the
   record) is the v1 release valve.
4. Attest-only legibility: the record exposes exactly the `finding_id <-> bug` +
   evidence-location projection a future jig reader needs (jig ADR-0050), and
   validates against a **servo-owned** schema fixture. servo owns the schema; no
   scorer runs on any jig-facing path; servo never hard-depends on jig.

## Vertical slices

- **024-01 — cross-run quarantine record + status + evidence-gated re-admission:**
  the `finding_id`-keyed record, the `heartbeat.py` write on plateau, the
  `quarantined` status + `open`-only skip, and the new-evidence re-admission. See
  the slice file for ACs.

## Notes

- The quarantine **key is the `finding_id`** (already content-derived and
  run-id-independent). The `failure_signature` (e.g. `oracle_plateau`) and
  `evidence_pointer` are *stored fields*, not part of the key (ADR-0030 FLAW 6).
- Boundary: servo writes; jig does cheap reads via subprocess/filesystem only
  (ADR-0011 / jig ADR-0022) — no shared imports, jig never re-derives a score.
