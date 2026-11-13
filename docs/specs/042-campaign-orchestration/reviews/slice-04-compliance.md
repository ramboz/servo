---
slice: 042-04 — host-driven verified-wrapped
pass: compliance
verdict: pass
reviewer: jig:reviewer
reviewed_at: 2026-11-13T05:43:11Z
prompt_source: review.py implementation docs/specs/042-campaign-orchestration/spec.md 042-04 skills/agent-loop/loop.py skills/heartbeat/campaign.py skills/agent-loop/test_loop.py skills/heartbeat/test_campaign.py skills/heartbeat/SKILL.md docs/architecture.md
---

VERDICT: pass (round 1)

All six ACs are implemented and backed by meaningful, non-vacuous tests over REAL
git worktrees (DoD "not a mock"):
- AC1: loop.py records a read-only content fingerprint (HEAD + `git diff HEAD
  --full-index` hash + untracked-content hash, bookkeeping excluded) plus
  start_head/allow_dirty/own-outcome at halt on both drivers.
- AC2/AC3/AC5: `_verify_wrapped` accepts `wrapped` iff run-state + fingerprint +
  base-sha (clean start) all hold; post-halt edits and commit-before-record are
  caught via the fingerprint/head.
- AC4: re-render from the loop's own state is proven by forwarding deliberately
  wrong values (result=blocked, cost=99.0, iters=999) and asserting the
  state-derived values win.
- AC6: verified wrapped cost is enforced (not self_reported); status states the
  subprocess-only boundary.

Vacuous-test check: passed. No design-principle violations, no new tech-debt
markers, no `## Tasks` section.

Issue (Medium, non-blocking, FIXED post-review): the `_status_summary` comment and
the `campaign status` credit-items line said a credit item's spend is "re-derived
in 042-04", but the slice records `cost_usd: null` and performs no re-derivation.
Corrected to "credit spend is in AI credits, bounded per-run by the 041-02 brake"
(matches architecture.md).

Reconciliation notes: the Copilot e2e DoD step ("an end-to-end wrapped run against
spec 041's brake") has no automated test (it needs a live Copilot host); the
USD/Claude wrapped path IS covered end-to-end. Logged as a documented e2e gap in
the deviation log.
