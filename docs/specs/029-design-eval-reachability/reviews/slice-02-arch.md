---
slice: 029-02 — subagent-advisory
pass: arch
verdict: pass
reviewer: jig:reviewer (arch)
reviewed_at: 2026-08-28T01:42:17Z
prompt_source: review.py arch 029-02
substrate: non-interactive
---

Arch pass (independent jig:reviewer): non-gating made STRUCTURAL (entrypoint refusal), advisory path cleanly outside the oracle seam (preserves ADR-0031/0032 §7), composes with 029-01 manual provider, labelled non-pipeable output. Fixed post-review: advisory_read now stacks the manual-capture advisory (both honesty tells fire) + tested. Logged for later: score()/advisory_read scoring-loop duplication; channel has no correlation id (concurrent same-dir advisory runs would collide) — out of scope today.
