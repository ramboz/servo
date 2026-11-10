---
status: RECONCILED
kind: feature
dependencies: [038-01, adr-0047]
last_verified: 2026-11-10
arch_review: true
frame_review: true
claimed_by: claude/model-tiering
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
- [x] All ACs pass; full suite green (3.13: 2637 passed / 10 skipped; 3.9.6 green
      except the two pre-existing macOS-only `[forged]` cases); new tests shown
      to fail with the feature removed, with the exceptions in deviation 11.
- [x] No `model:`/`effort:` added to `agents/*.md`; the 032-03 Copilot
      model-neutrality tests stay green.
- [x] `skills/agent-loop/SKILL.md`, `skills/execution-planner/SKILL.md` and
      `docs/architecture.md` (plan.json `models`, state `models`) updated.
      The SKILL.md names the split-only measurement baseline: a block that
      sets the default model explicitly gives the split without a tier.
      Host packages regenerated.
- [x] Reviewed (compliance + craft + arch); deviation log + reconciliation
      sweep; reconciliation review passed.

**Anti-horizontal-phasing check:** After this slice a user can run the runner on
Sonnet with an Opus advisor and an Opus judge in its own session, and read in
`state.json` exactly what each iteration requested, ran and cost.

### Deviation log (after reconciliation)

The original ACs are preserved above. What changed during implementation and
review (compliance, craft and arch all passed in round 1; their notes were
applied in one follow-up batch):

1. **AC7 advisor exclusion.** An id is marked as the advisor when it equals the
   requested advisor or contains it as a `-`-delimited token, unless it also
   equals or token-names the role's own requested model. This follows the
   plan.md wording rather than "equals" only, because aliases such as `opus`
   map to full ids. The second signal applies **only when the role requests an
   explicit `model`**. With an inherited model, the executor's own entry could
   share the advisor's family token, so only the `usage.iterations`
   (final-turn) signal is used. Spec A1 is corrected in place to name this
   case: a requested advisor consulted in a non-final turn under an
   inherited model is not attributed.
2. **AC1 inline detection** uses `value.lstrip().startswith("{")`, so leading
   whitespace is accepted. An inline value starting with `[`, and a file
   holding valid non-object JSON, both get a "must be a JSON object" message.
   Files are read as UTF-8, and a decode error is `models_invalid`, never a
   traceback.
3. **AC2 reason channel.** The structured reason is on the stdout summary line
   (via `_refuse_plan`), with a free-text `loop:` stderr breadcrumb. This
   follows the existing 016-03 plan-refusal convention.
4. **AC5 resume.** `--plan` and `--resume` are mutually exclusive (016-02 AC8),
   so only `--models` can replace the persisted block on resume. A kept,
   persisted block is re-validated, and an invalid one refuses with
   `models_invalid` before any model call.
5. **AC6 notes.** Under `--background`, the parent also prints the
   judge-ignored note; the child writes it to `background.log`.
   `--emit-routine-prompt` with `--models` prints one note that the block is
   not carried into the Routine prompt. The Routine path is not covered by
   any AC.
6. **AC8 presence hashing.** The planner hashes the presence of a `models` key
   with any value, including `null`, through an `_ABSENT` sentinel. This lets
   the planner and loop agree, since loop refuses `models: null`. A legacy
   plan with no hash that carries `models` now refuses overwrite without
   `--force`: `models` is never compiled, so its presence proves a human edit.
   Plans with no `models` key hash byte-identically to before (pinned digest).
   The hash-less case has its own `plan_edit_detected` message. One edge
   follows 016-03's semantics: a `models` block whose `budget_hash` was
   re-stamped to include it reads as unedited and is replaced on recompile
   (pinned by a test). SKILL.md states this exception.
7. **Built ahead for 038-03.** `_validate_models(allow_escalation=True)`
   validates an `escalation` list. No 038-02 caller enables it; 038-03 does.
   Flagged under the leanness lens and kept because 038-03 is the next commit
   on this branch.
8. **038-01 hardenings landed here.** Tracked in refinement-todo, now closed:
   - `_iteration_cost_delta` requires the snapshot's model-usage tokens to be
     greater than 0 before accepting `session_delta`;
   - `_reported_total_cost` parses through `_as_number`, so NaN, inf and
     numeric strings count as absent.
9. **Context-fill reading under the split.** `last_context_fill_ratio` and the
   summary's `context_fill_ratio` alternate between the runner's session and a
   fresh judge session. The gate still protects the runner, because every
   runner turn is followed by a pre-judge check on the runner's own ratio.
   This is documented in architecture.md, SKILL.md and a code comment.
10. **Persistence shape.** `models` is persisted in goal-driver state as well as
    loop state. An all-`inherit` block persists as `{"runner": {}, "judge": {}}`
    and is not in effect.
11. **DoD exceptions.**
    - Ten tests are negative guards. They pass with or without the feature, by
      design: no-config argv identical, shared session without a block,
      unmarked usage without an advisor, goal argv unchanged, plan without
      `models`, old state, `requested` all null, compiled plan hash unchanged,
      no inherit-judge note, all-inherit not configured.
    - The follow-up batch's tests were written after their code. Red was
      witnessed by mutation instead: 10 mutations, each turning its targeted
      tests red.
12. **Out of scope, tracked.** The Copilot branch of `_invoke_claude` drops
    `role_args`. This can't run today, because `run_loop` refuses
    `--host copilot`. Spec 041-02 now carries an AC to honour or refuse
    `role_args` before the refusal is lifted.
    ADR-0016's plan-shape example now lacks `budget_hash` and `models`. A
    pointer amendment needs owner approval, so it is recorded in
    refinement-todo rather than written.
13. **Pre-existing 3.9 failures.** Two macOS-only
    `test_gate_output_readback.py [forged]` cases fail the same way on
    `origin/main`, and they pass in Linux CI (PR 50).

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | The front door does not list loop flags; no user-facing claim changed. |
| `docs/specs/README.md` | `deferred` | Regenerated by `workflow.py status-board` at the close step, before DONE. |
| `docs/product-vision.md` | `no-op` | Checked; no scope change. |
| `docs/specs/038-…/spec.md` | `updated` | Assumption A1 corrected in place for the inherited-model case of the advisor signal. |
| `docs/architecture.md` | `updated` | plan.json `models`, state `models`, judge split, context-fill alternation. |
| Primer surfaces | `no-op` | servo has no root primer; scaffold templates don't describe loop flags. |
| `docs/inbox.md` | `no-op` | servo has no inbox file. |
| `docs/refinement-todo.md` | `updated` | The "Spec 038-01 hardening" entry is closed (deviation 8). A new entry records the ADR-0016 plan-shape pointer, which awaits the owner's decision. |
| `docs/memory/**` | `no-op` | Nothing new beyond 038-01's learning: the cache probe is recorded in spec 038 and ADR-0047. |
| `docs/decisions/**` | `no-op` | ADR-0047 governs; no ADR text changed in this slice. |
| `docs/specs/041-…/slice-02-…` | `updated` | Added an AC: honour or refuse `role_args` on the Copilot path (deviation 12). |
| `skills/agent-loop/SKILL.md`, `skills/execution-planner/SKILL.md`, generated `hosts/**` | `updated` | Options and refusal-table rows, the split rule and its rationale, the split-only measurement baseline, the advisor caveat. The planner's `plan_edit_detected` message and table row now cover the hash-less + `models` case, and the re-stamped-hash exception is stated. Hosts regenerated and drift-checked. |
| `agents/*.md` | `no-op` | Unchanged; Copilot model-neutrality preserved. |
