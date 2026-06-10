---
status: DRAFT
dependencies: [004-01]
last_verified:
---

## Slice 004-02 — fail-open-safety

**Goal:** Make the meta-judge safe to leave installed in a live interactive
session: a misconfigured, missing, slow, or crashing oracle must **never trap the
session by blocking** — it fails **open** (lets the turn stop) and surfaces a
one-line warning to the *user* (not a block to Claude). This is the inverse of
agent-loop's fail-closed brakes and is the slice where the full meta-judge
decision table (block on below-threshold + fail-open on env-error + runaway
guard) is complete. End-to-end value: a developer can install the hook and trust
it can't deadlock their session, whatever state the oracle is in.

**DoR:**
- ✅ 004-01 DONE — the block-on-below-threshold + pass-silent + `stop_hook_active`
  paths exist and are tested.
- ✅ `gate.py`'s closed `reason` taxonomy (11 codes, ADR-0002) is the input; this
  slice maps **all** env-error reasons to one fail-open behavior.

**Acceptance Criteria:**

1. **env_error never blocks.** When `gate.py` returns `status=env_error`
   (exit 2) for any `reason` in the closed taxonomy (`manifest_missing`,
   `oracle_missing`, `oracle_not_executable`, `timeout`, `unexpected_exit`, …),
   the meta-judge writes **no** `decision: block`, exits 0, and the turn is
   allowed to stop.
2. **User-visible warning, not a Claude block.** On env_error the meta-judge
   surfaces a one-line warning to the user via `systemMessage` (e.g.
   `servo meta-judge: oracle env_error (reason=manifest_missing); not gating`).
   It does **not** put the env-error into `reason` (which would block) or into
   Claude's context.
3. **gate.py invocation failure fails open.** If `gate.py` itself can't be run
   (helper not found, non-0/1/2 exit, unparseable output, raised exception), the
   meta-judge treats it as fail-open (exit 0 + `systemMessage`), never block.
4. **Hook timeout is bounded and fail-open.** The meta-judge bounds its own
   `gate.py` call (so a hung oracle can't hang the turn-stop indefinitely); on
   that bound being hit it fails open with a `systemMessage`. The `settings.json`
   entry's `timeout` is set to a sane default and documented.
5. **Decision table is total.** Every `gate.py` outcome (pass / below_threshold /
   env_error / unparseable / crash) maps to exactly one meta-judge action per the
   [Core model](spec.md#core-model) table, with a test per row.
6. **ADR-0006 recorded.** The output contract + fail-open posture +
   one-nudge-per-sequence rule are captured in
   `docs/decisions/adr-0006-meta-judge-output-contract.md` (Accepted), and
   referenced from architecture.md "Decisions".

**DoD:**
- [ ] All ACs pass; full test suite green.
- [ ] Test coverage per AC (one test per decision-table row, incl. each
      env-error reason class).
- [ ] Reviewed by `reviewer` subagent (compliance + craft); ADR-0006 gets the
      arch pass (`arch_review: true` — it changes a public contract).
- [ ] Implementation review passed.
- [ ] Deviation log produced under this slice heading.
- [ ] Reconciliation review passed.
- [ ] `docs/refinement-todo.md` updated if any decisions were deferred.

### Close-out (post-DONE)
- [ ] [docs/specs/README.md](../README.md) status board updated.
- [ ] architecture.md "Decisions" table gains the ADR-0006 row.

**Anti-horizontal-phasing check:** After this slice the installed hook is safe
to leave on in a real session — the observable behavior change (a broken oracle
warns instead of trapping) is the value, delivered end-to-end through the script
the user already installed in 004-01.
