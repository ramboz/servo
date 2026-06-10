---
status: DONE
dependencies: [004-01]
last_verified: 2026-06-10
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
- [x] All ACs pass; full test suite green (648 passed, 1 skipped).
- [x] Test coverage per AC (one test per decision-table row + a subtest per
      env-error reason class) in `FailOpenSafetyTests`.
- [x] Reviewed by `reviewer` subagent (compliance + craft + ADR/arch
      considerations folded into one `jig:reviewer` pass per servo convention).
- [x] Implementation review passed (`jig:reviewer`: **pass** first time).
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed (inline).
- [x] `docs/refinement-todo.md` — no *new* deferral this slice (the
      per-component-hint enhancement was logged in 004-01).

### Close-out (post-DONE)
- [x] [docs/specs/README.md](../README.md) status board updated.
- [x] architecture.md "Decisions" table gains the ADR-0006 row (+ ADR-0005 row
      backfilled; pending-candidate hint renumbered to 0007).

**Anti-horizontal-phasing check:** After this slice the installed hook is safe
to leave on in a real session — the observable behavior change (a broken oracle
warns instead of trapping) is the value, delivered end-to-end through the script
the user already installed in 004-01.

### Deviation log (after reconciliation)

Implemented 2026-06-10; 6 new tests (`FailOpenSafetyTests`, incl. a 6-reason
subtest) in `skills/oracle-hook/test_hook.py`; full suite 648 passed, 1 skipped.
Changed: `templates/meta-judge.sh.template` (env-error `systemMessage` branch +
`--timeout`-bounded gate call); new `docs/decisions/adr-0006-meta-judge-output-contract.md`
(Accepted) wired into the decisions index + architecture.md.

- **Decision table completed.** The script's `if/elif/else` now routes: rc=0 →
  silent pass; rc=1 → block-with-hint; **everything else** (rc=2, non-0/1/2,
  uninvocable/unparseable gate) → fail open with a `{"systemMessage":…}` warning
  naming the gate `reason`. No non-`below_threshold` path can emit
  `decision:block`.
- **Gate call time-bounded.** `gate.py … --timeout "${SERVO_META_JUDGE_GATE_TIMEOUT:-45}"`.
  The 45s default is intentionally **below** the `settings.json` hook `timeout`
  (60s, `hook.py:DEFAULT_TIMEOUT`) so the gate's own timeout fires first and
  yields a clean rc=2/`reason=timeout` the fail-open path handles, rather than
  Claude Code abruptly killing the hook. AC4 only required "a sane default and
  documented"; the explicit `<` ordering is recorded in ADR-0006.
- **ADR-0006 scope.** Captures the full output contract (block-default,
  fail-open, one-nudge-per-sequence, hint content) — not just this slice's
  fail-open half — because the contract is consumed by 004-03..05 + installed
  projects + users (the `Stop`-hook analog of ADR-0002). Also backfilled the
  missing ADR-0005 (Proposed) row in architecture.md's Decisions table and
  renumbered the stale "oracle.sh stays bash" pending hint (was labelled 0005
  then 0006; both now taken → "a future ADR / 0007").
- **Reviewer nits dispositioned.** (a) gate stderr still `2>/dev/null`-swallowed
  — the `systemMessage` surfaces the machine `reason=` and points at
  `/servo:quality-gate` for the full stderr; folding the first stderr line in is
  a possible future enhancement, not blocking. (b) A crashing `gate.py` (Python
  exit 1) would be *routed* to the block branch, but its inner parser
  `sys.exit(0)`s on the resulting unparseable stdout → no malformed block
  emitted; fail-open is preserved by this second line of defense (reviewer
  `[strength]`). (c) Fixed the stale `test_fails_open_on_env_error` docstring
  (004-01 forward-reference) — the assertion itself remained valid.

**Review:** `jig:reviewer` independent pass — **pass** first time (all six ACs;
two `[strength]` callouts on the double-guarded fail-open; three cosmetic nits,
all dispositioned above).

**Reconciliation review (inline):** deviation log checked against the diff
(faithful); the 45s/60s timeout ordering is an ADR-recorded refinement of AC4,
not a silent scope change; slice-boundary discipline verified (`hook.py` still
`install`-only — no 004-03 backup/merge or 004-04 uninstall/status leaked in).
