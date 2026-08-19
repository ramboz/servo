---
status: Proposed
dependencies: []
last_verified:
frame_review: true
---

# ADR-0031: design-eval browser acquisition — runtime preflight, unfrozen capture transport, browser identity in the ledger

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
- **Reproducibility (and the limit of what the freeze can do about it).** A
  fidelity score is only comparable across runs if the rendering engine is
  stable. The frozen definition
  ([ADR-0005](adr-0005-eval-oracle-component.md), `definition_hash`) pins the
  judge, samples, threshold, viewport, and screen set — and **deliberately does
  not pin environmental fields**. Its docstring is explicit: it "excludes
  anything *environmental* (e.g. design-eval's `app_url`, where the running app
  is reached) … pinning it would force a re-freeze + re-approval on an
  environment move." The browser is exactly such an environmental field.

  Moreover `validate_freeze` is **self-referential by construction**: it
  compares `definition_hash(config)` against the stored
  `approved_content_hash` plus on-disk artifact hashes, and never probes the
  live environment. So adding a browser-version string to the frozen definition
  would **not** detect drift — it would be an inert label that trips only when a
  human hand-edits the config. And making it a real gate (probing the live
  browser and refusing on mismatch) is the very anti-pattern the docstring
  rejects: every OS Chrome auto-update and every CI `npx playwright install`
  patch bump would raise `StaleError` → rc 2 → fail-closed halt, punishing the
  bring-your-own path hardest — the exact path the footprint argument favours.

  So the honest statement of the gap is narrower than "the freeze is unsound":
  **nothing records which browser produced a score**, which is an
  *observability* gap, not a missing gate. Whether engine drift is even a
  material noise source is itself unestablished — ADR-0005 clause 3's n-sample
  lower bound and the plateau noise floor δ already absorb the vision judge's
  own sampling variance, which for a semantic "does this UI match the design"
  judgment plausibly dominates sub-pixel rasterization differences.

A natural first instinct — "defer to the Claude/Codex browser connector" —
resolves cleanly against the architecture and is worth recording as a rejected
option: it works for *authoring-time* capture (an agent is present, and the
reference PNG is in the freeze hash so the capture transport is irrelevant to
reproducibility), but **cannot** serve *scoring-time* capture. The installed
component runs as `oracle.sh → gate.py → score.py → node capture.mjs`, a plain
subprocess with no MCP channel, under Routines / CI / detached `loop.py
--background` / the `oracle-hook` Stop hook. There is no agent to borrow a
browser from at score time.

**Where the gap is actually hit decides where to fix it.** The wall — the bare
`import` throwing `env_error` — is struck *at score time*, on whatever machine
runs the oracle: CI, a Routine, a detached `loop.py --background`, the
`oracle-hook` Stop hook. That machine is usually **not** the author's laptop.
So a detection-and-ask step in `init` (which runs once, on the authoring machine)
learns nothing about the machine where scoring later fails, and cannot ask a
human there because none is present. The core of the reported gap — "adopters
hit a wall with no guidance beyond prose" — is therefore a **runtime
message-quality problem on the failing machine**, best answered by a
non-interactive preflight in the scoring path, not by an interactive authoring
step. The "ask the adopter which browser they want" convenience is real but
secondary, and belongs where a human and install-consent actually exist:
authoring.

## Decision Options Considered

Two independent questions, kept separate because an earlier draft conflated them:
**(1) which browser and where its identity is recorded** (Options A–E), and
**(2) when and where acquisition/guidance happens** (Options F–G). The
recommendation composes an answer to each.

### Question 1 — which browser, and where identity is recorded


### Option A: Status quo — bundled Playwright + Chromium, prose-only prerequisite

- **Pros:** Version is implicitly pinned by the Playwright release, so
  reproducibility is stable by construction (modulo the ledger not recording
  it). Simplest code — the current `import { chromium } from 'playwright'`.
- **Cons:** No acquisition mechanism at all — the reported gap. ~150–300 MB
  download is the adoption barrier. Nothing records which browser produced a
  score, so a score shift after a Playwright bump is uninvestigable.

### Option B: Bring-your-own system Chrome only (`channel: 'chrome'` / `-core`)

- **Pros:** No browser download; drives the Chrome the adopter already has. Much
  lighter.
- **Cons:** Uncontrolled, silently-updating version → weaker run-to-run
  comparability, and the freeze cannot police it (see Context). Fails outright
  on a machine with no Chrome (CI images, headless servers). Forcing this on
  everyone trades one wall (download) for another (no Chrome present).

### Option C: `connectOverCDP` to a host-launched Chrome

- **Pros:** Zero download, zero browser-lifecycle management; dovetails with the
  connector idea (a host-launched Chrome on a debug port is drivable from a
  plain subprocess, no MCP needed).
- **Cons:** Requires a Chrome already running on a known debug port — an
  operational precondition that does not hold under unattended CI/Routines
  without extra orchestration. Version still uncontrolled (same as B).

### Option D: `capture` transport is a config choice; browser identity recorded in the ledger

A `capture` block in `config.json` records the chosen **transport**
(`"system-chrome"` / `"pinned-chromium"` / ...), sitting beside `app_url` and —
like `app_url` — **excluded from `definition_hash`**. Transport is
environmental: it answers "how do I reach a browser *here*", and the mechanism
that resolves it probes the machine. `score.py`/`capture.mjs` read it at runtime;
a named env override (`SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT`) takes precedence, so
a machine that lacks the configured browser can select another without editing —
let alone re-freezing — the eval. Both "reuse system Chrome" and "pinned
Chromium" are first-class.

The **resolved transport + browser name + version** are written to
`ledger.jsonl` **only** — never the frozen definition. Both are environmental;
per the freeze model's own rule (Context) pinning either would be inert at best
and a fail-closed halt on every environment move at worst. The ledger entry makes
a score shift *investigable* by a human without a gate that fires on
semantically irrelevant churn.

- **Pros:** No new fail-closed mode (nothing added is hashed). Adopter picks the
  footprint/comparability point. Records what rendered a score. Mirrors the
  established `app_url`-excluded and `SERVO_DESIGN_EVAL_CLAUDE_BIN`-override
  patterns.
- **Cons:** BYO engine drift is unpoliced (deliberate trade). A new `capture`
  config surface to validate.


### Option E (rejected): pin browser identity into the frozen definition

Add the resolved browser version to `definition_hash` so drift refuses as stale.
**Rejected on the evidence** (see Context): `validate_freeze` never probes the
environment, so a frozen version string is inert; and a live-probing variant is
the environmental-pinning anti-pattern `definition_hash`'s own docstring rejects,
converting every OS/CI browser patch bump into a fail-closed halt — worst
precisely on the BYO path this ADR is trying to enable.

### Question 2 — when and where acquisition/guidance happens

### Option F: interactive detect-and-ask in `init` (authoring-time only)

`init` (authoring) detects the environment, asks the adopter which transport
they want, and — with explicit consent — runs the installer in their repo.

- **Pros:** A human is present, so consent-gated install is possible; good for
  the author's own local loop.
- **Cons:** Runs on the **authoring** machine, which is generally not where the
  score-time wall is hit — so on its own it does not close the reported gap.
  Critically, `install()` calls `init()` unconditionally
  (`design_eval.py:148`), so making `init` interactive makes `install`
  block on stdin — a hazard in scripted/CI installs. Insufficient alone.

### Option G: non-interactive runtime preflight in the scoring path

The **node/library probe lives in `score.py`** (the Python parent that spawns
`node capture.mjs`), because `capture.mjs`'s own top-level
`import { chromium } from 'playwright'` (`capture.mjs:11`) throws before any of
its code can run — a module cannot preflight its own missing import. `score.py`
runs `shutil.which("node")`, a `require.resolve('playwright')` resolvability
check, and a per-transport reachability check **before** spawning capture, and
on failure emits the exact install/override command for *this* machine instead
of the opaque `node/playwright unavailable for capture`. Any `capture.mjs`-side
check is reserved for *post-launch* browser-reachability only.

- **Pros:** Runs on the machine that actually fails (CI/Routine/`--background`).
  Non-interactive by construction — no consent gate, no stdin. No new config
  surface. Directly upgrades the "no guidance beyond prose" message the gap is
  about. Still `env_error` (rc 2) — no new failure mode, just a better message.
- **Cons:** Cannot *install* unattended (nor should it — installing without
  consent on someone's CI is out of bounds); it guides, it does not acquire.
  Pairs with F, which supplies the consented-install path for authors.

## Recommended Decision

Compose **D + G + F**, in that order of load-bearing weight:

- **D — `capture.transport` is an unfrozen config field; transport + browser
  identity go to the ledger.** Excluded from `definition_hash` exactly as
  `app_url` is; overridable by `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT`. Both
  "reuse system Chrome" and "pinned Chromium" are first-class. Identity is
  recorded for a human investigating a score shift — no gate, no new
  fail-closed mode.
- **G (the primary *guidance* mechanism) — a non-interactive runtime preflight
  in the scoring path.** It closes the gap **as ADR-0020 forces it to be scoped**
  — a *guidance-quality* problem: it annotates the score-time wall with an
  actionable message for a human, on the machine that hits it. It does **not**
  let an unattended run acquire a browser and proceed (see its con). It is also
  the most *reversible* piece here — a better `env_error` string. The genuinely
  hard-to-reverse commitments are D's `capture` schema and its
  "missing block ⇒ assume bundled" back-compat default, and the
  F-out-of-`install()` boundary. Before capture, probe node / library /
  browser-for-the-resolved-transport and, on failure, emit the precise
  install-or-override command for *this* machine instead of the opaque
  `node/playwright unavailable`. It stays `env_error` (rc 2); it changes the
  message, not the contract.
- **F (secondary, authoring convenience) — optional detect-and-ask with
  consented install, at authoring time only.** It MUST NOT sit in the code path
  `install()` runs: `install()` calls `init()` unconditionally
  (`design_eval.py:148`), so the interactive ask lives behind an explicit
  opt-in (a separate verb or an `--interactive` flag), and `init`/`install`
  stay non-interactive by default. This preserves scripted/CI installs.

**Two corrections this ADR carries in its own body, because both were wrong in
earlier drafts and an accepted ADR must not launder its mistakes:**

1. *Footprint and reproducibility are not "dual."* Round-1 claimed pinning
   browser identity in the freeze made removing the download safe. False — the
   freeze is self-referential and cannot police the environment (Option E). They
   are in **tension**: BYO trades comparability for footprint, and servo offers
   **observability** (the ledger record) rather than a guarantee it cannot keep.
2. *The seam was in the wrong place.* Round-3 established that once transport is
   unfrozen, `init`-detection loses its rationale and aims at the wrong machine.
   The mechanism is therefore a runtime preflight (G), with authoring-time ask
   (F) demoted to an opt-in convenience.

Boundaries this ADR fixes (leaving implementation to a spec):

- `capture.transport` is **excluded from `definition_hash`** (environmental, like
  `app_url`); changing it never re-freezes. The env override is the CI escape
  hatch. *Note it does not follow that transport-freezing was ever attractive:* a
  transport **string** is not a browser **version**, so freezing it pins no
  engine — the same inertness that kills Option E — independent of the
  reference-PNG point below.
- Reference PNGs are already content-hashed at freeze, so the **reference**
  engine is fixed in bytes at `capture-refs` time. Engine mixing between the
  frozen reference and the live app is therefore *structural*, not a knob a
  frozen transport could remove; the spec should record the reference-render
  engine in the ledger so a mismatch is at least visible.
- The **resolved transport + browser identity** are appended to `ledger.jsonl`:
  not hashed, not a staleness trigger, advisory-warn-not-refuse on change.
  Consumer is a human; no programmatic reader exists today and this ADR adds
  none ([ADR-0017](adr-0017-conformance-scores-ledger.md), Proposed, is where one
  would be decided).
- The runtime preflight (G) is **non-interactive** and never installs; it guides.
  Its node/library probe lives in **`score.py`** (not `capture.mjs`, which cannot
  preflight its own top-level import); only post-launch browser-reachability may
  be checked `capture.mjs`-side. The consented installer (F) runs **only** at
  authoring, behind an explicit opt-in, never from `install()`'s `init()` call.
- The host browser connector stays **out of scope for scoring-time capture** and
  MAY serve only authoring-time reference rendering (the reference PNG is frozen,
  so its transport is irrelevant). This ADR does not require building it.
- `capture_app`'s contract is unchanged: subprocess, fails closed to `env_error`
  (rc 2), never a silent `0.0`.
- **No new fail-closed mode is introduced, and none is hidden in the schema.**
  Because neither transport nor browser identity is hashed, an environment move
  can never raise `StaleError`. The worst case stays the pre-existing
  `env_error` when no browser can be reached — the override avoids a **human
  re-approval**, not the `env_error` itself (on a box with no browser at all,
  selecting a transport changes the message, not the exit code; acquisition is
  F's job, or the adopter's).

## Consequences

**Becomes easier:**
- Adopting design-eval without a mandatory ~150 MB download — reuse an existing
  Chrome.
- Investigating a fidelity-score shift: the ledger now says which engine and
  version produced each run.
- Onboarding: the failing machine itself prints a precise, environment-aware
  instruction instead of an opaque `node/playwright unavailable`; an author who
  opts in can have the browser installed with consent.

**Becomes harder:**
- The scoring path (`score.py`/`capture.mjs`) grows a preflight probe; the
  authoring path grows an opt-in detect-ask-install verb. Keeping the ask out of
  `init`/`install` is a constraint the spec must honor (they stay
  non-interactive).
- The `config.json` schema and its freeze/validation grow a `capture` block;
  existing frozen configs predate it and need a back-compat story (a missing
  block ⇒ assume bundled, warn, do not refuse — to be settled in the spec).
- Adopters on the BYO transport carry real, unpoliced engine drift. That is a
  deliberate trade, and the docs must say so plainly rather than implying the
  freeze protects them.
- "servo depends on nothing" becomes "servo depends on nothing it ships, but
  design-eval's runtime requires a JS browser library the adopter provides."

## Assumptions

- **`capture.mjs` hard-imports Playwright and there is no preflight today.**
  Verified by read: `skills/design-eval/capture.mjs:11`
  (`import { chromium } from 'playwright'`) and the sole handling at
  `skills/design-eval/score.py:106` (`node/playwright unavailable for capture`).
  No detection/install code exists in the skill.
- **The freeze model deliberately excludes environmental fields, and
  `validate_freeze` never probes the environment.** Verified by read:
  `definition_hash`'s docstring (`skills/_common/fidelity_eval.py`) excludes
  "anything *environmental* (e.g. design-eval's `app_url`) … pinning it would
  force a re-freeze + re-approval on an environment move"; `validate_freeze`
  compares `definition_hash(config)` to the stored `approved_content_hash` plus
  on-disk artifact hashes only. This grounds the rejection of Option E.
- **Browser version is recorded nowhere today** — absent from `definition_hash`'s
  definition dict and from the ledger writer. This is the observability gap the
  ADR closes.
- **`config`-driven transport dispatch is an established pattern** — but the
  precedent is cited for *mechanism*, not for freeze placement. `score.py` reads
  `judge.transport` from config (`score.py:119-124`); note that `judge` is hashed
  whole (`fidelity_eval.py:87`), so `judge.transport` *is* frozen today. This ADR
  does **not** treat that as validation: `judge.transport` routes to the same
  pinned `judge.model` (the evaluator is invariant), whereas `capture.transport`
  selects a different rendering engine. See Open questions — the frozen
  `judge.transport` looks like a latent wart with the same re-freeze-on-env-move
  shape, and is out of scope here.
- **`app_url` is the correct precedent, and it is exact.** Verified: `app_url`
  lives in `templates/config.example.json:4` and is named in `definition_hash`'s
  docstring as the example of an excluded environmental field. The `capture`
  block mirrors it — present in config, read at runtime, out of the hash.
- **Freezing transport would buy no engine consistency.** Verified:
  `_CASE_FILE_FIELDS = ("reference", "setup")` means reference PNGs are
  content-hashed at freeze, so the reference engine is fixed in bytes at
  `capture-refs` time regardless of the scoring transport. Reference-vs-app
  engine mixing is inherent to the design and is not something a frozen
  transport could prevent.
- **An unfrozen environmental escape hatch is established practice.** Verified:
  `SERVO_DESIGN_EVAL_CLAUDE_BIN` (`score.py:128-129`) overrides judge-binary
  resolution outside the freeze; `SERVO_DESIGN_EVAL_CAPTURE_TRANSPORT` mirrors it.
- **`install()` calls `init()` unconditionally.** Verified: `design_eval.py:148`
  (`init(target)  # ensure runtime is present`). This is why an interactive
  `init` would make `install` block on stdin, and why the consented-install (F)
  must live behind an explicit opt-in outside this path.
- **The reported gap is a message-quality problem at score time.** The failure is
  `EnvError("node/playwright unavailable for capture")` raised in `capture_app`
  (`score.py`), on the scoring machine — grounding the preflight (G) as the
  primary fix rather than authoring-time detection.
- **No programmatic ledger reader exists today.** Searched the tree for
  `ledger.jsonl`; the hits are writers (`fidelity_eval.py`, and the
  eval-authoring / spec-oracle equivalents), specs, ADRs, and tests. The ledger's
  consumer is a human, which the Recommended Decision now states outright.
- **Assumed, not verified (spike-gated):** that Playwright's `channel: 'chrome'`
  reliably drives a system Chrome across servo's target OS/versions, and that a
  trustworthy browser version string is cheaply obtainable for the ledger on the
  BYO path.
- **Explicitly NOT assumed:** that engine drift is a material contributor to
  fidelity-score noise. The frame-critique pointed out that the n-sample lower
  bound (`aggregate_lower_bound`) and plateau δ already absorb the judge's own
  sampling variance, which for a semantic judgment plausibly dominates
  rasterization differences. This ADR therefore does **not** rest on drift being
  material — it records identity for investigability, which is worthwhile either
  way.

## Kill criteria

- If a spike shows `channel: 'chrome'` / `-core` cannot reliably drive a system
  Chrome across servo's target environments, the BYO transport is not viable and
  the decision collapses toward Option A (bundled) — leaving only the ledger
  identity record, which remains independently worthwhile.
- If a trustworthy browser version string cannot be obtained on the BYO path,
  the ledger record is unreliable and should be omitted rather than misleading —
  which would leave the detect-and-ask acquisition mechanism as the ADR's only
  surviving contribution. That is still worth shipping (it closes the reported
  gap), but the ADR should be re-read at that point rather than assumed intact.
- If the adopter-facing `init` interaction proves to add more friction than the
  prose prerequisite it replaces (adopters routinely decline and end up worse
  off), prefer detect-and-instruct over detect-and-install.
- If measurement ever shows engine drift *does* dominate score noise, this
  decision is insufficient — but the answer is still not freeze-gating (Option E
  stays rejected); it would be same-engine enforcement at the *reference-render*
  boundary, which needs its own ADR.

## Open questions

- **Back-compat for existing frozen configs** without a `capture` block: assume
  bundled, warn, and do not refuse — confirm in the spec that this cannot
  silently change an existing adopter's behaviour.
- **Is engine drift material at all?** Worth a cheap experiment during the spec:
  score one fixed app/reference pair across two Chrome majors and compare the
  delta against the n-sample spread. If it is inside the noise the lower bound
  already absorbs, the ledger record is purely diagnostic — good to know before
  anyone argues for stronger enforcement.
- **Authoring vs scoring engine mixing is structural, not optional.** Because
  references are frozen as PNG bytes, the reference engine is whatever rendered
  them at `capture-refs` time, while the app is shot by the current transport.
  The spec should record the reference-render engine in the ledger too, so a
  mismatch is at least *visible*; forcing same-engine would mean re-rendering
  references per environment, which defeats freezing them at all.
- **Is the frozen `judge.transport` a latent wart?** It sits inside the hashed
  `judge` dict, so an adopter who freezes with `"api"` on a laptop and runs CI
  with only the `claude` CLI hits the same re-freeze-on-environment-move wall
  this ADR rejects for `capture.transport`. Out of scope here — flagged so it is
  examined on its own terms rather than inherited as precedent.
- **Puppeteer as an alternative library** — near-equivalent here; the spec should
  state whether to support both or standardize on one.
