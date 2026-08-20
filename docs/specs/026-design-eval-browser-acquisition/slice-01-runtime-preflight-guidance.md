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
   (b) library resolvability via a single `node -e "require.resolve('playwright')"`
   spawn. Each failure yields a distinct `EnvError` naming the exact remedy.
2. The preflight **performs no browser launch** and adds **at most one extra
   node spawn per run** — and none at all when (a) already failed. (Falsifiable
   restatement of "cheap".)
3. **Browser-binary presence is explicitly NOT preflighted** — detecting it needs
   a real Playwright import or launch, which would cost every success run or turn
   a working-but-slow environment into rc 2. It is covered by AC4 instead.
4. `capture_app`'s error surfacing changes from `stderr[:200]` (head) to the
   **last non-empty line(s)**, so a tool's own remedy survives instead of node's
   preamble. This is what improves the modes a preflight cannot detect.
5. The preflight runs **only** in the live-capture path: with
   `SERVO_DESIGN_EVAL_FAKE_SCORES` set, scoring still succeeds with node absent.
6. Contract unchanged: failures stay `EnvError` → rc 2, stdout empty. The
   preflight introduces **no new failing case** — it only reclassifies failures
   that would have failed anyway, earlier and with a better message.
7. Non-interactive: never prompts, never reads stdin, never installs.

**DoD:**
- [ ] Preflight implemented inside the live-capture arm of `score()`.
- [ ] Tests: node-missing, library-missing, all-clear, and **fake-scores-with-node-absent still passes** (AC5 regression guard).
- [ ] Test: stdout empty + rc 2 on every preflight failure.
- [ ] Test: the new stderr surfacing shows a remedy line that `[:200]` would have cut.
- [ ] Test asserts no browser launch occurs during preflight (AC2/AC3).
- [ ] `SKILL.md` Prerequisites references the runtime guidance.
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

**Out of scope (stated, not implied):** transport awareness (026-02 owns it — this
slice hardcodes today's single bundled path, preserving its "no config surface"
verticality claim); app-down / selector / timeout failures, which no pre-launch
probe can detect and which AC4 improves only by surfacing.

**Vertical?** Yes — an adopter whose run fails gets an actionable remedy at the
point of failure, with no config surface and no dependency on later slices.
