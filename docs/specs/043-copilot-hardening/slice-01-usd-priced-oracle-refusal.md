---
status: DRAFT
kind: feature
dependencies: [adr-0041, adr-0048, 041-02]
last_verified:
arch_review: true
frame_review: true
---

## Slice 043-01 — refuse known-USD-priced oracle components under Copilot

**Goal:** Under `--host copilot`, refuse to launch when the target's oracle
carries a component that is **known to spend USD** (for example an API-priced
eval judge), enforcing ADR-0048 part 5 and its resolved Open Question 5 (no
separate USD oracle ceiling is approved). Today `loop.py`'s
`_unpriced_oracle_error` guard refuses only *unknown*-cost
(`unpriced_components`) components; a *known*-USD-priced component runs with
`cost_ceiling` null — no USD bound — which violates the accepted policy. This
slice closes the one real safety hole among the 041-02 follow-ups; it enforces a
policy ADR-0048 already decided, extending ADR-0041's unpriced refusal to the
known-priced case.

**DoR:**
- ADR-0048 is Accepted (2026-11-11); part 5 + OQ5 decide the policy (refuse; no
  separate USD oracle ceiling). ✓
- ADR-0041 (unpriced oracles refuse USD execution) is Accepted — the parent
  rule this extends. ✓
- Spec 041-02 is DONE — the Copilot launch gate and the `_unpriced_oracle_error`
  guard this slice extends already ship.

**Acceptance Criteria:**

1. An install-metadata marker records that an oracle component is known to spend
   USD. `.servo/install.json` gains a `usd_priced` marker on each oracle
   component that bills in USD (e.g. an API-priced eval judge). The marker's
   exact shape and who sets it are an open design point — see
   `## Decisions needed`.
2. Under `--host copilot`, `loop.py` refuses to launch, fail-closed (the same
   rc the existing launch-refusal uses), when the resolved oracle carries at
   least one `usd_priced` component and no approved USD oracle ceiling is in
   effect. The refusal reason names the offending component(s) and is a distinct
   reason string from the existing unpriced-oracle refusal, citing ADR-0048
   part 5.
3. The refusal is independent of the credit ceiling: a credit ceiling bounds
   only the worker's Copilot session (ADR-0048 part 5), never oracle USD spend,
   so a `usd_priced` component is refused whatever the credit ceiling's value.
4. A USD-budgeted run is unaffected: under `--host claude` with a non-null
   `cost_ceiling`, a `usd_priced` component is bounded by that USD ceiling as
   today and does **not** trigger this refusal. The new refusal fires only in
   the no-USD-bound case (Copilot, `cost_ceiling` null).
5. The existing `_unpriced_oracle_error` behavior for *unknown*-cost components
   is preserved unchanged: an unknown-cost component still refuses under its
   existing reason, and the two refusals are separately identifiable in output
   and tests.

**DoD:** ACs pass with tests (TDD, witnessed red); compliance + craft + arch
reviews (slice declares `arch_review: true`); frame-critique
(`frame_review: true`); host-sync gate green (loop.py vendored to the three host
trees); reconciliation sweep + deviation log; `docs/refinement-todo.md` item 2
marked resolved.

**Anti-horizontal-phasing check:** a user points servo at a Copilot target whose
oracle includes an API-priced judge, and servo refuses at launch with a reason
naming the component — the unbounded-USD path ADR-0048 part 5 forbids is closed
end to end, not merely detected.

## Decisions needed

- **The `usd_priced` install-metadata marker shape.** ADR-0048 part 5 names the
  marker but not its shape. Open: where it lives in `.servo/install.json` (a
  per-component boolean `usd_priced: true`, a cost-unit enum
  `cost: {unit: usd|credit|unknown}`, or similar); who sets it (scaffold-init
  detection at Compile time, a manual install edit, or both); and how a
  component is *known* to be USD-priced (an explicit install marker only, or a
  detected signal). Recorded here, not decided — the slice's arch review and
  implementation settle it. Not ADR-shaped: an install-metadata schema detail
  inside ADR-0041 / ADR-0048, not a new load-bearing decision.
- **Whether an "approved USD oracle ceiling" path exists at all.** OQ5 is
  resolved as *keep refusing*, with no separate ceiling approved. AC2 is worded
  to let a future approved ceiling suppress the refusal, but this slice ships
  **pure refusal** (no ceiling flag). If a target later needs the ceiling, that
  is a new owner decision (ADR-0048 OQ5, "revisit if a target needs one"), out
  of scope here.

## Assumptions

- **A1 (known-USD-priced is a real, markable, reachable case).** A USD-spending
  oracle component can be identified in install metadata distinctly from an
  unknown-cost one, and known-USD-priced is a case a real Copilot target
  actually reaches. Partly grounded: `_unpriced_oracle_error` already partitions
  oracle components by known cost (it refuses the unknown ones), so a
  known/unknown partition exists. What is unverified — and what the
  frame-critique must test — is that *known-USD-priced under Copilot* is a
  populated, reachable configuration rather than a theoretical one; if it never
  occurs in practice, the marker adds a refusal nothing triggers.
