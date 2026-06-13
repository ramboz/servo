---
name: design-eval
description: >-
  Author a frozen UI design-fidelity eval component for a project — the
  non-deterministic sibling of servo's deterministic component templates. Use
  when a project must be built to match a design mockup ("does the UI match the
  design?") and that fidelity should drive or gate the loop. Captures app vs
  reference screenshots, judges fidelity with a pinned vision model (n-sampled,
  lower-bound), freezes the definition, and installs a `score_design_fidelity`
  component into the project's `oracle.sh`. Do not use for deterministic checks
  (use scaffold-init / spec-oracle) or for the per-iteration judge agent.
---

# /servo:design-eval — UI design-fidelity eval recipe

"Does the built UI faithfully match the design?" is **non-deterministic** — it
needs a judge, not an assertion, and the judge's score wobbles run-to-run. This
skill turns that into a **frozen eval component** (servo ADR-0005 / ADR-0006):
a project-authored `score_design_fidelity` that drops into the existing
`oracle.sh` + 0/1/2 contract unchanged, so the agent-loop can iterate a UI
toward its mockup and the quality-gate can attest the result.

**Ownership.** servo owns the *mechanism* (capture + judge + freeze + the
runtime `score.py`); the *project* owns the *policy* (which screens, the rubric,
the judge model, `n`/`k`/`δ`/threshold). Honesty is preserved: servo scores, it
does not prove; a missing key / unreachable judge is `env_error` (rc=2), never a
silent `0.0`; a changed rubric/dataset/model refuses as stale.

## Prerequisites

- A servo-scaffolded target (`oracle.sh` + `.servo/install.json` present — run
  `/servo:scaffold-init` first).
- The project can screenshot its UI with **Playwright** (a project
  devDependency; `npx playwright install chromium` once). servo ships no browser.
- Design mockups renderable in a browser (e.g. claude-design `.dc.html`).
- A judge transport for live scoring (the freeze + install steps need neither;
  only `score` does):
  - **`"api"`** (default) — the Anthropic Messages API; needs `ANTHROPIC_API_KEY`
    in the environment.
  - **`"cli"`** — a headless `claude -p`, which runs the vision judge on a Claude
    subscription with **no API key** (set `judge.transport: "cli"`; needs the
    `claude` CLI on `PATH`, or point `SERVO_DESIGN_EVAL_CLAUDE_BIN` at it).

## Flow

1. **`init`** — `python3 design_eval.py init <target>` scaffolds
   `<target>/.servo/design-eval/` with the runtime (`score.py`, `capture.mjs`)
   and a `config.json` skeleton (copied from `templates/config.example.json`).

2. **Author `config.json`** (the policy). For each screen set:
   - `id`, `weight`;
   - `reference` (output PNG path) + `referenceSource` `{ file, selector, crop }`
     — the mockup artifact, the element selector, and crop insets that strip
     device chrome (bezel + status bar + home indicator);
   - `setup` — a `setups/<id>.mjs` exporting `default(page, config)` that seeds
     **deterministic** state (the app is now-dependent: seed entries, pin the
     period/clock) and navigates to the screen;
   - and globally: `app_url`, `viewport`, `samples` (`n`, `k`, `delta`),
     `threshold`, the `rubric`, and `judge`:
     - `model` — a **vision-capable** model id (e.g. `claude-sonnet-4-6`);
     - `transport` — `"api"` (default) or `"cli"` (see Prerequisites);
     - `temperature` / `max_tokens` — decoding params that apply to the **`"api"`
       transport only**; `claude -p` exposes no decoding flags, so the `"cli"`
       transport runs at the model's CLI default and ignores them. (Both are
       still hashed into the freeze, so editing either re-freezes regardless.)

3. **`capture-refs`** — `python3 design_eval.py capture-refs <target>` renders
   each `referenceSource` to its `reference` PNG (cropped). Eyeball them.

4. **`freeze`** — `python3 design_eval.py freeze <target>` pins + sha256-hashes
   the definition (model/n/δ/threshold/screens), the rubric, and every reference
   + setup file, and sets `approval_status: approved`. Any later edit to those
   refuses at score time as **stale** until re-frozen.

5. **`install`** — `python3 design_eval.py install <target> [--weight W]`
   splices `score_design_fidelity` into `oracle.sh`, registers it in COMPONENTS
   + `.servo/install.json`, and copies the runtime into the target.

6. **Run** — `/servo:quality-gate` (or `/servo:agent-loop`) now includes the
   fidelity component in the weighted composite. The component, per run:
   validates the freeze → screenshots the app at each seeded state → judges
   app-vs-reference `n`× under the rubric → reports a conservative lower bound
   (`mean − k·stderr`) per screen → weighted-average composite. Each run appends
   the sampled + aggregated scores + hashes to `ledger.jsonl`.

   **Pair with the loop's plateau noise floor**: pass
   `/servo:agent-loop --plateau-noise-floor <δ>` (ADR-0005 clause 4) so the
   wobbling eval cannot fake progress or fake a plateau.

## Files (in `<target>/.servo/design-eval/`)

| File | Role |
|---|---|
| `config.json` | the frozen policy (screens, rubric, model, n/k/δ, threshold, hashes) |
| `score.py` | runtime: freeze-validate → capture → judge → aggregate → composite |
| `capture.mjs` | Playwright: render references / screenshot the seeded app |
| `setups/<id>.mjs` | per-screen deterministic state + navigation |
| `refs/<id>.png` | frozen reference screenshots (chrome-cropped) |
| `ledger.jsonl` | per-run sampled + aggregated scores + hashes (audit) |

## Authoring tips

- Keep `n` × `|screens|` bounded — it counts against the loop's cost ceiling.
- Start the threshold below the first frozen composite, then raise it as the UI
  improves; the loop optimises toward it.
- Tune `k`/`δ` together: too wide and the component never passes; too narrow and
  it flaps. Lean conservative (wider) when the judge is noisy.
- Sample at `temperature > 0`. The n-sample lower bound (`mean − k·stderr`) only
  protects you if the samples can *spread*: the app is screenshotted once and
  judged `n`× against it, so at `temperature: 0` those calls are near-identical,
  `stderr ≈ 0`, the lower bound collapses to the mean, and you pay `n`× the cost
  for no within-run anti-flap (ADR-0005 clause 3). The example ships `0.6`; lean
  higher for a more conservative judge. (Applies to the `"api"` transport; the
  `"cli"` transport runs at the model's CLI default.)
- The rubric should score *design intent* (layout/palette/type/shape), not
  dynamic content; bake the ignore-list into the rubric text.
