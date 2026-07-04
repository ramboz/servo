---
status: RECONCILED
dependencies: [016-02, 003-08, adr-0008, adr-0016]
last_verified: 2026-07-04
frame_review: true
---

## Slice 016-03 — clamp-and-review

**Goal:** Enforce **clamp-never-disable** on plan-sourced budget and let a
human review/adjust a plan before Run consumes it. A plan `budget` value that
requests the documented "disable this brake" sentinel is **clamped back to a
live default**, not honored as disabled (A1 — narrowed from a numeric
ceiling after frame-critique); `provenance: human_edited` plans become
consumable (superseding 016-02 AC7's blanket refusal) once clamped and
validated, free to *raise* any budget knob exactly like a CLI flag; and
recompiling a spec no longer silently overwrites a human's edit.

**DoR:**
- ✅ **016-02 DONE** — the plan-read seam (`_load_plan` / `_resolve_from_plan`)
  exists; this slice extends it rather than building it.
- ✅ **003-08 DONE** — the budget `DEFAULT_*` constants (spread across
  003-01/02/03/05) and the driver/background mechanics this slice must not
  disturb are stable.
- ✅ **ADR-0008 Accepted** — the guardrail-layer-is-retained decision this
  slice enforces against a plan.
- ✅ **ADR-0016 Accepted** — "a plan with no ceiling ... is clamped" (the
  disable-sentinel clause this slice implements) + the human review/approval
  posture (mirroring 006-04).
- ✅ Decision (scope): clamping/validation applies to **plan-sourced values
  only** — an explicit CLI flag is never clamped (A1/A3).
- ✅ Decision (exit contract): every new refusal is rc=2 with a structured
  stderr reason, matching 016-02's contract.

## Assumptions

- **A1 — "guardrail safe bound" = the disable-sentinel, not a numeric
  magnitude ceiling — per the
  [ADR-0016 amendment of 2026-07-04](../../decisions/adr-0016-execution-plan-artifact.md#amendments).**
  Two rounds of pre-implementation frame-critique on this slice surfaced a
  real ADR-level gap, not just a slice-authoring one: ADR-0016's Decision and
  Verification sections name **two** clamp triggers ("no ceiling, **or a
  ceiling above policy**"), but no numeric "policy ceiling" exists anywhere
  in `loop.py` — `DEFAULT_MAX_ITERATIONS` / `DEFAULT_COST_CEILING_USD` are
  documented CLI *defaults* ("per docs/architecture.md 'Project vs
  servo-core split'" — `skills/agent-loop/loop.py:87,90-95`), not a safety
  maximum anyone decided on (016-02's own A2: "no separate 'policy ceiling'
  exists in loop.py"), and a CLI flag can already exceed them uncapped today
  (`loop.py:3108-3119` only enforces lower bounds). Treating `DEFAULT_*` as
  that missing policy ceiling would have silently defeated this slice's own
  goal — a human raising a budget knob in review is the single most likely
  edit, and clamping it back to the out-of-the-box default makes "review and
  adjust" close to "review and be ignored." The amendment records this
  finding directly in ADR-0016 (not just here): the "no ceiling" clause
  ships as written (a plan may never request the documented `0` disable
  sentinel); the "ceiling above policy" clause is narrowed to mean exactly
  that disable-sentinel case, since no separate policy magnitude was ever
  defined. A plan value that *raises* a knob above `DEFAULT_*` is honored
  exactly like an explicit CLI flag. A genuine magnitude policy ceiling
  remains open for a future decision if a real need surfaces — it is not
  invented here. **Disclosed trade-off:** unlike a CLI flag (re-asserted per
  invocation), a `human_edited` plan is a persistent, reusable artifact — a
  raised value governs silently across every future run against that
  spec-id until the plan is recompiled/re-edited. This is a deliberate,
  disclosed choice, not an oversight (see the ADR-0016 amendment's
  "Disclosed trade-off" note); a re-approval/expiry policy is its own future
  decision if real use ever needs one.
- **A2 — "0 = disable" is the only case a plan-sourced value is clamped.**
  `--cost-ceiling 0`, `--context-fill-threshold 0`, and `--plateau-window 0`
  are documented (loop.py `--help` text) as "disable this brake" — literally
  "no ceiling" per ADR-0016. A plan (`compiled` or `human_edited`) requesting
  the disable sentinel on any of these three knobs is clamped **up** to that
  knob's `DEFAULT_*` (a brake re-enabled at its documented starting
  strength) rather than honored as disabled. `max_iterations` has no
  disable sentinel (argparse requires `>= 1`) and no numeric ceiling either
  (A1) — it is therefore **never** clamped; any plan-sourced value ≥ 1 is
  honored as-is.
- **A3 — only plan-sourced values are validated/clamped; CLI-flag values are
  untouched.** Consistent with 016-02's "plan value kept in a fresh local,
  never written into `args.*`" discipline (`_resolve_from_plan`'s docstring) —
  the clamp/validation helper reads `plan_budget` / `plan_driver` directly,
  never `args.*`. An explicit `--cost-ceiling 0` on the CLI still disables
  the brake exactly as today — A1/A2 apply to plan-sourced values only.
- **A4 — `execution_plan.py compile` gains its first flag.** No flag exists on
  the `compile` subcommand today (`skills/execution-planner/execution_plan.py`
  — `compile_p.add_argument` only defines `target` and `--spec`). `--force` is
  new surface; its exact name is a naming call, not load-bearing to the
  clamp/preserve mechanism itself.
- **A5 — a bare `provenance: "human_edited"` string is not a trustworthy edit
  signal; recompile-preserve must key on a content hash instead (added after
  frame-critique #3).** The first draft of AC4 refused recompile purely on
  `provenance == "human_edited"`. A frame pass caught the precedent this
  slice itself invokes (006-04, `docs/specs/006-spec-oracle/slice-04-freeze-and-controls.md:94-111`)
  does **not** trust a bare status string either — 006-04's own reconciliation
  found "a self-reported flag doesn't prove the content changed" and added
  `approved_content_hash` to close it. The same gap applies here: nothing
  sets/verifies `provenance`, so (a) a human who edits `budget`/`driver` but
  forgets to flip the field leaves `provenance: "compiled"` — a
  provenance-only check would silently let the next recompile clobber their
  edit, exactly the failure AC4 exists to prevent; (b) conversely a stale
  `human_edited` label with no real edit behind it would needlessly block a
  routine recompile, training people to reflexively pass `--force` and
  defeating the safeguard. **Resolution:** `compile_plan` stamps a
  `budget_hash` (sha256 of the canonical-JSON `{"budget": ..., "driver": ...}`
  — the two fields this slice's ACs and `loop.py` actually consume; the other
  referenced-not-copied fields per ADR-0016 are producer identity, not
  human-editable surface) at every compile. A subsequent `compile` recomputes
  the hash over the **existing on-disk plan's current** `budget`/`driver` and
  compares it to that plan's own recorded `budget_hash`: a mismatch means the
  content drifted since it was last (re)compiled — regardless of what
  `provenance` claims — and AC4 refuses on that, not on the label. The
  `provenance` field stays purely descriptive (what `loop.py`'s AC2 gate
  reads); it is no longer what recompile-safety depends on.
- **A6 — the clamp for `context_fill_threshold`/`plateau_window` is scoped to
  the loop driver, where those knobs are actually enforced (added after
  frame-critique #4).** AC1 clamps exactly the two knobs 016-02 AC3 already
  drops **entirely** under the goal driver (`context_fill_threshold` /
  `plateau_window` are "loop-only brakes" the `/goal` primitive doesn't
  support — `slice-02-run-consume.md` AC3; `loop.py`'s dispatch forwards them
  to `run_loop` only, never to `run_goal_loop`). A frame pass caught that
  clamping these two knobs *before* driver routing is decided would emit a
  "clamped `0` → `DEFAULT_*`" breadcrumb for a value that is about to be
  silently discarded under goal — a misleading "we protected you" message for
  a brake that was never going to be active. **Resolution:** the clamp for
  `context_fill_threshold` / `plateau_window` fires only on the branch that
  actually forwards them (`run_loop`, i.e. `effective_driver == loop`); under
  the goal driver they are dropped exactly as 016-02 AC3 already specifies —
  a plan-sourced disable-sentinel is simply one more value silently dropped,
  no different from any other plan-sourced value for those two knobs under
  goal, and no clamp breadcrumb fires. `cost_ceiling_usd`'s clamp is
  driver-independent (016-02 AC3: `cost_ceiling_usd` "still applies under
  goal") and fires unconditionally, before routing, same as today's
  resolution point.

**Acceptance Criteria:**

1. **Clamp-never-disable for plan-sourced budget, scoped to where each knob
   is enforced (A6).** For `cost_ceiling_usd`, when a plan supplies the
   disable sentinel `0`, the *effective* value used for the run is clamped
   **up** to `DEFAULT_COST_CEILING_USD` rather than honored as disabled —
   unconditionally, under either driver (A1/A2/A6, mirrors 016-02 AC3's
   "still applies under goal"). For `context_fill_threshold` and
   `plateau_window`, the same disable-sentinel clamp fires **only when the
   effective driver is `loop`** (the branch that actually forwards them to
   `run_loop`); under the goal driver they are dropped exactly as 016-02 AC3
   already specifies, clamp or not, and **no** clamp breadcrumb is emitted
   for them in that case (A6). `max_iterations` is never clamped (A2 — no
   disable sentinel, no numeric ceiling). A plan value that *raises* any
   knob above `DEFAULT_*` is honored as-is, exactly like an explicit CLI
   flag — this slice does **not** cap plan-sourced values from above. An
   explicit CLI flag is **never** clamped, including `--cost-ceiling 0` (A3).
   The clamped value is what persists to `state.json` (`loop.py:1650`) on
   the loop-driver path, and a stderr breadcrumb names each knob actually
   clamped (`0` → the `DEFAULT_*` it was clamped to). *Test:*
   `PlanClampTests`.
2. **`human_edited` plans become consumable (016-02 AC7 superseded).**
   `_load_plan`'s provenance gate now accepts
   `provenance ∈ {"compiled", "human_edited"}`; only a plan with any *other*
   provenance value still refuses with `plan_requires_clamp` (the existing
   reason, now meaning "unrecognized provenance" rather than "any
   non-compiled provenance"). A `human_edited` plan's budget goes through the
   same clamp (AC1) and validation (AC3) as a `compiled` plan before being
   consumed — no separate code path. *Test:* `PlanHumanEditedConsumableTests`
   (rewrites `PlanHumanEditedDeferredTests.test_human_edited_plan_refuses_pending_clamp`;
   `test_unknown_provenance_refuses` for `provenance: "mystery"` is retained
   unchanged).
3. **Fail-closed plan-value validation precedes clamping.** A plan-sourced
   budget value of the wrong type (not the numeric type the equivalent CLI
   flag's `type=` would produce), or a value that argparse's own flag-shape
   check would reject for the equivalent CLI flag (negative `max_iterations`,
   `cost_ceiling`/`plateau_noise_floor` below 0, `context_fill_threshold`
   outside `[0.0, 1.0]`) refuses with exit `2` and a new structured reason
   `plan_value_invalid` naming the offending key — before any run starts, no
   partial run, no `state.json` written. A plan-sourced `driver` value outside
   `{auto, loop, goal}` refuses the same way instead of silently routing as
   `auto`. This closes 016-02's deviation-log item 4. Validation runs *before*
   clamping — a wrong-type/out-of-range value is a refusal, not something to
   clamp. *Test:* `PlanValueValidationTests`.
4. **Recompile preserves an edited plan, detected by content hash, not a
   self-reported label (A5).** `compile_plan` stamps a `budget_hash` (sha256
   of the canonical-JSON `{budget, driver}`) into every plan it writes.
   `execution_plan.py compile` refuses (exit `2`, structured stderr reason
   `plan_edit_detected`) when an existing `plan.json` for the target spec is
   present **and** its current `budget`/`driver` content no longer hashes to
   its own recorded `budget_hash` — i.e. something changed the file's
   editable content since it was last (re)compiled, regardless of what its
   `provenance` field claims — instead of silently overwriting it via
   `write_plan`'s unconditional `os.replace`. An explicit `--force` flag
   bypasses the refusal and recompiles (fresh `budget_hash`,
   `provenance: "compiled"`) — mirroring the spec-oracle approval posture
   (006-04's `approved_content_hash`): drifted content is treated as a
   deliberate edit that only an explicit override discards. Recompiling over
   an existing plan whose content still matches its recorded `budget_hash`
   (never edited, or freshly written) is unaffected — unconditional
   overwrite, exactly as today (`PlanRecompileIdempotentTests` unchanged: the
   producer's constants never drift, so the hash always matches). *Test:*
   `RecompilePreservesEditTests`.
5. **No-plan / no-disable-sentinel plan ⇒ unaffected (regression guard).**
   With no `--plan`, or a plan that does not request the disable sentinel
   `0` on any knob (including a plan that *raises* a knob above
   `DEFAULT_*`), behavior and `state.json` are byte-for-byte identical to
   pre-016-03 (016-02's AC1/AC5 unchanged) and no clamp breadcrumb is
   emitted. *Test:* `PlanClampNoOpTests` (extends `NoPlanUnchangedTests`).

**DoD:**
- [x] All ACs pass; full test suite green (no regressions in the existing
      1327+ tests).
- [x] Implementer coverage exercises each AC with ≥1 fixture per knob for
      AC1, both directions (accept/refuse) for AC2/AC3, both flag states
      (absent/`--force`) for AC4, and the no-op baseline for AC5.
- [x] Reviewed by jig compliance + craft; `frame_review: true` ⇒
      frame-critique pass cleared before READY_FOR_REVIEW.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation sweep produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated if any decisions are deferred during
      implementation — n/a: no new deferred decision; the deliberately-open
      magnitude-ceiling question is already recorded in ADR-0016's Amendment,
      not a fresh refinement-todo entry.

### Close-out (post-DONE)

- [x] `docs/specs/README.md` regenerated; the clamp + human-edited-consumable
      + recompile-preserve behavior recorded in the Notes column.
- [x] 016-04's dependency on this slice (skill-surface) re-checked — it stays
      DEFERRED regardless (still parked behind its own trigger).

**Anti-horizontal-phasing check:** After this slice, a human can hand-edit a
compiled plan — raise a budget knob, tighten one, or leave it alone — and
`loop.py --plan` runs against it exactly as edited, transparently clamped
back to a live brake only if the edit tried to disable one — real, observable
Compile→Run value, not intermediate plumbing.

### Deviation log (after reconciliation)

Original ACs preserved above. Implementation notes:

1. **Six rounds of pre-implementation frame-critique, not the usual one-shot.**
   `frame_review: true` fired an adversarial pass that ran six times before
   authoring even reached READY_FOR_IMPLEMENTATION (evidence:
   `reviews/slice-03-frame-critique.md` + this file's `## Assumptions`
   A1-A6, each dated to the round that surfaced it). Rounds 1-2 found the ACs
   themselves were built on an undecided premise (a numeric "policy ceiling"
   ADR-0016 named but nothing ever defined) and an ADR/spec/slice
   inconsistency once that premise was narrowed; rounds 3-4 found the AC4
   recompile-refusal and AC1 clamp mechanisms each had a real correctness gap
   (a self-reported label with no integrity check; a sequencing collision
   with 016-02 AC3's goal-driver brake-drop); round 5 found the narrowed
   scope's own disclosure undersold a persistence risk; round 6 passed. All
   six findings are fixed in the ACs/Assumptions as authored — nothing was
   deferred to implementation.
2. **ADR-0016 amended, not just the slice.** Because round 1-2's finding was
   at the ADR level (ADR-0016's Decision/Verification text names a "ceiling
   above policy" clamp trigger that was never operationalized anywhere in
   `loop.py`), the fix landed as a dated `## Amendments` section in
   `docs/decisions/adr-0016-execution-plan-artifact.md` (2026-07-04),
   preserving the original Decision/Verification text per the
   records-vs-live-prose convention, plus matching updates to `spec.md`'s
   Goal 5, Core-model diagram, and the 016-03 SPIDR-table row so the ADR,
   the parent spec, and the slice all state the same narrowed scope.
3. **Post-implementation review found two real, fixed issues; both required
   one re-review round.** The first compliance + craft passes both
   independently flagged the same live bug: `loop.py`'s `--plan` `--help`
   text still said a `human_edited` plan refuses, directly contradicting
   this slice's own AC2 — fixed. Compliance additionally flagged that
   `execution_plan.py`'s `write_plan` has two fail-open edge cases (an
   existing plan with no `budget_hash` field at all — i.e. 016-01-vintage;
   and an unreadable/malformed existing plan) that fall through to an
   unconditional overwrite, undocumented and untested — fixed by adding an
   explicit docstring rationale for both plus one dedicated regression test
   each (`test_legacy_plan_with_no_budget_hash_field_overwrites_unconditionally`,
   `test_malformed_existing_plan_overwrites_unconditionally` in
   `test_execution_plan.py`). Craft's remaining nits (a stale
   `plateau_noise_floor` docstring mention, a stale line-number citation)
   were fixed inline. Both passes were re-run against the fixed deliverable
   and returned `pass`.
4. **`_load_plan` never checks `budget_hash`; only `execution_plan.py`'s
   `write_plan` does (compliance re-review note).** This is intentional, not
   an oversight: the hash exists solely to protect the *recompile* step from
   clobbering an edit (AC4/A5); `loop.py`'s consumption side already treats
   `compiled` and `human_edited` plans identically (AC2) and clamps/validates
   uniformly (AC1/AC3) regardless of whether the content matches any prior
   hash. There is nothing for the hash to protect on the read side — recorded
   here per the reviewer's request, no code change needed.
5. **`PlanHumanEditedDeferredTests` test-class name is now narrower than it
   sounds (compliance re-review note, not fixed).** The class originally held
   016-02 AC7's full "any non-compiled provenance refuses" coverage; this
   slice's AC2 supersedes most of that, so the class now holds only the
   retained `test_unknown_provenance_refuses` case. The class docstring was
   updated to say so accurately, but the class name itself was left as-is
   (a cosmetic rename after both reviews had already passed the deliverable
   was judged not worth a further re-review cycle) — noted here for anyone
   grepping test-class names later.
6. **Craft-flagged strength adopted as a pattern, not a code change:** the
   "deliberately fail-open, here's why" docstring style added to `write_plan`
   (execution_plan.py:332-341) is a good precedent for any future similar
   choice elsewhere in the codebase — noted for future authors, not acted on
   here (out of this slice's scope).

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Skill-internal flags on `loop.py` / `execution_plan.py`; the project front door covers install + high-level usage, not per-flag detail. |
| `docs/specs/README.md` | `updated` | Regenerated by `workflow.py status-board`; 016-03 status + Notes column reflect clamp-never-disable + human-edited-consumable + recompile-preserve. |
| `docs/product-vision.md` | `no-op` | No behavior/scope drift beyond what ADR-0016's amendment already reconciles; no design-principle violation (both reviews' principles checks passed). |
| `docs/architecture.md` | `no-op` | No module-boundary or public-contract change; `--plan`/`--force` are additive flags on existing skill-internal CLIs, already covered by their own `--help` text. |
| `docs/decisions/README.md` / ADR index | `updated` | ADR-0016 gained a dated `## Amendments` section (2026-07-04); no new ADR authored, no `status:` change (stays Accepted). |
| agent-loop `SKILL.md` | `no-op` | `--plan`'s `human_edited`-consumable + clamp behavior is self-documenting via `loop.py --help` (updated this slice); no SKILL.md narrative references the old refused-human_edited behavior. |
| execution-planner skill docs | `no-op` | `execution_plan.py`'s own module docstring was updated inline (this slice's diff) to describe AC4; no separate SKILL.md exists for this skill. |
| `docs/inbox.md` | `no-op` | No items resolved by this slice. |
| `docs/refinement-todo.md` | `no-op` | The one open question this slice deliberately leaves (a genuine magnitude policy ceiling, if ever needed) is recorded as a disclosed trade-off in ADR-0016's Amendment, not a servo-dev refinement-todo entry — it's a product-policy question, not an implementation loose end. |
| `docs/memory/**` | `deferred` | `/jig:memory-sync` to be run as a separate step after this reconciliation lands (out-of-repo artifact under `~/.claude/projects/.../memory/`). |
| Additional live prose / generated templates | `no-op` | No install-contract or template surface touched. |
| `docs/bugs/**` | `no-op` | This slice originated from spec-authoring (016-03 reopen), not a bug report; no bug record applies. |
