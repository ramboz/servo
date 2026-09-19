---
slice: 028-01 — structured-policy
pass: craft
verdict: pass
reviewer: jig:reviewer (craft)
reviewed_at: 2026-08-28T02:58:27Z
prompt_source: review.py craft 028-01
substrate: non-interactive
---

Craft pass (independent jig:reviewer): no blockers; belt-and-braces v1 rejection (explicit message + hash staleness) with discriminating-message tests; self-verifying v2 hash pin. Fixes: corrected the false DoR 'Probe #1 done' to 'could not run in-env → fallback adopted'; added a weight-only staleness case (AC3); SKILL.md notes dimension weight is advisory-to-judge under the fallback. AC5 deferral → deviation log.
