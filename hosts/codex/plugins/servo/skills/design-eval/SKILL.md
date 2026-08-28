---

name: design-eval
description: >-
  Author a frozen UI design-fidelity eval component for a project — the non-deterministic sibling of servo's deterministic component templates. Use when a project must be built to match a design mockup ("does the UI match the design?") and that fidelity should drive or gate the loop. Captures app vs reference screenshots, judges fidelity with a pinned vision model (n-sampled, lower-bound), freezes the definition, and installs a `score_design_fidelity` component into the project's `oracle.sh`. Do not use for deterministic checks (use scaffold-init / spec-oracle) or for the per-iteration judge agent.
---

# /servo:design-eval — UI design-fidelity eval recipe

"Does the built UI faithfully match the design?" is **non-deterministic** — it
needs a judge, not an assertion, and the judge's score wobbles run-to-run. This
skill turns that into a **frozen eval component** (servo ADR-0005 / ADR-0006):
a project-authored `score_design_fidelity` that drops into the existing
`oracle.sh` + 0/1/2 contract unchanged, so the agent-loop can iterate a UI
toward its mockup and the quality-gate can attest the result.

**Ownership.** servo owns the *mechanism* (capture + judge + freeze + the
runtime `score.py`); the *project* owns the *policy* (which screens, the scoring policy,
the judge model, `n`/`k`/`δ`/threshold). Honesty is preserved: servo scores, it
does not prove; a missing key / unreachable judge is `env_error` (rc=2), never a
silent `0.0`; a changed policy/dataset/model refuses as stale.

## Prerequisites

- A servo-scaffolded target (`oracle.sh` + `.servo/install.json` present — run
  `/servo:scaffold-init` first).
- The project can screenshot its UI with **Playwright** (a project
  devDependency; `npx playwright install chromium` once). servo ships no browser.
  **If it is missing, you do not have to remember this:** the scoring run
  preflights `node` and the Playwright library on the machine that actually
  runs the oracle — CI, a Routine, a detached loop — and fails with the exact
  install command for that machine rather than an opaque error. Failures stay
  `env_error` (rc 2), never a silent `0.0`.
- Design mockups renderable in a browser (e.g. claude-design `.dc.html`).
- A judge transport for live scoring (the freeze + install steps need neither;
  only `score` does):
  - **`"api"`** (default) — the Anthropic Messages API; needs `ANTHROPIC_API_KEY`
    in the environment.
  - **`"cli"`** — a headless `claude -p`, which runs the vision judge on a Claude
    subscription with **no API key** (set `judge.transport: "cli"`; needs the
    `claude` CLI on `PATH`, or point `SERVO_DESIGN_EVAL_CLAUDE_BIN` at it).
  - **`"subagent"`** — an **attended, non-frozen ADVISORY** transport (029-02 /
    [ADR-0034](../../docs/decisions/adr-0034-design-eval-subagent-judge-transport.md))
    for the setup where neither of the above is reachable — Claude Code inside the
    **Claude Desktop app** (no spawnable `claude -p`, no API key). The orchestrating
    session runs the vision judge itself. **It is not a gating score.** The oracle
    path (`score.py`, the `score_design_fidelity` component) **refuses** `subagent`
    transport with `env_error` regardless of attendance — the discriminator is the
    *entrypoint*, so even the attended `/servo:agent-loop` gate can never consume a
    subagent number. Reach the read **only** via `python3 design_eval.py advisory
    <target>`: it captures each screen (any capture provider — pairs naturally with
    `manual` for a non-automatable target), writes a judge request to
    `subagent/request.json`, and waits (bounded — `SERVO_DESIGN_EVAL_SUBAGENT_TIMEOUT`,
    default 120s) for the session to score and write `subagent/response.json`. No
    session responds → `env_error` (never a hang, never a silent 0.0). The model is
    **self-reported, not verified** (recorded as `self_reported_model` in the
    ledger, never attestation), and every run prints a loud `SUBAGENT JUDGE …`
    stderr advisory. Use it to *steer authoring/iteration*, not to gate — a gating
    fidelity score still needs `api`/`cli`.

## Flow

1. **`init`** — `python3 design_eval.py init <target>` scaffolds
   `<target>/.servo/design-eval/` with the runtime (`score.py`, `capture.mjs`,
   `capture_lib.mjs`, and the shared `fidelity_eval.py`) and a `config.json`
   skeleton (copied from `templates/config.example.json`).

2. **Author `config.json`** (the policy). For each screen set:
   - `id`, `weight`;
   - `reference` (output PNG path) + `referenceSource` `{ file, selector, crop }`
     — the mockup artifact, the element selector, and crop insets that strip
     device chrome (bezel + status bar + home indicator);
   - `setup` — a `setups/<id>.mjs` exporting `default(page, config)` that seeds
     **deterministic** state (the app is now-dependent: seed entries, pin the
     period/clock) and navigates to the screen;
   - and globally: `app_url`, `viewport`, `samples` (`n`, `k`, `delta`),
     `threshold`, the **structured scoring policy** (`schema_version: 2` +
     `dimensions` + `ignore`, 028-01 / [ADR-0033](../../docs/decisions/adr-0033-design-eval-structured-scoring-policy.md)),
     and `judge`:
     - `dimensions: [{id, description, weight?}]` — the aspects that ARE scored
       (layout, palette, typography, component-shape, …). The judge instruction is
       **assembled from this list**, so what the judge scores is a function of the
       approved structure, not hand-written prose. Under the current holistic
       fallback, `weight` is **advisory to the judge** (passed as relative-importance
       guidance in the prompt), not a mechanical per-dimension multiplier — editing
       it changes the guidance (and re-freezes) but does not by itself change the
       arithmetic; mechanical per-dimension weighting arrives with per-dimension
       sub-scoring (deferred; `docs/refinement-todo.md`).
     - `ignore: [{id, reason}]` — the aspects explicitly **excluded** from the
       score, each a **discrete, reason-bearing item** — never prose buried in a
       sentence. This is the anti-gaming split: an exclusion is a visible,
       hashed, reviewable record, not a silent "IGNORE …" clause. (The legacy
       free-text `rubric` is **gone**: a `schema_version: 1` config refuses at
       freeze/score time with a re-author message — force re-author, ADR-0033 §5.
       *Per-dimension* sub-scoring is a deferred follow-up — see
       `docs/refinement-todo.md`; today the judge returns one holistic score under
       the structured instruction, the ADR-0033 Kill-criteria fallback shape.)
     - `model` — a **vision-capable** model id (e.g. `claude-sonnet-4-6`);
     - `transport` — `"api"` (default) or `"cli"` (see Prerequisites);
     - `temperature` / `max_tokens` — decoding params that apply to the **`"api"`
       transport only**; `claude -p` exposes no decoding flags, so the `"cli"`
       transport runs at the model's CLI default and ignores them. (Both are
       still hashed into the freeze, so editing either re-freezes regardless.)
   - optionally, `capture` — which **capture provider** takes the app
     screenshots: `capture.transport`, `"web"` (Playwright) by default. The
     `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT` env var overrides the config value
     (precedence: env → `capture.transport` → `"web"`). Unlike `judge`, the
     capture transport is **environmental, not frozen** — it is **not** hashed
     into the freeze (ADR-0031/ADR-0032 §6), so switching it never re-freezes; the
     provider that actually ran is recorded in `ledger.jsonl` instead (see below).
     An unknown provider fails closed to `env_error`, never a silent score. The
     providers:
     - `"web"` (default) — the built-in Playwright path (`node capture.mjs`).
     - `"command"` — the **escape hatch** for any non-web stack. Set
       `capture.command` to an argv list; servo invokes it **per screen** as
       `<your argv…> --screen <id> --out <path>` (cwd = the eval dir, 180s
       timeout). Your command must **drive the app into that screen's state,
       screenshot it, and write a frame-normalized PNG to `--out`** — state
       seeding and chrome-cropping are the command's job, not servo's (ADR-0032
       §4/§5); servo does not run your `setup` module or post-process the image.
       A non-zero exit, timeout, missing binary, or no-output PNG fails closed to
       `env_error`; a missing/empty `capture.command` fails before any capture.
       The resolved argv is recorded in the ledger as `capture_command`. If your
       command emits no `##servo-capture:` attestation line its per-screen
       provenance is honestly `not_attested` (never a fabricated engine).
     - `"android"` — a **blessed built-in** for native Android. Servo runs
       `adb -s <serial> exec-out screencap` per screen, optionally fires a
       per-screen deep link first, and crops the device chrome to the reference
       frame. Config under `capture.android`:
       - `serial` — device/emulator serial; precedence is `serial` →
         `SERVO_DESIGN_EVAL_ANDROID_SERIAL` → the single connected device. No
         device, or an ambiguous set with no serial, fails closed to `env_error`.
       - `crop` — `{top,bottom,left,right}` pixel insets stripping the status /
         navigation bars to the reference's logical frame (via a dependency-free
         stdlib PNG crop; an out-of-bounds crop fails closed).
       - a screen may set `deeplink: "<uri>"` to seed its state
         (`am start -a VIEW -d <uri>`); complex tap-flows use the `command`
         provider instead. State equivalence to the web seed is project-authored,
         not certified (ADR-0032 §4).
       `adb` is found on `PATH` or via `SERVO_DESIGN_EVAL_ADB_BIN`; the resolved
       screencap argv is the ledger `capture_command`, and provenance is
       `not_attested` (adb has no attestation channel).
     - `"ios"` — a **blessed built-in** for native iOS, parallel to `android`.
       Servo runs `xcrun simctl io <target> screenshot` per screen (writing a PNG
       to the shot file), optionally fires `simctl openurl` first, and crops the
       chrome via the same stdlib cropper. Config under `capture.ios`:
       - `udid` — simulator udid; precedence is `udid` →
         `SERVO_DESIGN_EVAL_IOS_UDID` → the literal `booted` (simctl's
         single-booted-simulator selector; simctl fails closed if none/ambiguous).
       - `crop` — `{top,bottom,left,right}` pixel insets (out-of-bounds /
         non-integer fails closed).
       - a screen may set `deeplink: "<uri>"` (→ `simctl openurl`); complex flows
         use the `command` provider. State equivalence is project-authored (§4).
       `xcrun` is found on `PATH` or via `SERVO_DESIGN_EVAL_XCRUN_BIN`; the resolved
       screenshot argv is the ledger `capture_command`; provenance is
       `not_attested` (simctl has no attestation channel).
     - `"manual"` — a **human-supplied PNG** for **non-automatable** targets
       (an in-game overlay, a Windows-only plugin on a Mac host — anything servo
       cannot drive), 029-01 / [ADR-0035](../../docs/decisions/adr-0035-design-eval-manual-capture-provider.md).
       You stage the screenshot at `manual/<screen-id>.png` under the eval dir;
       servo consumes it, optionally chrome-crops it (`capture.manual.crop`
       `{top,bottom,left,right}`), retains it as the run's shot, and records
       per-screen `provenance: manual_capture` with the input's sha256 + mtime.
       An absent / non-PNG staged shot fails closed to `env_error`. **Every manual
       run prints a loud `MANUAL CAPTURE …` stderr advisory** naming the sha256 —
       the tell is masquerade-prevention (a manual composite can never pass as a
       servo-captured measurement), **not** doctoring-detection: a human controls
       the bytes, so a fabricated image is possible and inherent (ADR-0035 §6);
       the honesty gain over `SERVO_DESIGN_EVAL_FAKE_SCORES` is a real, retained,
       hashed image scored by the real judge, loudly marked. State-seeding and
       framing are the human's job; servo runs no `setup`. Distinct from the
       fake-scores test hook — it must be explicitly selected and is never silent.

3. **`capture-refs`** — `python3 design_eval.py capture-refs <target>` renders
   each `referenceSource` to its `reference` PNG (cropped). Eyeball them.

4. **`freeze`** — `python3 design_eval.py freeze <target>` pins + sha256-hashes
   the definition (model/n/δ/threshold/screens), the structured policy (dimensions + ignore), and every reference
   + setup file, and sets `approval_status: approved`. Any later edit to those
   refuses at score time as **stale** until re-frozen. **Freeze surfaces the
   exclusion list and refuses without an acknowledgement** (028-02 / ADR-0033 §4):
   it prints `SCORES N … / EXCLUDES M …` and will not stamp `approved` unless you
   pass **`--reviewer <id>`** (a party *distinct from the author* who vetted the
   exclusions → `approval_provenance: reviewed`, the prevention path) or
   **`--acknowledge-exclusions`** / `SERVO_DESIGN_EVAL_ACK_EXCLUSIONS=1` (a human
   owner accepting them → `self_approved`, **auditability-only**). A `self_approved`
   freeze is legible in the ledger and prints a loud `SELF-APPROVED …` advisory on
   every run — because a self-acked ignore-list carries auditability, **not**
   prevention (a backwards-authored policy would not have been vetoed). The env
   bypass is a human-owner ack; it is **never** silently upgraded to `reviewed`.
   **`reviewed` is ENFORCED (028-03):** `--reviewer <id>` earns `reviewed` only when
   a **recorded independent re-enumeration verdict** exists that (a) names a
   `reviewer` **distinct from the author** — distinctness is proven by the *record*
   (both ids required at `record-reenumeration` time, `reviewer != author` rejected
   at the source), **not** by an optional freeze flag; (b) is `verdict: pass`;
   (c) attests a **non-empty** `catalogue`; and (d) still matches the current
   **policy + reference** fingerprint (a reference swap, a disposition re-file, or a
   catalogue edit stales it). Without all of that — or on a `fail`, a self-review, an
   empty catalogue, or a stale verdict — freeze refuses `reviewed` (fall back to
   `--acknowledge-exclusions` for self_approved). This is what defends the
   **omission** path — a thin catalogue that silently drops divergences (ADR-0033's
   2×2): auditability holds unconditionally, but *prevention* rests entirely on this
   distinct re-enumerator. (`freeze --author <id>` is an optional cross-check against
   the record; it is not the source of the distinctness guarantee.) **Residual:** the
   verdict record is a local, author-writable file with no attestation — identity
   distinctness rests on truthful `--reviewer`/`--author` inputs, so this is a
   *structured, catalogue-bound* discipline, not forgery-proof; the real teeth are
   the out-of-band independent reviewer actually doing the re-enumeration.

   **Enumerate-first + the re-enumeration verdict (028-03):**
   - `catalogue: [{id, description}]` — the **itemised divergence list** for the
     eval. `python3 design_eval.py catalogue <target>` prints it with each item's
     disposition (`SCORED` / `IGNORED` / `UNDISPOSITIONED`) and **no score**, for a
     human/reviewer to triage before any scalar. **Freeze refuses** if any
     catalogued item is undispositioned (neither a `dimension` nor an `ignore`) — no
     third, unaccounted state. The catalogue is hashed into the frozen definition,
     so editing it re-freezes (and invalidates a prior verdict).
   - `python3 design_eval.py record-reenumeration <target> --reviewer <id> --author
     <id> --verdict pass|fail [--note …]` records the independent reviewer's verdict
     (analogous to an ADR frame-critique verdict). The **live vision re-enumeration**
     — the reviewer actually reading the reference and hunting for an uncatalogued
     divergence — is that independent reviewer's job (a distinct subagent / human,
     out of band); servo records + enforces the verdict, it does not fake it.

5. **`install`** — `python3 design_eval.py install <target> [--weight W]`
   splices `score_design_fidelity` into `oracle.sh`, registers it in COMPONENTS
   + `.servo/install.json`, and copies the runtime into the target.

6. **Run** — `/servo:quality-gate` (or `/servo:agent-loop`) now includes the
   fidelity component in the weighted composite. The component, per run:
   validates the freeze → screenshots the app at each seeded state → judges
   app-vs-reference `n`× under the structured policy → reports a conservative lower bound
   (`mean − k·stderr`) per screen → weighted-average composite. Each run appends
   the sampled + aggregated scores + hashes to `ledger.jsonl`.

   **Pair with the loop's plateau noise floor**: pass
   `/servo:agent-loop --plateau-noise-floor <δ>` (ADR-0005 clause 4) so the
   wobbling eval cannot fake progress or fake a plateau.

## Files (in `<target>/.servo/design-eval/`)

| File | Role |
|---|---|
| `config.json` | the frozen policy (screens, dimensions + ignore, model, n/k/δ, threshold, hashes) |
| `score.py` | runtime: freeze-validate → capture → judge → aggregate → composite |
| `fidelity_eval.py` | shared frozen-eval harness (hash/aggregate/ledger/splice), imported by `score.py` (ADR-0024) |
| `capture.mjs` | Playwright: render references / screenshot the seeded app |
| `capture_lib.mjs` | pure helpers imported by `capture.mjs`: clip geometry, flag/screen resolution, and the engine-attestation channel |
| `pngcrop.py` | dependency-free stdlib PNG cropper, imported by `score.py` for the native providers' chrome-frame normalization (027-04) |
| `setups/<id>.mjs` | per-screen deterministic state + navigation |
| `refs/<id>.png` | frozen reference screenshots (chrome-cropped) |
| `ledger.jsonl` | per-run sampled + aggregated scores + hashes, plus **per-screen provenance** (audit) |

### Provenance in the ledger

Each `ledger.jsonl` row records, **per screen**, which browser actually rendered
that screenshot — `engine`, `engine_version`, `capture_transport`, and a
`provenance` token. It is **observability, not a gate**: nothing here is hashed,
none of it can raise `StaleError`, and a provenance failure never fails a score.

Read it when a fidelity score shifts and you want to know whether the engine
changed. The consumer is a human — nothing reads it programmatically today.

- `attested` — the capture process reported the engine it launched.
- `not_attested` — capture happened, identity unavailable (`provenance_error`
  says why: no accessor, or the accessor threw).
- `not_captured` — **no browser ran at all** (the `SERVO_DESIGN_EVAL_FAKE_SCORES`
  path still writes a row). A synthetic score is never byte-indistinguishable
  from a real capture.

**What each field is worth as evidence.** `engine` + `engine_version` are the
real attestation — reported by the process that actually launched the browser.
`capture_transport` is the transport that process was *instructed* to use,
echoed back as a mismatch canary; it is **not** independent evidence of what
launched. Note it is also deliberately distinct from the row's top-level
`transport`, which means the **judge** transport (`api`/`cli`) in every
historical row.

**Which capture provider ran.** The row also carries a top-level
`capture_provider` — the provider selected for that run (`"web"` today; see the
`capture.transport` selector above), or `null` on the fake-scores path where no
capture ran. Keep the three transport-ish names straight: top-level `transport`
is the **judge** transport (`api`/`cli`); top-level `capture_provider` is the
**capture provider** (027-02); per-screen `capture_transport` is the browser
transport that provider's process was instructed to use (026-03). All are
advisory — none is hashed.

**The shot that was judged.** Each per-screen entry also carries `shot`: a path,
relative to the eval directory, to the exact PNG that screen was scored on — or
`null` on the `not_captured` (fake-scores) path, where no browser ran. Shots are
retained per run (`shots/app-<id>-<run_id>.png`), never clobbered, so a past
row's `shot` still resolves: open it to see what the judge saw behind any score.
Like the rest of this row it is observability, not a gate — nothing here is
hashed. (`shots/` grows without bound today; a retention cap is a tracked
follow-up in `docs/refinement-todo.md`.)

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
- Score *design intent* (layout/palette/type/shape) via `dimensions`, not dynamic
  content. **Exclusions are dangerous, not free.** Every `ignore` entry defines a
  divergence *out of the score* — which is how a policy can be built *backwards*
  from a desired pass: widen the ignore-list until only the parts that already
  match are scored, then let `freeze` + hash + n-sampling lend it the look of
  rigor (the field report's exact failure). The structured split makes each
  exclusion a **discrete, hashed, reviewable `{id, reason}`** rather than prose an
  author can bury — but structure alone does not *prevent* gaming, it makes it
  **auditable**. Keep exclusions minimal; give each a real `reason`; and remember
  the load-bearing defense against a thin/omitted catalogue is an **independent
  re-enumerating reviewer at freeze** (028-02 / 028-03), not the author's own
  say-so (ADR-0033's 2×2).
