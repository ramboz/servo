---
status: RECONCILED
kind: feature
dependencies: [038-02, adr-0047]
last_verified: 2026-11-10
arch_review: true
frame_review: true
claimed_by: claude/model-tiering
---

## Slice 038-03 — plateau escalation ladder

**Goal:** When a loop-driver run plateaus, it climbs configured rungs (for
example raise effort, then raise model) inside the same run, worktree and
budget before it reports `oracle_plateau`. The rung reached is recorded in
`state.json`, on stdout and in the heartbeat outcome, so the heartbeat
quarantines a finding only after the whole ladder failed.

**DoR:**
- 038-02 DONE (role config, configured-run judge split).
- ADR-0047 Accepted, including its amendment of ADR-0010's single-attempt rule.

**Acceptance Criteria:**

1. **Ladder config.** The `models` block accepts `escalation`: a list of rung
   objects. Each rung takes the role keys (`model`/`effort`/`advisor`) and
   overrides the runner only. Rungs are cumulative: rung *k*'s runner config is
   the base runner config with rungs 1..*k* applied in order. A missing or
   empty list means no ladder. A non-list, an empty rung object, an unknown key
   or a bad value is refused by 038-02's validator (`models_invalid` /
   `plan_value_invalid`).
2. **Plateau escalates instead of halting, when a rung can get a fair try.**
   - **Rung window.** At escalation, record a baseline: the highest numeric
     composite so far, if any. The rung's window starts at its **first runner
     iteration**; a judge iteration that falls between the escalation and that
     runner iteration is left out, because it re-scores the previous rung's
     tree. The rung's plateau check runs `_check_plateau` on the baseline plus
     the rung-window entries, with the run's `plateau_window` /
     `plateau_noise_floor`. Rung 0 keeps today's check unchanged.
   - **Fair-window guard.** When the check fires, the run escalates only if
     the next rung can afford one full window on both budgets:
     - **iterations:** the iterations left (`max_iterations − current
       iteration`) must be at least `needed`. `needed` is `plateau_window`,
       plus 1 when the next iteration is a judge iteration;
     - **cost:** when a cost ceiling is set (`cost_ceiling_usd > 0`), the cost
       left (`cost_ceiling_usd − cumulative_cost_usd`) must be at least
       `needed × max_iter_cost`. `max_iter_cost` is the largest per-iteration
       `cost_usd` recorded so far (038-01). This is a lower bound: a raised
       rung usually costs more.
   - **Escalating.** The run does not halt:
     - the rung advances;
     - the runner config becomes that rung's;
     - one stderr breadcrumb names the rung and its runner config;
     - the next iteration proceeds.
   - **Halting.** On the last rung, with no ladder, or when the guard fails,
     the run halts with `oracle_plateau` exactly as today. A guard failure
     adds one stderr breadcrumb naming the budget left and needed (iterations
     and/or USD).
   - **A rung that fails at invocation stops the ladder.** If the invocation
     ends `claude_invocation_failed`, for example because a rung's
     model/advisor pairing is refused, the run halts with that reason as
     today, and the breadcrumb also names the rung and its runner config.

   Under the defaults (5 iterations, window 3) the guard always fails, so a
   configured ladder never turns a plateau into `max_iterations_reached`.
3. **Brakes and authority unchanged.** Rungs spend inside the run's existing
   `max_iterations`, `cost_ceiling` and context brake. Every pre/post-iteration
   brake runs as usual, and no rung raises a cap. The oracle threshold and
   required gate are untouched. The judge's config never changes with the
   rung.
4. **Every rung starts a fresh runner session.** On escalation the loop clears
   `current_session_id` and the 038-01 cost snapshot, so the rung's first
   runner iteration omits `--resume`. The worktree (the code progress) is
   kept; the transcript of the stuck attempt is not. This matches the
   "re-run the failure at higher capability" pattern behind spec 038 A2, and
   it keeps the rung from anchoring on the failed context. The rung's first
   runner prompt adds one short `Escalation` section to the usual seed, last
   oracle output and last verdict. It names:
   - the rung;
   - the best composite so far and the iteration that reached it;
   - the composite at escalation.

   The fresh runner then knows when the current tree has regressed from the
   best.
5. **Recorded in state, stdout and summary.** With a ladder configured:
   - each history entry and per-iteration stdout line carries `rung` (0 = base);
   - `state.json` carries `escalation_rung` and `escalation_events`
     (`[{rung, at_iteration, baseline_composite, runner}]`);
   - the summary line carries `escalation_rung` and `escalation_rungs`
     (the ladder length).

   With no ladder none of these keys appear, so the existing shapes stay
   unchanged.
6. **Resume.** The rung, its baseline and the escalation index are persisted,
   so `--resume <run-id>` continues at the persisted rung. If the resumed
   config's ladder is shorter, the rung is clamped to its length and no further
   escalation happens.
7. **Goal driver.** An `escalation` list under the goal driver prints one stderr
   note that it is ignored (the goal driver has no plateau signal), and the run
   proceeds.
8. **Heartbeat.**
   - `heartbeat.py run` and `dispatch` accept `--models <value>`. A value that
     isn't JSON or a readable file refuses the pass with rc=2 before any
     candidate is touched. Otherwise the value is forwarded verbatim to each
     dispatched `loop.py --models`.
   - A loop summary whose `terminal_reason` is `models_invalid` is a
     pass-level refusal: the finding stays `open` and gets no outcome, and the
     pass exits 2.
   - `outcome` passes through `escalation_rung` and `escalation_rungs` when the
     summary has them.
   - A finding is quarantined when either holds:
     - the summary's `terminal_reason` is `oracle_plateau` (today's trigger:
       the ladder was exhausted, or never started);
     - the run escalated (`escalation_rung ≥ 1`), did not pass, and ended on
       `max_iterations_reached`, `cost_ceiling_reached`, `context_full`,
       `claude_invocation_failed` or `verdict_schema_mismatch`. Such a run
       plateaued at least once before its ladder was cut short.

     Both cases write the same quarantine record
     (`failure_signature: oracle_plateau`), so ADR-0030's evidence-gated
     re-admission applies.
   - When the escalated run ended `claude_invocation_failed` or
     `verdict_schema_mismatch`, the heartbeat emits a breadcrumb naming the
     rung and its runner config, and the pass continues.
     `claude_invocation_failed` also covers timeouts and rate limits, so it
     does not prove a broken config. Even a broken rung leaves each finding
     where a no-ladder run would: quarantined after its plateau.
9. **ADR-0010 amended.** ADR-0010's single-attempt rule carries a dated
   amendment pointing to ADR-0047: one dispatch per finding still holds, and one
   dispatch may now span the configured rungs.

### Behavioral rules

| Rule | Operation/control | Actor | State/precondition | Outcome | Rationale | AC |
|------|-------------------|-------|--------------------|---------|-----------|----|
| BR-1 | plateau detected | loop driver | rung < ladder length and the next rung's window fits the iterations left | escalate, fresh runner session, continue | try more capability before giving up, with a fair window | AC2, AC4 |
| BR-2 | plateau detected | loop driver | last rung, no ladder, or window does not fit | halt `oracle_plateau` | a ladder never turns a plateau into a budget halt | AC2, AC8 |
| BR-6 | outcome recorded | heartbeat | escalated, not passed, ended on a budget brake / invocation failure / verdict mismatch | quarantine (signature `oracle_plateau`) | the finding plateaued; a cut-short ladder must not fall to sticky `tried` | AC8 |
| BR-7 | outcome recorded | heartbeat | escalated run ended `claude_invocation_failed` / `verdict_schema_mismatch` | quarantine (BR-6) + rung-naming breadcrumb; the pass continues | the terminal is shared with transient failures; the quarantine already matches the no-ladder outcome | AC8 |
| BR-8 | plateau detected | loop driver | cost left < needed × largest per-iteration cost | halt `oracle_plateau` (no escalation) | a rung must not start without the money for a full window | AC2 |
| BR-3 | any brake | loop driver | any rung | brake fires as today | rungs never loosen a brake | AC3 |
| BR-4 | `--models` value | heartbeat | not JSON / unreadable | pass refused rc=2, nothing dispatched | don't burn findings on a config typo | AC8 |
| BR-5 | loop refuses `models_invalid` | heartbeat | mid-pass | finding left `open`, pass rc=2 | same | AC8 |

**DoD:**
- [x] All ACs pass; full suite green (3.13: 2699 passed / 10 skipped; 3.9.6 green
      except the two pre-existing macOS-only `[forged]` cases); new tests shown
      to fail with the feature removed, with the exceptions in deviation 10.
- [x] `skills/agent-loop/SKILL.md` (ladder, sizing note: rungs share
      `max_iterations`), `skills/heartbeat/SKILL.md`, `docs/architecture.md`
      and the ADR-0010 amendment updated; host packages regenerated.
- [x] Reviewed (compliance + craft + arch); deviation log + reconciliation
      sweep; reconciliation review passed.

**Anti-horizontal-phasing check:** After this slice, a run that plateaus on
Sonnet/medium retries at Sonnet/high, then Opus/high, each in a fresh runner
session, within the caps it was given. A ladder needs room: at window 3 with
nothing improving, rung 0 plateaus at iteration 4, rung 1 at 7 and rung 2 at
11, so a two-rung ladder needs `--max-iterations 11` or more, and a
`--cost-ceiling` covering about 11 iterations at the top rung's price. Any
improvement pushes those points later. The inbox shows which rung passed, or that the
finding was quarantined after plateauing.

### Deviation log (after reconciliation)

The original ACs are preserved above. Review rounds:
- **Round 1:** compliance, craft and arch all returned needs-changes, with
  three blockers between them.
- **Round 2:** all three passed.
- **Round 3:** a polish batch (routing moved into loop.py, judge breadcrumb,
  kept events) plus an arch-only delta check, which passed. The "round 3" red
  counts in deviation 10 refer to that batch.

What changed against the ACs:

1. **Ladder-less resume (AC6, AC5).** A `--models` block with no `escalation`
   clamps the rung to 0. It drops `escalation_rung` and
   `escalation_history_start` from state, and `_rung_plateau` falls back to
   the plain `_check_plateau` whenever no ladder is configured.
   `escalation_events` is kept as the measurement record. That departs from
   AC5's "with no ladder none of these keys appear" for state; the summary
   still carries no ladder keys.

   Round 1 found that a stale rung with no window start would switch the
   plateau brake off for the rest of the run. That contradicts ADR-0016's
   clamp-never-disable rule, which D4 relies on. The fix makes "a shorter
   ladder clamps" cover length 0.
2. **Escalation resets the context-fill reading (AC3/AC4).** On escalation,
   `last_context_fill_ratio` is cleared in memory and in state, alongside
   the session id and cost snapshot. Otherwise the context gate measures the
   discarded session and can halt `context_full` before the fresh rung has
   run. "Every brake runs as usual" is read as "the brake measures the
   session about to run".
3. **Driver routing for a ladder (AC7/AC8, beyond the ACs).**
   - loop.py's `auto` routing, whether the driver is omitted, explicit or
     plan-sourced, picks the loop driver when the block carries a non-empty
     ladder, with one stderr line. The goal driver has no plateau signal.
   - An explicit `--driver goal` keeps AC7's "escalation ignored" note, as
     does `--background`, which still routes to the goal driver.
   - Round 2 first pinned `--driver loop` in the heartbeat. The arch reviewer
     moved the choice into the node instead, which is trigger-agnostic, so the
     heartbeat never passes `--driver`.
   - The heartbeat's ladder peek and pass-start sizing note were removed.
     Sizing guidance stays as prose in heartbeat SKILL.md.
   - Routing reads the ladder only from `--models` or the plan.
     `--explain-routing` still reports the host-only verdict. Under `auto` on
     a goal-capable host, a `--resume` without `--models` routes to goal and
     fails closed (`goal_resume_unsupported`). SKILL.md says to resume a
     laddered run with `--driver loop`, and architecture.md's routing matrix
     carries the ladder exception. The general resume-routing gap predates
     this slice and is tracked in refinement-todo.
4. **Rung failure detail goes through the existing breadcrumb channel
   (AC2/AC8).**
   - When a laddered run at rung ≥ 1 ends `claude_invocation_failed` or
     `verdict_schema_mismatch`, loop.py writes the rung and its runner config
     (or "judge turn; the judge config is unchanged by the rung") into the
     summary's `terminal_breadcrumb` and onto stderr.
   - The heartbeat embeds that, under ADR-0039, instead of re-folding the
     ladder itself. That removes a duplicated fold that disagreed on
     `inherit`.
   - `verdict_schema_mismatch` is an addition to AC2, which names only
     invocation failure. AC8's heartbeat breadcrumb needs it.
   - "Also covers timeouts and rate limits" is said only of
     `claude_invocation_failed`.
5. **Escalation state keys (AC5).** The baseline is read from
   `escalation_events[-1].baseline_composite`, which is a single source of
   truth; round 1's separate baseline key was dropped. That key only ever
   existed in uncommitted round-1 code, and no committed build wrote it. The
   ladder-less resume still pops `escalation_baseline_composite`, and three
   tests assert it is absent. This is a deliberate, harmless clean-up of any
   working-tree state from that period.
   `escalation_history_start` is kept as an extra key beyond AC5's list. A
   judge iteration between an escalation and the rung's first runner turn is
   labelled with the new `rung` but excluded from the rung window. Per-entry
   rung attribution should account for that.
6. **Human view.** The heartbeat's `status` and `inbox.md` render
   `escalation: rung N of M` whenever a ladder was configured, including
   rung 0. AC8 required only the inbox.jsonl outcome keys.
7. **Escalation prompt.** "Best composite so far" and "composite at
   escalation" are read from history up to the escalation's `at_iteration`
   at prompt time, so no extra state keys are needed.
8. **Heartbeat `--models` file check** also requires the file's contents to be
   valid JSON. That is stricter than AC8's "a readable file", and avoids
   dispatching a pass that loop.py would refuse on every candidate.
9. **ADR-0010 amendment (AC9)** says a rung "overrides" the runner's
   effort, model or advisor, rather than "raises": the validator does not
   enforce monotonic rungs. The amendment text landed in the ADR-0049 drafting
   commit `e9a2fce` rather than this slice's code commit, because they shared
   `docs/decisions`.
10. **DoD exceptions and red evidence.**
    - Round 1's implementation was written before its tests. Red was
      witnessed by swapping in HEAD sources, and the first reported counts
      were overstated.
    - The honest round-2 and round-3 counts:
      - round 2: 4 of 35 loop tests and 5 of 24 heartbeat tests were red
        before their fixes;
      - round 3: the judge-failure test and the auto+ladder routing test.
    - Preservation guards that pass without the feature by construction:
      - no-ladder shape;
      - no `--models` argv;
      - goal driver without a ladder;
      - base-rung failure;
      - the pure validator;
      - auto without a ladder;
      - explicit goal plus a ladder;
      - the heartbeat never passing `--driver`.
    - 15 round-1 mutants and 6 round-2 mutants were all killed, except one:
      the `_rung_plateau` fall-through survived the integration tests,
      because the state strip already covered that path. A dedicated unit
      test was added for it.
11. **Pre-existing 3.9 failures.** The two macOS-only `[forged]` cases are
    unrelated (they pass in Linux CI).

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | The front door lists no loop or heartbeat flags. |
| `docs/specs/README.md` | `deferred` | Regenerated by `workflow.py status-board` at the close step, before DONE. |
| `docs/product-vision.md` | `no-op` | Checked; no scope change. |
| `docs/architecture.md` | `updated` | Ladder state and summary keys, heartbeat `--models` forwarding, auto routing for a ladder, outcome keys, quarantine predicate, rung line in the human view. |
| `docs/decisions/adr-0010-…` | `updated` | Dated amendment pointing to ADR-0047 ("one dispatch may span an escalation ladder"). |
| `docs/decisions/adr-0047-…` | `no-op` | The `auto` + ladder → loop-driver routing (deviation 3) is consistent with D3-A, whose ladder is node-owned and trigger-agnostic, and the ADR's "goal driver ignores the ladder" still holds for an explicit goal driver. It is recorded in deviation 3, architecture.md and the arch review; an ADR note is the owner's call. |
| `docs/decisions/README.md` (ADR index) | `no-op` | No new ADR in this slice; ADR-0047 is already indexed. |
| `docs/specs/038-…/plan.md` | `updated` | The stale `escalation_baseline_composite` state key is corrected to "read from `escalation_events[-1]`". |
| `docs/decisions/adr-0030-…` | `deferred` | A pointer to the widened trigger needs owner approval; recorded in refinement-todo. |
| `docs/refinement-todo.md` | `updated` | Entries added for the ADR-0030 pointer (owner), the never-editing-runner guard (idea), and `auto` resume of a loop-driver run on a goal-capable host. |
| Primer surfaces | `no-op` | servo has no root primer. |
| `docs/inbox.md` | `no-op` | servo has no inbox file. |
| `docs/memory/**` | `no-op` | Nothing new beyond the spec and ADR records. |
| `skills/agent-loop/SKILL.md`, `skills/heartbeat/SKILL.md`, generated `hosts/**` | `updated` | Ladder, fair-window guard, sizing (window 3 plateaus at 4, 7 and 11), recording keys, routing, heartbeat forwarding, quarantine predicate. Hosts regenerated and drift-checked. |
| `agents/*.md` | `no-op` | Unchanged. |
