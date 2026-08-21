---
status: Proposed
dependencies: []
last_verified: 2026-08-21
frame_review: true
---

# ADR-0032: Pluggable capture providers for design-eval (platform-agnostic app capture)

## Status

Proposed (2026-08-21) — awaiting owner acceptance and a passing frame-critique.
Revised three times on 2026-08-21 after three frame-critique needs-changes rounds:
(1) state-seeding and frame-normalization promoted to co-load-bearing parts of
the provider contract; (2) the "portable neutral state directive + mechanical
migration + guaranteed matched cross-stack comparison" claim **retracted** as
unfounded — seeding is per-platform, only references/rubric/judge are shared, and
semantic state divergence is named as a residual risk env_error does not catch;
(3) corrected a factual error — the web *app* screenshot is not app-side cropped
(it is content-only for free via frozen viewport + headless-no-chrome), so native
chrome-cropping is new from-scratch work, not a generalization of a web crop;
(4) resolved a §4/§6 inconsistency (`threshold`/`δ` are **per-stack**, not shared
across stacks) and named **substrate-rendering divergence** as a second residual
risk alongside state divergence.

## Context

`/servo:design-eval` ([ADR-0009](adr-0009-design-fidelity-eval-recipe.md), spec
012) can only score a **web** UI. The naive reading is "only the screenshot is
web-specific," but that is wrong, and getting it right is the whole point of this
ADR. Scoring one screen depends on **three** things per screen — reach the
state, take the picture, frame it to match the reference. In today's app-capture
path the first two are web-coupled; the third is *free on web but a real
requirement on native*:

1. **Drive the app into the screen's state.** Each screen's `setup` is a
   content-hashed JavaScript ES module with the contract
   `export default(page, config)`, run against a live Playwright `Page`
   (`capture.mjs:82-86`). It is **frozen into the definition** —
   `_CASE_FILE_FIELDS = ("reference", "setup")` (`score.py:41`).
2. **Take the screenshot.** `capture.mjs:11` is a hard top-level
   `import { chromium } from 'playwright'`; `score.py::capture_app`
   (`score.py:161`) spawns `node capture.mjs …` as its only capture path.
3. **Frame it to match the reference — but note where the crop actually is.** The
   crop (`boundingBox` + `computeClip`, `capture.mjs:44-53`) runs **only in the
   reference-authoring branch** (`--refs`), producing the frozen mockup. The
   *app* screenshot (`capture.mjs` `--screen` branch, line ~93) is a plain
   **uncropped** `page.screenshot({ path: out })`, returned straight by
   `capture_app`. It is content-only *for free*, because headless Chrome renders
   **no OS chrome** and the `viewport` is frozen (`score.py:44`). So there is **no
   app-side crop step to generalize**.

Everything *downstream* — the vision judge, the n-sample lower bound, the sha256
freeze, the weighted composite — only ever touches **two PNGs** (app + reference),
so that half is genuinely platform-blind. But a provider that only produces
pixels leaves step 1 web-locked and step 3 unmet on native: a native
`adb exec-out screencap` has **no Playwright `page`** to run the frozen `setup`
against, and — unlike headless Chrome — returns **real device chrome** (status +
navigation bars) against a chrome-cropped reference. The app would be photographed
in the **wrong state and wrong frame**, and the judge would score that as low
fidelity — a silent garbage score, not an honest `env_error`. Native chrome-
cropping is a **new, from-scratch problem** (remove variable status/nav bars from
an opaque bitmap with no DOM or selector), not a reuse of a web app-side crop that
does not exist.

The cost of leaving this web-locked is concrete: any UI built on a non-web stack
— native Android (Jetpack Compose), iOS/SwiftUI, Flutter, React Native, desktop,
a game plugin — cannot be scored at all, even when the judge, rubric, and
references are identical. Motivating case: a product's web build scored fine
against its references, but the *same* product's native Android rebuild against
the *same* references was structurally impossible.

**What is genuinely hard here (and what this ADR does not pretend to solve).**
Step 1's `setup` is arbitrary imperative JavaScript against a live `Page` —
`page.evaluate`, `localStorage`/IndexedDB seeding, `page.route` network mocks,
click-throughs. It is Turing-complete code, not declarative data, so it **cannot
be mechanically reduced to a portable "what state, as data" directive** that a
native driver could replay. Any directive expressive enough to capture what real
setups do is itself code again; any directive simple enough to be portable cannot
express them. Therefore this ADR does **not** claim a portable neutral seed, does
**not** claim a mechanical migration of existing web setups, and does **not**
promise a guaranteed identical before/after across stacks. It claims only what
the seam actually delivers (below), and names the state-equivalence problem as a
project responsibility and a residual risk.

Three recent decisions shape where and how this lands:

- **[ADR-0031](adr-0031-design-eval-browser-acquisition.md)** settled that the
  capture *transport* is **environmental, not frozen** — browser identity is
  recorded in `ledger.jsonl` (advisory, never hashed, never a staleness trigger),
  because a live-probing freeze would fail-closed on every Chrome/CI patch bump.
  It *designed* a `capture.transport` config field + a
  `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT` env override (mirroring the existing
  `SERVO_DESIGN_EVAL_CLAUDE_BIN` escape hatch), **but that slice (spec 026-02) is
  DEFERRED and the field was never built** — only preflight (026-01) and ledger
  identity (026-03) shipped. The selector seam is on the books, not in the code.
- **[ADR-0024](adr-0024-extract-frozen-eval-harness.md)** kept capture **forked
  per eval-kind** (design-eval and content-fidelity are sibling skills, not one
  `--kind` flag).
- **[ADR-0026](adr-0026-generic-eval-authoring-surface.md)** made *eval authoring*
  kind-agnostic but scoped to **text-judged** evals, leaving vision/design-eval a
  preset and deferring the vision modality.

Together these place this decision **here** — a design-eval-scoped ADR extending
0031 — not in the generic eval-authoring surface, and not as a `--kind` flag.

Scope note: references are digital screenshots or digital mockups; no real-world
photographs. This ADR covers **only capture for targets servo can drive**. The
**human-supplied / manual** path for non-automatable targets (GitHub #29 — also a
loop-cadence change, and it overturns spike-findings' "no manual screenshots"
assumption) and **behavioural fidelity** against interactive references (GitHub
#23) are separate decisions built on this seam.

## Decision

Make **capture a pluggable provider** that owns all three web-coupled steps, keep
the mechanism environmental, and keep seeding **per-platform** — sharing only what
can honestly be shared.

1. **The provider contract widens to cover state, pixels, and frame.** A provider
   is invoked **per screen** and is responsible for: driving the app into that
   screen's defined state, taking the screenshot, and returning a **PNG
   normalized to the reference's logical frame** (device chrome cropped). A
   provider *failure* fails **closed to `env_error` (rc 2)** — never a silent
   `0.0`. (This replaces the old, too-narrow "just produce a PNG" contract.) Note
   the honest boundary: `env_error` catches provider **failure**, not **state
   inequivalence** — see §4 and Consequences.

2. **Provider selected by `capture.transport` — reviving spec 026-02's designed
   field.** Declared in `config.json`; a `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT`
   env var overrides it. **Absent → the existing Playwright web path**, so every
   current web project keeps working.

3. **Blessed providers plus an escape hatch.** Ship blessed providers for the
   common stacks — **web** (Playwright, default), **Android** (`adb … screencap`
   + a driver), **iOS** (`simctl … screenshot` + a driver) — *and* accept an
   arbitrary **project-supplied command** for anything else.

4. **Seeding is per-platform and provider-owned; only references/rubric/judge are
   shared.** There is **no** portable neutral seed. Each provider owns *how* it
   drives the app into a screen's state (today's Playwright `setup` module for
   web; a tap-flow / deep link / `adb` sequence for native), and each platform's
   seed is frozen **within its own eval definition**, not shared across stacks.
   What a cross-stack comparison genuinely shares is the **reference PNGs, the
   rubric, and the judge model** — **not** the seed, and **not** the per-stack
   `threshold`/`δ`, which are calibrated within each stack's own frozen definition
   (§6). Two residual risks follow, both **named, not eliminated**:
   - **State divergence.** Whether the web state and the native state are actually
     equivalent is the project's responsibility, authored per platform and *not*
     certified by the framework. A subtly divergent native state yields a
     real-looking low-fidelity score that `env_error` does **not** catch — the
     vision judge catches a *wrong* screen, not a *subtly wrong* one (different
     default ordering, a different nav landing).
   - **Substrate-rendering divergence.** A native screenshot and a web-rendered
     reference differ in font rasterization, anti-aliasing, system fonts, DPI, and
     color even at the same frame — the reference-vs-app engine mix ADR-0031
     already calls *structural, not a knob*. This is precisely why `threshold`/`δ`
     are **per-stack** (each stack calibrates its own pass bar for its own
     substrate, so a web-tuned bar is never forced onto native), and why a project
     may supply a **native-substrate reference** instead of a web-rendered mockup
     (§5 decouples reference from app). The vision judge + rubric + lower-bound
     tolerate non-pixel-exact rendering by design (ADR-0009), but substrate drift
     is a real residual, not certified away.

5. **Frame-normalization is a per-provider output contract — a no-op for web, new
   work for native.** The provider must return pixels matching the reference's
   logical frame. For **web** this is already satisfied *for free* (frozen
   viewport + headless-Chrome-renders-no-OS-chrome); there is no app-side crop
   today and none is added. For **native** providers it is a genuine new
   requirement: crop the status/navigation bars from an opaque bitmap (no DOM, no
   selector) to the reference's frame. Reference-authoring cropping is unchanged.
   The point: framing becomes an explicit provider output contract — trivially met
   on web, from-scratch on native — not a generalization of an app-side web crop
   that does not exist.

6. **Transport, driver, and provider identity stay environmental (extends
   ADR-0031).** The chosen provider, its driver, and resolved tool identities go
   to `ledger.jsonl` only — advisory, never part of `definition_hash`, never a
   staleness trigger. The frozen definition — judge model + decoding, rubric,
   `n`/`k`/`δ`/threshold, viewport, screen set, **reference PNG bytes**, and the
   platform's own frozen **seed** — is the hashed contract *within a stack*.

7. **No agent at score time.** Score-time capture runs with no MCP/browser
   connector present (CI, Routines, `--background`, Stop-hook), per ADR-0031.
   Providers are plain subprocesses; this ADR adds no interactive/agent
   dependency in the scoring path.

## Consequences

**Positive**
- design-eval can score **whatever stack the UI was built on** — against its
  references (a shared web mockup, or a native-substrate reference per §4/§5) with
  the same rubric and judge model. Independent per-stack scoring is the core
  value, unblocking projects that cannot be scored at all today; a matched
  cross-stack pair is a contingent add-on (Kill criteria).
- Revives the deferred spec 026-02 transport field with a concrete purpose.

**Negative**
- The provider contract is larger than "grab pixels": every non-web provider must
  supply a state driver and a chrome-crop step, or degrade honestly to
  `env_error`. This is real per-stack authoring work.
- **Neither state equivalence nor rendering equivalence is machine-checked**
  (Decision §4). Cross-stack comparison is *enabled* but only as trustworthy as
  (a) the per-platform seeds the project authors and (b) the rendering-substrate
  gap between a native screenshot and a web-rendered reference; both can score a
  plausible-but-wrong number that `env_error`/fail-closed does not catch. The
  framework shares references/rubric/judge, and calibrates `threshold`/`δ`
  per-stack — it does not certify state or substrate equivalence. Mitigation is
  the project's job (author equivalent seeds; supply a native-substrate reference;
  eyeball the captured shots — see the shot-retention work in #29's
  shared-plumbing).
- No mechanical migration of existing web setups: they stay as the web driver's
  own code. There is no portable-seed rewrite to perform, but also no free
  cross-stack reuse of them.

**Neutral**
- The ledger gains provider/driver fields; `definition_hash` composition and the
  0/1/2 composite contract are unchanged; the web default behaviour is preserved.
- Sets up the manual/human provider (#29) as the next provider family under this
  seam, and a future interaction script (#23) to drive native + web through their
  providers.

## Alternatives considered

- **Abstract only pixel acquisition (the first draft of this ADR).** Rejected by
  frame-critique #1: it leaves state-seeding (a frozen Playwright JS module) and
  chrome-cropping web-locked, so a native provider silently scores an unseeded,
  unframed screenshot. The seam must own all three steps.
- **A portable neutral state directive, frozen and shared across stacks, with a
  mechanical migration of existing setups (the second draft of this ADR).**
  Rejected by frame-critique #2: today's `setup` is Turing-complete imperative JS,
  so a portable directive is either code-again or too weak to express real setups,
  and no mechanical migration exists. It also relocated the silent-garbage risk
  to undetectable state divergence while *asserting* a matched comparison as
  delivered. Adopted instead: per-platform seeds, shared references/rubric/judge,
  divergence named as a residual risk.
- **Keep capture web-only (status quo).** Rejected: excludes every non-web stack;
  contradicts servo's own stack-blind split.
- **Freeze the provider/driver into the hash.** Rejected: ADR-0031 settled
  capture mechanism as environmental; hashing it reintroduces the
  fail-closed-on-Chrome-bump halt.
- **Fork the scorer per platform.** Rejected: only capture (the three steps) is
  platform-specific; ADR-0024 already draws the fork line at capture.
- **Put this in the generic eval-authoring surface (ADR-0026).** Rejected: 0026
  scoped that to text judges and deferred the vision modality.
- **Registry-only or command-only.** Rejected both: registry-only boxes out
  unanticipated stacks; command-only makes web/Android/iOS needless boilerplate.
- **Fold the manual/human path and behavioural fidelity in here.** Deferred: each
  is its own decision (cadence change; a different axis).

## Assumptions

- A provider can drive the app into a defined per-screen state and return a
  normalized screenshot reproducible to the same bar as today's web capture —
  *within* one platform. Equivalence of that state *across* platforms is authored,
  not assumed (see Decision §4).
- The app runs where the provider runs. The **non-automatable** case (app can't
  run where servo runs — a Mac host building a Windows-only product, a
  Windows-only 3D game plugin) is **out of scope here** and is the manual/human
  path (#29).

## Open questions

1. **Cross-provider framing contract.** How is "the reference's logical frame"
   specified so each provider crops to it (declared content rect vs. per-provider
   auto-detect of the app viewport)? Core design work of the follow-on spec.
2. **Provider/driver identity granularity in the ledger** (name+version vs.
   command string), extending ADR-0031's browser-identity approach.
3. **Optional state-equivalence aid (deferred, not blocking).** Whether the
   follow-on spec offers any *aid* to authoring equivalent per-platform seeds
   (e.g. surfacing both platforms' captured shots side-by-side for human review)
   — an ergonomic aid, explicitly not a machine guarantee of equivalence.

## Kill criteria

- If, for the first native adopter, no per-platform seed can be authored that a
  human accepts as equivalent to the web seed for the screens that matter, the
  **cross-stack before/after comparison** use is dropped for that project — the
  provider still scores each stack against the references independently (the core
  value), but the two are not presented as a matched pair. The comparison is a
  contingent benefit, never forced.

## References

- **[ADR-0009](adr-0009-design-fidelity-eval-recipe.md)** — the web-only recipe
  generalized; extended, not superseded (web is its default provider).
- **[ADR-0031](adr-0031-design-eval-browser-acquisition.md)** — capture mechanism
  is environmental → ledger, never hashed; the designed-but-unbuilt
  `capture.transport` field (spec 026-02) this ADR revives, now widened to seeding
  and framing.
- **[ADR-0024](adr-0024-extract-frozen-eval-harness.md)** — capture stays forked
  per eval-kind; the fork line respected.
- **[ADR-0026](adr-0026-generic-eval-authoring-surface.md)** — generic surface
  scoped to text judges; why this is design-eval-scoped.
- **[ADR-0005](adr-0005-eval-oracle-component.md)** — frozen-eval + honesty
  contract preserved.
- **spec 012 / spec 026** — design-eval and browser-acquisition specs (026-02
  deferred).
- **GitHub #22** — the proposal recorded here; **#29** (manual/human capture) and
  **#23** (behavioural fidelity) are follow-ons on this seam.
