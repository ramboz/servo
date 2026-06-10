---
status: DONE
dependencies: []
last_verified: 2026-06-10
---

## Slice 004-01 — install-and-judge

**Goal:** The vertical minimum, spike-shaped: `hook.py install <target>` drops a
meta-judge script into `<target>/.servo/hooks/meta-judge.sh` and registers a
`Stop` hook in `<target>/.claude/settings.json`, and the meta-judge script —
when fed a `Stop` event on stdin — runs the scaffolded oracle via `gate.py` and
**blocks with a structured retry hint** when the oracle is below threshold,
**exits silently** when it passes, and **never runaway-blocks** (respects
`stop_hook_active`). End-to-end value: a user installs once and the next
below-threshold turn-stop is nudged with real oracle evidence — no human
remembering to run the gate. Spike-shaped because it validates the load-bearing
`Stop`-hook contract (Assumptions A1, A2, A4, A5) end-to-end.

**DoR:**
- ✅ Specs 001 (scaffold) + 002 (gate.py) DONE — the target has `oracle.sh` +
  `.servo/install.json` and `gate.py --json` is the truth-source.
- ✅ `Stop`-hook contract captured in [spec.md](spec.md) "Pre-spec research" +
  Assumptions; this slice is the escape hatch if live behavior contradicts it.
- ✅ Lean decisions pinned: no `jq` dependency (hand-roll the small fixed JSON);
  `install` refuses if the target is not servo-scaffolded.

**Acceptance Criteria:**

1. **Install places the script.** `hook.py install <target>` copies the
   meta-judge template to `<target>/.servo/hooks/meta-judge.sh` with the
   executable bit set. The template is servo-owned at
   `templates/meta-judge.sh.template`.
2. **Install registers the Stop hook.** `install` writes a `hooks.Stop[]` entry
   to `<target>/.claude/settings.json` whose `command` invokes the script via
   `$CLAUDE_PROJECT_DIR` (e.g. `"$CLAUDE_PROJECT_DIR"/.servo/hooks/meta-judge.sh`),
   `type: "command"`, with a bounded `timeout`. If `settings.json` does not
   exist, it is created with valid JSON; if `.claude/` does not exist, it is
   created.
3. **Install refuses an unscaffolded target.** If `<target>/.servo/install.json`
   or `<target>/oracle.sh` is absent, `install` refuses with a nonzero exit and a
   message pointing at `/servo:scaffold-init` (it does not write a half-install).
4. **Meta-judge blocks on below-threshold.** Given a `Stop` event on stdin
   (`stop_hook_active: false`) and a target whose oracle scores below threshold,
   the script emits `{"decision": "block", "reason": "<hint>"}` on stdout and
   exits 0. The `<hint>` names the composite and the threshold from
   `gate.py --json`; when the gate also reports `missing` components they are
   named too. (Per-component *failing-score* evidence is out of scope:
   `gate.py --json` exposes only `composite` / `threshold` / `missing`, and the
   stock oracle reports `missing` solely on its env-error path — so on a real
   below-threshold run the hint carries composite + threshold. Surfacing
   per-component scores on below-threshold is a deferred spec-002 enhancement;
   see [refinement-todo](../../refinement-todo.md).)
5. **Meta-judge passes silently.** Given the same stdin and a target whose oracle
   passes (`gate.py` exit 0), the script writes no `decision` and exits 0 (the
   turn is allowed to stop).
6. **Runaway guard.** Given stdin with `stop_hook_active: true`, the script exits
   0 without invoking the oracle (it never blocks twice in a sequence).
7. **No transcript read.** The script targets `$CLAUDE_PROJECT_DIR` for scoring
   and never reads `transcript_path` (asserted by a test that omits/garbles
   `transcript_path` and still gets correct behavior).
8. **Tested without a live Claude Code.** Tests drive the script by piping
   synthetic `Stop`-event JSON to its stdin and asserting stdout JSON + exit code
   (the mock-harness pattern from 003-01), and drive `gate.py` results via a
   scaffolded fixture target (or a stubbed `gate.py` on PATH).

**DoD:**
- [x] All ACs pass; full test suite green (642 passed, 1 skipped — the skip is
      the docker-less shellcheck case).
- [x] Test coverage per AC under `skills/oracle-hook/test_hook.py` (installer +
      synthetic-stdin script harness; 16 tests).
- [x] Reviewed by `reviewer` subagent (compliance + craft passes).
- [x] Implementation review passed (`jig:reviewer`: needs-changes → pass).
- [x] Deviation log produced under this slice heading.
- [x] Reconciliation review passed (inline).
- [~] Live-`Stop`-event confirmation of Assumptions A1/A2/A4/A5: contract
      docs-grounded + synthetic/real-gate validated, no contradiction; the true
      live-session check is **carried forward to the 004-05 dogfood** (recorded
      in the deviation log, not silently dropped).
- [x] [docs/refinement-todo.md](../../refinement-todo.md) updated (per-component
      hint-evidence enhancement deferred to spec-002).

### Close-out (post-DONE)
- [x] [docs/specs/README.md](../README.md) status board updated.
- [x] README skills-table row for `/servo:oracle-hook` flipped to IN PROGRESS.

**Anti-horizontal-phasing check:** After this slice a user can install the hook
and get a real, oracle-backed nudge on the next below-threshold turn — a working
end-to-end feature, not just a script on disk or a settings entry in isolation.

### Deviation log (after reconciliation)

Original ACs above are preserved (AC4 amended in-slice, see below). Implemented
2026-06-10; 16 tests in `skills/oracle-hook/test_hook.py`; full suite green.
New files: `skills/oracle-hook/hook.py` (`install` subcommand), the servo-owned
`templates/meta-judge.sh.template`, and `skills/oracle-hook/test_hook.py`.

- **Block-default contract (user-confirmed).** The v1 meta-judge defaults to
  `{"decision":"block","reason":…}` on below-threshold. The ROADMAP's shorthand
  ("emits retry hints as `additionalContext`") was imprecise — `additionalContext`
  is non-blocking (next-turn only), so it cannot make a meta-judge keep working.
  Block is the default; soft-context is a documented project knob (later slice).
- **Suppress-on-indeterminate runaway guard (review blocker #2).** The guard
  suppresses the nudge (exit 0, gate never invoked) when `stop_hook_active` is
  set **or cannot be parsed** from stdin; only a definitively-read
  `stop_hook_active: false` proceeds to score (an absent key = legit "first
  stop"). Biases toward never trapping a live session. Covered by
  `test_runaway_guard_suppresses_on_unparseable_stdin`.
- **AC4 amended (review blocker #1).** The below-threshold hint is scoped to
  `composite` + `threshold` (+ any `missing` the gate reports). Verified against
  `templates/oracle.sh.template`: the stock oracle emits `missing components`
  only on its **exit-2 (env_error)** path (it `exit 2`s before computing the
  composite), so on a real below-threshold (exit-1) nudge `gate.py`'s `missing`
  is always empty, and `gate.py --json` exposes no per-component scores.
  Per-component failing-score evidence is therefore a deferred **spec-002**
  `gate.py` enhancement (refinement-todo). The original test masked this by
  feeding the stub an impossible `below_threshold`+`missing:[…]` payload; it now
  uses the realistic shape, with a separate defensive test for the
  `missing`-present (custom-oracle) case. Spec.md Goal 3 / summary /
  open-questions and slice-05 AC5 were reconciled to drop the over-claim.
- **gate.py resolution + `SERVO_GATE_PY` seam.** `install` bakes a
  `$CLAUDE_PROJECT_DIR`-relative path to a vendored `servo-quality-gate/gate.py`
  when one exists in the target, else servo's own absolute `gate.py`; the script
  honors `SERVO_GATE_PY` first (test injection point + power-user override).
- **Zero extra dependencies (no `jq`).** All JSON parse/emit is inline `python3`
  (already required by `gate.py`).
- **Validate-before-write.** `install` checks manifest + `oracle.sh` +
  settings-parseable before any write (no half-install on refusal); a malformed
  `settings.json` refuses rather than clobbering (full backup/merge is 004-03).
- **Deferred to later slices (no over-reach):** env-error `systemMessage`
  warning → 004-02; idempotency/backup/merge-preservation **tests** → 004-03
  (a minimal marker-based dedup guard is present so dev re-installs don't
  duplicate, but it is not yet test-gated); `uninstall`/`status` → 004-04;
  SKILL.md + dogfood + `install-contract.json` entry → 004-05.
- **Nits dispositioned (reviewer concurred):** gate stderr is swallowed
  (`2>/dev/null`) because the user-facing diagnostic is 004-02's `systemMessage`;
  `_refuse` echoes a machine-readable `status=env_error reason=…` line to stdout
  mirroring `gate.py` house-style (the `/servo:scaffold-init` pointer is on
  stderr, satisfying AC3).
- **Live-`Stop`-event confirmation (Assumptions A1/A2/A4/A5) — NOT yet run
  against a live Claude Code session.** The contract was grounded via the
  official hooks docs (2026-06 probe) and validated against synthetic stdin + the
  real `gate.py` composition; no contradiction surfaced. A true live check
  (install into an interactive session; observe a `decision:block` nudge,
  `stop_hook_active=true` on the second stop, and `$CLAUDE_PROJECT_DIR`
  expansion) is carried forward to the 004-05 dogfood / spec-level DoD rather
  than claimed done here.

**Review:** `jig:reviewer` independent pass — first verdict **needs-changes**
(blocker #1 AC4 component-evidence gap; blocker #2 indeterminate-guard posture).
Both addressed; re-review verdict **pass** (AC4 amended-pass, AC6 pass).

**Reconciliation review (inline):** deviation log checked against the diff
(faithful); the AC4 amendment is a disclosed scope narrowing grounded in the
oracle/gate contract, not a silent one; spec/slice prose reconciled so no
"failing components" over-claim remains; slice-boundary discipline verified (no
004-02/03/04 surface implemented or tested here).
