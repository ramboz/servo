---
slice: 028-03 — agents
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-09-18T18:55:46Z
prompt_source: review.py (compliance+craft pass)
---

Independent review (compliance + craft) of slice 028-03 by a fresh jig:reviewer.
**VERDICT: PASS.** All 5 ACs met with tests that genuinely pin behavior (agents
rendered to `.github/agents/*.agent.md`; tools mapped Read→view/…/Bash→bash with a
fail-loud unmapped guard; model-neutral — raises on `model:`; judge read-only
preserved; drift clean + Claude/Codex byte-unchanged). Faithful to jig's intent;
the surgical-edit approach (remap only `tools:`, pass name/description/body
through) is correct + safe for servo's two agents.

Two low-severity latent findings (neither affects shipped output — servo's 2
agents are block-form, model-less, special-char-free):
1. **[hardened post-review]** The `tools:` block reader/writer only handled the
   block-list form; an inline `tools: [..]` in a *future* agent would pass through
   unmapped without raising — contradicting the module's "no silent pass"
   contract. **Fixed:** `_render_copilot_agent` now raises when a `tools:` key
   exists but the block reader yields nothing (inline/flow form), with a new
   mutation-verified test `test_render_copilot_agent_rejects_inline_tools_list`.
   The stated guarantee is now true, not aspirational.
2. Surgical pass-through keeps `description:` unquoted byte-for-byte vs jig's
   `json.dumps`-quoted; semantically (not byte-) equivalent for servo's two
   descriptions. Latent for a hypothetical future special-char description;
   recorded as a known limitation scoped to the current agent set.

`validate_copilot_package` intentionally left skills-only (agent static validation
a later concern). Safe to mark 028-03 REVIEWED → DONE.
