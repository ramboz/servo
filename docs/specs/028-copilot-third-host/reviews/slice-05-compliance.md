---
slice: 028-05 — execution-primitive-mapping
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-09-18T20:26:36Z
prompt_source: review.py (compliance+craft+arch pass)
---

Independent review (compliance + craft + arch) of slice 028-05 by a fresh
jig:reviewer, scrutinizing the normalized-result correctness, cost-honesty, and
goal-refusal. **VERDICT: PASS.** All 4 ACs met; the Copilot loop mode normalizes
JSONL+usage into the exact result-dict shape the loop body consumes (every
downstream key traced), the Claude default path is provably byte/behavior-
identical (pinned tests), the cost-honesty story is sound and loud (total_cost_usd
=0.0 no fabrication; USD ceiling honestly inert; --max-iterations always bounds;
loud per-iteration native-cost advisory), and the goal-family refusal is explicit,
first, and tested.

Four low-severity findings, disposition:
1. **[deferred → refinement-todo]** No hard-error-envelope guard: a *soft* Copilot
   failure emitting parseable JSONL is scored rather than env-erroring. Bounded/safe
   (oracle scores independently; max-iter + plateau bound; binary-absent/timeout
   already env-error). Needs a live Copilot error-envelope shape (uncapturable
   headlessly) → logged as a residual paired with the hook-firing/max-ai-credits
   live-validation cluster.
2. **[fixed]** `tempfile.mkstemp` sat outside the try/finally — an unwritable temp
   dir would raise into `run_loop` instead of returning `(None, breadcrumb)`.
   Wrapped in a guard that returns a breadcrumb (the one spot in the Copilot branch
   that could raise into the loop, now closed).
3. **[partially pinned]** Copilot invocation-failure paths were untested; added
   `test_copilot_not_on_path` (mirrors `test_claude_not_on_path`: empty bindir →
   rc=2 + `copilot not on PATH` breadcrumb). Timeout / no-parseable-event paths
   remain correct-by-inspection (fold into the follow-up polish if desired).
4. **[fixed]** Added a symmetric launch-time advisory under `--host copilot`
   (loop driver): warns once up front that the USD `--cost-ceiling` is inert and
   the loop is bounded by `--max-iterations` (+ `--max-ai-credits`), complementing
   the per-iteration advisory — so the cost model is clear before the first paid
   iteration.

Post-review changes re-verified: affected tests pass (incl. the new not-on-PATH
test), host packages regenerated (drift clean), lint clean, Claude path unchanged.
Safe to mark 028-05 REVIEWED → DONE.
