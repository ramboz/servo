---
status: DRAFT
skill: design-eval
use_cases: []
---

# Spec 026: design-eval browser acquisition

> Implements [ADR-0031](../../decisions/adr-0031-design-eval-browser-acquisition.md)
> (Accepted 2026-08-19, after a 4-round adversarial frame-critique).

## Overview

`/servo:design-eval` needs a real headless browser to screenshot the app it
scores, but servo ships none ([ADR-0020](../../decisions/adr-0020-python-39-floor.md)
dependency-light stance). Today there is **no acquisition mechanism at all**:
`capture.mjs` hard-imports Playwright (`capture.mjs:11`), and an adopter who
hasn't installed it gets — as the frame-critique established by probe — not a
tidy servo message but **node's own internals**, head-truncated:
`ERR_MODULE_NOT_FOUND … package_json_reader:256`. (The tidier
"node/playwright unavailable" string fires only when the `node` *binary* is
missing.) The only guidance is a sentence in `SKILL.md`'s Prerequisites. servo
detects nothing, asks nothing, installs nothing.

This spec builds ADR-0031's composed answer:

- **A non-interactive runtime preflight** in `score.py` — the primary mechanism,
  because the wall is hit at *score time* on CI / Routines / detached loops,
  which is where a human is *not*. It turns an opaque failure into a precise,
  actionable instruction for *this* machine.
- **An unfrozen `capture.transport` config field** (+ `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT`
  env override) so an adopter can reuse an installed Chrome instead of paying a
  ~150–300 MB pinned-Chromium download — the footprint concern that motivated
  the ADR.
- **Browser identity in the ledger** so a human investigating a score shift can
  see what rendered it.
- ~~An opt-in authoring assist~~ — **ABANDONED at frame-critique** (026-04).
  Two re-scopes could not find positive net value: v1 (consented install) made
  servo a package-manager driver in the adopter's repo; v2 (write the transport
  to config) was worse, because a laptop's answer lands in the config CI reads
  and manufactures the very failure 026-01 exists to explain. Its residual value
  — recommending a transport — is folded into 026-01's guidance message and
  026-02's `SKILL.md` update.

**What this spec does NOT do** (ADR-0031 boundaries, load-bearing):

- It does **not** put transport or browser identity in `definition_hash`. Both
  are environmental; the freeze is self-referential (`validate_freeze` never
  probes the environment) and `definition_hash` deliberately excludes
  environmental fields. Pinning them would be inert at best and a fail-closed
  halt on every browser patch bump at worst (ADR-0031 Option E, rejected).
- It introduces **no new fail-closed mode on the score path**. Nothing added
  there is hashed, so an environment move can never raise `StaleError`; the worst
  case stays the pre-existing `env_error` (rc 2). **Narrowed after
  frame-critique:** `capture.mjs` is *also* the reference renderer, and reference
  PNGs *are* content-hashed — so 026-02 explicitly guards the `--refs` path
  against silently re-rendering frozen references under a different engine.
- It does **not** make `init` or `install` interactive. `install()` calls
  `init()` unconditionally (`design_eval.py:148`), so any interactive ask lives
  behind an explicit opt-in outside that path.
- It does **not** use the host browser connector for scoring-time capture (no
  MCP channel in the scoring subprocess).

## Assumptions

Four rounds of frame-critique (one per slice) resolved most of the original set
by probe. What remains genuinely unverified is listed first.

**Still unverified (probe-gated inside the slice that depends on it):**

- **A1 — `channel: 'chrome'` / `playwright-core` + `executablePath` reliably
  drives an installed system Chrome** across adopter OS/versions. Probed inside
  026-02, and **the probe must run under `playwright-core` (or with browsers not
  downloaded)** — probing under the full `playwright` package would not test the
  footprint claim, since the download happens at install time regardless of
  channel. If false, ADR-0031 kill criterion 1 fires; 026-02 states its fallback
  deliverable explicitly.
- **A5 — Playwright exposes a usable per-launch engine name + version inside
  `capture.mjs`** (`browser.version()` or equivalent). 026-03's attestation
  channel depends on it. If unavailable, 026-03 records `"unknown"` rather than
  substituting an out-of-band guess.

**Resolved by probe during frame-critique (no longer assumptions):**

- ~~A2 (version string obtainable)~~ — confirmed: system Chrome reports
  `Google Chrome 151.0.7922.138` via `--version`. The *real* question the
  critique surfaced was not availability but **provenance**, which 026-03 now
  answers with an attestation channel rather than a probe.
- ~~A3 (`require.resolve` probe)~~ — confirmed: with the library absent, `node -e
  "require.resolve('playwright')"` exits **1** with a `MODULE_NOT_FOUND` token;
  and `shutil.which("node")` distinguishes node-missing **before** node is
  invoked. Both branches are cleanly separable.
- ~~A4 (stdin detection is the safety claim)~~ — **retired as mis-ranked.**
  026-04's safety rests on the opt-in surface living outside `install()`→`init()`,
  which a scripted install cannot reach whatever stdin looks like. `isatty` is
  demoted to a secondary guard.
- **Freeze-neutrality** — confirmed by running `definition_hash` directly: adding
  or changing a top-level `capture` block leaves the hash byte-identical, while
  `threshold` still moves it. New top-level keys are excluded **by construction**.
- **Failure taxonomy** — confirmed, and it **falsified 026-01's original
  premise**: the `node/playwright unavailable` message fires **only** when the
  `node` binary is absent. A missing *library* starts node fine and returns rc 1,
  surfacing head-truncated node internals
  (`ERR_MODULE_NOT_FOUND … package_json_reader:256`). 026-01 was rewritten around
  the real taxonomy and now also fixes the truncation.
- **Back-compat** — confirmed: `capture.mjs`'s `chromium.launch()` takes no
  channel, so no existing adopter can be on system Chrome; "absent block ⇒
  bundled" preserves behavior exactly rather than guessing.
- **No package-manager awareness** — confirmed by enumeration over
  `skills/`/`scripts/`: servo has none, which is why 026-04 no longer installs.

## Decomposition

SPIDR, in the order the axes were tried. **Spike was deliberately not used**: the
`channel: 'chrome'` viability question (A1) would conclude with "now ship the
transport field," so per the anti-eager-spike rule the implementation *is* the
slice — the probe lives inside 026-02's DoR rather than in a separate research
slice.

- **P — Path (026-01).** Split the *failure* path from the *success* path. The
  reported gap lives entirely on the failure path (an adopter with no browser),
  so guidance ships first and alone. Delivers value with no config surface and no
  new transport.
- **R — Rules (026-02).** Split by the rule that selects a browser: the simple
  rule (bundled, today's behavior) is already the default, so this slice adds the
  *alternative* rule (reuse system Chrome) plus the override precedence.
- **D — Data (026-03).** Split by the data recorded per run: add resolved
  transport + browser identity to the ledger rows.
- ~~**I — Interface (026-04)**~~ — the axis was tried and the resulting slice was
  **abandoned pre-implementation** on frame-critique evidence. Recorded rather
  than deleted: the axis was legitimate, the slice was not.

Every slice is vertical — each changes what an adopter or operator actually
experiences, not just an internal layer.

## Slices

- [026-01 — runtime-preflight-guidance](slice-01-runtime-preflight-guidance.md)
  — `score.py` preflights node + library (the two cheaply detectable modes) and
  fixes the head-truncated stderr surfacing that hides the remedy for the rest.
- [026-02 — transport-selection](slice-02-transport-selection.md)
  — unfrozen `capture.transport` + `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT`
  override; `capture.mjs` launches per transport; back-compat for existing
  frozen configs.
- [026-03 — ledger-browser-identity](slice-03-ledger-browser-identity.md)
  — `capture.mjs` **attests** the engine it launched over a stdout channel;
  `score.py` records transport + attested identity in `ledger.jsonl`.
- ~~[026-04 — authoring-assist](slice-04-authoring-assist.md)~~ — **ABANDONED**
  pre-implementation; see the slice for the full reasoning and where its value went.

## Non-goals

- Pinning transport or browser identity into the frozen definition (ADR-0031
  Option E, rejected on the evidence).
- Any gate, refusal, or staleness trigger on browser drift. An advisory warning
  is in scope; a refusal requires a superseding ADR.
- Making `init` / `install` interactive.
- The host-connector capture path (authoring-time reference rendering only, and
  not required by ADR-0031).
- Same-engine enforcement between the frozen reference PNG and the live app
  screenshot. Engine mixing is structural (references are frozen bytes); 026-03
  makes it *visible*, and closing it would need its own ADR.
