---
slice: 028-06 — committed-package-and-release
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-09-18T20:55:27Z
prompt_source: review.py (compliance+craft+arch pass)
---

Independent review (compliance + craft + arch) of slice 028-06 by a fresh
jig:reviewer. **VERDICT: PASS.** All 5 ACs met; release parity correct and the
copilot artifact cannot ship mislabeled (version-coherence exit-2 + drift guard +
release-please lockstep + a static lockstep test — belt-and-suspenders). Claude/
Codex non-regressive: `build_release_zip.py` intercepts copilot ahead of the
unchanged claude/codex build/smoke paths, and release.yml's dedicated claude/codex
build+smoke+alias steps are untouched (only shared upload/notes steps gained
additive copilot lines; claude/codex content within them unchanged). Docs accurate
across README + architecture.md + CONTRIBUTING. Real artifact builds + smoke-passes.

Two low findings, disposition:
1. **[hardened post-review]** `validate_copilot_package` (the release smoke)
   checked that the manifest *declares* an `agents` path but did not verify agent
   files exist — so AC2's "agents present" was covered only transitively (build
   test + drift guard), not by the smoke itself. **Fixed:** the smoke now verifies
   `.github/agents/*.agent.md` are present + loader-safe (name `:`-free, no
   `model:`), with two new mutation-verified tests
   (`test_validate_copilot_package_flags_missing_agents`,
   `..._flags_agent_model_field`). The release gate is now self-sufficient across
   every declared component.
2. **[wording, corrected here]** The 028-06 deviation log said release.yml's
   claude/codex "upload and notes steps are byte-unchanged"; precisely, those two
   **shared** steps gained additive copilot lines — the claude/codex *content*
   within them and all *dedicated* claude/codex steps are unchanged. Functional
   non-regression holds (confirmed: no claude/codex `run:` step modified); the
   "byte-unchanged" phrasing applied to the dedicated steps + the claude/codex
   content, not the shared steps verbatim.

Post-hardening re-verified: validate tests green (incl. the 2 new agent guards),
real `servo-copilot-v0.9.0.zip` smoke-passes (now checking agents), drift + lint
clean. Safe to mark 028-06 REVIEWED → DONE.
