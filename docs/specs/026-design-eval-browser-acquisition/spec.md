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
hasn't installed it gets the opaque `env_error` "node/playwright unavailable for
capture" at score time. The only guidance is a sentence in `SKILL.md`'s
Prerequisites. servo detects nothing, asks nothing, installs nothing.

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
- **An opt-in authoring assist** that may detect-ask-and-install *with consent*,
  kept strictly out of `install()`'s code path.

**What this spec does NOT do** (ADR-0031 boundaries, load-bearing):

- It does **not** put transport or browser identity in `definition_hash`. Both
  are environmental; the freeze is self-referential (`validate_freeze` never
  probes the environment) and `definition_hash` deliberately excludes
  environmental fields. Pinning them would be inert at best and a fail-closed
  halt on every browser patch bump at worst (ADR-0031 Option E, rejected).
- It introduces **no new fail-closed mode**. Nothing added here is hashed, so an
  environment move can never raise `StaleError`. The worst case stays the
  pre-existing `env_error` (rc 2).
- It does **not** make `init` or `install` interactive. `install()` calls
  `init()` unconditionally (`design_eval.py:148`), so any interactive ask lives
  behind an explicit opt-in outside that path.
- It does **not** use the host browser connector for scoring-time capture (no
  MCP channel in the scoring subprocess).

## Assumptions

These are the unverified, load-bearing claims this spec rests on. Each is
probe-gated inside the slice that depends on it — the ADR's kill criteria turn
on the first two.

- **A1 — `channel: 'chrome'` (or `playwright-core` + `executablePath`) reliably
  drives an installed system Chrome** across the OS/versions servo's adopters
  run. If false, the bring-your-own transport is not viable and 026-02 collapses
  to bundled-only (ADR-0031 kill criterion 1). Probed inside 026-02.
- **A2 — a trustworthy browser name + version string is cheaply obtainable** on
  both transports. If false, the ledger record would be misleading and should be
  omitted rather than shipped wrong (ADR-0031 kill criterion 2). Probed inside
  026-03.
- **A3 — `node -e "require.resolve('playwright')"` is a reliable library-presence
  probe** from `score.py`. Plausible but unverified; 026-01 must confirm it
  distinguishes "node missing" from "library missing" rather than collapsing
  both to a generic non-zero exit.
- **A4 — the authoring assist can detect a non-interactive stdin and degrade to
  print-the-command** rather than blocking. Load-bearing for 026-04's safety
  claim; unverified.

Grounded (probe-verified, not assumptions): `capture.mjs` hard-imports Playwright
at module top level (`capture.mjs:11`), so it cannot preflight its own missing
dependency — the probe must live in the Python parent; `install()` calls `init()`
unconditionally (`design_eval.py:148`); `app_url` is present in
`templates/config.example.json:4` and named in `definition_hash`'s docstring as
the excluded-environmental example; `validate_freeze` compares only config-to-its-
own-hash plus on-disk artifact hashes.

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
- **I — Interface (026-04).** Split by surface: the opt-in authoring assist is a
  new CLI surface, deliberately last because it is the ADR's *demoted*,
  convenience-tier mechanism.

Every slice is vertical — each changes what an adopter or operator actually
experiences, not just an internal layer.

## Slices

- [026-01 — runtime-preflight-guidance](slice-01-runtime-preflight-guidance.md)
  — `score.py` probes node/library/browser before spawning capture and emits an
  actionable instruction instead of the opaque `node/playwright unavailable`.
- [026-02 — transport-selection](slice-02-transport-selection.md)
  — unfrozen `capture.transport` + `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT`
  override; `capture.mjs` launches per transport; back-compat for existing
  frozen configs.
- [026-03 — ledger-browser-identity](slice-03-ledger-browser-identity.md)
  — record resolved transport + browser name/version in `ledger.jsonl`.
- [026-04 — authoring-assist](slice-04-authoring-assist.md)
  — opt-in detect-ask-(consented)install surface, outside `install()`'s path.

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
