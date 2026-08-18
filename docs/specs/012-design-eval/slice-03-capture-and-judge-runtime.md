---
status: DONE
dependencies: [adr-0009]
last_verified: 2026-08-18
---

## Slice 012-03 — capture-and-judge-runtime

**Goal:** Ship the runtime halves — `capture.mjs` (Playwright reference and
app screenshots, device-chrome cropped, seeded to deterministic state) and
`score.py`'s vision judge (pinned model, n-sampled, JSON-extracted) — so the
frozen definition from 012-01/02 can actually produce a score.

**DoR:**
- ✅ **The spike de-risked the five hard problems** (device chrome,
  deterministic state, app↔ref state match, composed mockups, rubric scope) —
  [spike-findings.md](spike-findings.md).
- ✅ **012-01's honesty rules are in place**, so every runtime failure mode
  here has a defined `env_error` landing spot rather than a silent `0.0`.

**Acceptance criteria** (spec ACs 4, 5):
1. `capture_app(base_dir, screen)` invokes `capture.mjs --screen <id>`, which
   runs the screen's `setup` to seed deterministic state before shooting (the
   app is now-dependent). The seeding lives in `capture.mjs`; `capture_app` is
   the Python side that drives it and maps its failures to `EnvError`.
2. References crop device chrome (`computeClip` in `capture_lib.mjs`) so
   app-vs-reference is a like-for-like comparison.
3. `judge(app_png, ref_png, config)` dispatches on `judge.transport` and samples
   the pinned vision model; the per-screen `n`× loop lives in `score()`.
   `_extract_json` tolerates prose-wrapped replies.
4. Fail-closed honesty on both transports → `EnvError` (rc 2), never a silent
   `0.0`. The **`api`** transport retries bounded (`_post_with_retry`, 3
   attempts, 4xx surfaced immediately); the **`cli`** transport (`_judge_cli`)
   has no retry and fails closed on the first subprocess/parse failure.
5. Each run appends sampled + aggregated scores + hashes to `ledger.jsonl`
   (best-effort: a disk failure on the ledger write is swallowed, not fatal).

**DoD:**
- [x] `capture.mjs` + `capture_lib.mjs` + `capture_app` / `judge` /
      `_judge_api` / `_judge_cli` / `_post_with_retry` / `_extract_json` /
      `_ledger` implemented.
- [x] 24 unit/node tests green — `JudgeParseTests` (5, api reply-parsing),
      `JudgeCliTransportTests` (6, the cli transport), `CaptureAppHonestyTests`
      (3, capture failure paths), and `test_capture_lib.mjs` (10 node tests on
      the extracted pure helpers, bridged into pytest, skipped where node is
      absent).
- [x] Exercised live end-to-end during the original build.
- [x] Compliance + craft review verdicts recorded under `reviews/`.
- [x] Reconciliation verdict + deviation log + reconciliation sweep recorded.

### Retro-reconciliation note (2026-08-18)

Retro-recorded with [012-01](slice-01-freeze-and-aggregation-core.md). The
original `spec.md` table flagged this slice as *"BUILT (runtime; exercised live
in the loop, not unit-tested)"*, and the first retro-record called
`capture.mjs` entirely uncovered. **That headline is no longer accurate** — and
correcting it is the point of this pass:

- The **pure geometry** (chrome-crop clip math, flag/screen/viewport
  resolution) was extracted into `capture_lib.mjs`, which `capture.mjs` imports,
  and now has 10 node tests (including the degenerate null-box and
  crop-exceeds-box cases a craft review asked for). A tripwire fails if
  `capture.mjs` re-inlines the geometry.
- The **`cli` judge transport** (`_resolve_claude` / `_judge_cli`), which the
  original spec text omitted entirely (api-only), is now both **documented in
  `SKILL.md`** and covered by `JudgeCliTransportTests` (happy path, clamp,
  non-zero rc, `is_error` envelope, unparseable reply, missing binary).
- The honest **residual** gap is now narrow: the *browser body* of
  `capture.mjs` (Playwright `goto`/`setup`-dispatch/`screenshot`) is still
  verified only by hand, because it cannot run without a browser servo does not
  ship. See the deviation log for the two robustness follow-ups this pass left
  open (silent-optional `setup`; the `1600×1600` reference-render constant).

### Deviation log

- **Retro-lifecycle, not a build deviation** (see 012-01's log).
- **AC re-wording (record fix):** AC1 no longer attributes `setup`-seeding to
  `capture_app` (it is `capture.mjs`); AC4 now distinguishes the `api`
  transport's bounded retry from the `cli` transport's fail-on-first.
- **`capture_lib.mjs` extraction (structure change, behavior-preserving):**
  pure helpers pulled out of `capture.mjs` for testability; `capture.mjs`
  imports them. Not part of the freeze hash. `computeClip` gained named-error
  guards for the null-box and crop-exceeds-box cases.
- **`capture.mjs` browser-leak fix:** `fail()` now throws (routing through the
  `finally { browser.close() }`) instead of `process.exit(2)`, which had
  skipped browser teardown.
- **Left open (recorded in `docs/refinement-todo.md`):** (1) `capture.mjs`
  makes per-screen `setup` silently optional — a screen with no `setup`
  captures unseeded, now-dependent state with no error; freeze does not require
  one. (2) the `1600×1600` reference-render viewport is the one geometry
  constant not in config or `capture_lib.mjs`. Both are latent robustness
  gaps in shipped runtime, deferred rather than expanded into this pass.

### Reconciliation sweep

| Artifact | Disposition |
|---|---|
| `skills/design-eval/capture.mjs` (browser body) | Verified by read; browser-leak fixed; body itself remains browser-only, hand-verified (disclosed residual). |
| `skills/design-eval/capture_lib.mjs` (pure helpers) | Extracted + guarded; 10 node tests. |
| `skills/design-eval/score.py` (judge/`_judge_cli`/`_ledger`) | Verified against AC3–5; `cli` transport now tested; SKILL.md documents it. |
| `test_capture_lib.mjs` + `JudgeCliTransportTests` + `CaptureAppHonestyTests` | 21 tests green (node bridge skips where node absent). |
| Reviews (`reviews/slice-03-{compliance,craft}.md`) | compliance re-pass after AC reword + cli coverage; craft pass. |
