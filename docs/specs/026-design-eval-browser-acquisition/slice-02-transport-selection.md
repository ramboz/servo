---
status: DEFERRED
dependencies: [026-01, adr-0031]
last_verified:
arch_review: true
frame_review: true
---

## Slice 026-02 — transport-selection

**Resolution trigger:** Resume when the **A1 probe can be run on a
Playwright-equipped machine** and answers the package question below. This slice
is blocked on missing evidence, not on wording — five frame-critique rounds
sharpened it until the remaining gap was factual.

**Why deferred (frame-critique round 5, structural).** The slice specifies the
transport *value's* plumbing exhaustively — resolver, `allow_env` mode, argv,
fail-closed-if-absent, never-re-derive — but cannot state what `capture.mjs`
actually **launches** per transport without resolving a fork it has no evidence
for:

- `capture.mjs:11` is a **static, top-level** `import { chromium } from
  'playwright'`. It executes before any argv parsing, so it cannot be made
  transport-conditional without restructuring the file into a resolved
  `await import(...)` — which also interacts with the module-level
  `await chromium.launch()` and with 026-03's attestation emission.
- **Horn A — keep importing `playwright`:** `channel: 'chrome'` would work, every
  test would pass, and the adopter **still pays the ~150–300 MB**, because the
  browsers land at install time regardless of channel. The slice would ship, its
  verticality claim would be technically satisfied, and ADR-0031's motivating
  concern would be untouched. A false success.
- **Horn B — switch to `playwright-core`:** the footprint saving becomes real,
  but `transport: "bundled"` then has no browser unless the adopter separately
  installs one — breaking this slice's own probe-verified "back-compat preserves
  behavior exactly", and breaking it *silently*, since `init()` overwrites the
  target's `capture.mjs` unconditionally and `install()` calls `init()`.

**What was probed, and what it could not settle.** `playwright` (5 MB unpacked)
depends on `playwright-core` (13 MB unpacked), confirming they are distinct
packages with distinct install behavior. But npm metadata does not expose the
install-time browser-download step, so the decisive question — *can
`playwright-core` + a system Chrome actually drive a capture, and does choosing
it genuinely avoid the download?* — is unanswerable without installing
Playwright, which this repo deliberately does not do.

**Disposition.** This is exactly [ADR-0031](../../decisions/adr-0031-design-eval-browser-acquisition.md)
kill criterion 1 ("if a spike shows `channel:'chrome'` / `-core` cannot reliably
drive a system Chrome … the BYO transport is not viable"), and this slice's own
fallback says to ship nothing rather than a one-valued enum. Deferring rather
than abandoning: the question is answerable, just not here.

**What survives without it** (so the spec still delivers): 026-01's runtime
preflight — ADR-0031's *primary* mechanism — is independent and unblocked, and
026-03 degrades cleanly to attesting the engine with a constant `bundled`
transport, as its own DoR already states.

_Deferred pre-implementation. Re-open via DRAFT once A1 is probed._

<!-- The full AC set from rounds 1-5 is preserved in git history (commits
     906a4f2, a9ce3b5, 9bdfc41, e6332cc) rather than carried here, so a reader
     is not misled into building against ACs whose central fork is unresolved. -->
