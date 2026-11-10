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
- ✅ 038-02 DONE (role config, `current_session_model` fresh-session rule).
- ✅ ADR-0047 Accepted, including its amendment of ADR-0010's single-attempt rule.

**Acceptance Criteria:**

1. **Ladder config.** The `models` block accepts `escalation`: a list of rung
   objects. Each rung takes the role keys (`model`/`effort`/`advisor`) and
   overrides the runner only. Rungs are cumulative: rung *k*'s runner config is
   the base runner config with rungs 1..*k* applied in order. A missing or
   empty list means no ladder. A non-list, an empty rung object, an unknown key
   or a bad value is refused by 038-02's validator (`models_invalid` /
   `plan_value_invalid`).
2. **Plateau escalates instead of halting.** At escalation, record a baseline
   (the highest numeric composite so far, if any). Each rung's plateau check
   runs `_check_plateau` on that baseline plus the iterations scored since the
   escalation, with the run's `plateau_window` / `plateau_noise_floor`.

   When the check fires and a next rung exists, the run does not halt:
   - the rung advances;
   - the runner config becomes that rung's;
   - one stderr breadcrumb names the rung and its runner config;
   - the next iteration proceeds.

   When it fires on the last rung, or with no ladder, the run halts with
   `oracle_plateau` exactly as today.
3. **Brakes and authority unchanged.** Rungs share the run's `max_iterations`
   and `cost_ceiling`. Every pre/post-iteration brake runs as usual, and no rung
   adds iterations or spend. The oracle threshold and required gate are
   untouched. The judge's config never changes with the rung.
4. **Session follows the rung.** A rung that changes the runner `model` starts
   a fresh runner session (038-02 AC5). A rung that changes only
   `effort`/`advisor` resumes the current session.
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
   - The quarantine trigger stays `terminal_reason == oracle_plateau`, which
     now means the ladder was exhausted.
9. **ADR-0010 amended.** ADR-0010's single-attempt rule carries a dated
   amendment pointing to ADR-0047: one dispatch per finding still holds, and one
   dispatch may now span the configured rungs.

### Behavioral rules

| Rule | Operation/control | Actor | State/precondition | Outcome | Rationale | AC |
|------|-------------------|-------|--------------------|---------|-----------|----|
| BR-1 | plateau detected | loop driver | rung < ladder length | escalate, continue | try more capability before giving up | AC2 |
| BR-2 | plateau detected | loop driver | rung == ladder length (incl. no ladder) | halt `oracle_plateau` | unchanged terminal; heartbeat quarantine semantics hold | AC2, AC8 |
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

**Anti-horizontal-phasing check:** After this slice a heartbeat or human run
that plateaus on Sonnet/medium retries at Sonnet/high, then Opus/high, inside
its existing budget, and the inbox shows which rung passed or that the whole
ladder plateaued.

### Deviation log (after reconciliation)

_Filled at reconciliation._

### Reconciliation sweep

_Filled at reconciliation._
