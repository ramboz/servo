---
status: DRAFT
dependencies: [adr-0032, 027-02]
last_verified:
---

## Slice 027-05 — blessed iOS provider

**Goal:** Ship a built-in **iOS** capture provider — `xcrun simctl io booted
screenshot` for pixels, a state driver for per-screen seeding, and chrome-frame
normalization to the reference's logical frame — so a native iOS/SwiftUI UI can
be scored against the same mockups. Degrades honestly to `env_error` when the
simulator/`simctl` is absent.

**Scope note:** the second blessed native built-in, parallel in shape to the
Android provider (027-04). Same per-platform-seeding and frame-normalization
contract from [ADR-0032](../../decisions/adr-0032-design-eval-capture-providers.md).

**Acceptance Criteria:** _TBD when picked up (READY_FOR_IMPLEMENTATION)._

**DoD:** _Standard slice DoD; ACs + tests authored at pickup._
