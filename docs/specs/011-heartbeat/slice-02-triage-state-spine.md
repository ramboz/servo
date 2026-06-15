---
status: DONE
dependencies: [011-01, adr-0010]
last_verified: 2026-06-15
---

## Slice 011-02 — triage-state-spine

**STATUS: DONE**

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
   breadcrumb (atomic write still prevents torn files). The `.inbox.lock` file is a
   **persistent** git-ignored lock target — never unlinked (unlinking it races the
   `flock`: a run arriving in the unlink→close window would create a fresh inode and
   proceed concurrently; the kernel releases the *lock* on process exit, so no
   *stale lock* ever blocks a future run — the ADR-0010 property a pidfile lacks).
   No orphaned `.tmp` staging file is left behind after a successful or failed write.
   *Test:* `ConcurrencyLockTests`.
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
- [x] All ACs pass; full existing suite green (no regressions in `test_gate.py` /
      `test_scaffold.py` / `test_loop.py`).
- [x] Per-AC coverage under `skills/heartbeat/test_heartbeat.py`:
      AC1→`SchemaV2RecordShapeTests`, AC2→`FindingIdStabilityTests`,
      AC3→`MergeDedupeTests`, AC4→`ResumeTests`, AC5→`RetentionTests`,
      AC6→`ActionabilityClassificationTests`, AC7→`ProvenanceMarkerTests`,
      AC8→`ConcurrencyLockTests`, AC9→`StatusSubcommandTests`,
      AC10→`SchemaMigrationTests`, AC11→the extended 011-01 classes.
- [x] Reviewed by independent reviewer subagent (compliance + craft +
      reconciliation passes; verdicts recorded under `reviews/`).
- [x] Implementation review passed.
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed.
- [x] **ADR-0010 flipped Proposed → Accepted** — the crystallizing decision is now
      implemented and verified.
- [x] `docs/architecture.md` updated: ADR-0010 graduated into the "Decisions"
      table, and the "Runtime artifacts" inbox-schema prose finalized to the
      shipped v2 shape (the spec-level DoD's "finalized at close-out" item).
- [x] `docs/refinement-todo.md` updated if any decisions were deferred during
      implementation.

### Close-out (post-DONE)

- [x] `docs/specs/README.md` status board: spec 011 → `IN_PROGRESS (slice 011-02)`
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

### Deviation log (after reconciliation)

Implementation matched the ACs as written; the items below are clarifications,
in-slice test evolutions, and disclosed limitations. No AC was dropped or
reshaped beyond the AC8 plan-review clarification (now recorded in AC8 itself).

**Plan-review clarification (pre-implementation).**
- AC8's "no `.inbox.lock` left behind" was clarified to "the lock file is
  **persistent** — never unlinked" before implementation. Unlinking a `flock`
  target reintroduces a race (a run arriving in the unlink→close window mints a
  fresh inode and proceeds concurrently); the kernel releases the *lock* on
  process exit, so no stale lock persists. Aligns the AC with ADR-0010's own
  pidfile-vs-flock reasoning.

**In-slice test evolutions (live-shape regression tests updated, not new gaps).**
- `FindingRecordShapeTests::test_schema_version_is_first_key_and_int_one` (011-01)
  asserted `== 1`; renamed `...int_two` + assertion updated for the universal v2
  bump (AC1).
- `AtomicWriteTests::test_rerun_overwrites_not_appends` →
  `test_rerun_does_not_duplicate`: overwrite became merge; on identical signals
  the record count is unchanged, so the assertion held and only the name/comment
  were corrected to describe merge-in-place (AC3/AC11).
- `.inbox.lock` added to the AC11 byte-snapshot exact-set + the stdlib allowlist
  (`fcntl`). The read-only-*outside*-triage invariant is unchanged — the lock
  lives *inside* `.servo/triage/`.

**Design clarifications (faithful to ADR-0010, made explicit).**
- Default branch is resolved **lazily inside `_discover_ci`** (only when ≥1 CI
  run exists), honoring ADR-0010's "once per pass" while avoiding a needless
  `gh repo view` on the bad-JSON / empty-ci degradation paths (AC4/AC6).
- The `main`/`master` last-resort tier is applied per-finding in `_classify_ci`
  (matching only the two conventional names, so it never up-classifies a feature
  branch); `_resolve_default_branch` returns `None` when both `gh` and
  `git symbolic-ref` fail (AC6).
- `provenance` is **re-derived (healed)** from `source` on every merge, and
  `_normalize_record` re-emits records in canonical v2 key order — a hand-edited
  inbox is restored to a byte-stable, drift-free shape. "Immutable" is enforced,
  not merely asserted (AC7).

**Reason-code reconciliation (ADR-0010 finalized to shipped reality).**
- The implementation emits `schema_version_mixed` (rc=2) when the `status` read
  path sees >1 distinct known version. ADR-0010 already specified the
  mixed-version refusal ("a reader refuses with rc=2"); the reason-code *name*
  was added to ADR-0010 at reconciliation so the vocabulary matches the code.
- Migration asymmetry (consistent with ADR-0010): the **`status` read path**
  rejects a mixed/higher-unknown version (rc=2); the **`discover` write path**
  discards any non-current record (incl. a stray higher version) and rebuilds
  from live signals — "rejection" on read, "discard+rebuild" on write. The
  write-path drop is by `schema_version != current`, marginally broader than
  AC10's literal "< 2"; benign because the inbox is fully re-derivable.

**Disclosed limitations (deferred — see `docs/refinement-todo.md`).**
- `_classify_ci` returns `ci_non_default_branch` for a CI run disqualified by its
  *event* even when its branch is the default — a cosmetic reason-code
  imprecision (the `actionable: false` verdict is correct). A future additive
  `ci_non_actionable_event` code is queued for before 011-03 consumes
  `actionable_reason`.
- `_status_counts` (markdown view) and the inline by-status tally in
  `_summarize_inbox` (status verb) duplicate a small computation; a shared helper
  is queued as a nice-to-have.
- Contributor-controlled `title`/`detail` render verbatim into `inbox.md`
  (`detail` line-1-trimmed; `title` not newline-sanitized). Out of scope for
  011-02 — the artifact is human-reviewed and ADR-0010 scopes untrusted-text
  handling to 011-03, which acts on the recorded `provenance`.

**Verification.** 111 `test_heartbeat.py` tests green (53 original + 58
new/extended); ruff 0.15.17 clean (targeted + repo-wide). Full suite: 943 passed,
1 skipped, 2 pre-existing `skills/oracle-hook/` env failures (empty meta-judge
stdout under the venv) — proven unrelated by re-running with the heartbeat changes
`git stash`ed (they fail identically on a clean tree); no regressions in
`test_gate.py` / `test_scaffold.py` / `test_loop.py`.
