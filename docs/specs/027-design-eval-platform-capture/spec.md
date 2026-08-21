---
status: IN_PROGRESS
skill:
use_cases: []
---

# Spec 027: Platform-agnostic design-eval capture

> Implements [ADR-0032](../../decisions/adr-0032-design-eval-capture-providers.md)
> (Accepted) — make `/servo:design-eval`'s app capture a pluggable provider so
> non-web stacks can be scored — plus the shared shot-retention plumbing that
> makes any run's screenshots inspectable. GitHub #22.

## Overview

`/servo:design-eval` scores UI fidelity by screenshotting the running app and
judging it against a frozen mockup. Today capture is hardwired to a headless
browser: `capture.mjs` hard-imports Playwright's `chromium`, and
`score.py::capture_app` (`skills/design-eval/score.py:161`) spawns
`node capture.mjs …` as its only capture path. Everything downstream — the
vision judge, the n-sample lower bound, the freeze, the composite — touches only
two PNGs, so it is already platform-blind. Only capture is web-coupled.

[ADR-0032](../../decisions/adr-0032-design-eval-capture-providers.md) decided to
make capture a **pluggable provider** owning three per-screen steps (drive the
app to a state, take the screenshot, normalize the frame), with the mechanism
kept environmental (ledger, not the frozen hash — extending
[ADR-0031](../../decisions/adr-0031-design-eval-browser-acquisition.md)), seeding
per-platform, and only references/rubric/judge shared across stacks. This spec
builds that, in vertical slices, and ships one piece of **shared plumbing** the
issue surfaced along the way: app screenshots are currently **clobbered** every
run (fixed name `shots/app-<id>.png`, `score.py:168`) and **not surfaced**
anywhere — there is no `report.md`; `main()` prints only the composite float
(`score.py:423`). The per-run history that *does* exist is `ledger.jsonl`, but it
carries no pointer to the images it scored.

## Assumptions

None load-bearing beyond probe-verified current-state claims. The claims this
spec rests on were read from source on 2026-08-21:
- app capture writes `base_dir/shots/app-<id>.png` with a fixed name, overwritten
  each run (`score.py:161-176`);
- the per-screen crop (`boundingBox`/`computeClip`) runs only in `capture.mjs`'s
  `--refs` reference-authoring branch, not the app-screenshot branch (the app
  shot is an uncropped full-viewport grab);
- `_judge_cli` cwd's to `app_png.parent.parent` (`score.py:222`), so app-shot
  path *depth* is load-bearing for the CLI judge's Read sandbox;
- `ledger.jsonl` is written by `_fe.write_ledger` with one record per run, each
  carrying per-screen `samples`/`lower_bound`/provenance but no shot path;
- `capture.transport` was designed in ADR-0031 but never built — spec 026-02 is
  DEFERRED (`score.py` reads only `judge.transport`).

## Decomposition

**SPIDR — Interface axis** (split by capture platform / channel; minimal first,
richer later). Spike is not needed: ADR-0032 already de-risked the design.

- **027-01** ships **shared plumbing** that stands alone (retention + ledger
  visibility), independent of the provider abstraction and valuable to web today.
- **027-02** introduces the **seam** with the existing web path as the default
  provider — behavior-preserving, the minimal interface.
- **027-03** adds the **custom-command provider** — the escape hatch that unlocks
  *any* non-web stack via a project script, the shortest path to cross-stack
  value and the first real exercise of the seam on a non-web target.
- **027-04 / 027-05** add the **blessed Android / iOS providers** (screencap +
  state driver + chrome-frame normalization), the richer built-ins.

Each slice touches the user-facing surface (the score run, the ledger, or a
newly scorable platform) and delivers end-to-end value; none is horizontal
phasing.

## Slices

- [027-01 — shot retention + ledger visibility](slice-01-shot-retention.md) — shared plumbing (all modes, web included)
- [027-02 — capture-provider seam + web default](slice-02-provider-seam-web.md) — DRAFT
- [027-03 — custom-command provider](slice-03-custom-command-provider.md) — DRAFT
- [027-04 — blessed Android provider](slice-04-android-provider.md) — DRAFT
- [027-05 — blessed iOS provider](slice-05-ios-provider.md) — DRAFT

Slices 02–05 depend on [ADR-0032](../../decisions/adr-0032-design-eval-capture-providers.md);
027-01 is independent shared plumbing. 027-02..05 will be fleshed to full ACs
when each is picked up (`READY_FOR_IMPLEMENTATION`).
