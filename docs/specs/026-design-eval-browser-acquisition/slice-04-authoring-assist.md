---
status: ABANDONED
dependencies: [026-02, adr-0031]
last_verified:
frame_review: true
---

## Slice 026-04 — authoring-assist

**Abandonment reason:** two independent re-scopes could not find a version of
this slice with positive net value, and the second made it worse. The frame
-critique gate killed it before implementation, which is what the gate is for.

- **v1 (detect → ask → consented install).** Falsified: "run the install command"
  is not one knowable act. It conflates the **library** (mutates the adopter's
  `package.json` + lockfile, because `capture.mjs`'s bare import resolves upward
  into `<target>/node_modules`) with the **browser binary** (a machine-global
  cache touching no repo file). servo has **zero** package-manager detection
  (enumerated over `skills/` + `scripts/`; `scaffold.py` reads `package.json`
  only to detect a test runner), so an implementation hardcodes npm and drops a
  `package-lock.json` beside a pnpm/yarn/bun lockfile, breaking the adopter's CI
  far from servo. Nothing requires a design-eval target to be a Node project at
  all. Consent cannot bound this: what is asked is "install a browser", not
  "adopt npm as this repo's package manager".
- **v2 (detect → recommend → write `capture.transport` → print command).**
  Falsified in turn: the re-scope traded a *machine-local* act for a
  *cross-machine* one. `config.json` lives in `<target>/.servo/design-eval/`,
  carries `approved_content_hash`, and must travel with the repo for CI to
  validate the freeze — so a laptop's answer becomes every later machine's
  commitment. An author on a Mac with Chrome gets `system-chrome` written and
  committed; CI, a headless container with pinned Chromium but no Chrome, then
  takes `env_error` on a run that **passed before the assist ran**. In other
  words 026-04's output manufactures the failure 026-01 exists to explain —
  negative value against this spec's own primary mechanism. "Unfrozen" buys only
  *no `StaleError`*; it says nothing about cross-machine effect. ADR-0031 already
  named this shape in its Open Questions (the `judge.transport` laptop-answers-
  for-CI wart).
- **Residual value, and where it went.** Strip the write and what remains is a
  recommendation the author can act on from 026-01's runtime message plus one
  line of JSON in a file they are already hand-authoring (`SKILL.md` Flow step 2).
  That is **folded into 026-01** (its guidance message names the transport
  options and the env override) and **026-02** (its `SKILL.md` update documents
  choosing a transport and states the BYO drift trade plainly). Both are already
  required by those slices' DoDs, so nothing is lost by abandoning this slice.
- **Also unsound independently:** the recommendation rule "BYO when Chrome
  exists" hard-codes the hoped-for outcome of A1, still unprobed; and presence of
  a Chrome binary is not the predicate that matters (Playwright being able to
  *launch* it is). It would have steered nearly every developer laptop onto the
  less reproducible path by default, silently, since Chrome is near-universal.

_Abandoned pre-implementation. Re-open via DRAFT only if a concrete adopter need
appears that 026-01's guidance and 026-02's docs demonstrably do not serve._
