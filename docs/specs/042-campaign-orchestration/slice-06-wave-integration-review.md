---
status: DONE
kind: feature
dependencies: [042-02]
last_verified: 2026-11-13
arch_review: false
frame_review: true
---

## Slice 042-06 — wave integration-review brief

**Goal:** Before a wave's PRs go out, `campaign review <id>` emits one
fresh-context integration-review brief over the wave's diffs — a single brief
servo produces, not a reviewer it runs. Running the reviewer is the host's or
jig's job (ADR-0049 A3).

**DoR:**
- 042-02 is DONE (a "wave" is the set of items a coordinator dispatched and
  recorded).

**Acceptance Criteria:**

1. `campaign review <id>` collects the diffs of the wave's recorded items (their
   worktrees against their base shas) and emits one brief that asks a fresh
   reviewer to look across the wave for integration problems the per-item oracle
   can't see (cross-item API drift, duplicated or conflicting changes).
2. The brief is host-agnostic text written to a file or stdout; servo does not
   spawn or run a reviewer, and does no git operations beyond read-only diff
   queries.
3. The brief names each item, its outcome and its diff range, so the reviewer
   has the wave's scope without servo summarising the changes for it.
4. `campaign review` is read-only on the ledger and worktrees; it records
   nothing and merges nothing.

**DoD:** ACs pass with tests; compliance + craft reviews (no arch — emits a
brief, changes no contract); reconciliation.

**Anti-horizontal-phasing check:** after a wave finishes, a human gets one
review brief spanning all the wave's diffs and hands it to a fresh reviewer
before any PR publishes — the cross-PR check the recorded run did by hand.

## Assumptions

- **A3 (integration review as an emitted brief):** the integration review is
  useful as a step servo emits — a brief — not one it runs. Unverified;
  running a reviewer is the host's or jig's job. ADR-0049 now carries an **A3
  kill criterion** (added with this slice): a trial comparing the emitted brief
  against the raw worktrees decides whether the emitted-brief shape adds lift.

## Scope — what the brief carries, and what it does and does NOT establish

The frame-critique's reading (recorded in the deviation log) is that the single
load-bearing claim is **A3 as realized here**: that a *scope-only* brief lets a
fresh reviewer find the wave's cross-item integration problems. Two honesty
boundaries are stated plainly rather than left implicit:

- **Scope, not summary.** The brief carries, per recorded item: its outcome
  (result, tier, `self_reported`), its worktree path, its base sha, its worktree
  HEAD, the diff range, and the mechanical changed-file list
  (`git diff --name-status`, paths + change-type only). It carries **no** diff
  body, line content, stat counts, or any servo characterization of what the
  changes do or whether they conflict. servo forms no integration verdict and
  runs no reviewer (emit-not-run: a cross-wave verdict is not oracle-gated, so
  servo cannot own it — ADR-0049 Option C rejection + ADR-0008). File NAMES are a
  change's extent; file CONTENTS and their meaning are the reviewer's to read.
- **The changed-file list surfaces ONE class of problem, not all.** Same-path
  overlap (a path touched by more than one item) is a duplicated/conflicting-edit
  signal a per-item oracle cannot see. It does **not** surface cross-item
  API/contract drift, where a producer and its consumer sit in different files
  with no path overlap; the brief says so and hands the reviewer the per-item
  `git diff` command to trace shared interfaces. The file list is a worktree
  index, not an integration analysis — the slice does not over-claim its power.
- **Worktree locating is best-effort across modes.** A **servo-driven** item's
  worktree lives at the `<campaign_dir>/worktrees/<item>` convention (servo owns
  it), so its diff is always carried. A **host-driven** item's worktree is the
  host's own choice, known to servo only as the `record --worktree` path; this
  slice **persists that path on the ledger entry** so the brief can locate it
  too — closing the motivating (Copilot, host-driven) gap for the verified-wrapped
  tier, whose `state.json` also yields the base sha. The residual: the host owns
  that worktree's lifecycle (it can be gone by review time), and an **advisory**
  item ran no `loop.py`, so it has no recorded base sha — in both cases the brief
  degrades to a named "unavailable" rather than inventing scope.
- **A3 stays unverified; the slice ships deferred out of the parity release.** It
  ships in a later version than the 042-01..04 parity bundle (like 042-05) — a
  release-sequencing note, **not** a DEFERRED lifecycle state; the slice itself
  reaches DONE. The emitter is built and tested; whether an emitted brief is the
  *useful* shape is settled by the ADR-0049 A3 kill-criterion trial, not by this
  slice.

### Deviation log (after reconciliation)

The original ACs are preserved above. Review rounds:
- **Round 1:** **compliance PASS** and **craft PASS** (each with nits, folded
  below); **frame-critique NEEDS-CHANGES** — one `[blocker]` on A3 as realized:
  (a) host-driven worktrees were unlocatable (`_review_item_scope` hardcoded the
  `<campaign_dir>/worktrees/<item>` convention, but a host-driven worker runs in a
  host-chosen worktree never persisted), so the ADR's *motivating* Copilot case got
  a diff-less brief; (b) the brief over-claimed its one cross-item signal —
  same-path overlap cannot surface cross-file API/contract drift; and A3 was the
  only ADR-0049 assumption with no kill criterion.
- **Round 2:** **frame-critique PASS** after the fixes below; **reconciliation
  PASS**.

Load-bearing choices made during implementation:

1. **AC1 "collect the diffs" is realized as "collect diff SCOPE, not diff
   content"** — resolving AC1 against AC3's "without servo summarising the changes."
   The brief carries each item's outcome, worktree path, base sha, diff range and
   the mechanical changed-file list (`git diff --name-status`), never the diff body
   or any servo characterization. File names are a change's extent (scope); file
   contents are the reviewer's to read. *Rejected:* embedding diff bodies / a
   servo-written change summary (crosses into summarising, AC3 forbids it).
2. **emit-not-run (AC2):** servo produces the brief and never spawns or runs a
   reviewer. A cross-wave integration verdict is not oracle-gated, so servo cannot
   own it (ADR-0049 Option C rejection + ADR-0008); running the reviewer is the
   host's or jig's job (A3). This is honest, not a gap.
3. **Read-only git via a local `_git_capture`, not heartbeat's `_git`.** heartbeat's
   `_git` returns `(ok, breadcrumb)` with no stdout, so it cannot carry diff output;
   `_git_capture` mirrors the module's own `_git_head_sha` local subprocess (list
   argv, timeout, no shell). Consequently `campaign review` loads NEITHER loop.py NOR
   heartbeat.py — every read is a pure file read or a local read-only git query,
   keeping the command off both heavier modules (structurally proven by
   `ReviewNoReviewerTests`, which points the loop/heartbeat env hooks at nonexistent
   paths and still exits 0).

Frame-critique fixes (Round 1 → Round 2):
- **(a) Host-driven worktrees are now locatable.** `campaign record` persists the
  worker's `--worktree` on the ledger entry (`entry["worktree"]`), and
  `_review_item_scope` resolves that persisted host-chosen path before the
  servo-driven convention. A servo-driven item still uses the convention (servo owns
  it). This closes the motivating (host-driven, verified-wrapped) case — whose
  `state.json start_head` also yields the base sha — proven by
  `test_host_driven_item_located_via_persisted_record_worktree` (a worktree *outside*
  the convention path is located and its diff carried). The persisted field is
  additive and backward-compatible (status/accounting ignore it).
- **(b) The one-signal claim is now honest.** `_REVIEW_HOWTO` and the module
  "SCOPE, NOT SUMMARY" comment state the changed-file list surfaces same-path overlap
  ONLY and NOT cross-file API/contract drift (producer/consumer in disjoint files),
  which the reviewer must find by reading the diffs; the brief is a worktree index,
  not an integration analysis (`test_brief_does_not_overclaim_the_file_list_signal`).
- **A3 kill criterion** added to ADR-0049 `## Kill criteria`: an emitted-brief
  vs. raw-worktrees trial (plus a degenerate "cannot carry the diffs at all" clause).

Nits fixed (compliance / craft):
- **Vacuous test strengthened.** `test_base_resolves_from_wrapped_brief_when_state_
  lacks_start_head` now commits so HEAD ≠ base and asserts the `base sha:` line
  specifically (+ `"base sha: unavailable" not in out`), so it fails if the
  wrapped-brief fallback regresses — previously a bare `self.base in out` the
  "worktree HEAD" line satisfied regardless (issue #124 instance 2).
- **`--output` fails closed.** A bad `--output` path (e.g. a missing parent) now
  returns rc=2 via `_fail` rather than leaking a raw `FileNotFoundError` traceback,
  matching the module's otherwise-uniform discipline
  (`test_output_to_missing_parent_dir_fails_closed`).
- **Uncommitted range clarified.** When HEAD == base (uncommitted work) the brief
  annotates `base..base` as "HEAD still at base — changes are uncommitted; the
  name-status list below is vs the working tree", so it is not misread as "no
  changes" (`test_uncommitted_item_notes_head_still_at_base`).

Conscious design choices (noted, not changed):
- **servo does NOT compute the cross-item same-path intersection** — it lists each
  item's changed files and leaves the cross-referencing to the reader. Computing the
  intersection would stay within scope-not-summary (names, not content), but NOT
  computing it is the more conservative "servo analyses nothing" posture and the
  brief never claims servo computes it. A possible future reduction of reviewer toil
  (recorded in `docs/refinement-todo.md`).

Deferred / documented follow-ups (`docs/refinement-todo.md`, ADR-0049 A3 kill
criterion):
- **A3 (emitted brief is the useful shape)** — unverified; the kill-criterion trial
  decides keep / reduce-to-index / drop.
- **Host-driven residuals:** the host owns its worktree's lifecycle (gone by review
  time → "worktree not found"); an advisory item ran no `loop.py` so has no recorded
  base sha (no diff range) — the read-only advisory kickoff brief persists none.
- **Cross-item overlap computation** as an optional reviewer-toil reduction.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `skills/heartbeat/campaign.py` + 3 host copies | `updated` | New read-only `campaign review`: `cmd_review` + argparse `review` subparser; `_git_capture`, `_review_base_sha`, `_review_item_scope`, `_render_review_item`, `_build_review_brief` and the `_REVIEW_*` constants; `cmd_record` persists `entry["worktree"]` when `--worktree` is given. Byte-identical across hosts (drift gate green). |
| `skills/heartbeat/test_campaign.py` | `updated` | TDD coverage over a REAL git repo with real per-item worktrees + diffs: one brief spanning the wave, scope-not-summary (file names present, secret diff bodies absent), diff range (committed + uncommitted), read-only byte-snapshot of campaign state + unchanged target/worktree HEADs, no-reviewer/no-loop-no-heartbeat, host-driven persisted-worktree locating, `--output` to file + fail-closed, injection containment, empty wave, unknown campaign. Source-only, not vendored. |
| `skills/heartbeat/SKILL.md` + 3 host copies | `updated` | The `campaign review` subsection + the intro/heading mention; hosts regenerated + drift-checked (host-transformed, the drift gate is authoritative). |
| `docs/architecture.md` | `updated` | The campaign paragraph now documents 042-06 (the emitted scope-only brief, emit-not-run, read-only, the one-signal reach, servo/host-driven worktree resolution, A3 unverified + kill criterion). |
| `docs/decisions/adr-0049-campaign-orchestration.md` | `updated` | Added the **A3 kill criterion** under `## Kill criteria` (the one assumption that lacked one). The decision itself is unchanged. |
| `docs/refinement-todo.md` | `updated` | A3 verification + the host-driven residuals + the optional cross-item overlap computation recorded as follow-ups. |
| `docs/specs/042-…/spec.md` | `deferred` (close-out) | Last slice: `workflow.py transition` rolls the spec `status: IN_PROGRESS → DONE` at the close step before landing (parallel to the board row) — unchanged at review time. |
| `docs/specs/042-…/slice-06-…md` | `updated` | This slice doc — lifecycle, the Scope section, the deviation log, this sweep. |
| `docs/specs/042-…/reviews/slice-06-*` | `new` (written at close-out) | The compliance / craft / frame-critique / reconciliation verdicts, persisted by `review.py record-review` at the close step (no arch — `arch_review: false`, the brief changes no contract). |
| `docs/specs/README.md` (board) | `deferred` | Regenerated by `workflow.py status-board` at the close step, before DONE. |
| `skills/agent-loop/loop.py` | `no-op` | 042-06 is campaign.py-only; loop.py is untouched. |
| `README.md` / `docs/product-vision.md` / `docs/memory/**` / `CLAUDE.md` | `no-op` | No front-door, principle, glossary, or primer change beyond the spec + ADR + skill doc. |
