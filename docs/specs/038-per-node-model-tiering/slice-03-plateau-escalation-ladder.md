---
status: DRAFT
kind: feature
dependencies: [038-02, adr-0047]
last_verified:
arch_review: true
frame_review: true
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
   it keeps the rung from anchoring on the failed context.
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
     `verdict_schema_mismatch`, a rung config is likely broken. The heartbeat
     records that finding's outcome and quarantine (its spend counts), then
     stops the pass with rc=2 and a breadcrumb naming the rung. The remaining
     candidates stay `open`, so one bad `--models` ladder cannot burn every
     stuck finding in the pass.
9. **ADR-0010 amended.** ADR-0010's single-attempt rule carries a dated
   amendment pointing to ADR-0047: one dispatch per finding still holds, and one
   dispatch may now span the configured rungs.

### Behavioral rules

| Rule | Operation/control | Actor | State/precondition | Outcome | Rationale | AC |
|------|-------------------|-------|--------------------|---------|-----------|----|
| BR-1 | plateau detected | loop driver | rung < ladder length and the next rung's window fits the iterations left | escalate, fresh runner session, continue | try more capability before giving up, with a fair window | AC2, AC4 |
| BR-2 | plateau detected | loop driver | last rung, no ladder, or window does not fit | halt `oracle_plateau` | a ladder never turns a plateau into a budget halt | AC2, AC8 |
| BR-6 | outcome recorded | heartbeat | escalated, not passed, ended on a budget brake / invocation failure / verdict mismatch | quarantine (signature `oracle_plateau`) | the finding plateaued; a cut-short ladder must not fall to sticky `tried` | AC8 |
| BR-7 | outcome recorded | heartbeat | escalated run ended `claude_invocation_failed` / `verdict_schema_mismatch` | quarantine that finding, stop the pass rc=2, rest stay `open` | a broken rung config must not burn every stuck finding | AC8 |
| BR-8 | plateau detected | loop driver | cost left < needed × largest per-iteration cost | halt `oracle_plateau` (no escalation) | a rung must not start without the money for a full window | AC2 |
| BR-3 | any brake | loop driver | any rung | brake fires as today | rungs never loosen a brake | AC3 |
| BR-4 | `--models` value | heartbeat | not JSON / unreadable | pass refused rc=2, nothing dispatched | don't burn findings on a config typo | AC8 |
| BR-5 | loop refuses `models_invalid` | heartbeat | mid-pass | finding left `open`, pass rc=2 | same | AC8 |

**DoD:**
- [ ] All ACs pass; full suite green; new tests shown to fail with the feature removed.
- [ ] `skills/agent-loop/SKILL.md` (ladder, sizing note: rungs share
      `max_iterations`), `skills/heartbeat/SKILL.md`, `docs/architecture.md`
      and the ADR-0010 amendment updated; host packages regenerated.
- [ ] Reviewed (compliance + craft + arch); deviation log + reconciliation
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

_Filled at reconciliation._

### Reconciliation sweep

_Filled at reconciliation._
