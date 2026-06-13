# Spike findings → seed for spec 012 (`/servo:design-eval`)

> Source: throwaway Playwright spike run against food-log (the first consumer)
> on 2026-06-12. Captures app screens vs `design_v1.0` claude-design mockups and
> judges fidelity. This doc is the **input** to spec 012; it is not the spec.

## What the spike validated

- **Headless rendering of claude-design `.dc.html` works.** The DC runtime
  (`support.js`) renders templates/`Component` logic in headless Chromium, so
  references can be generated programmatically (no manual screenshots).
- **The vision-judge approach is sound.** Comparing an app screenshot against a
  reference screenshot under a rubric yields a usable `[0,1]` fidelity signal
  (spike judge scored Home ~0.82, Settings ~0.90, AddSheet ~0.85; composite
  ~0.85 — first-pass UI already close).

## The five problems spec 012 must solve (the de-risking payoff)

1. **Device chrome.** Showcase mockups wrap each screen in a phone bezel (9px
   border) + an OS status bar (`16:10`, signal/wifi/battery) + a home-indicator
   pill. The real PWA renders none of these (full-bleed). → The reference must be
   **cropped to the inner content rectangle**, or the rubric must explicitly
   ignore device chrome. Cropping is more deterministic and cheaper for the
   judge — prefer it. The skill needs a per-screen crop (exclude bezel + status
   strip + home-indicator strip).

2. **Deterministic app state is mandatory.** The app is **now-dependent**
   (current time-of-day period + real timestamps) and starts empty. A screenshot
   taken at 09:00 vs 11:30 differs (Morning vs Lunch active). → Each screen needs
   a **setup step** that (a) seeds a fixed entry dataset, (b) pins the clock /
   active period, (c) navigates to the screen. Without this, the n-sample lower
   bound is meaningless because the *input* itself varies. The spike seeded
   IndexedDB directly + clicked the period tab — that pattern works.

3. **App state must match the reference's logical state.** The mockup Home is
   `Afternoon`-active with specific sample entries; an app seeded as
   `Morning`-active with different entries is an unfair comparison (different
   favorites, different timeline). → The reference and the app-under-test must be
   driven to the **same logical state**; the rubric scores "does the app render
   *this state* the way the design renders it," not "are the two screens
   identical pixel-for-pixel."

4. **Composed / multi-file screens.** The mockup AddSheet is pulled into the Home
   file via `<dc-import name="AddSheet">`; capturing the Home sub-region did NOT
   render the sheet (only the dimmed background). → A screen's reference may come
   from a **standalone component file** (`AddSheet.dc.html`), not a region of a
   showcase. The skill must let the author point at `{ file, selector }` per
   screen.

5. **Dynamic content vs design intent.** Times, dates, entry names are dynamic.
   The rubric must score **layout / spacing / palette / typography / component
   shape**, and explicitly IGNORE dynamic content values, device chrome, and
   exact pixel positions.

## Proposed `/servo:design-eval` shape (for spec 012 to formalize)

**Guided authoring** detects the project's mockups + app screens and, per screen,
captures: `screen_id`, reference `{ file, selector, crop }`, app
`{ url, setup_script, viewport }`. Then it generates references, picks
`model`/`n`/`δ`/`threshold`, freezes, and installs `score_design_fidelity` into
`oracle.sh` + `.servo/install.json`.

**`freeze.json`** (ADR-0005 clause 2) pins + sha256-hashes: the screen dataset
(incl. reference PNGs), the rubric, the judge model id + decoding params, `n`,
the aggregation rule (mean − k·stderr lower bound), `δ`, threshold, score
semantics.

**`score_design_fidelity` component** (ADR-0005 clauses 3/5/7): validate freeze
hashes (rc=2 stale on mismatch); per screen → setup → screenshot app → judge `n`×
(app vs reference, under rubric) → lower-bound aggregate; average across screens
→ echo composite `[0,1]`; rc=2 (`env_error`) if browser/judge/`ANTHROPIC_API_KEY`
unavailable — never a silent `0.0`; append per-screen sampled+aggregated scores +
hashes to `ledger.jsonl`.

**Judge** = Anthropic Messages API (vision), pinned model + decoding — distinct
from servo's iteration `judge` agent (ADR-0005 clause 1).

## Artifacts
- Throwaway harness: `food-log/eval-spike/capture.mjs` (+ `shots/`), gitignored.
- Screens captured: Home (empty + seeded), AddSheet, Settings; references for
  Home/Settings clean, AddSheet reference needs the standalone-file fix (#4).
