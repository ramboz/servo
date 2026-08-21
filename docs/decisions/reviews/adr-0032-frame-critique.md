---
adr: 0032
pass: frame-critique
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-08-21T19:39:57Z
prompt_source: review.py frame-critique docs/decisions/adr-0032-design-eval-capture-providers.md
---

Frame-critique of ADR-0032 (pluggable capture providers for design-eval), run
pre-implementation with independent general-purpose reviewers. The frame passed
on the fifth pass after four consecutive needs-changes rounds, each of which
caught a genuine flaw and drove a revision:

1. **needs-changes** — the first draft abstracted only pixel acquisition, leaving
   state-seeding (a frozen Playwright `setup` module) and chrome-cropping
   web-locked; a native pixels-only provider would silently score an unseeded,
   unframed shot. Fix: the provider contract now owns state + pixels + frame.
2. **needs-changes** — the second draft overclaimed a portable neutral state
   directive, a mechanical migration of existing setups, and a guaranteed matched
   cross-stack comparison. `setup` is Turing-complete imperative JS, so no
   portable directive / mechanical migration exists. Fix: seeding is per-platform;
   only references/rubric/judge are shared; state divergence named as a residual
   `env_error` does not catch; kill criterion added.
3. **needs-changes** — a factual error: the ADR claimed the web *app* screenshot
   is app-side cropped. Verified in code that the crop runs only in the reference-
   authoring `--refs` branch; the app shot is an uncropped full-viewport grab,
   content-only because headless Chrome renders no OS chrome. Fix: framing
   reframed as a no-op on web and new from-scratch work on native.
4. **needs-changes** — an internal inconsistency (§4 called `threshold`/`δ`
   "shared" across stacks; §6 froze them per-stack) plus an unnamed residual
   (substrate-rendering divergence: web-rendered reference vs native screenshot
   differ in fonts/AA/DPI/color). Fix: thresholds consistently per-stack;
   substrate-rendering divergence named as a second residual, reconciled with
   ADR-0031's "reference-vs-app engine mix is structural, not a knob."

## Final verdict: PASS

The load-bearing assumption — capture (drive-state + pixels + frame) is the only
platform-coupled part, so the downstream judge / n-sample lower bound / freeze /
weighted composite are platform-blind — was verified against the code: `judge`,
`_judge_api`/`_judge_cli`, and `aggregate_lower_bound`/`score` touch only two PNG
paths, with no web-specific coupling below the capture seam. Every concrete code
claim checks out (Playwright hard-import at `capture.mjs:11`; crop only in the
`--refs` branch; uncropped app `page.screenshot` at line 89; `setup` frozen via
`_CASE_FILE_FIELDS`; `capture.transport` genuinely unbuilt — 026-02 deferred). The
ADR retracts its earlier overclaims and names state divergence and substrate-
rendering divergence as explicit residuals with a kill criterion that keeps the
core value (independent per-stack scoring) while making the matched cross-stack
pair contingent.

## Residual note (not blocking)

The "Positive" consequence originally read "against the same references" while
§4/§5 allow a native-substrate reference; tightened post-pass so the Positive
bullet matches the honest body (shared references are one option, not guaranteed;
a real cross-stack setup may share only rubric + judge).

Reviewer: independent general-purpose subagent (read-only), 5 rounds.
Prompt built via: review.py frame-critique docs/decisions/adr-0032-design-eval-capture-providers.md
