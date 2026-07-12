---
adr: 0028
pass: frame-critique
verdict: pass
reviewer: arch-review
reviewed_at: 2026-07-12T18:18:46Z
prompt_source: review.py frame-critique docs/decisions/adr-0028-committed-dual-host-plugin-packages.md
---

Adversarial architecture review found the original premises sound after two corrections: add the root Codex remote marketplace pointer and make archive smoke verify the complete committed package. Both are implemented and verified. No remaining frame blocker; accepting the dual-host committed-package decision is appropriate.
