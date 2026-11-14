---
slice: 043-01 — refuse known-USD-priced oracle components under Copilot
pass: craft
verdict: pass
reviewer: general-purpose
reviewed_at: 2026-11-14T01:41:02Z
prompt_source: review.py pr-review spec.md 043-01 loop.py test_usd_priced_oracle.py --non-interactive --richer-skill none
substrate: non-interactive
---

VERDICT: pass (round 1)

The slice adds a known-USD-priced oracle marker reader and a copilot-gated launch
refusal that faithfully mirror the ADR-0041 unpriced path, wired into `run_loop`
as the sole Copilot launch chokepoint. No blockers; strong, non-vacuous tests
(59 new). No 3.9 violations — the new code uses only `Optional[...]` + PEP 585
`tuple[str,str]`, no bare `X | None` at runtime.

Strengths:
- The copilot refusal message enumerates the offending component(s), cites
  "ADR-0048 part 5" and resolved OQ5, explains why the credit ceiling does not
  bound oracle USD spend, and offers two concrete remediations.
- Copilot-only gating is unambiguous: `_usd_priced_oracle_preflight`
  short-circuits `if host != HOST_COPILOT: return None` before touching the
  reader, with a safe `host=HOST_CLAUDE` default; reader is host-agnostic, policy
  lives in the caller.
- The claude sentinel test (asserts control reaches `_install_signal_handlers`)
  and the both-markers precedence test (`"usd_priced_components" not in err`) are
  well-targeted.

Nits (non-blocking, logged in the deviation log):
- Enforcement asymmetry: the unpriced guard re-checks mid-run at `_invoke_gate`;
  the usd_priced guard is launch-only, so a Copilot run that gains the marker
  mid-run is not re-caught. Deferred to the arch pass to confirm launch-only is
  the intended boundary (it did); a mid-run re-check needs `host` threaded through
  the host-blind gate stack. Recorded as a follow-up.
- Deliberate verbatim validator duplication between the two readers (+ heartbeat
  mirror); maintenance cost accepted for byte-consistency + distinct messages.
- Cosmetic `cost_ceiling_usd` default shown in Copilot refusal summaries
  (inherited from `_unpriced_oracle_preflight`).
- One mildly-vacuous `test_invalid_target_defers_to_other_preflight` (inherited
  parity weakness from the sibling test); every other test is non-vacuous.

Recommend REVIEWED.
