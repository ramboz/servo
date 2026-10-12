---
adr: 0040
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-10-12T16:33:40Z
prompt_source: review.py frame-critique adr0040
---

VERDICT: pass

REASONING:
The highest-risk assumption is that deliberately accepting native defaults still
permits meaningful frozen statistical gating. Same-version backend changes can
shift scores without increasing sample variance, so the lower-bound aggregator
cannot establish backend stability. The frame survives because it expressly
disclaims that guarantee, requires artifact-level consent and re-freeze, rejects
unsupported numeric controls and preserves human/statistical authority.

SPECIFIC ISSUES:
- Nonblocking residual: common-mode backend shifts can invalidate previously
  accepted statistical behavior without changing hashes. The re-review kill
  criterion acknowledges this; exact CLI version must not be presented as
  detecting such shifts.

RECONCILIATION NOTES:
Record freezing a decoding policy versus pinning numeric parameters.
No implementation conformance or live capability success is established.

Source: fresh jig:reviewer frozen-policy-frame actual returned ADR0040 envelope.
