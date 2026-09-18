---
slice: 028-04 — hooks
pass: craft
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-09-18T19:36:35Z
prompt_source: review.py (compliance+craft+arch pass)
---

Independent review (compliance + craft + arch) of slice 028-04 by a fresh
jig:reviewer, cross-checked against jig's shipped adapter/schema. **VERDICT: PASS.**
All 4 ACs met with mutation-verified pinning tests; faithful to the ADR + jig,
Claude path provably non-regressive (ClaudePathUnchangedByHostFlagTests). servo's
hook-free-plugin + target-side-install divergences correctly realized (no
`.github/hooks/` in the committed Copilot package; adapter ships as a skill
resource in all three host packages; emitted `{version:1,hooks:{agentStop:[…]}}`
matches jig's shipped agentStop entries).

Two low-severity findings:
1. **[resolved]** The advisory `agentStop` adapter forwarded the child's exit
   code verbatim, whereas jig's advisory adapter always returns 0 — a thinner
   fail-open margin (safe only because meta-judge always exits 0), and in tension
   with the adapter's own "a Stop hook must never trap the session" comment.
   **Fixed post-review:** the adapter now always exits 0 (advisory posture); the
   gate decision travels solely in the child's stdout `{decision:block,reason}`
   body. Test `test_exit_code_forwarded_verbatim` replaced by
   `test_advisory_never_forwards_nonzero_child_exit` (child exits 7 → adapter 0,
   stdout decision still forwarded). AC1 wording corrected. Host packages
   regenerated; drift clean.
2. **[accepted, low-risk]** `cmd_uninstall_copilot` unlinks the whole
   `servo-oracle.json` when no hook events remain, dropping any user-added
   top-level non-hook keys. `servo-oracle.json` is servo-owned and a single
   backup is taken before mutation, so impact is negligible; recorded rather than
   changed.

Reconciliation: exit-code semantics for a live Copilot `agentStop` are unverified
headlessly (jig 113-08) — now moot since the adapter never forwards a non-zero
exit. `.github/`-presence host auto-detection was consciously dropped (unsafe
selector — most repos carry `.github/` for Actions); explicit `--host` flag only.
Safe to mark 028-04 REVIEWED → DONE.
