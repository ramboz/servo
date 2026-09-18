---
name: content-fidelity
description: >-
  Author a frozen text content-fidelity eval component for a project — the
  non-visual sibling of servo's design-eval. Use when generated text (a
  reply, a doc, a templated message) must match an intended rubric or spec
  ("does this text match the intended tone/content/style?") and that
  fidelity should drive or gate the loop. Gathers the generated text under
  test (file read or generator command), judges fidelity with a pinned
  text-capable model (n-sampled, lower-bound), freezes the definition, and
  installs a `score_content_fidelity` component into the project's
  `oracle.sh`. Do not use for deterministic checks (use scaffold-init /
  spec-oracle), for visual/UI fidelity (use design-eval), or for the
  per-iteration judge agent.
---

# /servo:content-fidelity — text content-fidelity eval recipe

"Does the generated text faithfully match the intended rubric or spec?" is
**non-deterministic** — it needs a judge, not an assertion, and the judge's
score wobbles run-to-run. This skill turns that into a **frozen eval
component** (servo ADR-0005 / ADR-0024): a project-authored
`score_content_fidelity` that drops into the existing `oracle.sh` + 0/1/2
contract unchanged, so the agent-loop can iterate generated text toward its
target and the quality-gate can attest the result.

**Ownership.** servo owns the *mechanism* (gather + judge + freeze + the
runtime `score.py`); the *project* owns the *policy* (which cases, the
rubric, the judge model, `n`/`k`/`δ`/threshold). Honesty is preserved: servo
scores, it does not prove; a missing key / unreachable judge / artifact-
gathering failure is `env_error` (rc=2), never a silent `0.0`; a changed
rubric/dataset/model refuses as stale.

## Prerequisites

- A servo-scaffolded target (`oracle.sh` + `.servo/install.json` present — run
  `/servo:scaffold-init` first).
- A **text-capable** judge model id (no vision/multimodal requirement —
  unlike design-eval, this skill never sends image content).
- A judge transport for live scoring (the freeze + install steps need
  neither; only `score` does):
  - **`"api"`** (default) — the Anthropic Messages API; needs
    `ANTHROPIC_API_KEY` in the environment.
  - **`"cli"`** — a headless `claude -p`, which runs the text judge on a
    Claude subscription with **no API key** (set `judge.transport: "cli"`;
    needs the `claude` CLI on `PATH`, or point
    `SERVO_CONTENT_FIDELITY_CLAUDE_BIN` at it).
- No Playwright, no browser — text is read from a file or captured from a
  command's stdout, never rendered.

## Flow

1. **`init`** — `python3 content_fidelity.py init <target>` scaffolds
   `<target>/.servo/content-fidelity/` with the runtime (`score.py`) and a
   `config.json` skeleton (copied from `templates/config.example.json`).

2. **Author `config.json`** (the policy). For each case set:
   - `id`, `weight`;
   - `reference` — the rubric/spec text this case should match, either
     inline in `config.json` or a path to a text file under the eval dir;
   - `source` — where the *generated* text under test comes from:
     - `{"type": "file", "path": "..."}` — read the target's
       already-generated text output at a given path, **relative to** the
       eval dir at score time;
     - `{"type": "command", "run": [...]}` — run a project-supplied
       generator and capture its stdout;
   - and globally: `samples` (`n`, `k`, `delta`), `threshold`, the `rubric`,
     and `judge`:
     - `model` — any **text-capable** model id (e.g. `claude-sonnet-4-6`);
     - `transport` — `"api"` (default) or `"cli"` (see Prerequisites);
     - `temperature` / `max_tokens` — decoding params for the **`"api"`
       transport only**; `claude -p` exposes no decoding flags, so the
       `"cli"` transport runs at the model's CLI default and ignores them.
       (Both are still hashed into the freeze, so editing either re-freezes
       regardless.)

3. **`freeze`** — `python3 content_fidelity.py freeze <target>` pins +
   sha256-hashes the definition (model/n/δ/threshold/cases), the rubric, and
   every file-backed reference, and sets `approval_status: approved`. Any
   later edit to those refuses at score time as **stale** until re-frozen.

4. **`install`** — `python3 content_fidelity.py install <target> [--weight W]`
   splices `score_content_fidelity` into `oracle.sh`, registers it in
   COMPONENTS + `.servo/install.json`, and copies the runtime into the
   target.

5. **Run** — `/servo:quality-gate` (or `/servo:agent-loop`) now includes the
   fidelity component in the weighted composite. The component, per run:
   validates the freeze → gathers the generated text once per case → judges
   it against the reference `n`× under the rubric → reports a conservative
   lower bound (`mean − k·stderr`) per case → weighted-average composite.
   Each run appends the sampled + aggregated scores + hashes to
   `ledger.jsonl`.

   **Pair with the loop's plateau noise floor**: pass
   `/servo:agent-loop --plateau-noise-floor <δ>` (ADR-0005 clause 4) so the
   wobbling eval cannot fake progress or fake a plateau.

## Files (in `<target>/.servo/content-fidelity/`)

| File | Role |
|---|---|
| `config.json` | the frozen policy (cases, rubric, model, n/k/δ, threshold, hashes) |
| `score.py` | runtime: freeze-validate → gather → judge → aggregate → composite |
| `refs/<id>.txt` | file-backed reference text (if a case uses a file reference) |
| `ledger.jsonl` | per-run sampled + aggregated scores + hashes (audit) |

## Limitation: `command`-backed cases have no structural determinism guarantee

**This is a named limitation, not a soft tip.** design-eval enforces
cross-run determinism *structurally*: every screen requires a
`setups/<id>.mjs` that seeds deterministic app state before capture
(`skills/design-eval/SKILL.md`). content-fidelity's `command`-backed source
has **no equivalent structural requirement** — a project can point `source`
at any generator, including a non-deterministic (e.g. LLM-backed) one, and
nothing in this skill enforces otherwise.

Within a single scoring run this is safe: the artifact is gathered exactly
once per case and judged `n` times against that one fixed text (see
`score.py::score()`), so the n-sample lower bound still measures judge
confidence, not generator variance (ADR-0005 clause 3). But **across runs**,
a non-deterministic `command` case can produce a composite delta that
ADR-0005 clause 4's plateau noise floor `δ` was never sized to absorb — `δ`
is calibrated to *judge* stderr, not *generator* output drift. The
noise-floor mechanism itself is not broken; it works correctly on whatever
delta it is given. The gap is that a `command` case can hand it a delta
outside what it was sized for, and `loop.py` may then read generator drift
as false progress or a false plateau, with **zero servo-side mitigation for
that input class** today.

**Recommendation:** prefer `file`-backed cases (a target-written, inherently
stable artifact) over `command` for any case that gates a loop's plateau
detection, until a structural fix exists (see
`docs/refinement-todo.md` for the candidate mitigation under consideration —
content-hash-keyed caching of the gathered artifact across a loop's plateau
window).

## Authoring tips

- Keep `n` × `|cases|` bounded — it counts against the loop's cost ceiling.
- Start the threshold below the first frozen composite, then raise it as the
  generated text improves; the loop optimises toward it.
- Tune `k`/`δ` together: too wide and the component never passes; too narrow
  and it flaps. Lean conservative (wider) when the judge is noisy.
- Sample at `temperature > 0`. The n-sample lower bound (`mean − k·stderr`)
  only protects you if the samples can *spread*: the text is gathered once
  and judged `n`× against it, so at `temperature: 0` those calls are
  near-identical, `stderr ≈ 0`, the lower bound collapses to the mean, and
  you pay `n`× the cost for no within-run anti-flap (ADR-0005 clause 3). The
  example ships `0.6`; lean higher for a more conservative judge. (Applies
  to the `"api"` transport; the `"cli"` transport runs at the model's CLI
  default.)
- The rubric should score *content intent* (tone, key points, structure,
  style-guide adherence), not incidental wording — bake the ignore-list into
  the rubric text.
