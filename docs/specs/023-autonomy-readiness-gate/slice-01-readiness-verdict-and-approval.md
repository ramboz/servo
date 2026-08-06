---
status: RECONCILED
dependencies: [adr-0029]
arch_review: true
last_verified: 2026-08-06
claimed_by: claude/spec-023-jig-ceremony-9bffc1
---

## Slice 023-01 — readiness verdict, artifact, and human approval

**Goal:** A `autonomy-readiness` skill reviews a goal's scope + initial prompt and
emits a human-owned three-state verdict that gates whether an unattended loop may
start — refusing bad premises and identity-collapsed setups before any budget is
burned. Implements [ADR-0029](../../decisions/adr-0029-autonomy-readiness-gate.md).

**DoR:**
- ✅ [ADR-0029](../../decisions/adr-0029-autonomy-readiness-gate.md) is the governing record (**Accepted 2026-08-06**, frame-critique pass recorded).
- ✅ **Confirmed** (grounding 2026-08-06). `edd-suitability` = `skills/edd-suitability/suitability.py`:
  verdict ∈ `suitable|needs_evidence|unsuitable`, exit `{0,2}`, atomic artifact
  `<target>/.servo/suitability/<spec-id>.json` with keys `schema_version, verdict,
  reasons[{code,message}], missing_evidence[{kind,detail,blocking}], spec_id,
  analyzed_at, inputs`; pure ordered `_rule_table()` shared by `decide()`/`build_trace()`
  (mirror for readiness). `eval-authoring` approval = a scalar `approval_status`
  string flipped `draft/proposed → approved` (`freeze_dataset_config`); `criteria-check`
  exit is tri-valued (0 all-approved / 1 not-yet / 2 env).
- ✅ **Confirmed.** `loop.py` refuse-without-oracle = `_target_preflight_error`(1294)
  → `_preflight`(1383) → `_refuse_preflight`(1048, returns `EXIT_ENV_ERROR=2`);
  dirty-tree = `_dirty_tree_paths`(1340). Insertion points: `--emit-routine-prompt`
  gate before loop.py:3264 (`_emit_routine_prompt`), `--background` gate before
  loop.py:3417 (`run_goal_loop_background`). Flags are manual-`parser.error`
  mutually-exclusive (3246). (`--max-candidates` is heartbeat's, not loop.py's.)
- ✅ **Pinned.** No host-identity probe exists in the repo (only `gh repo view
  --json defaultBranchRef` in heartbeat). Per amended ADR-0029 the identity posture
  is **best-effort/networked**: probe merge authority via `gh` when available,
  degrade to an advisory note otherwise; escalate to `unsafe_for_autonomy` only
  when the run declares an autonomous-merge capability. Jig co-install probe mirrors
  `eval_authoring._jig_independent_review_skill_path` (user-scope `~/.claude/skills/…`,
  conservative on error, `Path.home()` for hermetic tests).

**Acceptance Criteria:**

1. **Three-state verdict + atomic artifact.** The skill emits
   `ready | needs_tightening | unsafe_for_autonomy`, exit `{0,2}` (fail-closed),
   writing `<target>/.servo/readiness/<goal-id>.json` atomically. Observable: each
   verdict is reachable from a corresponding fixture brief.
2. **Deterministic tier.** Missing/unexecutable oracle, no approved component,
   infinite (unset) budget/iteration/`max-candidates` cap, dirty tree/no isolation,
   or absent mutation perimeter each downgrade the verdict. Observable: toggling
   each precondition changes the verdict deterministically.
3. **Identity-collapse check (conditional, best-effort).** When the run declares
   an autonomous land/merge capability AND the principal that would run the loop
   is also able to merge to the base branch, the verdict is `unsafe_for_autonomy`
   with a message naming identity collapse. Under servo's default
   human-lands-the-worktree model (no autonomous-merge declared, or no host probe
   available), the identity posture is recorded as an advisory scorecard note and
   does not by itself force a refusal. Observable: a single-identity + autonomous-
   merge fixture is flagged `unsafe_for_autonomy`; a two-identity fixture is not;
   a single-identity fixture with no autonomous-merge declared yields an advisory
   note, not a refusal (amended ADR-0029).
4. **Model-judged tier scores the prompt.** Precision, Scope-boundedness,
   Stop/escalation, Safety surface, and Internal-contradiction are scored via the
   expand-then-independent-review two-call pattern. Observable: an open-ended brief
   → `needs_tightening`; a secrets/deploy-touching brief → at least
   `needs_tightening` with the safety surface named.
5. **Human-owned approval + consumer contract.** The artifact starts
   `approval_status: proposed`; it is never auto-approved; a human flip to
   `approved` (the `approve` verb) is required. The skill exposes a `check`
   consumer contract — the deterministic gate a launcher will consult (023-02
   wires `loop.py` to it): `check <target> --prompt <brief>` exits **non-zero**
   (refuse) while the goal's artifact is missing or `proposed`, and **zero**
   (permit) once `approved`. `approve` refuses to flip an `unsafe_for_autonomy`
   verdict (fail-closed). Observable: `check` refuses before approval and permits
   after; approving an `unsafe_for_autonomy` artifact is refused.
6. **Boundary integrity.** When jig is co-installed, `clarify` / `frame_review` are
   reached by subprocess + filesystem only (no servo→jig import); absent jig, a
   built-in rubric is used. Observable: the co-installed path spawns a subprocess;
   the standalone path does not error.

**DoD:**
- [x] All ACs pass; test suite green (39 skill tests; full `skills`+`scripts`
      suite green; ruff `py39` clean; host packages in sync).
- [x] Each AC covered by ≥1 fixture; each new test shown capable of failing
      (blocker regression test proven red at returncode 1 without the fix).
- [x] Reviewed (compliance **pass** + craft **pass** after a blocker fix + arch
      **pass** — this slice adds a Compile-phase gate and the `check` contract).
- [x] Deviation log + reconciliation sweep recorded under this slice.

### Close-out (post-DONE)
- [ ] `docs/specs/README.md` regenerated (status-board).
- [ ] Skill surface documented; README/product-vision Compile-phase order updated
      to place readiness upstream of `edd-suitability`.

**Anti-horizontal-phasing check:** After this slice lands, a user can run
`autonomy-readiness` on a real goal and get an actionable, human-approvable
verdict that blocks an unattended start on a bad premise — end-to-end value even
before the loop is wired.

### Frame-critique follow-ups (from the 2026-08-06 pass)

Non-load-bearing notes the passing frame-critique surfaced. Both concern the
`loop.py` preflight wiring, so they are carried to **slice 023-02**:

1. **Launch-surface coverage assertion.** 023-02's regression guard proves the
   heartbeat *exemption* (a neither-flag `--prompt` run is not refused), not gate
   *coverage*. Pin the preflight to an explicit launch-surface set so a future
   third unattended long-horizon surface can't silently escape the gate; add a
   coverage assertion tied to that set.
2. **Routine recurrence re-verification (disclosed limit).** `--emit-routine-prompt`
   gates only at emit time; the emitted recurring Routine re-runs where the
   deterministic preconditions (clean tree, oracle freeze, mutation perimeter) are
   not re-verified per recurrence. Premise-quality checks still hold across
   recurrences; record this as a disclosed limit (candidate refinement-todo).

### Deviation log (after reconciliation)

1. **ADR-0029 amended before acceptance (4 frame-critique flaws).** The governing
   ADR was Proposed with four load-bearing frame flaws that five independent
   frame-critique passes caught and the author fixed before any code: identity
   check re-tiered from offline-deterministic to conditional/best-effort; the
   readiness preflight scoped off the spec-less heartbeat (ADR-0018); the
   loop.py-scoping given a concrete `--background` discriminator with a
   loop-layer regression guard; and the discriminator widened to BOTH unattended
   surfaces (`--background` + `--emit-routine-prompt`). Spec goals/ACs were
   realigned to match. Evidence: `docs/decisions/reviews/adr-0029-frame-critique.md`.
2. **Slice split 023-01 ⁄ 023-02.** AC5 originally required the `loop.py`
   `--background`/`--emit-routine-prompt` preflight in this slice. Wiring it here
   would fire on every existing loop.py test that exercises those flags (none
   carry a readiness artifact), destabilizing loop.py's large suite inside this
   slice. Per the spec's own anti-horizontal boundary ("value even before the
   loop is wired") and the 023-02 note, the loop.py wiring was split to a new
   **DEFERRED slice 023-02**; AC5 here was re-scoped to the skill-layer `check`
   consumer contract (a human runs readiness → `check` blocks/permits), which is
   the end-to-end value. spec-lint clean on both slices.
3. **jig reuse seam narrowed from spec goal 5.** Goal 5 / AC6 phrase the seam as
   "shell to jig `clarify` + `frame_review` (subprocess)". Per the DoR (mirror
   `eval-authoring._jig_independent_review_skill_path`), the implementation
   reaches jig only by *reading* `~/.claude/skills/clarify/SKILL.md` and splicing
   it as model-judge framing into servo's OWN `claude -p` call; `frame_review`
   is not invoked. The load-bearing invariant (no servo→jig import, subprocess +
   filesystem only) holds and is tested. Narrowing recorded here.
4. **Identity probe = `gh repo view --json viewerPermission`.** No host-identity
   probe existed (DoR). "Who can merge the base branch" maps to `viewerPermission`:
   ADMIN/WRITE/MAINTAIN → the run principal can merge (collapse, under declared
   autonomous-merge → `unsafe_for_autonomy`); READ/TRIAGE → a distinct identity
   must approve (separated). Best-effort/networked, mocked hermetically via
   `SERVO_AUTONOMY_READINESS_GH_BIN`.
5. **Three caps modeled as three checks** (`budget_cap`/`iteration_cap`/`candidate_cap`)
   rather than one, so each toggles the verdict independently (faithful to AC2).
6. **Craft-review blocker fixed + hardening (2026-08-06).** `_parse_scores`/
   `_parse_flags` could crash `analyze` with exit 1 on a braces-present-but-invalid
   model reply — fixed via `_load_model_json` → fail-closed `model_tier_unavailable`
   concern, with a regression test proven red without the fix. Folded in from the
   same review: partial-reply fail-close, a `schema_version` forward-compat guard
   in `load_artifact`, and closing the last uncaught-`OSError` (unreadable built-in
   rubric) so the "never exit 1" contract on the analyze path is total.

**Carried to 023-02** (recorded, not lost): the two launch surfaces' loop.py
wiring; the launch-surface coverage assertion + Routine-recurrence disclosed
limit (frame-critique follow-ups); and the `check`-vs-`approve` schema-guard
divergence (arch nit — `check` keeps its missing→exit-1 semantics, so it reads
directly rather than through `load_artifact`).

### Reconciliation sweep

| Artifact | Disposition | Rationale |
|----------|-------------|-----------|
| `docs/decisions/adr-0029-autonomy-readiness-gate.md` | `updated` | Amended (4 frame flaws) then **Accepted 2026-08-06**; frame-critique evidence recorded. |
| `docs/decisions/README.md` | `updated` | ADR-0029 index entry + reserved→Accepted narrative line. |
| `docs/architecture.md` | `updated` | Phase table gains the `autonomy-readiness` row as the first Compile step, upstream of `edd-suitability`. |
| `docs/product-vision.md` | `updated` | Unattended-execution prerequisites now name the autonomy-readiness gate (upstream of suitability). |
| `README.md` | `no-op` | The generic "Compile … into an oracle" line needs no change; skill enumeration is not maintained there. |
| `skills/autonomy-readiness/**` | `updated` | New skill: `readiness.py`, `SKILL.md`, `readiness-rubric.md`, tests, examples. |
| `hosts/claude/**`, `hosts/codex/**` | `updated` | Host packages rebuilt (`build_host_packages.py`); `--check` parity green. |
| `docs/refinement-todo.md` | `updated` | Routine-recurrence disclosed limit recorded. |
| `docs/specs/README.md` | `deferred` | Regenerated via `status-board` at DONE close-out (post-RECONCILED). |
| `.claude-plugin/install-contract.json` | `no-op` | Host/Compile-phase tool, plugin-discovered — deliberately absent from `required.skills` (asserted by `test_skill_surface.py`), mirroring `edd-suitability`. |
