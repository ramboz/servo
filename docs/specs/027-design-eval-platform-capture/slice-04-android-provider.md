---
status: DRAFT
dependencies: [adr-0032, 027-02]
last_verified:
---

## Slice 027-04 — blessed Android provider

**Goal:** Ship a built-in **Android** capture provider — `adb … exec-out
screencap` for pixels, a state driver for per-screen seeding, and chrome-frame
normalization (crop status/navigation bars to the reference's logical frame) —
so a native Android (Jetpack Compose) UI can be scored against the same mockups
as its web build. Degrades honestly to `env_error` when `adb`/device absent.

**Scope note:** the first blessed native built-in. Chrome-cropping here is
new from-scratch work (no DOM/selector), per [ADR-0032](../../decisions/adr-0032-design-eval-capture-providers.md)
§5; state equivalence to the web seed is project-authored, not certified.

**Acceptance Criteria:** _TBD when picked up (READY_FOR_IMPLEMENTATION)._

**DoD:** _Standard slice DoD; ACs + tests authored at pickup._
