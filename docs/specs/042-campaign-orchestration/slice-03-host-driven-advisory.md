---
status: REVIEWED
kind: feature
dependencies: [042-01, 042-02]
last_verified:
arch_review: true
frame_review: true
claimed_by: claude/spec-042-03-advisory-4c2d8b
---

## Slice 042-03 — host-driven advisory

**Goal:** In host-driven **advisory** mode, servo emits the plan plus one
kickoff brief per item, the host spawns the workers, and `campaign record`
accepts each item's reported outcome **only after re-running the item's oracle**
on the worker's worktree. Every field other than the re-checked pass is marked
`self_reported`, and `self_reported` cost is never counted as enforced spend.
servo neither spawns nor messages host sessions.

**DoR:**
- 042-01 is DONE (ledger + record) and 042-02 is DONE (coordinator + brief
  machinery to reuse).

**Acceptance Criteria:**

1. `campaign brief <id> [<item>]` emits, per item, a kickoff brief containing
   the item's prompt, `oracle_ref`, budget and `models` block as **data**, the
   item's base sha, and the instruction to run `campaign record` before any
   commit. The brief states that item text is data, never instructions to the
   worker (ADR-0049 / spec 011 Guardrail #4).
2. `campaign record <id> <item> --tier advisory --outcome <line>` re-runs the
   item's oracle (`gate.py`) on the worker's worktree before accepting a
   `passed` result. A host's claim of `passed` that the oracle re-check does not
   confirm is recorded as `blocked`/`error`, never `passed`.
3. Every outcome field other than the re-checked oracle result is recorded with
   `self_reported: true` (cost, rung, reason). The aggregate ceiling does not
   count `self_reported` cost as enforced spend (042-01 AC2).
4. Nothing stops a runaway advisory worker in flight — advisory mode enforces
   the planned list, the ledger and verified passes only. This limit is stated
   in the brief and in `campaign status` output, not hidden.
5. servo never spawns or messages a host session; it only writes briefs and
   reads worktrees. In advisory mode budget, model tier and the ladder reach the
   worker as brief text only.

**DoD:** ACs pass with tests; compliance + craft + arch reviews; reconciliation.

**Anti-horizontal-phasing check:** a host coordinator runs a campaign's items
its own way and still gets, per item, a durable ledger row with an
oracle-verified pass — the Option B floor plus the one check Option B lacks.

## Assumptions

- **A1 (adoption):** a host coordinator actually calls `campaign brief` /
  `record`. Unverified; the kill criterion drops host-driven mode for a host
  under ~80% recorded-without-prompt.
- **A5 (worker compliance):** advisory workers can't be verified beyond the
  oracle re-check; a self-reported field may be wrong, which is why it is marked
  and never counted as enforced spend.

### Deviation log (after reconciliation)

The original ACs are preserved above. Review rounds:
- **Round 1:** **craft PASS** (three nits); **compliance needs-changes** (one
  blocker: the two AC5 no-spawn tests were vacuous); **arch needs-changes** (one
  blocker: `docs/architecture.md` not updated in-slice, breaking the 042-01/02
  convention); **frame-critique needs-changes** (the advisory re-check's
  trust-boundary claim over-reached).
- **Round 2:** compliance / arch / frame-critique re-reviewed clean after the
  fixes below (all PASS). Reconciliation reviewed at close (recorded alongside
  the DONE transition).

Load-bearing choices made during implementation:

1. **`campaign brief` and the advisory re-check are new subcommands/branches of
   `campaign.py`**, extending 042-01/02's CLI — not a new module. Surfaces:
   `campaign brief <id> [<item>]` and `campaign record … --tier advisory
   --worktree <path>`.
2. **The oracle re-check reuses heartbeat's canonical `_run_gate_json`** via a
   lazy `spec_from_file_location` load of `heartbeat.py` (never a static import —
   the dependency-free invariant), exactly as 042-02's `next` reuses heartbeat's
   provisioning. servo scores the oracle ITSELF rather than trusting the worker's
   reported `result`; reimplementing a second gate invocation would duplicate
   security-relevant logic and invite drift. The load is confined to the
   advisory-`passed` branch (`test_non_pass_claim_skips_recheck`,
   `test_servo_tier_pass_not_rechecked` prove the gate — and thus the heartbeat
   load — never fires otherwise), so 042-01's hot-path-off-heartbeat invariant
   holds for every other `record`/`status` call.
3. **The re-check's scope is deliberately bounded (frame-critique resolution).**
   It catches a claimed `passed` the worktree's oracle does not actually support
   — the honest-but-wrong / hallucinated pass, the realistic A5 non-compliance.
   It does **not** bind the worktree's provenance: the worker supplies and
   controls `--worktree` (and its `.servo/` policy + `oracle.sh`), so an
   adversarial worker can still present trivially-passing content and obtain a
   genuine exit-0. That is faithful to ADR-0049 A5 ("verification detects
   non-compliance after the fact; it cannot prevent it") and keeps advisory the
   lightweight floor over Option B (servo runs the oracle instead of taking the
   worker's word, never more). Cryptographic worktree-provenance binding (base
   sha + content fingerprint + record-before-commit) is the **verified-wrapped
   tier (042-04)**, not this one. The implementation docstring, the kickoff
   brief's record instruction, `SKILL.md`, and `docs/architecture.md` were
   corrected in R2 so none over-claims a trust boundary the advisory tier does
   not deliver (the SKILL.md sweep was completed after R2 compliance + frame both
   flagged a residual "can no longer be verified" phrase in its brief summary).
4. **The re-checked oracle result is recorded in an additive `oracle_recheck`
   ledger field** (servo's own verdict: `claimed_result`, `recorded_result`,
   `confirmed`, the re-check's own `status`/`composite`/`threshold`), and
   `outcome.result` is overwritten with it so the ledger's authoritative result —
   what `status`, escalation and accounting read — is servo's, never the host's
   claim (AC2 "recorded as blocked/error, never passed"). AC3's per-field wording
   ("every field other than the re-checked result is `self_reported`") is modeled
   with the single entry-level `self_reported` boolean (true for advisory,
   covering cost/rung/reason) PLUS the `oracle_recheck` block for the result —
   not per-field flags. Accounting is unchanged: advisory cost is never enforced
   spend, even on a confirmed pass (`_status_summary` keys on entry-level
   `self_reported`). The field is backward-compatible (`_is_outcome_entry` /
   `_status_summary` ignore it).
5. **`--worktree` is required for an advisory `passed` and fail-closed.** Missing
   `--worktree`, or a path that is not a directory, exits rc=2 with the ledger
   unchanged (a caller/usage error to fix and retry). A wholly-uninvocable
   `gate.py` (no parseable verdict) also exits rc=2 — a servo-side
   gate-environment problem, not an item outcome. An oracle that *ran* and
   env-errored (exit 2) is a real campaign outcome, recorded as `error`.
   `--worktree` is ignored for a servo-tier outcome or a non-pass advisory claim
   (no re-check runs); noted in its `--help`.
6. **The AC4 runaway-limit disclosure has a single source of truth**
   (`ADVISORY_RUNAWAY_NOTE`): emitted in every `campaign brief` and in `campaign
   status` once advisory is in play (`advisory_active` in the `--json` summary;
   quiet for a confirmed servo-only campaign), so the two surfaces cannot drift.
7. **AC5 — no spawn, no message.** The advisory `record`/`brief` paths spawn no
   worker/host session. The only write under the worker's worktree is the
   oracle's own git-ignored `<worktree>/.servo/gate-runs/<run_id>/` bookkeeping,
   an inherent side effect of running `gate.py` (required by ADR-0049's "re-run
   the oracle on the worker's worktree"), never a modification of the worker's
   deliverable. AC5's prose "only … reads worktrees" understates that gate-run
   write; the ADR governs and the write is namespace-scoped bookkeeping. The
   no-spawn tests assert the trace a spawned loop would leave (an invocation log
   and `<worktree>/.servo/runs/`), not a sentinel the stub never produces (R1
   compliance/craft blocker/nit).
8. **AC2 scores the worktree's installed oracle**, reached by `_run_gate_json`,
   not keyed on the plan item's `oracle_ref` (the item field reaches the worker
   as brief data only). Consistent with servo's single-project-oracle model and
   AC2's own "(gate.py)" parenthetical; noted for a future per-item divergent
   oracle.
9. **Non-git / no-HEAD base-sha fallback (AC1).** When the target has no
   resolvable git HEAD (not a work tree, git absent, no commit, or a timeout),
   `brief` emits `base sha: unavailable (no resolvable git HEAD on the target)`
   rather than failing — graceful degradation; `brief` stays read-only and exit 0.
10. **Known read-back consequence:** after a downgrade, `outcome.result` is
    servo's (`blocked`/`error`) while `outcome.reason` keeps the host's
    self-reported narrative, so a human read-back can show `blocked … reason=<the
    host's pass reason>`. Inherent to keeping self-reported fields verbatim; the
    authoritative verdict is in `oracle_recheck`. Logged, not changed.
11. **One existing 042-01 test updated.** `test_advisory_is_self_reported` now
    records a non-`passed` advisory outcome (it no longer asserts the pre-042-03
    behavior of accepting an advisory `passed` on the host's word, which AC2
    removes). The tier → `self_reported` mapping it checks is unchanged.

Deferred / noted, not fixed here:
- Advisory worktree-provenance binding → **042-04** (verified-wrapped).
- `gate_consumer.request` can raise `ValueError` ("destination already exists")
  inside `_run_gate_json` outside its try/except; effectively impossible (uuid4
  run id) and pre-existing/shared with heartbeat dispatch, not introduced here.
- **Coupling accretion (arch open question):** `campaign.py` now reuses several
  of `heartbeat.py`'s private underscore helpers (`_run_gate_json` here;
  `_is_git_work_tree` / `_remove_worktree_if_present` / `_provision_oracle` /
  `_git` / `_format_ceiling` from 042-02). Correct and lean for two consumers and
  guarded by the real-`gate.py` integration test; if a fourth consumer appears,
  extracting a shared dispatch-commons module would be worth it. Not a blocker.

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `skills/heartbeat/campaign.py` + 3 host copies | `updated` | The feature — `brief`, the advisory oracle re-check in `record`, `ADVISORY_RUNAWAY_NOTE`, `--worktree`, `oracle_recheck`. Byte-identical across hosts (sync gate green). |
| `skills/heartbeat/test_campaign.py` | `updated` | TDD coverage for 042-03 (incl. a real-`gate.py` integration test); source-only, not vendored to hosts. |
| `skills/heartbeat/SKILL.md` + 3 host copies | `updated` | `brief` section, the advisory re-check in `record`, `--worktree`, the status runaway disclosure; hosts regenerated + drift-checked. |
| `skills/heartbeat/heartbeat.py` | `no-op` | Reused read-only via `_load_heartbeat()._run_gate_json`; not modified. |
| `docs/architecture.md` | `updated` | The campaign paragraph now documents 042-03 advisory dispatch (brief, the `--worktree` oracle re-check, `oracle_recheck`, the gate-run write, the honest trust-boundary scope); only verified-wrapped remains 042-04. |
| `docs/decisions/adr-0049-…` | `no-op` | Accepted; 042-03 implements its advisory tier. Scope of the re-check is reconciled against A5 in this deviation log. |
| `docs/specs/README.md` (board) | `deferred` | Regenerated by `workflow.py status-board` at the close step, before DONE. |
| `docs/specs/042-…/spec.md` | `no-op` | Already `status: IN_PROGRESS`; the slice marker carries this slice's lifecycle. |
| `docs/specs/042-…/slice-03-…md` | `updated` | This slice doc — lifecycle transitions + hosts the deviation log + sweep. |
| `docs/specs/042-…/reviews/slice-03-*` | `new` | compliance / craft / arch / frame-critique / reconciliation verdicts. |
| `docs/refinement-todo.md` | `no-op` | No new deferred follow-up beyond 042-04's provenance binding (already an ADR-0049 tier) and the pre-existing `gate_consumer.request` note. |
| `README.md` / `docs/product-vision.md` | `no-op` | No front-door or design-principle change. |
| `docs/inbox.md` / `docs/memory/**` / `CLAUDE.md` / `agents/*.md` | `no-op` | No new domain terms, rules, or primer changes beyond the spec + ADR. |
