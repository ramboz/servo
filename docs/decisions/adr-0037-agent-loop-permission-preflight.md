---
status: Proposed
dependencies: []
last_verified: 2026-09-01
frame_review: true
---

# ADR-0037: Agent-loop diagnoses a missing headless edit-permission wall — post-hoc terminal relabel, best-effort goal-driver advisory

## Status

Proposed (2026-08-27)

> Filed from a dogfood run against the **airlock** project (spec 008, GA4
> purchase-conversion). Evidence is external to this repo; the owner should
> run the frame-critique + accept flow before adopting.
>
> **Revised 2026-09-01** after a two-reviewer frame-critique (both
> `needs-changes`, orchestrator-verified against `loop.py`; evidence at
> [reviews/adr-0037-frame-critique.md](reviews/adr-0037-frame-critique.md)). The
> **policy** (refuse loudly on missing edit permission, [ADR-0021](adr-0021-oracle-first-agent-loop-optional-consumer.md))
> was never in dispute; the original **mechanism** — a cheap *ex-ante* probe as
> the gate for both drivers — was exposed as cheap-XOR-faithful and carrying a
> new capable-run-blocking regression. The gate is now **post-hoc zero-edit
> detection** (reality, not prediction); a best-effort ex-ante check survives
> only as an **advisory** cost-saver on the goal driver. Old Option A is retained
> below as a rejected alternative.

## Context

`/servo:agent-loop` (`loop.py`) subprocesses `claude -p --agent runner` with
**no** `--dangerously-skip-permissions` and no `acceptEdits` / allow-list. In a
default-permission context the headless child's `Edit` / `Write` tool calls are
**silently denied** — headless mode cannot prompt for approval — so the `runner`
*runs, emits verdicts, and costs real money*, but makes **zero source edits**.
The oracle never moves, and the signal is unambiguous **after** the run: a
completed, non-error turn that produced **zero file changes**. That post-hoc
signature — not a prediction of it — is what the chosen mechanism reads.

Observed (airlock spec 008, 2026-08-27): two runs — the goal driver
(`iteration_cap_reached`, 15 turns, **$1.27**) and the loop driver
(`oracle_plateau`, 4 iters, **$0.94**) — both made **zero edits** (`map.js`
byte-unchanged) and left the oracle at its red baseline (composite 0.5). Both
failed **safely** (guardrails fired, fail-closed: no false pass, tests not
gamed), but both halted with a **misleading terminal reason and no fix hint** —
`oracle_plateau` / `iteration_cap_reached` rather than "your headless runner
cannot edit; here is the grant to add." ~**$2.2** bought a diagnosis the loop
already had the facts to name. After the user added `.claude/settings.local.json`
`{"permissions":{"defaultMode":"bypassPermissions"}}`, the loop converged in
**one iteration ($0.18)**.

servo already fails **closed** on comparable preconditions — `dirty_tree`
(003-07), `manifest_missing` / `oracle_missing` — those are all *statically*
knowable before spending. Headless edit-capability is different in kind: it is
**not reliably knowable ex ante** (see the rejected Option A), because the
runner's true permission is resolved by `claude -p` itself from a merged,
version-dependent settings hierarchy plus path/tool-scoped allow-lists. The
loop's own detection lineage is post-hoc by nature — bugs 001/002/004 all
inspect the `claude -p` *result* envelope. So the honest analogue is not another
static preflight but a **result-envelope check**: read whether the runner ever
landed a change, and at the halt the existing brakes already produce, report the
*correct* terminal reason with a fix — rather than the misleading `oracle_plateau`
the airlock run got.

## Options considered

### Option A: Cheap *ex-ante* edit-capability probe as the gate for both drivers (rejected on frame-critique)
The original proposal: before the first paid iteration, run a cheap probe (a
scratch write / no-op `Edit`) "through the same permission resolution the
runner's `claude -p` will use" and refuse `rc=2` on denial.
- **Pros:** turns a silent multi-dollar non-result into a refusal *before*
  spending; superficially mirrors the `dirty_tree` / `manifest_missing`
  preflights.
- **Cons (why rejected):** the two required properties are in tension — **cheap
  XOR faithful**. The only faithful resolution is the runner's own mechanism
  (`_invoke_claude` = `claude -p` + `_settings_args(target)` at `cwd=target`,
  `loop.py:1662-1674`); a real `claude -p` probe is neither instant/free nor
  deterministic (a one-turn agent may emit no `Edit` → **false-negative that
  blocks a capable run**). The only genuinely cheap probe — a Python scratch
  write by `loop.py` — is meaningless, since `loop.py` already writes into the
  target unconditionally (`_atomic_write_state`) → always passes →
  false-positive. And "same settings layers" is contradicted by the code:
  `_settings_args` (`loop.py:1607-1621`) forwards only the committed
  `.claude/settings.json`, never the `.claude/settings.local.json` grant this
  ADR cites as its own fix; the runner's real permission is that flag *merged
  with* `claude`'s cwd-hierarchy and path/tool-scoped allow-lists (`Edit(src/**)`,
  Write-vs-Edit), a version-dependent resolution a probe cannot cheaply
  replicate. A false-negative here is **strictly worse than status quo** — it
  blocks work that would have succeeded — a regression neither the status quo nor
  a post-hoc detector can produce.

### Option B: Warn-and-continue
- **Cons:** still spends the full budget making zero edits — the warning does not
  prevent the waste it warns about. Rejected.

### Option C: Auto-inject `--dangerously-skip-permissions` into the child
- **Cons:** servo would **silently disable the host's permission system** on the
  user's behalf — an unacceptable trust escalation for an unattended tool, and
  exactly the kind of self-granted bypass a host safety layer should (and here
  did) refuse. Rejected.

### Option D: Do nothing (status quo)
- **Cons:** the documented failure above — silent budget waste, diagnosable only
  by hand after the run. Rejected.

### Option E: Post-hoc *terminal-reason relabel* at the existing halt, with a best-effort ex-ante *advisory* on the goal driver (chosen)
Do not add a new mid-run brake at all. Track whether the runner ever landed a
change; at the halt the existing brakes already produce (`oracle_plateau` /
`iteration_cap_reached`), **relabel** the terminal reason to
`edit_permission_unavailable` — with a fix breadcrumb — iff the runner never once
edited while the oracle stayed red. On the goal driver, an optional best-effort
ex-ante check may refuse *earlier* to save the goal budget, but it is **advisory**
(never a gate), so it cannot block a capable run.
- **Pros:** reads reality instead of predicting a permission model the loop
  cannot cheaply resolve; no probe-fidelity burden; detection lineage matches
  bugs 001/002/004 (post-hoc envelope inspection). Because it only *relabels a
  halt that already happened*, it **cannot fire earlier than the existing brakes**
  and so can never lose a capable run — dissolving the "fire early enough to be
  useful XOR late enough to be safe" tension a mid-run threshold has (a
  runner-only threshold cannot align with the plateau's every-iteration fire
  point: `_check_plateau` fires at total iteration `window+1` = 4 and `break`s,
  `loop.py:588,2328-2334`, while runner iterations are the odd totals, so `M=3`
  runner iterations → total 5 is dead code and `M=2` → total 3 fires *before* the
  plateau and re-introduces the Option A regression).
- **Cons:** delivers only a *correct terminal reason + fix*, not earlier halting
  (the existing brakes already bound the run); and it needs a **net-new**
  per-runner-iteration disk-change signal (the existing `_dirty_tree_paths` is
  preflight-only and, by design, ignores new files — see the correctness note in
  the Decision).

## Recommended Decision

Adopt **Option E**. The mechanism is a **post-hoc terminal-reason relabel** — no
new mid-run brake — driven by one persisted fact: *did the runner ever land a
change?*

**The signal — "did the runner land anything," including new files.** For each
**runner** iteration `loop.py` records whether it changed **anything on disk**,
computed as a per-iteration **delta** (snapshot before the turn vs. after) and
**including untracked new files**. Two correctness points, both load-bearing:
- *Runner iterations only.* `loop.py` alternates agents — `_agent_for_iteration`
  returns the runner on odd iterations and the **judge** on even ones
  (`loop.py:444`) — and the judge is **read-only by contract** (`Read`/`Glob`/`Grep`;
  "No `Write`, no `Edit`, no `Bash`", `judge.md:18`), so judge iterations land
  zero edits *by design* and carry no capability signal. The signal is recorded
  on runner iterations only.
- *Untracked-inclusive delta.* The shipped `_dirty_tree_paths` (`loop.py:1460`)
  deliberately **excludes** untracked `??` entries (`loop.py:1485`), so a capable
  runner whose work is *creating* a module/test/component — the common
  oracle-driven shape, and literally the Bug 002 case ("none of the deliverables
  exist yet") — would read as "zero edits." The signal is therefore a **net-new**
  git-tree delta that counts created files; a *delta* (not an absolute clean-tree
  check) so `--allow-dirty` / `--resume` from a legitimately dirty tree does not
  confuse it. It is independent of, and more robust than, the runner's
  self-reported `files_changed`.

**The disarm flag.** From this signal `loop.py` maintains one boolean in the
persisted run state: `runner_ever_edited`. The **first** runner iteration that
lands any change sets it true, permanently for the run — an edit *proves* the
runner has edit permission. Because it lives in state, it survives `--resume`
(which today reconstructs only from `oracle_score_history` / `iteration_count`,
`loop.py:2095-2099`, and deliberately skips the dirty-tree check,
`loop.py:2037-2042`); without persistence a resumed capable run could re-arm and
mislabel, so the flag **must** be checkpointed.

**The relabel — at the halt that already happens, not a new one.** The loop's
existing brakes (`oracle_plateau`, which fires at total iteration `window+1` and
`break`s, `loop.py:588,2328-2334`; or `iteration_cap_reached`) already bound the
run. At that terminal point, if `runner_ever_edited` is **false** and the oracle
is **below threshold**, `loop.py` **relabels** the terminal reason from
`oracle_plateau`/`iteration_cap_reached` to `edit_permission_unavailable` and
attaches the fix breadcrumb (a worktree `.claude/settings.local.json` grant, or a
Routine with Bash + Edit/Write granted, per 003-08). Nothing halts earlier than
today; the loop just reports the *correct* reason. This deliberately avoids a
mid-run threshold: a runner-only threshold cannot align with the plateau's
every-iteration fire point (it would be dead code at `M=3` or fire before the
plateau at `M=2`), and firing early is what re-introduces Option A's
capable-run-blocking regression. Relabel-at-halt is always live and never early,
so it cannot lose a capable run. `edit_permission_unavailable` still exits `rc=2`
(distinct from a clean plateau's exit), preserving the fail-closed contract.

The **oracle-below-threshold conjunct is load-bearing**: it confines every
signal blind-spot to already-failing runs. Any way the delta could misjudge
"nothing landed" — a runner that edits then reverts, one whose only change is to
a path the snapshot doesn't observe, a missed edit — can *only* mislabel a run
whose oracle also failed to move (i.e. one already halting red); it can never
touch a progressing or passing run, whose oracle moves and whose halt is never
relabeled. A false *arm* (spurious `runner_ever_edited=true` from stray
artifacts) is safer still: it just suppresses the relabel back to today's
`oracle_plateau`. So both error directions degrade to status quo, never to a
false pass or a blocked capable run.

**Goal driver.** The single long `claude -p` has no per-iteration checkpoint; the
same `runner_ever_edited` fact is read at its terminal point to relabel a
nothing-landed outcome. Because that spends the whole goal budget first, the goal
driver **may additionally** run a best-effort ex-ante capability check to refuse
*before* spending — but that check is **advisory and fail-open**: a confident
denial refuses early; anything uncertain proceeds. It never blocks a run on its
own, so it introduces no capable-run-blocking regression.

servo never self-grants the bypass (Option C stays rejected); it names what the
**user** must grant, consistent with the host safety boundary
([ADR-0021](adr-0021-oracle-first-agent-loop-optional-consumer.md)).

## Consequences

**Becomes easier:**
- A permission wall that today halts with a misleading `oracle_plateau` /
  `iteration_cap_reached` and no fix hint now reports `edit_permission_unavailable`
  with an actionable breadcrumb — the diagnosis the airlock run lacked.

**Becomes harder:**
- A **net-new** per-runner-iteration disk-delta signal must be built
  (untracked-inclusive, delta-based, runner-iterations-only), plus a persisted
  `runner_ever_edited` flag that survives `--resume`. The existing
  `_dirty_tree_paths` cannot be reused as-is (preflight-only, skips new files) and
  the raw `oracle_plateau` window cannot (it counts judge iterations). Getting the
  signal wrong reintroduces a false-refusal regression, so this is the
  load-bearing implementation surface.

## Assumptions

- **A run that halts via an existing brake (`oracle_plateau` / `iteration_cap`)
  while the oracle is red and `runner_ever_edited` is false is a reliable
  permission-wall signature.** The relabel rides the existing halt, so at least
  one runner iteration has run — usually several, though not guaranteed: a plateau
  needs `window+1` *scored* iterations, which include read-only judge turns, so
  the runner count is lower, and at `--plateau-window 1` or `--max-iterations ≤ 2`
  a **single** runner no-op can be the halting state. The one-runner-iteration
  case is absorbed by the graded residual below, not by a multi-iteration
  guarantee; and **any** runner edit sets `runner_ever_edited` permanently, so a
  runner that edits early then stalls is a genuine `oracle_plateau`, **never**
  relabeled. Grounded at n=2
  (airlock spec 008, whose loop-driver run was 2 runner + 2 judge iterations — the
  2 *runner* iterations landed nothing and it halted at `oracle_plateau`; Bug 002 /
  cwv-workbench spec 015, the identical "reads/reasons but Write/Edit denied,
  oracle never moves"). **Residual (graded):** a genuinely capable-but-stuck
  runner that lands nothing *from its very first iteration through the halt*
  (never once editing) for a non-permission reason is indistinguishable from a
  wall and gets the same *label* — but the run was **halting anyway** at the same
  point, so nothing is lost but a precise reason; the breadcrumb names permission
  as the *most likely*, not the only, cause. Kill criterion below covers a field
  miss.
- **The disk-delta signal counts created files, and brackets only the runner
  turn.** If it silently reverts to tracked-only (`_dirty_tree_paths` semantics),
  the new-file blindness returns and `runner_ever_edited` would stay false on a
  capable file-creating run, mislabeling its eventual halt. The snapshot must
  also bracket the **runner invoke only** (`loop.py:2161-2167`), excluding the
  subsequent `gate.py` call (`loop.py:2247`) and `loop.py`'s own `.servo/` state
  write (`loop.py:2287`), and filter `claude -p` cwd bookkeeping / gate test
  artifacts (`__pycache__`, coverage), so those do not *false-arm* the flag. So
  spec-level tests must guard **both directions**: (a) a runner that creates a new
  untracked source file flips `runner_ever_edited` true (arm); (b) a walled runner
  whose only on-disk residue is gate/`claude`/`.servo` bookkeeping leaves it false
  (no false-arm). A false-arm is *safe* — it merely suppresses the relabel, so the
  run reverts to today's `oracle_plateau`/rc-0 status quo (no false pass) — but it
  misses the wall this ADR exists to name, so the disarm-direction fixture matters.
- **The disarm flag is persisted.** If `runner_ever_edited` is not checkpointed,
  a `--resume` of an already-capable run re-arms and can mislabel its halt; the
  flag must live in run state alongside `iteration_count` / `oracle_score_history`.
- The goal-driver advisory check, being fail-open, is net-positive by
  construction: at worst it saves nothing; it can never block a capable run.

## Kill criteria

- If headless `claude -p` gains reliable default edit capability (or `loop.py`
  moves to an explicitly-granted permission model per invocation), the relabel is
  redundant and should be retired rather than maintained.
- If the `runner_ever_edited`-false signature proves ambiguous in the field (a
  capable run whose halt is repeatedly mislabeled for a non-permission reason),
  tighten the signature (e.g. require the runner's own denial annotation) rather
  than loosen it.

## Open questions

- **Should the goal-driver advisory ex-ante check ship in v1 at all, or be
  deferred?** The post-hoc gate alone closes the diagnosis hole for both drivers;
  the advisory check is purely a goal-budget cost optimization and carries the
  (now advisory-only) resolution-fidelity complexity. A reasonable v1 ships the
  post-hoc gate only and defers the advisory optimization until goal-driver waste
  is measured.
- **Should the relabel ever fire *earlier* than the existing halt?** This ADR
  says no — relabel-at-halt is what makes the mechanism provably unable to lose a
  capable run. If field data shows permission-wall runs waste meaningful budget
  before the plateau/cap halt, a *separate* future decision could add an earlier
  halt, but only with a safety argument the mid-run threshold explored here could
  not supply. Deliberately out of scope.
- **Non-git targets are uncovered.** For a non-git target the disk-delta signal
  (like `_dirty_tree_paths`, `loop.py:1472`) cannot compute tracked deltas; a
  filesystem-mtime/snapshot fallback is possible but out of scope for v1, so a
  permission wall on a non-git target still halts via `oracle_plateau` with the
  old, less-actionable reason. Named, not silently assumed away.
