---
slice: 038-02 — role model placement
pass: frame-critique
verdict: needs-changes
reviewer: jig:reviewer
reviewed_at: 2026-11-10T19:38:34Z
prompt_source: review.py frame-critique docs/specs/038-per-node-model-tiering/spec.md 038-02
---

VERDICT: needs-changes

REASONING:
Round 1. The split rule keys on model equality because "caches are model-scoped", but the shared lane already alternates `--agent runner`/`--agent judge` on every --resume with different tool lists and prompts; if that already breaks the cache, model equality is the wrong variable. Unprobed.

SPECIFIC ISSUES:
- [spec] Probe cache_read across an --agent switch on --resume at equal model; re-base the split trigger and A3/kill criteria on the result.
- [spec] "thinking blocks don't carry across models" is unprobed.
- [spec] DoR claims ADR-0047 Accepted while it is Proposed.
