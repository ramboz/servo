---
status: DRAFT
dependencies: [026-02, adr-0031]
last_verified:
frame_review: true
---

## Slice 026-04 — authoring-assist

**Goal:** Give an author a guided setup — detect what's on the machine, ask which
transport they want, and with **explicit consent** run the install command in
their repo — without making any existing verb interactive.

**DoR:**
- ✅ 026-02 supplies the `capture` field this writes into.
- ✅ **The hazard is verified and bounds the design:** `install()` calls
  `init()` unconditionally (`design_eval.py:148`), so putting the ask in `init`
  would make `install` block on stdin in scripted/CI use. This slice therefore
  ships a **separate opt-in surface** and leaves `init`/`install`
  non-interactive.
- ✅ **This is the ADR's demoted, convenience-tier mechanism.** It runs on the
  authoring machine, which is *not* where the score-time wall is hit — 026-01 is
  what closes the reported gap. Scope accordingly; do not let this grow.
- ⚠️ **A4 unverified:** can the assist reliably detect a non-interactive stdin
  and degrade to printing the command? Its whole safety claim rests on this.

**Acceptance criteria:**
1. A new opt-in surface (a distinct verb, or an explicit `--interactive` flag)
   runs the detect → ask → optionally-install flow.
2. **`init` and `install` remain non-interactive by default** — a test asserts
   `install()` never prompts and never blocks on stdin.
3. Installation happens **only** with explicit consent, in the adopter's repo.
   Without consent the assist prints the exact command and exits cleanly. servo
   itself still ships no browser and installs nothing of its own.
4. On a non-interactive stdin the assist degrades to print-the-command rather
   than hanging or assuming consent.
5. The recorded choice is written to the `capture` block and, being unfrozen,
   requires no re-freeze.
6. Tests cover: consent given, consent declined, non-interactive stdin, and the
   `install()`-stays-silent guard.

**DoD:**
- [ ] Opt-in surface implemented outside the `install()` → `init()` path.
- [ ] Guard test: `install()` is non-interactive (the regression this slice
      exists to prevent).
- [ ] Consent, decline, and non-interactive paths all tested.
- [ ] `SKILL.md` documents the assist as optional, naming 026-01's runtime
      guidance as the mechanism that actually closes the gap.
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Vertical?** Yes — an author gets a guided path from "no browser" to a working,
frozen eval.
