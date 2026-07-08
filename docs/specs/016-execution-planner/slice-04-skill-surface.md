---
status: DONE
dependencies: [016-01, 016-02, 016-03, 007-05]
last_verified: 2026-07-08
frame_review: true
---

## Slice 016-04 — skill-surface

**Goal:** Ship the `/servo:execution-planner` skill surface (house-style
SKILL.md: fire / Do-NOT-fire triggers, sibling pointers, refusal table, Q&A)
plus a `--json` output mode on `execution_plan.py compile`, so the ADR-0016
Compile→Run planner is discoverable, self-explaining, and scriptable. This is
the **Interface** axis over the already-shipped 016-01/02/03 engine — it builds
no new plan logic and wires no new gate. Closes spec 016's active work.

> **Re-scoped by [ADR-0018](../../decisions/adr-0018-suitability-gates-compile-not-heartbeat.md).**
> The original sketch also had the heartbeat "reuse a plan across passes." That is
> **removed**: heartbeat findings are spec-less, so a per-`spec-id` plan has
> nothing to bind to at the dispatch boundary. This slice is the skill surface
> only.

> **Install posture reframed from the original goal (see `## Assumptions` A1).**
> The pre-SPIDR goal said "+ the install-contract entry (007)". The
> [015-04 follow-up](../015-edd-suitability/slice-04-skill-and-explain.md)
> established the opposite for a Compile-phase host tool: `/servo:edd-suitability`
> and `/servo:spec-oracle` are **not** in `install-contract.json`
> `required.skills` because nothing in the vendored *unattended runtime* invokes
> them — they run from the full plugin against a target. `execution_plan.py` is
> the same shape: its only runtime consumer, `loop.py --plan`, is already vendored
> as `agent-loop`. So AC4 registers the surface as a **plugin-discovered** skill
> (shipped via the release zip's `include: skills/`) and deliberately does **not**
> add a `required.skills` entry. This reverses the written goal, so it is
> surfaced as a load-bearing assumption for the frame-critique pass to test.

**DoR:**
- ✅ **016-01 / 016-02 / 016-03 DONE + landed on `main`** — `execution_plan.py
  compile` emits/clamps/preserves the plan headlessly; this slice wraps that
  stable helper in a skill surface and adds a `--json` view. No plan logic is
  added or changed.
- ✅ **007-05 DONE** — `scripts/verify_install_surfaces.sh` exists as the one
  command that gates the plugin / zip / scaffold surfaces in CI, so AC4's
  "surfaces stay green" is checkable.
- ✅ Servo SKILL.md house style is established (`/servo:edd-suitability`,
  `/servo:spec-oracle`, `/servo:heartbeat`): fire / Do-NOT-fire triggers,
  sibling-helper table, refusal table, Q&A, "where it sits" section.

**Acceptance Criteria:**

1. **Skill surface (house style).** `skills/execution-planner/SKILL.md` ships
   with `name: servo:execution-planner` and house-style **fire** triggers
   ("compile the execution plan for this spec" / "produce the Compile→Run
   handoff" / "emit `plan.json` for this spec") and explicit **Do-NOT-fire**
   bounds delegating to siblings: the suitability verdict → `/servo:edd-suitability`
   (015); AC classification / the spec-oracle overlay → `/servo:spec-oracle`
   (006); *running* the loop / *consuming* the plan → `/servo:agent-loop` (003);
   scoring a build → `/servo:quality-gate` (002). It carries the sibling-helper
   table (the `compile` role, keyed to 016-01/02/03), a Q&A-before-compiling
   block (target path / spec path / output mode), and a "where the plan sits"
   section placing `compile` as the last Servo Compile step feeding `loop.py
   --plan` (ADR-0016), reciprocal to `state.json` (ADR-0004). *Test:*
   `SkillSurfaceTriggerTests`.

2. **Refusal table + closed exit contract.** SKILL.md documents every exit-2
   `reason` `execution_plan.py compile` can emit —
   `spec_missing`, `suitability_missing`, `suitability_malformed`,
   `suitability_not_suitable`, `manifest_missing`, `manifest_malformed`,
   `oracle_missing`, `plan_edit_detected` — each with its actionable next step,
   and states the closed `{0,2}` exit contract (0 = plan emitted; 2 =
   environment error with a structured stderr reason and no torn artifact; never
   exit 1). *Test:* `RefusalTableTests` — asserts every `reason` string the
   helper defines appears in SKILL.md (guards against the table drifting out of
   sync with the code).

3. **Human + `--json` output mode.** `compile` keeps its existing human line by
   default (`servo: execution plan for <id> compiled -> <path>`) and, under
   `--json`, prints a structured **outcome envelope** to stdout —
   `{schema_version, spec_id, status: "compiled", plan_path, provenance, driver,
   budget}` — enough for a scripted Compile→Run caller to locate and gate on the
   plan without re-reading `plan.json`. Env-error refusals are unchanged in
   **all** modes (structured stderr `reason` + exit 2, no JSON envelope, no torn
   artifact); `--json` only shapes the **success** output (mirrors 015-04's
   "env errors unchanged under `--json`"). *Test:* `OutputModeTests` — asserts
   the human default is unchanged, the `--json` envelope shape + keys, and that a
   refusal under `--json` still prints the stderr reason and exits 2.

4. **Install posture — plugin-discovered, not vendored.** `execution-planner` is
   surfaced as a plugin skill (SKILL.md present in `skills/execution-planner/`,
   already shipped in the release zip via the contract's `include: skills/`) and
   is **deliberately not added** to `.claude-plugin/install-contract.json`
   `required.skills`: it is a Compile-phase host tool whose only unattended-runtime
   consumer, `loop.py`, is already vendored as `agent-loop` — mirroring the
   `/servo:edd-suitability` and `/servo:spec-oracle` posture (015-04 follow-up).
   SKILL.md states this "host / Compile-phase tool, not vendored into a scaffolded
   runtime" posture explicitly. *Test:* `InstallPostureTests` — asserts
   `execution-planner` is **absent** from `required.skills` and the posture note
   is present in SKILL.md; DoD runs `verify_install_surfaces.sh` and it stays
   green.

**DoD:**
- [x] All ACs pass; `skills/execution-planner/` suite green (47 passed). Full
      repo suite: 1373 passed, 1 pre-existing **environmental** failure in an
      untouched skill (`content-fidelity` — the sandbox raises `PermissionError`
      instead of `FileNotFoundError` when exec-ing a nonexistent binary; zero
      diff overlap with this slice), not a regression.
- [x] Implementer test coverage exercises each AC (`SkillSurfaceTriggerTests`,
      `RefusalTableTests`, `OutputModeTests`, `InstallPostureTests`); the
      `--json` refusal path and the human-default path are both covered.
- [x] `ruff check skills/execution-planner/` clean (pinned 0.15.17);
      `execution_plan.py` stays Python-3.9-compatible (`from __future__ import
      annotations` present).
- [x] `scripts/verify_install_surfaces.sh` green across plugin / zip / scaffold
      (106/106).
- [x] Reviewed by jig compliance + craft passes (recorded under `reviews/`, both
      PASS); frame-critique pass run (`frame_review: true`) and PASS.
- [x] Deviation log + reconciliation sweep produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md`: no **new** decision deferred by this slice; the
      pre-existing `_load_evaluation_model` item (~line 570) was triggered but
      left open with its trigger intact (deviation-log item 7).

### Close-out (post-DONE)
- [x] `docs/specs/README.md` regenerated by `workflow.py status-board`
      (idempotent; the 016-04 surface invariants live in the board Note).
- [x] **This slice closes spec 016's active work (016-05 stays DEFERRED).**
      Spec 025 compress-on-close-out applied: surface invariants folded into the
      016-04 board Note; the spec.md status blockquote + SPIDR row + overview
      provisional-skill line reconciled to `/servo:execution-planner` DONE. No
      Skills table in the board to update; no root `CLAUDE.md` / `AGENTS.md`.
- [x] Persist execution-planner surface vocabulary to memory (session
      auto-memory updated; no project `docs/memory/glossary.md` term gap — the
      execution-planner vocabulary was already seeded by 016-01/02/03).

**Anti-horizontal-phasing check:** After this slice lands, a user can ask
"compile the execution plan for this spec", get a discoverable skill that runs
`execution_plan.py compile`, and receive either a human confirmation or a
machine-readable `--json` envelope they can pipe into `loop.py --plan` — an
end-to-end, user-facing Compile→Run capability, not intermediate state.

## Assumptions

Load-bearing claims a future agent (or the frame-critique pass) should test.

- **A1 — install posture reverses the written goal (the one worth an adversarial
  look).** I claim `execution-planner` should **not** get a `required.skills`
  entry, contradicting the pre-SPIDR goal's "+ the install-contract entry (007)".
  Grounding: `install-contract.json` `required.skills` today lists only
  `scaffold-init`, `quality-gate`, `agent-loop`, `oracle-hook`, `heartbeat`;
  `spec-oracle`, `edd-suitability`, `design-eval`, and `content-fidelity` — all
  Compile-phase / host tools — are absent, and the 015-04 follow-up explicitly
  reverted vendoring `edd-suitability` because "no vendored runtime skill invokes
  it." `execution_plan.py` matches that shape (host-side compiler; `loop.py`
  consumes a plan *path*, it never runs the compiler). **Risk if wrong:** a real
  scaffold-runtime consumer of `execution_plan.py` exists that I've missed, in
  which case AC4 should vendor it instead.
- **A2 — surfaces stay green un-registered.** I assume `verify_install_surfaces.sh`
  passes with a new SKILL.md present in `skills/execution-planner/` that is *not*
  in `required.skills`. Backed by the `edd-suitability` precedent (it ships
  exactly this way, green). Verified for real at DoD by running the script.
- **A3 — `--json` breaks no consumer.** I assume no current caller parses
  `compile`'s stdout human line, so adding an opt-in `--json` flag is
  non-breaking. The only landed consumer, `loop.py --plan` (016-02), reads
  `plan.json` from disk, not `compile`'s stdout. Verified by grep at
  implementation time.

## Kill criteria

- If a vendored runtime skill (or a scaffold-mode fixture) is found to invoke
  `execution_plan.py`, A1 is falsified — vendor the skill into `required.skills`
  and re-frame AC4.
- If `--json` on the success path cannot be added without changing the human
  default or the env-error contract, AC3 is mis-scoped — split the output-mode
  work out and ship the SKILL.md alone.

### Deviation log (after reconciliation)

Original ACs preserved above; the implementation deviated/extended as follows:

1. **Install posture reversed the written goal (A1) — frame-critique-validated.**
   The pre-SPIDR goal said "+ the install-contract entry (007)". AC4 instead
   registers `execution-planner` as a **plugin-discovered** skill (shipped via
   the release zip's `include: skills/`) and deliberately does **not** add a
   `required.skills` entry — mirroring the 015-04 follow-up for Compile-phase
   host tools. The pre-implementation frame-critique pass
   ([reviews/slice-04-frame-critique.md](reviews/slice-04-frame-critique.md),
   PASS) independently confirmed the frame: `install-contract.json`
   `required.skills` excludes every Compile-phase tool; `loop.py --plan` reads
   `plan.json` from a path and never invokes `execution_plan.py`; per ADR-0018
   the heartbeat is spec-less, so no unattended-runtime path compiles a plan.
2. **Provisional skill name `/servo:execution-plan` → `/servo:execution-planner`.**
   Realized to match the existing `skills/execution-planner/` directory
   (committed by 016-01/02/03) and servo's dir==skill-name convention (every
   sibling matches). The spec.md core-model blockquote's provisional
   `/servo:execution-plan` is superseded by `/servo:execution-planner`.
3. **ADR-0018 heartbeat plan-reuse removed** (carried forward from the DEFERRED
   stub) — the original sketch's "heartbeat reuses a plan across passes" is
   dropped; heartbeat findings are spec-less.
4. **`--json` is a success-path-only envelope.** AC3 shapes only the success
   output; env-error refusals keep the closed stderr `reason` + exit 2 in all
   modes (the `EnvError` handler precedes the `args.json` branch — the invariant
   is enforced by control-flow, not merely by test). Mirrors 015-04's "env
   errors unchanged under `--json`". The envelope `schema_version` reuses the
   plan's `SCHEMA_VERSION` (1); a future envelope-only schema bump would need to
   decouple them (logged, not blocking).
5. **Module docstring synced in-pass.** Both review passes flagged the
   `execution_plan.py` docstring (slice-attribution + Usage line) omitting the
   016-04 `--json` addition; fixed during review (docstring now names 016-04 and
   the Usage line shows `[--json]`).
6. **Deferred nits (non-blocking, logged not fixed):** test fixtures are
   duplicated from the sibling `test_execution_plan.py` — idiomatic per the
   edd-suitability self-contained-module precedent (a shared `_fixtures.py` would
   DRY them if servo ever adopts one); a dead `threshold=` param in the test's
   `_make_target` was carried from the sibling. None warrant a refinement-todo
   entry (polish, not deferred decisions).
7. **Pre-existing 016 debt triggered but deferred (scope).** Reconciliation's
   refinement-todo sweep surfaced the open item *"execution-planner's
   evaluation_model still reads the pre-ADR-0023 spec-oracle path"* (~line 570),
   whose trigger is "the next time spec 016 is touched." The weak trigger fired,
   but the fix is **plan logic** (`_load_evaluation_model` path resolution),
   explicitly **outside 016-04's reviewed Interface-only scope**, and the item
   itself asks for "its own tests, not bolted onto" another slice. Bolting it on
   would contaminate the diff both review passes validated as
   "no plan-assembly logic touched." Disposition: **deferred.** The durable
   record is the still-open `docs/refinement-todo.md` item (left intact with its
   trigger) — that is what a future session acts on; a session-side task chip was
   also raised as a convenience. The fix belongs in a dedicated 016 slice /
   bug-fix with a regression test on the post-019-02 layout, per the item's own
   "its own tests, not bolted onto" clause.

### Reconciliation sweep

Drift-prone surfaces checked (`updated` / `no-op` / `deferred`):

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `README.md` | `no-op` | Slice adds a plugin skill + a CLI output mode; the project front door is unaffected. |
| `docs/specs/README.md` | `deferred` | Regenerated by `workflow.py status-board` at DONE close-out (post-RECONCILED). |
| `docs/specs/016-execution-planner/spec.md` | `deferred` | Status blockquote + SPIDR row reconciled at close-out (the compress-on-close-out step); the frontmatter `status:` is auto-rolled-up by `transition`. |
| `docs/product-vision.md` | `no-op` | Has `## Design principles` (compliance pass verified no violation); no `## Use cases` section, so the advisory coverage check is a no-op. |
| `docs/architecture.md` | `no-op` | No module boundary or public contract changed — additive skill surface + CLI output mode over the existing 016-01/03 engine (same posture as 015-04). No ADR: implements existing ADR-0016 / ADR-0018 and applies the established 015-04 host-tool-not-vendored posture (not a new load-bearing decision with rejected alternatives). |
| Primer surfaces: `CLAUDE.md` / `AGENTS.md` / scaffold templates | `no-op` | No root `CLAUDE.md` / `AGENTS.md` in this repo; the status-board Notes column is the primer surface, updated at close-out. |
| `docs/inbox.md` | `no-op` | Swept for 016 / execution-plan items — none. |
| `docs/refinement-todo.md` | `deferred` | The open item *"execution-planner's evaluation_model still reads the pre-ADR-0023 spec-oracle path"* (~line 570) was triggered by touching spec 016 but is out of 016-04's Interface-only scope; deferred to a dedicated follow-up task (deviation-log item 7). Item left open. No new deferred decisions from this slice. |
| `docs/memory/**` | `deferred` | Execution-planner surface vocabulary persisted at close-out via memory-sync. |
| `docs/decisions/README.md` / ADR index | `no-op` | No ADR added or amended; the slice implements ADR-0016/0018 and applies the 015-04 precedent. |
| `.claude-plugin/install-contract.json` | `no-op` | Deliberately unmodified per AC4 (the not-vendored posture); `verify_install_surfaces.sh` green with the new SKILL.md present (106/106). |
