---
slice: 025-01 — priority ranking and lifecycle-aware normalization
pass: arch
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-08-06T18:31:40Z
prompt_source: independent arch review (025-01); host regen resolved the sole blocker
---

Independent architecture review of slice 025-01 (general-purpose, Opus, no impl-conversation access).
Changes the dispatch contract, bumps the inbox SCHEMA_VERSION 2→3, adds a soft jig-board dependency.

VERDICT: pass (design sound on all 5 axes; the sole needs-changes blocker — stale host packages —
was the deferred final regen, now done: `build_host_packages.py --check` reports in sync, both host
copies carry the `_KNOWN_SOURCES` hardening + the errors="replace" fail-open, manifests agree).

Axes verified SOUND:
1. Schema migration (2→3) — lossless. Discover upgrades v2 in place (sticky status/attempts/outcome
   preserved, priority backfilled; quarantined retained), drops only v1/unknown. A bare dispatch of a
   uniform-v2 inbox normalizes the WHOLE locked set to v3 before any write-back, so a partial dispatch
   provably cannot leave a MIXED file that the next read refuses. Covered by the migration +
   version-uniformity tests.
2. Boundary integrity (ADR-0011) — no jig import/subprocess; `_jig_present` filesystem-only;
   `_claimed_in_jig_board` fail-opens on every failure edge; `_read_frontmatter` dependency-free +
   tolerant; `read_text(errors="replace")` hardens against non-UTF-8 foreign files.
3. Priority as materialized-derived field — volatile (refreshed on re-observation), backfilled on
   migration, tolerant of hand-edits; sticky records are never candidates so a stale priority can't
   mis-rank; the one transient FIFO window self-corrects on the next discover.
4. Dispatch-contract change + injection resistance — the normalized work-item's title uses only
   `source` (clamped to `_KNOWN_SOURCES`) + the hashed finding_id; untrusted text stays inside the
   delimited block.
5. Ladder honesty — the four ADR-sanctioned rungs only; the two unsourced rungs deferred, not faked.

Suite 210 green; ruff clean.
