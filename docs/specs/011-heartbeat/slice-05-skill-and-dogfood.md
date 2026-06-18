---
status: DONE
dependencies: [011-04, adr-0010, adr-0012]
last_verified: 2026-06-18
---

## Slice 011-05 — skill-and-dogfood

**STATUS: DONE**

**Goal:** `/servo:heartbeat` SKILL.md — **Tier-2 explicit-opt-in** framing, the
read-only-discovery promise, the whole-heartbeat-ceiling warning up front, the
refusal table, and the **Routine-wiring recipe** (cron / CI `schedule:` /
scheduled agent). Plus an end-to-end dogfood driving the real discover -> triage
-> preflight -> worktree -> loop -> record chain on a fixture target.

**SPIDR split:** Interface + Path/Data capstone. The user-facing interface is
the named skill and scheduler recipe; the evidence path is one deterministic
fixture target that exercises the shipped heartbeat path end to end. This is not
a new feature cascade: it proves the existing 011-01..04 capabilities are safe,
documented, installable, and scheduler-ready.

**DoR:**
- [x] 011-01..04 DONE: `discover`, `status`, `dispatch`, and `run` all exist and
      are covered by `skills/heartbeat/test_heartbeat.py`.
- [x] ADR-0010 and ADR-0012 Accepted: the inbox schema and whole-heartbeat cost
      semantics are stable enough for the skill surface to document.
- [x] The install-surface verifier contract exists at
      `.claude-plugin/install-contract.json`, and sibling skill-surface tests
      (`oracle-hook`, `spec-oracle`) provide the anti-greediness pattern.
- [x] Dogfood can run without live network or a live `claude -p`: `gh`/signal
      discovery and the loop are deterministic stand-ins, while git worktrees
      and `gate.py` remain real.

**Acceptance Criteria:**

1. **Skill exists and ships across install surfaces.** `skills/heartbeat/SKILL.md`
   defines `/servo:heartbeat` with `name: servo:heartbeat` and a narrow
   `description`, documents that the helper is
   `${CLAUDE_PLUGIN_ROOT}/skills/heartbeat/heartbeat.py`, and
   `.claude-plugin/install-contract.json` lists the `heartbeat` skill with
   `SKILL.md` + `heartbeat.py` so plugin, zip, and scaffold installs include it.
   *Test:* `skills/heartbeat/test_skill_surface.py` frontmatter + install-contract
   assertions, plus the install-surface verifier.
2. **Trigger bounds are explicit.** The description fires on scheduled heartbeat
   requests (`run heartbeat`, `set up a scheduled heartbeat`, `Routine`, `cron`,
   `GitHub Actions schedule`, `read the heartbeat inbox`, `dispatch heartbeat
   findings`) and does **not** fire on sibling territory: one-shot oracle scoring
   (`/servo:quality-gate`), manual iteration (`/servo:agent-loop`), project
   scaffolding (`/servo:scaffold-init`), hook installation (`/servo:oracle-hook`),
   spec overlays (`/servo:spec-oracle`), or design eval (`/servo:design-eval`).
   The Do-NOT-fire block points to the correct sibling skill for each case.
   *Test:* surface tests split the description at the Do-NOT section and assert
   trigger placement, not just global substring presence.
3. **Tier-2 opt-in and guardrails are up front.** SKILL.md states the heartbeat
   is Tier-2 / explicit opt-in because a schedule can choose work and spend
   money. It names all four guardrails before operational examples: discovery is
   read-only and writes only `.servo/triage/`; dispatch/run require
   refuse-without-oracle preflight; discovered issue/commit text is untrusted DATA
   in loop prompts; and `run --cost-ceiling` is one whole-heartbeat ceiling, not a
   per-loop multiplier. It also states servo ships a command and recipes, not a
   daemon or scheduler.
   *Test:* surface tests assert each guardrail phrase and the Tier-2 explicit
   opt-in/never-auto-install wording.
4. **Q&A flow before running or wiring a schedule.** SKILL.md tells the agent to
   confirm the target path, whether the user wants `discover`, `status`,
   `dispatch`, or `run`, the whole-heartbeat `--cost-ceiling`, optional
   `--max-candidates` / `--max-iterations`, whether the target is
   servo-scaffolded before any execution edge, and whether `gh`/git credentials
   are available in the scheduler environment. It must distinguish that
   `discover`/`status` can operate without an oracle, while `dispatch`/`run`
   refuse before spawning a loop if the oracle preflight fails.
   *Test:* surface tests assert the Q&A terms and the discover-vs-dispatch
   prerequisite distinction.
5. **Refusal table and recovery guidance.** SKILL.md documents the closed `{0,2}`
   contract for `discover`, `status`, `dispatch`, and `run`, including
   `target_missing`, `target_not_directory`, `triage_dir_unwritable`,
   `schema_version_unsupported` / mixed schema, `lock_contended` as a successful
   no-op, and gate-preflight refusals (`manifest_missing`, `oracle_missing`,
   `oracle_not_executable`) for dispatch/run. It tells the agent to surface
   refusals verbatim and offer the matching recovery, never silently retry or
   loosen a guardrail.
   *Test:* surface tests assert the refusal table names the reasons and recovery
   routes (`scaffold-init`, inspect `.servo/triage/`, re-run later on lock
   contention).
6. **Routine-wiring recipes are concrete but non-mutating by default.** SKILL.md
   includes copy-ready recipes for: local cron/launchd/systemd-style invocation,
   GitHub Actions `schedule:` invocation, and a scheduled-agent/Routine prompt.
   Each recipe invokes `heartbeat.py run <target> --cost-ceiling <usd>` (with
   optional caps), states that the scheduler owns the clock and credentials, and
   warns that servo does not create or install the schedule unless the user
   explicitly asks. The CI recipe preserves the same guardrails and avoids
   checking in `.servo/triage/` output unless the project deliberately chooses
   to archive it.
   *Test:* surface tests assert the recipes contain `cron`, `schedule:`, and
   `Routine`/scheduled-agent wording, plus the non-mutating-by-default statement.
7. **Dogfood happy path proves the real chain.** A deterministic test target is
   a real git repository with a committed source file, a real executable
   `oracle.sh`, and `.servo/install.json`. The test uses mock `gh` output to
   create at least one actionable CI finding, invokes the real
   `heartbeat.py run`, uses the real `gate.py` preflight and real git worktree
   creation/provisioning, injects only the `loop.py` leaf via
   `SERVO_HEARTBEAT_LOOP_PY`, and asserts: the inbox records a v2 finding,
   `.servo/dispatch/<finding_id>/` exists on the `servo/heartbeat/<finding_id>`
   branch, the loop prompt frames discovered text as DATA, the outcome shape is
   recorded, and `status` becomes `passed` when the mock loop reports
   `final_oracle_status=pass`.
   *Test:* `HeartbeatDogfoodTests` (or equivalent) in
   `skills/heartbeat/test_heartbeat.py`; no live network, no live `claude -p`.
8. **Dogfood budget halt proves scheduled safety.** The same dogfood harness
   covers an over-budget run: multiple actionable findings are discovered, the
   first mock loop spends the whole/overshot budget, `heartbeat.py run` exits 0
   with a whole-heartbeat-ceiling breadcrumb, and at least one remaining
   actionable finding stays `open` for the next heartbeat. This is the spec-level
   DoD scenario, not only a unit test of the accounting helper.
   *Test:* dogfood assertion or focused `HeartbeatRunCostCeilingTests` extension
   tied from the 011-05 AC map.
9. **Docs close the public surface.** README marks `/servo:heartbeat` as
   Spec 011 **DONE** at close-out; `docs/product-vision.md` backlog #7 moves
   from DRAFT/in-progress to DONE; `docs/architecture.md` has no stale
   "when later specs land" language for heartbeat and reflects the shipped
   skill/install surface; `docs/specs/README.md` is regenerated. `.gitignore`
   already reserves `.servo/`, so no narrower `.servo/triage/` rule is added
   unless the implementation discovers a real gap.
10. **Install surfaces remain green.** Adding the skill does not regress plugin,
    zip, or project-local scaffold verification. The scaffolded runtime must
    vendor `servo-heartbeat/SKILL.md` and `heartbeat.py` without tests or docs,
    matching the data-driven install contract.

**DoD:**
- [x] All ACs pass; focused heartbeat surface/dogfood tests green.
- [x] `uvx pytest skills/heartbeat/test_heartbeat.py
      skills/heartbeat/test_skill_surface.py` green.
- [x] `scripts/verify_install_surfaces.sh` green, or failures are triaged with
      a reason and a narrower verifier command substituted in the deviation log.
- [x] Compliance + craft reviews recorded under
      `docs/specs/011-heartbeat/reviews/`.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review recorded and passed.
- [x] Close-out docs completed: README, product vision, architecture, status
      board, and spec 011 rollup.
- [x] `/jig:memory-sync` run if implementation surfaces new conventions,
      dead-end learnings, or workflow notes.

### Close-out (post-DONE) — spec 011 complete
- [x] Spec 011 top-level DoD ticked.
- [x] README skill table row: `/servo:heartbeat` -> Spec 011 **DONE**.
- [x] `docs/product-vision.md` backlog #7 -> Spec 011 **DONE**.
- [x] `docs/architecture.md` checked for shipped heartbeat wording and no stale
      "future/later" phrasing.
- [x] `docs/specs/README.md` status board regenerated after the DONE transition.

**Anti-horizontal-phasing check:** This slice ships the user-facing skill entry
point, the scheduler wiring recipe, and a real end-to-end dogfood. After it, a
user can explicitly opt into a scheduled heartbeat, understand its guardrails,
wire it into their scheduler, and see the shipped implementation proven across
discovery, triage, oracle preflight, worktree isolation, loop dispatch, outcome
recording, and whole-pass budget halt.

### Deviation log (after reconciliation)

Original ACs above are preserved. Implemented as specified; deviations and
scope calls:

- **Deliverables.** Added `skills/heartbeat/SKILL.md` (frontmatter trigger
  bounds, Tier-2 opt-in, four guardrails, modes, Q&A, refusal table, and cron /
  GitHub Actions `schedule:` / Routine recipes); registered `heartbeat`
  (`SKILL.md` + `heartbeat.py`) in `.claude-plugin/install-contract.json`; added
  `skills/heartbeat/test_skill_surface.py` (17 tests) and extended
  `skills/heartbeat/test_heartbeat.py` with `HeartbeatDogfoodTests` (2 tests).
  Close-out docs updated README, product vision, and architecture live prose.

- **Runtime implementation.** No `heartbeat.py` code change was needed. The
  shipped 011-01..04 runtime already satisfied the capstone chain; 011-05
  adds the named skill surface, packaging registration, dogfood evidence, and
  close-out docs.

- **Dogfood harness.** The dogfood uses a real git target, real `gate.py`
  preflight, real worktree creation/provisioning, and the real
  `heartbeat.py run` CLI. It keeps `gh` and `loop.py` deterministic: `gh` is a
  mock signal source, and `loop.py` is injected through `SERVO_HEARTBEAT_LOOP_PY`
  so the test makes no live network call and never invokes `claude -p`. The
  happy path records `passed`; the budget-halt path proves remaining actionable
  findings stay `open`.

- **Install-surface classifier fix.** Adding a vendored heartbeat skill exposed
  six scaffold-mode `heartbeat.py` example commands in `SKILL.md`. They are
  scheduler/credential/oracle-shaped and should not run as bare scaffold smoke
  tests, so `scripts/test_scaffold_runtime.py` now classifies `heartbeat.py` as
  illustrative alongside `gate.py`, `loop.py`, and `hook.py`.

- **Verification evidence.**
  - `python3 skills/heartbeat/test_skill_surface.py` — 17 passed.
  - `python3 skills/heartbeat/test_heartbeat.py HeartbeatDogfoodTests` — 2
    passed.
  - `python3 skills/heartbeat/test_heartbeat.py` — 175 passed.
  - `uvx pytest skills/heartbeat/test_heartbeat.py
    skills/heartbeat/test_skill_surface.py` — 192 passed.
  - `bash scripts/verify_install_surfaces.sh` — 102 passed; plugin, zip, and
    scaffold surfaces OK.
  - `python3 -m compileall -q skills/heartbeat/heartbeat.py
    skills/heartbeat/test_heartbeat.py skills/heartbeat/test_skill_surface.py
    scripts/test_scaffold_runtime.py` — passed.

- **Review evidence.** Compliance review:
  `docs/specs/011-heartbeat/reviews/slice-05-compliance.md` — pass. Craft
  review: `docs/specs/011-heartbeat/reviews/slice-05-craft.md` — pass.
  Reconciliation review:
  `docs/specs/011-heartbeat/reviews/slice-05-reconciliation.md` — pass.

- **Memory-sync.** `memory.py summary .` reported zero glossary entries, zero
  learnings, and zero inbox items; no new memory-worthy terms/learnings were
  introduced. `memory.py team-check .` surfaced the existing non-blocking
  advisory that the repo has 4 git contributors but no `docs/memory/people.md`;
  no people.md bootstrap/opt-out decision was made inside this slice.

- **No new deferrals.** The slice did not add a refinement-todo entry. Existing
  heartbeat follow-ups in `docs/refinement-todo.md` remain unchanged.

- **DONE transition note.** `workflow.py transition ... DONE` revalidated the
  review evidence but refused on `adr-0010` because jig's ADR dependency gate
  still looks for a prose `## Status` section and does not read ADR frontmatter.
  ADR-0010 and ADR-0012 both have accepted frontmatter status; per the local
  heartbeat convention used by 011-02/011-03, DONE was hand-set after verifying
  the ADR dependencies.
