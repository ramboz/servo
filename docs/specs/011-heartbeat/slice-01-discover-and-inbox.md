---
status: DONE
dependencies: []
last_verified: 2026-06-12
---

## Slice 011-01 — discover-and-inbox

**STATUS: DONE**

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
   identical (mirrors 006-01 AC5's read-only byte-snapshot). Both artifacts
   (`inbox.jsonl` and `inbox.md`) are written **atomically** — full payload to
   `<name>.tmp`, then `os.replace` onto the final path (ADR-0004's house
   discipline for `.servo/` state files) — so a SIGTERM/crash mid-write can
   never leave a torn artifact for the next reader or the next heartbeat.
   *(Single-writer torn-write safety only; concurrent multi-writer locking for a
   double-fired Routine is deferred to 011-02.)*
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
   hand-edit -->` marker (the `status-board` generated-view convention). The view
   also opens with a **per-source status header** — each of the three sources
   (`ci`, `issue`, `commit`) listed as `ran` (with its finding count) or
   `skipped` (with the AC4 cause) — so a silently-degraded unattended run (e.g. a
   missing `gh` auth surfacing an empty-looking inbox) is visible in the artifact
   a human actually reviews, not only in the stderr breadcrumb.
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
- [x] All ACs pass; full existing suite green (no regressions in `test_gate.py`
      / `test_scaffold.py` / `test_loop.py`).
- [x] Per-AC coverage under `skills/heartbeat/test_heartbeat.py`:
      AC1→`DiscoverThreeSourcesTests`, AC2→`ReadOnlyByteSnapshotTests` +
      `AtomicWriteTests`, AC3→`FindingRecordShapeTests`,
      AC4→`SourceDegradationTests` + `ClosedExitContractTests`,
      AC5→`HumanViewTests` + `PerSourceHealthHeaderTests`,
      AC6→`DependencyFreeTests`, AC7→`MockGhGitHarnessTests`,
      AC8→`FindingIdStabilityTests`, AC9→`TriageBootstrapTests`.
- [x] Reviewed by independent reviewer subagent (compliance + craft +
      reconciliation passes; verdicts recorded under `reviews/`).
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] `docs/refinement-todo.md` updated if any decisions were deferred during
      implementation — N/A: no new cross-cutting deferral (deviation-log item 8).

### Close-out (post-DONE)

- [x] `docs/specs/README.md` status board: spec 011 → `IN_PROGRESS (slice 011-01)`
      (via `workflow.py status-board`).
- [x] `README.md` skills table: the `/servo:heartbeat` row reads
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

### Deviation log

Implemented under strict TDD in `skills/heartbeat/heartbeat.py` (+
`skills/heartbeat/test_heartbeat.py`, 53 tests across the 12 required AC
classes — 52 at first green, +1 for the post-review fix in item 9). Full suite
green (758 passed / 1 skipped, no regressions); ruff (0.15.17) clean.
Deviations, interpretation calls, and 011-02 flags:

1. **CI `finding_id` fingerprint = `sha256("ci|" + workflowName + "|" +
   headBranch)[:16]` — NOT the AC8 "e.g." `workflow + job`.** AC8's
   `sha256("ci|"+workflow+"|"+job)` is illustrative, but the real
   `gh run list --json` surface (verified live, gh 2.92.0) has **no `job`
   field** — jobs live inside a run and need a *second* call
   (`gh run view <id> --json jobs`). To keep discovery to **one `gh` call per
   source** (cost + simplicity for an unattended pass), ci is fingerprinted on
   `workflowName + headBranch`, which is stable across reruns of the same
   failing workflow on a branch. **Flag for 011-02:** if job-granularity dedupe
   is wanted (distinguishing two failed jobs in one workflow), it requires the
   second `gh run view` call and a fingerprint-scheme revision — defer the
   decision to 011-02's fingerprint-scheme ADR, tuned against real signal
   output per the spike-shape note. Issue findings fingerprint on issue
   `number`; commit findings on the commit `sha` — both stable,
   content-identifying, never volatile (timestamps/ordinals/attempt are
   excluded). All ids are `sha256(...)[:16]` hexdigest.

2. **`gh --json` field surface validated as the spike's central check.** The
   mock `gh` emits the real field names: run list →
   `workflowName, headBranch, conclusion, url, displayTitle, event, createdAt`;
   issue list → `number, title, body, url, state, labels, author, createdAt,
   updatedAt`. The helper requests exactly the fields it reads. The mock-vs-real
   field-name match (`MockGhGitHarnessTests::test_mock_json_matches_real_field_names`)
   guards this. No live network/gh/repo touched — fake `gh`/`git` injected via
   PATH (the 003-01 mock-claude pattern).

3. **`git log` parsing uses a unit-separator (`%H%x1f%s`) `--pretty` format.**
   Chosen so each line parses deterministically into `<sha><US><subject>` even
   if a commit subject contains spaces/pipes; ASCII 0x1f never appears in a
   sha and practically never in a subject. Bounded to `--max-count=20`
   (`COMMIT_LIMIT`); ci/issue similarly bounded (`--limit 20` / `--limit 50`).
   These caps are first-pass heuristics — **flag for 011-02:** tune the limits
   (and the "what makes a commit-finding *actionable*" open question) against
   real output.

4. **AC2 atomic write + overwrite semantics.** Both `inbox.jsonl` and
   `inbox.md` are written full-payload-to-`<name>.tmp` then `os.replace`
   (ADR-0004 / loop.py `_atomic_write_state` discipline) — single-writer
   torn-write safety, no locking this slice (concurrent double-fired-Routine
   locking is 011-02 per the slice's own note). Re-running `discover`
   **overwrites** the JSONL (re-emits current findings), it does not append —
   matching the 011-02 boundary note; no cross-run state carried here.

5. **AC4 closed `{0,2}` exit + `triage_dir_unwritable`.** Env errors that
   prevent writing exit 2: `target_missing`, `target_not_directory`,
   `triage_dir_unwritable` (the last covers both "cannot create `triage/`" and
   "cannot write the artifacts into it"). Every other path — including all
   sources skipped — exits 0 with an empty inbox + a summary breadcrumb. No
   exit 1. Each skipped source emits a distinct, source-naming stderr
   breadcrumb (`gh not on PATH — skipping ci source`, `git log failed (...) —
   skipping commit source`, etc.).

6. **AC5 `detail` rendered in `inbox.md` (minor addition beyond the literal
   AC).** AC5 requires title + status + evidence ref per finding; the view also
   renders each finding's `detail` on an indented sub-line. For a CI finding
   this surfaces the run's `displayTitle`/`conclusion` — what a human actually
   scans to decide "is this worth a loop?" Judged in-scope as it strengthens
   the "silently-degraded run is visible in the artifact" intent; flag if a
   reviewer wants it trimmed.

7. **Subparser scaffold for later verbs.** `argparse` uses subparsers with
   only `discover` registered (`required=True`). `dispatch` (011-03) / `run`
   (011-04) / `status` (011-02) are intentionally **not** implemented — room is
   left, no stubs. Discovery is oracle-independent: a target with no
   `install.json`/`oracle.sh` still exits 0 and emits the
   `no oracle/manifest … dispatch unavailable until /servo:scaffold-init`
   breadcrumb (AC9); it never refuses on a missing oracle.

8. **No `docs/refinement-todo.md` edit.** No *new* cross-cutting decision was
   deferred during implementation. The **fingerprint scheme** and
   **commit-actionability** questions are explicit Open questions in `spec.md`;
   the **subprocess-limit tuning** (`COMMIT_LIMIT` / `CI_RUN_LIMIT` /
   `ISSUE_LIMIT`, `heartbeat.py:94-97`) is tracked **here in this deviation log
   and the code comment** — *not* in the spec's Open questions — as first-pass
   heuristics to revisit when 011-02 tunes against real output. The DoD's
   "refinement-todo updated **if** any decisions were deferred" is satisfied:
   the limit caps are trivially-tunable constants, not a standalone deferral
   warranting a refinement-todo entry.

9. **Post-review robustness fix (craft-pass nit, addressed before REVIEWED).**
   The craft review flagged an asymmetry: a `gh` source exiting 0 with *empty*
   stdout hit `json.loads("")` and was mislabeled `skipped (unparseable JSON)`
   instead of `ran (0 findings)`, denting the AC5 health header's purpose.
   Fixed in both `_discover_ci` and `_discover_issues` (coerce empty/whitespace
   stdout to `[]`, inline-mirrored across the two callers — no helper, per
   extract-on-third-caller) plus regression test
   `SourceDegradationTests::test_empty_stdout_reports_ran_not_skipped`. Slice
   suite now 53 tests / full suite 758 passed, ruff clean. The two other craft
   nits (process-group kill vs `gate.py`; fsync-before-`os.replace`) were left
   as **conscious house-style divergences** matching `loop.py`'s precedent, per
   the reviewer's own recommendation — not carried forward as work.

**Test-harness note (no production impact):** the mock `gh`/`git` bash
generators are built by string concatenation (not f-strings / `str.format`) so
the canned JSON payloads' braces/brackets are emitted verbatim into the
heredocs, and the quoted-heredoc terminators sit at column 0.
