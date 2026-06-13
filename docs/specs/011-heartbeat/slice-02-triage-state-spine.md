---
status: READY_FOR_REVIEW
dependencies: [011-01, adr-0010]
last_verified:
---

## Slice 011-02 — triage-state-spine

**STATUS: READY_FOR_REVIEW**

**Goal:** The inbox becomes the **state spine**: a stable `finding_id`
fingerprint dedupes across runs; a status lifecycle
(`open`→`tried`→`passed`/`skipped`) is tracked; `heartbeat.py status` reads it
back. The next heartbeat **resumes** — already-passed/tried findings are not
re-surfaced as new work. The crystallizing decision — the triage-inbox schema +
dedupe-identity contract — is recorded in
[ADR-0010](../../decisions/adr-0010-triage-inbox-schema.md) (Proposed; Accepted
at this slice's close-out).

> **Boundary with 011-03 (dispatch).** This slice makes the inbox a *resuming
> state spine* and adds the read-only `status` verb; it does **not** dispatch.
> The `open → tried` / `open → passed` transitions, the `attempts` increment, and
> the `outcome` object are **written by 011-03**; ADR-0010 *reserves* their shape
> so the contract is stable before data exists, and 011-02 writes only their
> defaults (`attempts: 0`, `outcome: null`). 011-02 records the `provenance`
> marker and the `actionable` verdict; **011-03 acts on them** (frames
> `contributor` text as untrusted data; dispatches the `actionable AND open`
> candidate set). 011-02 never auto-sets `skipped` (human-only this slice).

**DoR:**
- ✅ **011-01 DONE** — `heartbeat.py discover` (+ `test_heartbeat.py`, 53 tests),
  the `finding_id` scheme, and the atomic-write / read-only-byte-snapshot /
  per-source-degradation / closed-`{0,2}`-exit contracts exist to extend. 011-01
  *overwrites* the JSONL and writes every finding `status: "open"`; this slice
  replaces overwrite with merge and adds the lifecycle.
- ✅ **ADR-0010 drafted (Proposed)** — pins the v2 record schema, the ratified
  dedupe identity, the uniform merge + retention semantics, the two-axis
  (sticky `status` vs recomputed `actionable`) model, the immutable `provenance`
  marker (Guardrail #4), the `flock` double-fire discipline, and the
  migration rules. Flipped to **Accepted** at this slice's close-out (per the
  spec-level DoD).
- ✅ Decision: stdlib-only, Python 3.11+ (the spec 009 floor). `fcntl` is stdlib
  (POSIX); `gh` / `git` stay subprocess calls, never imported.
- ✅ Decision: discovery and `status` stay **oracle-independent** — the oracle
  gate lives at dispatch (011-03). A target with no `oracle.sh` / `install.json`
  is still discoverable and readable.
- ✅ Decision: the v1→v2 inbox migration is trivial — the inbox is a git-ignored
  runtime artifact and 011-01 only just shipped, so no v1 data of consequence
  exists in the wild (ADR-0010 "Migration").

**Acceptance Criteria:**

1. **Schema v2 record shape.** Each `inbox.jsonl` line is a JSON object carrying,
   per ADR-0010: `schema_version` (int `2`, **first key**); the **immutable**
   fields `finding_id`, `source` (`"ci"`|`"issue"`|`"commit"`), `provenance`
   (`"first_party"`|`"contributor"`), `discovered_at` (ISO-8601, first-seen); the
   **sticky** fields `status` (`"open"`|`"tried"`|`"passed"`|`"skipped"`),
   `attempts` (int, default `0`), `outcome` (object|`null`, default `null`); and
   the **volatile** fields `title`, `detail`, `evidence` (object), `last_seen_at`
   (ISO-8601), `actionable` (bool), `actionable_reason` (str). All records in a
   file carry the **same** `schema_version`; a mixed-version file is rejected
   (rc=2). *Test:* `SchemaV2RecordShapeTests`.
2. **Stable dedupe identity (ratified fingerprint).** `finding_id` is unchanged
   from 011-01 — `sha256("<source>|...")[:16]` over content-identifying parts only
   (CI = `workflowName`+`headBranch`, issue = `number`, commit = `sha`); never
   volatile fields (timestamps/ordinals/`attempts`). Re-running `discover` on
   identical signals yields identical ids. Job-granularity CI dedupe stays
   **deferred** (ADR-0010 — `gh run list` has no `job` field). *Test:*
   `FindingIdStabilityTests` (extends 011-01's).
3. **Uniform merge across runs (no more overwrite).** Re-running `discover` merges
   by `finding_id`: an existing finding **preserves** its immutable + sticky fields
   (`status`/`discovered_at`/`attempts`/`outcome`/`provenance`) and **refreshes**
   its volatile fields (`title`/`detail`/`evidence`/`last_seen_at`/`actionable`/
   `actionable_reason`); a newly-seen `finding_id` is appended with `status:
   "open"`, `discovered_at = last_seen_at = <now>`, `attempts: 0`, `outcome:
   null`. *Test:* `MergeDedupeTests`.
4. **Resume — sticky lifecycle survives re-discovery.** A finding at
   `tried`/`passed`/`skipped` (hand-set, or dispatch-set in 011-03) keeps that
   status across a later `discover` — never reset to `open`, so it is not
   re-surfaced as new work; its first-seen `discovered_at` is preserved while
   `last_seen_at` refreshes when the signal recurs. A persistently-recurring
   `tried` finding is **not** auto-re-dispatched (one attempt in v1; ADR-0010).
   *Test:* `ResumeTests`.
5. **Retention bound (uniform, all sources).** An `open` finding **not re-observed
   this pass** is evicted from the inbox; a finding with `status ∈ {tried, passed,
   skipped}` is **retained** even after its signal disappears (audit trail). This
   one rule bounds growth across CI / issue / commit (a scrolled-out commit is
   `open` + unseen → evicted; ADR-0010 rejects a per-source policy because the CI
   `headBranch` keyspace is as unbounded as commit SHAs). *Test:* `RetentionTests`.
6. **Actionability classification (deterministic, recomputed each pass).** Each
   finding carries `actionable` (bool) + `actionable_reason` (machine code) per
   ADR-0010's v1 heuristic: **CI** actionable iff `event ∈ {push, schedule}` **AND**
   `headBranch == <default branch>` — default branch resolved via `gh repo view
   --json defaultBranchRef` → `git symbolic-ref --short refs/remotes/origin/HEAD`
   → `main`/`master` → **unknown ⇒ not-actionable**; **issue** actionable unless it
   carries a non-actionable label (`wontfix`/`won't fix`/`duplicate`/`invalid`/
   `question`/`discussion`, case-insensitive name match against a named, tunable
   constant); **commit** always `actionable: false` (`commit_context_only`). The
   `event` field (already in `_GH_RUN_FIELDS`) is now read. *Test:*
   `ActionabilityClassificationTests`.
7. **Immutable provenance marker (Guardrail #4).** Each finding carries
   `provenance` set once at first-seen — `"first_party"` for CI, `"contributor"`
   for issue/commit — and preserved unchanged across merge (it is a function of
   `source`, which is in the fingerprint). 011-02 only *records* it; 011-03
   derives the dispatch treatment (frame `contributor` title/detail/evidence as
   untrusted **data, not instructions**). *Test:* `ProvenanceMarkerTests`.
8. **Double-fire concurrency safety.** `discover` takes an advisory
   `fcntl.flock(LOCK_EX | LOCK_NB)` on a **separate** lock file
   `<target>/.servo/triage/.inbox.lock` (never on `inbox.jsonl` — `os.replace`
   swaps the inode) around the read-merge-write. On contention it emits a
   `lock_contended` stderr breadcrumb and exits **0** (the closed `{0,2}` contract
   holds — the other run is maintaining the inbox); a `flock` `OSError` exits **2**;
   a missing `fcntl` module (non-POSIX) degrades to unlocked with a one-time
   breadcrumb (atomic write still prevents torn files). No `.inbox.lock`/`.tmp`
   cruft is left behind. *Test:* `ConcurrencyLockTests`.
9. **`heartbeat.py status` subcommand (read-only read-back).** `heartbeat.py
   status <target>` reads `inbox.jsonl` and prints a **human** summary by default —
   counts by `status`, by `source`, by actionability, plus the open-actionable
   candidate list with each candidate's `last_seen_at` — and a **machine** summary
   under `--json` (carrying `schema_version`). Closed `{0,2}` exit (0 = read OK,
   including an empty/absent inbox; 2 = env error). It never mutates and never
   gates (no exit 1). *Test:* `StatusSubcommandTests`.
10. **Schema migration (two rules).** On `discover` (write path) a record with
    `schema_version < 2` is **dropped and re-derived** from live signals (lossless
    because a v1 record carries no sticky lifecycle — `status` was always `open`).
    On `status` (read path, read-only) a *lower* known version **warns + best-effort
    displays**, a *higher* unknown version **refuses** (rc=2,
    `schema_version_unsupported`). Per ADR-0010 (a deliberate divergence from
    ADR-0004's hard-refuse, justified by the inbox being re-derivable). *Test:*
    `SchemaMigrationTests`.
11. **011-01 invariants preserved + view extended.** Through the new merge path:
    strictly **read-only** outside `<target>/.servo/triage/` (byte-snapshot);
    **atomic** `tmp`+`os.replace` writes of both artifacts; per-source independent
    degradation + closed `{0,2}` exit; **stdlib-only** (now incl. `fcntl`), `gh`/
    `git` subprocessed not imported. The generated `inbox.md` view (with its
    `do-not-hand-edit` marker + per-source health header) is **extended** to
    surface each finding's `status` and `actionable`/reason and a lifecycle
    summary. Full existing suite green — no regressions in `test_gate.py` /
    `test_scaffold.py` / `test_loop.py`. *Tests:* extend `ReadOnlyByteSnapshotTests`
    / `AtomicWriteTests` / `SourceDegradationTests` / `ClosedExitContractTests` /
    `HumanViewTests` / `DependencyFreeTests`.

**DoD:**
- [ ] All ACs pass; full existing suite green (no regressions in `test_gate.py` /
      `test_scaffold.py` / `test_loop.py`).
- [ ] Per-AC coverage under `skills/heartbeat/test_heartbeat.py`:
      AC1→`SchemaV2RecordShapeTests`, AC2→`FindingIdStabilityTests`,
      AC3→`MergeDedupeTests`, AC4→`ResumeTests`, AC5→`RetentionTests`,
      AC6→`ActionabilityClassificationTests`, AC7→`ProvenanceMarkerTests`,
      AC8→`ConcurrencyLockTests`, AC9→`StatusSubcommandTests`,
      AC10→`SchemaMigrationTests`, AC11→the extended 011-01 classes.
- [ ] Reviewed by independent reviewer subagent (compliance + craft +
      reconciliation passes; verdicts recorded under `reviews/`).
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] **ADR-0010 flipped Proposed → Accepted** — the crystallizing decision is now
      implemented and verified.
- [ ] `docs/architecture.md` updated: ADR-0010 graduated into the "Decisions"
      table, and the "Runtime artifacts" inbox-schema prose finalized to the
      shipped v2 shape (the spec-level DoD's "finalized at close-out" item).
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred during
      implementation.

### Close-out (post-DONE)

- [ ] `docs/specs/README.md` status board: spec 011 → `IN_PROGRESS (slice 011-02)`
      (via `workflow.py status-board`).

**Anti-horizontal-phasing check:** After this slice a Routine can run **repeated**
`discover` passes and get a **deduped, resuming** triage inbox — already-handled
findings stay handled, stale `open` noise is evicted, actionable candidates are
flagged with their provenance, and `heartbeat.py status` reads the spine back
(human or `--json`). That is end-to-end value on its own — a human can review a
stable, deduplicated inbox across days — before dispatch (011-03) or the
whole-heartbeat ceiling (011-04) exist. The slice touches the user-facing surface
(the inbox artifact + the new `status` verb), not just internal plumbing.

**Spike-shape note:** 011-01 was the load-bearing spike — it validated the real
`gh`/`git` surface against the mock. This slice builds the *state* layer on that
validated surface; the ADR-0010 decisions (fingerprint coarseness, actionability
heuristic, commit-as-context) are tuned to 011-01's real output per the spike's
"revisit before 011-02's ACs are pinned" note.

**Out of scope (this slice):**
- **Dispatch** (011-03) — the `open → tried`/`passed` transitions, the `attempts`
  increment, populating `outcome`, the oracle preflight, the worktree + loop, and
  *acting on* `provenance`/`actionable`. ADR-0010 reserves the fields; 011-03
  writes them.
- **Whole-heartbeat cost ceiling** (011-04) — ADR-0010 only *reserves*
  `outcome.cost_usd` so that ceiling can later sum from the inbox alone.
- **Deferred by ADR-0010:** job-granularity CI dedupe (needs a 2nd `gh run view`
  call + a schema bump), the actionable-commit signal (revert/`FIXME` detection),
  and retry-with-backoff for `tried` findings.
- **Target `.gitignore` `triage/` reservation** — a separate scaffold-init
  refinement-todo; servo's *own* repo already ignores `.servo/`.
