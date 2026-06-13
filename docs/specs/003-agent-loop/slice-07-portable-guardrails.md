---
status: DONE
dependencies: [003-06, adr-0008]
last_verified: 2026-06-12
---

## Slice 003-07 — portable-guardrails

**STATUS: DONE**

> ADR-0008 rebase phase, slice 2 of 3. Makes the guardrail layer portable +
> safe for unattended, scheduled, and cross-host runs.

**Goal:** Three guardrail-layer rules that let servo run the goal-driver (or the
loop-driver) safely outside an interactive Claude Code session:

1. **Vendor `gate.py`** into the target so the oracle + meta-judge resolve on a
   path **relative to `CLAUDE_PROJECT_DIR`** after a clone (ADR-0008 V4: a
   non-vendored install bakes servo's absolute path → fails open in a clone).
2. **Refuse-on-dirty-tree** preflight — halt before a run if the target's git
   working tree is dirty (ADR-0008 V4: a scheduled run inherited leftover
   uncommitted state → a spurious immediate `status=pass`).
3. **Host-scope routing** — pick the primitive-delegated path only on a Claude
   Code host with trusted hooks; otherwise route to the external-driver path
   (ADR-0008 V3 / Assumption 7).

End-to-end value: the loop runs portably and safely wherever it's invoked —
interactive, headless, scheduled, or a non-Claude host — without a human
babysitting the working tree or the host's hook policy.

**DoR:**
- ✅ [ADR-0008](../../decisions/adr-0008-loop-on-autonomy-primitives.md) Accepted; 003-06 exists.
- ✅ V4: meta-judge clone-portable **only if** `gate.py` is vendored at
  `<target>/.claude/skills/servo-quality-gate/gate.py` (relative). spec 004's
  `hook.py` already prefers that path; this slice makes vendoring a
  guardrail-layer responsibility for goal/Routine runs.
- ✅ V4: scheduled runs reusing a persistent tree inherit dirty state.
- ✅ V3: a hook-restricted host (`disableAllHooks` / `allowManagedHooksOnly`)
  disables **both** `/goal` and the project meta-judge → only the external
  driver (loop.py, no hooks) survives. The `adr-0008-experiments/v3_audit_env.py`
  settings-hierarchy check is the reference logic to productionize.
- ⏳ Verify at implementation: the deterministic host-support probe (is `/goal`
  available; are hooks enabled) is reliable enough to auto-route on.

**Acceptance Criteria:**

1. **Vendor gate.py (idempotent).** A driver preflight ensures
   `<target>/.claude/skills/servo-quality-gate/gate.py` exists (copies servo's
   `gate.py` when absent; no-op when present and current). Goal/Routine runs use
   this relative path; the meta-judge install inherits it.
2. **Refuse-on-dirty-tree.** Before a run, if `<target>` is a git repo with a
   dirty working tree (uncommitted changes to tracked files), the driver refuses
   with rc=2 / `reason=dirty_tree`; the breadcrumb names the dirty paths.
3. **Dirty-tree opt-out + non-git skip.** `--allow-dirty` bypasses AC2 for
   intentional dirty runs; a non-git target skips the check entirely (no false
   refusal). Both pinned by tests.
4. **Host-scope routing.** A deterministic host-support check decides the path:
   `/goal` available AND hooks permitted (not `disableAllHooks`, not
   `allowManagedHooksOnly`) → goal-driver eligible; otherwise the driver routes
   to `--driver loop` (external driver) and logs the downgrade reason. In `auto`
   mode the best available path is chosen; an explicit `--driver goal` on an
   unsupported host refuses (per 003-06 AC6).
5. **Auditable policy read.** The routing in AC4 reuses the settings-hierarchy
   inspection (`v3_audit_env.py` logic, productionized into the guardrail layer)
   so the routing decision is deterministic and independently auditable
   (`loop.py --explain-routing <target>` prints the verdict + the layer that
   forced it).
6. **Defaults are safe.** Dirty-tree refusal and host-scope routing are **on by
   default** (fail-closed / fail-safe), consistent with spec 003's
   "brakes wired in from day one" posture.

**DoD:**
- [x] All ACs pass; full suite green. Tests: dirty-tree refusal + `--allow-dirty`
      bypass + non-git skip; vendoring idempotence; routing picks loop-driver
      under a simulated `disableAllHooks` settings fixture (mirrors
      `adr-0008-experiments` V3). (full project suite 782 passed / 1 skipped;
      `test_loop.py` 230 passed; ruff clean.)
- [x] Per-AC coverage under `skills/agent-loop/test_loop.py` (44 new tests:
      `VendorGate*`, `DirtyTree*`, `RoutingUnitTests`, `HostScopeRoutingDispatchTests`,
      `ExplainRoutingTests`, `SafeDefaultsTests`).
- [x] `docs/architecture.md` "Runtime artifacts" notes the vendored-gate.py
      requirement + (cross-linked) the host-scope routing matrix; the
      Agent-loop guardrails table gains a dirty-tree row.
- [x] Reviewed by `jig:reviewer` (compliance + craft, both PASS — see
      `reviews/slice-07-{compliance,craft}.md`); deviation log produced below.
- [x] `arch_review` — **not triggered**: the host-probe seam only *reads* the
      settings hierarchy and *reuses* (does not modify) spec 004 `hook.py`'s
      vendored-gate path convention, so no module boundary shifts (confirmed by
      the compliance review).

**Anti-horizontal-phasing check:** After this slice the driver refuses to run
against a dirty tree, vendors its own oracle for portability, and picks the
right path for the host — all observable from the CLI (`--explain-routing`,
the refusal, the downgrade log). End-to-end behavior, not internal-only plumbing.

### Deviation log (after reconciliation)

Implemented in `skills/agent-loop/loop.py` with per-AC tests in `test_loop.py`
(44 new: `VendorGateUnitTests`/`VendorGateIntegrationTests`,
`DirtyTreeLoopTests`/`DirtyTreeGoalTests`/`DirtyTreeUnitTests`, `RoutingUnitTests`,
`HostScopeRoutingDispatchTests`, `ExplainRoutingTests`, `SafeDefaultsTests`) and
docs in `SKILL.md` + `docs/architecture.md`. All six ACs met; full project suite
**782 passed / 1 skipped**; `test_loop.py` **230 passed**; ruff clean. Reviewed by
`jig:reviewer` — compliance + craft both **PASS** (`reviews/slice-07-*.md`).

Deviations and decisions worth recording:

1. **`--driver` default flipped `loop` → `auto`.** 003-06 shipped `loop` as the
   default for backward-compat; this slice makes `auto` the default to satisfy
   AC6 ("host-scope routing on by default") and ADR-0008's "external driver
   demoted from default." `auto` is a **safe superset** — it fail-safe-downgrades
   to `loop` whenever `/goal` is unavailable, so no host loses functionality.
   The retained loop-driver tests were pinned to `--driver loop` (in the
   `_run_loop` helper + the two signal-test `_spawn` helpers) so they keep
   targeting the driver they exercise under the new default.
2. **Uniform eligibility predicate.** `_decide_route` computes one predicate —
   `/goal` available (`claude --version` ≥ `GOAL_MIN_VERSION` = 2.1.139) AND
   hooks permitted (settings audit) — and uses it for both `auto` routing AND
   the explicit-`goal` refusal (per 003-06 AC6). The version probe is the
   deterministic, test-hermetic signal for "/goal available"; the test mock's
   version was bumped to `2.1.175` so it stands in for a `/goal`-capable claude.
3. **Dirty-tree = tracked-file changes only.** AC2's wording ("uncommitted
   changes to tracked files") is honored literally: untracked files (`??`) don't
   trigger the refusal — which also means servo's own `.servo/` run artifacts and
   the freshly-vendored (untracked) `gate.py` never self-trip the brake on a
   later run. Loop-mode `--resume` **skips** the dirty check (a resumed loop's
   tree is legitimately dirty from prior agent mutations); only fresh runs refuse.
   In `run_goal_loop` the dirty-tree refusal runs **before** vendoring, so
   vendoring can't dirty the tree ahead of its own check.
4. **New closed-set reasons.** `dirty_tree` (shared preflight, both drivers) and
   `gate_vendor_failed` (goal-driver fail-closed when the clone-portable copy
   can't be written). `_invoke_gate` + `_compose_goal_prompt` gained a `gate_path`
   param (default servo's `GATE_PATH`; the goal driver passes the vendored copy).
5. **`SERVO_MANAGED_SETTINGS_PATH` env seam.** `_managed_settings_paths` honors
   this override (a path, or empty = "no managed layer"); production reads the
   real OS paths. Introduced so subprocess-level routing tests stay hermetic on
   MDM-managed CI hosts — a new (test-motivated) env var on the loop's surface.
6. **arch_review not triggered.** The host-probe seam only *reads* the settings
   hierarchy and *reuses* spec 004 `hook.py`'s vendored-gate path convention
   without modifying `hook.py`, so no module boundary shifts (confirmed by the
   compliance review). The ADR-0008 hard constraint holds: routing selects only
   *which driver* runs; the authoritative final `gate.py` + the fail-closed
   `oracle_disagreement` branch keep `oracle.sh` the sole authority.
7. **Craft nits addressed inline** (all `[Low]`/`[nit]`, non-blocking): the
   managed-settings hermeticity gap (env seam + an end-to-end managed-tier test);
   an inline comment on the intentional double `claude --version` probe; removal
   of a redundant `gate = gate_path` rebind; a stale test section-header comment
   and a dead `_write_settings` helper.

Review-evidence note: the first compliance pass mis-judged the slice as
unimplemented because it reasoned from git history (HEAD is still 003-06 — this
work is uncommitted pre-landing, as for 003-06). The craft pass read the working
tree and passed; the compliance pass was re-run with an explicit read-the-worktree
instruction and passed. No ADR or `docs/conventions.md` change required; the state
schema stays `state_schema_version=1` (no goal-state shape change in this slice).
