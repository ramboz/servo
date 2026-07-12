---
status: DONE
dependencies: [003-05, adr-0003, adr-0025]
last_verified: 2026-07-12
arch_review: true
---

## Slice 021-02 - record and verify load-bearing assumptions

**Goal:** Have the runner RECORD its load-bearing assumptions in the verdict
block, and the judge VERIFY them. The loop is headless — there is no human to
answer a clarifying question — so instead of silently interpreting an ambiguous
prompt (the current "no clarifying questions" posture), the runner surfaces the
assumption it acted on, and the judge checks it against the code/oracle and
reflects the result in its verdict/reasoning. Amends the ADR-0003 verdict-block
contract; the field shape and any `schema_version` bump are decided in
[ADR-0025](../../decisions/adr-0025-runner-records-judge-verifies-assumptions.md).

**DoR:**
- [x] ADR-0025 is **Accepted** (decides the `assumptions:` field shape, whether
      it is optional under `schema_version: 1` or forces a bump to `2`, and how
      the judge reflects a violated assumption).

**Acceptance Criteria:**

1. **Runner records.** `agents/runner.md`'s verdict block carries an
   `assumptions:` field (shape/optionality exactly per ADR-0025), reconciled
   with `loop.py`'s strict `schema_version` parser so no valid block is refused.
2. **Runner posture amended.** The "No clarifying questions — make the most
   reasonable interpretation and proceed" guidance is updated to "surface the
   load-bearing assumption in the verdict block instead of silently interpreting."
3. **Judge verifies.** `agents/judge.md` instructs the judge to check the
   runner's recorded assumptions against the code and oracle output, and to
   reflect a violated/unsupported assumption in its verdict and reasoning.
4. **Parser compatibility.** `loop.py`'s `schema_version` refusal path is intact
   — no `verdict_schema_mismatch` regression; if ADR-0025 chooses a bump to
   `schema_version: 2`, `loop.py` accepts `2` and the tests prove both the
   accept and the still-refuse-on-missing-field paths.
5. **Tests.** Surface tests for the runner/judge prompt changes, plus a `loop.py`
   parse test for the new field (accept valid, refuse malformed).

**DoD:**
- [x] All ACs met; full suite green.
- [x] ADR-0025 Accepted and linked.
- [x] Reviewed (compliance + craft + arch, since the verdict-block contract
      changes); evidence recorded.
- [x] Deviation log + reconciliation sweep under this slice.

**Anti-horizontal-phasing check:** After this slice, a headless run's runner
emits the assumptions it relied on and the judge audits them — an observable,
end-to-end reliability change in the loop's own artifacts, not scaffolding for a
later slice.

### Deviation log (after reconciliation)

- **ADR-0025 chose the additive schema-v1 branch.** `assumptions:` is optional
  under `schema_version: 1`; no `schema_version: 2` bump was introduced.
- **Runner and judge prompts now use assumptions as the headless clarification
  channel.** The runner records only load-bearing interpretations in the optional
  `assumptions:` field; the judge verifies recorded assumptions against changed
  code and oracle output, reflecting unsupported/violated assumptions in its
  verdict and reasoning.
- **Compliance review caught insufficient malformed-input coverage.** Initial
  implementation proved valid `assumptions:` round-trip behavior but did not
  refuse malformed/multiline assumptions. `_parse_verdict_block` now refuses any
  non-empty verdict-block field line without `:` as
  `verdict_schema_mismatch`, preserving colon-shaped additive fields while
  preventing silent truncation.
- **Review provenance caveat.** Compliance and craft used jig review evidence;
  the compliance needs-change finding was fixed locally, and the arch pass used
  the installed arch-review rubric locally because the multi-agent thread cap
  prevented spawning another reviewer. The review files record that provenance.
- **Verification.** Focused verdict tests passed with
  `python3 -m unittest skills/agent-loop/test_loop.py -k RunnerVerdictBlockTests -k JudgeVerdictBlockTests -k VerdictSchemaMismatchTests -k ParseVerdictBlockUnitTests`
  (24 tests). Full suite passed with `python3 scripts/run_tests.py`
  (1535 tests).

### Reconciliation sweep

- **Agent prompts** — `updated`. `agents/runner.md` documents optional
  `assumptions:` in the runner verdict block and replaces silent ambiguity with
  load-bearing assumption recording; `agents/judge.md` verifies those
  assumptions.
- **Parser** — `updated`. `skills/agent-loop/loop.py` still requires
  `schema_version: 1` first and still refuses missing / wrong / quoted /
  non-integer schema versions; it now also refuses malformed non key/value lines
  inside a present verdict block.
- **Tests** — `updated`. `skills/agent-loop/test_loop.py` covers runner/judge
  prompt guidance, valid `assumptions:` parser/per-iteration JSON behavior, and
  malformed/multiline assumption refusal.
- **ADR index** — `updated`. ADR-0025 is Accepted and
  `docs/decisions/README.md` was regenerated by `adr.py index`.
- **Architecture** — `updated`. `docs/architecture.md` describes runner/judge as
  live prompts and notes spec 021's assumption-verification hardening.
- **Host packages** — `updated`. `python3 scripts/build_host_packages.py`
  regenerated Claude and Codex host package copies after prompt/parser changes.
- **Dependency metadata** — `updated`. `dependencies:` names the concrete
  shipped contract `003-05` instead of whole-spec `003`, matching jig's
  DONE-time dependency validator.
- **Review evidence** — `updated`. Compliance, craft, and arch verdicts are
  recorded in `docs/specs/021-headless-agent-investigation/reviews/`.
- **Status board** — `pending final regen` by this landing thread. Trigger:
  after `021-02` transitions to DONE, regenerate `docs/specs/README.md` once so
  the board reflects final spec 021 state.
