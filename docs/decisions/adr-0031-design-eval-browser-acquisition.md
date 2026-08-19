---
status: Proposed
dependencies: []
last_verified:
frame_review: true
---

# ADR-0031: design-eval browser acquisition — detect-and-ask capture transport, freeze browser identity

## Status

Proposed (2026-08-19)

## Context

`/servo:design-eval` ([ADR-0009](adr-0009-design-fidelity-eval-recipe.md), spec
012) scores UI fidelity by screenshotting the running app and comparing it to a
frozen mockup reference. Both screenshots come from `capture.mjs`, which drives
a real headless Chrome via Playwright: `import { chromium } from 'playwright'`
(a hard import at module load). servo itself ships no browser and no Node
dependency — the [ADR-0020](adr-0020-python-39-floor.md) "dependency-light"
stance — so the browser is the adopter's responsibility.

**Today there is no acquisition mechanism.** The only thing servo provides is a
sentence in `SKILL.md`'s Prerequisites — *"Playwright is a project
devDependency; `npx playwright install chromium` once"* — that a human is
expected to act on. If they haven't, the bare `import` throws and surfaces as an
`env_error` at score time (`score.py`: `node/playwright unavailable for
capture`). servo detects nothing, asks nothing, and installs nothing. This is
the reported gap: adopters hit a wall with no guidance beyond prose.

Two forces pull against each other:

- **Footprint / packaging.** A full `npx playwright install chromium` pulls
  ~150–300 MB per browser. That is a real adoption barrier, and it is the
  concern that motivated this ADR. (Note: the bytes land in the *adopter's*
  machine-global Playwright cache, shared across projects — **not** in servo's
  plugin, which is 260 KB of text and references no browser binary. The plugin
  packaging is already clean; the burden is entirely downstream.)
- **Reproducibility.** A fidelity *score* is only comparable across runs if the
  rendering engine is stable. The frozen definition
  ([ADR-0005](adr-0005-eval-oracle-component.md), `definition_hash`) pins the
  judge, samples, threshold, viewport, and screen set — but **not the browser
  version**, and the ledger does not record it either. So two machines running
  the same frozen eval on different Chrome versions produce different
  screenshots, that difference lands in the score as noise, and **nothing
  refuses as stale**. That is precisely the failure mode the freeze contract
  exists to prevent, and it is latent in the current design regardless of this
  ADR.

A natural first instinct — "defer to the Claude/Codex browser connector" —
resolves cleanly against the architecture and is worth recording as a rejected
option: it works for *authoring-time* capture (an agent is present, and the
reference PNG is in the freeze hash so the capture transport is irrelevant to
reproducibility), but **cannot** serve *scoring-time* capture. The installed
component runs as `oracle.sh → gate.py → score.py → node capture.mjs`, a plain
subprocess with no MCP channel, under Routines / CI / detached `loop.py
--background` / the `oracle-hook` Stop hook. There is no agent to borrow a
browser from at score time.

The seam that makes a per-adopter choice work anyway: `init` (the interactive
authoring entry point) can **detect** the environment and **ask** the adopter
which transport they want; the answer is written into `config.json` and
**frozen**; the unattended scoring subprocess just reads it. This mirrors the
existing `judge.transport` field (`"api"` vs `"cli"`), which `score.py` already
dispatches on from the frozen config.

## Decision Options Considered

### Option A: Status quo — bundled Playwright + Chromium, prose-only prerequisite

- **Pros:** Version is implicitly pinned by the Playwright release, so
  reproducibility is stable by construction (modulo the ledger not recording
  it). Simplest code — the current `import { chromium } from 'playwright'`.
- **Cons:** No acquisition mechanism at all — the reported gap. ~150–300 MB
  download is the adoption barrier. Browser version still absent from the
  freeze/ledger, so even here cross-version drift is silent.

### Option B: Bring-your-own system Chrome only (`channel: 'chrome'` / `-core`)

- **Pros:** No browser download; drives the Chrome the adopter already has. Much
  lighter.
- **Cons:** Uncontrolled version → the reproducibility gap goes from latent to
  live. Fails outright on a machine with no Chrome (CI images, headless
  servers). Forcing this on everyone trades one wall (download) for another (no
  Chrome present).

### Option C: `connectOverCDP` to a host-launched Chrome

- **Pros:** Zero download, zero browser-lifecycle management; dovetails with the
  connector idea (a host-launched Chrome on a debug port is drivable from a
  plain subprocess, no MCP needed).
- **Cons:** Requires a Chrome already running on a known debug port — an
  operational precondition that does not hold under unattended CI/Routines
  without extra orchestration. Version still uncontrolled (same as B).

### Option D (recommended): `init` detects, asks, and freezes the answer; browser identity is pinned into the freeze

A `capture` block in `config.json` (mirroring `judge.transport`) records the
chosen transport. `init` walks a detection ladder (node present? browser library
resolvable? system Chrome present?), then asks the adopter the footprint /
reproducibility question and records their choice. Both "reuse system Chrome"
and "install pinned Chromium" are first-class. **Regardless of choice, the
resolved browser name + version is written into the frozen definition and the
ledger**, so cross-machine/version drift refuses as stale instead of biasing the
score. With the adopter's explicit consent, `init` may run the install command
in their repo; otherwise it prints the exact command. servo still installs
nothing itself and ships no browser.

- **Pros:** Closes the acquisition gap with a real mechanism, not prose. Lets
  the adopter pick their point on the footprint/reproducibility axis instead of
  servo guessing. Closes the browser-version-not-in-freeze honesty gap as a
  required side effect. Reuses the established `judge.transport` + qa-wizard +
  scaffold-init-detection patterns. Keeps the authoring/scoring boundary intact
  (choice is frozen; scoring reads it, no MCP).
- **Cons:** More code and a new interactive branch in `init`. The "reuse system
  Chrome" path still needs the JS library installed (`playwright-core`), so
  "servo touches nothing" is never fully true once a browser is required.
  Running an installer in the adopter's repo is a side-effectful, consent-gated
  action. Adds a `capture` config surface that must itself be frozen and
  validated.

## Recommended Decision

Adopt **Option D**: a **detect → ask → freeze-the-answer** mechanism in
design-eval's `init`, with both "reuse system Chrome" and "pinned Chromium" as
first-class transports, and the **resolved browser name + version pinned into
the frozen definition and recorded in the ledger**.

Rationale: the footprint concern and the reproducibility gap are dual — bring
your own browser and you must pin its identity, or scores stop being comparable;
the same change that removes the mandatory 150 MB download is what forces the
freeze to become honest about the engine. Making the adopter choose (rather than
servo defaulting) is the only way to serve both a laptop that already has Chrome
and a reproducibility-critical CI that wants a pinned build. The choice must be
frozen because the scoring path is unattended and cannot re-ask.

Defaults and boundaries this ADR fixes (leaving implementation to a spec):

- The transport choice lives in a frozen `config.json` `capture` block, mirroring
  `judge.transport`; `score.py`/`capture.mjs` dispatch on it. It is covered by
  `definition_hash` so editing it re-freezes.
- Browser identity (engine name + resolved version) is added to the frozen
  definition **and** the ledger. This is load-bearing and applies even to the
  bundled path.
- `init` may run an installer **only** with the adopter's explicit consent, in
  the adopter's repo; absent consent it prints the exact command. servo ships no
  browser and installs nothing of its own — [ADR-0020](adr-0020-python-39-floor.md)
  stance preserved.
- The host browser connector is **explicitly out of scope for scoring-time
  capture** and MAY be used only for authoring-time reference rendering, where
  the reference PNG's presence in the freeze hash makes the transport
  irrelevant. This ADR does not require building the connector path.
- `capture_app`'s runtime contract is unchanged: it stays a subprocess that
  fails closed to `env_error` (rc 2), never a silent `0.0`.

## Consequences

**Becomes easier:**
- Adopting design-eval without a mandatory ~150 MB download — reuse an existing
  Chrome.
- Trusting a fidelity score across machines/CI — browser drift now refuses as
  stale instead of silently biasing the number.
- Onboarding: `init` gives a precise, environment-aware instruction (or a
  consented install) instead of a static prose prerequisite.

**Becomes harder:**
- design-eval's `init` grows an interactive detection/ask branch and a new
  consent-gated side effect (running an installer).
- The `config.json` schema and its freeze/validation grow a `capture` block plus
  a browser-identity field; existing frozen configs predate it and need a
  migration/back-compat story (a missing block ⇒ assume bundled + record whatever
  version is resolved, or refuse as stale — to be settled in the spec).
- "servo depends on nothing" is now "servo depends on nothing it ships, but
  design-eval's runtime requires a JS browser library the adopter provides" —
  a nuance the docs must state plainly.

## Assumptions

- **`capture.mjs` hard-imports Playwright and there is no preflight today.**
  Verified by read: `skills/design-eval/capture.mjs:11`
  (`import { chromium } from 'playwright'`) and the sole handling at
  `skills/design-eval/score.py:106` (`node/playwright unavailable for capture`).
  No detection/install code exists (`grep` for `which`/`playwright`/`puppeteer`
  in the skill returns only this error string and the `claude` CLI resolver).
- **Browser version is not in the freeze or the ledger.** Verified: the
  `definition_hash` definition dict (`skills/_common/fidelity_eval.py`) contains
  judge / samples / threshold / viewport / screens only; no engine field. No
  `browser_version`/engine token appears anywhere in the skill.
- **The scoring path is a channel-less subprocess.** The installed component is
  `python3 .servo/design-eval/score.py "$PWD"` spliced into `oracle.sh`; it runs
  under `gate.py`, Routines, `oracle-hook`, and detached `loop.py` — none of
  which expose an MCP/agent channel. This is why the connector cannot serve
  scoring-time capture.
- **`config`-driven transport dispatch is an established pattern.** `score.py`
  already reads `judge.transport` (`"api"`/`"cli"`) from the frozen config
  (`skills/design-eval/score.py:119-124`); a `capture` block follows the same
  shape.
- **Assumed, not yet verified (flag for the spike/spec):** that Playwright's
  `channel: 'chrome'` reliably drives a system Chrome across the OS/versions
  servo's adopters run, and that a resolvable, trustworthy browser *version*
  string is cheaply obtainable for the ledger on the BYO path. These are
  library/OS-capability claims that a spec-time probe should confirm before
  committing to the BYO default.

## Kill criteria

- If a spike shows `channel: 'chrome'` / `-core` cannot reliably drive a system
  Chrome across servo's target environments, the BYO transport is not viable and
  the decision collapses toward Option A (bundled) — in which case the *only*
  surviving change is recording browser identity in the freeze/ledger.
- If a resolvable, trustworthy browser version cannot be obtained on the BYO
  path, the reproducibility guarantee is unenforceable and BYO must not be a
  default.
- If the adopter-facing `init` interaction proves to add more friction than the
  prose prerequisite it replaces (e.g. adopters routinely decline and are left
  worse off), prefer detect-and-instruct over detect-and-install.

## Open questions

- **Back-compat for existing frozen configs** without a `capture` block: assume
  bundled and back-fill the version, or refuse as stale on first run after
  upgrade? (Leaning: treat a missing block as "bundled, unpinned" and warn, so
  no silent behaviour change; settle in the spec.)
- **Which browser identity to pin** — engine name + full version string, or a
  coarser channel+major? Finer is more correct but flaps more; coarser is
  stabler but lets patch-level rasterization drift through.
- **Authoring vs scoring transport independence** — may an adopter render
  references with the connector but score with pinned Chromium, and if so does
  mixing engines across the two screenshots itself bias fidelity? (Likely yes —
  same-engine on both sides matters — which may argue for freezing *one* browser
  identity used for both.)
- **Puppeteer as an alternative library** — near-equivalent to Playwright here;
  worth a line in the spec on whether to support both or standardize on one.
