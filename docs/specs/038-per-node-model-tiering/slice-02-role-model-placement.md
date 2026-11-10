---
status: READY_FOR_IMPLEMENTATION
kind: feature
dependencies: [038-01, adr-0047]
last_verified:
arch_review: true
frame_review: true
---

## Slice 038-02 — role model placement

**Goal:** A run can place the `runner` and `judge` roles on a chosen model,
effort and advisor, from a compiled/human-edited plan or a flag. A configured
run gives the judge its own fresh session every judge iteration. With no
configuration, behaviour is unchanged.

**DoR:**
- 038-01 DONE (`requested` field exists, accounting proves what ran).
- ✅ ADR-0047 Accepted 2026-11-10 (role placement + session split decision),
  after two frame-critique rounds.
- ✅ `claude -p` accepts `--model`, `--effort`, `--advisor` (probed, spec 038).
- ✅ Shared-lane cache behaviour probed (spec 038 grounding): the judge's
  agent-switched `--resume` reads 0 cached tokens at equal model.

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
4. **A configured run splits the judge's session.** The split applies whenever
   the resolved block is **in effect**, meaning it sets at least one field.
   A block whose fields are all `inherit` counts as not configured. When the
   split applies:
   - every judge invocation omits `--resume`, so it starts a fresh session;
   - a judge invocation never updates `current_session_id` or the 038-01
     cost snapshot (its cost basis is `"reported"`, being a fresh session);
   - its `session_id` is still recorded on its history entry;
   - runner invocations keep resuming the runner session, so consecutive runner
     turns build a warm cache.

   With no block in effect, runner and judge share one session exactly as
   today.
5. **Resume with a changed block.** On `--resume <run-id>`, a `--models` or
   plan block replaces the persisted one; otherwise the persisted block is
   kept (missing in old state means no block). The runner keeps resuming its
   session with the new flags. A model change there cold-starts the cache,
   which the spec 038 probe confirmed, but keeps the transcript. Fresh
   sessions on escalation are 038-03's rule, not this slice's.
6. **Goal driver.** The runner block applies to the single `/goal` invocation
   (its argv carries the runner's set flags). A non-inherit judge block under
   the goal driver prints one stderr note that it is ignored, and the run
   proceeds. A `--background` launch forwards the resolved block to the
   detached child, which applies it.
7. **Accounting and persistence.**
   - Each history entry's (and the goal record's) `requested` names the role's
     resolved `model`/`effort`/`advisor` (`null` = inherited).
   - When the role requested an advisor, any `model_usage` entry whose id equals
     it, or contains it as a hyphen-delimited token (`opus` in
     `claude-opus-5-5`), also gets `"advisor": true`. This is the second
     signal 038-01 AC2 promised, unless that id equals the role's own requested
     model.
   - The resolved block is persisted in `state.json` as `models`.
8. **Planner keeps human edits.** `execution_plan.py`'s recompile-preserve
   check counts a hand-added or edited `models` block as an edit, so it refuses
   to overwrite without `--force`. A plan with no `models` key hashes
   byte-identically to today.

### Behavioral rules

| Rule | Operation/control | Actor | State/precondition | Outcome | Rationale | AC |
|------|-------------------|-------|--------------------|---------|-----------|----|
| BR-1 | judge invocation | loop driver | no `models` block in effect | `--resume <current_session_id>` (shared lane) | default unchanged | AC4 |
| BR-2 | judge invocation | loop driver | a `models` block in effect | fresh session; no session/snapshot update | probe: the judge's first agent-switched resume reads 0 cached tokens, and later ones still re-read interleaved runner turns uncached; a fresh judge reads only its self-contained prompt (`agents/judge.md`) and stays independent | AC4 |
| BR-3 | judge config | goal driver | judge non-inherit | ignored + stderr note | the goal driver has no judge role | AC6 |

**DoD:**
- [ ] All ACs pass; full suite green; new tests shown to fail with the feature removed.
- [ ] No `model:`/`effort:` added to `agents/*.md`; the 032-03 Copilot
      model-neutrality tests stay green.
- [ ] `skills/agent-loop/SKILL.md`, `skills/execution-planner/SKILL.md` and
      `docs/architecture.md` (plan.json `models`, state `models`) updated.
      The SKILL.md names the split-only measurement baseline: a block that
      sets the default model explicitly gives the split without a tier.
      Host packages regenerated.
- [ ] Reviewed (compliance + craft + arch); deviation log + reconciliation
      sweep; reconciliation review passed.

**Anti-horizontal-phasing check:** After this slice a user can run the runner on
Sonnet with an Opus advisor and an Opus judge in its own session, and read in
`state.json` exactly what each iteration requested, ran and cost.

### Deviation log (after reconciliation)

_Filled at reconciliation._

### Reconciliation sweep

_Filled at reconciliation._
