---
status: DRAFT
dependencies: [adr-0031]
last_verified:
frame_review: true
---

## Slice 026-01 — runtime-preflight-guidance

**Goal:** Make the machine that actually fails say what to do about it — for the
two failure modes that are *cheaply* detectable before launch (node missing,
browser library missing), plus fix the stderr surfacing that currently hides the
remedy for everything else.

**DoR:**
- ✅ [ADR-0031](../../decisions/adr-0031-design-eval-browser-acquisition.md)
  Accepted; this is its Option G.
- ✅ **Failure taxonomy corrected and probe-grounded** (the first frame-critique
  found the original premise wrong). Verified by running the real shapes:
  | failure | branch in `score.py:103-111` | what the adopter sees today |
  |---|---|---|
  | `node` binary absent | `FileNotFoundError` → `EnvError("node/playwright unavailable…")` | the only case that message covers |
  | **library absent** | node starts, **rc 1** → `EnvError("capture failed …: {stderr[:200]}")` | `node:internal/modules/package_json_reader:256 / throw new ERR_MODULE_NOT_FOUND…` — node internals |
  | browser binary absent | node starts, rc≠0 → same branch | Playwright's launch error, head-truncated |
  | app down / selector / setup throw / timeout | node starts, rc≠0 → same branch | head-truncated |
  Probe: a script doing `import { chromium } from 'playwright'` with the library
  absent returns **rc 1, not `FileNotFoundError`**, and `stderr[:200]` is
  entirely node-internals preamble.
- ✅ **`stderr[:200]` is a *head* truncation** (`score.py:111`), so when a tool's
  own remedy text appears later in the message it is cut away.
- ✅ **Fake-scores bypass located:** `score()` skips `capture_app` entirely when
  `SERVO_DESIGN_EVAL_FAKE_SCORES` is set. The preflight must sit inside the
  live-capture arm or every offline/CI run breaks.

**Acceptance criteria:**
1. Before the first capture, `score.py` probes: (a) `shutil.which("node")`;
   (b) library resolvability via a single `node -e "require.resolve('<specifier>')"`
   spawn. **The probe fails OPEN:** it reports "library absent" *only* when the
   probe's stderr carries the `MODULE_NOT_FOUND` token (probe-confirmed). On any
   other non-zero exit or unrecognised stderr it proceeds to capture and lets
   capture's error be authoritative — because `-e` runs as CommonJS and an
   environment such as `NODE_OPTIONS=--input-type=module` would make `require`
   undefined, which must not be misreported as a missing library on a machine
   where capture would have succeeded.
2. The preflight **performs no browser launch** and adds **at most one extra
   node spawn per run** — and none at all when (a) already failed. (Falsifiable
   restatement of "cheap".)
3. **Browser-binary presence is explicitly NOT preflighted** — detecting it needs
   a real Playwright import or launch, which would cost every success run or turn
   a working-but-slow environment into rc 2. It is covered by AC4 instead.
4. `capture_app`'s error surfacing changes from `stderr[:200]` (a blind head
   slice) to **salient-line selection**: drop stack frames (`^\s+at `), node
   internals (`^node:internal/`), the caret line, the trailing `Node.js vX.Y.Z`
   banner, and the `{ code: … }` object; keep the survivors (first 2 + last 2 if
   over budget) under a character cap. **Grounded, not assumed** — a tail slice
   was probed and rejected: for the library-absent case the cause
   (`Cannot find package 'playwright'`) sits at line 4 of 18, the last non-empty
   line is `Node.js v22.16.0`, and `stderr[-200:]` yields stack frames plus the
   version banner — strictly worse than today's head. The filter above was probed
   against the same output and returns exactly the cause line with no noise.
5. The preflight runs **only** in the live-capture path: with
   `SERVO_DESIGN_EVAL_FAKE_SCORES` set, scoring still succeeds with node absent.
6. Contract unchanged: failures stay `EnvError` → rc 2, stdout empty. The
   preflight introduces **no new failing case** — guaranteed by AC1's fail-open
   rule, not merely asserted: the only conditions that halt are node-absent and a
   token-confirmed missing library, both of which would have failed at capture
   anyway. Every ambiguous probe outcome proceeds to capture.
7. Non-interactive: never prompts, never reads stdin, never installs.

**DoD:**
- [ ] Preflight implemented inside the live-capture arm of `score()`.
- [ ] Tests: node-missing, library-missing, all-clear, and **fake-scores-with-node-absent still passes** (AC5 regression guard).
- [ ] Test: stdout empty + rc 2 on every preflight failure.
- [ ] Test: the salient-line filter, run against a **recorded real** node
      `ERR_MODULE_NOT_FOUND` stderr fixture (not a hand-written one with the
      remedy conveniently last), returns the cause line and drops the banner,
      caret, `code:` object and `at` frames.
- [ ] Test: an ambiguous probe failure (non-zero exit **without** a
      `MODULE_NOT_FOUND` token) does **not** halt — capture still runs (AC1/AC6
      fail-open guard).
- [ ] Test asserts no browser launch occurs during preflight (AC2/AC3).
- [ ] `SKILL.md` Prerequisites references the runtime guidance.
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Out of scope (stated, not implied):** transport awareness (026-02 owns it — this
slice probes today's single bundled specifier, preserving its "no config surface"
verticality claim); app-down / selector / timeout failures, which no pre-launch
probe can detect and which AC4 improves only by surfacing.

**Inherited obligation for 026-02 (so it is a handoff, not a discovery):** this
slice hardcodes the probe specifier `'playwright'`. When 026-02 changes what
`capture.mjs` imports/launches (e.g. `playwright-core` + `channel:'chrome'`), it
**must** update the preflight specifier alongside it — or derive it from the
resolved transport — otherwise the preflight demands a package the chosen
transport does not need (a new false failure) or passes while the real import
fails.

**Vertical?** Yes — an adopter whose run fails gets an actionable remedy at the
point of failure, with no config surface and no dependency on later slices.
