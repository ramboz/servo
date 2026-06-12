---
status: DRAFT
dependencies: []
last_verified:
---

## Slice 011-01 — discover-and-inbox

**STATUS: DRAFT**

**Goal:** A `heartbeat.py` helper whose `discover` subcommand, invoked against a
target, does a **strictly read-only** pass over the project's signals — CI
failures (`gh`), open issues (`gh`), recent commits (`git`) — and writes the
findings to `<target>/.servo/triage/inbox.jsonl` (one JSON record per finding)
plus a generated, human-readable `<target>/.servo/triage/inbox.md` view. The
pass mutates nothing outside `.servo/triage/`. Each source degrades
independently: a missing `gh`, an auth error, or one source failing skips *that
source* with a stderr breadcrumb and continues over the rest — discovery never
hard-fails because one signal is unavailable. End-to-end value: any project can
put **read-only discovery on a schedule** (a Routine invokes `heartbeat.py
discover <target>`) and review the resulting triage inbox — before any of
dedupe (011-02), dispatch (011-03), or the ceiling (011-04) exist.

> **Boundary with 011-02:** this slice produces an inbox from a *single*
> discovery pass. Cross-run **dedupe**, the **status lifecycle**
> (`open`/`tried`/`passed`/`skipped`), and **resume** are 011-02. At 011-01,
> every discovered finding is written with `status: "open"` and a stable
> `finding_id`; re-running `discover` is defined as "re-emit the current
> findings" (overwrite-rewrite of the JSONL), not merge — so this slice carries
> no cross-run state semantics. The `finding_id` is computed here (so 011-02 has
> a stable identity to dedupe on) but not yet *used* for dedupe.

**DoR:**
- ✅ Specs 001 / 002 / 003 DONE — the manifest (`.servo/install.json`) and the
  oracle/gate contract exist; the loop is the eventual dispatch target. (011-01
  itself only does discovery + inbox; it does **not** invoke the gate or the
  loop — those are 011-03.)
- ✅ Decision: helper is a Python script (`skills/heartbeat/heartbeat.py`), same
  shape as `scaffold.py` / `gate.py` / `loop.py`; stdlib-only, Python 3.11+ (the
  spec 009 floor). External tools (`gh`, `git`) are invoked via subprocess,
  never imported.
- ✅ Decision: discovery is **oracle-independent**. A target with no
  `oracle.sh` / `install.json` can still be discovered (the oracle gate lives at
  dispatch, 011-03) — so discovery never refuses on a missing oracle. It records
  a breadcrumb noting dispatch will be unavailable.
- ✅ Decision: reserved state path is `<target>/.servo/triage/`, beside `runs/`
  and `races/`. `inbox.jsonl` is the machine spine; `inbox.md` is the generated
  human view (the `state.json` + `status-board` split).
- ✅ Decision: v1 signal set is exactly **CI failures · open issues · recent
  commits**. The discovery dispatch table is the documented extension point for
  more sources later (same shape as the oracle component registry).

**Acceptance Criteria:**

1. **Read-only discovery over three signal families.** `heartbeat.py discover
   <target>` enumerates: (a) **CI failures** — recent failed runs via `gh`
   (e.g. `gh run list --status failure --json ...`); (b) **open issues** — via
   `gh` (e.g. `gh issue list --state open --json ...`); (c) **recent commits** —
   via `git log` over the target's repo. Each enumerated item becomes one finding
   record. With the mock harness (AC7) seeding two failures, three issues, and
   four commits, exactly nine findings are written.
2. **Strictly read-only outside the artifact dir.** Discovery writes **only**
   under `<target>/.servo/triage/`. It invokes no git-write command, no
   `gh`-mutating subcommand, no `claude -p`, no `loop.py`, and creates no
   worktree. *Test:* byte-snapshot the entire target tree **excluding**
   `<target>/.servo/triage/` before and after `discover`; assert byte-for-byte
   identical (mirrors 006-01 AC5's read-only byte-snapshot).
3. **Finding record shape.** Each line of `inbox.jsonl` is one JSON object with,
   at minimum: `schema_version` (int `1`, **first key** — mirrors `gate.py` /
   `loop.py` / ADR-0004), `finding_id` (stable fingerprint string; see AC8),
   `source` (`"ci"` | `"issue"` | `"commit"`), `title` (string), `detail`
   (string), `evidence` (object: e.g. `{"run_url": ...}` / `{"issue_number": ...}`
   / `{"commit_sha": ...}`), `discovered_at` (ISO-8601 string), `status`
   (`"open"` — every finding at first sight in this slice).
4. **Per-source independent degradation + closed exit contract.** If `gh` is not
   on `PATH`, or a source's subprocess exits non-zero / emits unparseable output,
   that source is **skipped** with a distinct stderr breadcrumb naming the cause
   (e.g. `heartbeat: gh not on PATH — skipping ci, issue sources`;
   `heartbeat: git log failed (<rc>) — skipping commit source`), and discovery
   continues over the remaining sources. Exit codes are a **closed `{0, 2}`**
   set: `0` = discovery completed (with **zero or more** findings, including the
   all-sources-skipped case → an empty inbox + a summary breadcrumb), `2` =
   environment error that prevents writing at all (`target_missing` /
   `target_not_directory` / `triage_dir_unwritable`). There is **no exit 1** —
   discovery does not gate.
5. **Generated human-readable view.** Discovery also writes/refreshes
   `<target>/.servo/triage/inbox.md` — a human-reviewable rendering of the JSONL
   spine grouped by `source`, each finding showing title + status + an evidence
   link/ref. The file carries a `<!-- generated by heartbeat.py — do not
   hand-edit -->` marker (the `status-board` generated-view convention).
6. **Dependency-free.** Python 3.11+, stdlib only (matches `scaffold.py` /
   `gate.py` / `loop.py`); enforced by source inspection in tests. `gh` / `git`
   are subprocess calls, not imports.
7. **Mock harness.** Tests inject fake `gh` and `git` binaries via `PATH` (the
   003-01 mock-claude pattern) that emit canned JSON / log output matching the
   real surfaces; no live network, `gh`, or repo state is touched in CI. The
   harness covers: the happy path (nine findings), each source individually
   failing/absent, and the all-sources-absent path.
8. **Stable `finding_id` fingerprint.** Each finding gets a deterministic
   `finding_id` derived only from stable, content-identifying fields (e.g.
   `sha256("ci|" + workflow + "|" + job)[:16]` for CI; issue number for issues;
   commit sha for commits) — **not** from volatile fields (timestamps, run
   ordinals). Re-running `discover` on identical mock signals yields identical
   `finding_id`s. (This is the identity 011-02 will dedupe on; this slice only
   *computes and records* it.)
9. **Triage dir bootstrap + oracle-independence breadcrumb.** `discover` creates
   `<target>/.servo/triage/` if absent. If `<target>/.servo/install.json` or
   `<target>/oracle.sh` is absent, discovery still completes (exit 0) and emits a
   breadcrumb (`heartbeat: no oracle/manifest at <target> — discovery only;
   dispatch unavailable until /servo:scaffold-init`). Discovery never refuses on
   a missing oracle.

**DoD:**
- [ ] All ACs pass; full existing suite green (no regressions in `test_gate.py`
      / `test_scaffold.py` / `test_loop.py`).
- [ ] Per-AC coverage under `skills/heartbeat/test_heartbeat.py`:
      AC1→`DiscoverThreeSourcesTests`, AC2→`ReadOnlyByteSnapshotTests`,
      AC3→`FindingRecordShapeTests`, AC4→`SourceDegradationTests` +
      `ClosedExitContractTests`, AC5→`HumanViewTests`, AC6→`DependencyFreeTests`,
      AC7→`MockGhGitHarnessTests`, AC8→`FindingIdStabilityTests`,
      AC9→`TriageBootstrapTests`.
- [ ] Reviewed by `jig:reviewer` subagent.
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred during
      implementation.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` status board: spec 011 → `IN_PROGRESS (slice 011-01)`
      (via `workflow.py status-board`).
- [ ] `README.md` skills table: add a `/servo:heartbeat` row reading
      `Spec 011 — IN PROGRESS`.

**Anti-horizontal-phasing check:** After this slice, a user (or a Routine) can
run `heartbeat.py discover <target>` and get a real, read-only triage inbox of
the project's current CI/issue/commit signals — reviewable as `inbox.md`, parseable
as `inbox.jsonl`. That is end-to-end value on its own: "scheduled read-only
discovery → inbox" works standalone, before dedupe (011-02), dispatch (011-03),
or the ceiling (011-04) exist. Each later slice adds a capability, not a
prerequisite for "discovery works."

**Spike-shape note:** This slice is **load-bearing spike-shape** for spec 011 as
a whole. It validates the central assumption — *a read-only discovery pass can
enumerate CI/issue/commit signals via `gh`/`git` subprocess and serialize them
to an inbox artifact without mutating the target.* If the real `gh` surface
differs from the mock (auth model, JSON field names, pagination/rate limits), or
if a no-LLM mechanical pass turns out to under-surface what's "actionable" enough
to be useful, **pause and re-plan 011-02..05** before proceeding — a re-plan here
is cheaper than carrying a wrong shape through four more slices. In particular,
the Open questions "what makes a finding actionable?" and "finding fingerprint
scheme" should be revisited against the spike's real output before 011-02's ACs
are pinned.
