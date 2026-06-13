---
status: DRAFT
dependencies: [011-01]
last_verified:
---

## Slice 011-02 — triage-state-spine

**STATUS: DRAFT**

**Goal:** The inbox becomes the **state spine**: a stable `finding_id`
fingerprint dedupes across runs; a status lifecycle
(`open`→`tried`→`passed`/`skipped`) is tracked; `heartbeat.py status` reads it
back. The next heartbeat **resumes** — already-passed/tried findings are not
re-surfaced as new work.

> **Goals-only stub — ACs deliberately not pinned yet.** Acceptance criteria
> want grounding against (a) slice 011-01's spike findings (the real `gh`/`git`
> surface, the `finding_id` fingerprint behaviour) and (b) a real project that
> wants scheduled discovery — see the spec's [slice index](spec.md) and the
> 011-01 spike-shape note. **To begin:** SPIDR-split this into fleshed ACs and
> transition to `READY_FOR_REVIEW`. This file exists as a `DRAFT` stub so spec
> 011 rolls up `IN_PROGRESS` (not falsely `DONE`) now that 011-01 has landed.
> The crystallizing decision here is the **triage-inbox schema + dedupe-identity
> ADR** (next free number, reciprocal to ADR-0004) — see spec.md "ADR
> candidates". `dependencies:` above is a provisional hint; refine at split.
