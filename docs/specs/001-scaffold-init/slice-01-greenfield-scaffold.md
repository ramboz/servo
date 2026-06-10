---
status: DONE
dependencies: []
last_verified:
---

## Slice 001-01 — greenfield-scaffold

**Goal:** A `scaffold.py` helper that, invoked against an empty target directory, copies a placeholder `oracle.sh` from `${CLAUDE_PLUGIN_ROOT}/templates/` to `<target>/oracle.sh`, makes it executable, and writes `<target>/.servo/install.json` recording what landed. End-to-end value: an empty repo gains a runnable (if minimal) oracle in one command.

**DoR:**
- ✅ Plugin shell exists (`.claude-plugin/`, `templates/`, `skills/`)
- ✅ Target dir exists and is a git repo (servo's own dogfood case)
- ✅ Architecture decision recorded: scaffolder is a Python helper invoked by SKILL.md (mirrors jig)

**Acceptance Criteria:**

1. **Empty-target install succeeds.** `python3 skills/scaffold-init/scaffold.py <empty-dir>` exits 0; `<empty-dir>/oracle.sh` exists and is executable (`-rwxr-xr-x`); `<empty-dir>/.servo/install.json` exists and parses as JSON with keys `servo_version`, `timestamp`, `installed_tier="tier-0"`, `signals` (empty object at this slice), `components` (empty list).
2. **Refusal on existing oracle.** Re-running against the same dir exits non-zero with a message naming `oracle.sh` already present; nothing on disk changes.
3. **Force overwrites.** `--force` against the same dir overwrites `oracle.sh` and rewrites `.servo/install.json` with a new timestamp.
4. **Refusal on missing target.** Invoking against a nonexistent path exits non-zero with a clear error; nothing on disk changes.
5. **Helper is dependency-free.** `scaffold.py` runs on system Python 3.10+ with no `pip install` step.

**DoD:**
- [x] All ACs pass; full test suite green (no regressions). _12/12 in `test_scaffold.py`._
- [x] Helper test coverage: at least one fixture per AC under `skills/scaffold-init/test_scaffold.py`. _AC1→`GreenfieldScaffoldTests`, AC2→`RefuseExistingOracleTests`, AC3→`ForceOverwriteTests`, AC4→`MissingTargetTests`, AC5→`DependencyFreeTests`._
- [x] Reviewed by `reviewer` subagent. _jig:reviewer agent, 2026-05-15 — PASS, all five ACs met, tests real, deviations defensible._
- [x] Implementation review passed. _Same review as above._
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed. _Reviewer also evaluated deviation log; one minor gap (rc=1 vs rc=2 asymmetry) added post-review._
- [x] `docs/refinement-todo.md` updated if any decisions were deferred during implementation. _No 001-01-specific deferrals._

### Close-out (post-DONE)

- [x] `docs/specs/README.md` status board updated. _Flipped to `IN_PROGRESS (slice 001-01)`._
- [x] `README.md` skills table row for `scaffold-init` flipped from DRAFT to IN PROGRESS (or DONE if final slice).

**Anti-horizontal-phasing check:** After this slice, a user can run servo's scaffolder against an empty repo and get a working `oracle.sh` (even if minimal) and a manifest the next spec can read. That is end-to-end value, not intermediate state.

**Spike-shape note:** Servo has no prior Spike 0. Treat 001-01 as **spike-shaped** — its purpose is partly to validate that the weighted-composite-oracle approach holds up in practice. If implementation reveals a structural problem (e.g., bash composition doesn't compose cleanly across heterogeneous signals, or the manifest schema needs to encode more than expected), pause and re-plan slices 001-02 through 001-05 before proceeding. A re-plan here is cheaper than carrying a wrong shape through four more slices.

### Deviation log (after reconciliation)

**Slice 001-01 — implemented 2026-05-15.** 12 tests green via `python3 skills/scaffold-init/test_scaffold.py`. Dogfood smoke (`scaffold.py <tmp>` then `bash <tmp>/oracle.sh`) exits 0 with composite=1.0 threshold=0.0.

Deviations from spec text:
- AC #4 ("refusal on missing target") implemented as exit code **2** (env error) rather than the spec's unspecified non-zero. Mirrors the exit-code convention drafted for slice 001-02 (0 pass / 1 below-threshold / 2 env error) — applied early to avoid a churn-y rename next slice.
- `--force` rewrites `install.json` from scratch (per AC #3), but does **not** delete the existing `.servo/` directory; future runtime artifacts (`.servo/runs/`, `.servo/races/`) survive a re-scaffold. Not in the spec text but consistent with `docs/architecture.md` "Runtime artifacts" reservation.
- Shellcheck verification deferred to slice 001-02 (where it's an explicit AC). Local shellcheck not installed; placeholder template is small enough to eyeball.
- **Exit-code asymmetry between refusal cases** (added during reviewer pass): `FileExistsError` (oracle already present) → rc=1; `FileNotFoundError` / `NotADirectoryError` (target missing or not a dir, template missing) → rc=2. Rationale: rc=1 means "state precondition fails but the environment is healthy" — the dev can recover by passing `--force`. rc=2 means "the environment itself is wrong" — no `--force` is going to help. This aligns with the slice 001-02 exit-code convention (1 = below-threshold-style failure, 2 = env error).

**Spike-shape check:** Weighted-composite-oracle approach holds — the placeholder template composes cleanly (single function → score → awk threshold compare) and the manifest schema accepted the slice 001-01 fields without strain. **Proceeding to 001-02 with no re-plan.**

**Reviewer verdict:** PASS (independent review, jig:reviewer subagent, 2026-05-15). All 5 ACs met, tests are real subprocess-driven, deviations defensible, no structural problems forcing a re-plan.

---

