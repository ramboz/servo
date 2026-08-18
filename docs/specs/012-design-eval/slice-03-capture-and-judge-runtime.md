---
status: IN_PROGRESS
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
1. `capture_app(base_dir, screen)` runs the per-screen `setup` to seed
   deterministic state before shooting (the app is now-dependent).
2. References crop device chrome so app-vs-reference is a like-for-like
   comparison.
3. `judge(app_png, ref_png, config)` samples the pinned vision model `n`×;
   `_extract_json` tolerates prose-wrapped replies.
4. Transport failures retry bounded (`_post_with_retry`), then raise
   `EnvError` (rc 2) — never a silent `0.0`.
5. Each run appends sampled + aggregated scores + hashes to `ledger.jsonl`.

**DoD:**
- [x] `capture.mjs` + `capture_app` / `judge` / `_judge_api` / `_judge_cli` /
      `_post_with_retry` / `_extract_json` / `_ledger` implemented.
- [x] 5 unit tests green — `JudgeParseTests` (reply-parsing + honesty paths).
- [x] Exercised live end-to-end during the original build.
- [ ] Compliance + craft review verdicts recorded under `reviews/`.
- [ ] Reconciliation verdict + deviation log + reconciliation sweep recorded.

### Retro-reconciliation note (2026-08-18)

Retro-recorded with [012-01](slice-01-freeze-and-aggregation-core.md). The
original `spec.md` table flagged this slice as *"BUILT (runtime; exercised live
in the loop, not unit-tested)"*. That is now only partly true: `JudgeParseTests`
covers reply parsing and the honesty paths, but **`capture.mjs` has no
automated coverage at all** — it is a Playwright-driven browser script verified
by hand. This is the single largest evidence gap in spec 012 and should be
stated plainly rather than smoothed over by the retro-record.

**Undocumented addition found during reconciliation:** `score.py` grew a second
judge transport — `_resolve_claude()` / `_judge_cli()`, routing through the
`claude` CLI when available instead of the Anthropic Messages API. The original
spec text describes only the API path. The behavior is real and shipped; it is
recorded here so the spec stops under-describing its own runtime.
