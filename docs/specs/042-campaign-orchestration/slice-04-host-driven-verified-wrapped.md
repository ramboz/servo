---
status: DONE
kind: feature
dependencies: [042-03, 041-02]
last_verified: 2026-11-12
arch_review: true
frame_review: true
---

## Slice 042-04 — host-driven verified-wrapped

**Goal:** In host-driven **verified-wrapped** mode, the host-spawned worker runs
its item under `loop.py`, and `campaign record` accepts it as `wrapped` only
when the run is **verified**: a `loop.py` run id exists in the item's worktree,
the worktree's content fingerprint equals the one the loop recorded at halt, and
the loop started at the brief's base sha without `--allow-dirty`. The outcome is
re-rendered from the loop's `state.json`; anything that fails verification is
downgraded to advisory. This is the tier that bounds the loop's own spend on
Copilot (the recorded runaway), so it ships in the parity release.

**DoR:**
- 042-03 is DONE (advisory record + briefs).
- Spec 041 is DONE — `loop.py --host copilot` runs under the credit brake
  (041-02), so a Copilot worker can be wrapped (ADR-0043 is no longer a block).

**Acceptance Criteria:**

1. **`loop.py` records a content fingerprint at halt** in `state.json`: the HEAD
   sha at halt, a hash of the working-tree diff against that HEAD, and the
   contents of untracked, non-ignored files. Bookkeeping paths (`.servo/`,
   caches) are excluded. All of it comes from read-only git queries. The loop
   also records the HEAD sha it saw at start.
2. `campaign record <id> <item> --tier wrapped` accepts the item as `wrapped`
   **iff all** hold, else it is recorded as advisory (`self_reported`):
   - a `loop.py` state with the forwarded `run_id` exists in the item's
     worktree;
   - the worktree's recomputed content fingerprint equals the loop's recorded
     halt fingerprint;
   - the loop's recorded start HEAD equals the item's base sha from the kickoff
     brief, and `--allow-dirty` was not set.
3. **Record before commit.** If HEAD has moved since the halt (the worker
   committed first), the item cannot be verified and is recorded as advisory.
   The kickoff brief states the record-before-commit order.
4. **The record is re-rendered from the loop's state.** For a verified item,
   `result`, `rung`, iterations and cost come from that run's `state.json`; the
   forwarded line is used only to locate the run, and its own field values are
   never trusted.
5. A post-halt edit to a file the loop already changed alters the fingerprint
   (it is content, not a `git status` porcelain set), so it fails verification
   and downgrades to advisory.
6. Verified `wrapped` cost counts as enforced spend in the aggregate ceiling;
   the worker **session's** own spend, and any edits after the loop halts, stay
   outside every ceiling (wrapped binds the `loop.py` subprocess, not the
   session above it). `campaign status` states this boundary.

**DoD:** ACs pass with tests (fingerprint computed from a real git worktree, not
a mock; verification and downgrade paths covered); compliance + craft + arch
reviews; reconciliation. On Copilot, an end-to-end wrapped run is exercised
against spec 041's brake.

**Anti-horizontal-phasing check:** a host spawns a Copilot worker; for a
**compliant** worker (A5), servo verifies the loop's own recorded state is
self-consistent with the worktree content at the declared base, re-renders the
outcome from that state (never the worker's declaration), and the ledger carries
an enforced-spend row — so the recorded runaway is bounded on the motivating host
to the loop's metered spend.

## Assumptions

- **A5 (worker compliance):** a host-spawned worker actually runs its item under
  `loop.py`, stops when the loop halts, records before any commit, and forwards
  the loop's line unchanged. Verification detects non-compliance after the fact;
  it cannot prevent it (ADR-0049 A5). Kill criterion: under ~80% of a host's
  wrapped items verifying, treat that host as advisory-only.
- **Threat-model scope (what verification is and is not).** `_verify_wrapped`
  reads the halt fingerprint, start HEAD, `allow_dirty` and rendered outcome from
  the worker-controlled `<worktree>/.servo/runs/<run_id>/state.json`; the
  fingerprint is a public `sha256` with no servo-held secret, and the base sha is
  disclosed in the brief. So verification **binds the loop's recorded state to the
  worktree content at record time** — which catches a compliant worker's honest
  non-compliance (post-halt edits — AC5; commit-before-record — AC3; a dirty or
  off-base start) and lets servo take the loop's **metered** result/cost instead
  of the worker's declaration (AC4). It is **not** an adversarial provenance
  anchor: a worker that controls its worktree can fabricate a self-consistent
  `state.json` without running `loop.py` and pass — the same residual the advisory
  tier has (which trusts the worker's worktree + oracle). Host-driven mode holds
  no servo-side secret with which to prevent this; the adversarial anchor is only
  available in **servo-driven** mode (042-02), where servo runs `loop.py` itself.
  Because a forgery produces a verification **pass**, the ~80% kill criterion
  measures honest non-compliance (which fails verification), **not** deliberate
  forgery — a host that cannot be trusted at the honest-compliance level should be
  run advisory-only. "Verified, not declared" (ADR-0049) therefore means
  *verified against the loop's recorded state under A5*, not cryptographically
  verified against an adversary.

### Deviation log (after reconciliation)

The original ACs are preserved above. Review rounds:
- **Round 1:** **compliance / craft / arch PASS** (each with one nit, all fixed
  below); **frame-critique NEEDS-CHANGES** — one PRIMARY finding: the shipped
  docs/docstrings over-claimed that verified-wrapped *cryptographically binds
  provenance against an adversarial worker*. They do not: `_verify_wrapped` reads
  the halt fingerprint, start HEAD, `allow_dirty` and rendered outcome from the
  worker-controlled `<worktree>/.servo/runs/<run_id>/state.json`; the fingerprint
  is a public `sha256` with no servo-held secret; the base sha is disclosed in the
  brief. So a worker can fabricate a self-consistent `state.json` without running
  `loop.py` and pass, laundering chosen cost into enforced spend. Host-driven mode
  holds no servo-side anchor to prevent it, and a forgery produces a verification
  *pass*, so the ~80% kill criterion is blind to forgery.
- **Round 2:** **frame-critique PASS** after the honest re-scoping below.
  **Reconciliation PASS.**

Load-bearing choices made during implementation:

1. **The fingerprint lives in `loop.py` and is reused by the verifier via the
   dynamic loader.** `campaign._verify_wrapped` recomputes the worktree fingerprint
   with `loop.py`'s OWN `_content_fingerprint` (`_load_fingerprint_fn`, the same
   `spec_from_file_location` idiom used for the 038 validator / 040 renderer), so
   the halt record and the verifier's recompute are one implementation with no
   drift. The dependency-free skill invariant is preserved; heartbeat is reached
   only on a downgrade-to-advisory oracle re-check (lazy), as in 042-03.
2. **The fingerprint is CONTENT, not a `git status` porcelain set.** HEAD sha + a
   hash of `git diff HEAD --full-index` (full blob shas) + a hash of untracked
   non-ignored file contents, bookkeeping excluded via loop.py's existing
   `_is_bookkeeping_path`. A post-halt edit to an already-changed file alters the
   hash (AC5) where a porcelain line would not; a commit-before-record moves HEAD
   and fails (AC3). All read-only git.
3. **AC4 re-render via `state["outcome"]`.** `loop.py` persists its own rendered
   040 outcome into `state.json` at halt (both drivers), so the verifier re-renders
   result/rung/iterations from the loop's own record and sources cost from
   `cumulative_cost_usd` — never the forwarded line's field values. This avoids
   campaign.py reaching into driver-divergent raw state fields.
4. **The base sha is PERSISTED by `campaign brief --tier wrapped`, never
   worker-supplied.** A worker-supplied `--base-sha` could be set to match its own
   pre-baked start and defeat the "every change happened inside the loop" check;
   persisting servo's own emitted base (`<campaign_dir>/briefs/<item>.json`) closes
   that. A wrapped record with no persisted brief downgrades (`no_wrapped_brief`);
   a brief whose base sha was unresolvable downgrades (`brief_base_sha_unresolved`).
5. **Honest-worker threat-model scoping (the frame-critique R1 fix).** The
   "cryptographic/adversarial-provenance" language was RETRACTED at every site
   (campaign.py `_recheck_oracle` + `_verify_wrapped` + CLI_TIERS comment;
   architecture.md; SKILL.md; the Assumptions above). Verification binds the loop's
   recorded state to the worktree content for a **compliant** worker (ADR-0049 A5);
   it is not an adversarial anchor (the same residual advisory has), and the
   adversarial anchor exists only in servo-driven mode (042-02). This is a settled
   residual, not an over-claim.

Nits fixed (compliance/craft/arch):
- Stale "re-derived in 042-04" credit comments (`_state_cost`, `_status_summary`,
  the `campaign status` credit line) corrected to "credit spend is in AI credits,
  bounded per-run by the 041-02 brake" (matches architecture.md; a credit item
  records `cost_usd: null`, never a USD re-derivation).
- Happy-path cost test hardened: the state's own outcome `cost_usd` (7.77) is now
  distinct from `cumulative_cost_usd` (0.42), so the assertion proves cost is
  sourced from `_state_cost`, not the outcome record's own field.
- Null-base-sha downgrade reason split out (`brief_base_sha_unresolved`) from a
  wholly-missing brief (`no_wrapped_brief`) for clearer diagnosis.

Conscious no-ops (noted, not changed):
- `_read_run_state` + `_state_cost` read `state.json` twice on the verified path; a
  tiny stat+parse off the hot path, kept for reuse of the shared 042-02 helper.
- `_diff_section_is_bookkeeping` path extraction is heuristic for the rare tracked
  `.servo/` file; bookkeeping is normally untracked, so belt-and-suspenders.

Deferred / documented gaps:
- **Copilot e2e (DoD).** "On Copilot, an end-to-end wrapped run is exercised against
  spec 041's brake" could not be run in this build environment (no live Copilot
  host / credentials). It is NOT faked. The USD/Claude wrapped path is covered
  end-to-end (loop `EndToEndVerificationStateTests` writing real `state.json`, and
  campaign real-git-worktree `WrappedVerified*`/`WrappedDowngrade*` tests), and the
  Copilot credit path reuses loop.py's 041-02-validated argv (`--host copilot
  --credit-ceiling`) with the same verifier. Flagged for manual Copilot acceptance
  before the parity release ships.
- **AC6 for credit items.** Verified wrapped USD cost counts in `enforced_cost_usd`;
  a credit wrapped item records `cost_usd: null` (bounded by the per-run 041-02
  brake), and a campaign-level credit aggregate ceiling is 042-05's scope. The
  enforced-spend ROW (tier=wrapped, self_reported=false) exists either way.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `skills/agent-loop/loop.py` + 3 host copies | `updated` | The AC1 content fingerprint (`_content_fingerprint` / `_head_sha` / `_tracked_diff_digest` / `_untracked_digest`), `_record_halt_verification`, and `start_head` / `allow_dirty` / own-outcome recorded at halt in both drivers. Byte-identical across hosts (build_host_packages drift gate green). |
| `skills/agent-loop/test_loop.py` | `updated` | TDD coverage for AC1 over a real git worktree (content-vs-status, untracked, bookkeeping exclusion, end-to-end state, no-flag stdout regression); source-only, not vendored. |
| `skills/agent-loop/test_unpriced_oracle.py` | `updated` | One cross-slice harness touch: the model-activation-halts-next-gate test blanket-patches `subprocess.Popen` as a gate-dispatch detector; stub the new read-only `_head_sha` / `_content_fingerprint` git reads (as it already stubs `_tree_snapshot`) so the guard stays a gate detector. Source-only. |
| `skills/heartbeat/campaign.py` + 3 host copies | `updated` | The `--tier wrapped` verifier (`_verify_wrapped`, `_read_run_state`, the `cmd_record` gate + downgrade), `brief --tier wrapped` + persisted base (`briefs/`), `CLI_TIERS` open, `WRAPPED_BOUNDARY_NOTE`, `wrapped_active` status. Byte-identical across hosts (drift gate green). |
| `skills/heartbeat/test_campaign.py` | `updated` | TDD coverage for the wrapped happy path + every downgrade over real git worktrees; source-only, not vendored. |
| `skills/heartbeat/SKILL.md` + 3 host copies | `updated` | The verified-wrapped tier in `record`/`brief`, the loader boundary, the AC6 + A5 scope notes; hosts regenerated + drift-checked (host-transformed, not byte-identical — the drift gate is authoritative). |
| `skills/heartbeat/heartbeat.py` | `no-op` | Reached read-only on a downgrade's oracle re-check (`_load_heartbeat`); not modified. |
| `docs/architecture.md` | `updated` | The campaign paragraph now documents 042-04 verified-wrapped (fingerprint mechanics, the iff-conditions, re-render-from-state, the AC6 boundary, the honest-worker threat-model scope); credit note corrected to `cost_usd: null`. |
| `docs/decisions/adr-0049-…` | `no-op` | Accepted; 042-04 implements its verified-wrapped tier. Its A5 is the honest-worker frame this slice is scoped to; no ADR edit needed (the over-claim was in derived text, now retracted). |
| `docs/specs/README.md` (board) | `deferred` | Regenerated by `workflow.py status-board` at the close step, before DONE. |
| `docs/specs/042-…/spec.md` | `no-op` | Already `status: IN_PROGRESS`; the slice marker carries this slice's lifecycle. |
| `docs/specs/042-…/slice-04-…md` | `updated` | This slice doc — lifecycle transitions + hosts the deviation log + this sweep + the A5 threat-model scoping. |
| `docs/specs/042-…/reviews/slice-04-*` | `new` | compliance / craft / arch / frame-critique / reconciliation verdicts. |
| `docs/refinement-todo.md` / `docs/inbox.md` | `no-op` | No new deferred follow-up beyond the documented Copilot-e2e manual acceptance and the 042-05 credit-aggregate scope (both ADR-0049 tiers already). |
| `README.md` / `docs/product-vision.md` / `docs/memory/**` / `CLAUDE.md` | `no-op` | No front-door, design-principle, glossary, or primer change beyond the spec + ADR. |
