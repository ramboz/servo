---
status: DONE
kind: feature
dependencies: [adr-0041, adr-0048, 041-02]
last_verified: 2026-11-13
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
slice makes that already-decided policy enforceable **for a marked component**:
it adds the `usd_priced_components` marker protocol (reader + validator) and
refuses a marked component at the Copilot launch gate, extending ADR-0041's
unpriced refusal to the known-priced case. (For an *unmarked* component the
policy is no more enforced than before — see `## Scope and framing` and A1.)

**Scope and framing (settled at the frame-critique).** This slice ships the
enforcement half — loop.py *reads* the marker and refuses — and arms it ahead
of an auto-registrar. The marker's *writer* is a sequenced follow-up (see
`## Decisions needed`): today the marker is set by an explicit registration or
a hand-edit of `.servo/install.json`, the same narrow-but-legitimate writer
ADR-0041's marker protocol already relies on (ADR-0041 clause 5 — the marker is
a project-owned accounting record, not a security boundary). servo authors no
USD-priced oracle component yet, so there is no auto-producer to mirror
`register_manifest(..., unpriced=True)` here; when such a component is built it
will self-declare its USD pricing, exactly as native judges self-declare
`unpriced`. The guard closes the **marked** USD-priced case under Copilot; an
*unmarked* project-owned `oracle.sh` that calls a paid API is ADR-0041
clause 5's acknowledged residual (no marker-based guard can see it), not closed
here. So this enforces the accepted policy for the case the marker protocol can
reach — it does not claim to catch every conceivable paid oracle.

**DoR:**
- ADR-0048 is Accepted (2026-11-11); part 5 + OQ5 decide the policy (refuse; no
  separate USD oracle ceiling). ✓
- ADR-0041 (unpriced oracles refuse USD execution) is Accepted — the parent
  rule this extends. ✓
- Spec 041-02 is DONE — the Copilot launch gate and the `_unpriced_oracle_error`
  guard this slice extends already ship.

**Acceptance Criteria:**

1. An install-metadata marker records that an oracle component is known to spend
   USD. `.servo/install.json` carries a `usd_priced_components` marker listing
   each oracle component that bills in USD (e.g. an API-priced eval judge),
   validated like ADR-0041's `unpriced_components`. The marker's shape and its
   writer are settled in `## Decisions needed` (the array shape; reader+refusal
   shipped here, auto-writer a named follow-up).
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

**Anti-horizontal-phasing check:** a Copilot target whose `.servo/install.json`
marks an oracle component `usd_priced` (set by an explicit registration or a
hand-edit — the marker's legitimate writer today) is pointed at under `--host
copilot`, and servo refuses at launch with a reason naming the component — the
marker→refusal path ADR-0048 part 5 forbids is enforced end to end, not merely
detected. The vertical slice here is *enforcement* (marker present → refused),
which is complete and tested. What is deferred is the marker's *auto-writer*
(detecting USD pricing at install time) — a producer-side convenience, named as
a follow-up; its absence does not make this enforcement path horizontal, because
the marker has a working writer (explicit/hand) and the refusal fires end to end
from it. (If instead this slice shipped only *detection* of a USD-priced
component without the refusal, that would be the horizontal failure — it does
not.)

## Decisions needed

- **The `usd_priced` install-metadata marker shape — SETTLED.** A parallel
  array `usd_priced_components: [names]` in `.servo/install.json`, validated
  exactly like ADR-0041's `unpriced_components` (a unique list of nonempty
  names, a subset of the registered `components`; a malformed marker fails
  closed). Chosen over a per-component boolean or a `cost: {unit: …}` enum
  because it is byte-consistent with the proven `unpriced_components` precedent,
  keeps the manifest protocol small (ADR-0041 clause 6), and makes the two
  refusals trivially separable (AC5). Not ADR-shaped: an install-metadata schema
  detail inside ADR-0041 / ADR-0048, not a new load-bearing decision.
- **Who sets the marker — SETTLED (scope boundary).** This slice ships the
  **reader + refusal** only. The marker's writer today is an **explicit
  registration or a hand-edit** of `.servo/install.json` — a narrow but
  legitimate writer, the same surface ADR-0041's marker is set through. The
  **auto-writer** is a named follow-up (`docs/refinement-todo.md`): a
  `register_manifest(..., usd_priced=True)` knob mirroring the existing
  `unpriced` knob, called by a future self-declaring USD-priced component.
  Deliberately deferred to keep this slice bounded to `loop.py` (adding the knob
  would pull in a second vendored skill, `skills/_common/fidelity_eval.py`, and
  its host copies, for a producer with no servo caller yet). There is **no**
  automatic USD-pricing *detector* (ADR-0041 Option B rejected scanning
  `oracle.sh`); USD pricing is only ever an explicit self-declaration, never
  inferred — so the deferred writer is a registration knob, not a detector.
- **Whether an "approved USD oracle ceiling" path exists at all.** OQ5 is
  resolved as *keep refusing*, with no separate ceiling approved. AC2 is worded
  to let a future approved ceiling suppress the refusal, but this slice ships
  **pure refusal** (no ceiling flag). If a target later needs the ceiling, that
  is a new owner decision (ADR-0048 OQ5, "revisit if a target needs one"), out
  of scope here.

## Assumptions

- **A1 (known-USD-priced is a real, markable, reachable case) — tested by the
  frame-critique; resolved by re-scoping, not by claiming an auto-producer.**
  The marker partition is real: `.servo/install.json` already carries
  `unpriced_components`, and this slice adds the parallel `usd_priced_components`
  key with the same validator, so a USD-priced component *can* be identified in
  install metadata distinctly from an unknown-cost one. The frame-critique
  grounded the *reachability* half against the codebase and found it currently
  false for any **automatic** path: `register_manifest` (skills/_common/
  fidelity_eval.py) exposes only an `unpriced` knob and writes only
  `unpriced_components`; every native judge (design-eval, content-fidelity,
  eval-authoring) registers `unpriced=True` (native judges cannot supply a USD
  conversion — ADR-0041 Context), so servo ships **no** USD-priced component and
  **no** writer for the new marker, and scaffold-init has no USD-pricing signal
  to key on (ADR-0041 Option B rejected scanning `oracle.sh`). The honest
  resolution is a re-scope, not a false claim: the marker's writer today is an
  **explicit registration / hand-edit** (a narrow but legitimate writer — the
  same surface ADR-0041's marker is edited through), and the slice ships the
  **enforcement** (reader + refusal), arming the accepted ADR-0048 part 5 policy
  so a marked component is refused the instant one exists. The **auto-writer**
  (a `register_manifest(..., usd_priced=True)` knob that a future
  self-declaring USD-priced component calls, mirroring the `unpriced` knob) is a
  named, sequenced follow-up (`## Decisions needed` + `docs/refinement-todo.md`),
  not a silent gap. This borrows ADR-0041's guard/registrar *split* (the guard,
  slice 034-08, and component registration, slices 034-05/06, were separate
  slices) — but, honestly, without ADR-0041's concurrent producer: ADR-0041
  shipped `register_manifest(unpriced=True)` and real marked native judges
  *alongside* its guard, so that guard protected a populated configuration on day
  one, whereas this slice ships the guard **ahead of** any USD-priced component
  (none exists) and any auto-writer. The frame is sound because the guard's only
  producer today — a hand-edit / explicit registration — is first-class (ADR-0041
  clause 5: the marker is project-owned, like `oracle.sh`; ADR-0041 Option B
  rejected auto-detecting price), the refusal fires end to end from it, and the
  misdirection cost if no USD-priced component is ever built is small and
  terminal (a leaf reader+refusal, no downstream slice depends on it). The slice
  is at worst slightly *early*, not misframed — and its prose no longer claims a
  producer exists.

### Deviation log (after reconciliation)

The five ACs above are preserved as authored; the frame-critique refined the
*framing* (Goal / Scope / A1 / Anti-horizontal-phasing check), not the ACs.

Review rounds:
- **Round 1:** **frame-critique NEEDS-CHANGES** — one `[blocker]` on A1 as
  realized. Grounded against the codebase: `usd_priced_components` had a reader
  but **no producer** — `register_manifest` (skills/_common/fidelity_eval.py)
  exposes only an `unpriced` knob, every native judge self-marks `unpriced`
  (native judges cannot supply a USD conversion — ADR-0041 Context), so servo
  ships no USD-priced component and no auto-writer, and scaffold-init has no
  USD-pricing signal (ADR-0041 Option B rejected scanning `oracle.sh`). As
  framed, the slice shipped a refusal nothing servo produces could trigger, and
  the Goal / Anti-horizontal-phasing prose over-claimed ("closes the one real
  safety hole end to end").
- **Round 2:** **frame-critique PASS** after the re-scope below; **compliance
  PASS**, **craft PASS**, **arch PASS** (each with non-blocking nits, folded
  here); **reconciliation PASS**.

Frame-critique fix (R1 → R2) — honest re-scope, the reviewer's option (b), not a
false producer claim:
- The slice now ships the **enforcement half** (reader + copilot-gated refusal)
  and states plainly that the marker's **writer** today is an explicit
  registration / hand-edit — a narrow but legitimate writer, the same
  project-owned surface ADR-0041 clause 5 relies on — with the **auto-writer** a
  named, sequenced follow-up (`docs/refinement-todo.md`). The Goal, `## Scope and
  framing`, A1 and the Anti-horizontal-phasing check were rewritten to say this:
  the guard is armed **ahead of** any USD-priced component (none exists), closes
  only the **marked** case, and leaves an *unmarked* project-owned `oracle.sh`
  that calls a paid API as ADR-0041 clause 5's acknowledged residual (the marker
  is an accounting record, not a security boundary). This is a complete vertical
  (marker → refusal, tested end to end), not horizontal detect-without-act.

Load-bearing choices made during implementation:

1. **Host-keyed discriminator, not `cost_ceiling`-keyed.** The refusal fires on
   `host == HOST_COPILOT`, not on `cost_ceiling is None`. Verified by the arch
   pass: under `--host copilot` `--cost-ceiling` is a hard parser error, so
   `cost_ceiling` is always None there; but a `--host claude` run that omits
   `--cost-ceiling` *also* reaches the gate with `cost_ceiling` None (it is
   defaulted to the USD default only later), so a ceiling-keyed discriminator
   would false-refuse an ordinary claude run and regress AC4. Host-keying is the
   only correct choice.
2. **`run_loop` is the sole enforcement site (launch gate).** Copilot forces the
   loop driver; `--driver goal` / `--background` are refused earlier and
   `--emit-routine-prompt` runs no oracle, so `main → run_loop` and direct
   programmatic entry both funnel through this one gate (arch-confirmed: campaign
   dispatch launches `loop.py` subprocesses that re-enter here, and
   `_invoke_copilot` has no caller outside `run_loop`'s iteration).
3. **Marker shape `usd_priced_components: [names]`**, a parallel array to
   `unpriced_components` with the identical validator — chosen for
   byte-consistency with the proven ADR-0041 precedent and trivially separable
   refusals (AC5). See `## Decisions needed`.
4. **Reader / policy split.** `_usd_priced_oracle_error` is a host-agnostic pure
   reader; `_usd_priced_oracle_preflight` owns the "when it bites" policy
   (copilot-only), reusing `_refuse_preflight` for the summary + rc. A no-op
   under claude even for a malformed marker: the unbounded-USD hazard exists only
   with no USD bound, so the copilot gate is the honest scope for the whole check.
5. **Ordering.** The usd_priced check runs *after* the host-agnostic unpriced
   preflight (ADR-0041's stricter unknown-cost rule wins when both markers are
   present — AC5) and *after* the credit-ceiling capability gate (a Copilot run
   with no credit ceiling is already refused `native_capability_unavailable`; the
   usd_priced reason surfaces on the normal Copilot launch, which supplies a
   credit ceiling — compliance pass's benign-ordering note; no USD hole either
   way).

Nits folded (compliance / craft / arch / frame):
- **run_loop comment corrected** — `--emit-routine-prompt` is a no-op early
  return under Copilot, not a refusal; the comment now says "runs no oracle".
- **Headline prose brought down to the Scope paragraph's precision** — the Goal
  now says "enforceable **for a marked component**", and A1's ADR-0041 analogy is
  corrected to "ADR-0041's guard/registrar split, without its concurrent
  producer" (ADR-0041 shipped its auto-producer and real marked components
  alongside its guard; this slice ships the guard ahead of both).
- **`--cost-ceiling 0` test comment corrected** — `0` is the disable sentinel,
  not a `$0` bound; the case now documents that it proves host-keying (claude
  never triggers the copilot refusal) and flags the claude-side bounding question
  as out of scope.

Conscious scope choices (noted, not changed):
- **Launch-only enforcement vs the unpriced guard's mid-run `_invoke_gate`
  re-check.** The unpriced guard (host-agnostic) also runs at the per-iteration
  gate to catch a mid-run install/re-freeze; the usd_priced guard is launch-only.
  A Copilot run that gains a `usd_priced_components` marker *mid-run* is not
  re-caught. This matches the ACs ("refuses to **launch**") and the frame-critique
  scope, and a copilot-specific mid-run re-check would need `host` threaded
  through the host-blind `_invoke_gate` stack. Recorded as a follow-up
  (`docs/refinement-todo.md`), not shipped here. (gate.py cannot own it: it is
  host-blind, and the refusal is copilot-specific.)
- **Validator duplication.** `_usd_priced_oracle_error` copies
  `_unpriced_oracle_error`'s list/nonempty/unique/subset validation verbatim.
  Deliberate (AC5 requires `_unpriced_oracle_error` *unchanged* + distinct
  messages, so a shared core cannot subsume it without touching it). ADR-0041
  clause 6 sets the extraction bar at a third client; the validator now spans 2
  functions × 4 trees = 8 copies, so a third marker or any validator fix should
  trigger extraction of a shared `_oracle_marker_error` core. Follow-up recorded.
- **Cosmetic `cost_ceiling_usd` in the Copilot refusal summary** shows the USD
  default (the preflight substitutes it when `cost_ceiling` is None) on a Copilot
  run that has no USD ceiling — inherited verbatim from `_unpriced_oracle_preflight`,
  not introduced here.

Deferred / documented follow-ups (`docs/refinement-todo.md`):
- **The marker's auto-writer** — a `register_manifest(..., usd_priced=True)` knob
  mirroring the `unpriced` knob, called by a future self-declaring USD-priced
  component (there is no price *detector*; USD pricing is only ever an explicit
  self-declaration).
- **Mid-run usd_priced re-check parity** with the unpriced guard (needs `host`
  threaded through `_invoke_gate`).
- **Shared validator extraction** when a third marker or a validator fix appears.
- **Claude `--cost-ceiling 0` + a (future) usd_priced oracle** — whether ADR-0005
  clause 6's "eval cost counts against the loop ceiling" bounds a USD-priced
  oracle when the cumulative ceiling is disabled; a future ADR-0005 revisit, out
  of this slice's (Copilot-only) scope.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `skills/agent-loop/loop.py` + 3 host copies | `updated` | New `REASON_USD_PRICED_ORACLE_COMPONENTS` / `REASON_USD_PRICED_COMPONENTS_INVALID`, `_usd_priced_oracle_error` (host-agnostic reader), `_usd_priced_oracle_preflight` (copilot-gated), and the `run_loop` launch gate. Byte-identical across the three host trees (`build_host_packages.py --check` green). |
| `skills/agent-loop/test_usd_priced_oracle.py` | `new` | TDD coverage (witnessed red → green) of all 5 ACs: marker protocol, copilot refusal (distinct reason, names components, cites ADR-0048 part 5, fail-closed rc), credit-ceiling independence, claude-unaffected, unpriced-unchanged + distinct. Source-only, not vendored (test files never ship to host packages). |
| `docs/specs/043-…/slice-01-…md` | `updated` | Frame-critique re-scope (Goal / Scope / A1 / Anti-horizontal-phasing / Decisions needed), this deviation log + sweep. |
| `docs/refinement-todo.md` | `updated` (at close-out) | Item 2 (known-USD-priced oracle under Copilot) marked **RESOLVED** by this slice; the four follow-ups above recorded. Written at close-out (same timing as the board row). |
| `docs/specs/README.md` (board) | `updated` | Regenerated by `status-board` at close-out, before DONE. |
| `docs/specs/043-…/reviews/slice-01-*` | `new` | The frame-critique / compliance / craft / arch / reconciliation verdicts, persisted by `review.py record-review`. |
| `skills/quality-gate/gate.py` | `no-op` | gate.py is host-blind; the usd_priced refusal is copilot-specific and lives only in loop.py's launch gate. gate.py's unpriced (host-agnostic) behavior is untouched. |
| `docs/architecture.md` | `no-op` | The gate.py `env_error` reason taxonomy is correctly unchanged (gate.py does not emit the new loop-only reasons); the Copilot section already references ADR-0048. Module boundaries preserved (arch pass). |
| `docs/decisions/adr-0041-*.md` / `adr-0048-*.md` | `no-op` | This slice enforces ADR-0048 part 5 + resolved OQ5 and extends ADR-0041; no ADR change (confirmed no new load-bearing decision). |
| `skills/_common/fidelity_eval.py` + copies | `no-op` | The marker writer is a deferred follow-up; this slice touches no producer. |

The branch also carries the spec-043 authoring commit (`e812b36`:
`slice-02-*`, `slice-03-*`, `spec.md`, `docs/specs/README.md`), from PR #62 —
out of this slice's implementation scope and not listed above; those files drop
from this branch's diff once #62 merges to main and this branch rebases onto it.
