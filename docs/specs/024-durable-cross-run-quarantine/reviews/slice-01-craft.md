---
slice: 024-01 — cross-run quarantine record, quarantined status, and evidence-gated re-admission
pass: craft
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-08-06T17:40:07Z
prompt_source: independent craft review (024-01)
---

Independent craft/code-quality review of slice 024-01 (general-purpose, Opus, no impl-conversation access).

VERDICT: pass

The new code is idiomatic with the surrounding file: imperative AC/ADR-referenced docstrings,
helper-family naming, reuse of `_fingerprint`/`_atomic_write`/`_now_iso`/`_emit_breadcrumb`.
Error handling is fail-soft exactly as the rest of the module (`_read_quarantine_record` mirrors
`_read_inbox_for_discover`; a failed record write is non-fatal). Edge cases handled: non-dict
evidence → {}, missing finding_id, non-str run_id → None. Concurrency sound: record write +
reconcile/unlink both run inside the existing `.inbox.lock` flock. `_dispatch_one`'s tuple return
keeps the ADR-0010 outcome shape intact; the sole production call site is updated. Tests are
hermetic (tempdir + real git / empty-PATH), deterministic (no clock assertions), and non-vacuous
(expected pointers computed via the real helper; two-target key-stability test).

The one substantive nice-to-have — a record-write failure previously left the finding
`quarantined` with no record and thus un-re-admittable — was fixed in the follow-up commit
(fall back to `tried`), which also makes the human release gesture (delete the record) work.
Remaining nits (nested-key projection assumption; a section-banner comment) are cosmetic.
