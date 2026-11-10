---
status: DRAFT
kind: feature
dependencies: [038-01, adr-0047]
last_verified:
arch_review: true
frame_review: true
---

## Slice 038-02 — role model placement

**Goal:** A run can place the `runner` and `judge` roles on a chosen model,
effort and advisor, from a compiled/human-edited plan or a flag. When the two
roles are on different models, the judge runs in its own fresh session. With
no configuration, behaviour is unchanged.

**DoR:**
- ✅ 038-01 DONE (`requested` field exists, accounting proves what ran).
- ✅ ADR-0047 Accepted (role placement + session split decision).
- ✅ `claude -p` accepts `--model`, `--effort`, `--advisor` (probed, spec 038).

**Acceptance Criteria:**

1. **One config shape, two sources.** A `models` block
   `{"runner": {...}, "judge": {...}}` is read from `--models <value>` and
   from a plan's top-level `models` key. `<value>` is inline JSON when it starts
   with `{`, otherwise a path to a JSON file. Each role block takes only
   `model`, `effort` and `advisor`, all optional strings, where `"inherit"`
   means absent. Precedence is block-level: `--models` replaces the plan's
   block entirely (no per-field merge), and with neither every role inherits.
   The plan's `schema_version` stays `1`.
2. **Fail-closed validation.** One validator refuses, before any run directory
   or `state.json` exists, with rc=2 and a structured stderr reason
   (`models_invalid` for the flag, including an unreadable file or bad JSON;
   `plan_value_invalid` for the plan key). It refuses on:
   - a non-object block;
   - an unknown key at either level;
   - a non-string value;
   - an `effort` outside `low|medium|high|xhigh|max|inherit`;
   - a `model`/`advisor` that does not match
     `^[A-Za-z0-9][A-Za-z0-9._:/\[\]-]*$` (no leading `-`, no whitespace).
3. **Roles reach the argv.** Each runner iteration's argv carries
   `--model <m>` / `--effort <e>` / `--advisor <a>` for the runner's set
   fields; each judge iteration's argv does the same for the judge's fields.
   Inherited fields add no flag. With no config, every argv is byte-identical
   to 038-01's.
4. **Judge session split.** Runner and judge share one session (today's
   behaviour) iff their resolved `model` values are equal, with `inherit`
   equal to `inherit`. Otherwise:
   - every judge invocation omits `--resume`, so it starts a fresh session;
   - a judge invocation never updates `current_session_id` or the 038-01
     cost snapshot;
   - its `session_id` is still recorded on its history entry;
   - runner invocations keep resuming the runner session.
5. **Model change starts a fresh runner session.** `state.json` records
   `current_session_model`, the runner model the current session started
   under; missing in old state means `inherit`. A runner invocation whose
   resolved model differs from it omits `--resume` and then records the new
   model. This covers a `--resume <run-id>` run whose config changed (and
   038-03's rungs).
6. **Goal driver.** The runner block applies to the single `/goal` invocation
   (its argv carries the runner's set flags). A non-inherit judge block under
   the goal driver prints one stderr note that it is ignored, and the run
   proceeds. A `--background` launch forwards the resolved block to the
   detached child, which applies it.
7. **Accounting and persistence.** Each history entry's (and the goal record's)
   `requested` names the role's resolved `model`/`effort`/`advisor` (`null` =
   inherited). The resolved block is persisted in `state.json` as `models`. On
   `--resume <run-id>`, a `--models` or plan block replaces the persisted one;
   otherwise the persisted block is kept.
8. **Planner keeps human edits.** `execution_plan.py`'s recompile-preserve
   check counts a hand-added or edited `models` block as an edit, so it refuses
   to overwrite without `--force`. A plan with no `models` key hashes
   byte-identically to today.

### Behavioral rules

| Rule | Operation/control | Actor | State/precondition | Outcome | Rationale | AC |
|------|-------------------|-------|--------------------|---------|-----------|----|
| BR-1 | judge invocation | loop driver | runner.model == judge.model | `--resume <current_session_id>` (shared lane) | default unchanged | AC4 |
| BR-2 | judge invocation | loop driver | runner.model != judge.model | fresh session; no session/snapshot update | caches are model-scoped and thinking blocks don't carry across models; also independence (judge.md) | AC4 |
| BR-3 | runner invocation | loop driver | config model != `current_session_model` | fresh session | a model switch inside one session cold-starts the cache anyway | AC5 |
| BR-4 | judge config | goal driver | judge non-inherit | ignored + stderr note | the goal driver has no judge role | AC6 |

**DoD:**
- [ ] All ACs pass; full suite green; new tests shown to fail with the feature removed.
- [ ] No `model:`/`effort:` added to `agents/*.md`; the 032-03 Copilot
      model-neutrality tests stay green.
- [ ] `skills/agent-loop/SKILL.md`, `skills/execution-planner/SKILL.md` and
      `docs/architecture.md` (plan.json `models`, state `models` /
      `current_session_model`) updated; host packages regenerated.
- [ ] Reviewed (compliance + craft + arch); deviation log + reconciliation
      sweep; reconciliation review passed.

**Anti-horizontal-phasing check:** After this slice a user can run the runner on
Sonnet with an Opus advisor and an Opus judge in its own session, and read in
`state.json` exactly what each iteration requested, ran and cost.

### Deviation log (after reconciliation)

_Filled at reconciliation._

### Reconciliation sweep

_Filled at reconciliation._
