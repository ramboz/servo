---
status: DRAFT
dependencies: [026-02, adr-0031]
last_verified:
frame_review: true
---

## Slice 026-04 — authoring-assist

**Goal:** Give an author a guided way to choose and record a capture transport:
detect what's on the machine, recommend a transport, write it to the `capture`
block, and print the exact acquisition command. **It installs nothing.**

**DoR:**
- ✅ 026-02 supplies the `capture` field and the resolver this writes into.
- ✅ **`install()` calls `init()` unconditionally** (`design_eval.py:148`), so the
  ask must live on a separate opt-in surface or scripted installs block on stdin.
- ✅ **Re-scoped after frame-critique: the installer is removed.** "Run the
  install command in their repo" is not one knowable act. It conflates two with
  different blast radii — the **library** (`playwright`/`playwright-core`, which
  mutates `package.json` + a lockfile in the adopter's tree, because
  `capture.mjs`'s bare import resolves upward into `<target>/node_modules`) and
  the **browser binary** (`npx playwright install`, a machine-global cache
  touching no repo file). Verified: servo has **zero** package-manager detection
  anywhere in `skills/`/`scripts/` (`scaffold.py` reads `package.json` only to
  detect a test runner), so an implementation would hardcode npm and drop a
  `package-lock.json` beside a pnpm/yarn/bun lockfile, breaking the adopter's CI
  far from servo. And nothing requires a design-eval target to be a Node project
  at all (the only precondition is `oracle.sh` + `.servo/install.json`), so on a
  Python repo it would materialize a `package.json` from nowhere. Consent does
  not bound this: the consent asked is "install a browser", not "adopt npm as
  this repo's package manager". ADR-0031 says `init` **may** run an installer —
  permission, not requirement — so declining that permission is within the ADR.
- ✅ **Safety rests on AC1+AC2, not on stdin detection.** A distinct opt-in verb
  outside `install()`→`init()` cannot be reached by a scripted install regardless
  of what stdin looks like. `isatty` answers "is this a terminal", not "is a human
  here to consent" — it is wrong in both directions (pty-allocating automation;
  a human piping input). It is therefore a **secondary guard**, not the claim.

**Acceptance criteria:**
1. A distinct opt-in surface (its own verb / explicit flag) runs
   detect → recommend → write `capture.transport` → print the exact command.
2. **`init` and `install` remain non-interactive** — a test asserts `install()`
   never prompts and never blocks on stdin. This is the regression this slice
   exists to prevent.
3. **Nothing is installed and no dependency manifest is written.** The assist
   prints the command for the recommended transport and exits; acquisition stays
   the adopter's action. servo continues to install nothing of its own.
4. Detection reports what is actually present (node, library resolvable, system
   Chrome) and recommends accordingly — recommending BYO when Chrome exists, and
   pinned otherwise.
5. On a non-interactive stdin the assist degrades to print-only (secondary
   guard) rather than hanging or assuming an answer.
6. The written choice needs no re-freeze (the field is unfrozen, per 026-02).
7. Tests: recommend-BYO, recommend-pinned, non-interactive degrade, the
   `install()`-stays-silent guard, and that **no package manager is invoked**.

**DoD:**
- [ ] Opt-in surface implemented outside the `install()` → `init()` path.
- [ ] Guard test: `install()` is non-interactive.
- [ ] Guard test: the assist spawns no package manager (the re-scope's teeth).
- [ ] Detection/recommendation paths tested.
- [ ] `SKILL.md` documents the assist as optional, naming 026-01's runtime
      guidance as the mechanism that actually closes the gap.
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Vertical?** Yes — an author gets a recommendation grounded in their actual
machine and a recorded, correct transport, without servo mutating their repo.
