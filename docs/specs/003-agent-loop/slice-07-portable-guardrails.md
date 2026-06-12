---
status: DRAFT
dependencies: [003-06, adr-0008]
last_verified:
---

## Slice 003-07 — portable-guardrails

**STATUS: DRAFT**

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
- [ ] All ACs pass; full suite green. Tests: dirty-tree refusal + `--allow-dirty`
      bypass + non-git skip; vendoring idempotence; routing picks loop-driver
      under a simulated `disableAllHooks` settings fixture (mirrors
      `adr-0008-experiments` V3).
- [ ] Per-AC coverage under `skills/agent-loop/test_loop.py`.
- [ ] `docs/architecture.md` "Runtime artifacts" notes the vendored-gate.py
      requirement + the host-scope routing matrix.
- [ ] Reviewed by `jig:reviewer` (compliance + craft); deviation log produced.
- [ ] `arch_review` if module boundaries shift (host-probe seam crosses into
      spec 004's hook surface).

**Anti-horizontal-phasing check:** After this slice the driver refuses to run
against a dirty tree, vendors its own oracle for portability, and picks the
right path for the host — all observable from the CLI (`--explain-routing`,
the refusal, the downgrade log). End-to-end behavior, not internal-only plumbing.
