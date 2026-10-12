---
adr: 0042
pass: frame-critique
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-10-12T17:51:35Z
prompt_source: review.py frame-critique adr0042; constraint-free correction
---

VERDICT: pass

REASONING:
Revised Decision6 explicitly limits file-v1 to constraint-free scored cases,
whose old constraint gate is a no-op, and rejects unsupported/invalid constraints
and native fake-actuals before model calls. This closes the acquisition-completeness
blocker without invented metrics, command execution or oldAPI hash changes.
The supplement correctly states that an installed constraint-free positive proof
does not establish constrained-case support.

RECONCILIATION NOTES:
Retain constraint-free support and deferred actual-value extraction in proof/logs.
Frame verdict only, not implementation certification.

Source: independent jig:reviewer candidate-frame-correction actual ADR0042 and
supplement03305 pass envelopes.
