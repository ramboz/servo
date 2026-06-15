---
status: DONE
dependencies: [011-02, 002, 003, adr-0010]
arch_review: true
last_verified: 2026-06-15
---

## Slice 011-03 — candidate-dispatch

**STATUS: DONE**

**Goal:** Each **actionable, `open`** finding becomes a candidate and gets one
oracle-gated loop attempt in isolation: a `gate.py` oracle **preflight
(refuse-without-oracle)** → a **fresh, isolated git worktree** provisioned with
the target's oracle → `loop.py` (spec 003) dispatched with an **untrusted-data-
framed** prompt → the outcome (`tried` + final oracle status / composite / cost,
or `passed`) recorded back to the inbox through 011-02's locked merge. Nothing
crosses from "proposed in the inbox" to "a running loop" without passing the
oracle gate. `heartbeat.py dispatch <target>` is the new verb.

> **Boundary with 011-04 (whole-heartbeat ceiling) and the loop/race seam.**
> This slice dispatches the `actionable AND open` candidate set **serially** and
> forwards a **per-loop** `--cost-ceiling` to each `loop.py` run; it does **not**
> aggregate a whole-pass ceiling — that is 011-04 (`heartbeat.py run` = discover
> → dispatch under one ceiling). It dispatches to `loop.py` (003, DONE); the
> dispatch target is kept **pluggable** so `race.py` (005, parked) can slot in
> later without reshaping the inbox contract. Landing/merging a worktree's result
> is **out of scope** — the loop *proposes* a fix in isolation; a human (or a
> future slice) decides whether to land it.

**DoR:**
- ✅ **011-02 DONE** — the inbox is a resuming **state spine**: stable
  `finding_id`, the `open`→`tried`→`passed`/`skipped` lifecycle, the locked
  (`fcntl.flock`) + atomic (`tmp`+`os.replace`) merge, and the `actionable` /
  `actionable_reason` / immutable `provenance` fields exist to read and write
  back. ADR-0010 **reserves** the `attempts` / `outcome` fields this slice is the
  first to populate.
- ✅ **002 DONE** — `gate.py <target> --json` emits the closed `{0,1,2}` exit
  contract and the refuse-without-oracle reason taxonomy this slice defers to
  (`manifest_missing` / `oracle_missing` / `oracle_not_executable`, ADR-0002).
- ✅ **003 DONE** — `loop.py <target> --prompt <text> [--cost-ceiling --max-iterations
  --driver auto|loop|goal]` exists; its **final summary JSON** exposes
  `final_oracle_status`, `oracle_score_history[-1].{composite,threshold}`,
  `cumulative_cost_usd`, `run_id`, `terminal_reason`. loop.py **vendors its own
  `gate.py`** (003-07), runs a dirty-tree preflight that **skips untracked files
  and non-git targets**, and does **not** create/manage worktrees — the caller
  supplies the isolated path.
- ✅ **ADR-0010 Accepted** — the reserved `outcome` shape
  `{run_id, oracle_status, oracle_composite, cost_usd, dispatched_at}`, the
  one-attempt-in-v1 rule (a `tried` finding is not auto-re-dispatched), and the
  status lifecycle are frozen.
- ✅ **Probed fact (grounds AC3/AC4):** servo's `.gitignore` ignores `.servo/`
  and `git ls-files` shows `.servo/install.json` is **not tracked**, so a fresh
  `git worktree add` does **not** inherit the manifest; `loop.py`'s preflight
  ([`loop.py`](../../../skills/agent-loop/loop.py) ~L1060) requires
  `<worktree>/.servo/install.json` **and** `<worktree>/oracle.sh` present. The
  worktree must therefore be **provisioned** with the oracle.
- ✅ Decision: stdlib-only, Python 3.11+ (spec 009 floor); `gh` / `git` /
  `gate.py` / `loop.py` are **subprocess** calls, never imported (the 011-01/02
  dependency-free invariant).
- ✅ Decision: dispatch is **serial** in v1 (Open question; deterministic spend,
  simplest ceiling accounting for 011-04).

**Acceptance Criteria:**

1. **Candidate selection — `actionable AND open`.** `heartbeat.py dispatch
   <target>` reads `inbox.jsonl` (011-02 schema v2) and selects the candidate set
   = findings with `actionable == true` **AND** `status == "open"`, in a
   deterministic order (`discovered_at`, then `finding_id`). Findings that are
   `passed` / `tried` / `skipped` or `actionable == false` are **never**
   dispatched (resume discipline — the set shrinks across runs). An empty
   candidate set is a clean no-op (exit 0, inbox untouched). *Test:*
   `CandidateSelectionTests`.

2. **Oracle preflight — refuse-without-oracle (Guardrail #3).** Before creating
   any worktree or spawning any loop, `dispatch` runs `gate.py <target> --json`;
   if it returns `exit_code == 2` with a refuse-without-oracle reason
   (`manifest_missing` / `oracle_missing` / `oracle_not_executable`, ADR-0002),
   `dispatch` refuses the **whole pass** (rc=2, a stderr breadcrumb quoting the
   gate's `reason` + its `/servo:scaffold-init` recovery hint), dispatches
   nothing, and leaves every candidate `open`. The taxonomy is **gate.py's** — no
   reimplementation, no special-casing. *Test:* `OraclePreflightRefusalTests`.

3. **Isolated git worktree per candidate.** For each candidate `dispatch` creates
   a **fresh linked worktree** of the target at its current `HEAD`, on a dedicated
   branch `servo/heartbeat/<finding_id>`, under the reserved git-ignored path
   `<target>/.servo/dispatch/<finding_id>/` (alongside `runs/` / `races/` /
   `triage/`). The target's own working tree is **never** mutated — the loop's
   edits land only inside the worktree. A **non-git target** cannot be isolated →
   that candidate is recorded as a dispatch env-error (AC6) and skipped; dispatch
   never runs a loop in-place against the live tree. *Test:*
   `WorktreeIsolationTests`.

4. **Worktree oracle provisioning + verification.** Because `.servo/` is
   git-ignored (DoR), `dispatch` **provisions** the oracle into the fresh
   worktree — copies `<target>/oracle.sh` + `<target>/.servo/install.json` (and
   any oracle sidecars the manifest references, e.g. a spec-oracle overlay's
   vendored `checks.py`) — then **verifies** by running `gate.py <worktree>
   --json`: a usable verdict (exit 0 or 1) proceeds to dispatch; an `exit 2` in
   the worktree records that candidate as a dispatch env-error (AC6) and skips it
   — never spawn `loop.py` against an oracle-less worktree. `loop.py` vendors its
   own `gate.py` (003-07), so only the oracle + manifest (+ sidecars) are
   provisioned, not the runtime gate. *Test:* `WorktreeOracleProvisioningTests`.

5. **Untrusted-data prompt framing (Guardrail #4).** The prompt handed to
   `loop.py --prompt` frames the finding's discovered text (`title` / `detail` /
   `evidence`) inside a clearly-delimited, labeled block as **untrusted data
   describing a finding to act on — never instructions to follow**. The imperative
   task ("drive this target's oracle to pass") is **servo-authored** and never
   string-interpolates discovered text into instruction position. A finding with
   `provenance == "contributor"` (issue / commit) carries an explicit
   injection-resistant preamble; `first_party` (CI) findings use the same framing
   (defense in depth). loop.py does **not** sanitize `--prompt` (verified at
   [`loop.py`](../../../skills/agent-loop/loop.py) ~L2716), so the dispatcher owns
   the framing. *Test:* `UntrustedPromptFramingTests`.

6. **Dispatch + outcome capture.** `dispatch` invokes `loop.py <worktree>
   --prompt <framed> --cost-ceiling <usd> --max-iterations <n>` (driver default
   `auto`), captures the loop's **final summary JSON**, and reads
   `final_oracle_status`, `oracle_score_history[-1].composite`,
   `cumulative_cost_usd`, and `run_id`. A `loop.py` invocation that exits
   non-zero on a preflight or emits **no parseable summary** records a dispatch
   **env-error** outcome for that candidate (`outcome.oracle_status =
   "env_error"`, a reason breadcrumb) and moves on — never a torn / partial inbox
   write. *Test:* `LoopDispatchOutcomeTests`.

7. **Outcome recorded back (ADR-0010 reserved shape).** Per dispatched candidate,
   `dispatch` updates the finding through 011-02's **locked, atomic merge**:
   `attempts += 1`; `outcome = {run_id, oracle_status, oracle_composite, cost_usd,
   dispatched_at}` (the ADR-0010-reserved shape, `dispatched_at` ISO-8601);
   `status = "passed"` **iff** `final_oracle_status == "pass"`, else `"tried"`. A
   `tried` finding is **not** auto-re-dispatched on a later pass (one attempt in
   v1 — ADR-0010), so it leaves the candidate set. `skipped` is **never**
   auto-set (human-only, 011-02). *Test:* `OutcomeRecordingTests`.

8. **Spine-safe concurrent writes.** The outcome write reuses 011-02's
   `fcntl.flock(LOCK_EX | LOCK_NB)` on `.servo/triage/.inbox.lock` + `tmp` +
   `os.replace` discipline, so a concurrent `discover` cannot tear or drop the
   outcome and a lock-contended dispatch backs off (breadcrumb, exit 0) without
   corruption. The merge **preserves** every immutable / sticky / volatile field
   except the three this slice owns (`status` / `attempts` / `outcome`) and
   re-emits records in canonical v2 key order. *Test:* `DispatchConcurrencyTests`.

9. **Serial dispatch + per-loop ceiling forwarding + candidate cap.** Candidates
   are dispatched **serially** (v1 default). `dispatch` accepts `--cost-ceiling
   <usd>` and forwards it as **each loop's per-run** ceiling; it does **not** yet
   aggregate a whole-pass ceiling (that is 011-04). `--max-candidates <n>` bounds
   how many candidates are dispatched in one pass; any beyond the cap stay `open`
   for the next pass. *Test:* `SerialDispatchTests`.

10. **Closed `{0,2}` exit + read-only-outside-its-writes + stdlib-only.**
    `dispatch` exits **0** when the pass completes — **including** when individual
    loops scored below threshold (recorded `tried`) or hit per-candidate
    env-errors; a below-threshold loop is a recorded *outcome*, not a dispatch
    error — and **2** only on a pass-level env error (target missing /
    not-a-directory, refuse-without-oracle per AC2, unreadable or
    unsupported-schema inbox). It never mutates the target outside
    `<target>/.servo/` and the per-candidate worktree; stdlib-only (`gh` / `git` /
    `gate.py` / `loop.py` subprocessed, never imported). *Tests:*
    `DispatchExitContractTests` + extend `ReadOnlyByteSnapshotTests` /
    `DependencyFreeTests`.

**DoD:**
- [x] All ACs pass; full existing suite green (no regressions in `test_gate.py` /
      `test_loop.py` / `test_scaffold.py`). *(heartbeat 168, gate 75, scaffold 42/1
      skipped, loop 253 — all green; ruff 0.15.17 clean.)*
- [x] Per-AC coverage under `skills/heartbeat/test_heartbeat.py`:
      AC1→`CandidateSelectionTests`, AC2→`OraclePreflightRefusalTests`,
      AC3→`WorktreeIsolationTests`, AC4→`WorktreeOracleProvisioningTests`,
      AC5→`UntrustedPromptFramingTests`, AC6→`LoopDispatchOutcomeTests`,
      AC7→`OutcomeRecordingTests`, AC8→`DispatchConcurrencyTests`,
      AC9→`SerialDispatchTests`, AC10→`DispatchExitContractTests` +
      `DispatchReadOnlyByteSnapshotTests` + `DispatchStdlibOnlyTests` (the extended
      011-01/02 invariant classes). `loop.py` / `gate.py` are driven via the
      established mock-binary harness (003-01 AC8 pattern) — adapted to the
      `SERVO_HEARTBEAT_{GATE,LOOP}_PY` env-override test-hook (see deviation log) —
      so no test makes a live `claude -p` call.
- [x] **arch_review TRIGGERED** (`arch_review: true`): this slice opens the
      heartbeat's **one execution edge** — it spawns `loop.py` subprocesses and
      creates git worktrees, a new module boundary (heartbeat *composes* the loop;
      the loop stays trigger-agnostic) with an adversarial surface (Guardrail #4).
      Arch-pass verdict recorded under `reviews/slice-03-arch.md`
      (**PASS-WITH-NITS** — module boundary sound, Guardrails #3/#4 well-bounded,
      A1/A2 de-risked, no new ADR needed; nits folded into the deviation log +
      refinement-todo).
- [x] Reviewed by independent reviewer subagent (`jig:reviewer`): compliance
      (**PASS**), craft (**PASS-WITH-NITS**), arch (**PASS-WITH-NITS**),
      reconciliation (**PASS**) — verdicts under `reviews/slice-03-*.md`. No
      blockers; all nits addressed inline or routed to refinement-todo.
- [x] Deviation log produced under this slice heading.
- [x] `docs/architecture.md` updated: the dispatch execution edge, the reserved
      git-ignored `<target>/.servo/dispatch/` worktree path (added beside
      `runs/` / `races/` / `triage/`), and the heartbeat-composes-loop boundary.
- [x] `docs/refinement-todo.md` updated for any decisions deferred during
      implementation (esp. the worktree-retention / GC policy and the
      does-the-loop-commit question — see Open questions).

### Deviation log

Implementation matched the ACs as written. The items below are implementer's
calls within the spec's stated latitude, assumption resolutions, and disclosed
limitations. No AC was dropped or reshaped. **168 heartbeat tests green** (112
prior + 56 new), full suite green (`test_gate.py` 75, `test_scaffold.py` 42/1
skipped, `test_loop.py` unchanged), ruff clean (0.15.17).

**Assumption resolutions (the `arch_review: true` load-bearing claims).**
- **A1 — nested worktree path: CONFIRMED by probe.** `git worktree add -B
  servo/heartbeat/<fid> .servo/dispatch/<fid> HEAD` yields a working linked
  worktree even though `.servo/` is git-ignored; the HEAD checkout carries the
  tracked source (`src.py`, a committed `oracle.sh`) but **not** `.servo/`
  (git-ignored) — which is exactly why AC4 provisioning is required.
  `git worktree remove --force` cleans up. No fallback to an out-of-tree temp dir
  was needed; `WorktreeIsolationTests` exercises the real path.
- **A2 — provisioning completeness: de-risked by the AC4 gate verification.**
  `test_incomplete_provisioning_records_env_error_and_skips` drives an oracle that
  reads a deliberately non-provisioned file (`.servo/triage/sentinel`) — it passes
  the `<target>` preflight but `exit 2`s in the worktree, and the candidate is
  recorded `env_error` and skipped, never mis-scored.
- **A3 — loop result shape:** v1 **retains** the worktree + records
  `outcome.run_id`, so the contract does not depend on the loop committing. The
  live-`claude -p` gap is unchanged from the 003 spike (tests use a deterministic
  stand-in loop).

**Implementer's calls (within spec latitude).**
- **Test seam = `SERVO_HEARTBEAT_{GATE,LOOP}_PY` env override**, not a literal
  PATH-injected binary. servo scripts are invoked as `python3 <abspath>` (loop.py
  resolves gate.py via `GATE_PATH`, not PATH), so the established `SERVO_*`
  test-hook idiom (cf. `SERVO_TEST_RUN_IDS`, `SERVO_MANAGED_SETTINGS_PATH`) is the
  faithful mechanism. The mock `loop.py` is injected via the override (logs argv +
  emits a canned summary); `gate.py` runs **for real** against a controlled
  `oracle.sh` for AC2/AC4, proving genuine deference to gate.py's taxonomy. Same
  principle as the cited 003-01 AC8 pattern (a fake stand-in so no live
  `claude -p` runs); no test makes a live call.
- **Advisory lock held across the whole pass**, not just the brief read-merge-
  write `discover` uses. AC8's `LOCK_EX | LOCK_NB` + "backs off (exit 0)" wording
  most directly supports an up-front-acquire-and-hold model, and holding it
  guarantees no *completed* loop outcome is ever lost to mid-pass contention
  (outcomes are written atomically after each candidate). Trade-off: a concurrent
  `discover` backs off for the pass duration (self-correcting; rare outside a
  double-fire). Flagged in refinement-todo.
- **Dispatch env-error → `status = tried`** (`attempts += 1`,
  `outcome.oracle_status = "env_error"`). AC7's status rule is unconditional
  ("`passed` iff `pass`, else `tried`") and recording an `outcome` implies an
  attempt was made; the one-attempt-in-v1 rule (ADR-0010) then prevents
  re-dispatch churn against a non-transient env-error (non-git target, missing
  sidecar). A human sees `tried` + `env_error` in the reviewable inbox. The
  "should a *transient* env-error stay `open` for retry?" question is in
  refinement-todo.
- **Provisioning scope = `oracle.sh` + all of `.servo/` minus
  `{runs,races,triage,dispatch}`.** The manifest does not enumerate sidecars, and
  the spec-oracle overlay vendors `checks.py`/`checks.json`/frozen baselines under
  `.servo/spec-oracles/<id>/`; copying the tree minus the volatile/recursive dirs
  captures them future-proofly, with the AC4 gate verification as the completeness
  net (A2). `dispatch/` is excluded as a recursion hazard (it *contains* the
  worktrees).
- **`dispatch` writes only `inbox.jsonl`** (the spine + the contract AC8 pins),
  not `inbox.md`. The accurate post-dispatch human read-back is
  `heartbeat.py status` (reads the jsonl); the next `discover` regenerates the
  `inbox.md` view. Minimal write surface (tightest AC10 read-only posture); noted
  in refinement-todo.
- **`--cost-ceiling` / `--max-iterations` forwarded only when provided** (else
  loop.py's own defaults — $2 / 5). Defers a heartbeat-specific per-candidate
  default to 011-04's whole-pass ceiling (the Open question).
- **No outer subprocess timeout on the loop or the gate preflight** — both
  self-bound: `loop.py` via `--max-iterations` + the per-iteration claude timeout
  + the cost ceiling; `gate.py` via its own oracle timeout
  (`DEFAULT_TIMEOUT_SECONDS = 300`, `SERVO_GATE_TIMEOUT`-overridable), so a wedged
  oracle on an attacker-influenced repo can't hang the preflight. An outer
  wall-clock cap would prematurely kill a legitimate long loop.

**Disclosed limitations (→ refinement-todo).**
- An `oracle.sh` whose **live content or mode diverges from HEAD** in the target
  makes the provisioned worktree's tracked `oracle.sh` differ from its checkout →
  loop.py's dirty-tree preflight refuses (`dirty_tree`) → recorded as a
  per-candidate env-error (safe degradation; v1 does **not** pass `--allow-dirty`
  on the unattended path). The common trigger is an **uncommitted** oracle edit; a
  subtler one is a committed-non-exec oracle made executable only in the working
  tree (provisioning's defensive `chmod +x` then diverges from HEAD's mode).
- The env-error→`tried` rule and `_remove_worktree_if_present`'s
  clobber-safety are **coupled**: a retained worktree is only ever force-removed
  for a finding that stayed `open` (never looped), because a looped finding is
  `tried`/`passed` and leaves the candidate set. If a future slice lets a
  *transient* env-error stay `open` for retry (the refinement-todo question),
  that teardown would start clobbering a worktree whose prior loop *did* run —
  resolve the two together.
- Worktree **retention is unbounded** (v1 retains every `.servo/dispatch/<fid>/`).

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` status board: spec 011 stays `IN_PROGRESS (slice
      011-03 → 011-04 next)` (via `workflow.py status-board`).

**Anti-horizontal-phasing check:** After this slice a human (or, once 011-04
lands, the scheduled `heartbeat.py run`) can take a deduped, resuming inbox and
have its **actionable findings actually attempted** — each in an isolated,
oracle-provisioned worktree, judged by the project's own oracle, with the
`passed` / `tried` outcome (score + cost + run-id) written back so the next pass
resumes and a human can review what was tried. That is the heartbeat's first
*execution* and end-to-end value on its own — the verb a user runs (`dispatch`)
and the inbox state they review both change — before the whole-heartbeat ceiling
(011-04) or the skill + Routine recipe (011-05) exist. It crosses every layer
(inbox read → gate → worktree → loop → inbox write), not internal plumbing.

**Out of scope (this slice):**
- **Whole-heartbeat cost ceiling** (011-04) — this slice forwards a *per-loop*
  ceiling and dispatches serially; aggregating discovery + Σ loop costs under one
  fail-closed ceiling, and `heartbeat.py run` (discover → dispatch), are 011-04.
- **Landing / merging a worktree's result.** The loop proposes a fix in
  isolation; deciding whether to merge the `servo/heartbeat/<finding_id>` branch
  is a human's (or a later slice's) call — never automatic (the read-only-
  proposing posture).
- **Worktree GC / retention bounding.** v1 **retains** the worktree + records its
  `run_id` (and branch) so a `passed` candidate is inspectable; bounding the
  number of retained `.servo/dispatch/` worktrees is deferred (Open questions +
  refinement-todo).
- **`race.py` alternate dispatch** (005, parked) — the target is kept pluggable
  but only `loop.py` is wired here.
- **Bounded-parallel dispatch** — v1 is serial; parallelism interacts with
  011-04's ceiling and edges toward spec 005.
- **Model-assisted candidate selection** and **retry-with-backoff for `tried`** —
  both ADR-0010 / spec-level deferrals.
- **The `/servo:heartbeat` skill + Routine-wiring recipe** (011-05).

## Assumptions

Load-bearing claims about runnable surfaces that are **not** fully probed yet —
surfaced per the spec-frame discipline (this is why `arch_review: true`). The
review/implementation pass verifies or amends each.

- **A1 — nested worktree path.** `git worktree add` into a path under the
  target's own git-ignored `.servo/dispatch/` yields a working linked worktree
  without git treating the nested path as part of the parent tree. *Plausible —
  servo itself runs from `.claude/worktrees/*` inside the repo — but the specific
  `.servo/dispatch/` nesting is unprobed. If git balks, fall back to an
  out-of-tree temp directory and record the path in `outcome`.*
- **A2 — provisioning completeness.** Copying `oracle.sh` + `.servo/install.json`
  (+ manifest sidecars) is sufficient for `gate.py <worktree>` to reproduce the
  target's composite. AC4's post-provision `gate.py` verification is the
  self-check that **de-risks** this — an incomplete copy surfaces as a worktree
  `exit 2` and the candidate is skipped, not silently mis-scored.
- **A3 — loop result shape.** A dispatched `loop.py` leaves its result in the
  worktree in a form a human can later inspect/land. Whether the loop *commits*
  is the loop's own behavior (unprobed here) and drives the worktree-retention
  question; v1 retains the worktree + records `outcome.run_id`, so the contract
  does not depend on the loop committing.

## Open questions (resolve at SPIDR-split review / against a live dispatch)

- **Worktree + result lifecycle.** retain-and-record (v1) vs. GC-on-completion
  vs. retain-only-on-`passed`. v1 retains + records; unbounded `.servo/dispatch/`
  growth is the footgun to bound in a follow-up (refinement-todo).
- **Does the dispatched loop commit its fix?** Determines whether
  `servo/heartbeat/<finding_id>` is a landable branch or the human reconstructs
  from a working-tree diff. Resolve against a live `loop.py` dispatch (the same
  live-`claude -p` gap the 003 spike open-questions note records).
- **loop vs race target (005).** Keep the dispatch target pluggable; don't
  hard-wire `loop.py` so a future `race.py` can slot in.
- **Per-loop ceiling default.** Forward loop.py's own default ($2) or pick a
  heartbeat-specific per-candidate default? Tie-break with 011-04's whole-pass
  ceiling so the two don't double-count.
