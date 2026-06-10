---
status: DONE
dependencies: [001]
last_verified: 2026-05-18
---

> **DONE 2026-05-18.** All five slices (002-01 through 002-05) implemented, reviewed (each by `jig:reviewer` subagent), and reconciled. Spec-level DoD passed including the three-scenario dogfood (pass-path JSON with `schema_version=1`, `--timeout 1` against a 5s sleep returning rc=2 with `reason=timeout`, manifest-missing refusal). 146 tests green across four files.

# Spec 002 — quality-gate

> Runtime invocation of the scaffolded `oracle.sh`. Locates the target's oracle, runs it under a bounded timeout, normalizes exit codes (0 = ≥threshold / 1 = <threshold / 2 = env error), and emits structured score data callers can act on. The truth-source every other servo runtime skill (003 agent-loop, 004 oracle-hook, 005 variant-race) depends on.

## Why this spec

Spec 001 dropped `oracle.sh` and `.servo/install.json` into the target. Without spec 002, every downstream skill would have to re-invent oracle invocation: locate the file, exec it, parse stdout, handle missing-tool failures, bound the runtime, and decide whether the exit code means "below threshold" or "environment broken". Doing that once — here — eliminates four near-duplicate copies of the same brittle subprocess-and-regex logic across specs 003 / 004 / 005.

It is also the **truth-source** framing servo's design philosophy hinges on: a single uniform call shape (`gate.py <target>`), a single output schema, a single set of exit codes. Once 002 lands, the rest of servo's runtime skills can treat the oracle as a black-box function `(target) -> {exit, score, threshold, missing}` and never touch `oracle.sh` directly.

## Out of scope (deferred to later specs)

- Per-iteration run logging at `<target>/.servo/runs/<run-id>/` (→ 003 agent-loop). The gate is intentionally stateless: callers own persistence.
- Hook-driven `Stop`-event scoring (→ 004 oracle-hook). The gate is a one-shot subprocess; hook integration is its own surface.
- Per-variant scoring across worktrees (→ 005 variant-race). The race driver loops the gate; the gate doesn't know about variants.
- Re-running the gate after edits (a loop concern, not a gate concern).
- Watching files / scheduling / cron-style invocation. Out of scope forever — servo composes with Unix tools that already do this.

## SPIDR decomposition

Mirrors the spec 001 cadence (spike-shaped first slice → core content → contract refinement → safety → wizard) because the problem shape is the same: ship a tool the LLM and the runtime skills both invoke, in vertical slices that each deliver end-to-end value.

### Slice index

| Slice | Title | Goal |
|---|---|---|
| 002-01 | invoke-passthrough | `gate.py <target>` locates `<target>/oracle.sh`, runs it via subprocess, passes through the 0/1/2 exit code. Refuses with rc=2 on missing oracle. |
| 002-02 | structured-output | Parse the oracle's `composite=X threshold=Y` summary; emit normalized text + `--json` mode with `{exit_code, composite, threshold, status, missing}`. |
| 002-03 | manifest-aware | Read `<target>/.servo/install.json` to confirm this is a servo-scaffolded install; refuse on missing manifest. `gate.py audit <target>` prints manifest + components. |
| 002-04 | timeout-safety | Bound oracle runtime (default 5 min, `--timeout` override); kill-on-timeout returns rc=2 with a stderr breadcrumb. Required for unattended callers. |
| 002-05 | qa-wizard | `SKILL.md` exposes the helper to the LLM with trigger phrases ("score this code", "run the oracle"), anti-greediness tests, and refusal-handling guidance. |

Five slices, sized to match spec 001's cadence.

---

## Slices

- [002-01 — invoke-passthrough](slice-01-invoke-passthrough.md)
- [002-02 — structured-output](slice-02-structured-output.md)
- [002-03 — manifest-aware](slice-03-manifest-aware.md)
- [002-04 — timeout-safety](slice-04-timeout-safety.md)
- [002-05 — qa-wizard](slice-05-qa-wizard.md)


## Spec-level Definition of Done

- [x] All five slices DONE (002-01 invoke-passthrough, 002-02 structured-output, 002-03 manifest-aware, 002-04 timeout-safety, 002-05 qa-wizard) — each reviewed by `jig:reviewer` subagent. Verdicts: 002-01 PASS, 002-02 PASS, 002-03 PASS, 002-04 PASS-WITH-CAVEATS (all caveats addressed in-flight), 002-05 PASS. 146 tests across four files: `test_gate.py` (75), `test_skill_surface.py` (18), `test_scaffold.py` (40 regression), `scaffold-init/test_skill_surface.py` (13 regression).
- [x] End-to-end dogfood: three scenarios run 2026-05-18, all PASS:
  1. **Pass-path JSON.** Scaffold a tmp project + pass-path oracle → `gate.py --json` emits `{schema_version: 1, status: "pass", composite: 0.95, ...}`, exit 0. ✓
  2. **Timeout path.** Replace oracle with `sleep 5` body → `gate.py --timeout 1 --json` exits 2, `reason=timeout`, `timeout_seconds=1.0`. ✓
  3. **Manifest-missing refusal.** `mv .servo/install.json .bak` → `gate.py --json` exits 2, `reason=manifest_missing`. ✓
- [x] [README.md](../../../README.md) skills table: `quality-gate` row reads `DONE`.
- [x] `docs/architecture.md` "Runtime artifacts" section unchanged (gate is stateless, no new disk artifacts at `<target>/.servo/`). New "Quality-gate JSON contract" section added below it documenting the closed exit codes, JSON schema, full 11-code `reason` taxonomy, audit JSON shape, and timeout machinery.
- [x] One ADR recorded. _[ADR-0002](../../decisions/adr-0002-gate-caller-contract.md) Accepted 2026-05-18 — closed 0/1/2 exit codes + versioned `--json` schema. Both clauses verified in tests (`UnexpectedExitTests` for the closed-exit clause; `JsonOutputTests.test_schema_version_present_and_equals_one` for the schema-version clause across all five JSON-emitting paths)._
- [x] [docs/specs/README.md](../README.md) status board reflects DONE.

## Critical files (when implementation starts)

In jig (reference patterns):
- `skills/tdd-loop/tdd.py` — subprocess invocation + exit-code passthrough pattern (mirror for 002-01)
- `skills/pr-review/test_skill_surface.py` — anti-greediness test pattern (mirror for 002-05)

In servo (already shipped by spec 001):
- `skills/scaffold-init/scaffold.py` — manifest schema source; gate.py mirrors its CLI shape
- `templates/oracle.sh.template` — the contract source (exit codes, summary line format)
- `skills/scaffold-init/SKILL.md` — Q&A surface pattern for 002-05

In this spec (to be created):
- `skills/quality-gate/gate.py` — new in 002-01, extended each slice
- `skills/quality-gate/test_gate.py` — new in 002-01, extended each slice
- `skills/quality-gate/SKILL.md` — new in 002-05
- `skills/quality-gate/test_skill_surface.py` — new in 002-05

## Clarifications

Recorded 2026-05-18 via `/jig:clarify` before READY_FOR_REVIEW. Q1 and Q3 jointly captured as [ADR-0002](../../decisions/adr-0002-gate-caller-contract.md) because they define the gate's outward caller contract.

### Q1: What should `gate.py` do if `oracle.sh` exits with a code outside the 0/1/2 contract (e.g., signal-killed = 137, buggy = 99)?
_(category: Edge Cases & Failure Modes)_

**Remap to rc=2.** Treat any non-contract exit as `status=env_error reason=unexpected_exit code=<N>`. Keeps the gate's 0/1/2 contract strictly closed; callers never see surprise codes. Captured in [ADR-0002](../../decisions/adr-0002-gate-caller-contract.md).

### Q2: What should `--timeout 0` mean?
_(category: Edge Cases & Failure Modes)_

**Disable timeout.** Treat 0 as 'no bound'. Useful for human runs where you want unbounded wait; unattended callers can still pass a positive value.

### Q3: Should the `--json` output schema (slice 002-02) carry a `schema_version` field from day one?
_(category: Non-functional Requirements)_

**Yes, schema_version=1.** Add the field upfront so 003/004/005 can detect future schema changes. Cheap insurance for a contract three runtime skills depend on. Captured in [ADR-0002](../../decisions/adr-0002-gate-caller-contract.md).

### Q4: What should `gate.py` do if `<target>/oracle.sh` exists but is not executable (e.g., chmod was lost by a git operation)?
_(category: Edge Cases & Failure Modes)_

**Refuse with chmod hint.** Exit 2 with stderr naming `chmod +x oracle.sh` so the user recovers explicitly. Never silently mutate the target's filesystem.

### Coverage summary

| Category | Status |
|---|---|
| Scope & Boundaries | Clear |
| Acceptance Criteria Testability | Clear |
| Dependencies & Blockers | Clear |
| Non-functional Requirements | Resolved |
| Edge Cases & Failure Modes | Resolved |
| Terminology Consistency | Clear |
